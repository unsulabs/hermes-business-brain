"""Provisional discovery capture; never approved knowledge."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .lib_ce import make_note, visible_filename
from .operacion import (
    index_ids,
    local_sources,
    safe_vault,
    unique_path,
    utcnow,
    valid_title,
)

# Repository root (upstream operacion.ROOT analog): the git checkout that
# must never hold private business content.
ROOT = Path(__file__).resolve().parent.parent.parent

# Split concatenation (never contiguous in source): private-key detection markers.
_PEM_BEGIN = "-----BEGIN "
_PEM_SHAPE = "PRIVATE KEY-----"
_PEM_MARKERS = (_PEM_BEGIN + _PEM_SHAPE, "-----BEGIN OPENSSH " + "PRIVATE KEY-----")


def capture_discovery(vault_path: Path, title: str, content_file: Path,
                      *, sources: list[str] | None = None) -> dict:
    vault, cfg = safe_vault(vault_path)
    title = valid_title(title)
    raw = content_file.expanduser()
    if raw.is_symlink():
        raise ValueError("The input file cannot be a symbolic link")
    source = raw.resolve()
    if source == ROOT or ROOT in source.parents:
        raise ValueError("Do not prepare private content inside the Git repository")
    if source == vault or vault in source.parents:
        raise ValueError("Prepare the capture outside the vault to avoid duplication")
    if not source.is_file() or source.stat().st_size > 24000:
        raise ValueError("Input missing or excessive; use a brief synthesis")
    text = source.read_text(encoding="utf8").strip()
    if len(text) < 20 or "\x00" in text:
        raise ValueError("Empty or invalid capture")
    if any(x in text for x in _PEM_MARKERS):
        raise ValueError("Capture contains a credential: do not store")
    refs = local_sources(vault, sources or [])
    nid = "CAP-" + uuid4().hex[:12].upper()
    if nid in index_ids(vault):
        raise ValueError("ID collision")
    target = vault / "90_Sistema" / "Descubrimiento" / visible_filename(title)
    unique_path(vault, target)
    front = {
        "id": nid, "tipo": "registro_descubrimiento", "clase": "control",
        "empresa_id": cfg["company_id"], "estado_editorial": "borrador",
        "estado_conocimiento": "pendiente", "vigencia": "sin_verificar",
        "sensibilidad": "interno", "registrado_en": utcnow(),
        "fuentes": refs, "autoridad": "ninguna", "revisado_por": "por_validar",
    }
    body = (
        "# " + title + "\n\n"
        "> **PROVISIONAL CAPTURE.** This is not an approved business document, "
        "contract, sale or automatic proof of company participation.\n\n"
        "## Findings to cross-check\n\n" + text + "\n\n"
        "## Validation pending\n\n"
        "- [ ] Separate observations, interpretations and company attributions.\n"
        "- [ ] Cross-check authorized original sources and validity.\n"
        "- [ ] Review with the owner before integrating as D/X or entity.\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf8", newline='\n') as handle:
        handle.write(make_note(front, body))
    return {"id": nid, "ruta": str(target), "estado": "borrador_no_autoritativo",
            "fuentes": sources or [], "aprobado": False,
            "importado_como_conocimiento": False}
