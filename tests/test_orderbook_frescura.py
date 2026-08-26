"""K13 — /api/scalp/orderbook dice si el libro no existe o si es viejo.

El endpoint filtra ``ts >= now()-30s``, asi que un libro rancio sale como CERO filas,
igual que un libro que no existe. La distincion no puede vivir dentro de ``rows``: con
cero filas no queda nada de donde inferirla.

De los tres estados, "stale" es el que NO se puede observar contra produccion -el libro
esta fresco casi siempre- y por eso se prueba aqui: si no, esa rama no la ejecuta nadie.
"""

from datetime import UTC, datetime, timedelta

import pytest

import app.api as api
from app.api import ORDERBOOK_MAX_AGE_SECONDS, scalp_orderbook

SIM = "BTCUSDT_PERP.A"


class _Conexion:
    """Sirve la consulta de filas y la de edad por separado, como hace el endpoint."""

    def __init__(self, filas: list[dict], as_of: datetime | None) -> None:
        self.filas = filas
        self.as_of = as_of
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_args: object) -> list[dict]:
        self.consultas.append(query)
        return self.filas

    async def fetchval(self, query: str, *_args: object) -> datetime | None:
        self.consultas.append(query)
        return self.as_of


class _Pool:
    def __init__(self, conn: _Conexion) -> None:
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *_exc: object) -> None:
                return None

        return Ctx()


def _montar(monkeypatch, filas, as_of):
    conn = _Conexion(filas, as_of)
    monkeypatch.setattr(api.app.state, "pool", _Pool(conn), raising=False)
    return conn


@pytest.mark.skipif(SIM not in api.SETTINGS.SYMBOLS, reason="el simbolo no esta configurado")
async def test_libro_rancio_dice_que_es_viejo_y_cuanto(monkeypatch) -> None:
    as_of = datetime.now(UTC) - timedelta(seconds=300)
    _montar(monkeypatch, [], as_of)

    salida = await scalp_orderbook(SIM)

    assert salida["rows"] == []
    assert salida["freshness"]["status"] == "stale"
    assert 290 <= salida["freshness"]["age_seconds"] <= 320
    assert salida["freshness"]["as_of"] == as_of.isoformat()
    assert salida["freshness"]["max_age_seconds"] == ORDERBOOK_MAX_AGE_SECONDS


@pytest.mark.skipif(SIM not in api.SETTINGS.SYMBOLS, reason="el simbolo no esta configurado")
async def test_sin_libro_no_se_dice_viejo(monkeypatch) -> None:
    """Sin ninguna instantanea no hay edad que dar, y eso NO es lo mismo que rancio."""
    _montar(monkeypatch, [], None)

    salida = await scalp_orderbook(SIM)

    assert salida["freshness"]["status"] == "empty"
    assert salida["freshness"]["age_seconds"] is None
    assert salida["freshness"]["as_of"] is None


@pytest.mark.skipif(SIM not in api.SETTINGS.SYMBOLS, reason="el simbolo no esta configurado")
async def test_libro_fresco_conserva_las_filas_y_la_forma_de_siempre(monkeypatch) -> None:
    as_of = datetime.now(UTC) - timedelta(seconds=2)
    _montar(monkeypatch, [{"exchange": "binance", "spread_bps": 1.2}], as_of)

    salida = await scalp_orderbook(SIM)

    assert salida["symbol"] == SIM
    assert [r["exchange"] for r in salida["rows"]] == ["binance"]
    assert salida["freshness"]["status"] == "fresh"


@pytest.mark.skipif(SIM not in api.SETTINGS.SYMBOLS, reason="el simbolo no esta configurado")
async def test_la_edad_se_pregunta_SIN_el_filtro_de_30s(monkeypatch) -> None:
    """Si la consulta de la edad llevara el mismo filtro que esconde el problema, un libro
    rancio seguiria sin tener edad. Y lleva el MISMO predicado de venue, para que sea la
    edad de lo que se serviria y no la de cualquier fila."""
    conn = _montar(monkeypatch, [], datetime.now(UTC) - timedelta(seconds=90))

    await scalp_orderbook(SIM)

    edad = next(q for q in conn.consultas if "ORDER BY ts DESC LIMIT 1" in q)
    assert "make_interval" not in edad
    assert "venue_count=2" in edad
