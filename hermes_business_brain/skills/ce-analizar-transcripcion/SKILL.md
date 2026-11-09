---
name: ce-analizar-transcripcion
description: "Preserved version to analyze; correction or invalidation of an earlier analysis."
---

# ce-analizar-transcripcion

Read the [common contract](../ce-banco-transcripciones/references/contrato-comun.md) for states, permissions, context and availability.

- **Trigger:** preserved version to analyze, correction or invalidation of an earlier analysis.
- **Inputs:** original and hash, offset map, all parts, versioned taxonomy, canonical context with hashes and access policies. A partial version may be analyzed provisionally, without declaring it complete.
- **Outputs:** analysis of each core, attributed claims, matter→passage→destination matrix, mechanical/semantic coverage, whole-conversation reconciliation, immutable run with dependencies. Differentiate decisions, ideas, reasons, exceptions and doubts; absent fields stay absent.
- **Errors:** `SOURCE_CHANGED`, `OFFSET_INVALID`, `COVERAGE_GAP`, `UNSUPPORTED_ENCODING`, `ANALYSIS_INCOMPLETE`, `CONTEXT_STALE`. Don't resolve uncertain attribution by inventing identity.
- **Gate:** partition reconstructs exact bytes; each core examined; all material matters have a destination or reasoned preservation in source; an independent judge checks a sample and passages with cross-corrections. 100% numeric coverage doesn't prove comprehension by itself.

## Execution

Interpretation is the work of the reading agent: no title, regex, word list or preassigned category attests semantic analysis. Validators only check structure, hashes and mechanical coverage. Examine each core with neighbors, identify late changes and return to the whole before reconciling. If there is a gap, keep the uncertainty. Record explicit/paraphrase/inference, attributed voice, mechanism, reasons, alternatives and exceptions; a commercial synthesis doesn't replace secondary matters.

Verify each citation by opening the original bytes in this execution: TR-ID, version, SHA-256, UTF-8 byte offsets [start,end), extract hash; check character boundaries. Don't cite a card as if the original was read. A run requires text_sha256, segmenter_version, analyzer_version, taxonomy_version, canonical_context_hashes and permission_snapshot. A change in any of them invalidates what's affected; a new run preserves history and repeats global reconciliation.

Use [taxonomy](../ce-taxonomia-conocimiento/SKILL.md) for identity and [antecedentes](../ce-revisar-antecedentes/SKILL.md) for connections. Then architecture: one logical card (ficha) per transcript, owner notes per matter when justified. Permission to analyze doesn't authorize integrating nor ratifying.

If the owner already authorized integrating sensitive sources into their private vault, keep the original sensitivity and apply the [private destination profile](../ce-banco-transcripciones/references/destino-privado.md): explicit path/company/audience/TR, sealed policy and live permissions local_analysis/internal_query. Don't exclude them for being confidential nor reclassify them to internal; don't extend that authorization to other vaults or purposes. Already-linked generic Bases and manuals are kept; cards, full views and maps with sensitive sources propagate the maximum classification.
