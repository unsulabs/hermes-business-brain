"""In-process English operations over the Business Brain vault engine (no subprocess).

Each operation is a thin keyword-argument wrapper over the adapted upstream
logic modules, mirroring the upstream CLI flags they wrap. Results are plain
dicts whose JSON keys are identical to the upstream commands' output. Hard
(non-success) errors are raised as :class:`BrainError` with an English message
-- the in-process equivalent of the upstream CLI's non-zero error exit.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import crear_instancia, doctor_preflight, operacion, validar_boveda
from . import registrar_boveda_obsidian as registrar
from . import resolver_boveda_obsidian as resolver

__all__ = [
    "BrainError",
    "create_vault",
    "doctor",
    "register_vault",
    "resolve_vault",
    "status",
    "validate_vault",
]


class BrainError(Exception):
    """Hard engine error: the operation did not reach a success state.

    The message is always English; the transition from the upstream CLI's
    ``SystemExit(2)`` (or ``SystemExit(1)`` where the CLI reports validation
    failure) to a raised exception is the in-process contract.
    """


_HARD_ERRORS = (ValueError, FileExistsError, PermissionError, UnicodeError, KeyError, OSError, json.JSONDecodeError)


def _hard(exc: Exception) -> BrainError:
    """Convert an underlying failure to the engine's error type, keeping its message."""
    if isinstance(exc, BrainError):
        return exc
    return BrainError(str(exc))


def doctor(*, vault=None) -> dict:
    """Read-only environment/dependency diagnostic (upstream ``doctor``).

    Never installs anything; installs no dependencies. ``vault`` is optional.
    """
    try:
        return doctor_preflight.diagnose(vault)
    except _HARD_ERRORS as exc:
        raise _hard(exc) from exc


def create_vault(*, id: str, name: str, dest) -> dict:
    """Create a new company vault from the bundled template; never overwrites.

    ``id`` must match ``[A-Za-z0-9][A-Za-z0-9_-]{1,63}`` (2–64 characters).
    """
    try:
        path = crear_instancia.create(id, name, Path(dest))
    except _HARD_ERRORS as exc:
        raise _hard(exc) from exc
    return {'creada': str(path), 'estado': 'infraestructura_sin_conocimiento',
            'nota': 'Open and verify manually in Obsidian'}


def validate_vault(*, vault) -> dict:
    """Validate integrity of notes, ids, wiki links and imported transfers.

    Returns the upstream outcome dict (``notas``/``ids``/``bloques``/
    ``traspasos``/``errores``/``advertencias``/``tipos``); a failed validation
    is reported through the ``errores`` list, not an exception.
    """
    try:
        return validar_boveda.validate(Path(vault))
    except _HARD_ERRORS as exc:
        raise _hard(exc) from exc


def status(*, vault) -> dict:
    """Owner-oriented structural summary of the company vault (upstream ``estado``)."""
    try:
        return operacion.summary(Path(vault))
    except _HARD_ERRORS as exc:
        raise _hard(exc) from exc


def register_vault(*, vault, name, alias, proyecto=None, nativo=None,
                   registry=None, instructions=None, entrypoint=None) -> dict:
    """Register a vault already open in Obsidian for the local selector router.

    ``proyecto`` is the agent project directory that must resolve the vault;
    ``nativo`` is the native Obsidian registry path. Neither the vault nor the
    native registry is created or modified. ``registry``/``instructions``/
    ``entrypoint`` default to the selector registry
    ``~/.config/hermes-business-brain/vaults.json`` and the instance files
    ``90_Sistema/Como_usar.md`` / ``Inicio.md`` like the upstream CLI flags.
    """
    try:
        result = registrar.register(
            Path(vault), name, alias,
            Path(registry) if registry is not None else registrar.REGISTRY,
            Path(nativo) if nativo is not None else registrar.NATIVE,
            instructions if instructions is not None else '90_Sistema/Como_usar.md',
            entrypoint if entrypoint is not None else 'Inicio.md',
            Path(proyecto) if proyecto is not None else None,
        )
    except _HARD_ERRORS as exc:
        raise _hard(exc) from exc
    return result


def resolve_vault(*, selector=None, project=None, nativo=None, registry=None) -> dict:
    """Resolve an explicit vault selector or project against the registries.

    Provide exactly one of ``selector`` (a registered id/name/alias or
    absolute path) or ``project`` (an agent project directory). ``nativo`` is
    the native Obsidian registry path; ``registry`` defaults to the selector
    registry. Read-only; opens no vault contents.
    """
    try:
        result = resolver.resolve(
            Path(registry) if registry is not None else registrar.REGISTRY,
            Path(nativo) if nativo is not None else registrar.NATIVE,
            selector=selector,
            project=Path(project) if project is not None else None,
        )
    except _HARD_ERRORS as exc:
        raise _hard(exc) from exc
    return result
