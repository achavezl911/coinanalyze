"""K16 · los porteros de app/partitioning.py, el unico modulo que BORRA por diseno.

Estos tests NO necesitan base de datos, y eso es deliberado: CI no define hoy
TEST_DATABASE_URL (razonado en .github/workflows/ci.yml), asi que los 167 tests de
persistencia no corren. Si la unica cobertura de este modulo viviera ahi, el modulo que
borra datos seguiria sin vigilancia en la unica suite que se ejecuta de verdad.

Lo que se cubre aqui son los dos porteros que deciden SI se borra y sobre que. Lo que
se borra de verdad -la frontera de retencion, fila a fila- se mide contra una base en
tests/test_partitioning_postgres.py.
"""

from __future__ import annotations

import pytest

from app.partitioning import (
    PARTITIONED_TEMPORAL_TABLES,
    apply_temporal_retention,
    ensure_temporal_partitions,
)


class _RecordingConnection:
    """Registra lo que se le manda sin ejecutar nada. Si un portero deja pasar algo
    que no deberia, se ve en `calls` en vez de en una base."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.calls.append((query, args))
        return "SELECT 1"


def test_managed_table_set_is_exactly_the_five_partitioned_tables() -> None:
    # La lista tambien esta escrita en sql/schema.sql, en drop_expired_temporal_partitions
    # y en ensure_temporal_partitions. Si aqui se anade una tabla y alli no, la tabla se
    # queda sin particiones nuevas y sin retencion, en silencio: por eso se fija.
    assert frozenset(
        {
            "futures_trades_realtime",
            "spot_trades_realtime",
            "orderbook_snapshot",
            "liquidations_realtime",
            "scalp_signal_snapshot",
        }
    ) == PARTITIONED_TEMPORAL_TABLES


@pytest.mark.asyncio
async def test_retention_refuses_a_table_it_does_not_manage() -> None:
    """El portero que impide borrar de una tabla equivocada.

    Es el mas importante de los dos: apply_temporal_retention acaba en un
    DELETE ... WHERE ts < cutoff sobre el nombre que se le pase. Sin este portero, un
    nombre mal escrito no falla, BORRA otra cosa.
    """

    conn = _RecordingConnection()
    for prohibida in (
        "signal_observation",
        "metrics_snapshot",
        "futures_trades_realtime_p20260827",  # una particion hija, no el padre
        "",
    ):
        with pytest.raises(ValueError, match="not managed by temporal partitioning"):
            await apply_temporal_retention(conn, prohibida, 24)
    # Y no basta con que levante: no puede haber llegado NADA a la conexion.
    assert conn.calls == []


@pytest.mark.asyncio
async def test_retention_refuses_a_non_positive_horizon() -> None:
    """Un horizonte de 0 pondria el corte en `ahora` y vaciaria la tabla entera."""

    conn = _RecordingConnection()
    for horas in (0, -1, -24):
        with pytest.raises(ValueError, match="retention_hours must be positive"):
            await apply_temporal_retention(conn, "futures_trades_realtime", horas)
    assert conn.calls == []


@pytest.mark.asyncio
async def test_retention_passes_table_and_horizon_as_parameters_not_as_text() -> None:
    """El nombre y el horizonte viajan como PARAMETROS, no interpolados en el SQL."""

    conn = _RecordingConnection()
    await apply_temporal_retention(conn, "orderbook_snapshot", 48)
    assert len(conn.calls) == 1
    query, args = conn.calls[0]
    assert args == ("orderbook_snapshot", 48)
    assert "orderbook_snapshot" not in query
    assert "48" not in query


@pytest.mark.asyncio
async def test_ensure_partitions_asks_the_database_and_adds_nothing() -> None:
    conn = _RecordingConnection()
    await ensure_temporal_partitions(conn)
    assert conn.calls == [("SELECT ensure_temporal_partitions()", ())]
