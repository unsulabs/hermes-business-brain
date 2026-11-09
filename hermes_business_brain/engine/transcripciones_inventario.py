"""Inventory reconciliation preserves unknowns and does not attest UI extraction."""
from .transcripciones_modelo import ModelError, result, validate_record


def validate_inventory(snapshot):
    validate_record("inventario", snapshot)
    if not snapshot["sections"]:
        raise ModelError("INVENTORY_SCOPE_EMPTY")
    names = [s["name"] for s in snapshot["sections"]]
    if len(names) != len(set(names)):
        raise ModelError("DUPLICATE_SECTION")
    for section in snapshot["sections"]:
        if section["end_observed"] and (not section["end_evidence"] or section["limit"] is not None):
            raise ModelError("END_NOT_OBSERVED")
        if not section["end_observed"] and not section["limit"]:
            raise ModelError("LIMIT_UNEXPLAINED")
    ids = [m["id"] for m in snapshot["meetings"]]
    if len(ids) != len(set(ids)):
        raise ModelError("DUPLICATE_MEETING")
    return {"valid": True, "kind": "inventario", "inventory_closed": all(s["end_observed"] for s in snapshot["sections"])}


def reconcile(snapshot, catalog):
    validation = validate_inventory(snapshot)
    account = snapshot["account"]["id"]
    by_meeting = {}
    for row in catalog:
        validate_record("catalogo", row)
        for occurrence in row["occurrences"]:
            if occurrence["account_id"] == account:
                key = occurrence["provider_meeting_id"]
                if key in by_meeting:
                    raise ModelError("IDENTITY_AMBIGUOUS")
                by_meeting[key] = row
    counts = {k: 0 for k in ("complete", "partial", "unverified", "inaccessible", "pending", "failed")}
    entries = []
    for meeting in snapshot["meetings"]:
        row = by_meeting.get(meeting["id"])
        state = meeting["state"] if meeting["state"] in ("inaccessible", "failed") else "pending"
        if row:
            state = {"completa_comprobada": "complete", "parcial": "partial", "desconocida": "unverified", "inaccesible": "inaccessible"}[row["states"]["completeness"]]
            if row["states"]["integrity"] != "verificada" and state != "inaccessible":
                state = "failed"
        counts[state] += 1
        entries.append({"meeting_id": meeting["id"], "state": state, "tr_id": row["tr_id"] if row else None})
    pending = sum(counts[k] for k in ("pending", "partial", "unverified", "failed"))
    # Inaccessible entries are terminal accounting, but never downloaded.
    closed = validation["inventory_closed"]
    return result("reconcile", request_id=snapshot["snapshot_id"], status="DONE" if closed and pending == 0 else "DONE_WITH_CONCERNS",
                  evidence={"inventory_closed": closed, "download_complete": closed and pending == 0 and counts["inaccessible"] == 0,
                            "all_discovered_accounted": pending == 0, "discovered": len(entries), "downloaded_complete": counts["complete"],
                            "pending_recoverable": pending, "counts": counts, "meetings": entries})
