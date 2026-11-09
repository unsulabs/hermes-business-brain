---
name: ce-arquitectura-conocimiento
description: "Mandatory before drafting D/X or handling multi-matter narratives: design autonomous notes, reuse existing ones, tags, sources and relations before writing."
---

# ce-arquitectura-conocimiento

New transcripts pass first through [ce-banco-transcripciones](../ce-banco-transcripciones/SKILL.md) and [ce-analizar-transcripcion](../ce-analizar-transcripcion/SKILL.md). Use a matrix of all cores/matters and global reconciliation, not a summary as original. One logical card (ficha) per TR-ID with versions; owner notes per justified matter. Plans of up to 30 matters/30 units and 90,000 bytes: split proposals into batches with a parent manifest and global IDs, without truncating or duplicating the source. An accepted architecture doesn't ratify edges nor authorize overwriting approved content. Don't load the whole vault for a spot correction.

## Proactive triggers

Activate it WITHOUT the user asking when:
- An interview, account or transcript contains two or more matters with a life of their own (strategy, offering, process, decision, case, research).
- Creating/reviewing D01–D07/X01–X07 is requested and part of the knowledge deserves other specialized notes.
- A generic draft mixing prices, processes, strategy and cases in a single section was produced.

For a small correction or literal query of one concrete note, no need to re-plan the whole business.

## Mandatory sequence

1. Re-read admissible original sources and the vault's real indexes; don't use rejected editorial notes.
2. Extract matters in the expert's language, why they matter and which business question they serve. Keep the reasons for their decisions.
3. For each matter propose: **reuse**, **revise**, **create** or **don't create** (if it only deserves staying in the source).
4. Justify autonomy by authority, currency, responsible party, independent changes, history or consultation. A mention doesn't force a note.
5. A matter has one canonical owner; other documents may link it and explain its implications without duplicating its changing data.
6. Choose thematic tags and typed links with source, scope and direction; tags and wiki links are not authority.
7. Prepare the private JSON following `docs/ARQUITECTURA_CONOCIMIENTO_ANTES_DE_REDACTAR.md` and `ejemplos/planes_conocimiento/plan_empresa_sintetica.json`. Run `brain_knowledge_plan --vault PATH --archivo EXTERNAL_PLAN` (the v2 plugin tool wrapping the upstream `plan-conocimiento` subcommand) in read-only mode.
8. Leave the distribution map legible and traceable for the business owner. If the commission already authorizes building or correcting the vault and the distribution is grounded in sources, continue drafting; don't turn every map into a new permission request. Ask only when two locations materially change authority or use and the criterion isn't in the sources.
9. With the architecture reviewed, develop substantive notes and states/sources. For an entity use `brain_card` (the v2 plugin tool for the upstream `ficha` subcommand: `brain_card --archivo PATH --etiquetas TAG`) with complete Markdown and no placeholders; for D/X use `brain_document` only when it doesn't exist yet, and the upstream `previsualizar-dx` subcommand (upstream CLI subcommand, not exposed as a v2 plugin tool) for revisions. Register edges only after IDs and sources.
10. Test a task that depends on the created notes and a currency/attribution countercheck, not just search matches. Review the output with `ce-consulta` before considering the distribution useful.
11. To make already existing connections visible, run `brain_knowledge_map` without writing. Present the derived Markdown links and Canvas and their states. Only after specific authorization, SHA/confirmation and backup outside the vault, `publicar-mapa` (upstream CLI subcommand, not exposed as a v2 plugin tool). Don't edit the notes to achieve the graph.

**Output:** a minimal map of matters and owners, current/new/not-created notes, reasons, tags, links and sources. Fails B18 if the Hermes agent didn't do this unprompted in multi-matter material, even if the final D01 is well written. The CLI doesn't replace expert criteria.
