---
name: ce-evolucion
description: "Scan a business vault for knowledge that is ready to evolve: promotion candidates from captured sources, areas whose revisit cadence is due; proposals are presented to the owner, never applied automatically, so the vault matures with use."
---

# ce-evolucion

The evolution scan is how a business vault keeps maturing after onboarding. The first session seeds the vault with captured sources; daily use keeps feeding it; and this loop turns accumulated material into better knowledge: criteria that become explicit, offers that earn their living record, decisions that get their X07, areas that fall due for a revisit. The rulebook lives in `reglas_evolucion.json` and the scan itself is read-only.

**1. When to scan.** Run `brain_evolution_scan` (vault = the resolved vault path): (a) in any session where new material was captured or a case moved forward; (b) before closing a working session, to leave the next session with a clear focus; (c) on the cadence of each area (see the scan output) so nothing silently lapses. Always resolve the vault first per the [obsidian-router skill](../obsidian-router/SKILL.md): a scan against the wrong or unresolved path is noise.

**2. Read the candidates as proposals, not decisions.** The scan returns:

- `candidates`: each item says which promotion rule fired (`rule_id`), what action it proposes (`proposed_action`), the evidence paths that triggered it (`evidence`), and a state: `ready` (enough distinct evidence per the rule) or `partial` (thin evidence - keep the material in source and keep collecting).
- `due_visits`: areas whose revisit cadence is due (`area`, `last_review`, `cadence_days`, `primary`, `suggestion`).

A `ready` candidate is a *candidate*, never an instruction. A `partial` candidate must stay in source; promoting it now would repeat the classic error of turning one anecdote into a document.

**3. Owner confirmation protocol.** Present the candidates to the owner one by one with their evidence paths and the exact proposed action. Nothing is applied automatically:

- For a document action (D/X or X01/X07): draft it with `brain_document` (or `brain_propose` for a change to an existing note), citing the evidence files, in `en_revision` state, for the owner to review - never approved content.
- Applying any accepted change goes through the existing change machinery and only after explicit authorization and a backup: `brain_propose` first (owner reviews), then `brain_dx_apply` with a real `referencia_autorizacion` and `backup_dir`.
- A rejected candidate is never rehabilitated in another round; leave it in source.

**4. Record the evolution log.** After any promotion, append a short line to the vault CONTROL note (the same note used by ce-descubrimiento): date, rule id, target document, and the evidence paths. The log is what later scans use to avoid re-proposing the same promotion twice.

**5. Tie revisits to continuity.** When `due_visits` lists an area, schedule the follow-up through [ce-continuidad](../ce-continuidad/SKILL.md): next focus = the area's `suggestion` plus the round-2 prompts in the matching [area template](../ce-primera-sesion/references/area-templates/README.md). The cadence lives in `reglas_evolucion.json` and is itself a versioned file - improving the rules improves every vault that uses the plugin.

**6. Close with a runnable task.** After presenting candidates and confirming the accepted set, finish with one concrete next action from the knowledge (a question via [ce-consulta](../ce-consulta/SKILL.md), a draft to prepare, a revisit to schedule) and report paths, IDs and evidence. Do not declare the session complete for having run the scan.

## Invariants

- **Read-only scan:** `brain_evolution_scan` never writes to the vault.
- **Proposal is not decision:** every promotion needs the owner's explicit word; apply only via the existing proposal/apply flow with backup.
- **Partial stays in source:** thin evidence is a K2/K3 gap, not a document slot.
- **No double promotion:** the CONTROL evolution log prevents re-proposing what was already promoted or rejected.
- **NO_VERIFICADO:** anything the owner has not confirmed stays unverified, even inside a `ready` candidate.
