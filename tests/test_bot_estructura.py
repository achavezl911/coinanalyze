"""ESTRUCTURA R1: los avisos deterministas del bridge (giro de estructura, liquidaciones masivas, flujo pasivo) pasan al bot.

El bridge de Telegram de 140 (coinalyze-ai-bridge, fuera del repo) manda en modo alert_only «ESTRUCTURA / LIQUIDACIONES
(<ts>) ...»; el dueno lo usa y se va a apagar. La prueba de equivalencia: 6 cargas inventadas de /api/ai/context/bundle
(tests/fixtures/estructura_r1_cargas.json) por la REFERENCIA (tests/genera_dorado_estructura.py, que importa la copia del
bridge de x1-tmp; el dorado se commitea, la referencia no) y por el bot: el MISMO texto, la MISMA decision de enviar y el
MISMO estado de anti-repeticion paso a paso, con un envio que falla en medio. Todo con dobles: ni red ni filas del dueno.

AVISOS R1 (H3): la decision y el estado siguen IDENTICOS a la referencia; el texto es el del dorado con SUSTITUCIONES (las
palabras del bridge que nombran una direccion sin medirla -Fable I18: ninguna senal la da- y el icono, por el hecho que
miden). El dorado no se regenera: la tabla se aplica aqui y cada fila tiene que morder al menos una vez.
"""

from __future__ import annotations

import json
import pathlib
import re

from app.bot import estructura as est
from app.bot import servicio as sv

FIX = pathlib.Path(__file__).parent / "fixtures"
CARGAS = json.loads((FIX / "estructura_r1_cargas.json").read_text(encoding="utf-8"))
DORADO = json.loads((FIX / "estructura_r1_dorado.json").read_text(encoding="utf-8"))
# (patron de la referencia, texto del bot). alcista/bajista del giro = HH_HL/LH_LL (app/setups.py:1265); la lectura del
# flujo pasivo, app/scalp_logic.py:_classify_passive (ventas o compras agresivas absorbidas, con el CVD de contado opuesto)
SUSTITUCIONES = [
    (r"^⚠️ ESTRUCTURA / LIQUIDACIONES", "ESTRUCTURA / LIQUIDACIONES"),
    (r"giro ▲ ALCISTA \(", "pasa a maximos y minimos mas altos ("),
    (r"giro ▼ BAJISTA \(", "pasa a maximos y minimos mas bajos ("),
    (r" → cascada BAJISTA \(longs\)", ", sobre todo de largos"),
    (r" → squeeze ALCISTA \(shorts\)", ", sobre todo de cortos"),
    (r"REACUMULACION silenciosa (\w+) ", r"flujo pasivo \1: ventas agresivas absorbidas y contado comprando "),
    (r"REDISTRIBUCION silenciosa (\w+) ", r"flujo pasivo \1: compras agresivas absorbidas y contado vendiendo "),
]


def sustituye(texto: str) -> str:
    for a, b in SUSTITUCIONES:
        texto = re.sub(a, b, texto, flags=re.M)
    return texto


def test_cada_sustitucion_muerde_en_el_dorado():
    textos = [d["texto"] for v in DORADO.values() for d in v if d["texto"]]
    for a, _ in SUSTITUCIONES:
        assert any(re.search(a, t, flags=re.M) for t in textos), a


BUNDLE = "/api/ai/context/bundle?symbols=BTCUSDT_PERP.A,ETHUSDT_PERP.A,SOLUSDT_PERP.A&profile=default&bucket_bps=10"


class Base:
    """bot_evento en una lista: lo que el bot registraria."""

    def __init__(self):
        self.eventos: list = []

    async def execute(self, sql, *a):
        assert sql.startswith("INSERT INTO bot_evento"), sql
        self.eventos.append({"tipo": a[0], "symbol": a[1], "enviada": a[5], "detalle": json.loads(a[6])})


def montado(modo: str | None, **mas):
    e = dict(CARGAS["umbrales"]) | mas
    if modo is not None:
        e["BOT_ESTRUCTURA"] = modo
    bot, mandados, rutas = sv.Bot(e, Base(), None), [], []
    bot.falla = False

    async def manda(texto):
        mandados.append(texto)
        return not bot.falla
    bot.manda = manda
    return bot, mandados, rutas


async def _corre(bot, mandados, rutas, monkeypatch, dorado: list):
    for i, (p, d) in enumerate(zip(CARGAS["pasos"], dorado, strict=True)):
        async def api(ruta, carga=p["carga"]):
            rutas.append(ruta)
            return json.loads(json.dumps(carga))
        bot.api, bot.falla = api, p["falla_envio"]
        monkeypatch.setattr(sv.time, "time", lambda ahora=p["ahora"]: ahora)
        antes = len(bot.db.eventos)
        await bot.tic_estructura()
        nuevos = bot.db.eventos[antes:]
        yield i, d, nuevos
        assert bot.estructura["kv"] == d["kv"] and bot.estructura["t"] == d["t"], (i, bot.estructura, d)


async def test_enviar_da_el_mismo_texto_decision_y_anti_repeticion_que_el_bridge(monkeypatch):
    bot, mandados, rutas = montado("enviar")
    async for i, d, nuevos in _corre(bot, mandados, rutas, monkeypatch, DORADO["enviar"]):
        if d["envia"]:
            assert mandados.pop() == sustituye(d["texto"]), i
            (ev,) = nuevos
            assert ev["tipo"] == "estructura" and ev["symbol"] is None, ev
            assert ev["enviada"] == (not CARGAS["pasos"][i]["falla_envio"]) and ev["detalle"]["texto"] == sustituye(d["texto"]), (i, ev)
            assert ev["detalle"]["modo"] == "enviar", ev
        else:
            assert not nuevos, (i, nuevos)
        assert not mandados, (i, mandados)
    assert rutas == [BUNDLE] * len(CARGAS["pasos"]), rutas


async def test_sombra_calcula_y_registra_sin_enviar(monkeypatch):
    for modo in (None, "sombra", "SOMBRA "):  # por defecto, SOMBRA
        bot, mandados, rutas = montado(modo)
        async for i, d, nuevos in _corre(bot, mandados, rutas, monkeypatch, DORADO["sombra"]):
            assert [x["detalle"]["texto"] for x in nuevos] == ([sustituye(d["texto"])] if d["envia"] else []), (modo, i, nuevos)
            assert all(x["enviada"] is False and x["detalle"]["modo"] == "sombra" for x in nuevos), nuevos
        assert not mandados, mandados
        assert bot.texto_estructura().startswith("estructura (avisos del bridge): sombra · 5 en 24 h, 0 enviados"), bot.texto_estructura()


async def test_apagado_no_lee_ni_registra(monkeypatch):
    bot, mandados, rutas = montado("apagado")
    async for _i, _d, nuevos in _corre(bot, mandados, rutas, monkeypatch, [{"kv": {}, "t": {}}] * len(CARGAS["pasos"])):
        assert not nuevos
    assert not mandados and not rutas
    assert bot.texto_estructura().startswith("estructura (avisos del bridge): apagado"), bot.texto_estructura()


def test_umbrales_de_las_variables_del_bridge():
    u, avisos = est.Umbrales.desde({})
    assert (u.modo, u.simbolos, u.bps, u.piso, u.mult, u.enfriamiento, u.intervalo) == (
        "sombra", ["BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"], 10, 2_000_000.0, 4.0, 240.0, 300.0) and not avisos
    u, avisos = est.Umbrales.desde({"SYMBOLS": '["BTCUSDT_PERP.A"]', "LIQUIDATION_BUCKET_BPS": "25", "LIQ_BURST_FLOOR_USD": "5e6",
                                    "LIQ_BURST_MULT": "3", "MIN_SEND_INTERVAL_SECONDS": "600", "ANALYSIS_INTERVAL_SECONDS": "120",
                                    "BOT_ESTRUCTURA": "enviar"})
    assert (u.modo, u.simbolos, u.bps, u.piso, u.mult, u.enfriamiento, u.intervalo) == (
        "enviar", ["BTCUSDT_PERP.A"], 25, 5e6, 3.0, 600.0, 120.0) and not avisos
    assert est.ruta(u) == "/api/ai/context?symbol=BTCUSDT_PERP.A&profile=default&bucket_bps=25"
    u, avisos = est.Umbrales.desde({"BOT_ESTRUCTURA": "manda", "LIQ_BURST_MULT": "x"})
    assert u.modo == "sombra" and u.mult == 4.0 and len(avisos) == 2, (u, avisos)


async def test_el_estado_de_anti_repeticion_sobrevive_al_reinicio(monkeypatch):
    bot, mandados, rutas = montado("enviar")
    pasos = _corre(bot, mandados, rutas, monkeypatch, DORADO["enviar"])
    await anext(pasos)
    await anext(pasos)
    guardado = json.loads(sv.js(bot.estado))["estructura"]
    otro, _, _ = montado("enviar")
    otro.restaura_estructura(guardado)
    assert otro.estructura["kv"] == bot.estructura["kv"] and otro.estructura["t"] == bot.estructura["t"]
    assert len(otro.estructura["avisos"]) == 2
    otro.restaura_estructura("ilegible")  # lo que no se entiende no tumba la carga
    assert otro.estructura["kv"] == bot.estructura["kv"]


ORDEN = re.compile(r"(?<![\w/])/[a-z]\w*")


def _ordenes_del_bot() -> set[str]:
    """Las ordenes que atiende Servicio.atiende (servicio.py): las «/x» de sus `orden in (...)` y `orden == "..."`."""
    fuente = pathlib.Path(sv.__file__).read_text(encoding="utf-8")
    cuerpo = fuente.split("async def atiende(", 1)[1].split("\n    async def ", 1)[0]
    return set(re.findall(r'"(/[a-z]+)"', " ".join(re.findall(r'orden (?:in \([^)]*\)|== "[^"]*")', cuerpo))))


def test_el_aviso_no_remite_a_ordenes_que_el_bot_no_atiende():
    """ESTRUCTURA R3: el pie copiado del bridge remitia a dos ordenes del bridge que el bot no tiene (y nombraba al asistente
    ajeno que PURGA quito del repo). Ningun texto del dorado (= el del bot, por la prueba de equivalencia) nombra una «/x» que
    el bot no atienda, y todos acaban en el pie del bot."""
    ordenes = _ordenes_del_bot()
    assert {"/calc", "/evalua", "/estado", "/ayuda"} <= ordenes, ordenes  # el extractor ve las ordenes
    textos = [d["texto"] for v in DORADO.values() for d in v if d["texto"]]
    assert len(textos) == 10
    ajenas = sorted({o for t in textos for o in ORDEN.findall(t)} - ordenes)
    assert not ajenas, f"el aviso remite a ordenes que el bot no atiende: {ajenas}"
    assert {t.rsplit("\n", 1)[1] for t in textos} == {est.PIE}
    assert not set(ORDEN.findall(est.PIE)) - ordenes
