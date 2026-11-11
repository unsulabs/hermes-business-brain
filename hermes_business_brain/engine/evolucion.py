"""Read-only evolution scan for a business vault (native engine, v2).

Evaluates the promotion rules in ``data/modelo/reglas_evolucion.json`` against
what the vault actually holds (captured sources, D/X documents, entity cards,
CONTROL notes) and returns a structured plan of evolution *candidates* and
*due revisits*. The scan writes nothing: candidates are proposals for the owner
to confirm, and promotions are applied later through the existing proposal and
apply machinery. Heuristics are conservative: thin evidence is reported as
``partial``, a candidate is never invented, and every candidate cites the files
that already exist in the vault.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_RULES_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "modelo" / "reglas_evolucion.json"
)

_EVENT_MARKERS = ("event", "wedding", "ceremony", "boda", "ceremonia", "evento")
_PRICE_MARKERS = ("$", "mxn", "precio", "cotizac", "quote", "invoice", "total", "inversion")
_COST_MARKERS = ("gasto", "cost", "compr", "nomina", "payroll", "staff")
_PAID_MARKERS = ("cobr", "pago", "paid", "saldo", "balance", "deposito", "anticipo")
_DECISION_MARKERS = ("decid", "acuerdo", "acord", "pactad", "contrato", "decided", "agreement")
_CRITERION_MARKERS = ("criterio", "criterion", "k1", "signal")
_TIMING_MARKERS = ("semana", "week", "antes", "pedir", "orden", "order", "compra", "pre-", "supplier", "proveedor")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _load_rules() -> tuple[list[dict], dict]:
    """Load the promotion rules and cadence file; [] and {} when unavailable."""
    try:
        data = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], {}
    return data.get("rules", []), data.get("cadence", {})


def _scan_sources(vault: Path) -> dict[str, str]:
    """Path -> text for every capture-like note under 90_Sistema/Descubrimiento."""
    notes: dict[str, str] = {}
    folder = vault / "90_Sistema" / "Descubrimiento"
    if folder.is_dir():
        for path in sorted(folder.glob("*.md")):
            notes[str(path)] = _read_text(path)[:5000]
    return notes


def _scan_docs(vault: Path) -> list[str]:
    """Paths of D/X documents under 10_Conocimiento (may be empty)."""
    folder = vault / "10_Conocimiento"
    if not folder.is_dir():
        return []
    return [str(path) for path in sorted(folder.glob("*.md"))]


def _scan_entities(vault: Path) -> list[str]:
    """Paths of entity cards under 20_Entidades (may not exist yet)."""
    folder = vault / "20_Entidades"
    if not folder.is_dir():
        return []
    return [str(path) for path in sorted(folder.glob("*.md"))]


def _control_text(vault: Path) -> str:
    """Best-effort text of the first CONTROL-like note under 90_Sistema."""
    folder = vault / "90_Sistema"
    if not folder.is_dir():
        return ""
    for path in sorted(folder.glob("*.md")):
        if "control" in path.name.lower():
            return _read_text(path)
    return ""


def _count_contains(texts: dict[str, str], markers: tuple[str, ...]) -> list[str]:
    """Paths whose lowercase text contains any of *markers*."""
    hits: list[str] = []
    for path, text in texts.items():
        lowered = text.lower()
        if any(marker in lowered for marker in markers):
            hits.append(path)
    return hits


def _candidate(regla: dict, paths: list[str], required: int) -> dict:
    """Build a candidate dict for one rule given the evidence paths."""
    ready = len(paths) >= required
    return {
        "rule_id": regla.get("id", ""),
        "name": regla.get("name", ""),
        "proposed_action": regla.get("proposed_action", ""),
        "evidence": paths[:5],
        "status": "ready" if ready else "partial",
        "why_not": (
            ""
            if ready
            else f"only {len(paths)} of {required} required distinct sources were found"
        ),
    }


def _evaluate(sources: dict[str, str], rules: list[dict]) -> list[dict]:
    """Evaluate every promotion rule; a rule with zero evidence produces nothing."""
    candidates: list[dict] = []
    for regla in rules:
        rid = regla.get("id", "")
        if rid == "R01":
            paths = _count_contains(sources, _CRITERION_MARKERS + _EVENT_MARKERS)
            if paths:
                candidates.append(_candidate(regla, paths, 2))
        elif rid == "R02":
            paths = _count_contains(sources, _PRICE_MARKERS)
            if paths:
                candidates.append(_candidate(regla, paths, 2))
        elif rid == "R03":
            decision_hits = _count_contains(sources, _DECISION_MARKERS)
            dated = [p for p in decision_hits if _has_year(sources[p])]
            if dated:
                candidates.append(_candidate(regla, dated, 1))
            elif decision_hits:
                candidates.append(_candidate(regla, decision_hits, 1))
        elif rid == "R04":
            price = set(_count_contains(sources, _PRICE_MARKERS))
            costs = set(_count_contains(sources, _COST_MARKERS))
            paid = set(_count_contains(sources, _PAID_MARKERS))
            paths = sorted(price & costs & paid)
            partial = sorted((price & (costs | paid)) | (costs & paid))
            if paths:
                candidates.append(_candidate(regla, paths, 1))
            elif partial:
                candidates.append(_candidate(regla, partial, 2))
        elif rid == "R05":
            paths = _count_contains(sources, _EVENT_MARKERS)
            if paths:
                candidates.append(_candidate(regla, paths, 3))
        elif rid == "R06":
            paths = _count_contains(sources, _TIMING_MARKERS)
            if paths:
                candidates.append(_candidate(regla, paths, 2))
    return candidates


def _has_year(text: str) -> bool:
    """True when the text carries a 4-digit year token (an event or decision date)."""
    return any(token.isdigit() and 1900 <= int(token) <= 2100 for token in text.split())


def _due_visits(vault: Path, docs: list[str], cadence: dict, control: str) -> list[dict]:
    """Areas whose revisit cadence is due, based on doc existence and mtimes."""
    today = date.today()
    visits: list[dict] = []
    for area, spec in cadence.items():
        primary = spec.get("primary", "")
        last: date | None = None
        for path in docs:
            if Path(path).name.startswith(primary):
                try:
                    last = date.fromtimestamp(Path(path).stat().st_mtime)
                except OSError:
                    last = None
                break
        days = int(spec.get("days", 0))
        if last is None:
            visits.append(_visit(area, spec, "never", today))
            continue
        delta = (today - last).days
        if days and delta > days:
            visits.append(_visit(area, spec, last.isoformat(), today))
    return visits


def _visit(area: str, spec: dict, ultima: str, today: date) -> dict:
    return {
        "area": area,
        "last_review": ultima,
        "cadence_days": spec.get("days"),
        "primary": spec.get("primary"),
        "suggestion": spec.get("suggestion", ""),
    }


def plan_evolucion(*, vault, **kwargs) -> dict:
    """Read-only evolution scan for one vault.

    Returns: ``{date, vault, summary, candidates, due_visits}``.
    Writes nothing; candidates need owner confirmation before any document
    is created or promoted.
    """
    vault_path = Path(vault)
    sources = _scan_sources(vault_path)
    docs = _scan_docs(vault_path)
    entities = _scan_entities(vault_path)
    control = _control_text(vault_path)
    rules, cadence = _load_rules()
    candidates_list = _evaluate(sources, rules)
    visits = _due_visits(vault_path, docs, cadence, control)
    return {
        "date": date.today().isoformat(),
        "vault": str(vault_path),
        "summary": {
            "sources": len(sources),
            "documents": len(docs),
            "entities": len(entities),
        },
        "candidates": candidates_list,
        "due_visits": visits,
    }
