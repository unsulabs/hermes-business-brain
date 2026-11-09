"""In-process API for the native English transcript pipeline.

Wraps the translated transcript family (transcripciones_*.py, importar_traspaso,
exportar_producto) so a host process can run every upstream pipeline step without
subprocesses or argparse. Return values are plain dicts with upstream JSON keys
preserved (resultado.v1 envelopes) and English messages. Hard errors raise
BrainError instead of returning a BLOCKED envelope.

BrainError is imported from the engine core (engine/api.py) when available;
until that sibling module lands, a local fallback class with the same shape is
used (see _verify/engine-transcripts.md).
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["BrainError", "transcript_cycle", "import_handoff", "export_product",
           "steps", "STEPS"]


try:  # engine core owns the canonical error type
    from .api import BrainError
except ImportError:  # pragma: no cover - sibling engine core not yet present
    class BrainError(Exception):
        """Native engine failure with a stable machine code.

        Local fallback definition used until engine/api.py provides BrainError;
        the sibling copy wins automatically once it lands.
        """
        def __init__(self, code="TRANSCRIPT_OPERATION_FAILED", message="Transcript operation failed"):
            self.code = code
            super().__init__(f"{code}: {message}")


STEPS = ("registrar", "ingresar", "estado", "verificar", "inventario-validar", "conciliar",
         "segmentar", "analizar", "cobertura", "indexar", "buscar", "revisar-antecedentes",
         "permiso", "taxonomia")


def steps():
    """The step set the upstream transcripciones pipeline supports."""
    return STEPS


def _engine_transcripts():
    from . import transcripciones
    return transcripciones


def _wrap(error):
    code = getattr(error, "code", None) or "TRANSCRIPT_OPERATION_FAILED"
    message = str(error) or "Transcript operation failed"
    return _brain_error(code, message)


def _brain_error(code, message):
    """Build a BrainError compatible with both the engine-core class and the
    local fallback: engine core takes a single positional message; the local
    fallback takes code/message keywords. The code rides as an attribute."""
    try:
        error = BrainError(code=code, message=message)
    except TypeError:
        error = BrainError(f"{code}: {message}" if code else message)
    try:
        error.code = code
    except AttributeError:
        pass
    return error


def transcript_cycle(*, vault, step, profile, request_id, purpose,
                     audience=None, commit=False, output=None, **options):
    """Run one transcript pipeline step against a private transcript bank.

    Parameters mirror the upstream CLI flags:
      vault        transcript bank root (upstream --bank); must sit outside any
                   Obsidian vault and any Git worktree (validated by the engine).
      step         one of steps(): registrar, ingresar, estado, verificar,
                   inventario-validar, conciliar, segmentar, analizar, cobertura,
                   indexar, buscar, revisar-antecedentes, permiso, taxonomia.
      profile      company profile: a dict (company_id + allowed_purposes,
                   optional vault/bank) or a path to a sealed profile JSON file.
      request_id   caller-assigned request identifier (safe_id format).
      purpose      one of the profile's allowed purposes (eg custody,
                   local_analysis, internal_query).
      audience     required for segmentar/analizar/cobertura/indexar/
                   revisar-antecedentes; optional for estado.
      commit       False previews the local custody mutation, True applies it.
      output       optional immutable JSON report path (required for buscar).
      **options    step-specific flags: capture_manifest, file/payload/
                   parts_manifest, source_id, account_id, attempt_id, closed,
                   expected_parts, tr_id, version, policy, max_core_bytes,
                   context_bytes, input, event, run, snapshot, request, results,
                   previous, taxonomy_version.

    Returns the upstream result dict (schema_version "resultado.v1", operation,
    request_id, status, warnings, errors, evidence, ...). Raises BrainError on
    validation or IO failures; the error code (eg "UNSAFE_ID") is preserved.
    """
    transcripts = _engine_transcripts()
    if step not in transcripts.COMMANDS:
        raise _brain_error("COMMAND_UNKNOWN", f"Unknown transcript step '{step}'")
    from .transcripciones_modelo import ModelError
    try:
        return transcripts.execute_request(command=step, bank=vault, profile=profile,
                                           purpose=purpose, request_id=request_id,
                                           audience=audience, commit=commit,
                                           output=output, options=options)
    except BrainError:
        raise
    except (ModelError, OSError, ValueError, TypeError, KeyError) as exc:
        raise _wrap(exc) from exc


def import_handoff(*, vault, manifest, allow_real=False):
    """Import a validated vNext-0.9 handoff package into an Obsidian vault.

    vault      absolute path to the target Obsidian vault (must already have
               90_Sistema/config_empresa.yaml and match the package company).
    manifest   absolute path to the sealed vNext-0.9 manifest JSON.
    allow_real False rejects packages whose company is not synthetic (upstream
               --permitir-real); the operator must authorize those explicitly.

    Requires the vendored vNext-0.9 contract validator
    (engine/validador_de_traspaso.py, shipped in this package) and its schema:
    `Esquema_Manifiesto_vNext.schema.json` must sit next to the manifest (the
    engine also falls back to its shipped copy under data/contratos/vNext-0.9/).
    Returns the upstream summary dict with keys empresa, documentos, bloques,
    fuentes_referenciadas, relaciones, pruebas_semanticas_pendientes. Raises
    BrainError when the schema is unavailable, ValueError on contract or
    company rejection.
    """
    from .importar_traspaso import import_package
    try:
        return import_package(Path(manifest), Path(vault), allow_real=allow_real)
    except BrainError:
        raise
    except Exception as exc:
        raise _wrap(exc) from exc


def export_product(*, vault, destination):
    """Export the versioned product archive (software only, no private data).

    vault        absolute path to the product Git repository (the repo root).
    destination  absolute path of the output ZIP; must be outside the repo.

    Requires a committed Git HEAD in the repository. Returns the upstream dict
    (sha_producto, archivos, salida, manifest_sha256, material_privado_incluido).
    Raises BrainError on packaging violations.
    """
    from .exportar_producto import exportar
    try:
        return exportar(Path(vault), Path(destination))
    except BrainError:
        raise
    except Exception as exc:
        raise _wrap(exc) from exc
