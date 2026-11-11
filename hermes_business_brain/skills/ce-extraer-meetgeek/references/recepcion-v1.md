# MeetGeek Reception v1

Portable adaptation of the operational contract approved on 2026-11-04. It preserves the delivery format and the sealing protocol; it parameterizes only the destination. The local contract `docs/plans/CONTRATO_RECEPCION_V1.md` remains frozen and is not a dependency of the distributed product.

The extractor's only write destination: `<bank>/recepcion/meetgeek/<run>/<account>/<meeting>/<attempt>/`. `bank` is the absolute private path of the explicit profile, verified before writing; it is never inferred from the cwd nor from the exported product root. Verify the real product root and any repository containing `bank` with Git; reject a bank located inside any Git tree (even ignored), inside the vault, or one that escapes through symlinks. If the profile/destination is missing or unverifiable, preserve the work without starting capture and request only that destination. The existence of a directory does not accredit write permission.

The authorized mapping is `bank = <verified_workspace_root>/banco-transcripciones`; check that the containing root is still outside Git before using it. In another deployment, use the configured external bank -- do not reproduce that relative name inside the checkout. Directory components after `bank` (`recepcion`, `meetgeek`, `_inventario`) and the placeholder segments `run`/`account`/`meeting`/`attempt` are safe local identifiers, without slashes or `..`. Each attempt is new and immutable after sealing. The extractor is the only browser and clipboard operator; the consolidator only reads sealed deliveries.

Write the complete original first, without correcting it. Publish by atomic rename, at the end, `capture-manifest.v1.json`, UTF-8, with this structure (illustrative values):

```json
{
  "schema_version": "capture-manifest.v1",
  "job_id": "run-20261104",
  "attempt_id": "attempt-001",
  "account": {"id": "account-01", "observed_identity": "visible identity or unknown"},
  "meeting": {"id": "observed-id", "url": "https://app.meetgeek.ai/meeting/observed-id", "title": "observed title"},
  "captured_at": "2026-11-04T12:00:00Z",
  "method": "ui-copy-transcript",
  "file": {"path": "original.txt", "size_bytes": 123, "sha256": "64 hexadecimal characters"},
  "completeness": "unverified",
  "evidence": {"beginning": "beginning observation", "ending": "ending observation", "continuity": "how continuity was checked", "gaps": [], "uncertainties": []}
}
```

`completeness`: `complete`, `partial`, `unverified`, `inaccessible`. Only `complete` if beginning, end and continuity were all verified; a hash proves bytes, not completeness. For inaccessible meetings without a file, use `file: null` and describe the limit in gaps/uncertainties. Do not invent an ID, date, identity or evidence. `file.path` is relative to the attempt, without escapes or symlinks. SHA-256 and size are computed from the saved bytes. Do not store credentials.

Inventory and progress are saved under the same prefix, in `<run>/<account>/_inventario/<attempt>/`, as `inventory.json` and `progress.md`. Inventory: version, observed account, date, inspected sections, observed end of pagination or limit, list of IDs/URLs/titles/states, and attempts. Do not confuse inventory with capture. The inaccessible state does not count as a download. The two accounts keep independent provenances even when their bytes are equal.

Order: discover own session; inventory; check short, long and old samples; escalate only with preserved integrity; prioritize accessible old meetings; reconcile each meeting with an outcome. Do not pay, use new services, interpret content, or modify code, vault or taxonomy. If the session is missing, ask to open/start MeetGeek in the extractor chat. Absent access to the second account does not block preserving the first.
