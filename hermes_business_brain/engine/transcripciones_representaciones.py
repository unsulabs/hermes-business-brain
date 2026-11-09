"""Verified auxiliary views; canonical originals and conversation identity stay intact.

Input hashes must come from the caller's sealed receipt/review, not from this
importer's reading of an untrusted sidecar. Provider labels are never identities.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .transcripciones_custodia import load_catalog
from .transcripciones_modelo import (
    ModelError,
    atomic_write,
    bank_lock,
    json_bytes,
    load_json,
    read_bytes,
    result,
    safe_id,
    safe_path,
    sha256_bytes,
    validate_bank_location,
    validate_record,
)
from .transcripciones_permisos import authorized, permission_snapshot


def _require_permission(bank, tr_id, version_id, company, audience):
    if not authorized(bank, tr_id, version_id, company, audience, 'local_analysis'):
        raise ModelError('PERMISSION_DENIED')


def _parse_json(data):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ModelError('INVALID_JSON')
            obj[key] = value
        return obj
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ModelError('INVALID_JSON')))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelError('INVALID_JSON') from exc


def _time(header):
    # Only a delimited terminal HH:MM:SS token is unambiguous. Concatenated
    # provider initials/numbers, MM:SS and timestamps with other syntax stay null.
    match = re.search(r'(?:^|\s)(\d{2}):([0-5]\d):([0-5]\d)$', header)
    return sum(int(v) * scale for v, scale in zip(match.groups(), (3600, 60, 1))) if match else None


def _mapping(dom, raw, headered):
    if not isinstance(dom, dict) or not isinstance(dom.get('groups'), list) or not dom['groups']:
        raise ModelError('REPRESENTATION_STRUCTURE_INVALID')
    groups, sentences, raw_parts, header_parts, seen = [], [], [], [], set()
    raw_cursor = header_cursor = 0
    for gi, group in enumerate(dom['groups']):
        if (not isinstance(group, dict) or not isinstance(group.get('header'), str)
                or not isinstance(group.get('sentences'), list) or not group['sentences']):
            raise ModelError('REPRESENTATION_STRUCTURE_INVALID')
        header = group['header']
        if gi:
            header_cursor += 2  # LF LF between provider groups
        group_header_start = header_cursor
        header_cursor += len(header.encode('utf-8')) + 1
        group_raw_start = raw_cursor
        texts = []
        for si, sentence in enumerate(group['sentences']):
            if (not isinstance(sentence, dict) or any(not isinstance(sentence.get(k), str)
                    or not sentence[k] for k in ('id', 'source_id', 'text'))):
                raise ModelError('REPRESENTATION_STRUCTURE_INVALID')
            if sentence['id'] in seen:
                raise ModelError('PROVIDER_SENTENCE_ID_DUPLICATE')
            seen.add(sentence['id'])
            text = sentence['text']
            size = len(text.encode('utf-8'))
            if raw_parts:
                raw_cursor += 1
            if si:
                header_cursor += 1
            if si == 0:
                group_raw_start = raw_cursor
            sentences.append(dict(ordinal=len(sentences), group_ordinal=gi,
                provider_sentence_id=sentence['id'], provider_source_id=sentence['source_id'],
                raw_start=raw_cursor, raw_end=raw_cursor + size,
                headered_start=header_cursor, headered_end=header_cursor + size,
                text_sha256=sha256_bytes(text.encode('utf-8'))))
            raw_cursor += size
            header_cursor += size
            raw_parts.append(text)
            texts.append(text)
        header_parts.append(header + '\n' + '\n'.join(texts))
        groups.append(dict(ordinal=gi, provider_header=header, time_seconds=_time(header),
            attribution_state='etiqueta_proveedor_sin_resolver', resolved_entity_id=None,
            raw_start=group_raw_start, raw_end=raw_cursor,
            headered_start=group_header_start, headered_end=header_cursor))
    if '\n'.join(raw_parts).encode('utf-8') != raw:
        raise ModelError('RAW_RECONSTRUCTION_MISMATCH')
    if '\n\n'.join(header_parts).encode('utf-8') != headered:
        raise ModelError('HEADERED_RECONSTRUCTION_MISMATCH')
    if dom.get('sha256') != sha256_bytes(raw) or dom.get('with_speakers_sha256') != sha256_bytes(headered):
        raise ModelError('HASH_MISMATCH')
    if 'sentence_count' in dom and (type(dom['sentence_count']) is not int or dom['sentence_count'] != len(sentences)):
        raise ModelError('REPRESENTATION_STRUCTURE_INVALID')
    for label, item in [('first', dom['groups'][0]['sentences'][0]), ('last', dom['groups'][-1]['sentences'][-1])]:
        if label in dom and dom[label] != item:
            raise ModelError('REPRESENTATION_STRUCTURE_INVALID')
    return groups, sentences


def _prepare(bank, tr_id, version_id, artifacts, expected_hashes, company, audience):
    validate_bank_location(bank)
    safe_id(tr_id)
    safe_id(version_id)
    _require_permission(bank, tr_id, version_id, company, audience)
    if (not isinstance(artifacts, dict) or not isinstance(expected_hashes, dict)
            or set(artifacts) != set(expected_hashes)
            or not {'dom_source', 'with_speakers'} <= set(artifacts)):
        raise ModelError('ARTIFACTS_INVALID')
    for role in artifacts:
        safe_id(role)
        if not isinstance(expected_hashes[role], str) or not re.fullmatch('[a-f0-9]{64}', expected_hashes[role]):
            raise ModelError('HASH_INVALID')
    row = next((r for r in load_catalog(bank) if r['tr_id'] == tr_id), None)
    if row is None or version_id not in row['version_ids']:
        raise ModelError('VERSION_REFERENCE_INVALID')
    original = load_json(safe_path(bank, f'versiones/{version_id}.json'))
    raw = read_bytes(bank, original['blob_path'])
    validate_record('original', original, lambda _: raw)
    payloads, artifact_records = {}, {}
    for role, path in sorted(artifacts.items()):
        path = Path(path).absolute()
        data = read_bytes(path.parent, path.name)
        digest = sha256_bytes(data)
        if digest != expected_hashes[role]:
            raise ModelError('HASH_MISMATCH')
        dest = f'representaciones/blobs/{digest}.bin'
        payloads[dest] = data
        artifact_records[role] = dict(path=dest, sha256=digest, byte_length=len(data),
                                      source_path=str(path))
    dom = _parse_json(payloads[artifact_records['dom_source']['path']])
    if not isinstance(dom, dict) or dom.get('meeting_id') not in {o['provider_meeting_id'] for o in row['occurrences']}:
        raise ModelError('PROVIDER_MEETING_MISMATCH')
    groups, sentences = _mapping(dom, raw, payloads[artifact_records['with_speakers']['path']])
    manifest = dict(schema_version='representacion.v1', producer_version='representaciones-1',
        tr_id=tr_id, version_id=version_id, raw_sha256=original['sha256'],
        reconstruction='provider-groups-lf-v1', artifacts=artifact_records,
        authorization=dict(company=company, audience=audience, purpose='local_analysis',
                           permission_snapshot=permission_snapshot(bank)),
        groups=groups, sentences=sentences)
    manifest['representation_id'] = 'REP-' + sha256_bytes(json_bytes(manifest))
    validate_record('representacion', manifest)
    return manifest, payloads


def importar_representacion(bank, tr_id, version_id, artifacts, expected_hashes, *, company, audience, commit=False):
    """Verify exact caller-pinned bytes; append blobs then manifest under bank lock.

    A crash before the manifest leaves only unreferenced blobs; repeating the same
    call completes safely. No raw version, preference or catalog row is created.
    """
    def run():
        manifest, payloads = _prepare(bank, tr_id, version_id, artifacts, expected_hashes, company, audience)
        path = f"representaciones/manifests/{manifest['representation_id']}.json"
        exists = safe_path(bank, path).exists()
        if exists:
            if read_bytes(bank, path) != json_bytes(manifest):
                raise ModelError('IMMUTABLE_CONFLICT')
            for blob, data in payloads.items():
                if read_bytes(bank, blob) != data:
                    raise ModelError('HASH_MISMATCH')
        if commit:
            for blob, data in payloads.items():
                atomic_write(bank, blob, data)
            atomic_write(bank, path, json_bytes(manifest))  # visibility last
        return result('importar-representacion', input_hashes=sorted(expected_hashes.values()),
            outputs=[dict(path=path, sha256=sha256_bytes(json_bytes(manifest)))],
            evidence=dict(representation_id=manifest['representation_id'], tr_id=tr_id,
                version_id=version_id, sentence_count=len(manifest['sentences']),
                group_count=len(manifest['groups']), committed=commit, idempotent=exists))
    if commit:
        with bank_lock(bank):
            return run()
    return run()


import_representation = importar_representacion
