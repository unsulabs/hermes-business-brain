"""Local typed relations, proposals and declared human ratification.

No inference. Wiki links, text coincidences and AI mentions are not converted
into validated relations automatically.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
from datetime import date
from pathlib import Path
from uuid import uuid4

from .documentos import _is_symlinked
from .lib_ce import split_frontmatter
from .operacion import index_ids, local_sources, safe_vault, utcnow
from .platform_fs import private_directory

RELROOT=Path("90_Sistema")/"Relaciones"
REL_RE=re.compile(r"^REL-[A-F0-9]{12}$")
VER_RE=re.compile(r"^VALREL-[A-F0-9]{12}$")
PREDICATES={
    "sustentado_por","documenta","utiliza","depende_de",
    "deriva_de","implementa","participa_en","refiere_a",
    "informa_decision","componente_de"
}


def _sha(data:bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _private_dir(path:Path) -> None:
    if _is_symlinked(path):
        raise ValueError("Directory with symbolic links not allowed")
    private_directory(path)


def _notes(vault:Path) -> dict:
    notes={}
    for nid,path in index_ids(vault).items():
        fm,_=split_frontmatter(path.read_text(encoding="utf8"))
        notes[nid]=(path,fm)
    return notes


def _read_relations(vault:Path) -> list[tuple[Path,dict]]:
    root=vault/RELROOT
    if not root.exists():
        return []
    if _is_symlinked(root):
        raise ValueError("Relations folder is linked")
    records=[]
    for path in sorted(root.glob("REL-*.json")):
        if _is_symlinked(path):
            raise ValueError("Linked relation: "+path.name)
        content=json.loads(path.read_text(encoding="utf8"))
        if not isinstance(content,dict):
            raise ValueError("Invalid relation JSON")
        records.append((path,content))
    return records


def validate_relations(vault:Path) -> list[str]:
    """Referential validation, NOT semantic truth of the predicates."""
    errors=[]
    notes=_notes(vault)
    seen=set()
    ids=set()
    for path,r in _read_relations(vault):
        rid=r.get("id")
        if (not isinstance(rid,str) or not REL_RE.fullmatch(rid)
                or path.stem!=rid or rid in ids):
            errors.append("Relation with incorrect or duplicated ID: "+path.name)
            continue
        ids.add(rid)
        a,b=r.get("origen_id"),r.get("destino_id")
        if a not in notes or b not in notes or a==b:
            errors.append("Relation "+rid+" refers to missing or identical notes")
        if r.get("predicado") not in PREDICATES:
            errors.append("Unregistered predicate: "+rid)
        if r.get("estado")!="propuesta":
            errors.append("A base relation is always registered as a proposal: "+rid)
        sources=r.get("fuentes")
        if not isinstance(sources,list) or not sources:
            errors.append("Relation without source references: "+rid)
        elif any(fid not in notes or notes[fid][1].get("tipo")!="fuente"
                 for fid in sources):
            errors.append("Relation with non-existent source: "+rid)
        key=(a,b,r.get("predicado"),r.get("ambito"))
        if key in seen:
            errors.append("Relation duplicated by origin/destination/subject: "+rid)
        seen.add(key)
        if not r.get("ambito") or not r.get("motivo"):
            errors.append("Relation without context or explanation: "+rid)
    return errors


def propose(vault_path:Path, source_id:str, target_id:str, predicate:str, *,
            fuentes:list[str], ambito:str, motivo:str) -> dict:
    vault,_=safe_vault(vault_path)
    if predicate not in PREDICATES:
        raise ValueError("Predicate not allowed")
    if not ambito.strip() or len(ambito)>250 or len(motivo.strip())<20 or len(motivo)>1500:
        raise ValueError("Insufficient scope or explanation")
    notes=_notes(vault)
    if source_id==target_id or source_id not in notes or target_id not in notes:
        raise ValueError("Relation endpoints do not exist or are identical")
    if any(notes[x][1].get("sensibilidad")!="interno" for x in (source_id,target_id)):
        raise ValueError("Local relations only for internal notes, without restricted ACL")
    if not fuentes:
        raise ValueError("Every relation requires references to existing sources")
    local_sources(vault,fuentes)
    errors=validate_relations(vault)
    if errors:
        raise ValueError("Previous record invalid: "+"; ".join(errors[:2]))
    for _,r in _read_relations(vault):
        if (r["origen_id"],r["destino_id"],r["predicado"],r["ambito"])==(
                source_id,target_id,predicate,ambito.strip()):
            raise FileExistsError("A relation with the same subject already exists")
    rid="REL-"+uuid4().hex[:12].upper()
    entry={"id":rid,"tipo":"relacion_tipada","origen_id":source_id,
           "destino_id":target_id,"predicado":predicate,
           "ambito":ambito.strip(),"motivo":motivo.strip(),
           "fuentes":sorted(set(fuentes)),"estado":"propuesta",
           "registrado_en":utcnow(),
           "aviso":"Proposed predicate: not equivalent to approved fact or client acceptance"}
    root=vault/RELROOT
    _private_dir(root)
    dest=root/(rid+".json")
    with dest.open("x",encoding="utf8", newline='\n') as handle:
        handle.write(json.dumps(entry,ensure_ascii=False,indent=2)+"\n")
    return {"relacion_id":rid,"ruta":str(dest),"estado":"propuesta","validada":False}


def _validations(vault:Path) -> list[dict]:
    root=vault/RELROOT
    if not root.exists():
        return []
    records=[]
    for path in sorted(root.glob("VALREL-*.json")):
        if _is_symlinked(path):
            raise ValueError("Linked validation")
        r=json.loads(path.read_text(encoding="utf8"))
        if r.get("id")!=path.stem or not VER_RE.fullmatch(path.stem):
            raise ValueError("Invalid relation validation")
        records.append(r)
    return records


def confirm(vault_path:Path, relation_id:str, expected_sha:str, *,
            revisor:str, referencia_autorizacion:str, confirmacion:str) -> dict:
    vault,_=safe_vault(vault_path)
    if not REL_RE.fullmatch(relation_id):
        raise ValueError("Invalid relation ID")
    path=vault/RELROOT/(relation_id+".json")
    if _is_symlinked(path) or not path.is_file():
        raise ValueError("Relation not found")
    payload=path.read_bytes()
    if _sha(payload)!=expected_sha:
        raise ValueError("The relation changed since the review")
    if confirmacion!=f"CONFIRM {relation_id} {expected_sha[:12]}":
        raise ValueError("Missing literal and specific confirmation")
    if not revisor.strip() or len(revisor)>160 or len(referencia_autorizacion.strip())<8:
        raise ValueError("Missing reviewer or reference to the human approval")
    if validate_relations(vault):
        raise ValueError("Invalid relations record; do not confirm")
    if any(x.get("relacion_id")==relation_id for x in _validations(vault)):
        raise ValueError("Relation already confirmed")
    vid="VALREL-"+uuid4().hex[:12].upper()
    record={"id":vid,"tipo":"revision_relacion",
            "relacion_id":relation_id,"sha_relacion":expected_sha,
            "revisor":revisor.strip(),"referencia_autorizacion":referencia_autorizacion.strip(),
            "registrado_en":utcnow(),"estado":"validada_por_revisor",
            "limite":"Registered declaration; does not verify the reviewer's signature or identity"}
    out=vault/RELROOT/(vid+".json")
    with out.open("x",encoding="utf8", newline='\n') as f:
        f.write(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
    return {"relacion_id":relation_id,"revision_id":vid,"estado":"validada_por_revisor",
            "autenticacion_externa":"NO_VERIFICADA"}


def query(vault_path:Path, *, source_id:str|None=None) -> dict:
    vault,_=safe_vault(vault_path)
    errors=validate_relations(vault)
    if errors:
        raise ValueError("Relations record with errors: "+"; ".join(errors[:3]))
    approved={r["relacion_id"]:r for r in _validations(vault)}
    rows=[]
    for path,r in _read_relations(vault):
        if source_id and source_id not in {r["origen_id"],r["destino_id"]}:
            continue
        approval=approved.get(r["id"])
        valid=approval is not None and approval.get("sha_relacion")==_sha(path.read_bytes())
        rows.append({**r,"estado_efectivo":"validada_por_revisor" if valid else "propuesta",
                     "evaluacion_autenticidad":"externa_no_verificada",
                     "revision_relacion_id":approval["id"] if valid else None})
    return {"total":len(rows),"relaciones":rows,
            "limite":"Registry of declared links; does not infer truth, legal authority or sales evidence"}
