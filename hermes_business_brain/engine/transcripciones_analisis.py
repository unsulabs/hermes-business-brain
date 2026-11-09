"""Assemble agent-authored semantics; structural validation is not semantic approval.

No text classifier or LLM is hidden here. An agent must read every source core and
submit explicit results, attributed claims, subject destinations and reconciliation.
Callers check current analysis permission before supplying private source bytes.
"""
from copy import deepcopy

from .transcripciones_lectura import request_value
from .transcripciones_modelo import (
    ModelError,
    json_bytes,
    sha256_bytes,
    utc_now,
    validate_record,
)
from .transcripciones_segmentacion import boundaries, validate_partition
from .transcripciones_taxonomia import resolve_identity, validate_taxonomy


def cache_key(text_sha256, segmenter_version, analyzer_version, taxonomy_version,
              canonical_context_hashes, permission_snapshot):
    return sha256_bytes(json_bytes([text_sha256, segmenter_version, analyzer_version,
                                  taxonomy_version, sorted(canonical_context_hashes), permission_snapshot]))


@request_value
def _boundary_points(data):
    return frozenset(boundaries(data))


def validate_span(span, sources):
    key = (span["tr_id"], span["version_id"])
    if key not in sources:
        raise ModelError("SOURCE_REFERENCE_INVALID")
    data = sources[key]
    if sha256_bytes(data) != span["text_sha256"]:
        raise ModelError("SOURCE_CHANGED")
    start, end = span["start"], span["end"]
    points = _boundary_points(data)
    if type(start) is not int or type(end) is not int or start not in points or end not in points or start >= end:
        raise ModelError("OFFSET_INVALID")
    if sha256_bytes(data[start:end]) != span["excerpt_sha256"]:
        raise ModelError("EXCERPT_CHANGED")
    return True


def validate_claim(claim, sources, *, taxonomy=None):
    validate_record("afirmacion", claim)
    for span in claim["evidence_spans"]:
        validate_span(span, sources)
    if (claim["attribution_state"] == "resuelta") != (claim["resolved_entity_id"] is not None):
        raise ModelError("ATTRIBUTION_INVALID")
    if claim["attribution_state"] == "etiqueta_sin_resolver" and claim["speaker_label"] is None:
        raise ModelError("ATTRIBUTION_INVALID")
    if claim["attribution_state"] == "resuelta":
        if taxonomy is None or not claim.get("resolved_entity_kind") or not claim["speaker_label"]:
            raise ModelError("ATTRIBUTION_REGISTRY_REQUIRED")
        # The explicit label must resolve uniquely within kind AND scope. Supplying
        # an entity ID cannot bypass a homonym or manufacture an identity.
        entity = resolve_identity(taxonomy, claim["speaker_label"], scope=claim["scope"], kind=claim["resolved_entity_kind"])
        if entity["entity_id"] != claim["resolved_entity_id"]:
            raise ModelError("ATTRIBUTION_REFERENCE_INVALID")
    elif claim.get("resolved_entity_kind") is not None:
        raise ModelError("ATTRIBUTION_INVALID")
    if claim["supersedes_claim_id"] == claim["claim_id"]:
        raise ModelError("CLAIM_CYCLE")
    return True


def validate_relation(relation, sources, known_refs, *, ref_registry=None, taxonomy=None):
    validate_record("relacion", relation)
    for side in ("source", "target"):
        ref = relation[side+"_ref"]
        if (ref["kind"], ref["id"], ref["version_id"]) not in known_refs:
            raise ModelError("RELATION_REFERENCE_INVALID")
        key = (ref["kind"], ref["id"], ref["version_id"])
        if ref["kind"] == "source":
            if (ref["id"], ref["version_id"]) not in sources:
                raise ModelError("SOURCE_REFERENCE_INVALID")
            allowed = None
        else:
            record = (ref_registry or {}).get(key)
            if record is None:
                raise ModelError("REFERENCE_REGISTRY_REQUIRED")
            if ref["kind"] == "claim":
                validate_claim(record, sources, taxonomy=taxonomy)
                if record["claim_id"] != ref["id"]:
                    raise ModelError("RELATION_REFERENCE_INVALID")
            elif record.get("id") != ref["id"] or record.get("version_id") != ref["version_id"]:
                raise ModelError("RELATION_REFERENCE_INVALID")
            allowed = record.get("evidence_spans", [])
            if not allowed or (ref["kind"] == "claim" and not any(s["version_id"] == ref["version_id"] for s in allowed)):
                raise ModelError("RELATION_EVIDENCE_MISMATCH")
            for span in allowed:
                validate_span(span, sources)
        for span in relation[side+"_evidence"]:
            validate_span(span, sources)
            if allowed is None:
                if (span["tr_id"], span["version_id"]) != (ref["id"], ref["version_id"]):
                    raise ModelError("RELATION_EVIDENCE_MISMATCH")
            elif span not in allowed:
                raise ModelError("RELATION_EVIDENCE_MISMATCH")
    if relation["editorial_state"] == "ratificado" and not relation["reviewer"]:
        raise ModelError("REVIEW_REQUIRED")
    if relation["supersedes_relation_id"] == relation["relation_id"]:
        raise ModelError("RELATION_CYCLE")
    return True


def _unique(records, key):
    result = {r[key]: r for r in records}
    if len(result) != len(records):
        raise ModelError("DUPLICATE_ID")
    return result


def check_coverage(run, segments, claims, relations, data, *, sources=None, known_refs=None, ref_registry=None, historical_claims=None, taxonomy=None):
    validate_record("analisis", run)
    if taxonomy is None:
        raise ModelError("TAXONOMY_REQUIRED")
    validate_taxonomy(taxonomy)
    if taxonomy["taxonomy_version"] != run["taxonomy_version"]:
        raise ModelError("BASE_VERSION_STALE")
    categories = {c["category_id"]: c for c in taxonomy["categories"]}
    validate_partition(data, segments)
    source_key = (run["tr_id"], run["version_id"])
    sources = dict(sources or {})
    sources[source_key] = data
    if run["text_sha256"] != sha256_bytes(data) or any((s["tr_id"], s["version_id"], s["segmenter_version"]) != (*source_key, run["segmenter_version"]) for s in segments):
        raise ModelError("SOURCE_CHANGED")
    expected_cache = cache_key(run["text_sha256"], run["segmenter_version"], run["analyzer_version"], run["taxonomy_version"], run["canonical_context_hashes"], run["permission_snapshot"])
    if expected_cache != run["cache_key"]:
        raise ModelError("CONTEXT_STALE")
    parts = _unique(run["segment_results"], "segment_id")
    subjects = _unique(run["subject_matrix"], "subject_id")
    claim_map, relation_map = _unique(claims, "claim_id"), _unique(relations, "relation_id")
    history = _unique(historical_claims or [], "claim_id")
    if history.keys() & claim_map.keys():
        raise ModelError("DUPLICATE_ID")
    for claim in history.values():
        validate_claim(claim, sources, taxonomy=taxonomy)
    lineage = {**history, **claim_map}
    completed = set()
    def visit_claim(cid, active):
        if cid in active:
            raise ModelError("CLAIM_CYCLE")
        if cid in completed:
            return
        previous = lineage[cid]["supersedes_claim_id"]
        if previous is not None:
            if previous not in lineage:
                raise ModelError("CLAIM_REFERENCE_INVALID")
            visit_claim(previous, active | {cid})
        completed.add(cid)
    for cid in lineage:
        visit_claim(cid, set())
    if set(parts) != {s["segment_id"] for s in segments}:
        raise ModelError("ANALYSIS_INCOMPLETE")
    if set(run["claim_ids"]) != set(claim_map) or len(run["claim_ids"]) != len(claim_map) or set(run["relation_ids"]) != set(relation_map):
        raise ModelError("CLAIM_REFERENCE_INVALID")
    for claim in claims:
        validate_claim(claim, sources, taxonomy=taxonomy)
        if claim["run_id"] != run["run_id"] or claim["subject_id"] not in subjects:
            raise ModelError("CLAIM_REFERENCE_INVALID")
    seen_claims, seen_subjects = set(), set()
    for segment in segments:
        part = parts[segment["segment_id"]]
        if not set(part["subject_ids"]) <= subjects.keys() or not set(part["claim_ids"]) <= claim_map.keys():
            raise ModelError("SUBJECT_REFERENCE_INVALID")
        if part["status"] == "sustantivo" and not part["subject_ids"]:
            raise ModelError("SUBJECT_MISSING")
        if part["status"] != "sustantivo" and (not part["reason"] or part["claim_ids"] or part["subject_ids"]):
            raise ModelError("EXCEPTION_REASON_REQUIRED")
        for cid in part["claim_ids"]:
            claim = claim_map[cid]
            if claim["subject_id"] not in part["subject_ids"] or not any((e["tr_id"], e["version_id"]) == source_key and e["start"] < segment["core_end"] and e["end"] > segment["core_start"] for e in claim["evidence_spans"]):
                raise ModelError("CORE_EVIDENCE_MISSING")
        seen_claims.update(part["claim_ids"])
        seen_subjects.update(part["subject_ids"])
    if seen_subjects != subjects.keys() or seen_claims != claim_map.keys():
        raise ModelError("COVERAGE_GAP")
    for sid, subject in subjects.items():
        for assignment in subject["classifications"]:
            category = categories.get(assignment["category_id"])
            if category is None or category["axis"] != assignment["axis"]:
                raise ModelError("CATEGORY_REFERENCE_INVALID")
        expected = {c["claim_id"] for c in claims if c["subject_id"] == sid}
        if set(subject["claim_ids"]) != expected:
            raise ModelError("SUBJECT_REFERENCE_INVALID")
        for span in subject["evidence_spans"]:
            validate_span(span, sources)
        if subject["destination"]["kind"] == "source" and subject["destination"]["id"] != run["tr_id"]:
            raise ModelError("DESTINATION_INVALID")
    refs = set(known_refs or []) | {("claim", cid, run["version_id"]) for cid in claim_map} | {("subject", sid, run["version_id"]) for sid in subjects} | {("source", run["tr_id"], run["version_id"])}
    registry = dict(ref_registry or {})
    registry.update({("claim", cid, run["version_id"]): claim for cid, claim in claim_map.items()})
    registry.update({("subject", sid, run["version_id"]): dict(id=sid, version_id=run["version_id"], evidence_spans=subject["evidence_spans"]) for sid, subject in subjects.items()})
    for relation in relations:
        validate_relation(relation, sources, refs, ref_registry=registry, taxonomy=taxonomy)
        for side in ("source", "target"):
            ref = relation[side+"_ref"]
            if ref["kind"] == "claim" and ref["id"] in claim_map:
                if any(span not in claim_map[ref["id"]]["evidence_spans"] for span in relation[side+"_evidence"]):
                    raise ModelError("RELATION_EVIDENCE_MISMATCH")
    reconciliation = run["global_reconciliation"]
    if set(reconciliation["subject_ids"]) != subjects.keys() or (reconciliation["status"] == "revisada" and not reconciliation["reviewer"]):
        raise ModelError("RECONCILIATION_INCOMPLETE")
    for correction in reconciliation["corrections"]:
        earlier, later, rid = (correction[k] for k in ("earlier_claim_id", "later_claim_id", "relation_id"))
        if earlier not in claim_map or later not in claim_map or rid not in relation_map:
            raise ModelError("CORRECTION_REFERENCE_INVALID")
        relation = relation_map[rid]
        if relation["source_ref"]["id"] != later or relation["target_ref"]["id"] != earlier or relation["predicate"] not in ("precisa", "contradice", "sustituye"):
            raise ModelError("CORRECTION_REFERENCE_INVALID")
    if not {c["claim_id"] for c in claims if c["kind"] == "correccion"} <= {c["later_claim_id"] for c in reconciliation["corrections"]}:
        raise ModelError("CORRECTION_UNRECONCILED")
    coverage = dict(examined_core_bytes=len(data), total_core_bytes=len(data), material_subjects=len(subjects),
                    subjects_with_destination=len(subjects), unreadable_segment_ids=[s["segment_id"] for s in segments if parts[s["segment_id"]]["status"] == "ilegible"],
                    state="completa" if reconciliation["status"] == "revisada" else "parcial", semantic_acceptance="pending_independent_review")
    if run["coverage"] != coverage:
        raise ModelError("COVERAGE_MISMATCH")
    return coverage


def analyze_parts(data, segments, *, agent_results, claims, relations, subject_matrix, global_reconciliation,
                  analyzer_version, taxonomy_version, canonical_context_hashes, permission_snapshot,
                  supersedes_run_id=None, run_id=None, dependency_ids=None, sources=None, known_refs=None, ref_registry=None, historical_claims=None, taxonomy=None):
    validate_partition(data, segments)
    first = segments[0]
    key = cache_key(first["text_sha256"], first["segmenter_version"], analyzer_version, taxonomy_version, canonical_context_hashes, permission_snapshot)
    run = dict(schema_version="analisis.v1", created_at=utc_now(), producer_version="assembler-1", run_id=run_id or "RUN-"+key[:32],
               tr_id=first["tr_id"], version_id=first["version_id"], text_sha256=first["text_sha256"], segmenter_version=first["segmenter_version"],
               analyzer_version=analyzer_version, taxonomy_version=taxonomy_version, canonical_context_hashes=canonical_context_hashes,
               permission_snapshot=permission_snapshot, cache_key=key, supersedes_run_id=supersedes_run_id,
               segment_results=agent_results, subject_matrix=subject_matrix, global_reconciliation=global_reconciliation,
               claim_ids=[c["claim_id"] for c in claims], relation_ids=[r["relation_id"] for r in relations], dependency_ids=dependency_ids or [])
    run["coverage"] = dict(examined_core_bytes=len(data), total_core_bytes=len(data), material_subjects=len(subject_matrix), subjects_with_destination=len(subject_matrix),
                           unreadable_segment_ids=[p["segment_id"] for p in agent_results if p["status"] == "ilegible"],
                           state="completa" if global_reconciliation["status"] == "revisada" else "parcial", semantic_acceptance="pending_independent_review")
    check_coverage(run, segments, claims, relations, data, sources=sources, known_refs=known_refs, ref_registry=ref_registry, historical_claims=historical_claims, taxonomy=taxonomy)
    return deepcopy(run)


def assemble_analysis(run_manifest, segment_results):
    """Manifest is an in-memory explicit bundle; never executes corpus instructions."""
    args = dict(run_manifest)
    return analyze_parts(agent_results=segment_results, **args)
