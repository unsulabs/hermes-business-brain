#!/usr/bin/env python3
"""Import a VALIDATED vNext-0.9 handoff package: no raw sources, no external writes."""
from __future__ import annotations
import hashlib
import json
import re
import os
import tempfile
import shutil
from pathlib import Path
import yaml

try:  # engine core owns the canonical error type
    from .api import BrainError
except ImportError:  # pragma: no cover - engine core always present in v2
    class BrainError(Exception):
        """Hard engine error: the operation did not reach a success state."""


SCHEMA_NAME = 'Esquema_Manifiesto_vNext.schema.json'


def validator_check(manifest: Path) -> dict:
    manifest = manifest.expanduser().resolve()
    try:
        from .validador_de_traspaso import check
        errors, obj = check(manifest)
    except FileNotFoundError as exc:
        raise BrainError('Handoff cannot be validated: ' + str(exc)) from exc
    if errors:
        raise ValueError('Handoff rejected; contract errors:\n- ' + '\n- '.join(errors))
    return obj


def heading_link(block: dict, docs: dict) -> str:
    doc_id = block['doc_id']
    path = docs[doc_id]['_relative'].removesuffix('.md')
    heading = block.get('heading_path') or []
    if heading:
        # The title is for human navigation, not a guarantee of precise block identity.
        path += '#' + heading[-1].replace('|', '-')
    return f'[[{path}]] (`{block["block_id"]}`)'


def esc_cell(val) -> str:
    return str(val or '').replace('|', '\\|').replace('\n', ' ')


def control_document(sys_id: str, title: str, body: str) -> str:
    from .lib_ce import make_note
    return make_note({'id': sys_id, 'tipo': 'control', 'estado_editorial': 'borrador', 'sensibilidad': 'interno'}, f'# {title}\n\n{body.rstrip()}\n')


def collect_changes(manifest: Path, vault: Path, allow_real: bool = False) -> tuple[dict[Path, bytes], dict]:
    from .lib_ce import make_note, split_frontmatter, visible_filename
    manifest = manifest.expanduser().resolve()
    vault = vault.expanduser().resolve()
    if not vault.is_dir(): raise ValueError('Vault does not exist; run crear_instancia.py first')
    config_path = vault / '90_Sistema' / 'config_empresa.yaml'
    if not config_path.is_file(): raise ValueError('Vault not recognized: missing config_empresa.yaml')
    company = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    obj = validator_check(manifest)
    cid = obj['company']['id']
    if company.get('company_id') != cid:
        raise ValueError(f'Wrong company: vault is {company.get("company_id")}, package is {cid}')
    if not obj['company']['synthetic'] and not allow_real:
        raise ValueError('Real package: allow_real plus prior source authorization are required')
    # There is no per-user isolation inside Obsidian; import only shared internal material.
    protected = [(kind, item.get('doc_id') or item.get('source_id') or item.get('block_id') or item.get('id'))
                 for kind in ('documents', 'sources', 'blocks', 'restrictions')
                 for item in obj.get(kind, []) if item.get('access', 'interno') != 'interno']
    if protected:
        raise ValueError('Rejected: the prototype vault has no ACL. Protected material: ' + str(protected))
    trans_dir = vault / '90_Sistema' / 'Traspasos' / cid
    if trans_dir.exists():
        raise FileExistsError('This package already has a handoff record; not overwriting: ' + str(trans_dir))
    docs = {d['doc_id']: dict(d) for d in obj['documents']}
    locations = {}
    for doc_id, doc in docs.items():
        original = (manifest.parent / doc['path']).read_text(encoding='utf8')
        match = re.search(r'(?m)^# +(.+)$', original)
        label = match.group(1).strip() if match else 'Document ' + doc['doc_type']
        label = re.sub(r'^(?:D\d{2}|X\d{2}[-_A-Za-z0-9]+)\s*[--:-]\s*', '', label)
        doc['_relative'] = '10_Conocimiento/' + visible_filename(label)
        locations[doc_id] = doc['_relative']
    for source in obj['sources']:
        sid = source['source_id']
        label = source.get('title') or ('Source of ' + source['kind'] + ' - ' + sid)
        locations[sid] = '50_Fuentes/' + visible_filename(label)
    if len({p.casefold() for p in locations.values()}) != len(locations):
        raise ValueError('Duplicate titles in the handoff; distinguish topics before importing')
    blocks = {b['block_id']: b for b in obj['blocks']}
    rels_by_doc = {id: {} for id in docs}
    for rel in obj.get('relationships', []):
        a = blocks[rel['subject_id']]['doc_id']
        b = blocks[rel['object_id']]['doc_id']
        if a == b: continue
        pred = re.sub('[^a-z0-9_]', '_', rel['predicate'].lower())
        rels_by_doc[a].setdefault('rel_' + pred, set()).add(f'[[{locations[b].removesuffix(".md")}]]')
    changes = {}
    for doc_id, doc in docs.items():
        path = (manifest.parent / doc['path']).resolve()
        original = path.read_text(encoding='utf-8')
        existing, body = split_frontmatter(original)
        sources = sorted(set(s for b in obj['blocks'] if b['doc_id'] == doc_id for s in b.get('source_ids', [])) |
                         set(s for q in doc.get('coverage_by_question', []) for s in q.get('source_ids', [])))
        # Do not assume every block shares the same knowledge state or validity.
        fm = dict(existing)
        fm.update({'id': doc_id, 'doc_id': doc_id, 'tipo': 'documento', 'clase': doc['doc_type'],
                   'estado_editorial': doc['editorial_status'], 'fecha_corte': str(doc.get('as_of', '')),
                   'revision': str(doc.get('revision', '')), 'sensibilidad': doc['access'],
                   'huella_original_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'fuentes': [f'[[{locations[sid].removesuffix(".md")}]]' for sid in sources]})
        for key, values in sorted(rels_by_doc[doc_id].items()):
            fm[key] = sorted(values)
        # Explicit navigation for the reader; the original document facts are not duplicated.
        navigation = ['## Linked navigation (view derived from the handoff)', '',
                      '> This section is a link index; it is not new authority or business content.', '']
        for key, values in sorted(rels_by_doc[doc_id].items()):
            navigation.append(f'- **{key[4:]}:** ' + ', '.join(sorted(values)))
        if sources:
            navigation.append('- **Registered sources:** ' + ', '.join(f'[[{locations[sid].removesuffix(".md")}]]' for sid in sources))
        if not sources and not rels_by_doc[doc_id]:
            navigation.append('- No additional links declared in this handoff.')
        body = body.rstrip() + '\n\n' + '\n'.join(navigation) + '\n'
        changes[vault / locations[doc_id]] = make_note(fm, body).encode('utf-8')
    for source in obj['sources']:
        sid = source['source_id']
        fm = {'id': sid, 'tipo': 'fuente', 'clase_fuente': source['kind'], 'lectura': source['read_status'],
              'sensibilidad': source['access']}
        if source.get('event_date'): fm['fecha_evento'] = str(source['event_date'])
        body = f'# {Path(locations[sid]).stem}\n\n- **Original locator:** `{source["locator"]}`\n- **Captured:** {source["captured_at"]}\n- **Declared permitted uses:** {", ".join(source.get("permitted_uses", []))}\n\n> A **record card** is kept, not the source content. Verify permissions, context and availability in the original system.\n'
        changes[vault / locations[sid]] = make_note(fm, body).encode('utf-8')
    lines = ['| Origin (block) | Predicate | Destination (block) | State | Sources |', '|---|---|---|---|---|']
    for r in obj['relationships']:
        left, right = blocks[r['subject_id']], blocks[r['object_id']]
        fuentes = ', '.join(f'[[{locations[s].removesuffix(".md")}]]' for s in r.get('source_ids', []))
        lines.append(f'| {heading_link(left, docs)} | `{esc_cell(r["predicate"])}` | {heading_link(right, docs)} | {esc_cell(r["status"])} | {fuentes} |')
    mapa = make_note({'id': 'SYS-MAPA-RELACIONES', 'tipo': 'mapa', 'estado_editorial': 'borrador', 'sensibilidad': 'interno'}, '# Knowledge relations\n\n**Typed** contract connections; a section link does not replace the `kb:id` block identity.\n\n' + '\n'.join(lines) + '\n\nBack to [[Inicio]].\n')
    changes[vault / '00_Mapas' / 'Relaciones_de_conocimiento.md'] = mapa.encode('utf-8')
    lines = ['| Topic | Scope | Authority block | Validity | From | To |', '|---|---|---|---|---|---|']
    for a in obj.get('authorities', []):
        lines.append(f'| {esc_cell(a["topic_key"])} | {esc_cell(a["scope"])} | {heading_link(blocks[a["block_id"]], docs)} | {esc_cell(a["temporal_status"])} | {esc_cell(a.get("valid_from"))} | {esc_cell(a.get("valid_to"))} |')
    changes[vault / '90_Sistema' / 'Autoridades.md'] = control_document('SYS-AUTORIDADES', 'Explicit package authorities', '\n'.join(lines) + '\n\n**Not automatic authority resolution for any question:** apply context, access and evidence.').encode('utf-8')
    lines = ['| Pending | Question | Priority | Affected documents |', '|---|---|---|---|']
    for p in obj.get('pending', []):
        refs = ', '.join(f'[[{locations[d].removesuffix(".md")}]]' for d in p['affected_doc_ids'])
        lines.append(f'| {esc_cell(p["id"])} | {esc_cell(p["question"])} | {esc_cell(p["priority"])} | {refs} |')
    changes[vault / '90_Sistema' / 'Pendientes.md'] = control_document('SYS-PENDIENTES', 'Handoff pending items', '\n'.join(lines) + '\n\nThese gaps are not considered approved.').encode('utf-8')
    lines = ['| Test | Question | Expected blocks | Reported state |', '|---|---|---|---|']
    for t in obj['retrieval_tests']:
        links = ', '.join(heading_link(blocks[b], docs) for b in t['expected_block_ids'])
        lines.append(f'| {esc_cell(t["test_id"])} | {esc_cell(t["question"])} | {links} | **{esc_cell(t["result"])}** |')
    changes[vault / '90_Sistema' / 'Pruebas_de_recuperacion.md'] = control_document('SYS-PRUEBAS', 'Semantic retrieval tests', '\n'.join(lines) + '\n\nNO Obsidian or agent query tests were executed here.').encode('utf-8')
    lines = ['| Block | Knowledge | Editorial | Coverage | Validity | Support | From | Sources |', '|---|---|---|---|---|---|---|---|']
    for b in obj['blocks']:
        fuentes = ', '.join(f'[[{locations[s].removesuffix(".md")}]]' for s in b.get('source_ids', []))
        lines.append('| ' + ' | '.join(esc_cell(v) for v in [heading_link(b, docs), b['knowledge_state'], b['editorial_status'], b['coverage_state'], b['temporal_status'], b['support_class'], b.get('valid_from') or '', fuentes]) + ' |')
    changes[vault / '90_Sistema' / 'Estados_de_bloques.md'] = control_document('SYS-BLOQUES', 'Per-block states (four separate axes)', '\n'.join(lines)).encode('utf-8')
    from .lib_canvas import canvas_from_manifest
    changes[vault / '00_Mapas' / 'Mapa_de_relaciones.canvas'] = canvas_from_manifest(obj, locations).encode('utf-8')
    manifest_bytes = manifest.read_bytes()
    changes[trans_dir / 'manifest.json'] = manifest_bytes
    audit = f'# Structural import log\n\n- **Package:** `{cid}`\n- **Contract:** {obj["contract_version"]}\n- **Manifest SHA-256:** `{hashlib.sha256(manifest_bytes).hexdigest()}`\n- **Documents:** {len(docs)}\n- **Blocks:** {len(blocks)}\n- **Sources as references, without copying:** {len(obj["sources"])}\n- **Typed edges:** {len(obj["relationships"])}\n- **Pending retrieval tests:** {sum(t["result"] != "aprobada_humana" for t in obj["retrieval_tests"])}\n\nThe importer verifies structure with the 0.9 validator. **It does not validate meaning or actual usage rights.** Raw sources were neither read nor copied.\n'
    changes[trans_dir / 'Reporte.md'] = control_document('SYS-IMPORT-' + cid, 'Import log', audit.replace('# Structural import log\n\n', '', 1)).encode('utf-8')
    return changes, obj


# Exact text of the prior (legacy) template note, translated to English
# (schema keys preserved). Never accept an edited note that merely partially
# matches a phrase inside it.
LEGACY_RELATION_PLACEHOLDER = "---\nid: SYS-MAPA-RELACIONES\ntipo: mapa\nestado_editorial: borrador\nsensibilidad: interno\n---\n# Knowledge relationships\n\nThe vNext contract importer generates a map of typed relationships here from the manifest blocks. If no material has been imported yet, there are no relationships yet.\n\nBack to [[Inicio]].\n"


def _intact_relation_placeholder(original: str) -> bool:
    template = Path(__file__).resolve().parents[1] / "data" / "plantilla_boveda" / "00_Mapas" / "Relaciones_de_conocimiento.md"
    return original in (LEGACY_RELATION_PLACEHOLDER, template.read_text(encoding="utf8"))


def import_package(manifest: Path, vault: Path, allow_real: bool = False) -> dict:
    changes, obj = collect_changes(manifest, vault, allow_real)
    root = vault.resolve()
    placeholders = {'00_Mapas/Relaciones_de_conocimiento.md', '90_Sistema/Autoridades.md',
                    '90_Sistema/Pendientes.md', '90_Sistema/Pruebas_de_recuperacion.md'}
    for p in changes:
        if root not in p.parents: raise ValueError('Path outside the vault')
        if p.exists():
            rel = p.relative_to(root).as_posix()
            if rel not in placeholders: raise FileExistsError('Not overwriting existing destination: ' + str(p))
            old = p.read_text(encoding='utf-8')
            if rel == '00_Mapas/Relaciones_de_conocimiento.md':
                if not _intact_relation_placeholder(old): raise FileExistsError('Map already edited: ' + str(p))
            elif rel == '90_Sistema/Autoridades.md':
                if 'No manifest has been imported yet' not in old: raise FileExistsError('Authorities already edited')
            elif rel == '90_Sistema/Pendientes.md':
                if 'The system keeps gaps' not in old: raise FileExistsError('Pending items already edited')
            elif rel == '90_Sistema/Pruebas_de_recuperacion.md':
                if 'PENDING: test with a real agent' not in old: raise FileExistsError('Tests already edited')
    # Transactional as far as possible: preflight the whole batch, stage bytes,
    # commit and roll back on failure. No concurrency lock is provided.
    for p in changes:
        if any(parent.is_symlink() for parent in [p, *p.parents] if root == parent or root in parent.parents):
            raise ValueError('Destination path has a symbolic link: ' + str(p))
    original = {p: p.read_bytes() if p.exists() else None for p in changes}
    committed = []
    with tempfile.TemporaryDirectory(prefix='.ce-stage-', dir=root) as work:
        staging = Path(work)
        for i, (p, data) in enumerate(changes.items()):
            (staging / str(i)).write_bytes(data)
        try:
            for i, p in enumerate(changes):
                p.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / str(i), p)
                committed.append(p)
        except Exception:
            for p in reversed(committed):
                prev = original[p]
                if prev is None:
                    p.unlink(missing_ok=True)
                else:
                    p.write_bytes(prev)
            raise
    return {'empresa': obj['company']['id'], 'documentos': len(obj['documents']), 'bloques': len(obj['blocks']),
            'fuentes_referenciadas': len(obj['sources']), 'relaciones': len(obj['relationships']),
            'pruebas_semanticas_pendientes': sum(t['result'] != 'aprobada_humana' for t in obj['retrieval_tests'])}
