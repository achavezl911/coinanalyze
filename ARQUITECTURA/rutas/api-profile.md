# `GET /api/profile`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `trading_profile` · `app/api.py:1605` (cuerpo hasta la 1621) · decorador en la linea 1604.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `profile` | `str` | `'intradia'` | no |

## Campos que publica

14 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/api.py:1619 |
| `bias` | literal en app/scalp_logic.py:4955 |
| `confidence` | literal en app/scalp_logic.py:4957 |
| `contradictions` | literal en app/scalp_logic.py:4961 |
| `coverage_pct` | literal en app/scalp_logic.py:4958 |
| `invalidation` | literal en app/scalp_logic.py:4967 |
| `layers` | literal en app/scalp_logic.py:4959 |
| `missing_data` | literal en app/scalp_logic.py:4962 |
| `net_score` | literal en app/scalp_logic.py:4956 |
| `profile` | literal en app/scalp_logic.py:4953 |
| `profile_label` | literal en app/scalp_logic.py:4954 |
| `reference_only` | literal en app/scalp_logic.py:4960 |
| `symbol` | literal en app/api.py:1618 |
| `weights_note` | literal en app/scalp_logic.py:4963 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `data_gap` — `sql/schema.sql:1412`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1092`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1243`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1262`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1311`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:322`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:584`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:663`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:687`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:798`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
- `choice`
- `edges`
- `exchanges`
- `parts`
- `requested`
- `required`
- `rt_span`
- `source`
- `ts`

## Funciones que la componen

29 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:232`
- `app.scalp_logic.delta_matrix` — `app/scalp_logic.py:4589`
- `app.scalp_logic.profile_view` — `app/scalp_logic.py:4800`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2592`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:6247`

<details><summary>Alcanzables de forma indirecta (24)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2586`
- `app.scalp_logic._flow_bias` — `app/scalp_logic.py:4787`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2604`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2612`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2619`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4376`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4346`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4358`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4557`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4473`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1227`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2372`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2358`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4721`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2868`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.spot_con_guarda` — `app/scalp_logic.py:2807`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2797`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (4)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `HTTPException`
- `app.state.pool.acquire`
- `as_of.isoformat`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:234` | una funcion de su cierre |
| 422 | — | `app/api.py:1609` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | — | `harness/checks/K31-cubos.py:62`, `harness/checks/K43-foto-unica.sh:44`, `harness/checks/K43-foto-unica.sh:118`, `harness/checks/K43-foto-unica.sh:251` _(+2)_ |
| **panel** | — | `static/js/04-flujo-y-libro.js:111` |
| **tests** | `tests/test_v150_desk_snapshot.py:130` | — |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['profile', 'symbol']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**Declarada** en [`declarada/api-profile.md`](../declarada/api-profile.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 65 | **0** | 0 | **65** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 25 | **0** | 12 ↑ | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 21 | **0** | 15 ↑ | **21** | [impacto](../impacto/app-data_gaps.md) |
| `app.metrics.current_nyse_start` | 16 | **0** | 15 ↑ | **16** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 26 | **0** | 0 | **26** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 15 | **0** | 11 ↑ | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 14 | **0** | 11 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._resample_highs_lows` | 15 | **0** | 0 | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_windows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_flow_windows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_and_baseline` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_threshold_seconds` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_too_large` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._contiguous_measured_suffix` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_change_pct` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._realtime_flow` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._complete_tail_values` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._structure_from_swings` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._swings` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.flow_confirmation` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.trend_matrix` | 8 | **0** | 3 ↑ | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_imbalance` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_rate` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.futures_flow_windows` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 5 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
