# hermes-business-brain

Offline Obsidian "business-brain" toolkit: 18 network-free Hermes tools with a native English engine to create, validate and query private knowledge vaults.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](docs/how-to/install.md)
[![Docs: English](https://img.shields.io/badge/docs-English-blue.svg)](docs/)

`hermes-business-brain` is an offline Python toolkit for Obsidian "business
brain" vaults, shipped as a Hermes plugin: **18 local tools** backed by a
**native English engine** (`hermes_business_brain/engine/`). Every tool runs
the engine **in-process** against **user-provided paths only**. The plugin
is privacy-first by construction:

- **No network.** The plugin never calls out; tool handlers run inside the Hermes
  process. The engine invokes the system `git` binary only for vault/transfer
  probes and product export (argv-only command lists, no shell, no user input
  executed), and nothing else.
- **No real business data shipped.** Every template, schema and piece of demo content
  bundled here is synthetic by design.
- **No hardcoded absolute user paths.** Every tool takes vault/bank/file paths as
  arguments. (The vault-registry tools work with the user's local selector registry
  (`~/.codex/obsidian/vaults.json`, legacy Codex-compatible format) and the native
  Obsidian registry files; both paths can be overridden.)

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Tools (18)](#tools-18)
- [Bundled skills (19)](#bundled-skills-19)
- [Documentation](#documentation)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

## Background

Obsidian users often keep a "business brain": a local vault of company knowledge —
entities, sources, decisions, transcripts, typed relations. This plugin brings that
workflow to Hermes as plain tools an agent can call, with one hard rule: **nothing
leaves your machine.** No API calls, no telemetry, no cloud — a business
decision stays a local file until *you* move it. The engine's only out-of-process
call is the system `git` CLI (argv-only, no shell, no network) for bank/transfer
location probes and product export.

For how the pieces fit together, see
[docs/explanation/architecture.md](docs/explanation/architecture.md); the
implementation evidence lives in the `_verify/` files.

## Install

Two supported ways (full walkthrough with real doctor output:
[docs/how-to/install.md](docs/how-to/install.md)):

```bash
# (a) From the catalog (once published):
hermes plugins install unsulabs/hermes-business-brain --enable

# (b) Local / development: symlink the repo into the plugin directory, then enable:
mkdir -p ~/.hermes/plugins
ln -s /path/to/hermes-business-brain-unsulabs ~/.hermes/plugins/hermes-business-brain
hermes plugins enable hermes-business-brain
```

> **Note (verified 2026-11-06):** the catalog entry does not exist yet — use path (b)
> until the plugin is published.

`hermes plugins install` with a local filesystem path is **not** supported — the CLI
parses the argument as `owner/repo`. After enabling, **restart Hermes** so the tools and
skills load. To confirm the installation (both read-only):

```bash
hermes plugins list                          # plugin should show status: enabled
hermes plugins doctor hermes-business-brain --ci   # manifest + registration gate
```

From inside a checkout, the same gate runs without the plugin being enabled:
`hermes plugins doctor . --ci`.

The manifest declares two Python dependencies, `PyYAML==6.0.3` and
`jsonschema>=4.23,<5`, installed by Hermes' package manager on enablement (consent is
requested). The engine works on Python 3.11+ (up to 3.14; examples verified on 3.14).

## Usage

Ask Hermes to run the tools; each step names the tool arguments so you can verify them
against the [reference](docs/reference/tools.md). The full guided walkthrough is the
[quickstart tutorial](docs/tutorials/quickstart-vault.md) (about 10 minutes).

**1. Preflight** — `brain_doctor` checks Python, dependencies and Obsidian, read-only,
installing nothing.

**2. Create a vault** — `brain_create_vault` with three arguments (`id`, `name`,
`dest`). It never overwrites: if the destination already exists, the tool fails —
that is a safety feature.

| Argument | Value |
| --- | --- |
| `id` | `EMPRESA-001` (2–64 chars, letters/digits/dash/underscore) |
| `name` | `Acme Consultores` |
| `dest` | `~/empresas/acme-consultores` (must **not** exist) |

**3. Validate** — `brain_validate_vault` checks structural integrity (ids, wikilinks,
transfers, frontmatter) — never business truth.

**4. Inspect** — `brain_status` prints a structural summary: company id/name, note
counts by type, editorial state, templates.

**5. Query** — `brain_query` returns candidate note blocks matched by literal text,
optionally filtered by `tema` / `ambito` / `fecha`, with `limite` candidates (default
10). Use `orientar: true` to order results by the terms of a natural request. A fresh
vault answers "no candidates yet" — that is designed behaviour, not a bug.

Continue with an existing vault: [docs/how-to/continue-existing-vault.md](docs/how-to/continue-existing-vault.md).
Capture transcripts and drive the custody pipeline: [docs/how-to/work-transcripts.md](docs/how-to/work-transcripts.md).

## Tools (18)

| Tool | CLI backing | Purpose |
| --- | --- | --- |
| `brain_doctor` | `cerebro.py doctor` | Read-only environment preflight (Python, deps, Obsidian). |
| `brain_create_vault` | `cerebro.py crear` | Create a new empty vault from the bundled template; never overwrites. |
| `brain_validate_vault` | `validar_boveda.py` | Structural integrity check (ids, links, transfers) — not business truth. |
| `brain_status` | `cerebro.py estado` | Structural company summary (counts, editorial state, templates). |
| `brain_register_vault` | `register_vault` | `registrar_boveda_obsidian.py` | Register an open vault in the local selector registry (legacy Codex-compatible `~/.codex` format; needs Obsidian's native id). |
| `brain_resolve_vault` | `resolve_vault` | `resolver_boveda_obsidian.py` | Resolve the vault registered for an agent project/selector. |
| `brain_query` | `cerebro.py consulta-contextual` | Candidate blocks by literal text + source/date/scope filters; no semantic generation. |
| `brain_capture` | `cerebro.py capturar` | Save preliminary findings as a draft note (not approved knowledge). |
| `brain_knowledge_map` | `cerebro.py mapa-conocimiento` | Knowledge-map preview (Markdown/Canvas); publish only with SHA/confirmation/backup. |
| `brain_relations` | `cerebro.py relaciones` | Query typed relations and their real state. |
| `brain_references` | `plugin_references.py` (wrap of `referencias_externas.py`) | Local versioned external-reference registry: metadata only, no content import, no network. |
| `brain_naming` | `nombres_legibles.py` | Plan (default) or apply readable filename changes from a spec JSON. |
| `brain_transcript_cycle` | `transcripciones.py` | One step of the transcript custody→analysis pipeline (`ingresar → registrar → segmentar → analizar → cobertura → indexar`, plus read-only custody steps and `buscar`). |
| `brain_propose` | `cerebro.py proponer` | Register a suggested change in the tray; does NOT touch the original note. |
| `brain_card` | `cerebro.py ficha` | Create a draft record card (ficha) from a candidate-model type; never invents data. |
| `brain_document` | `cerebro.py documento` | Register a developed D01–D07 / X01–X07 document without approving it. |
| `brain_knowledge_plan` | `cerebro.py plan-conocimiento` | Read-only note-map/tags/relations audit BEFORE drafting, from a structured JSON plan. |
| `brain_dx_apply` | `cerebro.py aplicar-dx` | Apply a D/X modification after specific authorization and backups (SHA-256-gated). |

All handlers call the engine in-process and return a JSON string with `stdout`,
`stderr`, `exit_code` and an English `summary` (0 = success, 2 = engine refused,
1 = unexpected error). Each schema lists the argument flags; they mirror the engine op's
keyword arguments. Full per-tool reference: [docs/reference/tools.md](docs/reference/tools.md).

## Bundled skills (21)

The plugin ships 21 workflow skills under `hermes_business_brain/skills/`, registered at
load time as `hermes-business-brain:<name>` - 20 `ce-*` skills (installation, discovery,
query and task execution, transcripts, taxonomy, relations, knowledge changes,
documentation, research) plus `obsidian-router`, which mandates vault resolution before
any access.

Skills never call the engine directly: they instruct the agent to invoke the `brain_*`
tools with the arguments documented in the reference. See
[docs/reference/skills.md](docs/reference/skills.md) for the master table and
[docs/how-to/use-bundled-skills.md](docs/how-to/use-bundled-skills.md) for how to work
with them.

## Documentation

Organized by quadrant (Diátaxis).

**Tutorial** — learn by doing:

- [Tutorial: create your first business vault](docs/tutorials/quickstart-vault.md) — the
  10-minute walkthrough from preflight to first query.

**How-to** — task-oriented guides:

- [How to install the plugin](docs/how-to/install.md) — both install paths, restart,
  confirmation, and the local-path gotcha.
- [How to continue an existing vault](docs/how-to/continue-existing-vault.md) — resume,
  dependency troubleshooting, the `NO VERIFICADO` discipline.
- [How to work with transcripts](docs/how-to/work-transcripts.md) — the custody and
  analysis pipeline.
- [How to use the bundled skills](docs/how-to/use-bundled-skills.md).
- [How to keep the vault evolving](docs/how-to/keep-the-vault-evolving.md) - the daily
  capture, periodic scan, approved-promotion and revisit loop.

**Reference** — the machinery, as a dictionary:

- [Reference: Tools](docs/reference/tools.md) — the 19 tools: arguments, types,
  required/optional, engine backings, examples.
- [Reference: Evolution](docs/reference/evolution.md) - the brain_evolution_scan tool,
  the promotion rulebook and the revisit cadence table.
- [Reference: Bundled Skills](docs/reference/skills.md) - the 21 bundled skills,
  families, when each activates.
- [Reference: CLI](docs/reference/cli-reference.md) — `cerebro.py` subcommands not
  exposed as plugin tools (no plugin CLI launcher exists).

**Explanation** — how and why:

- [Explanation: Architecture](docs/explanation/architecture.md) — native English
  in-process engine (`api.py` facade over `ops_vault`/`ops_knowledge`/`ops_transcripts`);
  read-only data; no network; skills interaction.
- [Explanation: Privacy and guardrails](docs/explanation/privacy-and-guardrails.md) —
  the invariants as implemented: authorization gates, `NO VERIFICADO`, source over
  summary, ID resolution, rejected legacy, provided-path-only, proposal ≠ decision.

## Security

The privacy invariants above are enforced in code, not just documented — the details
and the failure modes are in
[docs/explanation/privacy-and-guardrails.md](docs/explanation/privacy-and-guardrails.md).
Key points:

- **No real business data ever** — everything bundled is synthetic.
- **No absolute user paths** in the engine — operations only touch paths you pass in.
- **In-process by construction** — no shell, no network. The engine invokes the
  system `git` CLI for two structural checks only (argv-only command lists,
  never a shell): bank/existing-Git location probes (`transcripciones_modelo.py`)
  and product export via `git archive` (`exportar_producto.py`).
- Captures and transcript banks must live **outside** any vault and any Git worktree
  (enforced by the engine).
- Unconfirmable facts are reported as `NO VERIFICADO`, never silently assumed.

## Contributing

Contributions are welcome. For the Hermes plugin itself — tool schemas, handlers,
bundled skills, docs, tests — open an issue or pull request **in this repository**.

### Development setup and tests

```bash
python3.11 -m venv .venv
.venv/bin/pip install "PyYAML==6.0.3" "jsonschema>=4.23,<5" pytest
.venv/bin/python -m pytest tests/ -q
```

To validate the manifest and registration in place: `hermes plugins doctor . --ci`.

## License

MIT — see [LICENSE](LICENSE).

## Layout

```
plugin.yaml                 manifest v2 (18 provided tools)
__init__.py                 register(ctx): tools + bundled skills (tolerant of an empty skills dir)
schemas.py                  tool JSON schemas
tools.py                    in-process handlers over the engine api (tool layer spawns no processes)
hermes_business_brain/engine/   native English engine (api facade + ops_vault, ops_knowledge, ops_transcripts)
hermes_business_brain/data/     model schemas, baseline resources, vault template (English; keys/filenames preserved)
hermes_business_brain/skills/   the 21 bundled plugin skills (loaded as hermes-business-brain:<name>)
tests/                      pytest suite (engine + synthetic vault cycle)
```
