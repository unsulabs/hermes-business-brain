"""Local versioned references, without importing content or granting authority.

Owner, reading and faculties are explicit attestations of the operator.
Hashing does not prove semantic reading. URLs are catalogued without accessing
the network.
"""
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

from .transcripciones_modelo import (
    ModelError,
    atomic_write,
    bank_lock,
    json_bytes,
    load_json,
    read_bytes,
    safe_id,
    safe_path,
    sha256_bytes,
    validate_bank_location,
    validate_record,
)
from .transcripciones_permisos import PURPOSES, permission_snapshot
from .transcripciones_pipeline import source

ROOT = "referencias_externas"
KEYS = ("reference_id", "version_id", "company", "audience", "purpose")


def _scope(scope):
    if not isinstance(scope, dict) or set(scope) != {"company", "audience", "purpose"}:
        raise ModelError("EXTERNAL_SCOPE_REQUIRED")
    if not all(isinstance(x, str) and x.strip() for x in scope.values()) or scope["purpose"] not in PURPOSES:
        raise ModelError("EXTERNAL_SCOPE_REQUIRED")
    safe_id(scope["company"])


def _dependency(ref):
    if not isinstance(ref, dict):
        raise ModelError("EXTERNAL_DEPENDENCY_INVALID")
    kind = ref.get("kind")
    key = "reference_id" if kind == "external" else "tr_id"
    if kind not in {"external", "transcript"} or set(ref) - {"spans"} != {"kind", key, "version_id", "sha256"}:
        raise ModelError("EXTERNAL_DEPENDENCY_INVALID")
    safe_id(ref[key]); safe_id(ref["version_id"])
    digest = ref["sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ModelError("EXTERNAL_DEPENDENCY_INVALID")
    return kind, ref[key], ref["version_id"]


def _spans(data, spans):
    if not isinstance(spans, list):
        raise ModelError("EXTERNAL_SPANS_INVALID")
    intervals = []
    for span in spans:
        if (not isinstance(span, dict) or set(span) != {"start", "end", "sha256"}
                or type(span["start"]) is not int or type(span["end"]) is not int
                or not 0 <= span["start"] < span["end"] <= len(data)
                or sha256_bytes(data[span["start"]:span["end"]]) != span["sha256"]):
            raise ModelError("EXTERNAL_SPAN_CHANGED")
        intervals.append((span["start"], span["end"]))
    return sorted(intervals)


def _reading(record, ref, data, require_read):
    read = _spans(data, record.get("read_spans", []))
    used = _spans(data, ref.get("spans", []))
    if not require_read or record["reading_state"] == "complete":
        return
    if record["reading_state"] != "partial" or not used:
        raise ModelError("EXTERNAL_READING_INCOMPLETE")
    for start, end in used:
        cursor = start
        for left, right in read:
            if left <= cursor < right:
                cursor = right
            if cursor >= end:
                break
        if cursor < end:
            raise ModelError("EXTERNAL_SPAN_NOT_READ")


def _record_path(version):
    if not safe_id(version).startswith("EV-"):
        raise ModelError("EXTERNAL_VERSION_INVALID")
    return f"{ROOT}/versions/{version}.json"


def _version(payload):
    return "EV-" + sha256_bytes(json_bytes({k: v for k, v in payload.items() if k != "version_id"}))


def _location(record):
    locator = record["locator"]
    if locator["kind"] == "local_file":
        path = Path(locator["value"])
        if not path.is_absolute() or ".." in path.parts:
            raise ModelError("EXTERNAL_LOCAL_PATH_INVALID")
        safe_path(path.parent, path.name)
        return path
    url = urlparse(locator["value"])
    if url.scheme not in {"https", "http"} or not url.netloc or url.username or url.password:
        raise ModelError("EXTERNAL_URL_INVALID")
    return None


def _validate(record):
    validate_record("referencia-externa", record)
    if record["version_id"] != _version(record):
        raise ModelError("EXTERNAL_RECORD_CHANGED")
    path = _location(record)
    if record["reading_state"] != "unread" and not record["reading_evidence"]:
        raise ModelError("EXTERNAL_READING_EVIDENCE_REQUIRED")
    if record["access_state"] == "available":
        if path is None or record["sha256"] is None or record["byte_length"] is None:
            raise ModelError("EXTERNAL_LOCAL_BYTES_REQUIRED")
    elif record["reading_state"] != "unread":
        raise ModelError("EXTERNAL_UNREAD_REQUIRED")
    if record["reading_state"] == "unread" and record.get("read_spans"):
        raise ModelError("EXTERNAL_UNREAD_SPANS_CONFLICT")
    if path is None and (record["sha256"] is not None or record["byte_length"] is not None):
        raise ModelError("EXTERNAL_REMOTE_UNVERIFIED")
    keys = [_dependency(ref) for ref in record["dependencies"]]
    if len(keys) != len(set(keys)):
        raise ModelError("EXTERNAL_DEPENDENCY_DUPLICATED")


def _verify_file(record):
    path = _location(record)
    if path is None or record["access_state"] != "available":
        raise ModelError("EXTERNAL_ACCESS_UNVERIFIED")
    data = read_bytes(path.parent, path.name)
    if sha256_bytes(data) != record["sha256"] or len(data) != record["byte_length"]:
        raise ModelError("EXTERNAL_FILE_CHANGED")
    _spans(data, record.get("read_spans", []))
    return data


def read_reference(bank, reference_id, version_id):
    validate_bank_location(bank)
    safe_id(reference_id)
    record = load_json(safe_path(bank, _record_path(version_id)))
    _validate(record)
    if record["reference_id"] != reference_id:
        raise ModelError("EXTERNAL_ID_MISMATCH")
    return record


def register_reference(bank, metadata, *, commit=False):
    """Registers metadata only. The caller provides the expected SHA/bytes and reading."""
    validate_bank_location(bank)
    def prepare():
        record = deepcopy(metadata)
        if "version_id" in record or "schema_version" in record:
            raise ModelError("EXTERNAL_VERSION_COMPUTED")
        record["schema_version"] = "referencia-externa.v1"
        record["version_id"] = _version(record)
        _validate(record)
        if record["access_state"] == "available":
            _verify_file(record)
        for dep in record["dependencies"]:
            if dep["kind"] == "external":
                parent = read_reference(bank, dep["reference_id"], dep["version_id"])
                if parent["sha256"] != dep["sha256"]:
                    raise ModelError("EXTERNAL_DEPENDENCY_CHANGED")
        return record
    if not commit:
        return prepare()
    with bank_lock(bank):
        record = prepare()
        atomic_write(bank, _record_path(record["version_id"]), json_bytes(record))
        return record


def external_decisions(bank):
    validate_bank_location(bank)
    folder = safe_path(bank, f"{ROOT}/permissions")
    chain, previous = [], None
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        record = load_json(path)
        validate_record("permiso-externo", record)
        if record["sequence"] != len(chain) + 1 or record["previous_hash"] != previous or path.name != f"{record['sequence']:012d}.json":
            raise ModelError("EXTERNAL_PERMISSION_CHAIN_INVALID")
        chain.append(record)
        previous = sha256_bytes(json_bytes(record))
    return chain


def record_external_decision(bank, decision, *, commit=False):
    """Exact grant/revoke; never inferred from path, owner or OS access."""
    def prepare():
        read_reference(bank, decision.get("reference_id"), decision.get("version_id"))
        chain = external_decisions(bank)
        record = dict(decision, schema_version="permiso-externo.v1", sequence=len(chain) + 1,
                      previous_hash=sha256_bytes(json_bytes(chain[-1])) if chain else None)
        validate_record("permiso-externo", record)
        for prior in reversed(chain):
            if all(prior[k] == record[k] for k in KEYS):
                if all(prior[k] == record[k] for k in set(record) - {"sequence", "previous_hash"}):
                    return prior
                break
        return record
    if not commit:
        return prepare()
    with bank_lock(bank):
        record = prepare()
        atomic_write(bank, f"{ROOT}/permissions/{record['sequence']:012d}.json", json_bytes(record))
        return record


def _effective(bank):
    result = {}
    for d in external_decisions(bank):
        result[tuple(d[k] for k in KEYS)] = d
    return result


def verify_references(bank, references, scope, *, require_read=True, require_internal=False):
    """Verifies transitive closure of external references and TR without exposing bytes.

    Snapshot includes records/versions and effective dependency decisions,
    without being invalidated by grants of foreign sources. Never follows URLs.
    """
    validate_bank_location(bank)
    _scope(scope)
    if not isinstance(references, list) or not references:
        raise ModelError("EXTERNAL_REFERENCES_REQUIRED")
    effective = _effective(bank)
    visiting, verified, evidence, hashes = set(), set(), [], {}
    def visit(ref):
        key = _dependency(ref)
        if key in hashes and hashes[key] != ref["sha256"]:
            raise ModelError("EXTERNAL_DEPENDENCY_HASH_CONFLICT")
        hashes[key] = ref["sha256"]
        if key in visiting:
            raise ModelError("EXTERNAL_DEPENDENCY_CYCLE")
        fingerprint = sha256_bytes(json_bytes(ref))
        if fingerprint in verified:
            return
        visiting.add(key)
        if ref["kind"] == "transcript":
            raw = source(bank, ref["tr_id"], ref["version_id"], scope)
            if sha256_bytes(raw) != ref["sha256"]:
                raise ModelError("EXTERNAL_TRANSCRIPT_CHANGED")
            _spans(raw, ref.get("spans", []))
            evidence.append({"reference": ref, "permission_snapshot": permission_snapshot(bank, source_refs=[ref], **scope)})
        else:
            record = read_reference(bank, ref["reference_id"], ref["version_id"])
            if record["sha256"] != ref["sha256"]:
                raise ModelError("EXTERNAL_REFERENCE_HASH_MISMATCH")
            if record["admissibility"] != "admissible":
                raise ModelError("EXTERNAL_SOURCE_INADMISSIBLE")
            permission_key = (ref["reference_id"], ref["version_id"], scope["company"], scope["audience"], scope["purpose"])
            decision = effective.get(permission_key)
            if decision is None or decision["action"] != "grant":
                raise ModelError("EXTERNAL_PERMISSION_DENIED")
            if require_internal and record["sensitivity"] != "interno":
                raise ModelError("EXTERNAL_SENSITIVITY_RESTRICTED")
            raw = _verify_file(record)
            _reading(record, ref, raw, require_read)
            evidence.append({"reference": ref, "record_sha256": sha256_bytes(json_bytes(record)),
                             "permission": {k: v for k, v in decision.items() if k not in {"sequence", "previous_hash"}}})
            for dependency in record["dependencies"]:
                visit(dependency)
        visiting.remove(key)
        verified.add(fingerprint)
    for ref in references:
        visit(ref)
    # Reject concurrent access changes while reading files/recursing.
    current = _effective(bank)
    for item in evidence:
        ref = item["reference"]
        if ref["kind"] == "external":
            decision = current.get((ref["reference_id"], ref["version_id"], scope["company"], scope["audience"], scope["purpose"]))
            if decision is None or {k: v for k, v in decision.items() if k not in {"sequence", "previous_hash"}} != item["permission"]:
                raise ModelError("EXTERNAL_PERMISSION_CHANGED")
        elif permission_snapshot(bank, source_refs=[ref], **scope) != item["permission_snapshot"]:
            raise ModelError("EXTERNAL_PERMISSION_CHANGED")
    evidence.sort(key=lambda x: (_dependency(x["reference"]), json_bytes(x["reference"])))
    return {"scope": deepcopy(scope), "references": deepcopy(evidence),
            "snapshot_sha256": sha256_bytes(json_bytes({"scope": scope, "references": evidence})),
            "access_verified": True, "reading_is_operator_attestation": True}


def reference_ref(record, *, spans=None):
    """Explicit transportable form in a candidate; does not grant permissions."""
    _validate(record)
    if record["sha256"] is None:
        raise ModelError("EXTERNAL_HASH_UNAVAILABLE")
    ref = {"kind": "external", "reference_id": record["reference_id"],
           "version_id": record["version_id"], "sha256": record["sha256"]}
    if spans is not None:
        ref["spans"] = deepcopy(spans)
    return ref
