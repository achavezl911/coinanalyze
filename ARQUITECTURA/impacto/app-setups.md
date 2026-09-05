# Impacto · `app/setups.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

19 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA se calcula subiendo llamadores hasta **k=2**; lo que este mas arriba **no se afirma**.

| funcion | linea | por llamada | por tabla | total |
|---|---|---|---|---|
| [`classify_oi`](#classify-oi) | 162 | 9 | 9 | **16** |
| [`oi_price_reading`](#oi-price-reading) | 228 | 9 | 9 | **16** |
| [`_sign`](#-sign) | 95 | 9 | 0 | **9** |
| [`_bars_closed_beyond`](#-bars-closed-beyond) | 805 | 2 | 0 | **2** |
| [`_breakout_frontier`](#-breakout-frontier) | 741 | 2 | 0 | **2** |
| [`_gap_in`](#-gap-in) | 798 | 2 | 0 | **2** |
| [`_last_pivots`](#-last-pivots) | 927 | 2 | 0 | **2** |
| [`_level_defended`](#-level-defended) | 1003 | 2 | 0 | **2** |
| [`_norm_bars`](#-norm-bars) | 777 | 2 | 0 | **2** |
| [`_obs`](#-obs) | 716 | 2 | 0 | **2** |
| [`_pullback`](#-pullback) | 934 | 2 | 0 | **2** |
| [`_retest_done`](#-retest-done) | 891 | 2 | 0 | **2** |
| [`_returned_inside`](#-returned-inside) | 844 | 2 | 0 | **2** |
| [`_structure_event`](#-structure-event) | 665 | 2 | 0 | **2** |
| [`_tolerance`](#-tolerance) | 762 | 2 | 0 | **2** |
| [`build_setup_context`](#build-setup-context) | 1100 | 2 | 0 | **2** |
| [`evaluate_setup`](#evaluate-setup) | 1218 | 2 | 0 | **2** |
| [`setup_observables`](#setup-observables) | 1057 | 2 | 0 | **2** |
| [`split_hypothesis`](#split-hypothesis) | 88 | 2 | 0 | **2** |

## classify_oi

`app/setups.py:162` · clave completa `app.setups.classify_oi`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 14.</sub>

## oi_price_reading

`app/setups.py:228` · clave completa `app.setups.oi_price_reading`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 14.</sub>

## _sign

`app/setups.py:95` · clave completa `app.setups._sign`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 8.</sub>

## _bars_closed_beyond

`app/setups.py:805` · clave completa `app.setups._bars_closed_beyond`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _breakout_frontier

`app/setups.py:741` · clave completa `app.setups._breakout_frontier`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _gap_in

`app/setups.py:798` · clave completa `app.setups._gap_in`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _last_pivots

`app/setups.py:927` · clave completa `app.setups._last_pivots`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _level_defended

`app/setups.py:1003` · clave completa `app.setups._level_defended`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _norm_bars

`app/setups.py:777` · clave completa `app.setups._norm_bars`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _obs

`app/setups.py:716` · clave completa `app.setups._obs`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 6.</sub>

## _pullback

`app/setups.py:934` · clave completa `app.setups._pullback`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _retest_done

`app/setups.py:891` · clave completa `app.setups._retest_done`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _returned_inside

`app/setups.py:844` · clave completa `app.setups._returned_inside`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _structure_event

`app/setups.py:665` · clave completa `app.setups._structure_event`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _tolerance

`app/setups.py:762` · clave completa `app.setups._tolerance`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## build_setup_context

`app/setups.py:1100` · clave completa `app.setups.build_setup_context`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## evaluate_setup

`app/setups.py:1218` · clave completa `app.setups.evaluate_setup`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## setup_observables

`app/setups.py:1057` · clave completa `app.setups.setup_observables`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## split_hypothesis

`app/setups.py:88` · clave completa `app.setups.split_hypothesis`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

