# Explanation — Architecture: a native English engine behind 18 tools

This page explains how `hermes-business-brain` is put together and why it is
shaped that way. For exact arguments and names, see the
[Reference](../reference/tools.md) pages; this page is about how the pieces
fit.

## The big picture

The plugin is a **native Hermes plugin with an in-process English engine**.
Every subcommand, JSON key, state machine and security gate of the product is
preserved, with the runtime text in English. There are two layers:

1. **The plugin layer** — `plugin.yaml`, `__init__.py`, `schemas.py`,
   `tools.py`, and the bundled skills under `hermes_business_brain/skills/`.
   Written for Hermes, in English, MIT-licensed. This is what Hermes loads.
2. **The native engine** — `hermes_business_brain/engine/` (the package)
   plus the bundled `data/` directory (model schemas, baseline resources, the
   vault template). Logic, JSON keys, subcommand names and flags are the
   product's protocol; runtime messages are English.

`plugin.yaml` declares the manifest (v2, api version 1), the two Python
dependencies (`PyYAML==6.0.3`, `jsonschema>=4.23,<5`), and the 18 provided
tools. At load, `register(ctx)` in `__init__.py` registers each tool (schema
from `schemas.py`, handler from `tools.py`) and then registers every
`hermes_business_brain/skills/<dir>/SKILL.md` as a plugin skill under
`hermes-business-brain:<name>`. Registration is tolerant: an empty or missing
skills directory is fine, and a missing engine degrades each tool to a clear
English error instead of breaking load.

## The tool execution path

Every tool handler in `tools.py` calls exactly one engine op **in-process**.
The pattern is uniform:

- **No shell, no network, no launcher**: the handler lazily imports
  `hermes_business_brain.engine.api` and calls `api.<op>(**kwargs)` in the
  host process. There is no `run_script.py` launcher and no child process
  spawned by the tool layer. (The engine ops may invoke the system `git`
  binary itself — argv-only command lists, no shell — for two structural
  checks only: bank/existing-Git location probes in `transcripciones_modelo.py`
  and product export via `git archive` in `exportar_producto.py`.)
- **Engine package layout**: `ops_vault.py` (vault lifecycle: doctor, create,
  validate, status, register, resolve), `ops_knowledge.py` (knowledge
  operations: query, capture, knowledge map, relations, references, naming,
  propose, card, document, knowledge plan, D/X apply), and
  `ops_transcripts.py` (the transcript custody/analysis pipeline). `api.py`
  is the tolerant facade that re-exports the 18-op union; `engine/__init__.py`
  exposes the public API names and `BrainError`.
- **~120s timeout**: calls run through a shared `ThreadPoolExecutor`;
  `future.result(timeout=120)` abandons a hung call. A timeout is not an
  exception — the handler returns exit 1 with an English summary.
- **Result envelope, always JSON**: `{"stdout", "stderr", "exit_code",
  "summary"}`. `exit_code` is `0` (success), `2` (engine refused / input
  validation failed — `cerebro.py`'s exit-2 convention), or `1` (unexpected
  error, engine unavailable, timeout). `summary` is always English; the
  engine's own payload text is English too (v2 native engine).
- **Handlers never raise**: engine failure is returned inside the JSON, so
  one failing call cannot take down the agent.

## Data is shipped read-only

All model data lives under `hermes_business_brain/data/` and is bundled
as read-only product data:

- `data/modelo/` — the canonical document classes
  (`clases_documentales.json`), entity types (`tipos_entidad.json`), start
  routes (`rutas_de_inicio.json`), and the transcript schemas under
  `transcripciones/`.
- `data/recursos/` — baseline mirrors (`bases_baseline.json`,
  `registro_plugins.json`).
- `data/plantilla_boveda/` — the complete Obsidian vault template
  (`Inicio.md`, `00_Mapas/`, `90_Sistema/` with the D01–D07/X01–X07 and Ficha
  templates, `.base` views, `config_empresa.yaml`).

The plugin ships this tree as data: the native layer never writes into
`data/`, and engine writes go only to user-provided vault and bank paths.
Nothing here is real business data — everything is synthetic by design.

## No network access

The plugin has no network code at all. The only network-adjacent import in
the whole engine is `urllib.parse.urlparse` in `referencias_externas.py`,
used purely to **parse and catalog URL locators without connecting** (the
script's own contract: URLs are catalogued without accessing the network).
There are no HTTP/socket clients, no `requests`/`urllib.request` usage, no
call-out anywhere. The plugin is fully offline by construction.

## How the bundled skills interact with the tools

The 19 bundled skills (`hermes-business-brain:ce-*` plus `obsidian-router`)
are procedures that tell the agent *when and how* to call the tools. Their
interaction pattern:

- Skills prescribe **tool sequences with discipline** — e.g. `obsidian-router`
  requires `brain_resolve_vault` (exit 0, `status: selected`,
  `native_registry_verified: true`) before any vault read; `ce-instalacion`
  chains `brain_doctor` → `brain_create_vault` → `brain_validate_vault` →
  `brain_register_vault` → `brain_resolve_vault`.
- Skills pass the tools' **schema arguments** by name, so the schemas in
  `schemas.py` are the interface contract the skills program against.
- Where a needed CLI subcommand is **not exposed** as a plugin tool
  (17 of cerebro.py's 29 subcommands), skills reference it explicitly with the
  label "upstream CLI subcommand, not exposed as a v2 plugin tool" — and only
  when a skill's contracts and tests document it may it be reached through the
  engine API. The plugin ships no CLI launcher; see
  [cli-reference.md](../reference/cli-reference.md).

## Why in-process instead of wrapping

An earlier version wrapped the product's scripts in a subprocess launcher. The v2
engine is instead a native, fully in-process implementation, for three
reasons:

- **No subprocess layer**: in-process calls remove the launcher shim
  entirely — no `run_script.py`, no `sys.path` re-injection, no child-process
  exit-code plumbing. The tool layer is a thin, stable facade over plain
  Python functions.
- **Fidelity is verifiable**: logic, JSON keys, subcommand names and flags
  are the product's protocol. Every op maps to its engine module, and the
  mapping is recorded in the `_verify/` evidence files.
- **One exposed surface**: the 18 tools are the plugin's only surface; the
  remaining CLI subcommands stay in the engine's own `cerebro.py` and are not
  reachable as plugin tools (see
  [cli-reference.md](../reference/cli-reference.md)).

What stays as product protocol by design: JSON keys, enum tokens, state
machines and the data files — they are protocol, not prose.
