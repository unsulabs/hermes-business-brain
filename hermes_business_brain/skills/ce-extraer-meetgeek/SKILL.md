---
name: ce-extraer-meetgeek
description: "Authorized inventory/extraction request on an identified account."
---

# ce-extraer-meetgeek

Read the [common contract](../ce-banco-transcripciones/references/contrato-comun.md) for states, permissions, context and availability.

- **Trigger:** authorized request for inventory/extraction on an identified account.
- **Inputs:** account alias verified in the UI, scope/sections, cutoff, cursor and prior inventory, assigned IDs. Never receive credentials in the brief.
- **Outputs:** inventory with an observable end or limit, intact exports staged in the bank, beginning/end and turn-continuity evidence, method, per-meeting gaps and per-account reconciliation. An empty copy is an error, not a valid original.
- **Errors:** `ACCOUNT_MISMATCH`, `SESSION_REQUIRED`, `RETENTION_UNAVAILABLE`, `VIRTUALIZED_PARTIAL`, `COPY_EMPTY`, `END_NOT_OBSERVED`. Preserve inventory; try at most two distinct safe alternatives before requiring concrete action.
- **Gate:** complete short/long/old samples verified before escalating; every inventoried occurrence has an outcome. Provider duration and summary do not prove completeness. A single UI/clipboard operator across all agents.

## Execution

Read [reception v1](references/recepcion-v1.md) before operating. It is the extractor's only delivery contract: reception only, original first, sealed manifest at the end. Discover available tools/session, verify the visible account, and preserve unknowns. Never receive credentials in the brief nor invent provider IDs. A single UI/clipboard operator; do not analyze content, edit taxonomy/code, or write to the vault. Check pagination and retention limits; do not mistake visible cards for the total inventory. If the session is missing, the only required action is to open/start MeetGeek in the extractor chat. Preserve the accessible account even when the second account is not open. Do not pay for or activate new services.

An independent consolidator reads only sealed deliveries and validates path, hash and schema; the extractor never promotes originals to the catalog. A correct hash does not prove completeness. An inaccessible state does not count as a download. The reception contract governs its names/fields even when the internal catalog uses another vocabulary.
