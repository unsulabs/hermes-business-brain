# Reference — cerebro.py CLI (subcommands not exposed as plugin tools)

`cerebro.py` is the native English engine's CLI front-end (29 subcommands
registered via `add_parser`; verified: `grep -c "add_parser(" cerebro.py` →
29). Twelve of them back plugin tools — see [`tools.md`](tools.md). The other
**17** are **not exposed as a plugin tool in this release**: no `brain_*`
tool wraps them, and the plugin ships **no subprocess launcher** (there is no
`run_script.py`; the engine ops are called in-process). The engine may invoke
the system `git` binary, argv-only with no shell, for two structural checks
(bank/existing-Git location probes and `git archive` product export). A
bundled skill may document one of them as running through the engine API
(only when the skill's contracts and tests actually cover it); otherwise they
are reachable only through the engine's own `cerebro.py` CLI.

> Note on the help text: the "Purpose" column below is taken from
> `cerebro.py`'s `help=` strings directly, not paraphrased from elsewhere.

## Status

These are CLI subcommands, not plugin tools. Their behavior, flags and
messages are defined by the engine's `cerebro.py`. Bundled skills reference
them only with the explicit label "upstream CLI subcommand, not exposed as a
v2 plugin tool" — this keeps the skill layer honest: it never pretends an
unexposed subcommand is a tool, and it never invents a plugin launcher path.

## Subcommands not exposed as plugin tools (17)

| Subcommand | Purpose (English) | Key flags (verified in cerebro.py) | Notes |
| --- | --- | --- | --- |
| `fuente` | Register a reference to a source without copying the original document. | `--vault --id --titulo --localizador --clase [--lectura --fecha-evento]` | Conceptually related: `brain_references` (private custody bank registry). |
| `previsualizar-dx` | Simulate a D/X modification without writing. | `--vault --doc-id --archivo [--fuente …]` | Complements `brain_dx_apply` (which applies after authorization). |
| `preparar-dx` | Save a D/X proposal without modifying the current document. | `--vault --doc-id --archivo [--fuente …]` | Complements `brain_dx_apply`. |
| `restaurar-dx` | Restore a D/X version as a new revision after authorization. | `--vault --doc-id --historial --sha-actual --responsable --referencia-autorizacion --respaldo` | |
| `evaluar-dx` | Record an editorial evaluation (G1–G7) without modifying the D/X. | `--vault --doc-id --acta --sha-actual` | |
| `aprobar-dx` | Full editorial promotion with evaluation, authorization and backup. | `--vault --evaluacion --sha-actual --responsable --referencia-autorizacion --respaldo --confirmacion` | |
| `relacion-proponer` | Create a typed-edge proposal; never approve it. | `--vault --origen --destino --predicado --fuente … --ambito --motivo` | |
| `relacion-confirmar` | Record human ratification of a relation. | `--vault --relacion-id --sha-relacion --revisor --referencia-autorizacion --confirmacion` | |
| `aceptacion` | Pilot preflight: structural read, not human approval. | `--vault` | |
| `continuidad` | Record a session close to recover context later. | `--vault --resumen --siguiente [--revisado-por]` | |
| `validar` | Validate integrity of notes, ids, links and transfers — NOT business truth. | `--vault` | See the naming trap below. |
| `buscar` | Textual search with sources, without inferences. | `--vault --texto [--limite]` | Related: `brain_query`. |
| `autoridad` | Strict query by topic/scope/date declared in an imported contract. | `--vault --tema --ambito [--fecha]` | |
| `importar` | Import a vNext-0.9 manifest; non-destructive. | `--vault --manifest [--permitir-real]` | |
| `publicar-mapa` | Publish only the derived map, with exact SHA and external backup. | `--vault --sha-actual --sha-propuesto --confirmacion --respaldo` | Related: `brain_knowledge_map` (preview; publish mode implements these gates). |
| `grafo` | Export typed internal relations and hyperlinks (writes `90_Sistema/grafo.json` inside the vault by default). | `--vault [--output]` | |
| `tipos` | Show the candidate model's available types and distinctions. | `[--tipo]` | |

## Subcommands that ARE exposed as plugin tools (12)

| Subcommand | Plugin tool |
| --- | --- |
| `doctor` | `brain_doctor` |
| `crear` | `brain_create_vault` |
| `estado` | `brain_status` |
| `capturar` | `brain_capture` |
| `consulta-contextual` | `brain_query` |
| `relaciones` | `brain_relations` |
| `mapa-conocimiento` | `brain_knowledge_map` |
| `ficha` | `brain_card` |
| `proponer` | `brain_propose` |
| `plan-conocimiento` | `brain_knowledge_plan` |
| `documento` | `brain_document` |
| `aplicar-dx` | `brain_dx_apply` |

## Two naming traps

- **`validar` (cerebro) vs `validar_boveda.py`**: `brain_validate_vault` does
  NOT run `cerebro.py validar` — it runs the standalone
  `validar_boveda.py` logic. Both check integrity; the tool's backing is the
  standalone one.
- **`buscar` appears twice**: `cerebro.py buscar` (above, not exposed) is a
  text search over a vault; `transcripciones.py buscar` is a
  `brain_transcript_cycle` step that assembles a query context package. They
  are different commands in different scripts.
