# PR23 temporal integrity

PR23 aplica tres fronteras prospectivas sin backfill:

- A2-01 rechaza trades y libros con event-time futuro. `scalp_context` resuelve
  un solo `as_of` con el reloj PostgreSQL y todas sus selecciones usan ese mismo
  límite superior; un lag de book negativo nunca es fresh.
- A2-02 lee primero la provenance committed que quedará asociada a una señal y
  obtiene `observed_at` después. No se inventa commit timestamp ni se interpreta
  `metrics_snapshot.ts` como knowledge-time.
- A2-07 pasa un único `as_of` a `structure_detail`, `macro_context`,
  `cross_asset`, `passive_flow` y `trend_matrix`. Las consultas intradía quedan
  acotadas por ese instante y los bloques diarios sólo aceptan la última sesión
  NYSE ya cerrada según el cutoff.

## Alcance histórico de swing

`swing_score.as_of` significa **shared event-time cutoff**. No significa que el
score sea una reconstrucción point-in-time histórica perfecta: en PR23
`daily_session_agg` continúa siendo mutable. El snapshot diario PIT de esa tabla
queda explícitamente fuera de alcance hasta PR24.

## Versiones

- `SIGNAL_EVIDENCE_VERSION = 4`
- `DAILY_VERDICT_LOGIC_VERSION = daily-verdict-v3`
- `SCALP_SIGNAL_LOGIC_VERSION = scalp-summary-v1`
- `SIGNAL_SAMPLING_VERSION = 1`
- `REPLAY_CONTEXT_VERSION = 1`
- `REGIME_LOGIC_VERSION = 2`
- `OUTCOME_VERSION = 1`
- `EXECUTION_SNAPSHOT_VERSION = 1`
- `DAILY_VERDICT_SNAPSHOT_VERSION = 1`

Las constraints de provenance exigen regime v2 (o el bloque de régimen
completamente NULL) para evidence v3/v4 y daily verdict v2/v3. Las filas legacy
no se actualizan.
