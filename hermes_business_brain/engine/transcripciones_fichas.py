"""Read-only source notes and navigation proposals; never applies to a vault.

The caller supplies a verified vault snapshot and sensitivity attestations.
Unknown sensitivity remains restricted. Source permissions are always live.
"""
import re
from copy import deepcopy
from pathlib import Path

import yaml

from .transcripciones_custodia import load_catalog
from .transcripciones_destino import classification, destination, maximum
from .transcripciones_evolucion import END, START, transition, validate_view
from .transcripciones_modelo import (
    ModelError,
    json_bytes,
    load_json,
    read_bytes,
    safe_id,
    safe_path,
    sha256_bytes,
    validate_record,
)
from .transcripciones_permisos import authorized, permission_snapshot
from .transcripciones_pipeline import coverage_report, source
from .transcripciones_representaciones import _mapping, _parse_json


def _hash(value):
    return sha256_bytes(json_bytes(value))


def _front(text):
    if text.startswith('---\n') and '\n---\n' in text[4:]:
        return yaml.safe_load(text.split('\n---\n', 1)[0][4:]) or {}
    return {}


def _note(meta, body):
    return '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n' + body


def _literal(text):
    # Fence length follows data, so even malicious transcript Markdown is inert.
    fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', text)), default=0))
    return fence + 'text\n' + text + '\n' + fence + '\n'


def _text(value):
    return str(value).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ')


def _link(path, label, anchor=None):
    return '[[' + path + (('#' + anchor) if anchor else '') + '|' + label + ']]'


def _candidate(path, content, kind, identity, snapshot, **metadata):
    safe_path('/snapshot', path)
    old = snapshot.get(path)
    return dict(path=path, content=content, kind=kind, id=identity,
                expected_sha256=sha256_bytes(old.encode()) if old is not None else None,
                **metadata)


def batch_subjects(subjects, *, parent_id, max_subjects=30, max_units=30, max_bytes=90000):
    """Lossless parent/child work packets, NOT invented canonical note plans.

    Destinations are authored analysis decisions. A caller must turn these
    packets into business-justified plan-conocimiento inputs separately.
    """
    safe_id(parent_id)
    batches, current = [], []
    def packet(items, ordinal):
        return dict(parent_id=parent_id, batch_id=f'{parent_id}-{ordinal:04d}',
                    subjects=items, destination_ids=sorted({s['destination']['id'] for s in items}))
    for subject in subjects:
        trial = packet(current + [subject], len(batches) + 1)
        if (len(trial['subjects']) > max_subjects or len(trial['destination_ids']) > max_units
                or len(json_bytes(trial)) > max_bytes):
            if not current:
                raise ModelError('SUBJECT_EXCEEDS_BATCH_LIMIT')
            batches.append(packet(current, len(batches) + 1)); current = []
        current.append(deepcopy(subject))
        if len(json_bytes(packet(current, len(batches) + 1))) > max_bytes:
            raise ModelError('SUBJECT_EXCEEDS_BATCH_LIMIT')
    if current:
        batches.append(packet(current, len(batches) + 1))
    return dict(parent_id=parent_id, subject_ids=[s['subject_id'] for s in subjects],
                subject_count=len(subjects), batches=batches,
                canonical_units_generated=False, planner_validation='pending_authored_architecture')


def _representations(bank, tr, version, raw, scope):
    results = []
    folder = safe_path(bank, 'representaciones/manifests')
    for path in sorted(folder.glob('*.json')) if folder.exists() else []:
        rep = load_json(path)
        if (rep.get('tr_id'), rep.get('version_id')) != (tr, version):
            continue
        validate_record('representacion', rep)
        if any(rep['authorization'][k] != scope[k] for k in scope):
            continue
        identity = {k: v for k, v in rep.items() if k != 'representation_id'}
        if rep['representation_id'] != 'REP-' + _hash(identity) or path.stem != rep['representation_id']:
            raise ModelError('REPRESENTATION_CHANGED')
        if rep['raw_sha256'] != sha256_bytes(raw):
            raise ModelError('REPRESENTATION_CHANGED')
        blobs = {}
        for role, artifact in rep['artifacts'].items():
            blob = read_bytes(bank, artifact['path'])
            if sha256_bytes(blob) != artifact['sha256'] or len(blob) != artifact['byte_length']:
                raise ModelError('REPRESENTATION_CHANGED')
            blobs[role] = blob
        groups, sentences = _mapping(_parse_json(blobs['dom_source']), raw, blobs['with_speakers'])
        if groups != rep['groups'] or sentences != rep['sentences']:
            raise ModelError('REPRESENTATION_CHANGED')
        results.append((rep, blobs['with_speakers'].decode('utf-8')))
    return results


def validate_semantic_review(review, bundle):
    """Validate operator-supplied external review binding, not its conclusions.

    Hashes must come from the sealed reviewer delivery. This local file API is
    not an identity provider and cannot authenticate the person named reviewer.
    """
    if review is None:
        return None
    required = {'run_id', 'submission_sha256', 'submission_path', 'submission_file_sha256',
                'review_path', 'review_sha256', 'reviewer', 'status'}
    if (not isinstance(review, dict) or set(review) != required
            or review['run_id'] != bundle['run']['run_id']
            or review['submission_sha256'] != bundle['submission_sha256']
            or not isinstance(review['reviewer'], str) or not review['reviewer'].strip()
            or review['status'] not in ('reviewed', 'changes_requested')):
        raise ModelError('SEMANTIC_REVIEW_UNBOUND')
    payloads = {}
    for role, hashkey in [('submission', 'submission_file_sha256'), ('review', 'review_sha256')]:
        path = Path(review[role + '_path'])
        if not path.is_absolute():
            raise ModelError('SEMANTIC_REVIEW_UNBOUND')
        data = read_bytes(path.parent, path.name)
        if sha256_bytes(data) != review[hashkey]:
            raise ModelError('SEMANTIC_REVIEW_CHANGED')
        payloads[role] = data
    submitted = _parse_json(payloads['submission'])
    if _hash(submitted) != bundle['submission_sha256'] or submitted.get('run_id') != review['run_id']:
        raise ModelError('SEMANTIC_REVIEW_UNBOUND')
    return deepcopy(review)


def render_source(tr_id, run_id, profile):
    """Return candidate strings only. No writes, inference or ratification.

    profile: bank, company, audience, purpose=local_analysis, vault_snapshot
    (relative path -> UTF-8 text), optional source_sensitivity per TR and
    semantic_review bound to both run_id and submission_sha256.
    """
    from .lib_ce import visible_filename
    safe_id(tr_id); safe_id(run_id)
    bank = Path(profile['bank'])
    scope = {k: profile[k] for k in ('company', 'audience', 'purpose')}
    snapshot = profile['vault_snapshot']
    if not isinstance(snapshot, dict) or any(not isinstance(v, str) for v in snapshot.values()):
        raise ModelError('VAULT_SNAPSHOT_INVALID')
    report = coverage_report(bank, tr_id, run_id, **scope)
    if not report['evidence']['current']:
        raise ModelError('ANALYSIS_NOT_CURRENT')
    bundle = load_json(safe_path(bank, f'analisis/{run_id}.json'))
    run = bundle['run']; version = run['version_id']
    permission = permission_snapshot(bank, source_refs=bundle['source_refs'], **scope)
    review = validate_semantic_review(profile.get('semantic_review'), bundle)
    row = next(r for r in load_catalog(bank) if r['tr_id'] == tr_id)
    fid = 'F-' + sha256_bytes(tr_id.encode())[:32]
    title = str(row['title_reported'] or 'Untitled transcript').strip()
    try:
        filename = visible_filename(title[:80])
    except ValueError:
        filename = visible_filename('Untitled transcript')
    path = '50_Fuentes/' + filename
    matches = [(p, _front(t)) for p, t in snapshot.items() if p.endswith('.md')
               and _front(t).get('tr_id') == tr_id and _front(t).get('tipo') == 'fuente']
    if len(matches) > 1:
        raise ModelError('DUPLICATE_TR_NOTE')
    if matches:
        path, existing = matches[0]; fid = existing.get('id')
        if not isinstance(fid, str) or not re.fullmatch(r'F-[A-Za-z0-9_-]{2,60}', fid):
            raise ModelError('SOURCE_ID_INVALID')
    else:
        occupied = {p.casefold() for p in snapshot}
        if path.casefold() in occupied:
            path = '50_Fuentes/' + filename[:-3] + ' -- ' + sha256_bytes(tr_id.encode())[:8] + '.md'
        if path.casefold() in occupied or any(_front(t).get('id') == fid for t in snapshot.values()):
            raise ModelError('SOURCE_ID_COLLISION')
    sensitivities = profile.get('source_sensitivity', {})
    levels = ['interno', 'confidencial', 'restringido']
    values = [sensitivities.get(ref['tr_id'], 'restringido') for ref in bundle['source_refs']]
    if any(v not in levels for v in values):
        raise ModelError('SENSITIVITY_INVALID')
    sensitivity = max(values, key=levels.index)
    binding = profile.get('destination_profile')
    if binding is not None:
        policy = destination(binding, profile['vault'], scope)
        sensitivity = maximum([sensitivity, classification(policy, bundle['source_refs'])])
        if any(not authorized(bank, r['tr_id'], r['version_id'], **{**scope, 'purpose': 'internal_query'}) for r in bundle['source_refs']):
            raise ModelError('INTERNAL_QUERY_DENIED')
    if matches:
        prior = matches[0][1].get('sensibilidad', 'restringido')
        if prior not in levels:
            raise ModelError('SENSITIVITY_INVALID')
        sensitivity = max((sensitivity, prior), key=levels.index)
    if binding is not None and sensitivity not in policy['allowed_sensitivities']:
        raise ModelError('DESTINATION_SENSITIVITY_DENIED')
    shared = dict(tr_id=tr_id, run_id=run_id, sensibilidad=sensitivity,
                  local_private_only=sensitivity != 'interno', scope=scope,
                  permission_snapshot=permission, source_refs=bundle['source_refs'],
                  analysis_sha256=sha256_bytes(read_bytes(bank, f'analisis/{run_id}.json')),
                  semantic_review=review)
    if binding is not None:
        shared.update(destination_profile=deepcopy(binding), destination_vault=str(Path(profile['vault']).resolve()))
    spans = [s for subject in run['subject_matrix'] for s in subject['evidence_spans']]
    spans += [s for claim in bundle['claims'] for s in claim['evidence_spans']]
    spans += [s for rel in bundle['relations'] for side in ('source_evidence', 'target_evidence') for s in rel[side]]
    def viewpath(tr, vid):
        return view_paths.get((tr, vid), f'50_Fuentes/Transcripciones/{tr}/{vid}.md')
    view_paths = {}
    if matches and existing.get('version_id') == version:
        view_paths[(tr_id, version)] = existing.get('view_path', f'50_Fuentes/Transcripciones/{tr_id}/{version}.md')
    def anchor(span):
        return 'p-' + _hash(span)[:32]
    def passage(span):
        return _link(viewpath(span['tr_id'], span['version_id']), 'Passage ' + anchor(span)[2:10], '^' + anchor(span))
    candidates = []
    representation_ids = []
    for ref in bundle['source_refs']:
        tr, vid = ref['tr_id'], ref['version_id']
        raw = source(bank, tr, vid, scope)
        if sha256_bytes(raw) != ref['sha256']:
            raise ModelError('SOURCE_CHANGED')
        original = load_json(safe_path(bank, f'versiones/{vid}.json'))
        local = viewpath(tr, vid)
        body = '# Full derived reading\n\n' + _link(path, 'Back to record') + '\n\n'
        body += f"[Custodied original bytes]({safe_path(bank, original['blob_path']).as_uri()})\n\n"
        body += 'SHA-256: `' + ref['sha256'] + '`\n\n## Full text\n\n' + _literal(raw.decode('utf-8'))
        body += '\n## Cited passages\n\n'
        for key, span in sorted({anchor(s): s for s in spans if (s['tr_id'], s['version_id']) == (tr, vid)}.items()):
            excerpt = raw[span['start']:span['end']]
            if sha256_bytes(excerpt) != span['excerpt_sha256']:
                raise ModelError('PASSAGE_CHANGED')
            body += f"Bytes [{span['start']}, {span['end']}) - SHA `{span['excerpt_sha256']}`\n\n^{key}\n\n"
            body += _literal(excerpt.decode('utf-8')) + '\n' + _link(local, 'Full text', 'Full text') + ' - ' + _link(path, 'Back to record') + '\n\n'
        for rep, headered in _representations(bank, tr, vid, raw, scope):
            representation_ids.append(rep['representation_id'])
            body += '\n## Provider labels ' + rep['representation_id'] + '\n\n'
            body += 'Unresolved labels; they do not attest human identity. Complete auxiliary representation, does not replace the raw source.\n\n'
            body += 'SHA-256: `' + rep['artifacts']['with_speakers']['sha256'] + '`\n\n' + _literal(headered)
        view_id = 'VIEW-' + _hash(ref)[:32]
        meta = dict(id=view_id, tipo='transcripcion', tr_id=tr, transcripcion_id=tr, version_id=vid, sensibilidad=sensitivity,
                    estado_editorial='borrador', raw_sha256=ref['sha256'])
        if local in snapshot:
            if maximum([_front(snapshot[local]).get('sensibilidad', 'restringido'), sensitivity]) != _front(snapshot[local]).get('sensibilidad'):
                raise ModelError('EXISTING_VIEW_SENSITIVITY_DOWNGRADE')
            validate_view(bank, snapshot[local], tr, vid, scope)
            needed = [s for s in spans if (s['tr_id'], s['version_id']) == (tr, vid)]
            if all('^' + anchor(s) + '\n\n' + _literal(raw[s['start']:s['end']].decode()) in snapshot[local] for s in needed):
                continue  # Existing views are immutable, including their annotations.
            updated = f'50_Fuentes/Transcripciones/{tr}/{vid}--{_hash([run_id, needed, representation_ids])[:12]}.md'
            view_paths[(tr, vid)] = updated
            body = body.replace('[[' + local, '[[' + updated)
            local = updated
            view_id = 'VIEW-' + _hash([ref, local])[:32]
            meta['id'] = view_id
            meta['view_variant'] = local.rsplit('--', 1)[1][:-3]
            if local in snapshot:
                validate_view(bank, snapshot[local], tr, vid, scope)
                if all('^' + anchor(s) + '\n\n' + _literal(raw[s['start']:s['end']].decode()) in snapshot[local] for s in needed):
                    continue
                raise ModelError('IMMUTABLE_VIEW_CONFLICT')
        candidates.append(_candidate(local, _note(meta, body), 'transcript_view', view_id, snapshot, **shared))
    cats = sorted({c['category_id'] for s in run['subject_matrix'] for c in s['classifications']})
    reconciliation = run['global_reconciliation']
    meta = dict(id=fid, tipo='fuente', clase='fuente', empresa_id=scope['company'], clase_fuente='transcripcion',
                tr_id=tr_id, transcripcion_id=tr_id, version_id=version, run_id=run_id, sensibilidad=sensitivity,
                estado_editorial='en_revision' if review else 'borrador', lectura='leida_completa',
                lectura_alcance='bytes of the version; interpretation and completeness are independent',
                categorias=cats, conflictos_abiertos=len(reconciliation['open_conflicts']),
                semantic_acceptance='external_review_recorded' if review else 'pending_independent_review',
                submission_sha256=bundle['submission_sha256'], view_path=viewpath(tr_id, version))
    body = '# ' + _text(row['title_reported'] or 'Transcript ' + tr_id) + '\n\n'
    body += _link(viewpath(tr_id, version), 'Read full text', 'Full text') + '\n\n'
    body += _text(reconciliation['summary']) + '\n\n'
    body += '## Subjects and claims\n\n'
    for subject in run['subject_matrix']:
        body += '### ' + _text(subject['description']) + '\n\n'
        body += '**Subject:** ' + _text(subject['subject_id']) + '\n\n'
        for label, field in [('Reasons', 'reasons'), ('Exceptions', 'exceptions')]:
            if subject[field]:
                body += '**' + label + ':** ' + '; '.join(_text(x) for x in subject[field]) + '\n\n'
        body += '**Proposed categories:** ' + ', '.join(_text(c['axis'] + ': ' + c['category_id']) for c in subject['classifications']) + '\n\n'
        dest = subject['destination']
        body += '**Proposed destination:** ' + _text(dest['kind'] + ' / ' + dest['id'] + ' -- ' + dest['reason']) + '\n\n'
        for claim in bundle['claims']:
            if claim['claim_id'] not in subject['claim_ids']:
                continue
            body += '- ' + _text(claim['content']) + ' (' + _text(claim['kind'] + '; ' + claim['editorial_state'] + '; ' + claim['validity_state']) + ').\n'
            body += '  Attribution: ' + _text(str(claim['speaker_label']) + ' / ' + claim['attribution_state']) + '; scope: ' + _text(claim['scope']) + '.\n'
            body += '  ' + ' - '.join(passage(s) for s in claim['evidence_spans']) + '\n'
            if claim['limitations']:
                body += '  Limitations: ' + '; '.join(_text(s) for s in claim['limitations']) + '\n'
        body += '\n' + ' - '.join(passage(s) for s in subject['evidence_spans']) + '\n\n'
    body += '## Proposed relations\n\n'
    for rel in bundle['relations']:
        body += '- ' + _text(rel['source_ref']['id'] + ' -> ' + rel['predicate'] + ' -> ' + rel['target_ref']['id']) + ': ' + _text(rel['rationale']) + '\n'
        body += '  Scope: ' + _text(rel['scope']) + '; state: ' + _text(rel['editorial_state']) + '. ' + ' - '.join(passage(s) for s in rel['source_evidence'] + rel['target_evidence']) + '\n'
    body += '\n## Conflicts and limitations\n\n'
    for value in reconciliation['open_conflicts'] + reconciliation['limitations']:
        body += '- ' + _text(value) + '\n'
    version_record = load_json(safe_path(bank, f'versiones/{safe_id(version)}.json'))
    body += '\n## Reading control and permissions\n\n' + _literal(yaml.safe_dump(dict(
        completeness=row['states']['completeness'] if row['preferred_version_id'] == version else 'see_evidence_of_this_version',
        completeness_evidence=version_record['completeness_evidence'], coverage=run['coverage'],
        scope=scope, permission_snapshot=permission, semantic_review=review,
        ratified=False), allow_unicode=True, sort_keys=False))
    proof = None
    if matches:
        meta, body, historical, proof = transition(bank, path, snapshot[path], meta, body, snapshot, scope)
        if binding is not None:
            historical.update(destination_profile=deepcopy(binding), destination_vault=shared['destination_vault'],
                              sensibilidad=classification(policy, historical['source_refs']))
            historical['local_private_only'] = historical['sensibilidad'] != 'interno'
            if maximum([meta['sensibilidad'], historical['sensibilidad'], sensitivity]) != sensitivity:
                raise ModelError('HISTORICAL_SENSITIVITY_REQUIRES_REVIEW')
        shared['access_checks'] = [historical]
        for candidate in candidates:
            candidate['access_checks'] = [historical]
    else:
        body = START + body + END
    source_candidate = _candidate(path, _note(meta, body), 'source', fid, snapshot, **shared)
    if proof:
        source_candidate['source_transition'] = proof
    candidates.insert(0, source_candidate)
    if permission_snapshot(bank, source_refs=bundle['source_refs'], **scope) != permission:
        raise ModelError('PERMISSION_CHANGED')
    if binding is not None:
        destination(binding, profile['vault'], scope)
        if any(not authorized(bank, r['tr_id'], r['version_id'], **{**scope, 'purpose': 'internal_query'}) for r in bundle['source_refs']):
            raise ModelError('INTERNAL_QUERY_DENIED')
    return dict(status='DONE_WITH_CONCERNS', candidates=candidates,
                batch_parent=batch_subjects(run['subject_matrix'], parent_id='BATCH-' + _hash([tr_id, run_id])[:24]),
                evidence=dict(coverage=report['evidence'], semantic_review=review, ratified=False,
                              representation_ids=representation_ids, original_unchanged=True),
                warnings=['PROPOSALS_ONLY', 'PRIVATE_STAGING_REQUIRED' if sensitivity != 'interno' and binding is None else 'INTEGRATION_ACCEPTANCE_PENDING'])


def propose_navigation(candidates, snapshot):
    """Add dedicated views, preserving the existing 16 Bases and custom pages."""
    sources = [c for c in candidates if c['kind'] == 'source']
    if not sources:
        return []
    if len({c['tr_id'] for c in sources}) != len(sources):
        raise ModelError('DUPLICATE_TR_NOTE')
    private = any(c.get('local_private_only', True) for c in sources)
    sensitivity = maximum(c['sensibilidad'] for c in sources)
    bindings = [c.get('destination_profile') for c in sources]
    if any(b is not None for b in bindings) and any(b != bindings[0] for b in bindings):
        raise ModelError('DESTINATION_PROFILE_MIXED')
    access_checks = [{k: c[k] for k in ('scope', 'source_refs', 'permission_snapshot',
                     'tr_id', 'run_id', 'analysis_sha256', 'semantic_review',
                     'sensibilidad', 'local_private_only')}
                     for c in sources]
    for check, c in zip(access_checks, sources):
        for key in ('destination_profile', 'destination_vault'):
            if key in c:
                check[key] = deepcopy(c[key])
    result = []
    root = '90_Sistema/Vistas/Transcripciones'
    names = [('Transcripciones', None), ('Pendientes', 'estado_editorial != "aprobado"'),
             ('Categorias', None), ('Conflictos', 'conflictos_abiertos > 0')]
    for name, extra in names:
        path = root + '/' + name + '.base'
        if path in snapshot:
            continue  # Never regenerate existing custom views.
        filters = ['tipo == "fuente"', 'clase_fuente == "transcripcion"', 'transcripcion_id != null']
        if extra:
            filters.append(extra)
        view = dict(type='table', name=name, order=['file.name', 'estado_editorial', 'categorias', 'conflictos_abiertos'])
        if name == 'Categorias':
            view['groupBy'] = dict(property='categorias', direction='ASC')
        content = yaml.safe_dump(dict(sensibilidad=sensitivity, filters={'and': filters}, views=[view]), allow_unicode=True, sort_keys=False)
        result.append(_candidate(path, content, 'base_view', 'NAV-' + name, snapshot, local_private_only=private))
    map_path = '00_Mapas/Corpus de transcripciones.md'
    marker = '<!-- transcripciones:navegacion:v1 -->'
    prior = snapshot.get(map_path, _note(dict(id='NAV-corpus', tipo='mapa', estado_editorial='borrador'),
                         '# Transcript corpus\n\nMap derived from proposals; does not attest authority.\n'))
    # Append only missing links, retaining all pre-existing text and prior sources.
    missing = '\n'.join('- ' + _link(c['path'], Path(c['path']).stem) for c in sources
                        if '[[' + c['path'] + '|' not in prior and '[[' + c['path'] + ']]' not in prior)
    body = prior + ('\n' + missing + '\n' if missing else '')
    if bindings[0] is not None:
        meta = _front(body)
        meta['sensibilidad'] = maximum([sensitivity, meta.get('sensibilidad', 'interno')])
        body = _note(meta, body.split('\n---\n', 1)[1])
    if body != snapshot.get(map_path):
        result.append(_candidate(map_path, body, 'navigation', 'NAV-corpus', snapshot, local_private_only=private))
    for path in ('Inicio.md', 'Como_usar.md', '90_Sistema/Como_usar.md'):
        if path in snapshot and marker not in snapshot[path] and _front(snapshot[path]).get('id'):
            addition = '\n\n' + marker + '\n## Transcripts\n\n' + _link(map_path, 'Explore corpus') + '\n\n'
            addition += '\n'.join('- ' + _link(root + '/' + name + '.base', name) for name, _ in names) + '\n'
            identity = _front(snapshot[path]).get('id') or 'NAV-' + path[:-3]
            text = snapshot[path] + addition
            if bindings[0] is not None:
                meta = _front(text)
                meta['sensibilidad'] = maximum([sensitivity, meta.get('sensibilidad', 'interno')])
                text = _note(meta, text.split('\n---\n', 1)[1])
            result.append(_candidate(path, text, 'navigation_append', identity, snapshot, local_private_only=private))
    for candidate in result:
        candidate['access_checks'] = deepcopy(access_checks)
        candidate['sensibilidad'] = sensitivity
        if bindings[0] is not None:
            candidate['destination_profile'] = deepcopy(bindings[0])
            candidate['destination_vault'] = sources[0]['destination_vault']
            meta = yaml.safe_load(candidate['content']) if candidate['kind'] == 'base_view' else _front(candidate['content'])
            candidate['sensibilidad'] = maximum([sensitivity, meta.get('sensibilidad', 'interno')])
            candidate['local_private_only'] = candidate['sensibilidad'] != 'interno'
    return result
