"""Canonical public API facade of the Business Brain engine.

Re-exports the union of all engine operations:

* vault lifecycle (always available): ``doctor``, ``create_vault``,
  ``validate_vault``, ``status``, ``register_vault``, ``resolve_vault``
* knowledge family (from the ``ops_knowledge`` sibling module, once installed):
  ``query``, ``capture``, ``knowledge_map``, ``relations``, ``references``,
  ``naming``, ``propose``, ``card``, ``document``, ``knowledge_plan``,
  ``dx_apply``
* transcripts family (from the ``ops_transcripts`` sibling module, once
  installed): ``transcript_cycle``

The sibling modules are imported tolerantly: while a sibling module is absent
(or its op is not yet defined), accessing its op raises a clear ``AttributeError``
instead of breaking the engine import. Once the sibling modules land, the
corresponding names resolve automatically (PEP 562 module ``__getattr__``).
"""
# ruff: noqa: F822  (lazy re-exported names resolve via PEP 562 __getattr__)
from __future__ import annotations

import importlib
import importlib.util

from .ops_vault import (
    BrainError,
    create_vault,
    doctor,
    register_vault,
    resolve_vault,
    status,
    validate_vault,
)

KNOWLEDGE_OPS = (
    "query", "capture", "knowledge_map", "relations", "references",
    "naming", "propose", "card", "document", "knowledge_plan", "dx_apply",
)
TRANSCRIPTS_OPS = ("transcript_cycle",)

_SIBLING_OF = {name: "ops_knowledge" for name in KNOWLEDGE_OPS}
_SIBLING_OF.update({name: "ops_transcripts" for name in TRANSCRIPTS_OPS})

def _load_sibling(name):
    """Import a sibling op module if it exists; return None when it is absent.

    ``importlib.util.find_spec`` on the fully dotted module name (rather than a
    bare ``from . import``) keeps this importable while the parent package is
    still partially initialized, and the absence of a sibling module degrades
    to ``None`` -- never to an import error at engine import time.
    """
    full = f"{__package__}.{name}"
    if importlib.util.find_spec(full) is not None:
        try:
            return importlib.import_module(full)
        except ModuleNotFoundError:
            return None
    return None


ops_knowledge = _load_sibling("ops_knowledge")
ops_transcripts = _load_sibling("ops_transcripts")
__all__ = [
    "BrainError",
    "capture",
    "card",
    "create_vault",
    "doctor",
    "document",
    "dx_apply",
    "knowledge_map",
    "knowledge_plan",
    "naming",
    "propose",
    "query",
    "references",
    "register_vault",
    "relations",
    "resolve_vault",
    "status",
    "transcript_cycle",
    "validate_vault",
]


def __getattr__(name: str):
    source = _SIBLING_OF.get(name)
    if source is not None:
        module = globals().get(source)
        if module is not None:
            try:
                return getattr(module, name)
            except AttributeError:
                pass  # fall through to the clear error below
        raise AttributeError(
            f"engine.api.{name} requires the {source} module, which is not installed yet. "
            f"Install the engine with the {source} operations to enable it."
        )
    raise AttributeError(f"module 'hermes_business_brain.engine.api' has no attribute {name!r}")
