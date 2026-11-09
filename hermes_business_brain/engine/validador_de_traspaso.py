"""Validator for the vNext 0.9 contract: schema, IDs, references, paths and blocks.
It does NOT test that the business content is true nor that an agent performs
semantic retrieval.
Usage: python validador_de_traspaso.py Ejemplo_Manifiesto_Traspaso.json
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import jsonschema


def _schema_path(manifest: Path) -> Path:
    """Schema resolution: next to the manifest (upstream layout) first, then the
    engine's shipped contract copy (data/contratos/vNext-0.9/)."""
    nearby = manifest.parent / 'Esquema_Manifiesto_vNext.schema.json'
    if nearby.is_file():
        return nearby
    shipped = (Path(__file__).resolve().parents[1] / 'data' / 'contratos'
               / 'vNext-0.9' / 'Esquema_Manifiesto_vNext.schema.json')
    if shipped.is_file():
        return shipped
    raise FileNotFoundError(
        'Esquema_Manifiesto_vNext.schema.json is missing next to the manifest '
        'and from the engine data (data/contratos/vNext-0.9/); add it before '
        'validating the handoff')


def check(path: Path):
    errors = []
    root = path.parent.resolve()
    schema = json.loads(_schema_path(path).read_text(encoding='utf-8'))
    obj = json.loads(path.read_text(encoding='utf-8'))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors += [f'SCHEMA {"/".join(map(str, e.path))}: {e.message}' for e in validator.iter_errors(obj)]
    docs = {x['doc_id']: x for x in obj.get('documents', []) if 'doc_id' in x}
    sources = {x['source_id']: x for x in obj.get('sources', []) if 'source_id' in x}
    blocks = {x['block_id']: x for x in obj.get('blocks', []) if 'block_id' in x}

    def unique(coll, key):
        values = [x.get(key) for x in obj.get(coll, [])]
        for val, c in Counter(values).items():
            if c > 1:
                errors.append(f'DUPLICATE {coll}.{key}={val}')
    for coll, key in [('documents', 'doc_id'), ('sources', 'source_id'), ('blocks', 'block_id'),
                      ('pending', 'id'), ('retrieval_tests', 'test_id')]:
        unique(coll, key)

    def secure_rel(rel, context):
        p = Path(rel)
        if p.is_absolute() or '..' in p.parts or not p.parts:
            errors.append(f'UNSAFE PATH {context}: {rel}')
            return None
        target = (root / p).resolve()
        if root not in target.parents:
            errors.append(f'ESCAPE PATH {context}: {rel}')
            return None
        if not target.is_file():
            errors.append(f'MISSING FILE {context}: {rel}')
            return None
        return target
    for doc in obj.get('documents', []):
        p = secure_rel(doc['path'], 'document')
        if doc.get('doc_type') != doc['doc_id'].split('-')[0]:
            errors.append('TYPE mismatch ' + doc['doc_id'])
        if p:
            data = p.read_bytes()
            content = data.decode('utf-8', errors='replace')
            if doc.get('checksum_sha256') and doc['checksum_sha256'] != hashlib.sha256(data).hexdigest():
                errors.append(f'HASH document {doc["doc_id"]}')
            if not re.search(r'^doc_id:\s*[\x27\x22]?' + re.escape(doc['doc_id']) + r'[\x27\x22]?\s*$', content, re.M):
                errors.append(f'MARKDOWN DOC_ID {doc["doc_id"]}')
        for q in doc.get('coverage_by_question', []):
            for sid in q.get('source_ids', []):
                if sid not in sources:
                    errors.append('MISSING COVERAGE SOURCE ' + sid)
    for src in obj.get('sources', []):
        loc = src['locator']
        if loc.startswith('Ejemplo_sintetico/') or loc.startswith('docs/'):
            p = secure_rel(loc, 'source')
            if p and src.get('checksum_sha256') and src['checksum_sha256'] != hashlib.sha256(p.read_bytes()).hexdigest():
                errors.append('HASH source ' + src['source_id'])
        # Remote production locators are not required to resolve to a local path.
    docpaths = {x['doc_id']: secure_rel(x['path'], 'block-parent') for x in obj.get('documents', [])}
    for b in obj.get('blocks', []):
        if b['doc_id'] not in docs:
            errors.append('ORPHAN BLOCK ' + b['block_id'])
            continue
        p = docpaths.get(b['doc_id'])
        if p and '<!-- kb:id=' + b['block_id'] + ' -->' not in p.read_text(encoding='utf-8'):
            errors.append('MISSING BLOCK ANCHOR ' + b['block_id'])
        for sid in b.get('source_ids', []):
            if sid not in sources:
                errors.append('ORPHAN SOURCE ' + sid)
        if b.get('supersedes') and b['supersedes'] not in blocks:
            errors.append('BAD SUPERSEDES ' + b['block_id'])
        start, end = b.get('valid_from'), b.get('valid_to')
        if start and end and start > end:
            errors.append('REVERSED VALIDITY ' + b['block_id'])
    for a in obj.get('authorities', []):
        b = blocks.get(a['block_id'])
        if b is None or b['doc_id'] != a['doc_id']:
            errors.append('BAD AUTHORITY ' + a['topic_key'])
        if a['doc_id'] not in docs:
            errors.append('BAD AUTHORITY DOC ' + a['topic_key'])
    aa = [x for x in obj.get('authorities', []) if x['temporal_status'] == 'vigente']
    for i, a in enumerate(aa):
        for b in aa[i + 1:]:
            if (a['topic_key'], a['scope']) != (b['topic_key'], b['scope']):
                continue
            if (a.get('valid_to') or '9999-12-31') >= (b.get('valid_from') or '0001-01-01') and (b.get('valid_to') or '9999-12-31') >= (a.get('valid_from') or '0001-01-01'):
                errors.append('CONFLICTING ACTIVE AUTHORITIES ' + a['topic_key'] + ' ' + a['scope'])
    for rel in obj.get('relationships', []):
        if rel['subject_id'] not in blocks:
            errors.append('BAD EDGE SUBJECT ' + rel['subject_id'])
        if rel['object_id'] not in blocks:
            errors.append('BAD EDGE OBJECT ' + rel['object_id'])
        for sid in rel['source_ids']:
            if sid not in sources:
                errors.append('BAD EDGE SOURCE ' + sid)
    for t in obj.get('retrieval_tests', []):
        for b in t['expected_block_ids']:
            if b not in blocks:
                errors.append('BAD TEST BLOCK ' + b)
        for src in t['expected_source_ids']:
            if src not in sources:
                errors.append('BAD TEST SOURCE ' + src)
    for p in obj.get('pending', []):
        for d in p['affected_doc_ids']:
            if d not in docs:
                errors.append('BAD PENDING DOC ' + d)
    for h in obj.get('historicals', []):
        if h['block_id'] not in blocks:
            errors.append('BAD HISTORY BLOCK ' + h['block_id'])
        if h.get('replaced_by') and h['replaced_by'] not in blocks:
            errors.append('BAD HISTORY REPLACEMENT ' + h['block_id'])
    for r in obj.get('restrictions', []):
        if r['target_id'] not in set(blocks) | set(docs) | set(sources):
            errors.append('BAD RESTRICTION TARGET ' + r['target_id'])
    return errors, obj


if __name__ == '__main__':
    p = Path(sys.argv[1] if len(sys.argv) > 1 else 'Ejemplo_Manifiesto_Traspaso.json')
    errors, obj = check(p)
    if errors:
        print('FAIL — ' + str(len(errors)) + ' error(s)')
        print('\n'.join(errors))
        sys.exit(1)
    print('PASS — JSON Schema, references, hashes, paths, authority and block anchors')
    print('NOTE: ' + str(sum(x['result'] != 'aprobada_humana' for x in obj['retrieval_tests'])) +
          ' semantic retrieval test(s) NOT validated: they require the Step 2 agent')
