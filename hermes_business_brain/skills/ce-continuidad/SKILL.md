---
name: ce-continuidad
description: "Resume and maintain a business vault daily in the face of conversations, clients, files, decisions, corrections and tasks, without losing sources nor re-interviewing the owner."
---

# ce-continuidad

New conversation/pending parts → [ce-banco-transcripciones](../ce-banco-transcripciones/SKILL.md). Resume the batch by job_id, attempt, version, snapshot/cursor and hashes; don't re-download nor re-analyze indiscriminately. Correction/category/permission → [ce-revisar-antecedentes](../ce-revisar-antecedentes/SKILL.md), invalidate the affected derivatives and keep the unaffected ones. Installation acceptance applies to installation/migration, not to every query or daily maintenance; recover only pertinent state and sources. A new original source doesn't imply editorial approval.

**First recover the real state:** if a vault already exists, resolve obsidian-router (brain_resolve_vault, per the [obsidian-router skill](../obsidian-router/SKILL.md)) and its instructions, then locate the pertinent state and sources without modifications. In installation/migration acceptance follow `guia/ACEPTACION_REAL_CODEX_INSTANCIA_EXISTENTE.md`. Don't consider SES or an earlier summary as a substitute for originals. Don't re-run create nor regenerate existing notes.

1. Reopen a specific instance confirming the business path and identity; run `brain_status` and `brain_validate_vault` to re-read the real state. If the default Python fails for a missing module, look for the already-verified interpreter or venv for that instance and repeat there. Record both results; only declare the capability unverified after that safe attempt.
2. Review the last file of `90_Sistema/Continuidad/` if it exists, the affected notes and their sources; don't assume an old log prevails.
3. Treat each new entry as a possible knowledge change: identify the episode, decisions, signals, exceptions and owner patterns; locate its original source and the notes that depend on it. Retrieve and compare before asking for information already on record. A provisional capture doesn't replace the work of incorporating it into the pertinent unit.
4. Distinguish correction of an earlier error, new fact, proposal and approved decision. If a canonical claim changes, use [ce-cambios](../ce-cambios/SKILL.md): keep version, date, reason, source and repercussions; correct all affected places without propagating a questioned interpretation. If a matter with its own identity appears, use `ce-arquitectura-conocimiento`, avoiding duplicates.
5. Execute a real task with the updated notes via `ce-consulta`; check that the previous version doesn't present as current and that another agent can follow the transferable instruction. Don't declare maintenance finished for saving a continuity entry.
6. Close after the work via the `continuidad` subcommand of the engine's `cerebro.py` CLI (upstream CLI subcommand, not exposed as a v2 plugin tool): `continuidad --vault ... --resumen "..." --siguiente "..." --revisado-por "..."`. Don't include secrets nor speculative accounts. Verify the modified files, `brain_status` and `brain_validate_vault` and return a natural continuation route.
**Output:** knowledge and work actually updated, impacts checked, paths/IDs and the next real need. If nothing changed, explain which concrete source or decision prevented it; don't fabricate progress.
