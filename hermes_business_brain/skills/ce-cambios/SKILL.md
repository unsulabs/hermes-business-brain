---
name: ce-cambios
description: "Manage changes to business knowledge without overwriting authority: price, process, decision or promise changes."
---

# ce-cambios

A correction, taxonomy or permission change on the active corpus activates [ce-revisar-antecedentes](../ce-revisar-antecedentes/SKILL.md): versioned event, old/new sources, dependents and uncertainty. Do not propagate the questioned text through summary/circular citation. Revalidate base SHA and current authorization before applying through a real interface; proposing does not change the original. Check the tool's `--help` and the note-type contract: the product has specific D/X review and relations flows, not a universal merge or integrator. Do not invent commands nor claim application by generating a proposal. Reuse write authorization within its scope without confusing it with editorial ratification.

1. Identify what was requested, which note/block is the authority, its version and validity, and which other pieces depend on it.
2. Retrieve the source of the change and who has the faculty to approve. An AI proposal does not equal a decision.
3. Save the candidate change in a local temporary file and record the proposal with `brain_propose` (the v2 plugin tool for the upstream `proponer` subcommand): `brain_propose --vault <vault> --id ID --motivo ... --archivo /ruta/candidato.md`; this **does not change the original** and preserves the previous SHA-256.
4. Compare contradictions, exceptions, particular contracts and dates; present a human-readable diff and the effect on derivatives.
5. Check explicit approver approval for the editorial change of authority or validity; if missing, request that concrete decision before applying. The technical authorization persisted to integrate sources or save proposals is reused within its scope without repeating permission, but it does not ratify claims nor authorize overwriting approved notes. There is no automatic merge engine in this version, so do not declare a modification current because its proposal was saved.
6. When applying through a verified interface, preserve history/versions and re-validate; do not overwrite for green tests.
**Output:** proposal, sources, impacts, pending approval and scope limits.
