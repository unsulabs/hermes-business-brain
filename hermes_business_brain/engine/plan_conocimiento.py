"""Knowledge architecture audit before drafting or creating notes.

Does not extract meaning by itself: Codex classifies units from authorized
originals and this tool reviews IDENTITIES, coverage, sources and links.
Does not modify vaults or company files, does not create notes and does not
approve content.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .documentos import _is_symlinked
from .lib_ce import split_frontmatter
from .operacion import index_ids, load_registry, safe_vault
from .relaciones import PREDICATES

# Repository root (upstream operacion.ROOT analog).
ROOT = Path(__file__).resolve().parent.parent.parent

KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{2,55}$")
TAG_RE = re.compile(r"^[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*){0,2}$")
SOURCE_RE = re.compile(r"^F-[A-Za-z0-9_-]{2,60}$")
DOC_RE = re.compile(r"^(?:D0[1-7]|X0[1-7])$")
ACTIONS = {"crear", "revisar", "referenciar", "no_crear"}


def _text(value: object, name: str, minimum: int=12, maximum: int=1200) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f"{name} must contain a concrete explanation of {minimum} to {maximum} characters")
    return value.strip()


def _read_plan(plan_path: Path, vault: Path) -> dict:
    if _is_symlinked(plan_path):
        raise ValueError("External plan with symbolic link; not read")
    source = plan_path.expanduser().resolve()
    if source == vault or vault in source.parents or source == ROOT or ROOT in source.parents:
        raise ValueError("The plan is prepared outside the private vault and outside Git")
    if not source.is_file() or source.stat().st_size > 90000:
        raise ValueError("Plan missing or larger than 90 kB")
    raw = source.read_bytes()
    if b"PRIVATE KEY" in raw or b"BEGIN OPENSSH" in raw:
        raise ValueError("Possible private key in the plan")
    doc = json.loads(raw.decode("utf8"))
    if not isinstance(doc, dict):
        raise ValueError("The plan must be a JSON object")
    return doc


def _items(obj: dict, name: str, limit: int=30) -> list:
    val = obj.get(name)
    if not isinstance(val, list) or not 1 <= len(val) <= limit:
        raise ValueError(f"{name} requires between 1 and {limit} items")
    return val


def _sources(val: object, label: str) -> list[str]:
    if not isinstance(val, list) or not val or any(not isinstance(s, str) or not SOURCE_RE.fullmatch(s) for s in val):
        raise ValueError(f"{label}: indicate at least one source ID F-...")
    if len(set(val)) != len(val):
        raise ValueError(f"{label}: duplicated source")
    return val


def _tags(val: object, label: str) -> list[str]:
    if not isinstance(val, list) or not 1 <= len(val) <= 5:
        raise ValueError(f"{label}: use between 1 and 5 thematic tags")
    if len(set(val)) != len(val) or any(not isinstance(t, str) or not TAG_RE.fullmatch(t) for t in val):
        raise ValueError(f"{label}: tags must be unique, brief and without personal data")
    return val


def planificar(vault_path: Path, plan_path: Path) -> dict:
    """Audit of a plan previously REASONED by Codex. Strictly read-only."""
    vault, cfg = safe_vault(vault_path)
    plan = _read_plan(plan_path, vault)
    purpose = _text(plan.get("pregunta"), "business question", 15, 650)
    subjects = _items(plan, "asuntos")
    units = _items(plan, "unidades")
    registered = index_ids(vault)
    note_meta = {}
    note_titles = {}
    classes = {}
    for registered_id, note_path in registered.items():
        fm, body = split_frontmatter(note_path.read_text(encoding="utf8"))
        note_meta[registered_id] = fm
        title_match = re.search(r"(?m)^# (.+)$", body)
        note_titles[registered_id] = title_match.group(1).strip() if title_match else note_path.stem
        if fm.get("tipo") == "documento":
            classes.setdefault(str(fm.get("clase") or ""), set()).add(registered_id)
    registry = load_registry()
    subject_ids, unit_ids = set(), set()
    source_pending = set()
    warnings = []
    recommendations = []
    potential_duplicates = []
    mapped_subjects = Counter()
    declared_sources = set()

    def normalize_title(value: str) -> str:
        value = unicodedata.normalize("NFKD",value).casefold()
        value = "".join(c for c in value if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", " ", value).strip()

    for s in subjects:
        if not isinstance(s, dict):
            raise ValueError("Each subject must be an object")
        key = s.get("clave")
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in subject_ids:
            raise ValueError("Subject with repeated or invalid key")
        subject_ids.add(key)
        _text(s.get("criterio"), "Criteria of subject "+key, 25, 1300)
        ids = _sources(s.get("fuentes"), "subject "+key)
        declared_sources.update(ids)
        _text(s.get("por_que_importa"), "Importance of "+key, 20, 950)

    summaries = []
    for unit in units:
        if not isinstance(unit, dict):
            raise ValueError("Each proposed unit must be an object")
        key, action = unit.get("clave"), unit.get("accion")
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in unit_ids:
            raise ValueError("Unit without stable or repeated key")
        unit_ids.add(key)
        if action not in ACTIONS:
            raise ValueError(f"{key}: unrecognized action: {action}")
        title = _text(unit.get("titulo"), f"{key}.titulo", 5, 180)
        reason = _text(unit.get("razon_identidad"), f"{key}.razon_identidad", 35, 1400)
        assigned = unit.get("asuntos")
        if not isinstance(assigned, list) or not assigned or len(assigned) != len(set(assigned)):
            raise ValueError(f"{key}: each unit has to take on unique subjects")
        for a in assigned:
            if a not in subject_ids:
                raise ValueError(f"{key}: undeclared subject: {a}")
            mapped_subjects[a] += 1
        uid = unit.get("id_existente")
        typ = unit.get("tipo")
        path = None
        if action == "no_crear":
            if uid is not None:
                raise ValueError(f"{key}: no_crear does not accept an existing ID")
            if typ not in (None, "no_aplica"):
                raise ValueError(f"{key}: no_crear must not create an entity type")
            tags = []
        else:
            tags = _tags(unit.get("etiquetas"),key)
            if typ != "documento" and typ not in registry:
                raise ValueError(f"{key}: use documento or one of the real model types")
            if typ == "fuente":
                raise ValueError(f"{key}: the source is registered by provenance, not as an idea card")
            doc_class = unit.get("clase")
            if typ == "documento" and (not isinstance(doc_class,str) or not DOC_RE.fullmatch(doc_class)):
                raise ValueError(f"{key}: document class must be D01-D07 / X01-X07; the X01-... ID is a file id, not a class")
            if action in ("revisar","referenciar"):
                if not isinstance(uid,str) or uid not in registered:
                    raise ValueError(f"{key}: existing ID not found; recover the note before inventing another one")
                original_path = registered[uid]
                meta, _ = split_frontmatter(original_path.read_text(encoding="utf8"))
                if meta.get("tipo") != typ:
                    raise ValueError(f"{key}: existing type does not match the plan")
                if typ == "documento" and meta.get("clase") != doc_class:
                    raise ValueError(f"{key}: document class differs from the existing note")
                if meta.get("sensibilidad") not in (None, "interno"):
                    raise ValueError(f"{key}: access above interno; do not design an operation without ACL")
                path = str(original_path.relative_to(vault))
            elif action == "crear":
                if uid is not None:
                    raise ValueError(f"{key}: crear does not accept an existing ID; use revisar/referenciar")
                if typ == "documento" and doc_class.startswith("D") and classes.get(doc_class):
                    ids = ", ".join(sorted(classes[doc_class]))
                    raise ValueError(f"{key}: {doc_class} already exists (ID {ids}); link and review, do not duplicate")
                if typ != "documento":
                    normalized = normalize_title(title)
                    matches = sorted(nid for nid, existing in note_titles.items()
                        if note_meta[nid].get("tipo") == typ
                        and normalize_title(existing) == normalized)
                    if matches:
                        potential_duplicates.append({"unidad":key,"tipo":typ,
                                                     "titulo":title,"ids_existentes":matches})
                        warnings.append("POSIBLE_DUPLICADO_ENTIDAD: "+key+" -> "+", ".join(matches))
                path = ("10_Conocimiento/" if typ == "documento" else registry[typ]["carpeta"]+"/") + "(ID pendiente)"
        summaries.append({
            "clave":key,"titulo":title,"accion":action,"tipo":typ,
            "id_existente":uid,"ruta_destino":path,"asuntos":assigned,
            "etiquetas":tags,"razon_identidad":reason,
        })

    missed = subject_ids - set(mapped_subjects)
    duplicated = {k:n for k,n in mapped_subjects.items() if n > 1}
    if missed:
        raise ValueError("Subjects without destination: "+", ".join(sorted(missed)))
    if duplicated:
        raise ValueError("Subjects with two canonical owners (duplication): "+str(duplicated))

    rels = plan.get("relaciones")
    if not isinstance(rels, list):
        raise ValueError("relaciones must be a list (even when empty)")
    checked_rels, pairs = [], set()
    for r in rels:
        if not isinstance(r, dict):
            raise ValueError("Invalid relation")
        a,b,verb=r.get("origen"),r.get("destino"),r.get("predicado")
        if a not in unit_ids or b not in unit_ids or a==b:
            raise ValueError("Relation with non-existent or identical endpoints")
        actions_by_key = {x["clave"]:x["accion"] for x in summaries}
        if "no_crear" in (actions_by_key[a], actions_by_key[b]):
            raise ValueError("Cannot link a unit that will have no note; link the source or an existing one")
        if verb not in PREDICATES:
            raise ValueError("Use a typed model predicate, not a generic relation")
        if (a,b,verb) in pairs:
            raise ValueError("Repeated relation")
        pairs.add((a,b,verb))
        why = _text(r.get("fundamento"),"relation "+a+" -> "+b,20,1300)
        scope = _text(r.get("ambito"),"relation scope",6,250)
        checked_rels.append({"origen":a,"destino":b,"predicado":verb,
                             "ambito":scope,"fundamento":why,
                             "estado":"propuesta_no_verificada"})
    for sid in declared_sources:
        p = registered.get(sid)
        if p is None:
            source_pending.add(sid)
        else:
            fm,_=split_frontmatter(p.read_text(encoding="utf8"))
            if fm.get("tipo")!="fuente":
                raise ValueError("F- ID used for something other than a source: "+sid)
            if fm.get("sensibilidad")!="interno":
                warnings.append("Source with access not suitable for the MVP: "+sid)

    active=[u["clave"] for u in summaries if u["accion"] in ("crear","revisar")]
    if len(active)>1 and not checked_rels:
        explanation = plan.get("justificacion_sin_relaciones")
        if not isinstance(explanation,str) or len(explanation.strip())<50:
            warnings.append("VARIAS_UNIDADES_SIN_VINCULOS: propose relations or justify why they are independent")
        else:
            recommendations.append("Units without links because their independence was justified")
    if len(active)==1:
        sole_active=next(u for u in summaries if u["clave"]==active[0])
        if sole_active["tipo"]=="documento" and len(sole_active["asuntos"])>=3:
            warnings.append("POSIBLE_MONOLITO_DX: several subjects developed only in one D/X; check autonomous identities")
    if source_pending:
        warnings.append("FUENTES_PENDIENTES: register or link authorized originals: "+", ".join(sorted(source_pending)))
    if not any(u["accion"]=="no_crear" for u in summaries):
        recommendations.append("There are no no_crear items; review whether there were incidental mentions, without being forced to invent them")
    return {
        "empresa_id":cfg["company_id"],"pregunta":purpose,
        "asuntos_detectados":len(subjects),"unidades_propuestas":summaries,
        "relaciones_candidatas":checked_rels,"fuentes_pendientes":sorted(source_pending),
        "advertencias":warnings,"recomendaciones":recommendations,
        "posibles_duplicados":potential_duplicates,"plan_consistente":not warnings,
        "documentos_modificados":False,"modo":"SOLO_LECTURA",
        "limite":"Formal consistency does not guarantee judgment, value or fidelity; the owner reviews and authorizes every write.",
        "siguiente_paso":"Show the map to the owner first; then draft or propose per-note changes with their authorization.",
    }
