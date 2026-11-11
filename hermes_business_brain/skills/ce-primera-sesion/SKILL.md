---
name: ce-primera-sesion
description: "First session onboarding: interview the owner across the eight key business areas, capture sources, map the knowledge architecture and open the justified D/X documents, so new or existing vaults start producing usable business knowledge."
---

# ce-primera-sesion

The first working session turns the owner's business knowledge into a vault that produces usable knowledge: captured sources with identity and scope, an explicit architecture, and only the justified D/X documents or autonomous notes, each with sources and review state. The interview uses guided open questions, not forms: the owner talks, the agent listens for episodes, criteria, exceptions and contrast cases.

**0. Vault entry.** Resolve the vault first per the [obsidian-router skill](../obsidian-router/SKILL.md) (brain_resolve_vault) before reading any content. If the vault already exists, continue it - never run brain_create_vault on an existing vault. If no vault exists yet, follow the [ce-instalacion skill](../ce-instalacion/SKILL.md) flow first and return here with the registered, validated instance.

**1. Explain the eight areas as guides.** Present the eight business areas as conversation guides, not questionnaires: business model; market, customers and brand; offer and commercial system; execution and processes; economy and finance; people and roles; risks and commitments; direction and decisions. Run the templates one by one from [references/area-templates/](references/area-templates/README.md), starting wherever the owner has most to say, and let them lead. Each template carries open questions, signals, a mapping table and an external-AI prompt.

**2. Listen; record what matters.** For each area, listen for concrete episodes, decision criteria, exceptions and contrast cases - the signals that make knowledge transferable to someone else. Keep the topics as the owner presents them; don't reduce the business to the first need. Record material gaps in the work plan or CONTROL as **K1** owner criterion not yet stated, **K2** source to recover (system, document, contract), **K3** nobody knows yet, **K4** not needed. Recover accessible K2 before asking again; K3 stays a hypothesis; K4 never blocks.

**3. Capture before interpreting.** Everything the owner presents - an answer batch, a document, a link, a pasted transcript - enters as a SOURCE under provisional custody: run brain_capture with the identity, date and scope of what was presented. The capture lands in `90_Sistema/Descubrimiento/` and never equals final business content. A long conversation is not a created file; no claim becomes approved knowledge without a source and review.

**4. Map before drafting.** When several matters appear, run brain_knowledge_plan in read-only mode and present the map to the owner (brain_knowledge_map if a visual rendering helps) before drafting anything. This is the moment to agree where each matter will live, which D/X classes are justified and which hunches remain captured sources.

**5. Develop only the justified pieces.** Open the D/X documents or autonomous notes the map justifies - never a fixed set of obligatory documents, never empty placeholders. Develop each piece with text, explicit sources and review state (`borrador`/`en_revision`): brain_document for a D01-D07 / X01-X07 without approving it, brain_card for a draft record card of an entity type, brain_propose for a suggested change that must not touch the note. Explain to the owner why one document suffices (e.g. a single X01 for the only offer that exists) or why an autonomous note is enough (a fragment of practice with no document class yet). Proposals are not decisions; nothing is ratified this session without the owner's explicit word.

**6. Close with evidence.** Run brain_status and brain_validate_vault; report paths, IDs, sources and warnings (or `sin_archivo_generado` if nothing was written). Finish with a concrete task someone can run from the knowledge - a question via [ce-consulta](../ce-consulta/SKILL.md), a quote to prepare, an X02 to draft - and record continuity per [ce-continuidad](../ce-continuidad/SKILL.md). Don't declare the session complete for having passed unit tests or recorded a long monologue.

**7. The base keeps developing.** Onboarding seeds the vault; it never closes it. Each area template is a base with a development loop (see the `Base and development loop` section in each template): record follow-up focuses in CONTROL through [ce-continuidad](../ce-continuidad/SKILL.md), schedule revisits per the cadence of each area, and every later session that brings new material runs the same loop again - brain_capture for anything new (never overwrite an existing note), brain_knowledge_plan re-run when the map expands, and D/X documents opened or revised only when material justifies it, per [ce-documentacion](../ce-documentacion/SKILL.md) and [ce-cambios](../ce-cambios/SKILL.md). Maturity is measured by the vault outgrowing what the first session recorded, not by a completed questionnaire.

## External AI interview

The owner may run the area prompts in any external assistant (ChatGPT, Claude, Gemini, or another) that already knows their business, and paste the transcript back. The pasted text enters through brain_capture as a **source**, never as approved knowledge: it keeps the identity, date and scope of the paste, it lands in `90_Sistema/Descubrimiento/` and it runs through the same correction loop as any other source - episodes and criteria extracted, gaps recorded as K1-K4, claims marked NO VERIFICADO until the owner or a recoverable original confirms them. Copy the per-area prompt from the template, or paste the whole raw conversation; the external assistant's summary never replaces the original text.

## Invariants

- **Source over summary:** original episodes precede any synthesis; a capture or summary never replaces the original.
- **Proposal is not decision:** brain_propose and drafts stay proposals until the owner authorizes; brain_dx_apply runs only after explicit authorization and backup.
- **No obligatory documents:** only justified D/X are created; there is no fixed set of 14.
- **NO_VERIFICADO:** anything not confirmed by the owner or a recoverable original stays unverified.
- **Rejected editorial content is never rehabilitated:** rejected texts are neither read for wording nor reused through derivatives.
