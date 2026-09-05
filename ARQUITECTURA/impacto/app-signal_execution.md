# Impacto · `app/signal_execution.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

9 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`load_signal_execution_inputs`](#load-signal-execution-inputs) | 410 | 0 | **0** | 10 ↑ | **0** |
| [`persist_signal_execution_snapshots`](#persist-signal-execution-snapshots) | 429 | 0 | **1** | 10 ↑ | **1** |
| [`_canonical_json`](#-canonical-json) | 139 | 0 | **0** | 6 ↑ | **0** |
| [`execution_snapshot_record`](#execution-snapshot-record) | 263 | 0 | **0** | 6 ↑ | **0** |
| [`_aware_utc`](#-aware-utc) | 127 | 0 | **0** | 1 ↑ | **0** |
| [`_cost_curve`](#-cost-curve) | 245 | 0 | **0** | 1 ↑ | **0** |
| [`_decode_depth_levels`](#-decode-depth-levels) | 168 | 0 | **0** | 1 ↑ | **0** |
| [`_hash_book_payload`](#-hash-book-payload) | 150 | 0 | **0** | 1 ↑ | **0** |
| [`_ordered_depth`](#-ordered-depth) | 189 | 0 | **0** | 1 ↑ | **0** |

## load_signal_execution_inputs

`app/signal_execution.py:410` · clave completa `app.signal_execution.load_signal_execution_inputs`

**Radio exacto: 0 rutas** de 68 · **cota superior: 10** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 10 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (10 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**10 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_signal_execution_snapshots

`app/signal_execution.py:429` · clave completa `app.signal_execution.persist_signal_execution_snapshots`

**Radio exacto: 1 rutas** de 68 · **cota superior: 10** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 1 rutas · **exacto**

Escribe **ella misma**: `signal_execution_snapshot`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

### Por tabla · k<=2 — 10 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (10 contra 1). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**10 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _canonical_json

`app/signal_execution.py:139` · clave completa `app.signal_execution._canonical_json`

**Radio exacto: 0 rutas** de 68 · **cota superior: 6** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 6 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (6 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

Y esas tablas las leen:

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

**6 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## execution_snapshot_record

`app/signal_execution.py:263` · clave completa `app.signal_execution.execution_snapshot_record`

**Radio exacto: 0 rutas** de 68 · **cota superior: 6** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 6 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (6 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`
- `signal_outcome` — la escribe `app.signal_outcomes.schedule_signal_outcomes`
- `signal_replay_frame` — la escribe `app.signal_replay.persist_signal_replay_frame`

Y esas tablas las leen:

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

**6 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _aware_utc

`app/signal_execution.py:127` · clave completa `app.signal_execution._aware_utc`

**Radio exacto: 0 rutas** de 68 · **cota superior: 1** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 1 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (1 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _cost_curve

`app/signal_execution.py:245` · clave completa `app.signal_execution._cost_curve`

**Radio exacto: 0 rutas** de 68 · **cota superior: 1** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 1 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (1 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _decode_depth_levels

`app/signal_execution.py:168` · clave completa `app.signal_execution._decode_depth_levels`

**Radio exacto: 0 rutas** de 68 · **cota superior: 1** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 1 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (1 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _hash_book_payload

`app/signal_execution.py:150` · clave completa `app.signal_execution._hash_book_payload`

**Radio exacto: 0 rutas** de 68 · **cota superior: 1** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 1 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (1 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _ordered_depth

`app/signal_execution.py:189` · clave completa `app.signal_execution._ordered_depth`

**Radio exacto: 0 rutas** de 68 · **cota superior: 1** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 1 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (1 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `signal_execution_snapshot` — la escribe `app.signal_execution.persist_signal_execution_snapshots`

Y esas tablas las leen:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

