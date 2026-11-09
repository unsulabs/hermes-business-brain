"""Append-only capture import. Canonical visibility is an immutable commit receipt.

The journal contains exact prospective bytes. Recovery retries the same immutable
writes under the one bank lock and publishes the receipt last. A partially written
transaction is never a catalog entry. No semantic or permission inference occurs.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .transcripciones_lectura import request_memo
from .transcripciones_modelo import (
    PRODUCER_VERSION,
    ModelError,
    atomic_write,
    bank_lock,
    json_bytes,
    load_json,
    read_bytes,
    result,
    safe_path,
    sha256_bytes,
    utc_now,
    validate_bank_location,
    validate_record,
)


def _identity(account, meeting):
    digest = sha256_bytes(json_bytes([account, meeting]))
    return "TR-" + digest, "OC-" + digest


def _records(bank, folder):
    path = safe_path(bank, folder)
    if not path.exists():
        return []
    return [load_json(p) for p in sorted(path.glob("*.json"))]


def _receipt_id(manifest):
    return sha256_bytes(json_bytes([manifest["job_id"], manifest["account"]["id"],
                                  manifest["meeting"]["id"], manifest["attempt_id"]]))


def _check_receipt(receipt):
    if set(receipt) != {"schema_version", "capture_sha256", "capture", "tr_id", "version_id", "created_at", "original_path"} or receipt["schema_version"] != "receipt.v1":
        raise ModelError("RECEIPT_INVALID")
    validate_record("capture-manifest", receipt["capture"])
    if receipt["capture_sha256"] != sha256_bytes(json_bytes(receipt["capture"])):
        raise ModelError("HASH_MISMATCH")
    tr_id, _ = _identity(receipt["capture"]["account"]["id"], receipt["capture"]["meeting"]["id"])
    if receipt["tr_id"] != tr_id:
        raise ModelError("IDENTITY_MISMATCH")
    file = receipt["capture"]["file"]
    expected = "V-" + sha256_bytes(json_bytes([tr_id, file["sha256"]])) if file else None
    if receipt["version_id"] != expected or receipt["original_path"] != (f"versiones/{expected}.json" if file else None):
        raise ModelError("VERSION_REFERENCE_INVALID")


def _validate_transaction(tx):
    if set(tx) != {"schema_version", "receipt", "entries"} or tx["schema_version"] != "journal.v1":
        raise ModelError("JOURNAL_INVALID")
    receipt = tx["receipt"]
    _check_receipt(receipt)
    file = receipt["capture"]["file"]
    allowed = {f"originales/{file['sha256']}.bin", receipt["original_path"]} if file else set()
    if {entry["path"] for entry in tx["entries"]} != allowed or len(tx["entries"]) != len(allowed):
        raise ModelError("JOURNAL_INVALID")
    decoded = []
    for entry in tx["entries"]:
        if set(entry) != {"path", "sha256", "bytes_b64"}:
            raise ModelError("JOURNAL_INVALID")
        try:
            data = base64.b64decode(entry["bytes_b64"], validate=True)
        except ValueError as exc:
            raise ModelError("JOURNAL_INVALID") from exc
        if sha256_bytes(data) != entry["sha256"]:
            raise ModelError("HASH_MISMATCH")
        decoded.append((entry["path"], data))
    if file:
        blob = dict(decoded)[f"originales/{file['sha256']}.bin"]
        if sha256_bytes(blob) != file["sha256"] or len(blob) != file["size_bytes"]:
            raise ModelError("HASH_MISMATCH")
        original = json.loads(dict(decoded)[receipt["original_path"]])
        validate_record("original", original, lambda _: blob)
        if original["tr_id"] != receipt["tr_id"] or original["version_id"] != receipt["version_id"]:
            raise ModelError("IDENTITY_MISMATCH")
    return receipt, decoded


def _apply_transaction(bank, tx):
    receipt, decoded = _validate_transaction(tx)
    for path, data in decoded:
        atomic_write(bank, path, data)
    atomic_write(bank, f"receipts/{_receipt_id(receipt['capture'])}.json", json_bytes(receipt))


def _verify_completed(bank, tx):
    receipt, decoded = _validate_transaction(tx)
    if load_json(safe_path(bank, f"receipts/{_receipt_id(receipt['capture'])}.json")) != receipt:
        raise ModelError("IMMUTABLE_CONFLICT")
    for path, data in decoded:
        if read_bytes(bank, path) != data:
            raise ModelError("HASH_MISMATCH")


def _recover_locked(bank):
    count = 0
    # Journals remain append-only as an audit trail; completed ones are verified,
    # not re-applied, so corruption is detected instead of silently repaired.
    for tx in _records(bank, "journal"):
        receipt, _ = _validate_transaction(tx)
        rid = _receipt_id(receipt["capture"])
        if safe_path(bank, f"receipts/{rid}.json").exists():
            _verify_completed(bank, tx)
            continue
        _apply_transaction(bank, tx)
        count += 1
    return count


def recover_bank(bank):
    with bank_lock(bank):
        count = _recover_locked(bank)
    return result("recover", evidence={"recovered_transactions": count})


def _load_catalog(bank):
    groups = {}
    versions = {}
    completeness = {}
    for receipt in sorted(_records(bank, "receipts"), key=lambda r: (r["created_at"], r["capture_sha256"])):
        _check_receipt(receipt)
        m = receipt["capture"]
        tr_id, occurrence_id = _identity(m["account"]["id"], m["meeting"]["id"])
        if tr_id not in groups:
            groups[tr_id] = {
                "schema_version": "catalogo.v1", "created_at": receipt["created_at"], "producer_version": PRODUCER_VERSION,
                "tr_id": tr_id, "company_scope": [], "occurrences": [{"occurrence_id": occurrence_id,
                    "account_id": m["account"]["id"], "provider": "meetgeek" if m["method"] in ("ui-copy-transcript", "provider-export") else "local",
                    "provider_meeting_id": m["meeting"]["id"], "locator": m["meeting"]["url"], "access_state": "inaccessible"}],
                "version_ids": [], "preferred_version_id": None, "title_reported": m["meeting"]["title"],
                "event_time": None, "speaker_labels": [], "states": {"integrity": "pendiente", "completeness": "inaccesible",
                    "analysis": "pendiente", "editorial": "borrador", "validity": "sin_verificar"},
                "permission_record": {k: "desconocido" for k in ("custody", "local_analysis", "internal_query", "evaluation", "training", "publication")}, "analysis_runs": [],
            }
        row = groups[tr_id]
        if receipt["version_id"]:
            original_bytes = read_bytes(bank, receipt["original_path"])
            journal = load_json(safe_path(bank, f"journal/{_receipt_id(m)}.json"))
            if journal["receipt"] != receipt:
                raise ModelError("IMMUTABLE_CONFLICT")
            original_entry = next((e for e in journal["entries"] if e["path"] == receipt["original_path"]), None)
            if original_entry is None or original_entry["sha256"] != sha256_bytes(original_bytes):
                raise ModelError("HASH_MISMATCH")
            original = load_json(safe_path(bank, receipt["original_path"]))
            validate_record("original", original, lambda path: read_bytes(bank, path))
            if (original["tr_id"] != tr_id or original["version_id"] != receipt["version_id"]
                    or original["sha256"] != m["file"]["sha256"] or original["byte_length"] != m["file"]["size_bytes"]
                    or original["original_id"] != "OR-" + m["file"]["sha256"] or original["occurrence_ids"] != [occurrence_id]):
                raise ModelError("VERSION_REFERENCE_INVALID")
            versions[receipt["version_id"]] = original
            completeness.setdefault(receipt["version_id"], []).append(m["completeness"])
            if receipt["version_id"] not in row["version_ids"]:
                row["version_ids"].append(receipt["version_id"])
            row["occurrences"][0]["access_state"] = "accessible"
            row["states"]["integrity"] = "verificada"
            # No automatic preference by recency or evidence upgrades on historical versions.
            if row["preferred_version_id"] is None:
                row["preferred_version_id"] = receipt["version_id"]
            if row["preferred_version_id"] == receipt["version_id"]:
                state = {"complete": "completa_comprobada", "partial": "parcial", "unverified": "desconocida"}[m["completeness"]]
                order = {"inaccesible": 0, "desconocida": 1, "parcial": 2, "completa_comprobada": 3}
                if order[state] > order[row["states"]["completeness"]]:
                    row["states"]["completeness"] = state
    for row in groups.values():
        # Version lineage, not filesystem order or a wall clock, determines the
        # sequence. Detect forks, dangling references and cycles explicitly.
        successors = {}
        for version_id in row["version_ids"]:
            previous = versions[version_id]["previous_version_id"]
            if previous in successors or (previous is not None and previous not in row["version_ids"]):
                raise ModelError("VERSION_CHAIN_INVALID")
            successors[previous] = version_id
        chain = []
        current = successors.get(None)
        while current is not None:
            if current in chain:
                raise ModelError("VERSION_CHAIN_INVALID")
            chain.append(current)
            current = successors.get(current)
        if len(chain) != len(row["version_ids"]):
            raise ModelError("VERSION_CHAIN_INVALID")
        row["version_ids"] = chain
        row["preferred_version_id"] = chain[0] if chain else None
        if chain:
            observed = completeness[chain[0]]
            row["states"]["completeness"] = ("completa_comprobada" if "complete" in observed else
                "parcial" if "partial" in observed else "desconocida")
        validate_record("catalogo", row)
    return list(groups.values())


@request_memo
def load_catalog(bank):
    """Read-only derived view of committed receipts; never creates bank or lock."""
    validate_bank_location(bank)
    return _load_catalog(bank)


def verify_bank(bank):
    rows = load_catalog(bank)
    pending = 0
    for tx in _records(bank, "journal"):
        receipt, _ = _validate_transaction(tx)
        if safe_path(bank, f"receipts/{_receipt_id(receipt['capture'])}.json").exists():
            _verify_completed(bank, tx)
        else:
            pending += 1
    return result("verify", evidence={"transcriptions": len(rows), "versions": sum(len(r["version_ids"]) for r in rows),
                                      "pending_journals": pending})


def register_capture(bank, capture_manifest, *, commit=False):
    """Manifest is a sealed JSON path; dry-run does not create any bank files.

    Generic file/paste/monologue inputs use the same receipt shape with method
    file-import/pasted-text, an explicitly assigned local account and source ID,
    and nullable URL. Unknown capture completeness must remain unverified.
    """
    validate_bank_location(bank)
    manifest_path = Path(capture_manifest)
    if manifest_path.name != "capture-manifest.v1.json":
        raise ModelError("UNSEALED_CAPTURE")
    m = load_json(manifest_path)
    validate_record("capture-manifest", m)
    payload = None
    if m["file"]:
        payload = read_bytes(manifest_path.parent, m["file"]["path"])
        if not payload:
            raise ModelError("INPUT_EMPTY")
        if len(payload) != m["file"]["size_bytes"] or sha256_bytes(payload) != m["file"]["sha256"]:
            raise ModelError("HASH_MISMATCH")
    tr_id, occurrence_id = _identity(m["account"]["id"], m["meeting"]["id"])
    rid = _receipt_id(m)
    version_id = "V-" + sha256_bytes(json_bytes([tr_id, m["file"]["sha256"]])) if payload is not None else None
    receipt_path = f"receipts/{rid}.json"
    evidence = {"tr_id": tr_id, "version_id": version_id, "committed": False, "idempotent": False}
    output = result("register", request_id=m["job_id"], input_hashes=[m["file"]["sha256"]] if payload is not None else [],
                    evidence=evidence, warnings=["COMPLETENESS_UNVERIFIED"] if m["completeness"] == "unverified" else [])
    if not commit:
        return output
    with bank_lock(bank):
        _recover_locked(bank)
        if safe_path(bank, receipt_path).exists():
            prior = load_json(safe_path(bank, receipt_path))
            if prior["capture_sha256"] != sha256_bytes(json_bytes(m)):
                raise ModelError("SEALED_CAPTURE_CHANGED")
            _load_catalog(bank)  # do not acknowledge corruption as a successful retry
            evidence.update(committed=True, idempotent=True)
            return output
        rows = _load_catalog(bank)
        created = utc_now()
        receipt = {"schema_version": "receipt.v1", "capture_sha256": sha256_bytes(json_bytes(m)), "capture": m,
                   "tr_id": tr_id, "version_id": version_id, "created_at": created,
                   "original_path": f"versiones/{version_id}.json" if version_id else None}
        entries = []
        if payload is not None:
            path = receipt["original_path"]
            if safe_path(bank, path).exists():
                original_bytes = read_bytes(bank, path)
            else:
                row = next((r for r in rows if r["tr_id"] == tr_id), None)
                original = {"schema_version": "original.v1", "created_at": created, "producer_version": PRODUCER_VERSION,
                    "original_id": "OR-" + m["file"]["sha256"], "tr_id": tr_id, "version_id": version_id,
                    "blob_path": f"originales/{m['file']['sha256']}.bin", "sha256": m["file"]["sha256"],
                    "byte_length": len(payload), "media_type": "application/octet-stream", "encoding": None,
                    "captured_at": m["captured_at"], "capture_method": m["method"], "occurrence_ids": [occurrence_id],
                    "previous_version_id": row["version_ids"][-1] if row and row["version_ids"] else None,
                    "completeness_evidence": m["evidence"]}
                validate_record("original", original)
                original_bytes = json_bytes(original)
            for dest, data in [(f"originales/{m['file']['sha256']}.bin", payload), (path, original_bytes)]:
                entries.append({"path": dest, "sha256": sha256_bytes(data), "bytes_b64": base64.b64encode(data).decode("ascii")})
        tx = {"schema_version": "journal.v1", "receipt": receipt, "entries": entries}
        atomic_write(bank, f"journal/{rid}.json", json_bytes(tx))
        _apply_transaction(bank, tx)
        evidence["committed"] = True
        output["outputs"] = [{"path": receipt_path, "sha256": sha256_bytes(json_bytes(receipt))}]
    return output
