"""AUDITOR R1 · integracion (encargo del dueno, seccion 8, prueba 5): evalua() nunca llama a manda() sin la linea
AUDITOR, ni con Opus caido, ni con el sobre caido, ni con el INSERT caido, ni con el auditor reventando; el dictamen
va en detalle.auditor del mismo INSERT; la alerta aparte sale solo si falla A5/A6/A7. Sin red: Opus, el sobre y
Telegram son de mentira. La base, con TEST_DATABASE_URL (si no, se salta)."""

from __future__ import annotations

import json
import os
import pathlib
import time
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from app.bot import servicio as sv

RAIZ = pathlib.Path(__file__).resolve().parents[1]
OPUS_BIEN = {"texto": "VEREDICTO: A FAVOR\n- la lectura acompana [decide.bias.value]", "error": None, "id": None}
OPUS_CAIDO = {"texto": None, "error": "HTTP 529", "id": None}


@pytest.fixture
async def base():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    esquema = f"aud_{uuid.uuid4().hex}"
    c = await asyncpg.connect(dsn)
    await c.execute(f'CREATE SCHEMA "{esquema}"')
    await c.execute(f'SET search_path TO "{esquema}", public')
    sql = (RAIZ / "sql" / "schema.sql").read_text()
    await c.execute(sql[sql.index("-- CAMPANA BOT-2"):])
    try:
        yield c
    finally:
        await c.execute("SET search_path TO public")
        await c.execute(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')
        await c.close()


class BaseCaida:
    def __init__(self, error: Exception):
        self.error = error

    async def execute(self, *a):
        raise self.error


def posicion(**cambia) -> dict:
    """La posicion sana de tests/test_auditor.py con la forma de bybit.posiciones; visto = ahora (el reloj real)."""
    return {"id": "BTCUSDT:Buy:1", "symbol": "BTCUSDT", "lado": 1, "cantidad": 0.001, "entrada": 100_000.0,
            "stop": 98_000.0, "objetivo": 104_000.0, "liquidacion": 90_000.0, "visto": time.time() * 1000} | cambia


def montado(db, opus=OPUS_BIEN, sobre_cae: bool = False):
    """Un Bot con sobre, Opus y Telegram de mentira; el sobre se sella al leerse, como el de verdad."""
    bot, mandados, llamadas = sv.Bot({}, db, None), [], []

    async def sobre(activo):
        if sobre_cae:
            raise LookupError("sin sobre: HTTP 502")
        ya = datetime.now(UTC)
        iso = ya.isoformat()
        ctx = {"generated_at": iso,
               "orderbook": {"bybit": {"ts": iso, "spread_bps": 0.5, "ask_notional_l1": 500_000.0, "bid_notional_l1": 500_000.0}},
               "external_macro_context": {"event_risk": {"upcoming": [
                   {"title": "CPI", "event_at": (ya + timedelta(hours=30)).isoformat(), "importance": 3}]}}}
        return ctx, {"generated_at": iso, "age": {"snapshot_lag_seconds": {"value": 40.0}},
                     "decide": {"bias": {"value": "LONG"}, "evaluable": {"value": True}}}

    async def opus_falso(motivo, texto):
        llamadas.append(motivo)
        return opus

    async def manda(texto):
        mandados.append(texto)
        return True
    bot.sobre, bot.opus, bot.manda = sobre, opus_falso, manda
    return bot, mandados, llamadas


async def detalle(db) -> dict:
    (d,) = await db.fetch("SELECT detalle FROM bot_evaluacion WHERE tipo = 'veredicto'")
    return json.loads(d["detalle"])


async def test_el_caso_sano_manda_aprobado_primero_y_registra_el_dictamen_en_el_mismo_insert(base):
    bot, mandados, llamadas = montado(base)
    await bot.evalua(posicion(), "posicion nueva")
    assert llamadas == ["evalua"] and len(mandados) == 1, mandados
    lineas = mandados[0].split("\n")
    assert lineas[0] == "AUDITOR: APROBADO · las 9 compuertas pasan", lineas
    assert lineas[1] == "OPUS: A FAVOR" and lineas[2] == "DECIDE: LONG -> A FAVOR"
    assert lineas[3].startswith("EVALUACION BTCUSDT LARGO (posicion nueva) · VEREDICTO: A FAVOR (opus)")
    aud = (await detalle(base))["auditor"]
    assert aud["estado"] == "APROBADO" and [c["nombre"] for c in aud["compuertas"]] == [f"A{i}" for i in range(1, 10)]


async def test_con_opus_caido_la_linea_auditor_sale_primero_y_no_aprueba(base):
    bot, mandados, _ = montado(base, opus=OPUS_CAIDO)
    await bot.evalua(posicion(), "posicion nueva")
    lineas = mandados[0].split("\n")
    assert lineas[0].startswith("AUDITOR: NO EVALUABLE · A1: "), lineas
    assert lineas[1] == "OPUS: NO EVALUABLE (caido: HTTP 529)" and "VEREDICTO: A FAVOR (DECIDE (HTTP 529))" in lineas[3]
    assert (await detalle(base))["auditor"]["estado"] == "NO EVALUABLE"


async def test_con_el_sobre_caido_no_pregunta_a_opus_y_la_linea_sale_igual(base):
    bot, mandados, llamadas = montado(base, sobre_cae=True)
    await bot.evalua(posicion(), "/evalua")
    assert llamadas == [] and len(mandados) == 1
    lineas = mandados[0].split("\n")
    assert lineas[0].startswith("AUDITOR: NO EVALUABLE"), lineas
    assert lineas[1] == "OPUS: NO EVALUABLE (no se le pregunto: sin sobre: HTTP 502)"
    assert (await detalle(base))["auditor"]["estado"] == "NO EVALUABLE"


@pytest.mark.parametrize("error", [OSError("conexion"), asyncpg.InterfaceError("cerrada"), asyncpg.PostgresError("caida")])
@pytest.mark.parametrize("opus", [OPUS_BIEN, OPUS_CAIDO])
async def test_con_el_insert_caido_el_mensaje_sale_con_su_linea_auditor(error, opus):
    bot, mandados, _ = montado(BaseCaida(error), opus=opus)
    await bot.evalua(posicion(), "posicion nueva")
    assert len(mandados) == 1 and mandados[0].startswith("AUDITOR: "), mandados
    assert "BASE registro veredicto" in bot.estado["errores"]  # la caida queda nombrada, el mensaje no se pierde


async def test_si_el_auditor_revienta_sale_no_evaluable_con_el_error(base, monkeypatch):
    def revienta(*a, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(sv.auditor, "audita", revienta)
    bot, mandados, _ = montado(base)
    await bot.evalua(posicion(), "posicion nueva")
    assert len(mandados) == 1 and mandados[0].split("\n")[0] == "AUDITOR: NO EVALUABLE (error: RuntimeError: boom)"
    aud = (await detalle(base))["auditor"]
    assert aud["estado"] == "NO EVALUABLE" and aud["razon"] == "error: RuntimeError: boom"


async def test_la_alerta_aparte_sale_solo_si_falla_una_regla_de_riesgo(base):
    bot, mandados, _ = montado(base)
    await bot.evalua(posicion(stop=None), "posicion nueva")  # sin stop: A5 FALLA
    assert len(mandados) == 2 and mandados[0].startswith("AUDITOR: RECHAZADO · A5: "), mandados
    assert mandados[1].startswith("ALERTA AUDITOR BTCUSDT LARGO: A5 ")
    otro, solo_uno, _ = montado(base, opus={**OPUS_BIEN, "texto": "VEREDICTO: EN CONTRA\n- x"})
    await otro.evalua(posicion(id="BTCUSDT:Buy:2"), "posicion nueva")  # Opus contra DECIDE: A4 AVISO, sin alerta
    assert len(solo_uno) == 1 and solo_uno[0].startswith("AUDITOR: CON RESERVAS · A4: "), solo_uno
