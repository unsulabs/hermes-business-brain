# Explanation -- Privacy and guardrails: the product's invariants as implemented

This page states the invariants the product is built around. They are not
aspirations: each one is enforced or mandated in code and in the bundled
skills, and each is listed here with the evidence. The primary sources are
`ce-instalacion`, `ce-consulta`, `ce-banco-transcripciones`, `obsidian-router`
and the product posture this plugin inherits.

## 1. User authorization is the gate

Nothing that touches another system starts without the user's authorization.

- The *expressed request to install and build the business* authorizes the
  necessary operations within the chosen location -- permissions already
  granted are not asked again.
- Anything beyond that is gated: **ask before publishing data, sending
  messages, installing external plugins, or using another account**
  (`ce-instalacion`).
- Explicitly forbidden without consent: installing external plugins, changing
  Obsidian's security mode without explaining, and uploading business data to
  Git (`ce-instalacion`'s Forbidden list). "Don't import authorizations nor
  pilot profiles into a new instance."
- Destructive or authority-touching operations demand *specific*
  authorization plus artifacts: applying a D/X revision requires the
  proposal id, exact SHA-256s of original and candidate, the responsible
  person, an authorization reference and a backup directory
  (`brain_dx_apply`, the `aplicar-dx` flow); confirming a relation requires a
  `--confirmacion` string; installing never implies approval to touch
  content.

## 2. NO VERIFICADO discipline

Unverified is a first-class status, not a failure state to paper over.

- After installation, the agent reports **six surfaces separately** -- code,
  Python, Obsidian GUI, Bases, private instance, sources/connectors -- and
  marks `NO VERIFICADO` where appropriate (`ce-instalacion`).
- If the GUI or the router cannot confirm the vault path, the integration is
  marked `NO VERIFICADO`, the instance kept, and only independently
  authorized work outside the vault continues. "Don't close the commission
  by installing."
- A check that merely *passed tests* is not proof: "declaring the brain
  complete for having passed unit tests" is forbidden.
- The resolver must return `status: selected` and
  `native_registry_verified: true` before a vault is treated as resolved;
  registration "does not prove GUI/Bases function or editorial permission"
  (`obsidian-router`).

## 3. Source over summary

Authority lives in the original record, not in summary notes.

- A record card (`brain_card`, the engine's `ficha` command) "locates an original,
  but doesn't substitute for it" (`ce-consulta`). `lectura: leida_completa`
  on a card documents an *earlier* reading -- it is not a reading in this
  session.
- Before citing, the agent must contrast each claim against the original with
  a reading operation actually executed in this session, and separate claim
  owner, experience context/date, editorial version, task coverage and
  currency.
- New sources are registered with a reading status (default `no_verificada`)
  rather than assumed read (`fuente --lectura`; upstream CLI subcommand, not
  exposed as a v2 plugin tool -- `brain_references` covers the private
  custody-bank registry).
- If only the card was opened, the answer cites the card and says the
  original was not re-checked. Nothing is cited as read unless it was read.

## 4. ID resolution over display names

The vault you operate on is decided by explicit identity checks, never by
what "sounds right".

- Access requires an explicit selector -- name, ID, alias or absolute path --
  or an explicitly associated project. "Never select by the active window or
  guess a destination" (`obsidian-router`).
- `brain_resolve_vault` compares the local registry's ID and path against
  Obsidian's native registry and "rejects absent/ambiguous matches and
  symlinks". It must run before any `rg`, `ls`, `cat`, CLI or other read
  inside the vault -- "the path in the prompt does not replace that check"
  (`ce-consulta`).
- "Never fabricate a native file or ID to pass a check." A failed resolution
  is reported exactly, with work preserved outside the vault; it is never
  bypassed by overwriting registration or installing another skill.

## 5. Rejected legacy

Rejected material has no authority and no second life.

- "Rejected editorial texts are never authority nor draft for reconstructing
  the answer" (`ce-consulta`). Editorial rejection is terminal: it cannot be
  laundered back into an answer or a new draft.

## 6. No real business data in the repo

This repository is a product, not a warehouse.

- All templates, schemas and demo content shipped are **synthetic by design**
  -- no real business data ever (README privacy invariants).
- Captures and transcript banks must live **outside any vault and any Git
  worktree** (enforced by the engine, stated in the README invariants).
- "Never copy `ejemplos` nor data from another instance into a real
  business" (`ce-instalacion`).

## 7. Vault operations only on provided paths

The engine has no hardcoded absolute user paths (verified: no `Users/`-style
paths in `hermes_business_brain/engine/`).

- Every tool takes vault/bank/file paths as arguments; nothing is touched
  implicitly except the selector and Obsidian native registries, whose paths can be
  overridden with `registry`/`nativo`.
- Banks are validated to be outside any vault and Git worktree
  (`UNSAFE_PATH` is a defined pipeline error in `ce-banco-transcripciones`).
- The resolver reads only registry metadata, never vault content.

## 8. Proposal is not decision

The pipeline separates *recording a proposal* from *establishing knowledge*,
and nothing collapses the two.

- `brain_capture` saves findings "without declaring them approved knowledge";
  `brain_document` registers a D/X "without approving it" (draft by default);
  `brain_propose` "does NOT touch the original note"; `relacion-proponer`
  (upstream CLI subcommand) "creates a typed-edge proposal, never approve it".
- Human ratification is a separate, explicit act (`relacion-confirmar`,
  upstream CLI subcommand), guarded by confirmation strings and
  authorization references.
- Creation never overwrites: `brain_create_vault` fails if the destination
  exists, and a correction creates a version rather than replacing bytes
  (`ce-banco-transcripciones`: "A correction creates a version, doesn't
  replace bytes").

## Supporting epistemic guardrails

Two additional rules from `ce-consulta` shape outputs:

- **Negative-proof discipline**: an empty search result does not prove
  absence of knowledge (try synonyms, human names, the map); "without an
  admissible financial record, express 'billing/payment not substantiated' --
  don't record zero nor infer it didn't happen."
- **Don't claim what wasn't exercised**: "don't claim pending CLI
  capabilities"; don't claim a Python interpreter failed if it wasn't tested
  in this session; interest is not hiring, a recommended conversation is not
  a held one.
