from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)

PARTITIONED_TEMPORAL_TABLES = frozenset(
    {
        "futures_trades_realtime",
        "spot_trades_realtime",
        "orderbook_snapshot",
        "liquidations_realtime",
        "scalp_signal_snapshot",
        # OF-1 (app/orderflow.py). Tambien en las dos copias vivas de las funciones de sql/schema.sql.
        "orderflow_celda",
        "orderflow_cinta",
        # OF-1b (campana 149): las celdas sumadas por hora. Igual que orderflow_celda.
        "orderflow_celda_hora",
        # OF-4a (app/libro.py). Tambien en las dos copias vivas de las funciones de sql/schema.sql.
        "libro_foto",
        # 151-A (app/libro_honda.py). Igual que libro_foto.
        "libro_honda",
    }
)

# CINTA R1 (V-02). La retencion va en dos tiempos y ninguno puede deshacer al otro: (1) las particiones enteras
# caducadas se tiran en SU transaccion, corta (DROP); (2) las filas caducadas de la particion del borde se borran por
# tramos de BLOQUES_POR_TRAMO bloques de heap (ctid), cada tramo en su transaccion, hasta PRESUPUESTO_S por llamada:
# lo que no quepa queda para la vuelta siguiente. Antes era una sola sentencia SQL (apply_temporal_retention de
# sql/schema.sql): el DELETE del borde de orderflow_cinta pasaba de los 30 s de command_timeout del pool, y el
# ROLLBACK deshacia tambien el DROP, asi que no se podaba nada nunca (140, 11-22/11-23).
# El tramo va por ctid y no por un indice porque las diez tablas no comparten ninguno con ts en cabeza: cada tramo lee
# 16 MB de heap como mucho (~125 mil filas de cinta), muy por debajo del statement_timeout de 20 s del pool.
BLOQUES_POR_TRAMO = 2048
PRESUPUESTO_S = 60.0

HIJAS_EN_CORTE_SQL = """
SELECT c.relname, pg_relation_size(c.oid) / current_setting('block_size')::bigint AS bloques
  FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
 WHERE i.inhparent = to_regclass(format('%I.%I', current_schema(), $1::text))
   AND c.relname ~ ('^' || $1::text || '_p[0-9]{8}$')
   AND to_date(right(c.relname, 8), 'YYYYMMDD')::timestamp AT TIME ZONE 'UTC' < $2
 ORDER BY c.relname"""


class _ExecuteConnection(Protocol):
    async def execute(self, query: str, *args: object) -> str: ...


class _RetentionConnection(_ExecuteConnection, Protocol):
    async def fetchval(self, query: str, *args: object) -> Any: ...

    async def fetch(self, query: str, *args: object) -> list[Any]: ...

    def transaction(self) -> AbstractAsyncContextManager[Any]: ...


@dataclass(frozen=True)
class Poda:
    corte: datetime
    tiradas: int
    borradas: int
    completa: bool


async def ensure_temporal_partitions(conn: _ExecuteConnection) -> None:
    """Create the current and next UTC daily partitions under one DB lock."""
    await conn.execute("SELECT ensure_temporal_partitions()")


async def apply_temporal_retention(
    conn: _RetentionConnection,
    table: str,
    retention_hours: int,
    *,
    tope: datetime | None = None,
    transaccion: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
) -> Poda:
    """Drop complete expired partitions in their own transaction, then trim the boundary one by bounded batches.

    `transaccion` abre cada paso (por defecto conn.transaction; los servicios pasan su fenced_transaction). Si el
    llamador ya tiene una transaccion abierta, cada paso es un SAVEPOINT y nada se confirma por separado: solo
    daily_agg lo hace, y ahi lo acota el presupuesto. `tope` adelanta el corte (lo que aun no se puede tirar)."""
    if table not in PARTITIONED_TEMPORAL_TABLES:
        raise ValueError(f"table is not managed by temporal partitioning: {table}")
    if retention_hours <= 0:
        raise ValueError("retention_hours must be positive")
    tx = transaccion or conn.transaction
    async with tx():
        corte = await conn.fetchval(
            "SELECT statement_timestamp() - make_interval(hours => $1)", retention_hours
        )
        if tope is not None and tope < corte:
            LOGGER.warning("temporal_retention_tope table=%s corte=%s tope=%s", table, corte.isoformat(),
                           tope.isoformat())
            corte = tope
        await conn.execute("SELECT ensure_temporal_partitions()")
        tiradas = await conn.fetchval("SELECT drop_expired_temporal_partitions($1, $2)", table, corte)
    borradas = 0
    t0 = time.monotonic()
    for hija in await conn.fetch(HIJAS_EN_CORTE_SQL, table, corte):
        for desde in range(0, hija["bloques"], BLOQUES_POR_TRAMO):
            if time.monotonic() - t0 >= PRESUPUESTO_S:
                LOGGER.warning("temporal_retention_partial table=%s tiradas=%d borradas=%d hija=%s bloque=%d de %d",
                               table, tiradas, borradas, hija["relname"], desde, hija["bloques"])
                return Poda(corte, tiradas, borradas, False)
            async with tx():
                borradas += await conn.fetchval(
                    "SELECT podar_temporal_tramo($1, $2, $3, $4, $5)",
                    table, hija["relname"], corte, desde, BLOQUES_POR_TRAMO,
                )
    return Poda(corte, tiradas, borradas, True)
