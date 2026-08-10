# Signal Forward Outcomes

`signal_outcome` materializa qué ocurrió después de cada observación inmutable
de PR4. No modifica ni reconstruye `signal_observation`.

## Horizontes

1m, 3m, 5m, 15m, 30m, 1h, 2h y 4h.

## Ventana sin look-ahead

Una vela 1m que contiene el instante de la señal también contiene precio
anterior a la señal. Por ello el path comienza siempre en el primer minuto
completo posterior:

```text
observed_at   09:22:17
window_start  09:23:00
3m window     [09:23, 09:26)
```

`path_start_delay_seconds` registra la fracción de hasta 60 s excluida del
high/low. El retorno final se calcula contra el `reference_price` inmutable de
PR4; MFE/MAE sólo describen el path medido posterior.

## Fuente y cobertura

Sólo se usa `ohlcv` del mismo futures symbol con `interval='1min'`. El ingest
actual usa `ClosedCutoff`, así que PR5 espera dos minutos adicionales antes de
intentar materializar.

Un horizonte N exige exactamente N timestamps consecutivos. Además consulta
PR3 con la identidad exacta `ohlcv_1min/binance/perpetual/symbol`; cualquier
gap `unresolved` o `unrecoverable` solapado bloquea la evaluación aunque las
filas estén presentes. Un gap recuperado deja de bloquear. Gaps de otro
exchange/market/symbol no contaminan el outcome.

No hay nearest fill, interpolación, cero sintético, spot ni sustitución de
venue/feed.

Si falta cualquier barra, el outcome sigue `pending` y reintenta cada 15
minutos durante 7 días. Esto permite ingest/recovery tardío dentro de la
retención OHLCV 1m actual de 14 días. Después se finaliza:

`not_evaluable / incomplete_exact_ohlcv_path_after_grace`.

Si la observación no tenía reference price, se finaliza
`not_evaluable / missing_reference_price`; nunca se busca otro precio a
posteriori.

## Métricas

Para un path completo:
- end_price
- max_high
- min_low
- market_return_pct
- up_excursion_pct
- down_excursion_pct

Para long/short:
- directional_return_pct: positivo = favorable
- mfe_pct: Maximum Favorable Excursion, magnitud no negativa
- mae_pct: Maximum Adverse Excursion, magnitud no negativa

Neutral/unavailable conserva el path de mercado pero deja las métricas
direccionales en NULL.

## Lifecycle

Cada fila nace pending. Pending puede actualizar únicamente intentos,
bars_found, next_attempt_at y su transición final.

Una fila evaluated/not_evaluable es inmutable. DELETE y TRUNCATE también se
rechazan.

## Scheduling y concurrencia

Se agendan ocho jobs para toda observación periódica y para transiciones
accionables. Las transiciones no accionables no multiplican storage: el baseline
periódico ya conserva neutral/no-evaluable sin selection bias.

El scheduling ocurre dentro del mismo savepoint de la observación. Al desplegar
PR5, schema.sql agenda idempotentemente jobs para las observaciones PR4 elegibles
que ya existían; esto no es backfill de señales.

Sólo el shard global materializa outcomes. Los jobs se toman con
`FOR UPDATE ... SKIP LOCKED`, dentro del ServiceOwnership fenced transaction.

Un fallo del worker hace rollback de su savepoint, no del snapshot operacional
ni del ledger, registra `signal_outcome_materialization_failed` y deja de
avanzar `LAST_FLUSH["outcomes"]`; el shard global degrada su heartbeat si el
problema persiste.

## Rollback

Es aditivo. PR4 ignora signal_outcome. Un rollback de aplicación no destruye el
corpus. Al volver a PR5, schema.sql agenda idempotentemente los jobs que falten.

## Fuera de alcance

No cambia API/UI, scores, pesos, daily_verdict, retenciones de PR3 ni
`scripts/calibrate_signals.py`. No hace backtesting, fees/slippage, calibración
probabilística ni ML.
