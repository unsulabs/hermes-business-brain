"""Bounded bridge for TR record cards: direct lineage and custody of preview views."""
import re
from copy import deepcopy

from .transcripciones_custodia import load_catalog
from .transcripciones_modelo import (
    ModelError,
    json_bytes,
    load_json,
    read_bytes,
    safe_id,
    safe_path,
    sha256_bytes,
)
from .transcripciones_permisos import permission_snapshot
from .transcripciones_pipeline import _supersession_graph, source

START = '<!-- ce:source-generated:v1:start -->\n'
END = '<!-- ce:source-generated:v1:end -->\n'
MANAGED_FIELDS = {'version_id', 'run_id', 'sensibilidad', 'lectura', 'lectura_alcance', 'categorias',
                  'conflictos_abiertos', 'semantic_acceptance', 'submission_sha256', 'view_path', 'historial_fuentes'}


def literal(text):
    fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', text)), default=0))
    return fence + 'text\n' + text + '\n' + fence + '\n'


def generated_parts(body):
    if START not in body and END not in body:
        return '', body, '', False
    if body.count(START) != 1 or body.count(END) != 1:
        raise ModelError('SOURCE_GENERATED_BOUNDARY_INVALID')
    prefix, rest = body.split(START)
    managed, suffix = rest.split(END)
    return prefix, managed, suffix, True


def validate_view(bank, text, tr, version, scope):
    from .lib_ce import split_frontmatter
    fm, _ = split_frontmatter(text)
    raw = source(bank, tr, version, scope)
    if (fm.get('tipo') != 'transcripcion' or fm.get('transcripcion_id') != tr or fm.get('version_id') != version
            or fm.get('raw_sha256') != sha256_bytes(raw) or literal(raw.decode()) not in text):
        raise ModelError('HISTORICAL_VIEW_CHANGED')
    return dict(tr_id=tr, version_id=version, sha256=sha256_bytes(raw))


def lineage(bank, tr, previous, current):
    row = next((r for r in load_catalog(bank) if r['tr_id'] == tr), None)
    if row is None or previous not in row['version_ids'] or current not in row['version_ids']:
        raise ModelError('SOURCE_VERSION_NOT_IN_CATALOG')
    records = [load_json(safe_path(bank, f'versiones/{safe_id(v)}.json')) for v in (previous, current)]
    if any(r['tr_id'] != tr for r in records):
        raise ModelError('SOURCE_VERSION_WRONG_TRANSCRIPT')
    if previous != current and (records[1]['previous_version_id'] != previous
                               or row['version_ids'].index(current) != row['version_ids'].index(previous) + 1):
        raise ModelError('SOURCE_VERSION_NOT_DIRECT_SUCCESSOR')
    return [sha256_bytes(json_bytes(record)) for record in records]


def analysis_lineage(bank, previous_run, new_run, bundle):
    if previous_run == new_run:
        return
    if bundle['run']['supersedes_run_id'] != previous_run:
        raise ModelError('SOURCE_ANALYSIS_NOT_DIRECT_SUCCESSOR')
    siblings = [rid for rid, parent in _supersession_graph(bank).items() if parent == previous_run]
    if siblings != [new_run]:
        raise ModelError('SOURCE_ANALYSIS_BRANCH_AMBIGUOUS')


def transition(bank, path, previous_text, next_meta, next_body, snapshot, scope):
    """Keep text outside the generated section; a fully legacy body stays historical."""
    from .lib_ce import split_frontmatter, wiki_targets
    old, oldbody = split_frontmatter(previous_text)
    tr = next_meta['tr_id']
    if (old.get('tipo') != 'fuente' or old.get('tr_id', old.get('transcripcion_id')) != tr
            or old.get('id') != next_meta['id'] or old.get('empresa_id') != scope['company']
            or old.get('estado_editorial') not in {'borrador', 'en_revision'}):
        raise ModelError('SOURCE_PREVIOUS_IDENTITY_OR_EDITORIAL_INVALID')
    previous, current = old.get('version_id'), next_meta['version_id']
    hashes = lineage(bank, tr, previous, current)
    prior_bundle_path = f"analisis/{safe_id(old['run_id'])}.json"
    prior_bundle_bytes = read_bytes(bank, prior_bundle_path)
    prior_bundle = load_json(safe_path(bank, prior_bundle_path))
    if (prior_bundle['run']['tr_id'] != tr or prior_bundle['run']['version_id'] != previous
            or prior_bundle['submission_sha256'] != old.get('submission_sha256')):
        raise ModelError('SOURCE_PREVIOUS_ANALYSIS_MISMATCH')
    new_bundle = load_json(safe_path(bank, f"analisis/{safe_id(next_meta['run_id'])}.json"))
    if previous == current:
        analysis_lineage(bank, old['run_id'], next_meta['run_id'], new_bundle)
    paths = {link if link.endswith('.md') else link + '.md' for link in wiki_targets(oldbody)
             if link.startswith('50_Fuentes/Transcripciones/')}
    paths.add(old.get('view_path', f'50_Fuentes/Transcripciones/{tr}/{previous}.md'))
    views, references = [], {}
    for view_path in sorted(paths):
        if view_path not in snapshot:
            raise ModelError('HISTORICAL_VIEW_MISSING')
        text = snapshot[view_path]
        fm, _ = split_frontmatter(text)
        ref = validate_view(bank, text, fm.get('transcripcion_id'), fm.get('version_id'), scope)
        references[(ref['tr_id'], ref['version_id'])] = ref
        views.append(dict(path=view_path, view_sha256=sha256_bytes(text.encode()), tr_id=ref['tr_id'], version_id=ref['version_id']))
    for ref in prior_bundle['source_refs']:
        if sha256_bytes(source(bank, ref['tr_id'], ref['version_id'], scope)) != ref['sha256']:
            raise ModelError('HISTORICAL_SOURCE_CHANGED')
        references[(ref['tr_id'], ref['version_id'])] = ref
    refs = [references[k] for k in sorted(references)]
    history_check = dict(scope=deepcopy(scope), source_refs=refs,
                         permission_snapshot=permission_snapshot(bank, source_refs=refs, **scope),
                         query_permission_snapshot=permission_snapshot(bank, source_refs=refs, **{**scope, 'purpose': 'internal_query'}))
    prefix, managed, suffix, marked = generated_parts(oldbody)
    merged = {**old, **next_meta}
    levels = ['interno', 'confidencial', 'restringido']
    merged['sensibilidad'] = max([merged['sensibilidad']] + [split_frontmatter(snapshot[v['path']])[0].get('sensibilidad', 'restringido') for v in views], key=levels.index)
    merged['estado_editorial'] = old['estado_editorial']
    same_content = managed == next_body and all(old.get(k) == v for k, v in next_meta.items() if k != 'estado_editorial')
    if same_content and marked:
        return old, oldbody, history_check, None
    history = deepcopy(old.get('historial_fuentes', []))
    history.append(dict(version_id=previous, run_id=old['run_id'], source_sha256=sha256_bytes(previous_text.encode()),
                        view_path=old.get('view_path', f'50_Fuentes/Transcripciones/{tr}/{previous}.md')))
    merged['historial_fuentes'] = history
    archive = '\n\n## Proposal history — not the current version\n\n'
    archive += f"Version `{previous}` · analysis `{old['run_id']}`. Text preserved, not reinterpreted.\n\n"
    archive += literal(managed if marked else oldbody)
    body = prefix + START + next_body + END + suffix + archive
    proof = dict(path=path, tr_id=tr, previous_version_id=previous, next_version_id=current,
                 previous_run_id=old['run_id'], next_run_id=next_meta['run_id'],
                 previous_source_sha256=sha256_bytes(previous_text.encode()),
                 previous_analysis_sha256=sha256_bytes(prior_bundle_bytes), lineage_hashes=hashes,
                 history_views=views, history_check=history_check)
    return merged, body, history_check, proof


def validate_transition(bank, proof, previous_text, next_text, snapshot, scope):
    from .lib_ce import split_frontmatter, wiki_targets
    old, _ = split_frontmatter(previous_text)
    new, body = split_frontmatter(next_text)
    if (sha256_bytes(previous_text.encode()) != proof['previous_source_sha256'] or old['id'] != new['id']
            or old.get('tr_id', old.get('transcripcion_id')) != new.get('tr_id')
            or old['version_id'] != proof['previous_version_id'] or new['version_id'] != proof['next_version_id']
            or old['run_id'] != proof['previous_run_id'] or new['run_id'] != proof['next_run_id']):
        raise ModelError('SOURCE_TRANSITION_BINDING_CHANGED')
    if old.get('estado_editorial') not in {'borrador', 'en_revision'} or any(new.get(k) != v for k, v in old.items() if k not in MANAGED_FIELDS):
        raise ModelError('SOURCE_CUSTOM_METADATA_OR_EDITORIAL_CHANGED')
    if new.get('empresa_id') != scope['company']:
        raise ModelError('SOURCE_COMPANY_SCOPE_MISMATCH')
    oldbody = split_frontmatter(previous_text)[1]
    needed_paths = {link if link.endswith('.md') else link + '.md' for link in wiki_targets(oldbody)
                    if link.startswith('50_Fuentes/Transcripciones/')}
    needed_paths.add(old.get('view_path', f"50_Fuentes/Transcripciones/{proof['tr_id']}/{old['version_id']}.md"))
    if not needed_paths <= {view['path'] for view in proof['history_views']}:
        raise ModelError('HISTORICAL_VIEW_MISSING')
    if lineage(bank, proof['tr_id'], old['version_id'], new['version_id']) != proof['lineage_hashes']:
        raise ModelError('SOURCE_LINEAGE_CHANGED')
    prior = read_bytes(bank, f"analisis/{safe_id(old['run_id'])}.json")
    if sha256_bytes(prior) != proof['previous_analysis_sha256']:
        raise ModelError('SOURCE_PREVIOUS_ANALYSIS_CHANGED')
    historical = proof['history_check']
    if historical['scope'] != scope:
        raise ModelError('SOURCE_HISTORICAL_SCOPE_CHANGED')
    refs = historical['source_refs']
    known = {(r['tr_id'], r['version_id']) for r in refs}
    prior_bundle = load_json(safe_path(bank, f"analisis/{safe_id(old['run_id'])}.json"))
    if (prior_bundle['run']['tr_id'] != proof['tr_id'] or prior_bundle['run']['version_id'] != old['version_id']
            or prior_bundle['submission_sha256'] != old['submission_sha256']):
        raise ModelError('SOURCE_PREVIOUS_ANALYSIS_MISMATCH')
    needed = {(r['tr_id'], r['version_id']) for r in prior_bundle['source_refs']}
    needed.update((v['tr_id'], v['version_id']) for v in proof['history_views'])
    if not needed <= known:
        raise ModelError('SOURCE_HISTORICAL_DEPENDENCY_MISSING')
    for purpose, key in [('local_analysis', 'permission_snapshot'), ('internal_query', 'query_permission_snapshot')]:
        scoped = {**scope, 'purpose': purpose}
        if permission_snapshot(bank, source_refs=refs, **scoped) != historical[key]:
            raise ModelError('SOURCE_HISTORICAL_PERMISSION_CHANGED')
        for ref in refs:
            if sha256_bytes(source(bank, ref['tr_id'], ref['version_id'], scoped)) != ref['sha256']:
                raise ModelError('HISTORICAL_SOURCE_CHANGED')
    bundle = load_json(safe_path(bank, f"analisis/{safe_id(new['run_id'])}.json"))
    if (bundle['run']['tr_id'] != proof['tr_id'] or bundle['run']['version_id'] != new['version_id']
            or bundle['submission_sha256'] != new['submission_sha256']):
        raise ModelError('SOURCE_NEW_ANALYSIS_MISMATCH')
    if old['version_id'] == new['version_id']:
        analysis_lineage(bank, old['run_id'], new['run_id'], bundle)
    for view in proof['history_views']:
        text = snapshot.get(view['path'])
        if text is None or sha256_bytes(text.encode()) != view['view_sha256']:
            raise ModelError('HISTORICAL_VIEW_CHANGED')
        validate_view(bank, text, view['tr_id'], view['version_id'], scope)
    prefix, managed, suffix, marked = generated_parts(oldbody)
    if literal(managed if marked else oldbody) not in body or (marked and (prefix not in body or suffix not in body)):
        raise ModelError('SOURCE_HISTORY_OR_CUSTOMIZATION_LOST')
    previous_history = old.get('historial_fuentes', [])
    expected_entry = dict(version_id=old['version_id'], run_id=old['run_id'],
                          source_sha256=sha256_bytes(previous_text.encode()),
                          view_path=old.get('view_path', f"50_Fuentes/Transcripciones/{proof['tr_id']}/{old['version_id']}.md"))
    # Each transition extends the exact prior chain by precisely its bound
    # predecessor; a preserved prefix alone also accepts a missing new entry.
    if not isinstance(previous_history, list) or new.get('historial_fuentes') != previous_history + [expected_entry]:
        raise ModelError('SOURCE_HISTORY_LOST')
