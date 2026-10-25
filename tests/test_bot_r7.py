"""BOT-2 · remate 7: lo que el simulador no mira con la base de verdad. El interruptor avisa si el bot late pero no completa
una lectura de Bybit (punto 2) y /estado lo dice; un cierre se apunta UNA vez aunque la base falle y el bot se reinicie
(punto 10); bot_crudo es solo anadir, con la poda de lo de mas de 90 dias, y la lectura cruda se guarda solo al cambiar
(punto 13). Sin red; las de base, con TEST_DATABASE_URL."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from test_bot import AHORA, _NoCierra, _telegram, base  # noqa: F401

from app.bot import servicio as sv
from app.bot import vigia

VIVO = {"ActiveState": "active", "SubState": "running", "Result": "success"}


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_el_interruptor_ve_un_bot_que_late_y_no_lee_bybit():
    todo_bien = dict(unidad=VIVO, monitor=None, base_error=None, latido=AHORA - timedelta(seconds=40), parte_hoy=True,
                     informe_semana=True, falla_informe=None)
    parado = {"activo": True, "tic": _iso(AHORA - timedelta(minutes=7))}
    p = vigia.problemas(AHORA, **todo_bien, bybit=parado)
    assert list(p) == ["bybit"] and "no completa una lectura de Bybit desde hace 7 min" in p["bybit"]
    assert vigia.problemas(AHORA, **todo_bien, bybit={"activo": True, "tic": _iso(AHORA - timedelta(minutes=2))}) == {}
    assert vigia.problemas(AHORA, **todo_bien, bybit=parado | {"activo": False}) == {}  # Bybit apagado: lo dice su aviso
    sin_latido = vigia.problemas(AHORA, **(todo_bien | {"latido": AHORA - timedelta(minutes=9)}), bybit=parado)
    assert list(sin_latido) == ["latido"]  # si no late, eso primero


def test_estado_dice_cuanto_lleva_sin_leer_bybit():
    bot = sv.Bot({}, None, None)
    ahora = datetime.now(UTC)
    s = {"bybit": {"activo": True, "leida": _iso(ahora), "tic": _iso(ahora - timedelta(minutes=8))}, "validacion": None,
         "fuentes": {}, "datos": "sin datos", "alertas_24h": {}, "errores": {}, "arranque": _iso(ahora), "latido": _iso(ahora),
         "ultima_alerta": None, "gasto_hoy": 0.0, "tope": 3.0, "gasto_ayer": 0.0, "telegram": "ok", "informe": "-"}
    assert "SIN LEER BYBIT DESDE HACE 8 MIN" in bot.texto_salud(s, "ESTADO")
    s["bybit"]["tic"] = _iso(ahora - timedelta(seconds=30))
    assert "ultima lectura completa" in bot.texto_salud(s, "ESTADO") and "SIN LEER BYBIT" not in bot.texto_salud(s, "ESTADO")


async def test_el_interruptor_avisa_una_vez_si_bybit_se_para_y_otra_al_volver(base, tmp_path):  # noqa: F811
    async def conecta():
        return _NoCierra(base)
    entorno = {"TELEGRAM_BOT_TOKEN": "123:puente", "TELEGRAM_CHAT_ID": "-100", "BOT_INFORMES": str(tmp_path)}
    f = tmp_path / "estado.json"
    await base.execute("INSERT INTO bot_estado VALUES ('bot', $1, $2::jsonb)", AHORA - timedelta(seconds=30),
                       json.dumps({"bybit": {"activo": True, "tic": _iso(AHORA - timedelta(minutes=12))}}))
    await base.execute("INSERT INTO bot_evento (tipo, enviada, ts) VALUES ('parte', true, $1)", AHORA - timedelta(minutes=50))
    await base.execute("INSERT INTO bot_evento (tipo, enviada, detalle) VALUES ('informe', true, '{\"semana\": \"2026-W44\"}')")
    enviados: list = []
    p = await vigia.pasada(entorno, _telegram(enviados), VIVO, conecta, f, AHORA)
    assert len(enviados) == 1 and "no completa una lectura de Bybit desde hace 12 min" in enviados[0] and list(p["notificados"]) == ["bybit"]
    await base.execute("UPDATE bot_estado SET ts = $1 WHERE clave = 'bot'", AHORA + timedelta(minutes=4, seconds=40))
    await vigia.pasada(entorno, _telegram(enviados), VIVO, conecta, f, AHORA + timedelta(minutes=5))
    assert len(enviados) == 1  # sigue parado: no repite
    await base.execute("UPDATE bot_estado SET ts = $1, estado = $2::jsonb WHERE clave = 'bot'", AHORA + timedelta(minutes=9, seconds=40),
                       json.dumps({"bybit": {"activo": True, "tic": _iso(AHORA + timedelta(minutes=9, seconds=40))}}))
    p = await vigia.pasada(entorno, _telegram(enviados), VIVO, conecta, f, AHORA + timedelta(minutes=10))
    assert len(enviados) == 2 and "resuelto" in enviados[1] and p["notificados"] == {}


class _FallaCierre:
    """La base de verdad, salvo que no apunta un cierre mientras falla[0]."""

    def __init__(self, c, falla):
        self.c, self.falla = c, falla

    def __getattr__(self, k):
        return getattr(self.c, k)

    async def execute(self, sql, *a):
        if self.falla[0] and "'cierre'" in sql:
            raise OSError("connection reset (postgresql 5432)")
        return await self.c.execute(sql, *a)


async def test_un_cierre_se_apunta_una_vez_aunque_la_base_falle_y_el_bot_se_reinicie(base):  # noqa: F811
    i = "BTCUSDT:Buy:1792400000000"
    p = {"clave": "BTCUSDT:Buy", "symbol": "BTCUSDT", "lado": 1, "cantidad": 0.004, "entrada": 110000.0, "actualizada": 1792400000000, "id": i}
    await base.execute("INSERT INTO bot_evaluacion (tipo, posicion, veredicto, detalle) VALUES ('veredicto', $1, 'A FAVOR', $2::jsonb)",
                       i, json.dumps({"motivo": "posicion nueva", "posicion": p}))
    res = {"pnl": 1.5, "ordenes": ["o-1"], "nota": None}
    falla, textos = [True], []

    async def manda(t):
        textos.append(t)
        return True

    bot = sv.Bot({}, _FallaCierre(base, falla), None)
    await bot.carga()
    bot.manda = manda
    bot.cierres_pendientes[i] = res
    await bot.cierre(i, res)  # la base no lo apunta: sigue pendiente, y en el estado
    assert textos == [] and i in bot.cierres_pendientes and await base.fetchval("SELECT count(*) FROM bot_evaluacion WHERE tipo = 'cierre'") == 0
    await bot.latido()
    otro = sv.Bot({}, base, None)  # se reinicia: el pendiente vuelve del estado y se apunta, UNA vez
    await otro.carga()
    otro.manda = manda
    assert otro.cierres_pendientes == {i: res}
    await otro.cierre(i, otro.cierres_pendientes[i])
    assert len(textos) == 1 and textos[0].startswith("CERRADA BTCUSDT LARGO: +1.50 USD") and otro.cierres_pendientes == {}
    tercero = sv.Bot({}, base, None)  # se reinicia sin haber latido: el estado aun lo da pendiente, pero ya esta en la base
    await tercero.carga()
    assert tercero.cierres_pendientes == {} and i not in tercero.evaluadas
    tercero.manda = manda
    tercero.evaluadas[i] = {"veredicto": "A FAVOR", "posicion": p}  # (aunque la memoria lo creyera pendiente)
    await tercero.cierre(i, res)
    assert len(textos) == 1 and await base.fetchval("SELECT count(*) FROM bot_evaluacion WHERE tipo = 'cierre'") == 1


async def test_bot_crudo_es_solo_anadir_con_su_poda_y_guarda_la_lectura_al_cambiar(base):  # noqa: F811
    bot = sv.Bot({}, base, None)
    lista = [{"clave": "BTCUSDT:Buy", "symbol": "BTCUSDT", "cantidad": 0.004, "entrada": 110000.0, "stop": None, "actualizada": 1}]
    await bot.crudo_lectura(lista, 1000)
    await bot.crudo_lectura(lista, 61000)  # igual: no se guarda otra vez
    await bot.crudo_lectura([lista[0] | {"cantidad": 0.002, "actualizada": 2}], 121000)
    await bot.crudo_lectura([], 181000)  # ya no esta: tamano 0
    filas = [json.loads(r[0]) for r in await base.fetch("SELECT detalle FROM bot_crudo WHERE tipo = 'posicion' ORDER BY ts")]
    assert [f["size"] for f in filas] == [0.004, 0.002, 0] and filas[0]["updatedTime"] == 1 and filas[0]["local"] == 1000
    for sql in ("DELETE FROM bot_crudo", "UPDATE bot_crudo SET symbol = 'X'", "TRUNCATE bot_crudo"):
        with pytest.raises(asyncpg.PostgresError):
            await base.execute(sql)
    await base.execute("INSERT INTO bot_crudo (ts, tipo, symbol, detalle) VALUES (now() - interval '91 days', 'fila', 'BTCUSDT', '{}')")
    assert await base.execute("DELETE FROM bot_crudo WHERE ts < now() - interval '90 days'") == "DELETE 1"
    assert await base.fetchval("SELECT count(*) FROM bot_crudo") == 3
