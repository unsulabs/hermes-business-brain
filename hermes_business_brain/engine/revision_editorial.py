"""Traceable human evaluation of D/X documents, without automatic semantic assessment.

Evaluation records are declared evidence (NOT signature or identity control).
An editorial promotion requires a specific act and versioned backup. It never
implies commercial, legal, financial validity nor sufficiency for another
task.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from uuid import uuid4

from .documentos import _is_symlinked
from .lib_ce import BLOCK_RE
from .operacion import safe_vault, utcnow
from .platform_fs import private_directory
from .revisiones_dx import (
    _authorization,
    _backup_root,
    _context,
    _hash,
    _publish,
)

# Repository root (upstream operacion.ROOT analog).
ROOT = Path(__file__).resolve().parent.parent.parent

GATES={f"G{i}" for i in range(1,8)}
DECISIONS={"requiere_cambios","recomendar_parcial","recomendar_integral"}
STATES={"cumple","no_cumple","no_aplica"}
ID_RE=re.compile(r"^EVALDX-[A-F0-9]{12}$")
ALLOWED_PREFIX="90_Sistema/Evaluaciones_DX"


def _read_act(path: Path, vault: Path) -> tuple[dict, str]:
    raw=path.expanduser()
    if _is_symlinked(raw):
        raise ValueError("Linked evaluation record; not accepted")
    source=raw.resolve()
    if source==vault or vault in source.parents:
        raise ValueError("Evaluation record must be prepared outside the vault")
    if source==ROOT or ROOT in source.parents:
        raise ValueError("Private business evaluation records are not accepted in Git")
    if not source.is_file() or source.stat().st_size>24000:
        raise ValueError("Evaluation record missing or excessive")
    payload=source.read_bytes()
    if b"PRIVATE KEY" in payload or b"BEGIN OPENSSH" in payload:
        raise ValueError("Possible credential in evaluation record")
    obj=json.loads(payload.decode("utf8"))
    if not isinstance(obj,dict):
        raise ValueError("Evaluation JSON must be an object")
    return obj,_hash(payload)


def _validate_act(act:dict, doc_id:str, doc_sha:str, body:str, coverage:str) -> dict:
    if act.get("doc_id")!=doc_id or act.get("sha_documento")!=doc_sha:
        raise ValueError("The evaluation record does not match this document and fingerprint")
    decision=act.get("decision")
    if decision not in DECISIONS:
        raise ValueError("Invalid evaluation decision")
    reviewer=act.get("revisor")
    ref=act.get("referencia_decision")
    if not isinstance(reviewer,str) or len(reviewer.strip())<3 or len(reviewer)>160:
        raise ValueError("Evaluation record without an identified reviewer")
    if not isinstance(ref,str) or len(ref.strip())<8 or len(ref)>350:
        raise ValueError("Evaluation record without a decision reference verifiable by the operator")
    if "revision" in act and not isinstance(act["revision"],str):
        raise ValueError("Invalid revision")
    blocks=set(BLOCK_RE.findall(body))
    scope=act.get("alcance_bloques")
    if not isinstance(scope,list) or not scope or any(not isinstance(x,str) for x in scope):
        raise ValueError("Explicit scope by block ID is required")
    if len(set(scope))!=len(scope) or not set(scope).issubset(blocks):
        raise ValueError("Scope duplicated or includes blocks that do not exist")
    gates=act.get("gates")
    if not isinstance(gates,dict) or set(gates)!=GATES:
        raise ValueError("The evaluation must include exactly G1-G7")
    failures=[]
    for gid,check in gates.items():
        if not isinstance(check,dict) or check.get("estado") not in STATES:
            raise ValueError("Invalid state in "+gid)
        why=check.get("fundamento")
        if not isinstance(why,str) or len(why.strip())<12 or len(why)>1500:
            raise ValueError("Missing specific rationale in "+gid)
        if check["estado"]=="no_cumple":
            failures.append(gid)
        if gid in {"G2","G6"} and check["estado"]=="no_aplica":
            failures.append(gid)
    if decision.startswith("recomendar") and failures:
        raise ValueError("Cannot recommend approval with critical gates unmet: "+", ".join(sorted(failures)))
    if decision=="recomendar_integral":
        if scope!=list(dict.fromkeys(BLOCK_RE.findall(body))):
            raise ValueError("Integral approval requires ALL blocks in order")
        if coverage!="suficiente_para_tarea":
            raise ValueError("Do not recommend integral approval while coverage remains partial")
    return {"decision":decision,"revisor":reviewer.strip(),
            "referencia_decision":ref.strip(),"alcance_bloques":scope,
            "gates":gates,"fallos":sorted(failures)}


def registrar_evaluacion(vault_path:Path, doc_id:str, act_path:Path, *,
                         expected_sha:str) -> dict:
    """Registers an evaluation, without modifying the reviewed document."""
    vault,doc,meta,body,raw=_context(vault_path,doc_id)
    if expected_sha!=_hash(raw):
        raise ValueError("Document changed; redo the evaluation")
    act,act_sha=_read_act(act_path,vault)
    checked=_validate_act(act,doc_id,expected_sha,body,str(meta.get("cobertura","parcial")))
    root=vault/ALLOWED_PREFIX
    private_directory(root)
    folder=root/doc_id
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    eid="EVALDX-"+uuid4().hex[:12].upper()
    record={"id":eid,"tipo":"evaluacion_editorial",
            "doc_id":doc_id,"revision":str(meta["revision"]),
            "sha_documento":expected_sha,
            "fecha_registro":utcnow(),"acta_sha256":act_sha,
            "fuentes_documento":meta.get("fuentes") or [], **checked,
            "documento_modificado":False,
            "limite":"Registered human declaration, not authenticated identity nor autonomous G1-G7 verification"}
    target=folder/(eid+".json")
    with target.open("x",encoding="utf8", newline='\n') as f:
        f.write(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
    return {"evaluacion_id":eid,"ruta":str(target),"doc_id":doc_id,
            "decision":checked["decision"],"documento_modificado":False}


def _load_eval(vault:Path, evaluation_id:str) -> dict:
    if not ID_RE.fullmatch(evaluation_id):
        raise ValueError("Invalid evaluation ID")
    root=vault/ALLOWED_PREFIX
    found=list(root.glob("*/"+evaluation_id+".json"))
    if len(found)!=1 or _is_symlinked(found[0]):
        raise ValueError("Evaluation missing or ambiguous")
    record=json.loads(found[0].read_text(encoding="utf8"))
    if record.get("id")!=evaluation_id or record.get("doc_id")!=found[0].parent.name:
        raise ValueError("Malformed evaluation")
    return record


def aprobar_documento(vault_path:Path,evaluation_id:str,*,expected_sha:str,
                       responsable:str,referencia_autorizacion:str,
                       backup_dir:Path,confirmacion:str) -> dict:
    """Integral EDITORIAL promotion, only for a covered and reviewed document.

    This operation does not prove human identity or temporal validity. The
    agent must obtain the owner's authorization before invoking the CLI.
    """
    _authorization(responsable,referencia_autorizacion,expected_sha)
    vault,_=safe_vault(vault_path)
    record=_load_eval(vault,evaluation_id)
    doc_id=record["doc_id"]
    if confirmacion!=f"APPROVE {doc_id} {expected_sha[:12]}":
        raise ValueError("Missing exact and specific confirmation of the document")
    if record["decision"]!="recomendar_integral" or record.get("sha_documento")!=expected_sha:
        raise ValueError("No integral recommendation exists for this fingerprint")
    vault,path,meta,body,raw=_context(vault,doc_id)
    if _hash(raw)!=expected_sha or str(meta.get("revision"))!=record.get("revision"):
        raise ValueError("The evaluation does not match the current revision")
    if str(meta.get("cobertura"))!="suficiente_para_tarea":
        raise ValueError("Partial coverage; the editorial review must continue by blocks")
    checked=_validate_act(record,doc_id,expected_sha,body,str(meta.get("cobertura")))
    if checked["decision"]!="recomendar_integral":
        raise ValueError("Gates do not allow promotion")
    if not meta.get("fuentes"):
        raise ValueError("A document without references cannot be promoted automatically")
    _backup_root(vault,backup_dir)
    # The body is not altered: only the editorial state and the versioned revision.
    result=_publish(vault,path,meta,body,expected_sha=expected_sha,
                    responsable=responsable,referencia=referencia_autorizacion,
                    backup_dir=backup_dir,
                    origen={"evaluacion_id":evaluation_id,"tipo":"promocion_editorial_integral"},
                    editorial_status="aprobado",reviewed_by=checked["revisor"])
    result["aprobacion_editorial"]=True
    result["aprobacion_semantica_automatica"]=False
    result["aprobacion_evaluacion_id"]=evaluation_id
    result["advertencia"]="Does not equal contractual, legal, commercial or financial validity"
    return result
