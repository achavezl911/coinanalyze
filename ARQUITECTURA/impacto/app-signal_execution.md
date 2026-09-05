# Impacto · `app/signal_execution.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

9 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA se calcula subiendo llamadores hasta **k=2**; lo que este mas arriba **no se afirma**.

| funcion | linea | por llamada | por tabla | total |
|---|---|---|---|---|
| [`load_signal_execution_inputs`](#load-signal-execution-inputs) | 410 | 0 | 9 | **9** |
| [`persist_signal_execution_snapshots`](#persist-signal-execution-snapshots) | 429 | 0 | 9 | **9** |
| [`_canonical_json`](#-canonical-json) | 139 | 0 | 5 | **5** |
| [`execution_snapshot_record`](#execution-snapshot-record) | 263 | 0 | 5 | **5** |
| [`_aware_utc`](#-aware-utc) | 127 | 0 | 1 | **1** |
| [`_cost_curve`](#-cost-curve) | 245 | 0 | 1 | **1** |
| [`_decode_depth_levels`](#-decode-depth-levels) | 168 | 0 | 1 | **1** |
| [`_hash_book_payload`](#-hash-book-payload) | 150 | 0 | 1 | **1** |
| [`_ordered_depth`](#-ordered-depth) | 189 | 0 | 1 | **1** |

## load_signal_execution_inputs

`app/signal_execution.py:410` · clave completa `app.signal_execution.load_signal_execution_inputs`

**Radio total: 9 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

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

**9 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## persist_signal_execution_snapshots

`app/signal_execution.py:429` · clave completa `app.signal_execution.persist_signal_execution_snapshots`

**Radio total: 9 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

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

**9 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _canonical_json

`app/signal_execution.py:139` · clave completa `app.signal_execution._canonical_json`

**Radio total: 5 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 5 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

**5 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## execution_snapshot_record

`app/signal_execution.py:263` · clave completa `app.signal_execution.execution_snapshot_record`

**Radio total: 5 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 5 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

**5 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _aware_utc

`app/signal_execution.py:127` · clave completa `app.signal_execution._aware_utc`

**Radio total: 1 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 1 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _cost_curve

`app/signal_execution.py:245` · clave completa `app.signal_execution._cost_curve`

**Radio total: 1 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 1 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _decode_depth_levels

`app/signal_execution.py:168` · clave completa `app.signal_execution._decode_depth_levels`

**Radio total: 1 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 1 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _hash_book_payload

`app/signal_execution.py:150` · clave completa `app.signal_execution._hash_book_payload`

**Radio total: 1 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 1 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _ordered_depth

`app/signal_execution.py:189` · clave completa `app.signal_execution._ordered_depth`

**Radio total: 1 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 1 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

