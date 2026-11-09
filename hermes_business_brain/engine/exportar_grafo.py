#!/usr/bin/env python3
"""Export a JSON graph of contract-typed edges and wiki links of notes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .lib_ce import notes_in_vault, split_frontmatter, target_index, wiki_targets, resolve_link


def graph(vault: Path) -> dict:
    vault = vault.resolve()
    paths, names = target_index(vault)
    node_by_path = {}
    nodes, edges = [], []
    for p in notes_in_vault(vault):
        fm, _ = split_frontmatter(p.read_text(encoding='utf-8'))
        node_id = str(fm.get('id') or p.stem)
        node_by_path[p] = node_id
        nodes.append({'id': node_id, 'tipo': str(fm.get('tipo') or ''), 'ruta': str(p.relative_to(vault))})
    edge_keys = set()

    def add(src, pred, dst, layer, sources=None):
        if not src or not dst: return
        sources = sources or []
        key = (src, pred, dst, layer, tuple(sources))
        if key in edge_keys: return
        edge_keys.add(key)
        edges.append({'origen': src, 'predicado': pred, 'destino': dst, 'capa': layer, 'fuentes': sources})
    for p in notes_in_vault(vault):
        text = p.read_text(encoding='utf-8')
        fm, _ = split_frontmatter(text)
        source_id = node_by_path[p]
        for k, vals in fm.items():
            if not str(k).startswith('rel_') and k != 'fuentes': continue
            pred = k[4:] if k.startswith('rel_') else 'cita_fuente'
            for target in wiki_targets('\n'.join(vals) if isinstance(vals, list) else str(vals)):
                dest_path = resolve_link(target, paths, names)
                if dest_path: add(source_id, pred, node_by_path[dest_path], 'propiedad')
        for target in wiki_targets(text):
            dest_path = resolve_link(target, paths, names)
            if dest_path and dest_path != p: add(source_id, 'enlaza', node_by_path[dest_path], 'navegacion')
    manifests = sorted((vault / '90_Sistema' / 'Traspasos').glob('*/manifest.json'))
    for manifest in manifests:
        obj = json.loads(manifest.read_text(encoding='utf-8'))
        for b in obj.get('blocks', []):
            nodes.append({'id': b['block_id'], 'tipo': 'bloque', 'parent_id': b['doc_id'],
                          'conocimiento': b['knowledge_state'], 'vigencia': b['temporal_status'],
                          'editorial': b['editorial_status'], 'cobertura': b['coverage_state']})
            add(b['block_id'], 'pertenece_a', b['doc_id'], 'contrato')
            for s in b.get('source_ids', []): add(b['block_id'], 'sustentado_por', s, 'contrato')
        for r in obj.get('relationships', []):
            add(r['subject_id'], r['predicate'], r['object_id'], 'contrato', r.get('source_ids', []))
        for authority in obj.get('authorities', []):
            add(authority['block_id'], 'autoridad_en_' + authority['topic_key'], authority['doc_id'], 'contrato')
    # Distinguish reviewer-ratified links from mere proposals.
    from .relaciones import query as local_relations
    for relation in local_relations(vault)["relaciones"]:
        layer = ('local_ratificada_por_revisor' if relation["estado_efectivo"] == "validada_por_revisor"
                 else 'local_propuesta')
        add(relation["origen_id"], relation["predicado"], relation["destino_id"],
            layer, relation["fuentes"])
    return {'grafo_version': '0.1', 'empresa': vault.name, 'nodos': nodes, 'aristas': edges,
            'nota': 'Projection of navigation and declared edges. Not an inference engine nor access control.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vault', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    obj = graph(a.vault)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'GRAFO: {len(obj["nodos"])} nodes / {len(obj["aristas"])} edges: {a.output}')


if __name__ == '__main__':
    main()
