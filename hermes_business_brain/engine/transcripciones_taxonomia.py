"""Versioned semantic taxonomy proposals. Names alone never merge identities."""
from copy import deepcopy

from .transcripciones_modelo import (
    ModelError,
    json_bytes,
    sha256_bytes,
    utc_now,
    validate_record,
)


def validate_taxonomy(taxonomy):
    validate_record("taxonomia", taxonomy)
    categories = taxonomy["categories"]
    ids = {c["category_id"] for c in categories}
    entity_ids = {e["entity_id"] for e in taxonomy["entities"]}
    if len(ids) != len(categories) or len(entity_ids) != len(taxonomy["entities"]):
        raise ModelError("ENTITY_COLLISION")
    if taxonomy["taxonomy_version"] == taxonomy["previous_version"]:
        raise ModelError("TAXONOMY_CYCLE")
    graph = {}
    for change in taxonomy["equivalences"]:
        before, after = change["from_ids"], change["to_ids"]
        if not set(after) <= ids or set(before) & set(after):
            raise ModelError("TAXONOMY_REFERENCE_INVALID")
        if change["kind"] == "fusiona" and (len(before) < 2 or len(after) != 1):
            raise ModelError("TAXONOMY_CHANGE_INVALID")
        if change["kind"] == "divide" and (len(before) != 1 or len(after) < 2):
            raise ModelError("TAXONOMY_CHANGE_INVALID")
        if change["kind"] == "renombra" and (len(before) != 1 or len(after) != 1):
            raise ModelError("TAXONOMY_CHANGE_INVALID")
        for source in before:
            graph.setdefault(source, set()).update(after)
    def visit(node, active, done):
        if node in active:
            raise ModelError("TAXONOMY_CYCLE")
        if node in done:
            return
        for target in graph.get(node, ()):
            visit(target, active | {node}, done)
        done.add(node)
    done = set()
    for node in graph:
        visit(node, set(), done)
    return {"valid": True, "taxonomy_version": taxonomy["taxonomy_version"]}


def resolve_identity(taxonomy, name, *, scope, kind, entity_id=None):
    validate_taxonomy(taxonomy)
    candidates = [e for e in taxonomy["entities"] if e["scope"] == scope and e["kind"] == kind
                  and name.casefold() in {n.casefold() for n in [e["name"], *e["aliases"]]}]
    if entity_id is not None:
        candidates = [e for e in candidates if e["entity_id"] == entity_id]
    if len(candidates) != 1 or not candidates[0]["identity_evidence"]:
        raise ModelError("AMBIGUOUS_ALIAS")
    return deepcopy(candidates[0])


def propose_change(previous, proposed, *, expected_version, catalog_ids, affected_ids=None, impact_evidence=None):
    validate_taxonomy(previous)
    validate_taxonomy(proposed)
    if previous["taxonomy_version"] != expected_version or proposed["previous_version"] != expected_version:
        raise ModelError("BASE_VERSION_STALE")
    old = {c["category_id"]:c for c in previous["categories"]}
    new = {c["category_id"]:c for c in proposed["categories"]}
    for change in proposed["equivalences"]:
        if not set(change["from_ids"]) <= old.keys():
            raise ModelError("TAXONOMY_REFERENCE_INVALID")
    catalog = sorted(set(catalog_ids))
    affected = catalog if affected_ids is None else sorted(set(affected_ids))
    if affected_ids is not None and not impact_evidence:
        raise ModelError("IMPACT_EVIDENCE_REQUIRED")
    if not set(affected) <= set(catalog):
        raise ModelError("CATALOG_REFERENCE_INVALID")
    return {"previous_version":expected_version, "taxonomy_version":proposed["taxonomy_version"],
            "added":sorted(new.keys()-old.keys()), "removed":sorted(old.keys()-new.keys()),
            "changed":sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
            "entities_changed":previous["entities"] != proposed["entities"],
            "equivalences":deepcopy(proposed["equivalences"]),
            "snapshot_sha256":sha256_bytes(json_bytes(catalog)), "full_sweep":affected_ids is None,
            "impact_evidence":impact_evidence,
            "jobs":[{"tr_id":tr, "taxonomy_version":proposed["taxonomy_version"], "state":"pendiente"} for tr in affected]}


def seed_taxonomy():
    """Generic navigation vocabulary only, never assertions about an actual business."""
    definitions = [
        ("CAT-criterio", "asunto", "Criteria", "Reasons and exceptions that guide a decision", ["Explicit reasons", "Exceptions"], ["Inferences without evidence"], ["If the test fails, review the scope"]),
        ("CAT-proceso", "actividad", "Processes", "Work sequences described by a source", ["Steps and owners"], ["Promises without a described process"], ["Review before sending"]),
        ("CAT-recurso", "entidad", "Resources", "References to objects with identity and scope", ["Identified document"], ["Homonymy without identity"], ["Synthetic manual for testing"]),
        ("CAT-propuesta", "estado", "Proposals", "Ideas pending a decision or ratification", ["Explicit alternatives"], ["Already-measured results"], ["I propose testing an alternative"]),
        ("CAT-evaluacion", "finalidad", "Evaluation", "Use intended to verify results", ["Explicit trial"], ["Authorization inferred from possession"], ["Evaluate synthetic data only"]),
    ]
    result = dict(schema_version="taxonomia.v1", created_at=utc_now(), producer_version="taxonomy-seed-1", taxonomy_version="generic-1", previous_version=None,
                  categories=[dict(category_id=i,axis=a,name=n,definition=d,inclusion=inc,exclusion=exc,aliases=[],examples=ex) for i,a,n,d,inc,exc,ex in definitions],
                  equivalences=[], entities=[])
    validate_taxonomy(result)
    return result
