"""Register an already-drafted D/X document, without approving its content.

Does not replace human validation, revision governance or the block contract.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

from .lib_ce import (
    make_note,
    notes_in_vault,
    split_frontmatter,
    validate_tags,
    visible_filename,
)
from .operacion import local_sources, safe_vault, unique_path, utcnow, valid_title
from .validar_boveda import validate

# Repository root (upstream operacion.ROOT analog): master repository that
# must never hold private business content; model data lives under engine/data.
ROOT = Path(__file__).resolve().parent.parent.parent
DATA = Path(__file__).resolve().parent / "data"


X_ID = re.compile(r"^X\d{2}-[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")

# Split concatenation (never contiguous in source): private-key detection markers.
_PEM_BEGIN = "-----BEGIN "
_PEM_SHAPE = "PRIVATE KEY-----"
_PEM_MARKERS = (_PEM_BEGIN + _PEM_SHAPE, "-----BEGIN OPENSSH " + "PRIVATE KEY-----")

# Closed exceptions for the two macOS system roots.
# Paths inside /tmp or /var receive no exception of their own.
_MACOS_SYSTEM_ALIASES = {
    Path("/var"): ("private/var", "/private/var", Path("/private/var")),
    Path("/tmp"): ("private/tmp", "/private/tmp", Path("/private/tmp")),
}


def _trusted_macos_system_alias(part: Path) -> bool:
    """Accepts ONLY /var and /tmp if the link belongs to the macOS OS.

    Verifies exact path, readlink target and physical target. No other
    symbolic path is allowed, nor a user-created link under those roots.
    On Linux no exception is granted.
    """
    if sys.platform != "darwin":
        return False
    rule = _MACOS_SYSTEM_ALIASES.get(part)
    if rule is None:
        return False
    relative_target, absolute_target, physical_target = rule
    try:
        return (os.readlink(part) in (relative_target, absolute_target)
                and part.resolve(strict=True) == physical_target)
    except (OSError, RuntimeError):
        return False


def _is_symlinked(path: Path) -> bool:
    """Blocks arbitrary symlinks; admits only fixed OS aliases."""
    item = path.expanduser().absolute()
    from .platform_fs import is_link_or_reparse
    for part in (item, *item.parents):
        if is_link_or_reparse(part) and not _trusted_macos_system_alias(part):
            return True
    return False


def _read_input(file_path: Path, vault: Path) -> tuple[str, str]:
    if _is_symlinked(file_path):
        raise ValueError("Input file symbolically linked; not used")
    source = file_path.expanduser().resolve()
    if source == ROOT or ROOT in source.parents:
        raise ValueError("Do not store private business documents inside the master repository")
    if source == vault or vault in source.parents:
        raise ValueError("The input draft must be outside the vault to avoid overwriting")
    if not source.is_file() or source.stat().st_size > 120000:
        raise ValueError("Draft missing or excessive (>120 kB)")
    original = source.read_bytes()
    text = original.decode("utf-8")
    if len(text.strip()) < 90 or not text.lstrip().startswith("# "):
        raise ValueError("A developed Markdown document with a title and content is required")
    if text.startswith("---\n"):
        raise ValueError("The input document must be without YAML; the system manages its properties")
    if any(marker in text for marker in _PEM_MARKERS):
        raise ValueError("The draft appears to contain a private key")
    return text, hashlib.sha256(original).hexdigest()


def _model_file(name: str) -> Path:
    engine = Path(__file__).resolve().parent
    candidates = (
        engine / "data" / "modelo" / name,
        engine.parent / "data" / "modelo" / name,
        Path(__file__).resolve().parents[1] / "modelo" / name,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Model data not found: " + name)


def _classes() -> set[str]:
    data = json.loads(_model_file("clases_documentales.json").read_text(encoding="utf-8"))
    return {item["id"] for item in data["clases"]}


def _existing_doc_ids(vault: Path) -> set[str]:
    out = set()
    for path in notes_in_vault(vault):
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("tipo") == "documento" and meta.get("doc_id"):
            out.add(str(meta["doc_id"]))
    return out


def create_document(
    vault_path: Path,
    class_id: str,
    title: str,
    content_file: Path,
    *,
    doc_id: str | None = None,
    sources: list[str] | None = None,
    editorial: str = "borrador",
    coverage: str | None = None,
    as_of: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Creates a new file in 10_Conocimiento/ with a never-approved state.

    D01-D07: one stable doc_id per family. X01-X07: its own identity Xnn-...
    Does not import legacy content; contents must have been obtained/authorized
    by Codex.
    """
    vault, cfg = safe_vault(vault_path)
    if class_id not in _classes():
        raise ValueError("Unknown document class; use D01-D07 or X01-X07")
    title = valid_title(title)
    labels = validate_tags(tags)
    if editorial not in {"borrador", "en_revision"}:
        raise ValueError("Creation only allows borrador or en_revision, never approved")
    if coverage is not None and coverage not in {"sin_fuente", "parcial", "suficiente_para_tarea", "no_aplica"}:
        raise ValueError("Unknown document coverage")
    if as_of is None:
        as_of = date.today().isoformat()
    else:
        as_of = date.fromisoformat(as_of).isoformat()
    if class_id.startswith("D"):
        if doc_id is not None and doc_id != class_id:
            raise ValueError("The D document family keeps its doc_id stable, equal to its class")
        doc_id = class_id
    elif doc_id is None:
        doc_id = class_id + "-" + uuid4().hex[:12].upper()
    if class_id.startswith("X") and (not X_ID.fullmatch(doc_id) or not doc_id.startswith(class_id + "-")):
        raise ValueError("The X file doc_id must be Xnn-ID and match its class")

    # All preflight happens before writing, including the links to sources.
    pre = validate(vault)
    if pre["errores"]:
        raise ValueError("The vault already has structural errors; do not write: " + "; ".join(pre["errores"][:3]))
    if doc_id in _existing_doc_ids(vault):
        raise FileExistsError("The document already exists by doc_id; review and propose changes, do not duplicate: " + doc_id)
    source_links = local_sources(vault, sources or [])
    if coverage is None:
        coverage = "parcial" if source_links else "sin_fuente"
    body, original_hash = _read_input(content_file, vault)
    target = vault / "10_Conocimiento" / visible_filename(title)
    unique_path(vault, target)

    metadata = {
        "id": doc_id,
        "doc_id": doc_id,
        "tipo": "documento",
        "clase": class_id,
        "empresa_id": cfg["company_id"],
        "schema_version": "0.9",
        "revision": "0.1",
        "estado_editorial": editorial,
        "cobertura": coverage,
        "vigencia": "sin_verificar",
        "sensibilidad": "interno",
        "registrado_en": utcnow(),
        "fecha_corte": as_of,
        "fuentes": source_links,
        **({"tags": labels} if labels else {}),
        "revisado_por": "por_validar",
        "insumo_sha256": original_hash,
    }
    # Do not interpret the input text as an already-approved state.
    new_content = make_note(metadata, body)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline='\n') as handle:
        handle.write(new_content)
    try:
        post = validate(vault)
        if post["errores"]:
            raise ValueError("The new document failed structural validation: " + "; ".join(post["errores"][:3]))
    except Exception:
        # Only this new file was created; the existing files remain.
        target.unlink()
        raise
    return {
        "doc_id": doc_id,
        "ruta": str(target),
        "clase": class_id,
        "revision": "0.1",
        "estado_editorial": editorial,
        "aprobado": False,
        "fuentes": sources or [],
        "insumo_sha256": original_hash,
        "bloques_vnext_con_contrato": "pendiente_validacion",
        "limite": "Creates a note under review; does NOT approve content, authority, relations or gates G1-G7",
    }
