# Verification evidence - ce-primera-sesion

New bundled skill `ce-primera-sesion` (first-session onboarding) at `hermes_business_brain/skills/ce-primera-sesion/`.

## Files created (10)

- `SKILL.md` - skill body: vault entry, 8 areas as guides, K1-K4 gaps, brain_capture custody, read-only brain_knowledge_plan before drafting, justified D/X development, brain_status + brain_validate_vault close, External AI interview section, invariants.
- `references/area-templates/README.md` - index of the 8 areas with one-line summaries and usage.
- `references/area-templates/area-01-business-model.md`
- `references/area-templates/area-02-market-customers.md`
- `references/area-templates/area-03-offer-commercial.md`
- `references/area-templates/area-04-execution-processes.md`
- `references/area-templates/area-05-economy-finance.md`
- `references/area-templates/area-06-people-roles.md`
- `references/area-templates/area-07-risks-commitments.md`
- `references/area-templates/area-08-direction-decisions.md`

Each template: (a) Purpose, (b) 10 open guided questions (episodes/criteria/exceptions/contrast cases), (c) Signals to capture, (d) D/X + entity-type mapping table with "when NOT to create a doc", (e) External-AI copy-paste prompt (third person, open-ended, no jargon), (f) K1-K4 gap hints.

## Checks (run over all 10 files)

- Relative links: all resolve (checked every `](...)` target exists). `BAD_LINKS: none`
- Tool references: brain_capture, brain_card, brain_create_vault, brain_document, brain_dx_apply, brain_knowledge_map, brain_knowledge_plan, brain_propose, brain_resolve_vault, brain_status, brain_validate_vault - all present in the 18-tool list. `MISSING_TOOLS: none`
- Dead internal paths: no `guia/`, `metodologia/`, `docs/FLUJO_EMPRESA_COMPLETA.md` or similar. `DEAD_PATHS: none`
- English-only: no accented/non-ASCII characters. `NON_ASCII: none` (em/en dashes replaced with ASCII hyphens)
- YAML frontmatter: `name: ce-primera-sesion`, single-line `description:` (parseable by the plugin's `_skill_description`, same format as the 19 siblings).
- Doc-class ids D01-D07 / X01-X07 all referenced; entity ids used exactly as in `tipos_entidad.json`.

## Registration

- `ls hermes_business_brain/skills | wc -l` = 20 (was 19); `register()` globs `*/SKILL.md` under `hermes_business_brain/skills/`, so the skill is bundled at load time as `hermes-business-brain:ce-primera-sesion`.
- `hermes plugins doctor . --ci` -> exit 0; "registrations: 18 tool(s), 0 hook(s)"; "OK: runtime discovery, manifest parsing, import, and registration passed".
- `.venv/bin/python -m pytest tests/ -q` -> `220 passed, 33 skipped, 2 warnings, 24 subtests passed`.

## Commit

`feat(skills): add ce-primera-sesion onboarding skill with 8 area templates` - only `hermes_business_brain/skills/ce-primera-sesion/` and `_verify/ce-primera-sesion.md`.
