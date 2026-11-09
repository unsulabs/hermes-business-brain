"""Proposed, source-grounded dataset candidates. Never trains or grants rights.

The manifest publishes last; grouping control stays in a separate private ledger.
Grouping attestations are operator supplied; they are not inferred identities.
"""
from copy import deepcopy
from secrets import token_hex

from .transcripciones_custodia import load_catalog
from .transcripciones_lectura import guarded_read, live_reads
from .transcripciones_modelo import (
    ModelError,
    atomic_write,
    bank_lock,
    json_bytes,
    load_json,
    read_bytes,
    result,
    safe_path,
    sha256_bytes,
    validate_bank_location,
    validate_record,
)
from .transcripciones_permisos import authorized
from .transcripciones_permisos import permission_snapshot as snapshot


def _refs(selection):
    return sorted({(p['tr_id'], p['version_id']) for c in selection['candidates']
                   for p in c['passages']})


def _manifests(bank):
    folder = safe_path(bank, 'datasets')
    for path in sorted(folder.glob('DS-*.json')) if folder.exists() else []:
        manifest = load_json(path)
        validate_record('dataset-manifest', manifest)
        payload = {k: v for k, v in manifest.items() if k != 'export_id'}
        if manifest['export_id'] != 'DS-' + sha256_bytes(json_bytes(payload)) or path.stem != manifest['export_id']:
            raise ModelError('DATASET_HASH_MISMATCH')
        control = load_json(safe_path(bank, f"datasets-control/{manifest['export_id']}.json"))
        validate_record('dataset-control', control)
        if (sha256_bytes(json_bytes(control)) != manifest['control_commitment'] or
                any(control[k] != manifest[k] for k in ('company', 'audience', 'purpose'))):
            raise ModelError('DATASET_CONTROL_MISMATCH')
        # Internal only: never copy this envelope into the returned/exported payload.
        yield dict(manifest, _control=control)


def _groups(bank, selection, previous):
    rows = {r['tr_id']: r for r in load_catalog(bank)}
    identities = selection['identities']
    if set(identities) != set(rows):
        raise ModelError('GROUP_COVERAGE_REQUIRED')
    for old in previous:
        for tr, identity in old['_control']['identities'].items():
            if identities.get(tr) != identity:
                raise ModelError('GROUP_IDENTITY_CHANGED')
    parent = {tr: tr for tr in rows}
    def root(tr):
        while parent[tr] != tr:
            tr = parent[tr]
        return tr
    seen, originals = {}, {}
    for tr, row in rows.items():
        identity = identities[tr]
        if any(identity[k] == 'unknown' for k in ('client', 'project')):
            raise ModelError('GROUP_IDENTITY_UNKNOWN')
        keys = [(k, identity[k]) for k in ('client', 'project') if identity[k] is not None]
        for version in row['version_ids']:
            original = load_json(safe_path(bank, f'versiones/{version}.json'))
            validate_record('original', original)
            originals[(tr, version)] = original
            keys.append(('sha256', original['sha256']))
        for key in keys:
            if key in seen:
                parent[root(tr)] = root(seen[key])
            seen[key] = tr
    return rows, originals, {tr: root(tr) for tr in rows}


@guarded_read
def _prepare(bank, selection, purpose, permission_snapshot, company, audience, *, control_nonce=None):
    validate_record('dataset-selection', selection)
    ids = [c['candidate_id'] for c in selection['candidates']]
    if not ids or len(ids) != len(set(ids)):
        raise ModelError('CANDIDATE_IDS_INVALID')
    if purpose not in ('evaluation', 'training'):
        raise ModelError('DATASET_PURPOSE_INVALID')
    refs = _refs(selection)
    actual = snapshot(bank, source_refs=refs, company=company, audience=audience, purpose=purpose)
    if actual != permission_snapshot:
        raise ModelError('PERMISSION_SNAPSHOT_CHANGED')
    allowed = {ref for ref in refs if authorized(bank, *ref, company, audience, purpose)}
    previous = list(_manifests(bank))
    rows, originals, groups = _groups(bank, selection, previous)
    used = {}
    # Prior exports remain reservations even after revocation: no laundering via
    # removing a permission or excluding a duplicate in the next request.
    for old in previous:
        for candidate in old['candidates']:
            for passage in candidate['passages']:
                group = groups[passage['tr_id']]
                if group in used and used[group] != old['purpose']:
                    raise ModelError('SPLIT_LEAKAGE')
                used[group] = old['purpose']
    candidates, excluded = [], []
    for item in selection['candidates']:
        item_refs = {(p['tr_id'], p['version_id']) for p in item['passages']}
        if not item_refs <= set(originals):
            raise ModelError('VERSION_REFERENCE_INVALID')
        if not item_refs <= allowed:
            excluded.append(dict(candidate_id=item['candidate_id'], reason='PERMISSION_DENIED'))
            continue
        for tr, version in item_refs:
            if used.get(groups[tr], purpose) != purpose:
                raise ModelError('SPLIT_LEAKAGE')
            if version != rows[tr]['version_ids'][-1] and not selection['allow_historical']:
                raise ModelError('HISTORICAL_FLAG_REQUIRED')
        candidate = deepcopy(item)
        for passage in candidate['passages']:
            original = originals[(passage['tr_id'], passage['version_id'])]
            raw = read_bytes(bank, original['blob_path'])
            validate_record('original', original, lambda _: raw)
            if passage['source_sha256'] != original['sha256']:
                raise ModelError('HASH_MISMATCH')
            start, end = passage['start'], passage['end']
            cs, ce = passage['context_start'], passage['context_end']
            if not 0 <= cs <= start < end <= ce <= len(raw):
                raise ModelError('PASSAGE_RANGE_INVALID')
            if (sha256_bytes(raw[start:end]) != passage['passage_sha256'] or
                    sha256_bytes(raw[cs:ce]) != passage['context_sha256']):
                raise ModelError('HASH_MISMATCH')
            try:
                # Decode boundaries individually to reject UTF-8 mid-codepoint offsets.
                raw[:cs].decode('utf-8'); raw[:start].decode('utf-8')
                passage['text'] = raw[start:end].decode('utf-8')
                passage['permitted_context'] = raw[cs:ce].decode('utf-8')
            except UnicodeDecodeError as exc:
                raise ModelError('PASSAGE_ENCODING_INVALID') from exc
        candidates.append(candidate)
    permitted_selection = deepcopy(selection)
    permitted_ids = {c['candidate_id'] for c in candidates}
    permitted_selection['candidates'] = [c for c in permitted_selection['candidates']
                                       if c['candidate_id'] in permitted_ids]
    del permitted_selection['identities']
    exported_refs = sorted({(p['tr_id'], p['version_id']) for c in candidates for p in c['passages']})
    control = dict(schema_version='dataset-control.v1', company=company, audience=audience,
                   purpose=purpose, identities=deepcopy(selection['identities']))
    if control_nonce is None:
        for old in previous:
            if {k:v for k,v in old['_control'].items() if k != 'nonce'} == control:
                control_nonce = old['_control']['nonce']
                break
    # A private random nonce prevents public commitments from becoming a
    # dictionary oracle for client/project IDs or evidence. It never leaves control.
    control['nonce'] = control_nonce or token_hex(32)
    validate_record('dataset-control', control)
    manifest = dict(schema_version='dataset-manifest.v2', status='proposed', purpose=purpose,
        company=company, audience=audience, permission_snapshot=snapshot(bank, source_refs=exported_refs,
            company=company, audience=audience, purpose=purpose),
        selection=permitted_selection, candidates=candidates, excluded=excluded,
        source_refs=[dict(tr_id=t, version_id=v) for t,v in exported_refs],
        control_commitment=sha256_bytes(json_bytes(control)),
        separation='conversation-all-versions-sha256-client-project', trained=False)
    manifest['export_id'] = 'DS-' + sha256_bytes(json_bytes(manifest))
    validate_record('dataset-manifest', manifest)
    return manifest, control


def prepare_export(selection, purpose, permission_snapshot, *, bank, company, audience, commit=False):
    """Preview by default; explicit commit seals one manifest in the private bank.

    Pass an exact scoped permission_snapshot over every selection passage source.
    No derived analysis inputs are accepted in v1. All narrative fields are
    proposed operator annotations, never expert ratification by this exporter.
    """
    validate_bank_location(bank)
    def run():
        with live_reads():
            manifest, control = _prepare(bank, selection, purpose, permission_snapshot, company, audience)
            path = f"datasets/{manifest['export_id']}.json"
            if commit:
                # Recompute immediately before the sole visibility/commit operation.
                check, check_control = _prepare(bank, selection, purpose, permission_snapshot, company, audience,
                                                control_nonce=control['nonce'])
                if manifest != check or control != check_control:
                    raise ModelError('SNAPSHOT_CHANGED')
                # Control is private and never an output. A crash here leaves an
                # orphan ignored by _manifests; only the final manifest reserves use.
                atomic_write(bank, f"datasets-control/{manifest['export_id']}.json", json_bytes(control))
                atomic_write(bank, path, json_bytes(manifest))
            return result('prepare-export', outputs=[dict(path=path,
                sha256=sha256_bytes(json_bytes(manifest)))], evidence=dict(
                committed=commit, manifest=manifest, trained=False))
    if commit:
        with bank_lock(bank):
            return run()
    return run()


def inspect_exports(*, bank):
    """Revalidate derived permissions without modifying immutable historical uses."""
    validate_bank_location(bank)
    with live_reads():
        reports = []
        for manifest in _manifests(bank):
            refs = {(p['tr_id'], p['version_id']) for c in manifest['candidates'] for p in c['passages']}
            denied = [dict(tr_id=t, version_id=v) for t,v in sorted(refs) if not authorized(
                bank, t, v, manifest['company'], manifest['audience'], manifest['purpose'])]
            reports.append(dict(export_id=manifest['export_id'], permission_current=not denied,
                                denied_sources=denied, reuse_requires_fresh_export=True))
        return reports
