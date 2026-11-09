# Reference — Tools (hermes-business-brain v2)

This is the dictionary of the 18 plugin tools. Every argument name, type and
required/optional status below is taken from `schemas.py`, and every engine
backing from `tools.py`; example invocations show the JSON argument object the
model passes. If a detail here disagrees with a tool's actual schema, the
schema (and, behind it, the engine op it mirrors) wins.

## How a tool runs

Every tool is a handler in `tools.py` that calls one op of the native English
engine (`hermes_business_brain/engine/api.py`) **in-process** — the tool layer
spawns no subprocess and there is no launcher script (no shell, no network).
The engine ops themselves may invoke the system `git` binary, argv-only with
no shell, for two structural checks: bank/existing-Git location probes
(`transcripciones_modelo.py`) and `git archive` product export
(`exportar_producto.py`). The handler returns a JSON string
with this envelope:

```json
{
  "stdout": "...",
  "stderr": "...",
  "exit_code": 0,
  "summary": "doctor completed successfully (exit 0)."
}
```

`summary` is always English. `exit_code` is `0` on success, `2` when the
engine refuses the operation or input validation fails (mirroring the engine
CLI's exit 2 convention), and `1` for unexpected errors (engine unavailable,
timeout, internal exception). Calls are capped at ~120 seconds; a timed-out
call returns exit 1 with an English summary. Handlers never raise: engine
failure is returned inside the JSON, not thrown.

## Conventions

- Argument names mirror each engine op's keyword arguments — the native
  English spelling wins where the engine CLI's flag was Spanish
  (`name` not `--nombre`, `title`/`source` not `--titulo`/`--archivo`,
  `registry` not `--registro`).
- Some argument names on the knowledge/document tools (e.g. `tipo`, `titulo`,
  `resumen`) and the raw JSON result keys of engine tools (e.g. `brain_doctor`'s
  `directorio_trabajo`, `dependencias_python`) preserve the original Spanish
  identifiers as machine contracts (the documented flags rule). The tools'
  `summary` fields and this documentation always provide the English text.
- Paths are always user-provided absolute paths. The engine touches nothing
  outside them except the Codex/Obsidian registry files, whose locations are
  overridable (`registry`/`nativo`).
- Boolean arguments are flags: `true` means the behavior is enabled.
- Repeatable arguments (`sources`, `etiquetas`) are passed as arrays.

## Overview

| Tool | Engine op | CLI backing | Purpose (one line) |
| --- | --- | --- | --- |
| `brain_doctor` | `doctor` | `cerebro.py doctor` | Read-only environment preflight (Python, deps, Obsidian); never installs or writes. |
| `brain_create_vault` | `create_vault` | `cerebro.py crear` | Create a new empty vault from the bundled template; fails if the destination exists. |
| `brain_validate_vault` | `validate_vault` | `validar_boveda.py` | Structural integrity check (ids, wikilinks, transfers) — never business truth. |
| `brain_status` | `status` | `cerebro.py estado` | Structural company summary (counts, editorial state, templates, sources). |
| `brain_register_vault` | `register_vault` | `registrar_boveda_codex.py` | Register an open vault in the Codex selector registry (needs Obsidian's native id). |
| `brain_resolve_vault` | `resolve_vault` | `resolver_boveda_codex.py` | Resolve the vault registered for a Codex project/selector, verified against Obsidian's native registry. |
| `brain_query` | `query` | `cerebro.py consulta-contextual` | Candidate note blocks by literal text + topic/scope/date filters; no semantic generation. |
| `brain_capture` | `capture` | `cerebro.py capturar` | Save preliminary findings as a draft capture note — not approved knowledge. |
| `brain_knowledge_map` | `knowledge_map` | `cerebro.py mapa-conocimiento` (publish: `publicar-mapa`) | Knowledge-map preview (Markdown/Canvas); publish only with SHA/confirmation/backup. |
| `brain_relations` | `relations` | `cerebro.py relaciones` | Query typed relations and their real state (proposals, confirmations). |
| `brain_references` | `references` | `plugin_references.py` (wrapper of `referencias_externas.py`) | Local versioned external-reference registry: metadata only, no content import, no network. |
| `brain_naming` | `naming` | `nombres_legibles.py` | Plan (default) or apply readable filename changes from a spec JSON. |
| `brain_transcript_cycle` | `transcript_cycle` | `transcripciones.py` | One step of the transcript custody→analysis pipeline. |
| `brain_propose` | `propose` | `cerebro.py proponer` | Register a suggested change in the tray; does NOT touch the original note. |
| `brain_card` | `card` | `cerebro.py ficha` | Create a draft record card (ficha) from a candidate-model type; never invents data. |
| `brain_document` | `document` | `cerebro.py documento` | Register a developed D01–D07 / X01–X07 document without approving it. |
| `brain_knowledge_plan` | `knowledge_plan` | `cerebro.py plan-conocimiento` | Read-only note-map/tags/relations audit BEFORE drafting, from a structured JSON plan. |
| `brain_dx_apply` | `dx_apply` | `cerebro.py aplicar-dx` | Apply a D/X modification after specific authorization and backups (SHA-256-gated). |

Subcommands of the engine's CLI that are **not** exposed as plugin tools
are documented in [cli-reference.md](cli-reference.md).

---

## brain_doctor

Read-only environment preflight: reports Python, PyYAML/jsonschema
availability, Obsidian installation candidates, and optionally whether a
vault's company config exists. Never installs anything and never writes.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | no | Absolute path to a vault to include in the preflight report. |

```json
brain_doctor({"vault": "/Users/alice/vaults/empresa"})
```

## brain_create_vault

Create a new empty business vault from the bundled Obsidian template. Never
overwrites: fails if the destination already exists.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | string | yes | Company id, 2–64 chars: letters, digits, dash or underscore. |
| `name` | string | yes | Display name for the company (no newlines). |
| `dest` | string | yes | Absolute path where the new vault directory will be created; must not exist. |

```json
brain_create_vault({"id": "EMPRESA-001", "name": "Acme Consultores", "dest": "/Users/alice/vaults/empresa"})
```

## brain_validate_vault

Validate the structural integrity of a business vault: note ids, wikilinks,
transfers, frontmatter. Integrity only — never business truth.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory to validate. |

```json
brain_validate_vault({"vault": "/Users/alice/vaults/empresa"})
```

## brain_status

Structural summary of a company vault: company id/name, note counts by type,
editorial state, installed templates and bases, source summary. Read-only; a
count, not validated truth.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |

```json
brain_status({"vault": "/Users/alice/vaults/empresa"})
```

## brain_register_vault

Register an already-open Obsidian vault in the Codex local router so Codex
can resolve it. Updates the Codex selector registry only; requires the vault
to already have an id in Obsidian's native registry. May read/write the
user's Codex and Obsidian registry files under the home directory — override
with `registry`/`nativo`.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault already opened in Obsidian. |
| `name` | string | yes | Human-readable name for the vault entry. |
| `alias` | string | yes | Business id used as an alias, e.g. `EMPRESA-001`. |
| `registry` | string | no | Absolute path to the Codex vaults registry JSON (default `~/.codex/obsidian/vaults.json`). |
| `nativo` | string | no | Absolute path to the Obsidian native registry JSON (platform default). |
| `instructions` | string | no | Vault-relative instructions file (default `90_Sistema/Como_usar.md`). |
| `entrypoint` | string | no | Vault-relative entrypoint note (default `Inicio.md`). |
| `proyecto` | string | no | Absolute path of the Codex project directory that should resolve this vault. |

```json
brain_register_vault({"vault": "/Users/alice/vaults/empresa", "name": "Empresa", "alias": "EMPRESA-001"})
```

## brain_resolve_vault

Resolve which registered vault a Codex project (or a selector string) maps
to, verifying it against Obsidian's native registry. Read-only for the
registries. Use before operating on a vault to confirm identity.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `selector` | string | exactly one of `selector`/`project` | Selector matching a registered id, name, alias, or absolute vault path. |
| `project` | string | exactly one of `selector`/`project` | Absolute path of the Codex project whose registered vault should be resolved. |
| `registry` | string | no | Absolute path to the Codex vaults registry JSON (default `~/.codex/obsidian/vaults.json`). |
| `nativo` | string | no | Absolute path to the Obsidian native registry JSON (platform default). |

```json
brain_resolve_vault({"selector": "/Users/alice/vaults/empresa"})
```

## brain_query

Contextual consultation over a vault: candidate note blocks matched by
literal text, with topic/scope/date filters and an optional limit; set
`orientar` to order candidates by the terms of a natural request. Returns
candidates only — never a generated semantic answer.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `texto` | string | yes | Literal text to match against note blocks. |
| `tema` | string | no | Optional topic filter. |
| `ambito` | string | no | Optional scope filter. |
| `fecha` | string | no | Optional date filter (`YYYY-MM-DD`). |
| `limite` | integer | no (default `10`) | Maximum number of candidates. |
| `orientar` | boolean | no (default `false`) | Order candidates by terms from a natural request instead of raw match strength. |

```json
brain_query({"vault": "/Users/alice/vaults/empresa", "texto": "margen bruto", "orientar": true, "limite": 5})
```

## brain_capture

Save preliminary findings as a draft capture note in the vault without
declaring them approved knowledge. The synthesis markdown must be prepared in
a file outside the vault and Git; sources, if any, must already be registered
with `brain_references`.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `title` | string | yes | Title of the capture note. |
| `source` | string | yes | Absolute path to the authorized synthesis markdown file outside the vault and Git. |
| `sources` | array of string | no | Source ids (`F-...`) already registered with `brain_references`; repeatable. |

```json
brain_capture({"vault": "/Users/alice/vaults/empresa", "title": "Hallazgos Q3", "source": "/Users/alice/tmp/hallazgos.md", "sources": ["F-0001", "F-0002"]})
```

## brain_knowledge_map

Preview the knowledge map (Markdown/Canvas renderings) derived from the
vault's notes and relations. Read-only by default; with `publish: true`,
publishes only the derived map, requiring exact SHA-256s, a literal
confirmation phrase and an external backup directory (mirrors the engine
CLI's `publicar-mapa` gates).

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `publish` | boolean | no (default `false`) | Publish the derived map instead of previewing it. |
| `sha_actual` | string | for `publish` | SHA-256 of the currently published map. |
| `sha_propuesto` | string | for `publish` | SHA-256 of the proposed map. |
| `confirmacion` | string | for `publish` | Explicit confirmation phrase (`PUBLICAR MAPA <sha>`). |
| `backup_dir` | string | for `publish` | Absolute path of the external backup directory. |

```json
brain_knowledge_map({"vault": "/Users/alice/vaults/empresa"})
```

## brain_relations

Query typed relations stored in a vault and their real state (proposals,
confirmations). Read-only.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `id` | string | no | Filter: relation originates from or targets this note id. |

```json
brain_relations({"vault": "/Users/alice/vaults/empresa", "id": "EMP-0001"})
```

## brain_references

Local versioned external-reference registry over a private bank directory
(custody area outside any vault and any Git worktree). Registers metadata
only — never imports content, never touches the network. Records are prepared
as JSON files outside the vault, then committed here.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | no | Optional vault path accepted as an alias for `bank` (the knowledge contract keeps both). |
| `action` | string | yes | Operation: `register` (add a metadata record), `read` (fetch one record), `decisions` (list the permission chain), `verify` (transitive closure check). |
| `bank` | string | yes | Absolute path to the private custody bank directory (must not be inside a vault or Git worktree). |
| `commit` | boolean | no (default `false`) | Apply the custody mutation; default is a preview that validates without writing. |
| `metadata` | string | for `register` | Absolute path to the JSON reference record (`referencia-externa.v1`) prepared outside the vault. |
| `reference_id` | string | for `read` | Id of the registered reference. |
| `version_id` | string | for `read` | Version id (`EV-...`) of the registered reference. |
| `refs` | string | for `verify` | Absolute path to a JSON array of reference descriptors to verify transitively. |
| `company` | string | for `verify` | Company id scope. |
| `audience` | string | for `verify` | Audience scope. |
| `purpose` | string | for `verify` | Purpose scope (e.g. `local_analysis`, `custody`). |
| `require_read` | boolean | for `verify` (default `true`) | Require reading evidence for external references. |
| `require_internal` | boolean | for `verify` (default `false`) | Require `interno` sensitivity for external references. |
| `decision` | string | for `decisions` | Caller-supplied decision record (JSON path or inline payload) when recording a permission decision. |

```json
brain_references({"action": "register", "bank": "/Users/alice/banco", "metadata": "/Users/alice/tmp/ref.json", "commit": true})
```

## brain_naming

Plan (or apply) readable filename changes for a vault from a spec JSON
prepared outside the vault and Git. Default is a read-only plan; pass
`apply: true` to execute, which requires a backup directory and the plan's
expected SHA-256.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `spec` | string | yes | Absolute path to the naming spec JSON prepared outside the vault. |
| `apply` | boolean | no (default `false`) | Apply the rename plan instead of only previewing it. |
| `sha_plan` | string | no | Expected SHA-256 of the plan file; rejects mismatches when applying. |
| `backup_dir` | string | no (required when applying) | Absolute path of the backup directory. |

```json
brain_naming({"vault": "/Users/alice/vaults/empresa", "spec": "/Users/alice/tmp/spec.json", "apply": true, "sha_plan": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "backup_dir": "/Users/alice/backups"})
```

## brain_transcript_cycle

Drive one step of the transcript custody and analysis pipeline over a private
transcript bank (custody area outside any vault and Git worktree). The full
cycle is `ingresar → registrar → segmentar → analizar → cobertura → indexar`,
plus read-only custody steps (`estado`, `verificar`, `inventario-validar`,
`conciliar`), `buscar`, and the bookkeeping steps (`permiso`, `taxonomia`,
`revisar-antecedentes`). Profile JSON must contain `company_id` and
`allowed_purposes` and live outside the vault.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the private transcript bank root (the engine CLI's `--bank`); must not be inside an Obsidian vault or Git worktree. |
| `step` | string | yes | One of: `ingresar`, `registrar`, `segmentar`, `analizar`, `cobertura`, `indexar`, `revisar-antecedentes`, `taxonomia`, `permiso`, `estado`, `verificar`, `inventario-validar`, `conciliar`, `buscar`. |
| `profile` | string | yes | Absolute path to the profile JSON: `{company_id, allowed_purposes:[...], optional bank/vault}`. |
| `request_id` | string | yes | Caller-supplied request id for the custody ledger (`safe_id` format). |
| `purpose` | string | yes | Purpose scope that must be allowed by the profile (e.g. `custody`, `local_analysis`). |
| `audience` | string | no | Audience scope; required for `segmentar`/`analizar`/`cobertura`/`indexar`/`revisar-antecedentes`, optional for `estado`. |
| `commit` | boolean | no (default `false`) | Apply the local custody mutation; default is a read-only preview. |
| `output` | string | no | Optional absolute path for an immutable JSON report; must not already exist (required for `buscar`). |
| `file` | string | for `ingresar` | Absolute path to the transcript file to import. |
| `payload` | string | for `ingresar` | Inline raw ingest payload (alternative to `file`/`parts_manifest`). |
| `parts_manifest` | string | for `ingresar` | Absolute path to a JSON parts manifest instead of a single file. |
| `source_id` | string | for `ingresar` | Transcript source id. |
| `account_id` | string | for `ingresar` | Account id. |
| `attempt_id` | string | for `ingresar` | Attempt id. |
| `closed` | boolean | for `ingresar` | Mark the capture closed (complete). |
| `expected_parts` | integer | for `ingresar` | Expected part count for closed captures. |
| `capture_manifest` | string | for `registrar` | Absolute path to the capture receipt JSON produced by `ingresar`. |
| `tr_id` | string | for `segmentar`/`cobertura` | Transcript id. |
| `version` | string | for `segmentar` | Version id to segment. |
| `policy` | string | for `segmentar` | Segmentation policy id (default `utf8-bytes-1`). |
| `max_core_bytes` | integer | for `segmentar` (default `4096`) | Max bytes for a core segment. |
| `context_bytes` | integer | for `segmentar` (default `256`) | Context bytes around a segment. |
| `run` | string | for `cobertura` | Analysis run id. |
| `input` | string | for `analizar`/`permiso`/`taxonomia` | Absolute path to the JSON input payload prepared outside the vault. |
| `event` | string | for `revisar-antecedentes`/`taxonomia` | Absolute path to the event JSON. |
| `snapshot` | string | for `revisar-antecedentes`/`inventario-validar`/`conciliar`/`indexar` | Snapshot JSON path, or `current` for the live watermark. |
| `results` | string | for `revisar-antecedentes` | Optional agent-authored results JSON array path. |
| `previous` | string | for `revisar-antecedentes` | Prior review bundle path relative to the bank. |
| `taxonomy_version` | string | for `revisar-antecedentes` | Exact stored taxonomy version for claim resolution. |
| `request` | string | for `buscar` | Absolute path to the query request JSON `{query, company, audience, purpose, ...}`. |

```json
brain_transcript_cycle({"step": "ingresar", "vault": "/Users/alice/banco", "profile": "/Users/alice/tmp/perfil.json", "request_id": "doc-verify-ingreso-1", "purpose": "custody", "file": "/Users/alice/tmp/transcripcion.vtt", "commit": true})
```

## brain_propose

Register a suggested change for a note in the change tray; does **NOT** touch
the original note. The candidate text must be prepared in an authorized local
file outside the vault and Git.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `id` | string | yes | Exact id of the target note. |
| `motivo` | string | yes | Reason for the suggested change. |
| `archivo` | string | yes | Absolute path to the local authorized candidate text file outside the vault and Git (max 120000 bytes). |
| `author` | string | no (default `agente`) | Author recorded on the proposal. |

```json
brain_propose({"vault": "/Users/alice/vaults/empresa", "id": "NOTA-001", "motivo": "Precisar cifras", "archivo": "/Users/alice/tmp/candidato.md"})
```

## brain_card

Create a draft record card (ficha) from a specific type in the candidate
model; never invents data. Optional developed markdown must be prepared
outside the vault and Git, without YAML frontmatter.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `tipo` | string | yes | Card type from the candidate model (e.g. `empresa`, `persona`, `proyecto`, `tarea`); sources require the dedicated reference registration. |
| `titulo` | string | yes | Title of the record card. |
| `resumen` | string | no | Optional summary (max 7000 chars). |
| `archivo` | string | no | Absolute path to an optional developed note in Markdown, outside Git and the vault, without YAML frontmatter. |
| `sources` | array of string | no | Source ids (`F-...`) already registered; repeatable. |
| `etiquetas` | array of string | no | Obsidian thematic tags; repeatable. |

```json
brain_card({"vault": "/Users/alice/vaults/empresa", "tipo": "empresa", "titulo": "Acme Consultores", "resumen": "..."})
```

## brain_document

Register a developed D01–D07 / X01–X07 document **without** approving it.
The markdown must be prepared outside the vault and Git; sources, if any,
must already be registered.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `clase` | string | yes | Document class, one of D01–D07 / X01–X07. |
| `titulo` | string | yes | Title of the document note. |
| `archivo` | string | yes | Absolute path to the developed Markdown prepared outside the vault and Git. |
| `doc_id` | string | no | Optional identity `Xnn-...`; for Dnn classes it coincides with the class. |
| `estado` | string | no (default `borrador`) | Editorial state: `borrador` or `en_revision`. |
| `cobertura` | string | no | Source coverage level: `sin_fuente`, `parcial`, `suficiente_para_tarea`, `no_aplica`. |
| `fecha_corte` | string | no | Cut-off date `YYYY-MM-DD`; defaults to creation date. |
| `sources` | array of string | no | Source ids (`F-...`) already registered; repeatable. |
| `etiquetas` | array of string | no | Obsidian thematic tags; repeatable. |

```json
brain_document({"vault": "/Users/alice/vaults/empresa", "clase": "D01", "titulo": "Modelo de negocio", "archivo": "/Users/alice/tmp/doc.md", "estado": "en_revision"})
```

## brain_knowledge_plan

Audit the note map, tags and relations of a vault **BEFORE** drafting:
read-only planning step driven by a structured JSON plan file prepared
outside the vault and Git.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `archivo` | string | yes | Absolute path to the structured JSON plan prepared outside Git and the vault. |

```json
brain_knowledge_plan({"vault": "/Users/alice/vaults/empresa", "archivo": "/Users/alice/tmp/plan.json"})
```

## brain_dx_apply

Apply a D/X modification proposal after specific authorization and backup.
Requires exact SHA-256 fingerprints of the original and candidate documents
and a backup directory; never edits without authorization evidence.

| Argument | Type | Required | Meaning |
| --- | --- | --- | --- |
| `vault` | string | yes | Absolute path to the vault directory. |
| `propuesta` | string | yes | Absolute path to the authorized D/X proposal file. |
| `sha_original` | string | yes | SHA-256 of the current (original) document version. |
| `sha_candidato` | string | yes | SHA-256 of the candidate replacement document. |
| `sha_fuentes` | string | no | SHA-256 of the resulting sources set, required when sources are added. |
| `responsable` | string | yes | Human responsible for the change. |
| `referencia_autorizacion` | string | yes | Authorization reference id (e.g. `AUT-001`). |
| `backup_dir` | string | yes | Absolute path of the backup directory. |

```json
brain_dx_apply({"vault": "/Users/alice/vaults/empresa", "propuesta": "/Users/alice/tmp/propuesta.md", "sha_original": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "sha_candidato": "0a08f15d6c15b0f00a089f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822c", "responsable": "Alice", "referencia_autorizacion": "AUT-001", "backup_dir": "/Users/alice/backups"})
```
