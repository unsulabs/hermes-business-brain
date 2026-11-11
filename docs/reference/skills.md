# Reference — Bundled Skills (hermes-business-brain v2)

The plugin ships 21 skills under `hermes_business_brain/skills/`, each a
directory with a `SKILL.md`. At load time `register(ctx)` registers every
such directory as a plugin skill under the qualified name
`hermes-business-brain:<name>` (the registration is tolerant: missing or
malformed entries are skipped, never fatal). The description column below
quotes each skill's YAML frontmatter `description` verbatim; "family" is an
operational grouping used in this reference, and "activates when" comes from
the activation language the frontmatter description itself carries.

## Master table

| Qualified name | Description (frontmatter, verbatim) | Family | Activates when |
| --- | --- | --- | --- |
| `hermes-business-brain:ce-instalacion` | "Install and configure the Business Brain for the first time with the Hermes agent. Activate when a person asks to install, start, configure or continue the first installation of Obsidian/business." | Installation & bootstrap | First-time install, start, configuration, or continuation of the first Obsidian/business installation. |
| `hermes-business-brain:ce-desarrollo-empresa` | "Orchestrate the installation, construction, daily use and maintenance of the second brain of a new or existing business, venture or self-employment activity. Activate when asked to create, continue or complete the vault, transfer criteria to people/agents or use the knowledge for real work." | Installation & daily operation | Asked to create, continue or complete the vault; transfer criteria; use vault knowledge for real work. |
| `hermes-business-brain:ce-descubrimiento` | "Listen to the free braindump of a business, venture or self-employment activity, recover its sources and turn the owner's episodes and patterns into documents and operational work. Activate when building or expanding a vault, even if it already has notes." | Discovery | Building or expanding a vault from the owner's free-form talk, even with existing notes. |
| `hermes-business-brain:ce-consulta` | "Use the business brain to answer and perform concrete work with criteria, sources, time and permissions. Activate for queries, drafting, commercial preparation, execution, decisions, contracts, prices, projects or history." | Query & task execution | Queries, drafting, commercial preparation, execution, decisions, contracts, prices, projects, or history questions. |
| `hermes-business-brain:ce-continuidad` | "Resume and maintain a business vault daily in the face of conversations, clients, files, decisions, corrections and tasks, without losing sources nor re-interviewing the owner." | Continuity | Daily resumption and upkeep of a business vault. |
| `hermes-business-brain:ce-banco-transcripciones` | "Preserve and drive the complete cycle of a new conversation/transcript or continuation by parts, up to authorized integration; don't ingest ordinary documents for their length." | Transcripts (custody & pipeline) | A conversation/transcript arrives for preservation — new, by parts, or continued; not ordinary documents just because they are long. |
| `hermes-business-brain:ce-analizar-transcripcion` | "Preserved version to analyze; correction or invalidation of an earlier analysis." | Transcripts (analysis) | A preserved transcript version needs analysis, or an earlier analysis must be corrected or invalidated. |
| `hermes-business-brain:ce-revisar-antecedentes` | "New source, category/alias, correction, validity/permission change, resumed idea or response failure." | Transcripts (antecedents) | New source, category/alias change, correction, validity/permission change, resumed idea, or a response failure. |
| `hermes-business-brain:ce-evaluar-recuperacion` | "Pilot, index/query change, major correction or fidelity failure." | Transcripts (retrieval evaluation) | Pilot runs, index/query changes, major corrections, or fidelity failures. |
| `hermes-business-brain:ce-extraer-meetgeek` | "Authorized inventory/extraction request on an identified account." | Transcripts (ingestion) | An authorized inventory/extraction request on an identified MeetGeek account. |
| `hermes-business-brain:ce-taxonomia-conocimiento` | "Uncovered matter, doubtful alias, category/fusion/division or requested criterion change." | Taxonomy | Uncovered matter, doubtful alias, category fusion/division, or a requested criterion change. |
| `hermes-business-brain:ce-modelo-relaciones` | "Differentiate entity types and build verifiable relations in Obsidian: offers, products, services, clients, meetings, processes, projects and sources." | Relations | Differentiating entity types and building verifiable typed relations. |
| `hermes-business-brain:ce-cambios` | "Manage changes to business knowledge without overwriting authority: price, process, decision or promise changes." | Knowledge change management | Price, process, decision or promise changes — anything that touches authority. |
| `hermes-business-brain:ce-documentacion` | "Develop or improve business documents D01–D07/X01–X07 with research, expert judgment and utility tests, not generic templates." | Documentation | Developing or improving D01–D07 / X01–X07 business documents. |
| `hermes-business-brain:ce-arquitectura-conocimiento` | "Mandatory before drafting D/X or handling multi-matter narratives: design autonomous notes, reuse existing ones, tags, sources and relations before writing." | Knowledge architecture | Mandatory before drafting D/X documents or handling multi-matter narratives. |
| `hermes-business-brain:ce-investigacion` | "Research market needs, competition, clients and methodologies for a business without inventing data or passing hypotheses off as facts." | Research | Market, competition, client or methodology research. |
| `hermes-business-brain:ce-evaluar-recurso` | "Analyze plugins, repositories, tutorials, templates and external frameworks before incorporating them into the Business Brain." | External resource evaluation | Evaluating plugins, repositories, tutorials, templates or frameworks before incorporation. |
| `hermes-business-brain:ce-calidad-repositorio` | "Audit, improve or evolve the master repository's code with tests, migrations and preservation of existing functionality." | Repository quality & ops | Auditing, improving or evolving the master repository's code. |
| `hermes-business-brain:ce-evolucion` | "Scan a business vault for knowledge ready to evolve: promotion candidates from captured sources, areas whose revisit cadence is due; proposals are presented to the owner, never applied automatically." | Evolution | Running the evolution scan and confirming promotions so the vault matures with use. |
| `hermes-business-brain:obsidian-router` | "Resolve this product's private vault through explicit local registration and native Obsidian identity before access." | Vault routing & identity | Before ANY access to a vault: resolution first, registration on authorized new instances. |

## Family index

- **Installation & bootstrap**: `ce-instalacion`, `ce-desarrollo-empresa`
- **Discovery**: `ce-descubrimiento`
- **Query & task execution**: `ce-consulta`
- **Continuity**: `ce-continuidad`
- **Transcripts**: `ce-banco-transcripciones`, `ce-analizar-transcripcion`,
  `ce-revisar-antecedentes`, `ce-evaluar-recuperacion`, `ce-extraer-meetgeek`
- **Taxonomy**: `ce-taxonomia-conocimiento`
- **Relations**: `ce-modelo-relaciones`
- **Knowledge change & documentation**: `ce-cambios`, `ce-documentacion`,
  `ce-arquitectura-conocimiento`
- **Research & resource evaluation**: `ce-investigacion`, `ce-evaluar-recurso`
- **Repository quality & ops**: `ce-calidad-repositorio`
- **Evolution**: `ce-evolucion`
- **Routing**: `obsidian-router`

## How skills relate to tools

Skills never call the engine directly; they instruct the agent to invoke the
`brain_*` tools with the arguments documented in
[`tools.md`](tools.md) — for example `ce-instalacion` drives
`brain_create_vault`, `brain_validate_vault`, `brain_register_vault` and
`brain_resolve_vault` in sequence, and `obsidian-router` mandates
`brain_resolve_vault` before any vault read. Where a needed CLI
subcommand is not exposed as a v2 plugin tool, skills reference it explicitly
with the label "upstream CLI subcommand, not exposed as a v2 plugin tool" and
never invent a plugin launcher path — see
[`cli-reference.md`](cli-reference.md) for that split.

## Note on a non-bundled directory

The working tree of this repository also has `skills/documentation-writer`,
but it is **not** part of the product bundle: it is an `npx skills add`
artifact, `.gitignore` excludes the root `skills/` directory, and
`skills-lock.json` records it as installed from the third-party
`github/awesome-copilot` collection. Only the 21 skills above ship with the
plugin (bundled under `hermes_business_brain/skills/`).
