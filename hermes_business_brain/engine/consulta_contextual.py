"""Literal retrieval of existing documents and business units.

No LLM, no embeddings, no automatic synthesis and no semantic certification.
A result is a candidate for the agent's review together with its original
sources.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from .lib_ce import BLOCK_RE, notes_in_vault, split_frontmatter
from .operacion import authority_lookup, safe_vault

BLOCK_SPLIT=re.compile(r"<!--\s*kb:id=([^\s]+)\s*-->")
DATE_RE=re.compile(r"^\d{4}-\d{2}-\d{2}$")
STOPWORDS={
    "a", "al", "con", "como", "cual", "cuales", "cuando", "de", "del",
    "donde", "durante", "el", "ella", "en", "es", "esta", "este", "hay",
    "la", "las", "lo", "los", "mi", "nos", "o", "para", "por", "que",
    "quien", "quienes", "se", "ser", "si", "su", "sus", "un", "una", "y",
}


def _model_file(name: str) -> Path:
    """Model data in the engine layout: engine/data/modelo or package data."""
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


def _eligible_types() -> set[str]:
    data = json.loads(_model_file("tipos_entidad.json").read_text(encoding='utf-8'))
    return {r['tipo'] for r in data['tipos']} | {'documento'}

REJECTED_STATES = {'rechazado', 'legado_rechazado', 'retirado', 'rejected'}


def _terms(value: str) -> set[str]:
    normalized=unicodedata.normalize("NFKD",value.casefold())
    normalized="".join(c for c in normalized if not unicodedata.combining(c))
    return {t for t in re.findall(r"\w+",normalized)
            if len(t)>2 and t not in STOPWORDS and not t.isdigit()}


def _key(term: str) -> str:
    # Conservative prefix: orients inflected words; does not assert synonymy.
    return term[:5] if len(term)>=6 else term


def _date(val):
    if val in (None,""):
        return None
    if isinstance(val,date):
        return val
    if not isinstance(val,str) or not DATE_RE.fullmatch(val):
        raise ValueError("Knowledge date is not valid")
    return date.fromisoformat(val)


def _blocks(body:str, doc_id:str) -> list[dict]:
    control=re.search(r"(?m)^## CONTROL(?:[ \t]|$)",body)
    cap=control.start() if control else len(body)
    matches=[m for m in BLOCK_SPLIT.finditer(body) if m.start()<cap]
    output=[]
    for i,match in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else cap
        content=body[match.end():end].strip()
        if content:
            output.append({"id":match.group(1),"doc_id":doc_id,
                           "texto":content})
    return output


def _entity_sections(body:str, entity_id:str) -> list[dict]:
    """Fragments of a unit without marking CONTROL as business knowledge."""
    control=re.search(r"(?mi)^#{1,6}\s+CONTROL(?:\s|\b)",body)
    content=body[:control.start()] if control else body
    heads=list(re.finditer(r"(?m)^#{1,6}\s+[^\n]+$",content))
    if not heads:
        return [{"id":f"{entity_id}#texto", "doc_id":entity_id,
                 "texto":content.strip()}] if content.strip() else []
    sections=[]
    for i,head in enumerate(heads):
        end=heads[i+1].start() if i+1<len(heads) else len(content)
        text=content[head.start():end].strip()
        if text:
            sections.append({"id":f"{entity_id}#seccion-{i+1}",
                             "doc_id":entity_id,"texto":text})
    return sections


def consulta(vault_path:Path, literal:str, *, tema:str|None=None,
             ambito:str|None=None, fecha:str|None=None, max_results:int=10,
             orientar:bool=False) -> dict:
    vault,cfg=safe_vault(vault_path)
    eligible_types=_eligible_types()
    term=literal.strip()
    if not 2<=len(term)<=220:
        raise ValueError("Literal query must be between 2 and 220 characters")
    if (tema is None)!=(ambito is None):
        raise ValueError("Topic and scope must be specified together")
    if (tema is not None and (not tema.strip() or not ambito.strip())):
        raise ValueError("Topic and scope without content")
    if not 1<=max_results<=40:
        raise ValueError("Result limit must be between 1 and 40")
    query_terms=_terms(term) if orientar else set()
    if orientar and not query_terms:
        raise ValueError("The query has no useful terms to orient the search")
    target=date.fromisoformat(fecha) if fecha else date.today()
    candidates=[]
    excluded=0
    notes=[]
    rejected=set()
    for path in notes_in_vault(vault):
        raw=path.read_bytes()
        front,body=split_frontmatter(raw.decode('utf8'))
        aliases={str(front.get('id','')),str(front.get('doc_id','')),path.stem,
                 path.relative_to(vault).with_suffix('').as_posix()}
        notes.append((path,raw,front,body,aliases))
        if front.get('estado_editorial') in REJECTED_STATES:
            rejected.update(aliases- {''})
    # Refuse downstream reuse of explicitly rejected sources (including links).
    changed=True
    while changed:
        changed=False
        for path,raw,front,body,aliases in notes:
            refs=front.get('fuentes') or []
            refs=[refs] if isinstance(refs,str) else refs
            refs={str(r).removeprefix('[[').removesuffix(']]').split('|')[0].split('#')[0] for r in refs}
            if refs & rejected and not (aliases-{''}) <= rejected:
                rejected.update(aliases-{''})
                changed=True
    for path,raw,front,body,aliases in notes:
        note_type=front.get("tipo")
        if (note_type not in eligible_types or front.get("sensibilidad")!="interno"
            or front.get('empresa_id',cfg['company_id'])!=cfg['company_id']
            or (note_type=='fuente' and front.get('lectura','no_verificada')=='no_verificada')
            or front.get('estado_editorial') in REJECTED_STATES
            or bool((aliases-{''}) & rejected)
            or any(p in {'_plantillas','Plantillas','90_Sistema','legado_rechazado'} for p in path.relative_to(vault).parts)):
            continue
        doc_id=front.get("doc_id") if note_type=="documento" else front.get("id")
        if not doc_id:
            continue
        start,end=_date(front.get("valid_from")),_date(front.get("valid_to"))
        if (start and target<start) or (end and target>end):
            excluded+=1
            continue
        if note_type=="documento":
            blocks=_blocks(body,str(doc_id))
            # D/X created with `documento` may be partial and not yet have
            # kb:id markers. Orient by section without inventing a contractual
            # block ID or modifying the note.
            derived_sections=not blocks
            if derived_sections:
                blocks=_entity_sections(body,str(doc_id))
        else:
            blocks=_entity_sections(body,str(doc_id))
            derived_sections=False
        for block in blocks:
            if orientar:
                block_keys={_key(t) for t in _terms(block["texto"]+" "+path.stem)}
                matched=sorted(t for t in query_terms if _key(t) in block_keys)
                if not matched:
                    continue
            else:
                if term.casefold() not in block["texto"].casefold():
                    continue
            txt=block["texto"]
            span_start=raw.find(txt.encode('utf8'))
            excerpt=txt[:900] + ("…" if len(txt)>900 else "")
            row={
                "doc_id":str(doc_id),"bloque_id":block["id"],
                "tipo_fragmento":("seccion_derivada_sin_id_estable" if derived_sections
                                  else "bloque_con_id" if note_type=="documento"
                                  else "seccion_de_entidad"),
                "tipo_nota":note_type,
                "ruta":str(path.relative_to(vault)),
                "sha256_nota":hashlib.sha256(raw).hexdigest(),
                "span_bytes_nota":[span_start,span_start+len(txt.encode('utf8'))] if span_start>=0 else None,
                "extracto_literal":excerpt,
                "estado_editorial":front.get("estado_editorial","sin_estado"),
                "cobertura":front.get("cobertura","sin_registrar"),
                "vigencia_declarada":front.get("vigencia","sin_verificar"),
                "fuentes_nivel_documento":front.get("fuentes") or [],
                "fuente_demuestra_bloque":"NO_COMPROBADO",
                "as_of_consultado":target.isoformat(),
                "fecha_corte_documento":front.get("fecha_corte"),
                "advertencia":("Derived section without a contractual block ID; open the note and the original source. "
                               "Do not cite this locator as a stable identity."
                               if derived_sections else
                               "Term match; it may be irrelevant. Open the note and the original source"
                               if orientar else
                               "Literal mention; not equivalent to authority, sale, result or block truth"),
            }
            if orientar:
                row["terminos_coincidentes"]=matched
                row["puntaje_lexico"]=len(matched)
            candidates.append(row)
    for path,raw,front,body,aliases in notes:
        if path.read_bytes()!=raw:
            raise ValueError('The note changed during the query')
    if orientar:
        candidates.sort(key=lambda row:(-row["puntaje_lexico"],row["ruta"],row["bloque_id"]))
    authority = None
    if tema is not None and ambito is not None:
        authority=authority_lookup(vault,tema,ambito,as_of=target.isoformat())
    return {
        "empresa_id":cfg["company_id"],"consulta_literal":term,
        "fecha_consultada":target.isoformat(),
        "modo":("orientacion_lexica_de_bloques" if orientar else
                "busqueda_literal_de_bloques_con_contexto"),
        "total_coincidencias":len(candidates),
        "candidatos":candidates[:max_results],
        "documentos_fuera_vigencia_explicita":excluded,
        "autoridad_contextual":authority,
        "respuesta_semantica_generada":False,
        "limite":("Word match without semantic understanding or proof of relevance. Review the full note, the original source, scope, authority and counter-evidence before answering."
                  if orientar else
                  "Literal candidates. Review the original source, scope, authority, permissions and counter-evidence with Codex before answering the user."),
    }
