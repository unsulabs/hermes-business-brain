"""Explicit append-only access decisions. Profiles never confer source rights.

Authority/evidence are attestations supplied by the authorized local operator;
this local API is not an identity provider or an ACL against the OS account.
"""
from copy import deepcopy

from .transcripciones_custodia import load_catalog
from .transcripciones_lectura import request_memo
from .transcripciones_modelo import (
    ModelError,
    atomic_write,
    bank_lock,
    json_bytes,
    load_json,
    safe_path,
    sha256_bytes,
    validate_bank_location,
    validate_record,
)

PURPOSES = ('custody', 'local_analysis', 'internal_query', 'evaluation', 'training', 'publication')
KEYS = ('tr_id', 'version_id', 'company', 'audience', 'purpose')


@request_memo
def decisions(bank):
    validate_bank_location(bank)
    folder = safe_path(bank, 'permissions')
    chain, previous = [], None
    for path in sorted(folder.glob('*.json')) if folder.exists() else []:
        row = load_json(path)
        validate_record('permiso', row)
        if row['sequence'] != len(chain) + 1 or row['previous_hash'] != previous:
            raise ModelError('PERMISSION_CHAIN_INVALID')
        if path.name != f"{row['sequence']:012d}.json":
            raise ModelError('PERMISSION_CHAIN_INVALID')
        chain.append(row)
        previous = sha256_bytes(json_bytes(row))
    return chain


def permission_snapshot(bank, *, source_refs=None, company=None, audience=None, purpose=None):
    """Legacy global watermark, or exact effective dependency access snapshot."""
    if source_refs is None and company is None and audience is None and purpose is None:
        return sha256_bytes(json_bytes(decisions(bank)))
    if source_refs is None or not all(isinstance(v,str) and v.strip() for v in (company,audience,purpose)):
        raise ModelError('ACCESS_CONTEXT_REQUIRED')
    keys={(r['tr_id'],r['version_id']) if isinstance(r,dict) else tuple(r) for r in source_refs}
    if any(len(key)!=2 for key in keys):
        raise ModelError('SOURCE_REFERENCE_INVALID')
    selected=[]
    for record in effective_decisions(bank):
        if (record['tr_id'],record['version_id']) in keys and (record['company'],record['audience'],record['purpose'])==(company,audience,purpose):
            # Global sequence/hash chain aren't semantic dependencies.
            selected.append({k:v for k,v in record.items() if k not in ('sequence','previous_hash')})
    selected.sort(key=lambda r:tuple(r[k] for k in KEYS))
    return sha256_bytes(json_bytes({'sources':sorted(keys),'scope':[company,audience,purpose],'decisions':selected}))


def record_decision(bank, decision, *, commit=False):
    """Caller explicitly attests authority. Revocation applies only to exact scope."""
    def prepare():
        rows = load_catalog(bank)
        row = next((r for r in rows if r['tr_id'] == decision.get('tr_id')), None)
        if row is None or decision.get('version_id') not in row['version_ids']:
            raise ModelError('PERMISSION_SOURCE_UNKNOWN')
        chain = decisions(bank)
        record = dict(decision, schema_version='permiso.v1', sequence=len(chain)+1,
                      previous_hash=sha256_bytes(json_bytes(chain[-1])) if chain else None)
        validate_record('permiso', record)
        for prior in reversed(chain):
            if all(prior[k] == record[k] for k in KEYS):
                fields=set(record)-{'sequence','previous_hash'}
                if all(prior[k] == record[k] for k in fields):
                    return prior
                break
        return record
    if not commit:
        return prepare()
    with bank_lock(bank):
        record = prepare()
        atomic_write(bank, f"permissions/{record['sequence']:012d}.json", json_bytes(record))
        return record


def effective_decisions(bank):
    effective = {}
    for record in decisions(bank):
        effective[tuple(record[k] for k in KEYS)] = record
    return list(effective.values())


def enrich_catalog(bank):
    rows = deepcopy(load_catalog(bank))
    current = effective_decisions(bank)
    for row in rows:
        selected = [d for d in current if d['tr_id'] == row['tr_id']]
        row['permission_decisions'] = selected
        row['company_scope'] = sorted({d['company'] for d in selected if d['action'] == 'grant'})
        # The legacy aggregate purpose flags deliberately stay unknown: grants
        # are version/company/audience specific and must not be flattened.
    return rows


@request_memo
def _granted_keys(bank):
    return frozenset(tuple(d[k] for k in KEYS) for d in effective_decisions(bank)
                     if d['action'] == 'grant')


def authorized(bank, tr_id, version_id, company, audience, purpose):
    if not all(isinstance(v, str) and v.strip() for v in (company,audience,purpose)):
        return False
    key = (tr_id,version_id,company,audience,purpose)
    return key in _granted_keys(bank)
