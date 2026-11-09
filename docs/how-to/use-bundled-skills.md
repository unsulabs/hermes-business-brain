# How to use the bundled skills

**Use this when**: you want the plugin's *methodology* — not just its tools.
The tools (`brain_*`) execute operations; the bundled skills tell the agent
*how* to think about a business vault: when to capture vs. approve, how to
check sources, how to run transcripts through custody, and when to mark
something `NO VERIFICADO`.

## What ships with the plugin

Every `hermes_business_brain/skills/<name>/SKILL.md` folder in the plugin is
registered at load time by the plugin's `__init__.py`
(`ctx.register_skill(...)`), so the skills surface in Hermes as **plugin
skills** under the `hermes-business-brain:` namespace — the same convention
as the tools.

There are 20 bundled skill folders, grouped as:

| Group | Skills (19 `ce-*`) | When the family activates |
| --- | --- | --- |
| Installation & continuity | `ce-instalacion`, `ce-continuidad` | First set-up of a vault; resuming daily work on an existing one |
| Consultation | `ce-consulta`, `ce-evaluar-recuperacion`, `ce-evaluar-recurso`, `ce-revisar-antecedentes` | Queries, drafts, decisions, pilots, fidelity failures, new sources |
| Knowledge architecture | `ce-arquitectura-conocimiento`, `ce-taxonomia-conocimiento`, `ce-modelo-relaciones`, `ce-calidad-repositorio`, `ce-cambios`, `ce-documentacion`, `ce-investigacion`, `ce-descubrimiento` | Designing notes before drafting, taxonomy, relations, research, D/X documents, corrections |
| Transcripts | `ce-banco-transcripciones`, `ce-analizar-transcripcion`, `ce-extraer-meetgeek` | New conversations/transcripts (custody first), analysis, MeetGeek extraction |
| Company development | `ce-desarrollo-empresa` | Orchestrating the whole second-brain lifecycle |

…plus one companion:

- `obsidian-router` — resolves the private vault through explicit local
  registration and native Obsidian identity *before any access*. The
  `ce-instalacion`, `ce-consulta` and `ce-continuidad` skills all route
  through it (`brain_register_vault` / `brain_resolve_vault`).

The plugin's "20 bundled skills" figure counts the business-brain set: the 19
`ce-*` plus `obsidian-router`. (A root-level `skills/documentation-writer`
folder exists in the working tree but is an `npx skills add` artifact — not
bundled, never registered.)

## How they surface and activate

1. **Automatic activation (recommended).** Hermes loads a skill when your
   task matches its description. For example:
   - "install the Business Brain for the first time" →
     [`ce-instalacion`](../../hermes_business_brain/skills/ce-instalacion/SKILL.md)
     (its description says: *activate when a person asks to install, start,
     configure or continue the first installation*);
   - "answer a question from the company vault" →
     [`ce-consulta`](../../hermes_business_brain/skills/ce-consulta/SKILL.md)
     (*queries, drafting, commercial preparation, execution, decisions,
     contracts, prices, projects or history*);
   - "here is a transcript of the meeting" →
     [`ce-banco-transcripciones`](../../hermes_business_brain/skills/ce-banco-transcripciones/SKILL.md)
     (*preserve and drive the complete cycle of a new conversation/transcript
     … Custody is the first step*).
2. **Explicit loading.** List them and open one:

   ```text
   skills_list
   skill_view(name='hermes-business-brain:ce-consulta')
   ```

   The raw files also live in the plugin at
   `hermes_business_brain/skills/<name>/SKILL.md`.

Load them *before* running business-brain tools for a task — the skills
constrain how the tools are used (for example `ce-consulta` insists on
resolving the vault before any read inside it).

## What they are — and their honest limits

**What they are:** workflow guidance with hard invariants. Examples baked in:

- Never create or reinstall a vault that exists
  ([`ce-instalacion`](../../hermes_business_brain/skills/ce-instalacion/SKILL.md),
  [`ce-continuidad`](../../hermes_business_brain/skills/ce-continuidad/SKILL.md)).
- Captures are drafts; `aprobado: false` until editorial process says
  otherwise; corrections create versions, never replacements.
- Anything unproven is reported `NO VERIFICADO`, and "an empty result doesn't
  prove absence" ([`ce-consulta`](../../hermes_business_brain/skills/ce-consulta/SKILL.md)).

**Honest limits:**

- **Skills are not tools.** The plugin exposes exactly 18 `brain_*` tools (see
  the [README](../../README.md) and [`tools.md`](../reference/tools.md)). Five
  positions are now first-class tools: `ficha` →
  `brain_card`, `proponer` → `brain_propose`, `documento` →
  `brain_document`, `plan-conocimiento` → `brain_knowledge_plan`, and
  `aplicar-dx` → `brain_dx_apply`. Remaining CLI subcommands
  (e.g. `continuidad`, `buscar`, `autoridad`, `fuente`, `publicar-mapa`) are **not
  plugin tools and the plugin ships no CLI launcher** — a skill references
  them only as "upstream CLI subcommand, not exposed as a v2 plugin tool",
  and they run through the engine API only where a skill's contracts and
  tests actually cover them. See [`cli-reference.md`](../reference/cli-reference.md)
  for the full split.
- **Skills are read-only guidance.** They don't change engine behaviour. Their
  bodies are in English; JSON keys inside engine outputs are the product's
  protocol keys.
- **The set is a starting map, not a flowchart.** Several skills route to each
  other by *topic* (correction → `ce-revisar-antecedentes`, knowledge change
  → `ce-cambios`, new matter → `ce-arquitectura-conocimiento`). The
  descriptions quoted above are the activation triggers; when in doubt about
  which one applies, open the skill each candidate names.

## Verification

The folder inventory, registration mechanism, and the tool split above were
verified against this repository (`__init__.py`, `schemas.py`,
`hermes_business_brain/skills/`) and Hermes' plugin doctor; see
[`../../_verify/tool-layer.md`](../../_verify/tool-layer.md) and
[`../../_verify/skills-docs-v2.md`](../../_verify/skills-docs-v2.md).
