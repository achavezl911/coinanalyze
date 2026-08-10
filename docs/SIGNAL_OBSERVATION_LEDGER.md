# Signal Observation Ledger

## Objetivo

`signal_observation` es el corpus de investigación **inmutable** de CoinAnalyze.
Guarda lo que el sistema sabía y decidió en vivo. No reconstruye después qué
"habría debido saber" usando datos recuperados o una versión nueva de la lógica.

```text
conocimiento disponible en vivo != histórico corregido posteriormente
```

Ese contrato será la base de forward outcomes, replay, backtesting y calibración
sin hindsight/look-ahead.

## Relación con lo que ya existe

`scalp_signal_snapshot` continúa siendo el snapshot operacional de alta
frecuencia: se publica aproximadamente cada 10 s y conserva su retención corta.

`daily_verdict` sigue siendo un resumen por sesión y no se modifica en PR4.

`scripts/calibrate_signals.py` tampoco se modifica. Hoy calibra contra el
histórico corto; PR5 utilizará el ledger durable para materializar outcomes.

## Muestreo

PR4 usa dos razones de muestreo que pueden coexistir en una misma fila:

- `is_periodic=true`: máximo una fila por símbolo y minuto UTC. Incluye
  `No Trade` y estados no evaluables para evitar selection bias.
- `is_transition=true`: la decisión semántica cambió respecto de la última
  observación durable (`decision_status`, dirección, actionable, estado o
  confianza).

Si el cambio ocurre en la primera evaluación almacenada del minuto, una sola
fila puede tener ambos flags en `true`; no se duplica evidencia idéntica.

El fingerprint no cambia por pequeñas variaciones de score. Esas variaciones
quedan representadas por el muestreo periódico sin convertirse en falsos
episodios.

No existe backfill. Si el proceso o el servidor estuvo apagado, la ausencia de
filas es la verdad: CoinAnalyze no observó ni decidió durante ese intervalo.

## Evaluabilidad

Una señal y una falta de datos son cosas distintas:

- Long Momentum / Long Pullback con evidencia suficiente:
  `evaluable,long,true`.
- Short Momentum / Short Rejection con evidencia suficiente:
  `evaluable,short,true`.
- `No Trade` con book sano y cobertura suficiente:
  `evaluable,neutral,false`.
- book stale/missing, cobertura < 50 %, `Sin datos suficientes` o estado
  desconocido:
  `not_evaluable,unavailable,false`.

Así un fail-closed operacional nunca entrena investigación como "mercado
neutral".

## Evidencia

`evidence` congela el diccionario completo devuelto por
`compute_scalp_summary()` en JSON canónico. `None` permanece `null` y
NaN/Infinity se rechazan.

También se materializan columnas útiles para futuras consultas:

- scores y coverage;
- state/confidence/direction;
- precio de referencia y procedencia;
- último `metrics_snapshot` no futuro con regime/cutoffs;
- generación y shard del collector;
- versiones de lógica, evidencia y sampling.

El snapshot de métricas adjunto siempre cumple `metrics_snapshot.ts <=
observed_at`.

## Precio de referencia

Prioridad:

1. futuros realtime `combined`, únicamente si la pata futures está fresca según
   `basis_detail`;
2. la pata explícita `ohlcv_price` de 1 min cerrado;
3. `NULL`.

Spot nunca sustituye el precio de referencia de una señal de futuros.

PR4 expone `ohlcv_price` dentro de `scalp_context` porque el campo existente
`price` es un `COALESCE(futures_realtime, ohlcv)`: si hubiera un futures stale,
usar `price` como fallback mentiría sobre la procedencia.

## Inmutabilidad

PostgreSQL rechaza:

- `UPDATE`;
- `DELETE`;
- `TRUNCATE`.

La primera fila `is_periodic=true` de cada
`(symbol, signal_family, observed_minute)` gana. No se reescribe historia.

## Fencing y aislamiento operacional

El ledger se escribe dentro del mismo `fenced_transaction()` que publica
`scalp_signal_snapshot`, por lo que un owner viejo no puede escribir historia.

Cada intento del ledger usa además un savepoint. Un defecto exclusivo de la
función de investigación no revierte el snapshot operacional; se registra el
error y deja de avanzar `LAST_FLUSH["ledger"]`. El heartbeat `scalp` se degrada
si ese fallo persiste. Así investigación no tumba el pipeline operacional, pero
su fallo tampoco queda silencioso.

## Versionado

- `logic_version`: semántica de `compute_scalp_summary`.
- `evidence_version`: contrato del JSON guardado.
- `sampling_version`: contrato de muestreo.

Un cambio material futuro debe incrementar la versión correspondiente. El
análisis no debe mezclar versiones implícitamente.

## Retención

PR4 conserva `signal_observation` indefinidamente.

La tabla comienza como PostgreSQL ordinaria. No entra en la allowlist temporal
de PR3 y `cleanup_expired_rows()` no la toca.

Con tres símbolos, la base periódica es ~4,320 filas/día (~1.58 M/año), más
transiciones. Se medirá el crecimiento real antes de decidir particionado o
archive.

## Rollback

Es un cambio aditivo. Una versión previa de la aplicación ignora la tabla, por
lo que rollback de aplicación no requiere destruirla.

No existe down migration destructivo: borrar el ledger destruiría el corpus que
PR4 pretende preservar.

## PR5

PR5 quedó implementado en [`SIGNAL_OUTCOMES.md`](SIGNAL_OUTCOMES.md).
Los outcomes se vinculan por `observation_id`; la observación original nunca
se recalcula ni modifica.

## PR6

PR6 quedó implementado en [`SIGNAL_REPLAY.md`](SIGNAL_REPLAY.md). Cada nueva
observación PR4 congela también el `scalp_context` exacto que produjo su
evidencia. No existe backfill de contextos históricos.
