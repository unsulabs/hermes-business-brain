"""Safe revisions of D/X documents: prepare, apply and restore.

Does NOT certify consent or approve assertions. Authorization is obtained
outside the program; the references entered here only record that statement.
Does not run actions on external services nor writes business information to
Git.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .documentos import _is_symlinked, _read_input
from .lib_ce import (
    BLOCK_RE,
    make_note,
    notes_in_vault,
    resolve_link,
    split_frontmatter,
    target_index,
    wiki_targets,
)
from .operacion import local_sources, safe_vault, utcnow
from .platform_fs import private_directory
from .validar_boveda import validate

# Repository root (upstream operacion.ROOT analog): backups and proposals must
# stay outside the master repository.
ROOT = Path(__file__).resolve().parent.parent.parent

DOC_RE = re.compile(r"^(?:D0[1-7]|X0[1-7]-[A-Za-z0-9][A-Za-z0-9_-]{2,63})$")
ITEM_RE = re.compile(r"^(?:PRDX|REVDX)-[A-F0-9]{12}$")
REV_RE = re.compile(r"^(\d{1,5})\.(\d{1,5})$")
PROPOSALS = Path("90_Sistema") / "Propuestas_DX"
HISTORY = Path("90_Sistema") / "Historial_DX"

# Split concatenation (never contiguous in source): private-key detection markers.
_PEM_BEGIN = "-----BEGIN "
_PEM_SHAPE = "PRIVATE KEY-----"
_PEM_MARKERS = (_PEM_BEGIN + _PEM_SHAPE, "-----BEGIN OPENSSH " + "PRIVATE KEY-----")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_sha(links: list[str]) -> str:
    """Stable fingerprint of the source set visible for the authorization."""
    return _hash(json.dumps(sorted(set(links)), ensure_ascii=False, separators=(",", ":")).encode("utf8"))


def _validate_vault(vault: Path) -> None:
    errors = validate(vault)["errores"]
    if errors:
        raise ValueError("Vault with previous errors; nothing is written: " + "; ".join(errors[:3]))


def _document(vault: Path, doc_id: str) -> tuple[Path, dict, str, bytes]:
    if not DOC_RE.fullmatch(doc_id):
        raise ValueError("Incorrect D/X doc_id")
    found = []
    for path in notes_in_vault(vault):
        meta, body = split_frontmatter(path.read_text(encoding="utf8"))
        if meta.get("tipo") == "documento" and meta.get("doc_id") == doc_id:
            found.append((path, meta, body))
    if len(found) != 1:
        raise ValueError("Exactly one existing document with doc_id " + doc_id + " is required")
    path, meta, body = found[0]
    if path.parent != vault / "10_Conocimiento" or _is_symlinked(path):
        raise ValueError("Document outside the canonical folder or a symbolic link")
    if meta.get("estado_editorial") not in {"borrador", "en_revision"}:
        raise ValueError("Only drafts or documents under review can be updated; approved ones need the later governance flow")
    if not REV_RE.fullmatch(str(meta.get("revision") or "")):
        raise ValueError("Previous revision missing or incompatible; do not improvise a migration")
    return path, meta, body, path.read_bytes()


def _next_revision(previous: str) -> str:
    match = REV_RE.fullmatch(str(previous))
    if not match:
        raise ValueError("Original version not supported")
    major, minor = int(match.group(1)), int(match.group(2))
    if minor >= 99999:
        raise ValueError("Revision limit; requires planned migration")
    return f"{major}.{minor + 1}"


def _check_body(vault: Path, target: Path, previous: str, candidate: str, *, allow_block_removal: bool = False) -> dict:
    if not candidate.lstrip().startswith("# ") or len(candidate.strip()) < 90:
        raise ValueError("The draft must include a title and substantive content")
    if candidate.startswith("---\n"):
        raise ValueError("The candidate body cannot declare YAML; metadata is managed separately")
    if any(s in candidate for s in _PEM_MARKERS):
        raise ValueError("Credential marker detected")
    if candidate == previous:
        raise ValueError("No changes; do not create another revision")
    old_ids = BLOCK_RE.findall(previous)
    new_ids = BLOCK_RE.findall(candidate)
    if len(new_ids) != len(set(new_ids)):
        raise ValueError("Duplicated block ID in the candidate document")
    missing = set(old_ids) - set(new_ids)
    if missing and not allow_block_removal:
        raise ValueError("Removing block IDs without a migration procedure is not allowed: " + ", ".join(sorted(missing)))
    known = set()
    for other in notes_in_vault(vault):
        if other == target:
            continue
        known.update(BLOCK_RE.findall(other.read_text(encoding="utf8")))
    if set(new_ids) & known:
        raise ValueError("Block IDs already used in another document")
    paths, names = target_index(vault, include_assets=True)
    bad = [link for link in wiki_targets(candidate) if resolve_link(link, paths, names) is None]
    if bad:
        raise ValueError("Unresolved wiki link: " + ", ".join(sorted(set(bad))[:4]))
    diff = list(difflib.unified_diff(previous.splitlines(),candidate.splitlines(),
                                    fromfile="current",tofile="proposed",lineterm=""))
    return {"lineas_diferentes":len(diff),
            "resumen_diff":"\n".join(diff[:45])[:6500],
            "bloques_preservados":len(old_ids),
            "bloques_nuevos":len(set(new_ids)-set(old_ids))}


def _context(vault_path: Path, doc_id: str) -> tuple[Path, Path, dict, str, bytes]:
    vault, _ = safe_vault(vault_path)
    _validate_vault(vault)
    path, meta, body, raw = _document(vault,doc_id)
    return vault,path,meta,body,raw


def previsualizar(vault_path: Path, doc_id: str, input_file: Path,
                 *, sources: list[str] | None = None) -> dict:
    """Read only: current document, external draft and localized diff."""
    vault,path,meta,body,raw = _context(vault_path,doc_id)
    candidate,candidate_sha = _read_input(input_file,vault)
    diff = _check_body(vault,path,body,candidate)
    source_ids=sorted(set(sources or []))
    added=local_sources(vault,source_ids)
    current=meta.get("fuentes") or []
    if not isinstance(current,list):
        raise ValueError("The document fuentes property is not a list")
    resulting=sorted(set(current+added))
    return {"doc_id":doc_id,"ruta":str(path),"revision_actual":str(meta["revision"]),
            "revision_propuesta":_next_revision(str(meta["revision"])),
            "sha_original":_hash(raw),"sha_candidato":candidate_sha,
            "fuentes_adicionales":source_ids,"fuentes_resultantes":resulting,
            "sha_fuentes":_source_sha(resulting),
            "estado_editorial":meta["estado_editorial"],**diff,
            "aprobado":False,"operacion":"SOLO_LECTURA"}


def preparar(vault_path: Path, doc_id: str, input_file: Path,
             *, sources: list[str] | None = None) -> dict:
    """Records the proposal and draft without touching the current document."""
    preview=previsualizar(vault_path,doc_id,input_file,sources=sources)
    vault,_=safe_vault(vault_path)
    candidate=input_file.expanduser().resolve().read_bytes()
    if _hash(candidate)!=preview["sha_candidato"]:
        raise ValueError("Draft changed during preparation")
    pid="PRDX-"+uuid4().hex[:12].upper()
    base=vault/PROPOSALS
    private_directory(base)
    directory=base/pid
    directory.mkdir(mode=0o700,exist_ok=False)
    try:
        (directory/"candidato.snapshot").write_bytes(candidate)
        packet={**preview,"propuesta_id":pid,"creada_en":utcnow(),
                "tipo":"propuesta_revision_documental",
                "estado":"pendiente_autorizacion"}
        (directory/"propuesta.json").write_text(json.dumps(packet,ensure_ascii=False,indent=2)+"\n",encoding="utf8", newline='\n')
    except Exception:
        for item in directory.iterdir(): item.unlink()
        directory.rmdir()
        raise
    return {"propuesta_id":pid,"doc_id":doc_id,"ruta_propuesta":str(directory),
            "sha_original":preview["sha_original"],"sha_candidato":preview["sha_candidato"],
            "fuentes_adicionales":preview["fuentes_adicionales"],
            "fuentes_resultantes":preview["fuentes_resultantes"],
            "sha_fuentes":preview["sha_fuentes"],
            "revision_propuesta":preview["revision_propuesta"],
            "estado":"pendiente_autorizacion","documento_modificado":False}


def _proposal(vault: Path, pid: str) -> tuple[dict, bytes]:
    if not ITEM_RE.fullmatch(pid) or not pid.startswith("PRDX-"):
        raise ValueError("Invalid proposal ID")
    directory=vault/PROPOSALS/pid
    if _is_symlinked(directory) or not directory.is_dir():
        raise ValueError("Proposal missing or linked")
    data=json.loads((directory/"propuesta.json").read_text(encoding="utf8"))
    candidate_path=directory/"candidato.snapshot"
    if _is_symlinked(candidate_path):
        raise ValueError("Linked candidate")
    candidate=candidate_path.read_bytes()
    if data.get("propuesta_id")!=pid or _hash(candidate)!=data.get("sha_candidato"):
        raise ValueError("The proposal was altered")
    return data,candidate


def _authorization(responsable: str, referencia: str, esperado: str) -> None:
    if not responsable.strip() or not referencia.strip() or len(referencia)>350:
        raise ValueError("An accountable person and an explicit authorization reference, obtained outside the CLI, are required")
    if not re.fullmatch(r"[0-9a-f]{64}",esperado):
        raise ValueError("An exact SHA-256 is required to confirm the version being authorized")


def _backup_root(vault: Path, backup_dir: Path) -> Path:
    raw=backup_dir.expanduser()
    if not raw.is_absolute() or raw.is_symlink():
        raise ValueError("The backup directory must be absolute and without symbolic links")
    root=raw.resolve()
    if root==vault or vault in root.parents or root==ROOT or ROOT in root.parents:
        raise ValueError("The backup must be outside the vault and outside the master repository")
    return root


def _write_atomic(path: Path, contents: bytes) -> None:
    if os.name == 'nt':
        from .windows_fs import atomic_write
        atomic_write(path.parent, path.name, contents, immutable=False, preserve_acl=True)
        return
    temp=path.with_name("."+path.name+".tmp-"+uuid4().hex[:8])
    try:
        mode=stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
        with os.fdopen(fd,"wb") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp,mode)
        os.replace(temp,path)
    finally:
        if temp.exists(): temp.unlink()


def _publish(vault: Path, path: Path, meta: dict, content: str, *,
             expected_sha: str, responsable: str, referencia: str,
             backup_dir: Path, origen: dict, editorial_status: str = "en_revision",
             reviewed_by: str = "por_validar") -> dict:
    """Local lock + SHA, external/internal copy and restoration on failure."""
    lock_folder=vault/"90_Sistema"/".locks"
    lock_folder.mkdir(parents=True,exist_ok=True)
    lock=lock_folder/(str(meta["doc_id"])+".lock")
    try:
        with lock.open("x",encoding="utf8", newline='\n') as handle:
            handle.write("Operation in progress: "+utcnow()+"\n")
    except FileExistsError as exc:
        raise ValueError("Document locked by another revision; do not delete the lock without checking processes") from exc
    try:
        before=path.read_bytes()
        if _hash(before)!=expected_sha:
            raise ValueError("Document changed since the review; do not overwrite")
        nextrev=_next_revision(str(meta["revision"]))
        entry="REVDX-"+uuid4().hex[:12].upper()
        backroot=_backup_root(vault,backup_dir)
        private_directory(backroot)
        history_root=vault/HISTORY
        private_directory(history_root)
        history=history_root/str(meta["doc_id"])/entry
        history.mkdir(mode=0o700,parents=True,exist_ok=False)
        external=backroot/str(meta["doc_id"])/entry
        external.mkdir(mode=0o700,parents=True,exist_ok=False)
        (history/"anterior.snapshot").write_bytes(before)
        (external/"anterior.snapshot").write_bytes(before)
        if editorial_status not in {"en_revision","aprobado"}:
            raise ValueError("Requested editorial state not allowed")
        if editorial_status=="aprobado" and (not reviewed_by or reviewed_by=="por_validar"):
            raise ValueError("Editorial approval requires an explicit reviewer")
        newmeta=dict(meta)
        newmeta.update({"revision":nextrev,
                        "estado_editorial":editorial_status,
                        "revisado_por":reviewed_by,
                        "revision_registrada_en":utcnow(),
                        "revision_contenido_sha256":_hash(content.encode("utf8")),
                        "ultima_revision_id":entry})
        out=make_note(newmeta,content).encode("utf8")
        packet={"id":entry,"doc_id":meta["doc_id"],
                "revision_previa":meta["revision"],"revision_nueva":nextrev,
                "sha_previo":_hash(before),"sha_nuevo":_hash(out),
                "solicitante_de_cambio":responsable,
                "referencia_autorizacion":referencia,
                "registrado_en":utcnow(),"operacion":origen,
                "estado":"snapshot_creado",
                "nota":"The script records a declaration; it does not verify identity or consent."}
        prepared=json.dumps(packet,ensure_ascii=False,indent=2).encode("utf8")+b"\n"
        for location in (history,external):
            _write_atomic(location/"manifest.json",prepared)
        if _hash(path.read_bytes())!=expected_sha:
            raise ValueError("Document changed while preparing the backup")
        try:
            _write_atomic(path,out)
            errors=validate(vault)["errores"]
            if errors:
                raise ValueError("Posterior validation failed: "+"; ".join(errors[:3]))
            if _hash(path.read_bytes())!=_hash(out):
                raise ValueError("Posterior fingerprint does not match")
            packet["estado"]="aplicado"
            completed=json.dumps(packet,ensure_ascii=False,indent=2).encode("utf8")+b"\n"
            for location in (history,external):
                _write_atomic(location/"manifest.json",completed)
        except Exception:
            _write_atomic(path,before)
            if path.read_bytes()!=before:
                raise RuntimeError("RESTORATION FAILED: manual recovery from the external snapshot required")
            packet["estado"]="restaurado_por_fallo"
            restored=json.dumps(packet,ensure_ascii=False,indent=2).encode("utf8")+b"\n"
            for location in (history,external):
                try:
                    _write_atomic(location/"manifest.json",restored)
                except OSError:
                    pass  # Original backup preserved; review log and manifest.
            raise
        return {"doc_id":meta["doc_id"],"revision":nextrev,
                "ruta":str(path),"historial_id":entry,
                "historial":str(history),"respaldo_externo":str(external),
                "sha_original":_hash(before),"sha_nuevo":_hash(out),
                "estado_editorial":editorial_status,"aprobado":editorial_status=="aprobado",
                "limite":"Does not certify business approval or G1-G7 quality"}
    finally:
        if lock.exists(): lock.unlink()


def aplicar(vault_path: Path, proposal_id: str, *,
           expected_sha: str, candidate_sha: str, source_sha: str | None = None,
           responsable: str, referencia_autorizacion: str,
           backup_dir: Path) -> dict:
    """Applies an EXISTING proposal: never authorizes/declares the content approved."""
    _authorization(responsable,referencia_autorizacion,expected_sha)
    vault,_=safe_vault(vault_path)
    plan,raw_candidate=_proposal(vault,proposal_id)
    if plan.get("estado")!="pendiente_autorizacion":
        raise ValueError("Proposal already processed or not authorizable")
    if plan.get("sha_original")!=expected_sha or plan.get("sha_candidato")!=candidate_sha:
        raise ValueError("Confirmed fingerprint does not match the proposal")
    vault,path,meta,body,current=_context(vault,plan["doc_id"])
    if _hash(current)!=expected_sha:
        raise ValueError("Concurrent change: current document no longer matches")
    additional=plan.get("fuentes_adicionales") or []
    if not isinstance(additional,list) or not all(isinstance(s,str) for s in additional):
        raise ValueError("Invalid proposed sources")
    if additional:
        if not source_sha or source_sha!=plan.get("sha_fuentes"):
            raise ValueError("Confirmed source fingerprint does not match the proposal")
        existing=meta.get("fuentes") or []
        if not isinstance(existing,list):
            raise ValueError("The document fuentes property is not a list")
        resulting=sorted(set(existing+local_sources(vault,additional)))
        if resulting!=plan.get("fuentes_resultantes") or _source_sha(resulting)!=source_sha:
            raise ValueError("Sources changed since preparation; do not apply")
        meta=dict(meta)
        meta["fuentes"]=resulting
    candidate=raw_candidate.decode("utf8")
    _check_body(vault,path,body,candidate)
    result=_publish(vault,path,meta,candidate,expected_sha=expected_sha,
                    responsable=responsable,referencia=referencia_autorizacion,
                    backup_dir=backup_dir,origen={"propuesta_id":proposal_id})
    plan["estado"]="aplicada"
    plan["resultado_historial_id"]=result["historial_id"]
    plan_path=vault/PROPOSALS/proposal_id/"propuesta.json"
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf8", newline='\n')
    return result


def restaurar(vault_path: Path, doc_id: str, history_id: str, *,
             expected_sha: str, responsable: str,
             referencia_autorizacion: str, backup_dir: Path) -> dict:
    """Restoration as a NEW revision (does not destroy history)."""
    _authorization(responsable,referencia_autorizacion,expected_sha)
    vault,path,meta,body,current=_context(vault_path,doc_id)
    if _hash(current)!=expected_sha:
        raise ValueError("Document changed; do not restore a version different from the confirmed one")
    if not ITEM_RE.fullmatch(history_id) or not history_id.startswith("REVDX-"):
        raise ValueError("Invalid history ID")
    source=vault/HISTORY/doc_id/history_id
    if _is_symlinked(source) or not source.is_dir():
        raise ValueError("History missing or linked")
    packet=json.loads((source/"manifest.json").read_text(encoding="utf8"))
    snapshot_file=source/"anterior.snapshot"
    if _is_symlinked(snapshot_file):
        raise ValueError("Linked snapshot")
    original=snapshot_file.read_bytes()
    if packet.get("estado")!="aplicado" or packet.get("doc_id")!=doc_id or _hash(original)!=packet.get("sha_previo"):
        raise ValueError("Snapshot altered or belongs to another document")
    previous_meta,previous_body=split_frontmatter(original.decode("utf8"))
    if previous_meta.get("doc_id")!=doc_id or previous_meta.get("tipo")!="documento":
        raise ValueError("Snapshot is not a compatible D/X document")
    if previous_body==body:
        raise ValueError("Restoration without substantive change")
    _check_body(vault,path,body,previous_body,allow_block_removal=True)
    # Keep the historical attributes of the chosen version, and record a new revision.
    restored_meta=dict(previous_meta)
    restored_meta["revision"]=str(meta["revision"])
    restored_meta["estado_editorial"]="en_revision"
    restored_meta["revisado_por"]="por_validar"
    result=_publish(vault,path,restored_meta,previous_body,expected_sha=expected_sha,
                    responsable=responsable,referencia=referencia_autorizacion,
                    backup_dir=backup_dir,origen={"restauracion_desde":history_id})
    return result
