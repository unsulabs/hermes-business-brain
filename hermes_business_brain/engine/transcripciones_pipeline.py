"""Portable Stage B transactions. Agent-authored semantics remain proposals.

Every bundle is immutable and self-contained; publishing its one JSON file is
the commit point. Current per-version permission decisions and original hashes
are checked even on cache hits. No profile grants access to a source.
"""
from copy import deepcopy

from .transcripciones_analisis import analyze_parts, check_coverage
from .transcripciones_antecedentes import (
    invalidate_dependencies,
    merge_review,
    plan_review,
)
from .transcripciones_custodia import load_catalog
from .transcripciones_lectura import request_memo
from .transcripciones_modelo import (
    ModelError,
    atomic_write,
    bank_lock,
    json_bytes,
    load_json,
    read_bytes,
    result,
    safe_id,
    safe_path,
    sha256_bytes,
    validate_bank_location,
    validate_record,
)
from .transcripciones_permisos import authorized, permission_snapshot
from .transcripciones_segmentacion import (
    SEGMENTER_VERSION,
    segment_text,
    validate_partition,
)
from .transcripciones_taxonomia import propose_change, validate_taxonomy


def _digest(value):
    return sha256_bytes(json_bytes(value))


def _scope(company, audience, purpose="local_analysis"):
    if purpose != "local_analysis" or not all(isinstance(v, str) and v.strip() for v in (company, audience)):
        raise ModelError("ANALYSIS_SCOPE_REQUIRED")
    return dict(company=company, audience=audience, purpose=purpose)


def source(bank, tr_id, version_id, scope):
    safe_id(tr_id); safe_id(version_id)
    if not authorized(bank, tr_id, version_id, **scope):
        raise ModelError("SOURCE_PERMISSION_DENIED")
    rows = load_catalog(bank)
    if not any(r["tr_id"] == tr_id and version_id in r["version_ids"] for r in rows):
        raise ModelError("SOURCE_UNKNOWN")
    original = load_json(safe_path(bank, f"versiones/{version_id}.json"))
    data = read_bytes(bank, original["blob_path"])
    if original["tr_id"] != tr_id or original["sha256"] != sha256_bytes(data) or original["byte_length"] != len(data):
        raise ModelError("SOURCE_CHANGED")
    return data


def _publish(bank, operation, path, payload, commit, *, evidence=None, warning=None):
    encoded = json_bytes(payload)
    target = safe_path(bank, path)
    exists = target.exists()
    if exists and read_bytes(bank, path) != encoded:
        raise ModelError("IMMUTABLE_CONFLICT")
    if commit:
        atomic_write(bank, path, encoded)
    return result(operation, status="DONE_WITH_CONCERNS" if warning else "DONE",
                  outputs=[{"path": path, "sha256": sha256_bytes(encoded)}],
                  warnings=[warning] if warning else [],
                  evidence={"committed": commit, "idempotent": exists, **(evidence or {})})


def _transaction(bank, commit, action):
    validate_bank_location(bank)
    if commit:
        with bank_lock(bank):
            return action()
    return action()


def segment_capture(bank, tr_id, version_id, *, company, audience,
                    purpose="local_analysis", policy=SEGMENTER_VERSION,
                    max_core_bytes=4096, context_bytes=256, commit=False):
    scope = _scope(company, audience, purpose)
    if policy != SEGMENTER_VERSION:
        raise ModelError("SEGMENT_POLICY_INVALID")
    def prepare():
        source_keys = [(tr_id, version_id)]
        permission = permission_snapshot(bank, source_refs=source_keys, **scope)
        data = source(bank, tr_id, version_id, scope)
        identity = {"tr_id": tr_id, "version_id": version_id, "sha256": sha256_bytes(data),
                    "policy": policy, "max_core_bytes": max_core_bytes, "context_bytes": context_bytes,
                    "scope": scope, "permission_snapshot": permission}
        bundle_id = "SG-" + _digest(identity)
        path = f"segmentos/{bundle_id}.json"
        segments = segment_text(data, tr_id, version_id, max_core_bytes=max_core_bytes, context_bytes=context_bytes)
        if safe_path(bank, path).exists():
            prior = load_json(safe_path(bank, path))
            # Generated timestamps do not create a new semantic/cache identity.
            for old, new in zip(prior["segments"], segments):
                new["created_at"] = old["created_at"]
        payload = dict(schema_version="segment-bundle.v1", bundle_id=bundle_id, **identity, segments=segments)
        partition = validate_partition(data, segments)
        if permission_snapshot(bank, source_refs=source_keys, **scope) != permission:
            raise ModelError("PERMISSION_CHANGED")
        return _publish(bank, "segmentar", path, payload, commit,
                        evidence={"bundle_id": bundle_id, "permission_snapshot": permission,
                                  "segment_count": len(segments), "partition": partition})
    return _transaction(bank, commit, prepare)


def store_taxonomy(bank, taxonomy, *, event=None, commit=False):
    """A changed taxonomy requires an explicit invalidation event; no silent upgrade."""
    def prepare():
        validate_taxonomy(taxonomy)
        version = safe_id(taxonomy["taxonomy_version"])
        previous = taxonomy["previous_version"]
        impact = None
        folder = safe_path(bank, "taxonomia")
        existing = [load_json(p) for p in folder.glob("*.json")] if folder.exists() else []
        if previous is None and any(t["taxonomy_version"] != version for t in existing):
            raise ModelError("TAXONOMY_ROOT_EXISTS")
        if previous is not None:
            safe_id(previous)
            old = load_json(safe_path(bank, f"taxonomia/{previous}.json"))
            if any(t["previous_version"] == previous and t["taxonomy_version"] != version for t in existing):
                raise ModelError("BASE_VERSION_STALE")
            impact = propose_change(old, taxonomy, expected_version=previous,
                                    catalog_ids=[r["tr_id"] for r in load_catalog(bank)])
            if event is None:
                raise ModelError("TAXONOMY_EVENT_REQUIRED")
            validate_record("evento", event)
            if event["event_type"] != "taxonomia" or previous not in event["old_refs"] or version not in event["new_refs"]:
                raise ModelError("TAXONOMY_EVENT_INVALID")
        elif event is not None:
            raise ModelError("UNEXPECTED_EVENT")
        # Check every immutable destination before publishing an invalidation.
        preview = _publish(bank, "taxonomia", f"taxonomia/{version}.json", taxonomy, False,
                           evidence={"taxonomy_version": version, "impact": impact})
        if event is not None:
            _publish(bank, "evento", f"eventos/{safe_id(event['event_id'])}.json", event, False)
        if commit:
            if event is not None:
                # A crash here conservatively invalidates old derivatives; retry
                # completes the immutable new version without undoing history.
                _publish(bank, "evento", f"eventos/{event['event_id']}.json", event, True)
            return _publish(bank, "taxonomia", f"taxonomia/{version}.json", taxonomy, True,
                            evidence={"taxonomy_version": version, "impact": impact})
        return preview
    return _transaction(bank, commit, prepare)


def _events(bank):
    folder = safe_path(bank, "eventos")
    events = [load_json(p) for p in sorted(folder.glob("*.json"))] if folder.exists() else []
    for event in events:
        validate_record("evento", event)
    return events


def _analysis_graph(bank):
    nodes = {}
    for row in load_catalog(bank):
        nodes[row["tr_id"]] = {"id": row["tr_id"], "depends_on": []}
        for vid in row["version_ids"]:
            nodes[vid] = {"id": vid, "depends_on": [row["tr_id"]]}
    tax = safe_path(bank, "taxonomia")
    for path in tax.glob("*.json") if tax.exists() else []:
        taxonomy = load_json(path); validate_taxonomy(taxonomy)
        key = taxonomy["taxonomy_version"]
        nodes[key] = {"id": key, "depends_on": []}
    folder = safe_path(bank, "analisis")
    for path in folder.glob("*.json") if folder.exists() else []:
        bundle = load_json(path)
        run = bundle["run"]; validate_record("analisis", run)
        nodes[run["run_id"]] = {"id": run["run_id"], "depends_on": list(dict.fromkeys(
            [run["tr_id"], run["version_id"], run["taxonomy_version"], *run["dependency_ids"],
             *(ref["version_id"] for ref in bundle["source_refs"]),
             *(ref["tr_id"] for ref in bundle["source_refs"])]))}
    return list(nodes.values())


@request_memo
def invalidated_ids(bank):
    graph = _analysis_graph(bank)
    invalid = set()
    for event in _events(bank):
        invalid.update(invalidate_dependencies(event, graph)["evidence"]["invalidated_ids"])
    return invalid


@request_memo
def _supersession_graph(bank):
    """Replacement changes current selection, never the historical bytes."""
    folder = safe_path(bank, "analisis")
    bundles = {p.stem: load_json(p) for p in folder.glob("*.json")} if folder.exists() else {}
    parents = {}
    for rid, bundle in bundles.items():
        run = bundle["run"]
        validate_record("analisis", run)
        if run["run_id"] != rid:
            raise ModelError("RUN_REFERENCE_INVALID")
        old = run["supersedes_run_id"]
        if old is not None:
            previous = bundles.get(old)
            if previous is None or previous["run"]["tr_id"] != run["tr_id"] or previous["scope"] != bundle["scope"]:
                raise ModelError("RUN_REFERENCE_INVALID")
            parents[rid] = old
    for rid in parents:
        seen = set()
        while rid in parents:
            if rid in seen:
                raise ModelError("RUN_SUPERSESSION_CYCLE")
            seen.add(rid)
            rid = parents[rid]
    return parents


def _historical_context(bank, run_ids, scope):
    """Resolve only explicitly referenced stored runs; authenticate every cited source."""
    sources, registry, claims, visiting, visited = {}, {}, {}, set(), set()
    def visit(run_id):
        safe_id(run_id)
        if run_id in visiting:
            raise ModelError("RUN_DEPENDENCY_CYCLE")
        if run_id in visited:
            return
        visiting.add(run_id)
        bundle = load_json(safe_path(bank, f"analisis/{run_id}.json"))
        run = bundle["run"]
        if run["run_id"] != run_id or bundle["scope"] != scope:
            raise ModelError("RUN_REFERENCE_INVALID")
        for parent in bundle.get("historical_run_ids", []):
            visit(parent)
        for ref in bundle["source_refs"]:
            data = source(bank, ref["tr_id"], ref["version_id"], scope)
            if sha256_bytes(data) != ref["sha256"]:
                raise ModelError("SOURCE_CHANGED")
            sources[(ref["tr_id"], ref["version_id"])] = data
        taxonomy = load_json(safe_path(bank, f"taxonomia/{safe_id(run['taxonomy_version'])}.json"))
        check_coverage(run, bundle["segments"], bundle["claims"], bundle["relations"],
                       sources[(run["tr_id"], run["version_id"])], sources=sources,
                       known_refs=set(registry), ref_registry=registry,
                       historical_claims=list(claims.values()), taxonomy=taxonomy)
        for claim in bundle["claims"]:
            key = ("claim", claim["claim_id"], run["version_id"])
            if key in registry and registry[key] != claim:
                raise ModelError("HISTORICAL_ID_COLLISION")
            registry[key] = claim
            if claim["claim_id"] in claims and claims[claim["claim_id"]] != claim:
                raise ModelError("HISTORICAL_ID_COLLISION")
            claims[claim["claim_id"]] = claim
        for subject in run["subject_matrix"]:
            key = ("subject", subject["subject_id"], run["version_id"])
            value = {"id": subject["subject_id"], "version_id": run["version_id"], "evidence_spans": subject["evidence_spans"]}
            if key in registry and registry[key] != value:
                raise ModelError("HISTORICAL_ID_COLLISION")
            registry[key] = value
        visiting.remove(run_id); visited.add(run_id)
    for run_id in run_ids:
        visit(run_id)
    return sources, registry, list(claims.values())


def consolidate_analysis(bank, submission, *, company, audience, purpose="local_analysis", commit=False):
    """Input is agent-authored JSON, not executable instructions or model output inference."""
    scope = _scope(company, audience, purpose)
    required = {"tr_id", "version_id", "segment_bundle", "permission_snapshot", "run_id", "agent_results",
                "claims", "relations", "subject_matrix", "global_reconciliation", "analyzer_version",
                "taxonomy_version", "canonical_context_refs", "supersedes_run_id", "dependency_ids"}
    if not isinstance(submission, dict) or set(submission) != required:
        raise ModelError("ANALYSIS_SUBMISSION_INVALID")
    def prepare():
        tr, vid = submission["tr_id"], submission["version_id"]
        data = source(bank, tr, vid, scope)
        sg = safe_id(submission["segment_bundle"])
        segment_bundle = load_json(safe_path(bank, f"segmentos/{sg}.json"))
        primary_permission = permission_snapshot(bank, source_refs=[(tr, vid)], **scope)
        if segment_bundle["scope"] != scope or segment_bundle["permission_snapshot"] != primary_permission:
            raise ModelError("SEGMENT_SCOPE_STALE")
        if (segment_bundle["tr_id"], segment_bundle["version_id"]) != (tr, vid):
            raise ModelError("SOURCE_CHANGED")
        segments = segment_bundle["segments"]
        validate_partition(data, segments)
        taxonomy = safe_id(submission["taxonomy_version"])
        taxonomy_record = load_json(safe_path(bank, f"taxonomia/{taxonomy}.json"))
        validate_taxonomy(taxonomy_record)
        invalid = invalidated_ids(bank)
        if taxonomy in invalid or any(d in invalid for d in submission["dependency_ids"]):
            raise ModelError("DEPENDENCY_INVALIDATED")
        previous = submission["supersedes_run_id"]
        supersessions = _supersession_graph(bank)
        if previous is not None:
            safe_id(previous)
            old = load_json(safe_path(bank, f"analisis/{previous}.json"))["run"]
            if old["tr_id"] != tr or previous == submission["run_id"]:
                raise ModelError("RUN_REFERENCE_INVALID")
            cursor = previous
            while cursor in supersessions:
                cursor = supersessions[cursor]
                if cursor == submission["run_id"]:
                    raise ModelError("RUN_SUPERSESSION_CYCLE")
        known_ids = {r["id"] for r in _analysis_graph(bank)}
        if not set(submission["dependency_ids"]) <= known_ids:
            raise ModelError("DEPENDENCY_UNKNOWN")
        historical_ids = [d for d in submission["dependency_ids"] if safe_path(bank, f"analisis/{safe_id(d)}.json").exists()]
        if previous is not None and previous not in historical_ids:
            historical_ids.append(previous)
        history_sources, registry, historical_claims = _historical_context(bank, historical_ids, scope)
        context_hashes = []
        sources = {**history_sources, (tr, vid): data}
        for ref in submission["canonical_context_refs"]:
            if set(ref) != {"tr_id", "version_id", "sha256"}:
                raise ModelError("CONTEXT_REFERENCE_INVALID")
            context = source(bank, ref["tr_id"], ref["version_id"], scope)
            if sha256_bytes(context) != ref["sha256"]:
                raise ModelError("CONTEXT_CHANGED")
            context_hashes.append(ref["sha256"])
            sources[(ref["tr_id"], ref["version_id"])] = context
        spans = [s for c in submission["claims"] for s in c["evidence_spans"]]
        spans += [s for r in submission["relations"] for side in ("source_evidence", "target_evidence") for s in r[side]]
        spans += [s for subject in submission["subject_matrix"] for s in subject["evidence_spans"]]
        for span in spans:
            key = (span["tr_id"], span["version_id"])
            if key not in sources:
                sources[key] = source(bank, *key, scope)
        permission = permission_snapshot(bank, source_refs=list(sources), **scope)
        if submission["permission_snapshot"] != permission:
            raise ModelError("PERMISSION_SNAPSHOT_STALE")
        if any(c["editorial_state"] not in ("propuesta", "en_revision") for c in submission["claims"]) or any(r["editorial_state"] not in ("propuesta", "en_revision") for r in submission["relations"]):
            raise ModelError("RATIFICATION_FORBIDDEN")
        run_id = safe_id(submission["run_id"])
        args = {k: submission[k] for k in ("agent_results", "claims", "relations", "subject_matrix", "global_reconciliation",
                "analyzer_version", "taxonomy_version", "permission_snapshot", "supersedes_run_id", "run_id", "dependency_ids")}
        run = analyze_parts(data, segments, **args, canonical_context_hashes=context_hashes, sources=sources,
                            taxonomy=taxonomy_record, known_refs=set(registry), ref_registry=registry,
                            historical_claims=historical_claims)
        path = f"analisis/{run_id}.json"
        if safe_path(bank, path).exists():
            run["created_at"] = load_json(safe_path(bank, path))["run"]["created_at"]
        bundle = {"schema_version": "analysis-bundle.v1", "run": run, "segments": segments,
                  "claims": submission["claims"], "relations": submission["relations"], "scope": scope,
                  "source_refs": [{"tr_id": t, "version_id": v, "sha256": sha256_bytes(b)} for (t, v), b in sorted(sources.items())],
                  "submission_sha256": _digest(submission), "canonical_context_refs": submission["canonical_context_refs"]}
        bundle["historical_run_ids"] = historical_ids
        if permission_snapshot(bank, source_refs=list(sources), **scope) != permission:
            raise ModelError("PERMISSION_CHANGED")
        return _publish(bank, "analizar", path, bundle, commit,
                        evidence={"run_id": run_id, "cache_key": run["cache_key"], "coverage": run["coverage"]},
                        warning="SEMANTIC_ACCEPTANCE_PENDING")
    return _transaction(bank, commit, prepare)


def coverage_report(bank, tr_id, run_id, *, company, audience, purpose="local_analysis"):
    validate_bank_location(bank)
    scope = _scope(company, audience, purpose)
    safe_id(run_id)
    bundle = load_json(safe_path(bank, f"analisis/{run_id}.json"))
    run = bundle["run"]
    if run["tr_id"] != tr_id or bundle["scope"] != scope:
        raise ModelError("RUN_REFERENCE_INVALID")
    permission = permission_snapshot(bank, source_refs=bundle["source_refs"], **scope)
    sources, registry, history = _historical_context(bank, bundle.get("historical_run_ids", []), scope)
    for ref in bundle["source_refs"]:
        data = source(bank, ref["tr_id"], ref["version_id"], scope)
        if sha256_bytes(data) != ref["sha256"]:
            raise ModelError("SOURCE_CHANGED")
        sources[(ref["tr_id"], ref["version_id"])] = data
    taxonomy_record = load_json(safe_path(bank, f"taxonomia/{safe_id(run['taxonomy_version'])}.json"))
    report = check_coverage(run, bundle["segments"], bundle["claims"], bundle["relations"],
                            sources[(run["tr_id"], run["version_id"])], sources=sources, taxonomy=taxonomy_record,
                            known_refs=set(registry), ref_registry=registry, historical_claims=history)
    replacements = [rid for rid, previous in _supersession_graph(bank).items() if previous == run_id]
    reasons = []
    if run["permission_snapshot"] != permission:
        reasons.append("permission_snapshot_changed")
    if run_id in invalidated_ids(bank):
        reasons.append("dependency_invalidated")
    for ref in bundle["canonical_context_refs"]:
        if sha256_bytes(source(bank, ref["tr_id"], ref["version_id"], scope)) != ref["sha256"]:
            reasons.append("canonical_context_changed")
    dependency_current = not reasons
    if replacements:
        reasons.append("superseded")
    stale = bool(reasons)
    if permission_snapshot(bank, source_refs=bundle["source_refs"], **scope) != permission:
        raise ModelError("PERMISSION_CHANGED")
    return result("cobertura", status="DONE_WITH_CONCERNS", warnings=["DEPENDENCY_STALE" if stale else "SEMANTIC_ACCEPTANCE_PENDING"],
                  evidence={"run_id": run_id, "coverage": report, "current": not stale,
                            "dependency_current": dependency_current, "stale_reasons": sorted(set(reasons)),
                            "superseded_by": sorted(replacements), "ratified": False})


def review_snapshot(bank, *, company, audience, purpose="local_analysis"):
    scope = _scope(company, audience, purpose)
    permission = permission_snapshot(bank)
    entries = []
    for row in load_catalog(bank):
        versions = row["version_ids"]
        if not versions:
            continue
        eligible = [v for v in versions if authorized(bank, row["tr_id"], v, **scope)]
        entries.append({"tr_id": row["tr_id"], "version_ids": eligible or versions,
                        "excluded_version_ids": [v for v in versions if v not in eligible],
                        "eligibility": {**scope, "allowed": bool(eligible), "permission_snapshot": permission,
                                        "evidence": "current_per_version_permission_ledger"}})
    payload = {"entries": entries, "scope": scope, "permission_snapshot": permission}
    if permission_snapshot(bank) != permission:
        raise ModelError("PERMISSION_CHANGED")
    return {"snapshot_id": "SN-" + _digest(payload), **payload}


def review_history(bank, event, snapshot_id, *, company, audience, purpose="local_analysis",
                   results=None, previous_path=None, taxonomy_version=None, commit=False):
    scope = _scope(company, audience, purpose)
    def prepare():
        snapshot = review_snapshot(bank, **scope)
        if snapshot_id != snapshot["snapshot_id"]:
            raise ModelError("SNAPSHOT_CHANGED")
        plan = plan_review(event, snapshot)["evidence"]["plan"]
        previous = None
        if previous_path:
            prior = load_json(safe_path(bank, previous_path))
            if prior.get("taxonomy_version") != taxonomy_version:
                raise ModelError("REVIEW_TAXONOMY_CHANGED")
            previous = prior["merge"]
        sources, refs = {}, set()
        for job in plan["jobs"]:
            for vid in job["version_ids"]:
                sources[(job["tr_id"], vid)] = source(bank, job["tr_id"], vid, scope)
                refs.add(("source", job["tr_id"], vid))
        registry = {}
        folder = safe_path(bank, "analisis")
        eligible = set(sources)
        for path in folder.glob("*.json") if folder.exists() else []:
            bundle = load_json(path)
            if bundle["scope"] != scope or not {(r["tr_id"], r["version_id"]) for r in bundle["source_refs"]} <= eligible:
                continue
            _, known, _ = _historical_context(bank, [bundle["run"]["run_id"]], scope)
            for key, value in known.items():
                if key in registry and registry[key] != value:
                    raise ModelError("HISTORICAL_ID_COLLISION")
                registry[key] = value
        refs.update(registry)
        taxonomy = None
        if taxonomy_version is not None:
            taxonomy = load_json(safe_path(bank, f"taxonomia/{safe_id(taxonomy_version)}.json"))
            validate_taxonomy(taxonomy)
        merged = merge_review({"plan": plan, "results": results or [], "previous": previous,
                               "sources": sources, "known_refs": refs, "ref_registry": registry, "taxonomy": taxonomy})
        bundle = {"schema_version": "review-bundle.v1", "plan": plan, "merge": merged["evidence"],
                  "taxonomy_version": taxonomy_version}
        path = f"revisiones/{plan['plan_hash']}/{_digest(bundle)}.json"
        if review_snapshot(bank, **scope) != snapshot:
            raise ModelError("SNAPSHOT_CHANGED")
        _publish(bank, "evento", f"eventos/{safe_id(event['event_id'])}.json", event, False)
        output = _publish(bank, "revisar-antecedentes", path, bundle, False,
                          evidence={"plan_hash": plan["plan_hash"], "snapshot_id": snapshot_id,
                                    "pending_count": len(merged["evidence"]["pending_tr_ids"]),
                                    "cursor": merged["evidence"]["cursor"], "complete": merged["evidence"]["complete"]},
                          warning="SWEEP_INCOMPLETE" if not merged["evidence"]["complete"] else "SEMANTIC_ACCEPTANCE_PENDING")
        if commit:
            _publish(bank, "evento", f"eventos/{event['event_id']}.json", event, True)
            atomic_write(bank, path, json_bytes(bundle))
            output["evidence"]["committed"] = True
        return output
    return _transaction(bank, commit, prepare)
