"""Local leased queue. Immutable transitions and fenced result consolidation."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .transcripciones_modelo import (
    PRODUCER_VERSION,
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


class Queue:
    def __init__(self, bank, *, clock=None):
        validate_bank_location(bank)
        self.bank = Path(bank)
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))

    def _now(self):
        now = self.clock()
        if now.tzinfo is None:
            raise ModelError("CLOCK_INVALID")
        return now.astimezone(dt.timezone.utc)

    def _events(self, job_id):
        folder = safe_path(self.bank, f"jobs/{safe_id(job_id)}")
        return sorted(folder.glob("*.json")) if folder.exists() else []

    def get(self, job_id):
        events = self._events(job_id)
        if not events:
            raise ModelError("JOB_NOT_FOUND")
        record = load_json(events[-1])
        validate_record("cola", record)
        if record["job_id"] != job_id:
            raise ModelError("IDENTITY_MISMATCH")
        return record

    def _save(self, row):
        validate_record("cola", row)
        revision = len(self._events(row["job_id"])) + 1
        atomic_write(self.bank, f"jobs/{row['job_id']}/{revision:010d}.json", json_bytes(row))

    def enqueue(self, job_id, *, job_type="capture", scope=None, input_refs=None,
                input_hashes=None, depends_on=None, idempotency_key=None):
        safe_id(job_id)
        row = {"schema_version": "cola.v1", "created_at": utc_now(), "producer_version": PRODUCER_VERSION,
            "job_id": job_id, "job_type": job_type, "scope": scope or [], "input_refs": input_refs or [],
            "input_hashes": input_hashes or [], "snapshot_id": None, "cursor": None, "depends_on": depends_on or [],
            "idempotency_key": idempotency_key or job_id, "state": "pendiente", "attempt": 0, "lease_owner": None,
            "lease_expires_at": None, "fencing_token": 0, "staging_path": None, "result_manifest": None, "last_error": None}
        validate_record("cola", row)
        if len(row["input_refs"]) != len(row["input_hashes"]):
            raise ModelError("INPUT_SNAPSHOT_INVALID")
        for ref in row["input_refs"]:
            safe_path(self.bank, ref)
        with bank_lock(self.bank):
            if self._events(job_id):
                current = self.get(job_id)
                for key in ("job_type", "scope", "input_refs", "input_hashes", "depends_on", "idempotency_key"):
                    if current[key] != row[key]:
                        raise ModelError("IDEMPOTENCY_CONFLICT")
                return current
            self._save(row)
        return row

    def claim(self, job_id, owner, *, lease_seconds=300):
        safe_id(owner)
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float)) or not 0 < lease_seconds <= 86400:
            raise ModelError("LEASE_INVALID")
        with bank_lock(self.bank):
            row = self.get(job_id)
            now = self._now()
            if row["state"] in ("consolidado", "cancelado", "bloqueado"):
                raise ModelError("JOB_TERMINAL")
            if row["lease_expires_at"] and dt.datetime.fromisoformat(row["lease_expires_at"].replace("Z", "+00:00")) > now:
                raise ModelError("LEASE_BUSY")
            for dependency in row["depends_on"]:
                if self.get(dependency)["state"] != "consolidado":
                    raise ModelError("DEPENDENCY_PENDING")
            tokens = [load_json(path)["fencing_token"] for path in safe_path(self.bank, "jobs").glob("*/*.json")]
            token = max(tokens, default=0) + 1
            row.update(state="asignado", attempt=row["attempt"] + 1, lease_owner=owner,
                       lease_expires_at=(now + dt.timedelta(seconds=lease_seconds)).isoformat().replace("+00:00", "Z"),
                       fencing_token=token, staging_path=f"staging/{job_id}/{token}", result_manifest=None, last_error=None)
            self._save(row)
            return row

    def _fence(self, row, token):
        if type(token) is not int or token != row["fencing_token"]:
            raise ModelError("STALE_FENCING_TOKEN")
        if not row["lease_expires_at"] or dt.datetime.fromisoformat(row["lease_expires_at"].replace("Z", "+00:00")) <= self._now():
            raise ModelError("LEASE_EXPIRED")

    def _verify_inputs(self, row):
        for path, expected in zip(row["input_refs"], row["input_hashes"]):
            if sha256_bytes(read_bytes(self.bank, path)) != expected:
                raise ModelError("INPUT_VERSION_CHANGED")

    def _verify_outputs(self, row, manifest):
        probe = dict(row, result_manifest=manifest)
        validate_record("cola", probe)
        if not manifest["outputs"]:
            raise ModelError("OUTPUT_EMPTY")
        paths = set()
        outputs = []
        for item in manifest["outputs"]:
            path = item["path"]
            safe_path(self.bank, path)
            if not path.startswith(row["staging_path"] + "/") or path in paths:
                raise ModelError("STAGING_SCOPE_MISMATCH")
            paths.add(path)
            data = read_bytes(self.bank, path)
            if sha256_bytes(data) != item["sha256"]:
                raise ModelError("HASH_MISMATCH")
            outputs.append((path, data))
        return outputs

    def submit(self, job_id, token, manifest):
        with bank_lock(self.bank):
            row = self.get(job_id)
            self._fence(row, token)
            if row["state"] not in ("asignado", "ejecutando", "entregado"):
                raise ModelError("JOB_STATE_INVALID")
            self._verify_inputs(row)
            self._verify_outputs(row, manifest)
            if row["state"] == "entregado":
                if row["result_manifest"] != manifest:
                    raise ModelError("SEALED_RESULT_CHANGED")
                return row
            row.update(state="entregado", result_manifest=manifest)
            self._save(row)
            return row

    def commit(self, job_id, token):
        with bank_lock(self.bank):
            row = self.get(job_id)
            if row["state"] == "consolidado" and type(token) is int and token == row["fencing_token"]:
                for output in row["result_manifest"]["outputs"]:
                    dest = output["path"].replace(row["staging_path"] + "/", f"results/{job_id}/{token}/", 1)
                    if sha256_bytes(read_bytes(self.bank, dest)) != output["sha256"]:
                        raise ModelError("HASH_MISMATCH")
                return result("job-commit", request_id=job_id, evidence={"idempotent": True, "fencing_token": token})
            self._fence(row, token)
            if row["state"] != "entregado":
                raise ModelError("JOB_STATE_INVALID")
            self._verify_inputs(row)
            outputs = self._verify_outputs(row, row["result_manifest"])
            # The submitted immutable transition is the journal. Promotion can be
            # retried after any interruption; a consolidated transition is last.
            promoted = []
            for path, data in outputs:
                dest = path.replace(row["staging_path"] + "/", f"results/{job_id}/{token}/", 1)
                atomic_write(self.bank, dest, data)
                promoted.append({"path": dest, "sha256": sha256_bytes(data)})
            row["state"] = "consolidado"
            self._save(row)
            return result("job-commit", request_id=job_id, outputs=promoted, evidence={"idempotent": False, "fencing_token": token})


def claim(bank, job_id, owner, **kwargs):
    return Queue(bank).claim(job_id, owner, **kwargs)


def submit(bank, job_id, token, manifest):
    return Queue(bank).submit(job_id, token, manifest)


def commit(bank, job_id, token):
    return Queue(bank).commit(job_id, token)
