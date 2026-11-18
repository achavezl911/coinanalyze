"""D1 (diario R1): /api/ohlcv nunca sirve una vela sin precio como cerrada, completa y al 100 %.

El doble son las filas del apagon medido en 140 el 2026-11-18 (BTC 5 min, 11-16 15:30Z -> 11-18 01:25Z):
5 de 5 filas de 1 min debajo, hueco declarado, y la ruta las devolvia con OHLC nulo y coverage_pct 100.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

import app.api as api_module

T0 = datetime(2026, 11, 16, 15, 35, tzinfo=UTC)


def _fila(t: datetime, n: int = 5) -> dict:
    return {"bucket": t, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume_usd": 1e6,
            "sample_count": n, "expected_count": 5, "last_sample": t + timedelta(minutes=4),
            "is_complete": n == 5, "is_closed": True, "coverage_pct": Decimal(n * 20).quantize(Decimal("0.1"))}


class _Conn:
    def __init__(self, filas):
        self.filas, self.sql = filas, ""

    async def fetch(self, sql, *_args):
        self.sql = sql
        return [dict(f) for f in self.filas]


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *_):
                return False

        return Ctx()


async def _ruta(monkeypatch, filas, enmascara):
    """La ruta entera con la base y el registro de huecos dobles: `enmascara` son los cubos con hueco declarado."""
    conn = _Conn(filas)

    async def mask(_conn, rows, **kw):
        for r in rows:
            if r["bucket"] in enmascara:
                for k in kw["value_keys"]:
                    r[k] = None

    async def declared(_conn, rows, **_kw):
        return {"rows": rows}

    monkeypatch.setattr(api_module, "mask_gapped_series_rows", mask)
    monkeypatch.setattr(api_module, "declared_series_response", declared)
    monkeypatch.setattr(api_module.app.state, "pool", _Pool(conn), raising=False)
    out = await api_module.ohlcv("BTCUSDT_PERP.A", "5min", 288)
    return out["rows"], conn.sql


@pytest.mark.asyncio
async def test_un_cubo_enmascarado_no_sale_completo_ni_al_100(monkeypatch) -> None:
    filas = [_fila(T0 + timedelta(minutes=5 * k)) for k in range(4)]
    hueco = {filas[1]["bucket"], filas[2]["bucket"]}
    rows, _ = await _ruta(monkeypatch, filas, hueco)
    for r in rows:
        if r["bucket"] in hueco:
            assert r["close"] is None
            assert r["is_complete"] is False
            assert float(r["coverage_pct"]) == 0.0
            assert r["sample_count"] == 0
        else:
            assert r["close"] == 100.5 and r["is_complete"] is True and float(r["coverage_pct"]) == 100.0
    assert not [r for r in rows if r["close"] is None and r["is_closed"] and float(r["coverage_pct"]) >= 100]


@pytest.mark.asyncio
async def test_la_cobertura_cuenta_solo_muestras_con_precio(monkeypatch) -> None:
    _, sql = await _ruta(monkeypatch, [_fila(T0)], set())
    plano = " ".join(sql.split())
    assert "COUNT(*)::int AS sample_count" not in plano
    assert "close IS NOT NULL" in plano and "AS sample_count" in plano
