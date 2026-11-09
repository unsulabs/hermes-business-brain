# Tutorial: create your first business vault

By the end of this tutorial you will have:

- a brand-new business vault with a stable company id,
- proof that it is structurally sound,
- your first captured finding, preserved as a draft,
- a working understanding of why a fresh vault answers queries with "no
  candidates yet" — and that this is the designed behaviour, not a bug.

This tutorial takes about 10 minutes. You need Hermes with the
`hermes-business-brain` plugin installed and enabled
([How to install the plugin](../how-to/install.md)) — the commands below are
the *tools* the plugin adds. Every example in this tutorial was run, end to
end, against a throwaway vault by calling the engine ops in-process; the
outputs shown are the real envelopes' `stdout`.

## Before you start

Pick three things:

1. **A business id**: 2–64 characters, letters, digits, dash or underscore
   (`[A-Za-z0-9][A-Za-z0-9_-]{1,63}`). We use `EMPRESA-001`.
2. **A display name**: for example `Acme Consultores`.
3. **A destination path that does not exist yet**: for example
   `~/empresas/acme-consultores`. The creator refuses to overwrite anything —
   if the folder already exists, the command fails (that is a safety feature,
   see step 2).

## Step 1 — Check the environment with `brain_doctor`

Ask Hermes to run `brain_doctor`. It is a read-only preflight: it reports
Python, the Python dependencies, and any Obsidian installation it can find. It
never installs anything.

A healthy result looks like this (trimmed):

```json
{
  "producto": "Business Brain 0.2.0",
  "python": "3.14.7",
  "dependencias_python": { "yaml": "INSTALLED", "jsonschema": "INSTALLED" },
  "candidatos_obsidian": ["/Applications/Obsidian.app"],
  "obsidian_version": "NOT VERIFIED",
  "obsidian_gui": "NOT VERIFIED",
  "instalacion_real": "NOT DONE BY THIS COMMAND"
}
```

Note the `NOT VERIFIED` entries: the doctor tells you honestly what it could
*not* prove (Obsidian's version and its GUI, Bases, templates). That is the
plugin's reporting discipline: an unconfirmed fact is labelled `NOT VERIFIED`,
never silently assumed. If `yaml`/`jsonschema` do **not** say `INSTALLED`,
fix the Python environment first (see the
[install guide](../how-to/install.md)).

## Step 2 — Create the vault with `brain_create_vault`

Give Hermes exactly three arguments:

| Argument | Value |
| --- | --- |
| `id` | `EMPRESA-001` |
| `name` | `Acme Consultores` |
| `dest` | `~/empresas/acme-consultores` (must **not** exist) |

You should get:

```json
{
  "creada": "/Users/you/empresas/acme-consultores",
  "estado": "infraestructura_sin_conocimiento",
  "nota": "Open and verify manually in Obsidian"
}
```

Two safety properties are worth remembering:

- `id` must match `[A-Za-z0-9][A-Za-z0-9_-]{1,63}`. A value like `MI EMPRESA`
  is rejected before anything is written.
- `dest` must not pre-exist. Running the same create again on the existing
  folder fails with a safe-failure error. Nothing is ever overwritten, and
  you should never delete an existing folder to "make room".

## Step 3 — Validate with `brain_validate_vault`

Point `brain_validate_vault` at the new vault. This checks structural
integrity only: note ids, wikilinks, transfers, frontmatter. It does **not**
judge whether your business content is true.

Expected result for a fresh vault:

```json
{
  "notas": 7,
  "ids": 7,
  "bloques": 0,
  "traspasos": 0,
  "errores": [],
  "advertencias": []
}
```

`errores: []` and `advertencias: []` mean the skeleton is clean: 7 template
notes (Inicio plus system notes) with valid ids and links.

## Step 4 — See its state with `brain_status`

`brain_status` summarizes the company: id, name, note counts per type, and
how much is "infrastructure" versus "knowledge".

Key fields (trimmed):

```json
{
  "empresa": "Acme Consultores",
  "id_empresa": "EMPRESA-001",
  "total_notas": 7,
  "capas": {
    "infraestructura": 7,
    "fuentes": 0,
    "trabajo_provisional": 0,
    "documentos_dx": 0,
    "entidades_operativas": 0
  },
  "plantillas_instaladas": 47
}
```

The output ends with a warning worth taking literally:

> `advertencia`: "Structural count, NOT coverage sufficiency nor validated truth"

Translation: this is a *structural count*, not validated business truth. Every
future `brain_status` output carries the same caveat.

## Step 5 — Capture a first finding with `brain_capture`

Now do some real thinking. Suppose a first conversation produced a preliminary
finding: *the client asked for weekly review meetings and one single point of
contact*.

Write that synthesis to a plain Markdown file **outside the vault** (and
outside any Git worktree), for example `~/tmp/hallazgo.md`:

```markdown
# Draft finding

The client asked for weekly review meetings and one single point of contact.
To be confirmed against the 2026-11-03 meeting.
```

Then ask Hermes to run `brain_capture`:

| Argument | Value |
| --- | --- |
| `vault` | `~/empresas/acme-consultores` |
| `title` | `Weekly review meetings requested` |
| `source` | `~/tmp/hallazgo.md` |

Result:

```json
{
  "id": "CAP-2471F90F241C",
  "ruta": ".../acme-consultores/90_Sistema/Descubrimiento/Weekly review meetings requested.md",
  "estado": "borrador_no_autoritativo",
  "fuentes": [],
  "aprobado": false,
  "importado_como_conocimiento": false
}
```

Read that JSON carefully: the note is stored as `borrador_no_autoritativo`
(non-authoritative draft) with `aprobado: false`. **Capturing a finding is
preserving it — it is not declaring it knowledge.** The note lands in
`90_Sistema/Descubrimiento/`, the discovery area where raw material waits to
be developed.

## Step 6 — Query the vault with `brain_query`

Now the moment of truth: pull that finding back out.

```json
brain_query({ "vault": "~/empresas/acme-consultores", "texto": "weekly review meetings" })
```

Result:

```json
{
  "empresa_id": "EMPRESA-001",
  "consulta_literal": "weekly review meetings",
  "total_coincidencias": 0,
  "candidatos": [],
  "respuesta_semantica_generada": false
}
```

Zero candidates. Your first reaction might be "it's broken". It is not — three
engine rules make this the correct, expected answer on a brand-new vault:

1. `brain_query` returns **candidate blocks from knowledge notes only**: notes
   of business entity types and D/X documents. A fresh vault holds only
   infrastructure (`mapa`, `control`, `sistema`) — look back at
   `capas.infraestructura: 7` from step 4.
2. Discovery captures live under `90_Sistema/Descubrimiento/`, and the query
   engine deliberately excludes the `90_Sistema` area: drafts are not yet
   searchable knowledge.
3. The engine never fabricates an answer — `respuesta_semantica_generada` is
   always `false`. What you see is literally what it matched.

So an empty result does **not** prove the knowledge is absent; it proves
nothing is *candidate-ready* yet. This is the designed workflow: capture
preserves the raw finding, and the next steps (discovery
`ce-descubrimiento`, knowledge architecture `ce-arquitectura-conocimiento`,
and drafting D/X documents) turn it into knowledge that queries can retrieve
(see [How to use the bundled skills](../how-to/use-bundled-skills.md)).

The `orientar: true` variant (`texto` = a natural request) orders candidates
by word overlap instead of exact literal match — useful once your vault has
knowledge notes. It still never understands meaning:

```json
brain_query({ "vault": "~/empresas/acme-consultores", "texto": "the client wants weekly review meetings", "orientar": true })
```

## What you have now

- A validated, id-bearing vault: `EMPRESA-001` / *Acme Consultores*.
- A preserved draft finding with its own `CAP-…` id, safely outside any claim
  of approval.
- The mental model: **infrastructure → captures (drafts) → knowledge**.
  Queries only speak to the last layer.

Open the vault in Obsidian and read `Inicio.md` — it is the vault's own
entry point and explains the system in place. When the vault exists and you
want to keep working, do **not** run this tutorial again: follow
[How to continue an existing vault](../how-to/continue-existing-vault.md).
