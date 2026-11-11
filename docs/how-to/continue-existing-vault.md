# How to continue an existing business vault

**Use this when**: you already have a business vault — you created it
earlier, a colleague did, or a conversation starts with "continue", "resume",
"my company vault", or a vault path.

The single most important rule, in both relevant bundled skills, is **do not
create or reinstall**:

> **ce-instalacion**: "identify whether the user already has a vault; … If it
> exists, **do not create another one nor reinstall**."
> ([`../../skills/ce-instalacion/SKILL.md`](../../skills/ce-instalacion/SKILL.md))

> **ce-continuidad**: "Don't re-run create nor regenerate existing notes."
> ([`../../skills/ce-continuidad/SKILL.md`](../../skills/ce-continuidad/SKILL.md))

Running `brain_create_vault` on an existing vault does not work anyway (the
destination must not pre-exist), but the reason to avoid it is not technical:
a vault is someone's accumulated business state, and a re-created one would
lose identity and provenance. Recover the real state instead.

## Step 1 — Resolve the vault first: `brain_resolve_vault`

Before reading anything inside the vault, resolve *which* vault the
conversation refers to. Ask Hermes to run `brain_resolve_vault` with an
explicit selector:

| Argument | Value |
| --- | --- |
| `selector` | the business id (`EMPRESA-001`), a registered name, an alias, or the absolute vault path |

(Alternative: `project` — the absolute path of an agent project whose
registered vault should be resolved. Exactly one of `selector`/`project` must
be given.)

`brain_resolve_vault` is **read-only for both registries**: it reads the local
vault registry (`~/.codex/obsidian/vaults.json` by default, overridable with
`registry`/`nativo`) and cross-checks the match against Obsidian's native
registry. It only *reports*; it writes nothing. A verified success looks like
this (run against a synthetic registry, real output):

```json
{
  "status": "selected",
  "id": "vault-acme-001",
  "name": "Acme Consultores",
  "path": "/private/.../vault",
  "native_registry_verified": true,
  "instructions": ".../vault/90_Sistema/Como_usar.md",
  "entrypoint": ".../vault/Inicio.md"
}
```

Two design gates worth knowing (both verified in
[`../../_verify/tool-layer.md`](../../_verify/tool-layer.md)):

- **Exactly one match** must exist; a missing or ambiguous selector fails with
  "Destination missing or ambiguous; require one registered match".
- **Native proof is required** before any vault content is consulted: the
  matching entry must have exactly one id in Obsidian's native registry whose
  path matches, and the `instructions`/`entrypoint` files must exist inside
  the vault. Failure reads "Native Obsidian ID/path mismatch; open the vault
  in Obsidian and review registration". The resolver never opens note
  contents before that native proof.

## Step 2 — If it is not registered yet: `brain_register_vault`

Resolution fails whenever there is no local registry entry (the common case
for a vault that was never used through this plugin). Register it — this is
the *only* write step, and it is narrow:

| Argument | Value |
| --- | --- |
| `vault` | absolute path of the vault (already opened in Obsidian) |
| `name` | human-readable name, e.g. `Acme Consultores` |
| `alias` | the business id, e.g. `EMPRESA-001` |

`brain_register_vault` **requires the vault to already have an id in
Obsidian's native registry** — i.e. the folder was opened as a vault in
Obsidian at least once. If that identity is missing, it refuses to write
anything (verified):

```json
{ "status": "error", "error": "Open the folder as a vault in Obsidian first; a single native ID is required" }
```

That is an authorization gate, not a bug: registration is about *matching*
an already-existing Obsidian identity, never inventing one. Per
**ce-instalacion**, registration "only writes the local agent registry, with a
backup; it never alters the native registry nor the vault." After a successful
register, run `brain_resolve_vault` again (step 1) until it reports
`native_registry_verified: true`.

## Step 3 — Re-read the real state: `brain_status` + `brain_validate_vault`

With the vault resolved, re-establish what is actually there. **ce-continuidad**
requires both, and both are read-only:

> "run `brain_status` and `brain_validate_vault` to re-read the real state …
> Record both results; only declare the capability unverified after that safe
> attempt."

- `brain_status --vault <path>` — current counts, editorial state, layers.
  Remember its warning: structural count, **not** validated truth.
- `brain_validate_vault --vault <path>` — structural integrity (ids, links,
  transfers); integrity is not business truth either.

Do not trust an old summary in place of these: **ce-continuidad** says "Don't
consider SES or an earlier summary as a substitute for originals."

## Step 4 — Work with the vault's knowledge

Now you may query and operate normally:

- `brain_query` — pull existing knowledge into the task as literal candidate
  blocks (`--orientar` for natural-request ordering).
- `brain_capture` — preserve new preliminary findings as drafts (the synthesis
  file must live outside the vault and outside Git).
- Read-only inspection: `brain_knowledge_map`, `brain_relations`.

## If a tool fails with a Python dependency error

Do not declare the vault or the capability broken. First retry with an
interpreter that has the dependencies. **ce-consulta** prescribes: check
`command -v python3.11 python3.12 python3.13` (macOS Homebrew:
`/opt/homebrew/bin/python3.11`) and any venv already used for this instance;
run `python -c "import yaml, jsonschema"` with each candidate and retry the
same operation. **ce-continuidad** adds: only after that safe attempt fails
may you mark the capability unverified.

## The `NO VERIFICADO` discipline

Both skills insist on honest reporting when something cannot be proven:

- **ce-instalacion**: "If the GUI or the router are not available or don't
  confirm the path, mark that integration `NO VERIFICADO`, keep the instance
  and explain the concrete blocker; continue only independently authorized
  work outside the vault." It also says to report the six surfaces separately
  (code, Python, Obsidian GUI, Bases, private instance, sources/connectors)
  and mark each `NO VERIFICADO` where appropriate.
- **ce-continuidad**: "don't fabricate progress" — if nothing changed, say
  which concrete source or decision prevented it.

In practice: if Obsidian is not running and you cannot confirm the vault
opens there, say `NO VERIFICADO` for that surface and keep working on the
surfaces you could confirm. Never claim "the brain is complete" because a
check passed.

## Evidence

The resolver output, the registration refusal, and the interpreter probe
rules above were verified on this machine; see
[`../../_verify/tool-layer.md`](../../_verify/tool-layer.md) and
[`../../_verify/engine-core.md`](../../_verify/engine-core.md).
