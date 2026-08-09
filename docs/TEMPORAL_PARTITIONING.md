# Particionado temporal realtime

Las tablas `futures_trades_realtime`, `spot_trades_realtime`,
`orderbook_snapshot`, `liquidations_realtime` y `scalp_signal_snapshot` usan
particiones diarias UTC por rango de `ts`. `orderbook_depth` no se particiona:
representa únicamente el estado actual y conserva una fila por símbolo y venue.

`ensure_temporal_partitions()` crea de forma idempotente el día anterior, el día
actual y los dos días siguientes. Cada servicio la ejecuta al abrir su pool; un
advisory lock transaccional serializa arranques concurrentes. Los lectores y
escritores siguen usando exclusivamente el nombre lógico de la tabla padre.

La retención llama a `apply_temporal_retention()`. Primero elimina solamente
particiones cuyo límite superior completo ya está fuera de retención y después
borra las filas expiradas de la partición que cruza el cutoff. Las duraciones no
cambian.

## Unicidad de liquidaciones

PostgreSQL exige que una clave única de una tabla particionada incluya la clave
de partición. Por ello la PK física pasa de `(exchange,event_id)` a
`(exchange,event_id,ts)`. El trigger
`liquidations_realtime_event_unique_trigger` conserva la semántica más fuerte de
unicidad global por `(exchange,event_id)`: toma un advisory lock para esa
identidad y convierte duplicados, incluso en días distintos, en no-ops.

## Migración y rollback

`20260809_temporal_partitioning.sql` bloquea las cinco fuentes, crea reemplazos,
copia filas y verifica `COUNT/MIN/MAX`, columnas, constraints e índices antes de
hacer el swap. Las tablas originales quedan como
`*_unpartitioned_backup`.

El rollback compara padre y backup en ambas direcciones con `EXCEPT ALL`. Solo
revierte si son idénticos; cualquier escritura o retención posterior hace que
falle explícitamente para evitar pérdida de datos.
