"""vNext semantic relations canvas; derived visualization, not a source of truth."""
from __future__ import annotations
import json


def canvas_from_manifest(manifest: dict, paths_by_id: dict[str, str] | None = None) -> str:
    blocks = {b['block_id']: b for b in manifest['blocks']}
    doc_ids = [d['doc_id'] for d in manifest['documents']]
    source_ids = [s['source_id'] for s in manifest['sources']]
    nodes = []
    edges = []
    seen = set()
    for i, doc_id in enumerate(doc_ids):
        nodes.append({'id': 'doc-' + doc_id, 'type': 'file', 'file': (paths_by_id or {}).get(doc_id, f'10_Conocimiento/{doc_id}.md'),
                      'x': 0, 'y': i * 310, 'width': 370, 'height': 250})
    for i, source_id in enumerate(source_ids):
        nodes.append({'id': 'src-' + source_id, 'type': 'file', 'file': (paths_by_id or {}).get(source_id, f'50_Fuentes/{source_id}.md'),
                      'x': 900, 'y': i * 310 + 170, 'width': 350, 'height': 240})
    for r in manifest.get('relationships', []):
        a = blocks[r['subject_id']]['doc_id']
        b = blocks[r['object_id']]['doc_id']
        if a == b: continue
        key = (a, r['predicate'], b)
        if key in seen: continue
        seen.add(key)
        edges.append({'id': f'edge-rel-{len(edges)+1}', 'fromNode': 'doc-' + a,
                      'toNode': 'doc-' + b, 'label': r['predicate'], 'toEnd': 'arrow'})
    for b in manifest['blocks']:
        for source_id in b.get('source_ids', []):
            key = (b['doc_id'], 'fuente', source_id)
            if key in seen: continue
            seen.add(key)
            edges.append({'id': f'edge-source-{len(edges)+1}', 'fromNode': 'doc-' + b['doc_id'],
                          'toNode': 'src-' + source_id, 'label': 'sustentado_por', 'toEnd': 'arrow'})
    return json.dumps({'nodes': nodes, 'edges': edges}, ensure_ascii=False, indent=2) + '\n'
