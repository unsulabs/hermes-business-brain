---
name: ce-modelo-relaciones
description: "Differentiate entity types and build verifiable relations in Obsidian: offers, products, services, clients, meetings, processes, projects and sources."
---

# ce-modelo-relaciones

**0. Architecture first:** activate `ce-arquitectura-conocimiento`. Do not create a note per mention. Decide what has its own identity and lifecycle, what exists, what stays in the source and what is a link. Validate with the product's knowledge-planning flow read-only via `brain_knowledge_plan` (the v2 plugin tool wrapping the upstream `plan-conocimiento` subcommand); tags are for navigation, edges with source/scope for modeling relations -- do not confuse the two.

1. Consult `modelo/tipos_entidad.json`, the D/X catalog and the vNext-0.9 handover contract. The registry is a candidate: justify separations by identity, changes, history, permissions, reuse and query.
2. Before creating, check whether the entity already exists by ID, authoritative system, alias and context. A mention does NOT force a note.
3. Verify distinctions: product/offer; consulting/tool; project/case/session/meeting; client-account/person/organization; offer/proposal/agreement; research/result.
4. If a unit needs its own file, create it as a draft card with `brain_card` (the v2 plugin tool for the upstream `ficha` subcommand): `brain_card --vault <vault> --tipo ... --titulo ...`. Link registered sources.
5. Register typed relations with evidence, directionality and scope; do not use generic `related` as authority. Avoid duplicating price, financial state or contract across several notes.
6. Run `brain_validate_vault` after changes and inspect the graph (Obsidian Graph view); the Graph view shows navigation, not truth. Test one real question and one negative.
**Output:** justified entities, explicit relations, sources, and presence/absence of ambiguous cases.
