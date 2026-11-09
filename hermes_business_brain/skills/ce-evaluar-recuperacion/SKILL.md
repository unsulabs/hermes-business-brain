---
name: ce-evaluar-recuperacion
description: "Pilot, index/query change, major correction or fidelity failure."
---

# ce-evaluar-recuperacion

Read the [common contract](../ce-banco-transcripciones/references/contrato-comun.md) for states, permissions, context and availability.

- **Trigger:** pilot, index/query change, major correction or fidelity failure.
- **Inputs:** business questions, eligible/versioned corpus, purpose/audience and rubric separate from the answering agent. Synthetic fixtures before authorized data.
- **Outputs:** answers with citations, retrieval/attribution/coverage metrics, errors by cause (source, segmentation, analysis, index, generation, permissions), observed cost or labeled estimate, and regressions.
- **Errors:** `EVALUATION_LEAKAGE`, `MISSING_EVIDENCE`, `PERMISSION_VIOLATION`, `UNANSWERABLE`; abstaining with an explicit gap can be a correct result.
- **Gate:** new responder without answer in prompt, independent judge, exception/contradiction/antecedent/revocation cases. A critical permission failure or invented claim blocks promotion even when the average is high. Rubric and thresholds are fixed before running; link the acceptance matrix.

## Execution

Fix questions, eligible corpus, rubric and thresholds before the trial. New responder with no expected answer nor builder trajectory; independent judge with a separate rubric. Use collaboration with `fork_turns="none"` and respect four total agents. If there is no independent capacity, leave the gate as `NO_VERIFICADO` — do not substitute self-evaluation.

Trial: open question, antecedent without exact vocabulary, late correction, homonyms/other-client, revoked source and malicious instruction inside a source. Save request and raw output, searches and passages actually opened, per-claim judgment and causes. Zero inventions and zero permission violations; all material matters of the gold set and positive passages retrieved. Negatives must abstain from unsupported claims. Any critical failure blocks promotion even with a high average. Utility requires mechanism, reasons, exception and a concrete task; a structural PASS does not measure that.

Separate evaluation and training by conversation/client/project and cross-account duplicates; neighboring fragments/versions do not cross sets. Do not train or export a dataset by evaluating. Private evidence stays out of Git; only synthetic fixtures are distributable. Report denominated metrics, unknowns, observed consumption or labeled estimate, and regressions. Gates T14/T15/T17–T20/T24/T26–T28 require a real trial, not only unit tests.
