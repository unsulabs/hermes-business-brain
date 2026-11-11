# How to keep the vault evolving

The onboarding templates seed the vault; daily use keeps feeding it; the
evolution scan turns accumulated material into mature knowledge. This is the
loop, end to end.

## 1. Daily use feeds the sources

Every new piece of commercial reality is a potential source: a quote, a
payment, a supplier message, a decision, a closed event. Capture it with
`brain_capture` (identity, date, scope) so it lands in
`90_Sistema/Descubrimiento/` with provenance. Nothing the owner says or sends
is lost to the chat.

## 2. Scan periodically

Run `brain_evolution_scan` on the resolved vault (see the
[ce-evolucion skill](../../hermes_business_brain/skills/ce-evolucion/SKILL.md)):

- in any session with new material,
- before closing a working session,
- on the cadence of each area.

The scan is read-only; it returns `candidates` (promotion rules that fired,
with evidence paths and `ready`/`partial` state) and `due_visits`
(areas whose revisit is due).

## 3. Approve promotions, never auto-apply

A `ready` candidate is a proposal. Draft the proposed document with
`brain_document` in `en_revision` state citing the evidence files, present it
to the owner, and apply changes only through `brain_propose` plus
`brain_dx_apply` after explicit authorization and a backup. `partial`
candidates stay in source until more evidence arrives - a single anecdote
never becomes a document.

## 4. Revisit areas on cadence

When a revisit is due, run the matching round-2 prompts from the
[area templates](../hermes_business_brain/skills/ce-primera-sesion/references/area-templates/README.md)
through the continuity skill, and capture what the owner says. The documents
then grow by revision: new sources refine D01-D07 / X01-X07, and the vault
outgrows the information it started with.

## 5. Record and improve

Append promotions to the CONTROL evolution log (date, rule id, target,
evidence) so later scans do not re-propose them. If a rule fires too eagerly
or never, improve `reglas_evolucion.json` in the repository - the rulebook is
itself a versioned file that ships with the plugin.
