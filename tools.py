"""In-process engine handlers for the 18 hermes-business-brain tools (v2).

Every handler calls ``hermes_business_brain.engine.api.<op>(**kwargs)`` IN-PROCESS - no
subprocess, no shell, no network. The engine is imported lazily inside the handler, so the plugin
registers cleanly (and ``hermes plugins doctor`` passes) even before the engine package exists;
when it is missing, each tool fails gracefully with a clear English message instead of crashing
registration.

Result envelope (returned as a JSON string, per the Hermes tool contract)::

    {"stdout": str, "stderr": str, "exit_code": int, "summary": str}

exit_code semantics:
    0  success
    2  engine refused the operation / input validation failed (mirrors the upstream CLI's exit 2)
    1  unexpected error (engine unavailable, timeout, internal exception)

Execution is guarded by a ~120 second timeout via a shared ThreadPoolExecutor; a timed-out call
returns exit 1 with an English summary.
"""

from __future__ import annotations

import concurrent.futures
import json
from typing import Any, Callable, Optional

from . import schemas

#: Engine package/API location (imported lazily on first tool call).
ENGINE_API_MODULE = "hermes_business_brain.engine.api"

#: Per-call ceiling for engine operations.
TOOL_TIMEOUT_SECONDS = 120

#: Ops the engine api module exposes, keyed by plugin tool name. The engine implements each op as
#: ``api.<op>(**kwargs)`` with keyword arguments mirroring the tool schema property names.
OP_BY_TOOL: dict[str, str] = {
    "brain_doctor": "doctor",
    "brain_create_vault": "create_vault",
    "brain_validate_vault": "validate_vault",
    "brain_status": "status",
    "brain_register_vault": "register_vault",
    "brain_resolve_vault": "resolve_vault",
    "brain_query": "query",
    "brain_capture": "capture",
    "brain_knowledge_map": "knowledge_map",
    "brain_relations": "relations",
    "brain_references": "references",
    "brain_naming": "naming",
    "brain_transcript_cycle": "transcript_cycle",
    "brain_propose": "propose",
    "brain_card": "card",
    "brain_document": "document",
    "brain_knowledge_plan": "knowledge_plan",
    "brain_dx_apply": "dx_apply",
    "brain_evolution_scan": "evolution_scan",
}

_EMOJI = "\U0001f9e0"  # brain
_TOOLSET = "hermes-business-brain"

#: Shared executor so a hung engine call cannot block registration or other tools beyond the cap.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="bb-brain")
_ENGINE_IMPORT_ERROR: Optional[str] = None


class EngineUnavailable(RuntimeError):
    """The engine package could not be imported (plugin layer still registers fine)."""


def _load_engine_api() -> Any:
    """Import and return the engine api module, caching failures with a clear message."""
    global _ENGINE_IMPORT_ERROR
    try:
        import importlib

        api = importlib.import_module(ENGINE_API_MODULE)
        _ENGINE_IMPORT_ERROR = None
        return api
    except Exception as exc:  # noqa: BLE001 - every failure mode becomes a clear tool message
        _ENGINE_IMPORT_ERROR = (
            f"engine unavailable: could not import '{ENGINE_API_MODULE}' "
            f"({type(exc).__name__}: {exc}). The 'hermes-business-brain' engine package is not "
            "installed in this environment; install the plugin's Python dependencies and restart "
            "Hermes, then retry."
        )
        raise EngineUnavailable(_ENGINE_IMPORT_ERROR) from exc


def _envelope(stdout: str, stderr: str, exit_code: int, summary: str) -> dict[str, Any]:
    return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code, "summary": summary}


def _success_summary(op: str) -> str:
    return f"{op} completed successfully (exit 0)."


def _format_payload(payload: Any) -> str:
    """Render an engine result payload for stdout."""
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(payload)


def _normalize_result(op: str, result: Any) -> dict[str, Any]:
    """Normalize an engine op result into the stable envelope.

    Accepted engine contracts:
      * an envelope-like dict (any of stdout/stderr/exit_code/summary present) -- passed through;
      * a dict with an ``ok`` boolean -- ok:False maps to exit 2 (refused);
      * any other value -- treated as a successful result payload.
    """
    if isinstance(result, dict):
        keys = set(result)
        if keys & {"stdout", "stderr", "exit_code", "summary"}:
            raw_code = result.get("exit_code")
            if raw_code not in (0, 1, 2):
                raw_code = 0 if result.get("ok", True) else 2
            return _envelope(
                str(result.get("stdout") or ""),
                str(result.get("stderr") or ""),
                int(raw_code),
                str(result.get("summary") or _success_summary(op)),
            )
        if "ok" in keys:
            if result.get("ok"):
                return _envelope(_format_payload(result), "", 0, _success_summary(op))
            message = str(
                result.get("error")
                or result.get("message")
                or result.get("summary")
                or "the engine refused the operation"
            )
            return _envelope("", message, 2, f"{op} refused: {message}")
    return _envelope(_format_payload(result), "", 0, _success_summary(op))


def _is_engine_refusal(exc: BaseException, api: Any) -> bool:
    """True when *exc* means the engine refused or rejected the request (exit 2)."""
    if isinstance(exc, (ValueError, FileExistsError, PermissionError, UnicodeError, KeyError, OSError)):
        return True
    if isinstance(exc, Exception):
        name = type(exc).__name__
        if "Refused" in name or "Validation" in name or "BrainError" in name:
            return True
        # Engine-declared refusal bases, when defined.
        for marker in ("EngineRefused", "EngineValidationError", "ValidationError"):
            if getattr(api, marker, None) and isinstance(exc, getattr(api, marker)):
                return True
    return False


def _run_op(op: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Import the engine and run one op, mapping outcomes to the envelope (no timeout here)."""
    try:
        api = _load_engine_api()
    except EngineUnavailable as exc:
        return _envelope("", str(exc), 1, f"{op} could not run: {exc}")

    try:
        fn = getattr(api, op, None)
        if fn is None or not callable(fn):
            message = (
                f"engine contract violation: '{ENGINE_API_MODULE}' has no callable '{op}'. "
                "The installed engine does not match the plugin's expected ops; reinstall the "
                "plugin to the matching engine version."
            )
            return _envelope("", message, 1, f"{op} could not run: {message}")
        result = fn(**dict(kwargs))
        return _normalize_result(op, result)
    except Exception as exc:  # noqa: BLE001 - classification below decides the exit code
        stderr = f"{type(exc).__name__}: {exc}"
        if _is_engine_refusal(exc, api):
            return _envelope("", stderr, 2, f"{op} refused the request: {exc}")
        return _envelope("", stderr, 1, f"{op} failed with an unexpected error: {exc}")


def _execute_with_timeout(op: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Run *op* in the shared executor, returning a timeout envelope at ~120s."""
    try:
        future = _EXECUTOR.submit(_run_op, op, kwargs)
        return future.result(timeout=TOOL_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        message = (
            f"{op} timed out after {TOOL_TIMEOUT_SECONDS} seconds and was abandoned; "
            "the engine may still be finishing in the background. Retry with a narrower request "
            "if this persists."
        )
        return _envelope("", message, 1, message)
    except Exception as exc:  # noqa: BLE001
        return _envelope("", f"{type(exc).__name__}: {exc}", 1, f"{op} could not run: {exc}")


def make_handler(op: str) -> Callable[..., str]:
    """Build a Hermes tool handler for engine op *op*; always returns a JSON envelope string."""

    def _handler(args: Optional[dict], **kwargs: Any) -> str:
        data = dict(args or {})
        if kwargs:
            data.update({k: v for k, v in kwargs.items() if k not in data})
        envelope = _execute_with_timeout(op, data)
        return json.dumps(envelope)

    _handler.__name__ = f"handler_{op}"
    _handler.__qualname__ = f"handler_{op}"
    return _handler


def build_tool_specs() -> list[dict[str, Any]]:
    """Combine schemas + op mapping into the registration specs used by __init__.register()."""
    specs: list[dict[str, Any]] = []
    for tool_name, schema in schemas.TOOL_SCHEMAS.items():
        op = OP_BY_TOOL[tool_name]
        specs.append(
            {
                "name": tool_name,
                "toolset": _TOOLSET,
                "schema": schema,
                "handler": make_handler(op),
                "description": schema.get("description", ""),
                "emoji": _EMOJI,
                "op": op,
            }
        )
    return specs


TOOL_SPECS: list[dict[str, Any]] = build_tool_specs()

#: Every tool name this plugin registers, in manifest order.
TOOL_NAMES: list[str] = [spec["name"] for spec in TOOL_SPECS]
