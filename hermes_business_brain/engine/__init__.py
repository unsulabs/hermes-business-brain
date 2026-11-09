# ruff: noqa: N999  (repository directory name is not the package name)
"""Business Brain engine: in-process operations over local business vaults (no subprocess).

The engine is a native-English business-brain engine for local knowledge vaults.
Empresarial scripts: logic, identifiers, enums and JSON output keys are
preserved 1:1; all user-facing strings are English.

Public API
----------
Vault lifecycle ops (always present):
    doctor, create_vault, validate_vault, status, register_vault, resolve_vault

Errors
------
``BrainError`` is raised on hard (non-success) operation failures.

The full union of engine operations -- including the knowledge and transcripts
families once those sibling modules are installed -- is re-exported by
:mod:`hermes_business_brain.engine.api`.
"""
from . import api  # canonical facade (tolerant re-export, see api.py)
from .ops_vault import (
    BrainError,
    create_vault,
    doctor,
    register_vault,
    resolve_vault,
    status,
    validate_vault,
)

__all__ = [
    "BrainError",
    "api",
    "create_vault",
    "doctor",
    "register_vault",
    "resolve_vault",
    "status",
    "validate_vault",
]
