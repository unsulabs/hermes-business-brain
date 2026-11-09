---
name: ce-revisar-antecedentes
description: "New source, category/alias, correction, validity/permission change, resumed idea or response failure."
---

# ce-revisar-antecedentes

Read the [common contract](../ce-banco-transcripciones/references/contrato-comun.md) for states, permissions, context and availability.

- **Trigger:** new source, category/alias, correction, validity/permission change, resumed idea or response failure.
- **Inputs:** versioned event, eligible catalog universe, index with watermark, new analysis and canonical context. Read candidates with neighbors; expand to the full conversation when it affects meaning.
- **Outputs:** candidate relations with two cited endpoints, conflicts, dependencies/impacts, update proposals, sweep cursor and explicit list of pending/inaccessible.
- **Errors:** `INDEX_STALE`, `ANTECEDENT_UNAVAILABLE`, `SCOPE_MISMATCH`, `UNSUPPORTED_PREDICATE`, `SWEEP_INCOMPLETE`. A search with no results does not prove non-existence.
- **Gate:** a new category finds an old antecedent without sharing exact vocabulary in the designed trial; a conflict stays open if there is no authority to resolve it. Only claim a complete sweep when every entry of the snapshot has an outcome; new entries open a delta.

## Execution

Build the eligible universe by company, purpose, audience, sensitivity and current permissions before retrieving text. Include research, sources and secondary matters, not only D/X or titles. Search terms/aliases/contexts, read neighboring passages and expand to the complete original when meaning changes. FTS and literal matches are candidates, not semantic judgment nor proof of exhaustiveness.

Each relation requires verified original passages from both endpoints, direction, scope, time, predicate, reason and editorial state. Do not turn thematic coincidence into causality, nor a recent date into authority. A contradiction stays open until an authorized decision; resumed/refined items remain private proposals if the destination vocabulary does not admit them.

Resume the cursor by TR-ID and snapshot with outcome per entry; later entries form a delta. Do not claim a complete sweep while there are pending items. Propagate correction/revocation/rejection to registered dependents and mark unknowns: do not reintroduce rejected wording from summaries, web or circular citations. Use [ce-cambios](../ce-cambios/SKILL.md) only for editorial changes with a verified interface.
