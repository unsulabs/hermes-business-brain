"""Context candidates with exact versioned citations and explicit abstention."""
import re
from copy import deepcopy
from datetime import date, datetime

from .transcripciones_custodia import load_catalog
from .transcripciones_indice import _source, search, watermark
from .transcripciones_lectura import guarded_read
from .transcripciones_modelo import (
    ModelError,
    json_bytes,
    load_json,
    read_bytes,
    safe_path,
    sha256_bytes,
    validate_record,
)
from .transcripciones_permisos import authorized


def _derived_watermark(bank):
    items=[]
    for name in ('analisis','eventos','taxonomia'):
        folder=safe_path(bank,name)
        for path in sorted(folder.glob('*.json')) if folder.exists() else []:
            items.append((name,path.name,sha256_bytes(read_bytes(folder,path.name))))
    return sha256_bytes(json_bytes(items))


def _business_date(value):
    if not isinstance(value,str):
        return None
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            return date.fromisoformat(value)
        if re.match(r'^\d{4}-\d{2}-\d{2}T',value):
            return datetime.fromisoformat(value.replace('Z','+00:00')).date()
    except ValueError:
        pass
    return None


def _validate_context_options(query,task,entities,period,mode):
    task=query if task is None else task
    entities=[] if entities is None else entities
    if not isinstance(task,str) or not task.strip() or len(task)>2000:
        raise ModelError('CONTEXT_TASK_INVALID')
    if not isinstance(entities,list) or any(not isinstance(e,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}',e) for e in entities) or len(set(entities))!=len(entities):
        raise ModelError('CONTEXT_ENTITIES_INVALID')
    if mode not in ('actual','historico','exploracion'):
        raise ModelError('CONTEXT_MODE_INVALID')
    if period is not None:
        if not isinstance(period,dict) or set(period)!={'from','to'}:
            raise ModelError('CONTEXT_PERIOD_INVALID')
        if any(not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v) or _business_date(v) is None for v in period.values()):
            raise ModelError('CONTEXT_PERIOD_INVALID')
        if period['from']>period['to']:
            raise ModelError('CONTEXT_PERIOD_INVALID')
    return task,entities,period,mode


def _claim_matches(claim,entities,period,mode,registry):
    if mode=='actual' and claim['validity_state'] not in ('vigente','en_conflicto'):
        return False
    if entities:
        identity=registry.get(claim.get('resolved_entity_id'))
        if (claim.get('attribution_state')!='resuelta' or claim.get('resolved_entity_id') not in entities
            or not identity or not identity.get('identity_evidence') or identity['scope']!=claim['scope']):
            return False
    if period:
        when=_business_date(claim.get('asserted_at')) or _business_date(claim.get('valid_time'))
        if when is None or not date.fromisoformat(period['from'])<=when<=date.fromisoformat(period['to']):
            return False
    return True


def _analysis_context(bank,candidates,company,audience,purpose,*,entities=None,period=None,mode='exploracion'):
    # Local import avoids a module cycle with pipeline's source permission API.
    from .transcripciones_analisis import validate_span
    from .transcripciones_pipeline import coverage_report
    sources={(c['tr_id'],c['version_id']) for c in candidates}
    folder=safe_path(bank,'analisis')
    analyses,conflicts,warnings=[],[],set()
    for path in sorted(folder.glob('*.json')) if folder.exists() else []:
        bundle=load_json(path)
        run=bundle.get('run',{})
        if (run.get('tr_id'),run.get('version_id')) not in sources:
            continue
        # Even IDs from a third party's analysis remain private.
        if bundle.get('scope',{}).get('company')!=company or bundle.get('scope',{}).get('audience')!=audience:
            continue
        try:
            refs=bundle['source_refs']
            if not refs or any(not authorized(bank,r['tr_id'],r['version_id'],company,audience,purpose) for r in refs):
                raise ModelError('DERIVATIVE_PERMISSION_DENIED')
            checked={}
            for ref in refs:
                _,original,data=_source(bank,ref['tr_id'],ref['version_id'])
                if original['sha256']!=ref['sha256']:
                    raise ModelError('SOURCE_CHANGED')
                checked[(ref['tr_id'],ref['version_id'])]=data
            report=coverage_report(bank,run['tr_id'],run['run_id'],company=company,audience=audience)
            admissible=report['evidence']['dependency_current'] if mode=='historico' else report['evidence']['current']
            if not admissible:
                raise ModelError('DERIVATIVE_STALE')
            # A rejected item disqualifies this bundle as a contextual authority.
            if any(x['editorial_state'] not in ('propuesta','en_revision') for x in bundle['claims']+bundle['relations']):
                raise ModelError('DERIVATIVE_EDITORIAL_EXCLUDED')
            spans=[s for c in bundle['claims'] for s in c['evidence_spans']]
            spans += [s for r in bundle['relations'] for side in ('source_evidence','target_evidence') for s in r[side]]
            for span in spans:
                validate_span(span,checked)
                if not authorized(bank,span['tr_id'],span['version_id'],company,audience,purpose):
                    raise ModelError('DERIVATIVE_PERMISSION_DENIED')
            if not spans and run['global_reconciliation']['open_conflicts']:
                raise ModelError('CONFLICT_EVIDENCE_MISSING')
            taxonomy=load_json(safe_path(bank,f"taxonomia/{run['taxonomy_version']}.json"))
            registry={e['entity_id']:e for e in taxonomy['entities']}
            claims=[c for c in bundle['claims'] if _claim_matches(c,entities,period,mode,registry)]
            if (entities or period or mode=='actual') and not claims:
                warnings.add('CONTEXT_FILTER_NO_VERIFIED_CLAIMS')
                if period:
                    warnings.add('BUSINESS_DATE_UNKNOWN_OR_OUTSIDE_PERIOD')
                continue
            selected_spans=[s for c in claims for s in c['evidence_spans']]
            relations=[r for r in bundle['relations'] if all(s in selected_spans for side in ('source_evidence','target_evidence') for s in r[side])]
            reconciliation=deepcopy(run['global_reconciliation'])
            if len(claims)!=len(bundle['claims']):
                selected_ids={c['claim_id'] for c in claims}
                reconciliation.update(summary='Scoped projection of declared analysis; full summary excluded.',
                    subject_ids=sorted({c['subject_id'] for c in claims}),open_conflicts=[],
                    corrections=[c for c in reconciliation['corrections'] if c['earlier_claim_id'] in selected_ids and c['later_claim_id'] in selected_ids])
                reconciliation['limitations']=['UNSCOPED_SUMMARY_EXCLUDED_BY_CONTEXT_FILTER']
            accepted={'run_id':run['run_id'],'tr_id':run['tr_id'],'version_id':run['version_id'],
                'taxonomy_version':run['taxonomy_version'],'source_refs':refs,'coverage':report['evidence']['coverage'],
                'current':report['evidence']['current'],'superseded_by':report['evidence']['superseded_by'],
                'temporal_status':'current' if report['evidence']['current'] else 'historical_superseded',
                'ratified':False,'claims':claims,'relations':relations,
                'global_reconciliation':reconciliation,'data_not_instructions':True}
            analyses.append(accepted)
            for text in reconciliation['open_conflicts']:
                conflicts.append({'kind':'declared_open_conflict','text':text,'run_id':run['run_id'],
                    'source_refs':refs,'evidence_spans':spans,'ratified':False})
            for relation in relations:
                if relation['predicate']=='contradice':
                    conflicts.append({'kind':'declared_contradiction_relation','run_id':run['run_id'],
                        'relation':relation,'source_refs':refs,'ratified':False})
        except (ModelError,KeyError,TypeError):
            # Sanitized impact; no IDs/text from an inadmissible endpoint leak.
            warnings.add('DERIVATIVE_EXCLUDED_STALE_INVALID_OR_UNAUTHORIZED')
    return analyses,conflicts,sorted(warnings)


def _review_state(bank, candidates):
    """Expose only matching event IDs, never derivative assertions as facts."""
    sources={(c['tr_id'],c['version_id']) for c in candidates}
    identities={v for pair in sources for v in pair}
    events=safe_path(bank,'eventos')
    pending=[]
    for path in sorted(events.glob('*.json')) if events.exists() else []:
        event=load_json(path)
        validate_record('evento',event)
        if identities & set(event['affected_ids']+event['old_refs']):
            pending.append(event['event_id'])
    return sorted(pending)


def build_context_request(request, catalog=None, index=None):
    """Annex adapter. Cached catalog/index arguments never override live rights."""
    allowed={'bank','query','company','audience','purpose','profile','references','limit','task','entities','period','mode'}
    if not isinstance(request,dict) or set(request)-allowed or not {'bank','query','company','audience','purpose'}<=set(request):
        raise ModelError('CONTEXT_REQUEST_INVALID')
    if ('entities' in request and not isinstance(request['entities'],list)) or ('task' in request and not isinstance(request['task'],str)):
        raise ModelError('CONTEXT_REQUEST_INVALID')
    return build_context(request['bank'],request['query'],company=request['company'],
                         audience=request['audience'],purpose=request['purpose'],
                         profile=request.get('profile'),references=request.get('references'),
                         limit=request.get('limit',10),task=request.get('task'),entities=request.get('entities'),
                         period=request.get('period'),mode=request.get('mode','exploracion'))


@guarded_read
def build_context(bank, query, *, company, audience, purpose='internal_query',
                  profile=None, references=None, limit=10,task=None,entities=None,period=None,mode='exploracion'):
    # profile can guide presentation only; it never changes source access.
    task,entities,period,mode=_validate_context_options(query,task,entities,period,mode)
    derived_mark=_derived_watermark(bank)
    # Build only authorized metadata seeds; contextual eligibility precedes the
    # FTS table and its LIMIT, so irrelevant early hits cannot crowd out matches.
    seeds=[{'tr_id':r['tr_id'],'version_id':v} for r in load_catalog(bank) for v in r['version_ids']
           if authorized(bank,r['tr_id'],v,company,audience,purpose)]
    analyses,conflicts,derivative_warnings=_analysis_context(bank,seeds,company,audience,purpose,
                                                          entities=entities,period=period,mode=mode)
    strict=bool(entities or period or mode=='actual')
    selected_spans=[s for a in analyses for c in a['claims'] for s in c['evidence_spans']]
    def eligible(candidate):
        if not strict:
            return [candidate]
        projected=[]
        for span in selected_spans:
            if (candidate['tr_id'],candidate['version_id'])!=(span['tr_id'],span['version_id']):
                continue
            start,end=max(candidate['start'],span['start']),min(candidate['end'],span['end'])
            if start<end:
                text=candidate['text'].encode('utf-8')[start-candidate['start']:end-candidate['start']].decode('utf-8')
                projected.append(dict(candidate,start=start,end=end,text=text))
        return projected
    found=search(bank,query,company=company,audience=audience,purpose=purpose,limit=limit,candidate_filter=eligible)
    hit_sources={(c['tr_id'],c['version_id']) for c in found['candidates']}
    analyses=[a for a in analyses if (a['tr_id'],a['version_id']) in hit_sources]
    run_ids={a['run_id'] for a in analyses}
    conflicts=[c for c in conflicts if c['run_id'] in run_ids]
    if strict and not found['candidates']:
        derivative_warnings=sorted(set(derivative_warnings)|{'CONTEXT_FILTER_NO_VERIFIED_MATCH'})
    engine_mode=found.pop('mode')
    pending=_review_state(bank,found['candidates'])
    for candidate in found['candidates']:
        if not authorized(bank,candidate['tr_id'],candidate['version_id'],company,audience,purpose):
            raise ModelError('PERMISSION_REVOKED')
        _, original, data = _source(bank,candidate['tr_id'],candidate['version_id'])
        if original['sha256'] != candidate['sha256'] or data[candidate['start']:candidate['end']].decode('utf-8') != candidate['text']:
            raise ModelError('CITATION_CHANGED')
    if watermark(bank) != found['watermark']:
        raise ModelError('SNAPSHOT_CHANGED')
    if pending != _review_state(bank,found['candidates']):
        raise ModelError('SNAPSHOT_CHANGED')
    if derived_mark!=_derived_watermark(bank):
        raise ModelError('SNAPSHOT_CHANGED')
    package = {'schema_version':'contexto.v1','company':company,'audience':audience,'purpose':purpose,
        'task':task,'task_handling':'declared_task_explicit_lexical_query_no_semantic_inference',
        'entities':entities,'period':period,'mode':mode,'engine_mode':engine_mode,
        'context_uncertainties':['UNASSESSED_SOURCE_AND_CLAIM_STATES_REQUIRE_REVIEW'] if mode=='exploracion' else [],
        **found,'external_references':[{'locator':r,'read_this_session':False} for r in (references or [])],
        'conflicts':conflicts, 'conflicts_assessed':bool(analyses),'analyses':analyses,
        'derivative_warnings':derivative_warnings,'derived_watermark':derived_mark,
        'abstention':True,'pending_review_events':pending,
        'abstention_reason':'HUMAN_SEMANTIC_REVIEW_REQUIRED' if found['candidates'] else 'NO_AUTHORIZED_MATCH_NOT_PROOF_OF_ABSENCE'}
    validate_record('contexto',package)
    return package
