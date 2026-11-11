"""In-process English knowledge operations API (native engine, v2).

Every function is keyword-only, mirrors one upstream cerebro.py subcommand
(or the plugin_references wrapper) flag for flag, and returns a plain dict
with the upstream JSON keys preserved and English messages inside.

Sibling engine modules are imported lazily so this module remains importable
even while the engine package is still landing. Domain errors raised by the
backing modules (ValueError, FileExistsError, PermissionError, UnicodeError,
KeyError, OSError) propagate unchanged, preserving upstream error semantics;
hard/unexpected engine failures are wrapped in engine.BrainError (or the
local fallback defined at the bottom of this module when the engine package
does not define it yet).
"""
from __future__ import annotations

from pathlib import Path

# BrainError: the core engine package (engine/__init__.py) is expected to
# define it. Fall back to a local class when the package is not ready yet.
try:  # pragma: no cover - import tolerance
    from . import BrainError
except (ImportError, AttributeError):  # pragma: no cover
    class BrainError(Exception):
        """Engine-level failure raised when the engine package is not present."""


def _load(name: str):
    """Lazily import one engine submodule (sibling or knowledge module)."""
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


def _path(value):
    if value is None:
        return None
    return value if isinstance(value, Path) else Path(value)


# ---------------------------------------------------------------------------
# consulta-contextual
# ---------------------------------------------------------------------------

def query(*, vault, texto, tema=None, ambito=None, fecha=None, limite=10,
          orientar=False) -> dict:
    """Candidates by literal text (and optional topic/scope/date); no semantics."""
    mod = _load("consulta_contextual")
    return _handle(mod.consulta, _path(vault), texto, tema=tema, ambito=ambito,
                   fecha=fecha, max_results=limite, orientar=bool(orientar))


# ---------------------------------------------------------------------------
# capturar (registro_descubrimiento)
# ---------------------------------------------------------------------------

def capture(*, vault, source, title, sources=None) -> dict:
    """Stores preliminary findings as a draft capture; never approved knowledge."""
    mod = _load("registro_descubrimiento")
    return _handle(mod.capture_discovery, _path(vault), title, _path(source),
                   sources=list(sources or []))


# ---------------------------------------------------------------------------
# mapa-conocimiento / publicar-mapa
# ---------------------------------------------------------------------------

def knowledge_map(*, vault, publish=False, sha_actual=None, sha_propuesto=None,
                  confirmacion=None, backup_dir=None) -> dict:
    """Read-only map preview (default) or publication with SHA confirmation."""
    mod = _load("mapa_conocimiento")
    if not publish:
        if sha_actual or sha_propuesto or confirmacion or backup_dir:
            raise ValueError("Publication arguments require publish=True")
        return _handle(mod.previsualizar, _path(vault))
    if not (sha_actual and sha_propuesto and confirmacion and backup_dir):
        raise ValueError("publish=True requires sha_actual, sha_propuesto, confirmacion and backup_dir")
    return _handle(mod.publicar, _path(vault), sha_actual=sha_actual,
                   sha_propuesto=sha_propuesto, confirmacion=confirmacion,
                   backup_dir=_path(backup_dir))


# ---------------------------------------------------------------------------
# relaciones
# ---------------------------------------------------------------------------

def relations(*, vault, id=None) -> dict:
    """Queries typed relations and their real state (read-only)."""
    mod = _load("relaciones")
    return _handle(mod.query, _path(vault), source_id=id)


def relation_propose(*, vault, source_id, target_id, predicate, sources,
                     scope, reason) -> dict:
    """Proposes a typed edge: never approves it."""
    mod = _load("relaciones")
    return _handle(mod.propose, _path(vault), source_id, target_id, predicate,
                   fuentes=list(sources), ambito=scope, motivo=reason)


def relation_confirm(*, vault, relation_id, sha_relation, reviewer,
                     authorization_ref, confirmation) -> dict:
    """Registers the declared human ratification of a relation."""
    mod = _load("relaciones")
    return _handle(mod.confirm, _path(vault), relation_id, sha_relation,
                   revisor=reviewer, referencia_autorizacion=authorization_ref,
                   confirmacion=confirmation)


# ---------------------------------------------------------------------------
# referencias_externas (via plugin_references facade)
# ---------------------------------------------------------------------------

def references(*, vault=None, bank=None, action="verify", metadata=None,
               reference_id=None, version_id=None, refs=None, company=None,
               audience=None, purpose=None, commit=False, require_read=True,
               require_internal=False, decision=None) -> dict:
    """Local versioned external-reference registry over a private bank.

    `bank` is the private custody directory; `vault`, when given, is accepted
    as an alias for `bank` (the v2 API contract keeps vault in all knowledge
    signatures). Actions: register, read, decisions, verify.
    """
    bank = bank if bank is not None else vault
    if bank is None:
        raise ValueError("A bank (or vault) path is required")
    mod = _load("plugin_references")
    return _handle(mod.run, action, bank=_path(bank), metadata=metadata,
                   reference_id=reference_id, version_id=version_id, refs=refs,
                   company=company, audience=audience, purpose=purpose,
                   commit=commit, require_read=require_read,
                   require_internal=require_internal, decision=decision)


# ---------------------------------------------------------------------------
# nombres_legibles
# ---------------------------------------------------------------------------

def naming(*, vault, spec, apply=False, sha_plan=None, backup_dir=None) -> dict:
    """Plans (default) or applies readable filename changes from a spec JSON."""
    mod = _load("nombres_legibles")
    if not apply:
        if sha_plan or backup_dir:
            raise ValueError("apply arguments require apply=True")
        return _handle(mod.plan, _path(vault), _path(spec))
    if not (sha_plan and backup_dir):
        raise ValueError("apply=True requires sha_plan and backup_dir")
    return _handle(mod.apply, _path(vault), _path(spec), _path(backup_dir), sha_plan)


# ---------------------------------------------------------------------------
# proponer (bandeja) - operacion (core sibling module)
# ---------------------------------------------------------------------------

def propose(*, vault, id, motivo, archivo, author="agente") -> dict:
    """Registers a suggested change in the tray; never touches the objective note."""
    try:
        operacion = _load("operacion")
    except BrainError as exc:
        raise BrainError("propose requires the core operacion module: " + str(exc)) from exc
    return _handle(operacion.propose_change, _path(vault), id, motivo,
                   archivo, author=author)


# ---------------------------------------------------------------------------
# ficha (card) - operacion (core sibling module)
# ---------------------------------------------------------------------------

def card(*, vault, tipo, titulo, resumen="", archivo=None, sources=None,
         etiquetas=None) -> dict:
    """Creates a draft entity card from a specific type; never invents data."""
    try:
        operacion = _load("operacion")
    except BrainError as exc:
        raise BrainError("card requires the core operacion module: " + str(exc)) from exc
    return _handle(operacion.create_ficha, _path(vault), tipo, titulo,
                   resumen=resumen, sources=list(sources or []) or None,
                   tags=list(etiquetas or []) or None,
                   content_file=_path(archivo))


# ---------------------------------------------------------------------------
# documento
# ---------------------------------------------------------------------------

def document(*, vault, clase, titulo, archivo, doc_id=None, estado="borrador",
             cobertura=None, fecha_corte=None, sources=None, etiquetas=None) -> dict:
    """Registers an already-drafted D/X document without approving it."""
    mod = _load("documentos")
    return _handle(mod.create_document, _path(vault), clase, titulo, _path(archivo),
                   doc_id=doc_id, sources=list(sources or []) or None,
                   editorial=estado, coverage=cobertura, as_of=fecha_corte,
                   tags=list(etiquetas or []) or None)


# ---------------------------------------------------------------------------
# plan-conocimiento
# ---------------------------------------------------------------------------

def knowledge_plan(*, vault, archivo) -> dict:
    """Read-only audit of a knowledge plan previously reasoned by an external agent."""
    mod = _load("plan_conocimiento")
    return _handle(mod.planificar, _path(vault), _path(archivo))


# ---------------------------------------------------------------------------
# revisiones_dx
# ---------------------------------------------------------------------------

def dx_apply(*, vault, propuesta, sha_original, sha_candidato, sha_fuentes=None,
             responsable, referencia_autorizacion, backup_dir) -> dict:
    """Applies an EXISTING D/X proposal after specific authorization."""
    mod = _load("revisiones_dx")
    return _handle(mod.aplicar, _path(vault), propuesta, expected_sha=sha_original,
                   candidate_sha=sha_candidato, source_sha=sha_fuentes,
                   responsable=responsable,
                   referencia_autorizacion=referencia_autorizacion,
                   backup_dir=_path(backup_dir))


def dx_preview(*, vault, doc_id, archivo, sources=None) -> dict:
    """Read-only: current document, external draft and localized diff."""
    mod = _load("revisiones_dx")
    return _handle(mod.previsualizar, _path(vault), doc_id, _path(archivo),
                   sources=list(sources or []) or None)


def dx_prepare(*, vault, doc_id, archivo, sources=None) -> dict:
    """Stores the D/X proposal and draft without touching the current document."""
    mod = _load("revisiones_dx")
    return _handle(mod.preparar, _path(vault), doc_id, _path(archivo),
                   sources=list(sources or []) or None)


def dx_restore(*, vault, doc_id, historial, sha_actual, responsable,
               referencia_autorizacion, backup_dir) -> dict:
    """Restores a D/X version as a new revision (history is not destroyed)."""
    mod = _load("revisiones_dx")
    return _handle(mod.restaurar, _path(vault), doc_id, historial,
                   expected_sha=sha_actual, responsable=responsable,
                   referencia_autorizacion=referencia_autorizacion,
                   backup_dir=_path(backup_dir))


def dx_evaluate(*, vault, doc_id, acta, sha_actual) -> dict:
    """Registers a G1-G7 editorial evaluation without modifying the D/X."""
    mod = _load("revision_editorial")
    return _handle(mod.registrar_evaluacion, _path(vault), doc_id, _path(acta),
                   expected_sha=sha_actual)


def dx_approve(*, vault, evaluacion, sha_actual, responsable,
               referencia_autorizacion, backup_dir, confirmacion) -> dict:
    """Integral editorial promotion with evaluation, authorization and backup."""
    mod = _load("revision_editorial")
    return _handle(mod.aprobar_documento, _path(vault), evaluacion,
                   expected_sha=sha_actual, responsable=responsable,
                   referencia_autorizacion=referencia_autorizacion,
                   backup_dir=_path(backup_dir), confirmacion=confirmacion)


# ---------------------------------------------------------------------------
# grafo (graph export) - upstream cerebro.py grafo
# ---------------------------------------------------------------------------

def graph_export(*, vault, output=None) -> dict:
    """Exports the typed-relations and navigation graph as JSON inside the vault.

    vault    absolute path to the vault (notes + imported handoff manifests).
    output   optional absolute path; must stay inside the vault (defaults to
             90_Sistema/grafo.json, as upstream).
    Returns the upstream summary dict (salida, nodos, aristas).
    """
    mod = _load("exportar_grafo")
    vault = _path(vault).expanduser().resolve()
    out = _path(output)
    if out is None:
        out = vault / "90_Sistema" / "grafo.json"
    out = out.expanduser().absolute()
    if vault not in out.parents:
        raise ValueError("The graph must be saved inside the vault itself")
    data = _handle(mod.graph, vault)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_graph_json(data), encoding="utf8", newline="\n")
    return {"salida": str(out), "nodos": len(data["nodos"]), "aristas": len(data["aristas"])}


def _graph_json(data: dict) -> str:
    import json as _json
    return _json.dumps(data, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Plugin wrapper entry point (kept for CLI/tool parity; importable without it).
# ---------------------------------------------------------------------------

def run(action: str, **kwargs) -> dict:
    """Dispatches a knowledge action by name; keyword arguments as above."""
    dispatch = {
        "query": query,
        "capture": capture,
        "knowledge_map": knowledge_map,
        "relations": relations,
        "relation_propose": relation_propose,
        "relation_confirm": relation_confirm,
        "references": references,
        "naming": naming,
        "propose": propose,
        "card": card,
        "document": document,
        "knowledge_plan": knowledge_plan,
        "grafo": graph_export,
        "dx_apply": dx_apply,
        "dx_preview": dx_preview,
        "dx_prepare": dx_prepare,
        "dx_restore": dx_restore,
        "dx_evaluate": dx_evaluate,
        "dx_approve": dx_approve,
    }
    if action not in dispatch:
        raise ValueError(f"Unknown knowledge action: {action!r}")
    return dispatch[action](**kwargs)


__all__ = [
    "BrainError",
    "capture",
    "card",
    "document",
    "dx_apply",
    "dx_approve",
    "dx_evaluate",
    "dx_prepare",
    "dx_preview",
    "dx_restore",
    "graph_export",
    "knowledge_map",
    "knowledge_plan",
    "naming",
    "propose",
    "query",
    "references",
    "relation_confirm",
    "relation_propose",
    "relations",
    "run",
]
