"""Preserve user deliveries verbatim; assembly is an explicitly derived byte join."""
from pathlib import Path

from .transcripciones_custodia import register_capture
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
    utc_now,
    validate_bank_location,
    validate_record,
)


def ingest(bank, *, job_id, account_id, source_id, attempt_id, parts,
           closed=False, expected_parts=None, method="file-import", commit=False):
    """parts is [(positive ordinal, exact bytes)]. No source identity is inferred.

    Local source/account IDs are caller-assigned locators, not observed people.
    closed attests only completion of this delivery, never fidelity to audio.
    """
    validate_bank_location(bank)
    if type(closed) is not bool:
        raise ModelError("INVALID_RECEPTION_STATE")
    for identifier in (job_id, account_id, source_id, attempt_id):
        safe_id(identifier)
    if not parts or any(type(n) is not int or n < 1 or not isinstance(b, bytes) or not b for n, b in parts):
        raise ModelError("INVALID_PART")
    numbers = [n for n, _ in parts]
    if len(set(numbers)) != len(numbers):
        raise ModelError("DUPLICATE_PART")
    if expected_parts is not None and (type(expected_parts) is not int or expected_parts < 1 or max(numbers) > expected_parts):
        raise ModelError("INVALID_EXPECTED_PARTS")
    ordered = sorted(parts)
    missing = sorted(set(range(1, (expected_parts or max(numbers)) + 1)) - set(numbers))
    complete = closed and expected_parts is not None and not missing
    prefix = f"recepcion/local/{job_id}/{account_id}/{source_id}/{attempt_id}"
    destination = safe_path(bank, prefix)
    joined = b"".join(payload for _, payload in ordered)
    entries = [{"number": n, "path": f"parts/{n:06d}.bin", "size_bytes": len(b), "sha256": sha256_bytes(b)} for n, b in ordered]
    assembly = {"schema_version": "assembly-manifest.v1", "source_id": source_id,
                "timestamp_semantics": "capture timestamp is local reception time; source event time unknown",
                "parts": entries, "expected_parts": expected_parts, "received_parts": numbers,
                "missing_parts": missing, "reception_closed": bool(closed),
                "join": "ordered-byte-concatenation-no-separator", "sha256": sha256_bytes(joined)}
    gaps = [f"Missing part {n}" for n in missing]
    uncertainties = ([] if closed else ["Reception remains open"])
    if expected_parts is None:
        uncertainties.append("Expected part count unknown")
    manifest = {"schema_version": "capture-manifest.v1", "job_id": job_id, "attempt_id": attempt_id,
                "account": {"id": account_id, "observed_identity": "desconocida"},
                "meeting": {"id": source_id, "url": None, "title": ""},
                "captured_at": utc_now(), "method": method,
                "file": {"path": "original.bin", "size_bytes": len(joined), "sha256": sha256_bytes(joined)},
                "completeness": "complete" if complete else "partial",
                "evidence": {"beginning": "First delivered part retained" if 1 in numbers else "",
                             "ending": "Caller closed this delivery" if closed else "",
                             "continuity": "All declared parts retained in ordinal order" if complete else "",
                             "gaps": gaps, "uncertainties": uncertainties}}
    validate_record("capture-manifest", manifest)
    output = result("ingresar", request_id=job_id, input_hashes=[e["sha256"] for e in entries],
                    status="DONE" if complete else "DONE_WITH_CONCERNS",
                    warnings=[] if complete else ["DELIVERY_INCOMPLETE"],
                    evidence={"committed": False, "completeness": manifest["completeness"],
                              "received_parts": len(parts), "missing_parts": missing})
    if not commit:
        return output
    # Seal receipt last. A retry of an interrupted delivery reuses exact originals.
    with bank_lock(bank):
        manifest_path = safe_path(destination, "capture-manifest.v1.json")
        if manifest_path.exists():
            previous = load_json(manifest_path)
            manifest["captured_at"] = previous["captured_at"]
        writes = [(e["path"], b) for e, (_, b) in zip(entries, ordered)]
        writes += [("original.bin", joined), ("assembly-manifest.v1.json", json_bytes(assembly)),
                   ("capture-manifest.v1.json", json_bytes(manifest))]
        # Reject conflicting attempts before any write, including an existing seal.
        for name, payload in writes:
            target = safe_path(destination, name)
            if target.exists() and read_bytes(destination, name) != payload:
                raise ModelError("IMMUTABLE_CONFLICT")
        for name, payload in writes:
            atomic_write(destination, name, payload)
    registered = register_capture(bank, manifest_path, commit=True)
    output["outputs"] = registered["outputs"] + [{"path": f"{prefix}/capture-manifest.v1.json", "sha256": sha256_bytes(json_bytes(manifest))},
                                                  {"path": f"{prefix}/assembly-manifest.v1.json", "sha256": sha256_bytes(json_bytes(assembly))}]
    output["evidence"].update(registered["evidence"])
    return output


def read_parts_manifest(path):
    """Input JSON: {parts:[{number:1,path:'part.txt'}], expected_parts:2, closed:false}."""
    path = Path(path)
    obj = load_json(path)
    if not isinstance(obj, dict) or set(obj) != {"parts", "expected_parts", "closed"} or type(obj["closed"]) is not bool or not isinstance(obj["parts"], list):
        raise ModelError("PARTS_MANIFEST_INVALID")
    parts = []
    for item in obj["parts"]:
        if not isinstance(item, dict) or set(item) != {"number", "path"}:
            raise ModelError("PARTS_MANIFEST_INVALID")
        parts.append((item["number"], read_bytes(path.parent, item["path"])))
    return parts, obj["expected_parts"], obj["closed"]
