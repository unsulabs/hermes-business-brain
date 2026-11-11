"""In-process English evolution operation (native engine, v2).

Mirrors the engine convention of the sibling ops modules: every function is
keyword-only, delegates to the backing engine module, and returns a plain
dict. Errors raised by the backing module propagate unchanged.
"""
from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - import tolerance
    from . import BrainError
except (ImportError, AttributeError):  # pragma: no cover
    class BrainError(Exception):
        """Engine-level failure raised when the engine package is not present."""


def _load(name: str):
    import importlib

    try:
        return importlib.import_module("." + name, __package__)
    except ImportError as exc:
        raise BrainError(f"Engine module not available: {name} ({exc})") from exc


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except BrainError:
        raise
    except (ValueError, FileExistsError, PermissionError, UnicodeError,
            KeyError, OSError):
        raise
    except Exception as exc:
        raise BrainError(f"Unexpected engine failure: {exc}") from exc


def evolution_scan(*, vault, **kwargs) -> dict:
    """Read-only evolution scan: promotion candidates and due revisits."""
    mod = _load("evolucion")
    value = str(vault or "").strip()
    if not value:
        raise ValueError("vault is required")
    return _handle(mod.plan_evolucion, vault=Path(value))
