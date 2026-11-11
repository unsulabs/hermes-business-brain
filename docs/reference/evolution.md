# Reference: Evolution

The evolution scan (`brain_evolution_scan`) is the read-only mechanism that
turns accumulated material into mature knowledge. This page documents the
tool, the rulebook, and the cadence table.

## brain_evolution_scan

Read-only scan of one vault. Arguments: `vault` (absolute path, required).
Writes nothing.

Returns a JSON document with four sections:

- `fecha` - scan date (ISO).
- `vault` - the scanned path.
- `resumen` - `fuentes` (capture notes under `90_Sistema/Descubrimiento/`),
  `documentos` (`10_Conocimiento/`), `entidades` (`20_Entidades/`).
- `candidatos` - one entry per promotion rule that found any evidence:
  `regla_id`, `nombre`, `accion_propuesta`, `evidencia` (first 5 paths),
  `estado` (`listo` when the rule's required evidence count is met, `parcial`
  otherwise), `por_que_no` (shortfall explanation for `parcial`).
- `visitas_vencidas` - areas whose revisit cadence is due: `area`,
  `ultima_revision` (ISO date or `never`), `cadencia_dias`, `principal`,
  `sugerencia`.

Candidates are proposals, never instructions: promotion happens later through
the existing proposal and apply machinery, only after the owner confirms.

## reglas_evolucion.json

Versioned rulebook at `hermes_business_brain/data/modelo/reglas_evolucion.json`,
loaded at scan time. Two sections:

- `reglas` - promotion rules with `id`, `nombre`, `descripcion`, `condicion`,
  `evidencia_requerida`, `accion_propuesta`, `no_aplicar_si`.
- `cadencia` - per-area revisit cadence with `dias`, `principal` (the D/X that
  anchors the area), `sugerencia`.

## Cadence table

| Area | Principal | Cadence |
| --- | --- | --- |
| business_model | D01 | 75 days and after significant commercial change |
| market_customers | D02 | 75 days and after a new-client wave |
| offer_commercial | D03 | 75 days and after a quote-pattern change |
| execution_processes | D04 | 90 days and after each peak season |
| economy_finance | D05 | 30 days and after each closed event |
| people_roles | D06 | 180 days and after any hire or departure |
| risks_commitments | D07 | 90 days and before high-value events |
| direction_decisions | X07 | 90 days and after each strategic decision |

The rulebook is versioned in the plugin repo: improving the rules improves
every vault that uses the plugin. The scan does not edit the rulebook; propose
rule changes through the normal repository workflow.
