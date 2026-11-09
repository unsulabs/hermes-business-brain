# hermes_business_brain/data

English-native data payload for the **Hermes Business Brain** engine (v2 re-engineering).
All user-facing content shipped in this directory is **English** — vault template notes,
schema metadata, base view labels — while every machine contract is preserved.

## Layout

| Path | Contents | Provenance |
|---|---|---|
| `plantilla_boveda/` | Complete Obsidian vault template: `Inicio.md`, `00_Mapas/`, `90_Sistema/` (Auxiliary notes, `Plantillas/` — 47 note templates, `Vistas/` — 16 Obsidian Bases), `config_empresa.yaml`, `.obsidian/templates.json` | the product's `plantilla_boveda/` (English translation; keys/filenames preserved) |
| `modelo/` | Canonical model: `clases_documentales.json` (D01–D07, X01–X07), `tipos_entidad.json` (27 types), `rutas_de_inicio.json` (6 start routes), `transcripciones/*.schema.json` (19 JSON Schemas) | the product's `modelo/` — schemas already English, bundled verbatim |
| `recursos/` | `bases_baseline.json` (sha256 baseline of the 16 `.base` views), `registro_plugins.json` (plugin evaluation registry) | the product's `recursos/` |

The engine exposes `modelo`, `recursos`, and `plantilla_boveda` at the repository root via
symlinks back to `data/`, so relative paths such as `plantilla_boveda/90_Sistema/Plantillas`
and the `path` values in `bases_baseline.json` are untouched.

## What was translated (Spanish → English)

- All human-facing markdown prose: body text, headings, template fill-in instructions,
  expert questions, section skeletons, and the `**Represents:**` / `**Do not confuse with:**`
  definition blocks in the note templates.
- JSON human-facing value fields: `nombre`, `encabezados`, `elicitacion`,
  `contenido_obligatorio` (clases_documentales), `representa`, `no_confundir`,
  `contenido_minimo`, `pregunta_de_prueba`, `descripcion` (tipos_entidad),
  `identificar`, `primer_trabajo`, `peligro`, `principio` (rutas_de_inicio),
  and `politica`/`instalacion`/`aplica`/`limites`/`nombre` (registro_plugins).
- Obsidian Base view display names (`name:`) — e.g. `Tabla` → `Table`, `Tablero` → `Board`,
  `Tarjetas` → `Cards`. Filters, orders, and property expressions are untouched.

## Keys-preserved guarantee

The following are **byte-identical** to the upstream source:

- folder and file names (incl. `Inicio.md`, `00_Mapas`, `90_Sistema`, `Plantillas/*.md`, `*.base`)
- YAML/markdown frontmatter **keys and enum values** (`id`, `tipo`, `clase`, `doc_id`,
  `estado_editorial: borrador`, `sensibilidad: interno`, …)
- all JSON keys at every nesting level, plus ID/enum values (`D01…X07`, `familia`,
  `expediente_condicional`, `situacion` route IDs, `carpeta` folder names, `prefijo` codes,
  `relaciones_candidatas`, `campos_comunes`, `estado_inicial` enums, schema `$defs`/properties)
- template tokens (`{{EMPRESA_NOMBRE}}`, `{{EMPRESA_ID}}`, `{{title}}`, `PENDIENTE_ID_UNICO`)
- paths referenced in prose and in `lectura_referencia` (`metodologia/vNext-1.0R/…`),
  command tokens (`scripts/cerebro.py`, `mapa-conocimiento`, gates `G1–G7`, classes `K1–K4`,
  flows `iniciar-empresa`, `publicar-mapa`)
- `plantilla_boveda/90_Sistema/config_empresa.yaml` and `.obsidian/templates.json` verbatim.

**One intentional recomputation:** `recursos/bases_baseline.json` sha256 values were
recomputed over the shipped (translated) `.base` files, because translating view display
names changes the file contents. Paths, key structure, and semantics are unchanged;
without this the baseline would drift on first check.

No private-key material exists in this payload (repo-wide catalog rule: no contiguous
`-----BEGIN … PRIVATE KEY-----` header literal is written anywhere).

## Verification

See `_verify/data-en.md` at the repository root: file counts, JSON parse checks with
before/after top-level keys, deep key signatures, base-view diffs, and a sample of the
translated prose.
