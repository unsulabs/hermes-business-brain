"""Portable retrospective reviews. Semantic judgments are supplied by agents.

All functions are pure except stage_review, which writes an immutable queue output.
The caller obtains current scoped eligibility from the permission ledger before
constructing a snapshot. Queue is responsible for leases and consolidation.
"""
from __future__ import annotations

from copy import deepcopy

from .transcripciones_modelo import (
    ModelError,
    atomic_write,
    json_bytes,
    result,
    safe_id,
    sha256_bytes,
    validate_bank_location,
    validate_record,
)


def _hash(value):
    return sha256_bytes(json_bytes(value))


def plan_review(event, catalog_snapshot):
    """Plan every eligible TR in a frozen snapshot; no lexical pruning.

    Entries require tr_id, version_ids and explicit eligibility metadata. A
    rejected entry still receives an excluded decision, never a semantic job.
    A new snapshot/event creates a new plan; resume uses merge_review.previous.
    """
    validate_record("evento", event)
    snapshot = deepcopy(catalog_snapshot)
    safe_id(snapshot["snapshot_id"])
    if event["sweep_snapshot"] != snapshot["snapshot_id"]:
        raise ModelError("SNAPSHOT_MISMATCH")
    entries = snapshot["entries"]
    ids = [safe_id(e["tr_id"]) for e in entries]
    if len(ids) != len(set(ids)):
        raise ModelError("DUPLICATE_TR")
    scope = None
    decisions, jobs = {}, []
    snapshot_hash = _hash(snapshot)
    for entry in sorted(entries, key=lambda e: e["tr_id"]):
        eligibility = entry.get("eligibility", {})
        if (type(eligibility.get("allowed")) is not bool or
                any(not eligibility.get(k) for k in
                    ("company", "audience", "purpose", "permission_snapshot", "evidence"))):
            raise ModelError("ELIGIBILITY_UNPROVEN")
        current_scope = {k: eligibility[k] for k in ("company", "audience", "purpose", "permission_snapshot")}
        if scope is not None and scope != current_scope:
            raise ModelError("SCOPE_MISMATCH")
        scope = current_scope
        versions = entry.get("version_ids", [])
        if not versions or len(set(versions)) != len(versions):
            raise ModelError("VERSION_REFERENCE_INVALID")
        for version in versions:
            safe_id(version)
        if not eligibility["allowed"]:
            decisions[entry["tr_id"]] = {"state": "excluded", "reason": "scope_or_permission"}
            continue
        inputs = {"event": event, "snapshot_hash": snapshot_hash, "entry": entry}
        digest = _hash(inputs)
        jobs.append({"job_id": "RV-" + digest[:32], "tr_id": entry["tr_id"],
                     "version_ids": versions, "input_hash": digest,
                     "attempt": 1, "state": "pending"})
    plan = {"schema_version": "review-plan.v1", "event": deepcopy(event),
            "snapshot": snapshot, "snapshot_hash": snapshot_hash,
            "scope": scope, "jobs": jobs, "excluded": decisions,
            "mode": "full_snapshot", "semantic_authority": "agent"}
    plan["plan_hash"] = _hash(plan)
    return result("plan_review", request_id=event["event_id"],
                  input_hashes=[snapshot_hash], evidence={"plan": plan})


def _validate_plan(plan):
    original = deepcopy(plan)
    claimed_hash = original.pop("plan_hash", None)
    if _hash(original) != claimed_hash:
        raise ModelError("PLAN_CHANGED")
    fresh = plan_review(plan["event"], plan["snapshot"])["evidence"]["plan"]
    if fresh != plan:
        raise ModelError("PLAN_CHANGED")


def merge_review(job_results):
    """Merge {plan, results, previous?}; missing entries remain pending.

    Each result carries job_id,input_hash,attempt,tr_id,state,reason,
    reviewed_version_ids,relations,proposals. Relations are verified against
    provided sources (tuple keys to original bytes) and known_refs. Results
    are proposed knowledge; no state here grants editorial ratification.
    Previous is this function's evidence record, preserving reviewed entries.
    """
    plan = job_results["plan"]
    _validate_plan(plan)
    jobs = {j["job_id"]: j for j in plan["jobs"]}
    previous = job_results.get("previous")
    accepted = {}
    if previous:
        if previous.get("plan_hash") != plan["plan_hash"]:
            raise ModelError("SNAPSHOT_MISMATCH")
        # Revalidate accumulated submissions, not a caller's claimed cursor.
        accepted = {r["job_id"]: r for r in previous["accepted_results"]}
        if len(accepted) != len(previous["accepted_results"]):
            raise ModelError("DUPLICATE_RESULT")
    for record in job_results.get("results", []):
        key = record["job_id"]
        if key in accepted and accepted[key] != record:
            raise ModelError("RESULT_CONFLICT")
        accepted[key] = deepcopy(record)
    decisions = deepcopy(plan["excluded"])
    relations, proposals = [], []
    eligible_versions = {(j["tr_id"], v) for j in jobs.values() for v in j["version_ids"]}
    for key, record in sorted(accepted.items()):
        job = jobs.get(key)
        if job is None or any(record.get(k) != job[k] for k in ("input_hash", "attempt", "tr_id")):
            raise ModelError("STALE_DELIVERY")
        if record.get("state") not in ("reviewed", "inaccessible", "failed") or not record.get("reason"):
            raise ModelError("REVIEW_DECISION_MISSING")
        if record["state"] == "reviewed":
            if sorted(record.get("reviewed_version_ids", [])) != sorted(job["version_ids"]):
                raise ModelError("VERSION_COVERAGE_INCOMPLETE")
        elif record.get("relations") or record.get("proposals"):
            raise ModelError("UNREVIEWED_PROPOSAL")
        for relation in record.get("relations", []):
            if relation.get("editorial_state") not in ("propuesta", "en_revision"):
                raise ModelError("RATIFICATION_FORBIDDEN")
            from .transcripciones_analisis import validate_relation
            validate_relation(relation, job_results.get("sources", {}),
                              set(job_results.get("known_refs", [])),
                              ref_registry=job_results.get("ref_registry"),
                              taxonomy=job_results.get("taxonomy"))
            cited = {(s["tr_id"], s["version_id"]) for side in ("source_evidence", "target_evidence")
                     for s in relation[side]}
            if not cited <= eligible_versions or not any(tr == job["tr_id"] for tr, _ in cited):
                raise ModelError("RELATION_SCOPE_MISMATCH")
            relations.append(deepcopy(relation))
        for proposal in record.get("proposals", []):
            if proposal.get("editorial_state") != "propuesta" or not proposal.get("reason"):
                raise ModelError("RATIFICATION_FORBIDDEN")
            proposals.append(deepcopy(proposal))
        decisions[job["tr_id"]] = {"state": record["state"], "reason": record["reason"]}
    pending = sorted(j["tr_id"] for j in jobs.values()
                     if decisions.get(j["tr_id"], {}).get("state") != "reviewed")
    for tr_id in pending:
        decisions.setdefault(tr_id, {"state": "pending", "reason": "not_delivered"})
    complete = not pending
    evidence = {"schema_version": "review-merge.v1", "plan_hash": plan["plan_hash"],
                "snapshot_id": plan["snapshot"]["snapshot_id"],
                "snapshot_hash": plan["snapshot_hash"], "decisions": decisions,
                "accepted_results": list(accepted.values()), "relations": relations,
                "proposals": proposals, "pending_tr_ids": pending,
                "cursor": {"next_tr_id": pending[0] if pending else None,
                           "reviewed_tr_ids": sorted(k for k,v in decisions.items() if v["state"] == "reviewed")},
                "complete": complete, "scope": "frozen_snapshot_only"}
    return result("merge_review", request_id=plan["event"]["event_id"],
                  status="DONE" if complete else "DONE_WITH_CONCERNS",
                  input_hashes=[plan["plan_hash"]],
                  warnings=[] if complete else ["SWEEP_INCOMPLETE"], evidence=evidence)


def invalidate_dependencies(event, records):
    """Transitively quarantine derivatives, including cyclic citation graphs.

    records = [{id,depends_on:[id],editorial_state?,kind?}]. Missing graph
    references are reported and taint their dependents; unknown lineage never
    certifies a clean derivative. No original record is changed.
    """
    validate_record("evento", event)
    graph = {}
    for record in records:
        key = safe_id(record["id"])
        if key in graph or not isinstance(record.get("depends_on"), list):
            raise ModelError("DEPENDENCY_INVALID")
        graph[key] = deepcopy(record)
    missing = {d for r in graph.values() for d in r["depends_on"] if d not in graph}
    seeds = set(event["affected_ids"]) | set(event["old_refs"])
    rejected = {k for k,r in graph.items() if r.get("editorial_state") in ("rechazado", "rejected")}
    tainted = seeds | rejected | missing
    changed = True
    while changed:
        changed = False
        for key, record in graph.items():
            if key not in tainted and set(record["depends_on"]) & tainted:
                tainted.add(key)
                changed = True
    affected = sorted(set(graph) & tainted)
    audit = [{"id": key, "state": "invalidated", "usable": False,
              "action": "withdraw" if key in rejected else "review_from_primary_sources",
              "contaminated_dependencies": sorted(set(graph[key]["depends_on"]) & tainted)}
             for key in affected]
    return result("invalidate_dependencies", request_id=event["event_id"],
                  status="DONE_WITH_CONCERNS" if missing else "DONE",
                  warnings=["DEPENDENCY_LINEAGE_INCOMPLETE"] if missing else [],
                  evidence={"schema_version": "dependency-audit.v1", "event": deepcopy(event),
                            "graph_hash": _hash(records), "invalidated_ids": affected,
                            "missing_dependency_ids": sorted(missing), "audit": audit,
                            "repaired": False})


def stage_review(bank, job_id, token, review_result):
    """Write one immutable output; Queue.submit/commit owns promotion."""
    validate_bank_location(bank)
    safe_id(job_id)
    if type(token) is not int or token < 1:
        raise ModelError("INVALID_FENCING_TOKEN")
    path = f"staging/{job_id}/{token}/review.json"
    payload = json_bytes(review_result)
    atomic_write(bank, path, payload, immutable=True)
    return {"path": path, "sha256": sha256_bytes(payload)}
