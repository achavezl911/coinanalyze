# Impacto · `app/external_macro.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

17 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA se calcula subiendo llamadores hasta **k=2**; lo que este mas arriba **no se afirma**.

| funcion | linea | por llamada | por tabla | total |
|---|---|---|---|---|
| [`_get`](#-get) | 472 | 0 | 11 | **11** |
| [`parse_bls_calendar`](#parse-bls-calendar) | 113 | 0 | 11 | **11** |
| [`parse_coinglass_etf`](#parse-coinglass-etf) | 88 | 0 | 11 | **11** |
| [`parse_fomc_calendar`](#parse-fomc-calendar) | 150 | 0 | 11 | **11** |
| [`parse_fred_csv`](#parse-fred-csv) | 58 | 0 | 11 | **11** |
| [`parse_stablecoin_history`](#parse-stablecoin-history) | 74 | 0 | 11 | **11** |
| [`refresh_external_macro`](#refresh-external-macro) | 478 | 0 | 11 | **11** |
| [`_direction`](#-direction) | 190 | 3 | 0 | **3** |
| [`_metric`](#-metric) | 205 | 3 | 0 | **3** |
| [`_pct_change`](#-pct-change) | 184 | 3 | 0 | **3** |
| [`_pillar`](#-pillar) | 232 | 3 | 0 | **3** |
| [`_plain_html`](#-plain-html) | 146 | 0 | 3 | **3** |
| [`_state`](#-state) | 197 | 3 | 0 | **3** |
| [`_unfold_ics`](#-unfold-ics) | 103 | 0 | 3 | **3** |
| [`align_with_internal`](#align-with-internal) | 415 | 3 | 0 | **3** |
| [`build_external_macro_context`](#build-external-macro-context) | 237 | 3 | 0 | **3** |
| [`external_macro_context`](#external-macro-context) | 437 | 3 | 0 | **3** |

## _get

`app/external_macro.py:472` · clave completa `app.external_macro._get`

**Radio total: 11 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 11 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## parse_bls_calendar

`app/external_macro.py:113` · clave completa `app.external_macro.parse_bls_calendar`

**Radio total: 11 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 11 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## parse_coinglass_etf

`app/external_macro.py:88` · clave completa `app.external_macro.parse_coinglass_etf`

**Radio total: 11 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 11 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## parse_fomc_calendar

`app/external_macro.py:150` · clave completa `app.external_macro.parse_fomc_calendar`

**Radio total: 11 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 11 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## parse_fred_csv

`app/external_macro.py:58` · clave completa `app.external_macro.parse_fred_csv`

**Radio total: 11 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 11 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## parse_stablecoin_history

`app/external_macro.py:74` · clave completa `app.external_macro.parse_stablecoin_history`

**Radio total: 11 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 11 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## refresh_external_macro

`app/external_macro.py:478` · clave completa `app.external_macro.refresh_external_macro`

**Radio total: 11 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 11 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _direction

`app/external_macro.py:190` · clave completa `app.external_macro._direction`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _metric

`app/external_macro.py:205` · clave completa `app.external_macro._metric`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _pct_change

`app/external_macro.py:184` · clave completa `app.external_macro._pct_change`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _pillar

`app/external_macro.py:232` · clave completa `app.external_macro._pillar`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _plain_html

`app/external_macro.py:146` · clave completa `app.external_macro._plain_html`

**Radio total: 3 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

**3 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _state

`app/external_macro.py:197` · clave completa `app.external_macro._state`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _unfold_ics

`app/external_macro.py:103` · clave completa `app.external_macro._unfold_ics`

**Radio total: 3 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

**3 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## align_with_internal

`app/external_macro.py:415` · clave completa `app.external_macro.align_with_internal`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## build_external_macro_context

`app/external_macro.py:237` · clave completa `app.external_macro.build_external_macro_context`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## external_macro_context

`app/external_macro.py:437` · clave completa `app.external_macro.external_macro_context`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

