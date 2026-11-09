"""Request-local read memoization with a fresh, byte-exact commit check.

No authority survives a request. The guard includes every input of custody,
permission and derivative validation, and never returns a result after a change.
Writes suspend the memo so their checks always inspect live state.
"""
import os
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps

_active = ContextVar('transcript_read_request', default=None)
_INPUTS = ('receipts', 'journal', 'versiones', 'originales', 'analisis',
           'eventos', 'taxonomia', 'permissions')


def _fingerprint(bank):
    from .transcripciones_modelo import json_bytes, read_bytes, safe_path, sha256_bytes
    entries = []
    for name in _INPUTS:
        folder = safe_path(bank, name)
        entries.append((name, folder.exists()))
        pattern = '*.bin' if name == 'originales' else '*.json'
        for path in sorted(folder.glob(pattern)) if folder.exists() else []:
            entries.append((name, path.name, sha256_bytes(read_bytes(folder, path.name))))
    return sha256_bytes(json_bytes(entries))


@contextmanager
def live_reads():
    """Use live reads for mutation validation, including calls inside a query."""
    token = _active.set(None)
    try:
        yield
    finally:
        _active.reset(token)


def request_memo(function):
    """Memoize only pure bank-wide views, with defensive copies for callers."""
    @wraps(function)
    def wrapped(bank):
        state = _active.get()
        if state is None or state['bank'] != os.path.abspath(bank):
            return function(bank)
        if function not in state['memo']:
            state['memo'][function] = function(bank)
        value = state['memo'][function]
        # The immutable grant set contains only tuples of strings.
        return value if isinstance(value, frozenset) else deepcopy(value)
    return wrapped


def request_value(function):
    """Memoize a pure immutable value keyed by exact bytes, only in this request."""
    @wraps(function)
    def wrapped(data):
        state = _active.get()
        if state is None or not isinstance(data, bytes):
            return function(data)
        key = (function, data)
        if key not in state['memo']:
            state['memo'][key] = function(data)
        return state['memo'][key]
    return wrapped


def guarded_read(function):
    @wraps(function)
    def wrapped(bank, *args, **kwargs):
        from .transcripciones_modelo import ModelError, validate_bank_location
        key = os.path.abspath(bank)
        state = _active.get()
        if state is not None and state['bank'] == key:
            return function(bank, *args, **kwargs)
        validate_bank_location(bank)
        before = _fingerprint(bank)
        token = _active.set({'bank': key, 'memo': {}})
        try:
            result = function(bank, *args, **kwargs)
        finally:
            _active.reset(token)
        # This check is deliberately outside the memoized context. It hashes
        # originals and all journals/ledgers, including newly added files.
        validate_bank_location(bank)
        if _fingerprint(bank) != before:
            raise ModelError('SNAPSHOT_CHANGED')
        return result
    return wrapped
