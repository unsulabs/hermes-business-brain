# How to work with meeting transcripts

**Use this when**: a meeting transcript, a pasted conversation, or a
multi-part delivery arrives and must be *preserved* first, then analyzed —
with custody, hashes, and permission checks, and without ever dumping raw
content into the vault.

The tool is `brain_transcript_cycle`. It does **not** copy a transcript into
the vault. Instead it drives one step at a time of a custody-and-analysis
pipeline over a **private bank** — a directory that must live outside every
vault and outside every Git worktree.

> The pipeline's operating manual is the bundled skill
> [`ce-banco-transcripciones`](../../hermes_business_brain/skills/ce-banco-transcripciones/SKILL.md).
> This recipe covers the tool's mechanics; the skill covers the discipline
> (partial deliveries, corrections, permission chains).

## Arguments every call needs

Every step takes the same five base arguments (verified in `schemas.py`):

| Argument | Meaning |
| --- | --- |
| `step` | one of the 14 pipeline steps (below) |
| `vault` | absolute path of the private custody bank (the engine's `--bank`; must already exist) |
| `profile` | absolute path of a JSON profile (see next section) |
| `request_id` | caller-supplied request id for the custody ledger (`safe_id` format) |
| `purpose` | the purpose scope for this operation, e.g. `custody`, `local_analysis` |

Optional, per call: `audience` (required by the analysis steps), `commit`
(apply the mutation; the default is a read-only preview), `output` (an
immutable JSON report path — must not pre-exist), and the step-specific
flags listed below.

### The profile JSON

The profile pins the company and its permitted purposes (schema: "Profile
JSON must contain company_id and allowed_purposes and live outside the
vault"):

```json
{
  "company_id": "ACME-001",
  "allowed_purposes": ["custody", "local_analysis", "internal_query"],
  "bank": "/private/.../bank"
}
```

The optional `bank` key must match the tool's `vault` argument exactly. Every
call checks `purpose` against `allowed_purposes` first — a purpose that is
not allowed is refused with `PURPOSE_DENIED` and nothing runs:

```json
{ "status": "BLOCKED", "errors": [{ "code": "PURPOSE_DENIED", "recoverable": true }] }
```

### The bank directory

The bank must **already exist**; the engine validates it but never creates
it. It must be outside any Obsidian vault and any Git worktree, and its path
must not traverse symlinks (the engine rejects them with `UNSAFE_PATH` — on
macOS, write `/private/...` paths, because `/var` is a symlink).

## The custody → analysis cycle

The tool implements the pipeline described in its schema:

> `ingresar → registrar → segmentar → analizar → cobertura → indexar`

Each step is its own `brain_transcript_cycle` call. Steps that mutate (marked
"write") run as previews until you pass `commit`; the read-only steps never
write regardless.

| Step | Purpose | Key flags (from the schema) | Writes | Needs `audience` |
| --- | --- | --- | --- | --- |
| `ingresar` | Import transcript bytes/parts as an immutable original | `file` **or** `payload` **or** `parts_manifest`; `source_id`, `account_id`, `attempt_id`; `closed` + `expected_parts` for complete deliveries | yes | no |
| `registrar` | Commit a capture receipt | `capture_manifest` (path produced by `ingresar`) | yes | no |
| `segmentar` | Split a committed capture into spans | `tr_id` (from `ingresar`), `version`, `policy`; optional `max_core_bytes` (4096), `context_bytes` (256) | yes | **yes** |
| `analizar` | Consolidate agent-authored analysis | `input` (JSON payload prepared outside the vault) | yes | **yes** |
| `cobertura` | Coverage report for an analysis run | `tr_id`, `run` | no | **yes** |
| `indexar` | Rebuild the query index | `snapshot` (`current` for the live watermark) | yes | **yes** |
| `buscar` | Query a context package | `request` (JSON: query/company/audience/purpose…); `output` is **required** | no (but writes the `output` report) | no |

Read-only custody steps: `estado` (pipeline summary), `verificar` (bank
integrity), `inventario-validar` (snapshot check), `conciliar` (catalog vs
snapshot). Bookkeeping steps: `permiso` (record a custody purpose decision;
its input JSON must carry the profile's `company_id` and run with
`purpose: custody`), `taxonomia` (store taxonomy; purpose must be
`local_analysis`), `revisar-antecedentes` (historical context for new
analysis; needs `event`, `snapshot`, `audience`).

### What a custody step looks like

A verified `ingresar` (commit, single-part synthetic transcript) is the tool
call:

```json
brain_transcript_cycle({
  "step": "ingresar",
  "vault": "/private/.../bank",
  "profile": "/private/.../perfil.json",
  "request_id": "doc-verify-ingreso-1",
  "purpose": "custody",
  "file": "/private/.../transcript.txt",
  "source_id": "SRC-2026-1106-001",
  "account_id": "ACC-ACME",
  "attempt_id": "ATT-1",
  "commit": true
})
```

Result (trimmed; note the receipt paths and hashes — this is the custody
"paper trail"):

```json
{
  "status": "DONE_WITH_CONCERNS",
  "warnings": ["DELIVERY_INCOMPLETE"],
  "evidence": {
    "committed": true,
    "completeness": "partial",
    "received_parts": 1,
    "tr_id": "TR-00b5f2d22cdc34c5fe9cd5c9ecc51e9d4842525532d5459d95c6eefa1d797afb",
    "version_id": "V-3db7be8e0a22b70b0bfe557461fb91d3a93f03f671b2e9cb20dc420faf63d9a9"
  },
  "outputs": [
    { "path": "receipts/9f43a59d9c7fccf02c88411a06f6cd1a0ef997b018ebfc7699994cb558aa1018.json", "sha256": "35a64fab..." },
    { "path": "recepcion/local/doc-verify-ingreso-1/.../capture-manifest.v1.json", "sha256": "c0e67324..." }
  ]
}
```

Two things to notice:

- The capture is **partial** (`DELIVERY_INCOMPLETE`) because it was not
  declared closed. For a complete delivery pass `closed: true` with
  `expected_parts: N`; a correction creates a *version*, it never replaces
  bytes (the skill calls this "A correction creates a version, doesn't
  replace bytes").
- Every artifact carries a SHA-256. Later steps reference the transcript by
  `tr_id` and `version_id`, so nothing is re-downloaded or re-analyzed
  wholesale — **ce-continuidad**'s "resume by job_id, attempt, version,
  snapshot/cursor and hashes".

### Checking state

`estado` is the read-only dashboard (verified empty-bank call, `status:
DONE`, `transcriptions: 0`; and after the commit above, `transcriptions: 1`
with `integrity: verificada`, `analysis: pendiente`, `validity:
sin_verificar`). Use it to confirm where a delivery stands before resuming.

### Searching

`buscar` returns a *context package* — candidates from the index, with
`semantic_answer_generated: false` (no invented answers). It requires
`output` (a fresh immutable report path; `PRIVATE_OUTPUT_REQUIRED` is raised
without it), and the request JSON's `company`/`purpose` must match the
profile's (`QUERY_SCOPE_MISMATCH` otherwise).

## Limits: rendering cards back into the vault

The tool's own description ends the pipeline at `indexar` (plus `buscar` and
the read-only custody steps). Rendering the analyzed material back into the
vault as *knowledge cards* — the
`render_source / prepare_batch / apply_batch` APIs in
`transcripciones_fichas.py` — is **not** a plugin tool step. The engine
module ships, but no `brain_*` tool exposes it; the bundled skill
[`ce-banco-transcripciones`](../../hermes_business_brain/skills/ce-banco-transcripciones/SKILL.md)
is explicit that integration "uses the `render_source`, `prepare_batch`,
`apply_batch` APIs in `transcripciones_fichas.py` and
`transcripciones_integracion.py`, not an invented
CLI subcommand". So in v2: preserve → analyze → index → search; card
integration into the vault happens through the engine API only where the
skill's contracts and tests document it, otherwise it is not available as a
plugin-tool step.

For the full discipline around deliveries, permissions and parts, run this
recipe through the skills: [`ce-banco-transcripciones`](../../hermes_business_brain/skills/ce-banco-transcripciones/SKILL.md),
[`ce-analizar-transcripcion`](../../hermes_business_brain/skills/ce-analizar-transcripcion/SKILL.md),
and [`ce-extraer-meetgeek`](../../hermes_business_brain/skills/ce-extraer-meetgeek/SKILL.md)
([overview](use-bundled-skills.md)).
