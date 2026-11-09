"""Explicit, live local destination policy; never grants source permissions."""
import json
from pathlib import Path

from .transcripciones_modelo import ModelError, sha256_bytes

LEVELS = ('interno', 'confidencial', 'restringido')


def maximum(values):
    values = list(values)
    if not values or any(v not in LEVELS for v in values):
        raise ModelError('SENSITIVITY_INVALID')
    return max(values, key=LEVELS.index)


def destination(binding, vault, scope):
    if not isinstance(binding, dict) or set(binding) != {'path', 'sha256'}:
        raise ModelError('DESTINATION_PROFILE_REQUIRED')
    path = Path(binding['path'])
    target = Path(vault)
    for p in (path, target):
        if not p.is_absolute() or any(x.is_symlink() for x in (p, *p.parents)):
            raise ModelError('DESTINATION_PATH_INVALID')
    raw = path.read_bytes()
    if sha256_bytes(raw) != binding['sha256']:
        raise ModelError('DESTINATION_POLICY_CHANGED')
    policy = json.loads(raw)
    auth = policy.get('authorization', {})
    if (policy.get('schema') != 1 or policy.get('active') is not True
            or policy.get('vault') != str(target.resolve())
            or any(policy.get(k) != scope[k] for k in ('company', 'audience'))
            or scope.get('purpose') != 'local_analysis'
            or set(policy.get('purposes', [])) != {'local_analysis', 'internal_query'}
            or not all(isinstance(auth.get(k), str) and auth[k].strip() for k in ('responsable', 'referencia'))
            or not policy.get('allowed_sensitivities')
            or any(v not in LEVELS for v in policy['allowed_sensitivities'])
            or not isinstance(policy.get('source_sensitivity'), dict)):
        raise ModelError('DESTINATION_POLICY_INVALID')
    maximum(policy['source_sensitivity'].values())
    return policy


def classification(policy, refs):
    if not refs or any(r['tr_id'] not in policy['source_sensitivity'] for r in refs):
        raise ModelError('DESTINATION_SOURCE_DENIED')
    value = maximum(policy['source_sensitivity'].get(r['tr_id'], 'restringido') for r in refs)
    if value not in policy['allowed_sensitivities']:
        raise ModelError('DESTINATION_SENSITIVITY_DENIED')
    return value
