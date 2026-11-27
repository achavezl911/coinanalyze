"""AVISOS R1: los defectos de texto y de vara que Fable v6 demostro en el bot (entregas/fable/fable-v6, H1-H4).

La medida que manda es Fable I18: ninguna senal da DIRECCION, casi todas anuncian mas movimiento en 15 min y el precio no
respeta niveles. El bot DESCRIBE y no predice. Todo con dobles: posiciones inventadas, ni red ni filas del dueno.
"""

from __future__ import annotations

import ast
import pathlib
import re

from test_bot_estructura import DORADO, _corre, montado
from test_bot_r8 import _bot
from test_bot_seguimiento import CORTO, GRA_HIST, LIQ_HIST, M0, Base, plano, textos, tic, velas

from app.bot import centinela as cen
from app.bot import estructura as est
from app.bot import seguimiento as seg

# palabras que anuncian adonde va el precio (y los iconos de estado): ningun texto de estructura ni de seguimiento las lleva
PROHIBIDAS = ("alcista", "bajista", "acumulacion", "reacumulacion", "distribucion", "redistribucion", "squeeze",
              "cascada", "giro", "a favor", "en contra", "▲", "▼", "↑", "↓", "⚠")


def _prohibidas(texto: str) -> list[str]:
    t = texto.lower()
    return [p for p in PROHIBIDAS if p in t]


def _pos(lado, entrada, stop, marca, **mas):
    return {"clave": "BTCUSDT:" + ("Buy" if lado > 0 else "Sell"), "symbol": "BTCUSDT", "lado": lado, "entrada": entrada,
            "stop": stop, "marca": marca, "cantidad": 1.0, "liquidacion": None, "actualizada": 1} | mas


# ---------- H1 · el centinela con el stop en BENEFICIO ----------
def test_h1_los_cuatro_casos_de_fable_no_avisan():
    """Con la vara de main (0.3 x |entrada - stop|) avisaban a 1-4 % del stop: la vara crecia con la ganancia."""
    for lado, e, s, m in ((1, 100.0, 104.0, 105.0), (1, 100.0, 130.0, 138.0), (-1, 100.0, 70.0, 62.0),
                          (1, 60000.0, 66000.0, 67700.0)):
        assert cen.alertas_posicion(_pos(lado, e, s, m)) == [], (lado, e, s, m)


def test_h1_cerca_del_stop_en_beneficio_si_avisa_y_la_perdida_como_antes():
    assert [t for t, _ in cen.alertas_posicion(_pos(1, 100.0, 104.0, 104.3))] == ["stop"]
    assert [t for t, _ in cen.alertas_posicion(_pos(-1, 100.0, 96.0, 95.7))] == ["stop"]
    # del lado de la perdida, la vara de siempre: 0.3 x |entrada - stop|, sin tope (aqui 3 % del precio)
    assert [t for t, _ in cen.alertas_posicion(_pos(1, 100.0, 90.0, 92.9))] == ["stop"]
    assert cen.alertas_posicion(_pos(1, 100.0, 90.0, 93.1)) == []


async def test_h1_subir_el_stop_seis_veces_da_un_mensaje_y_no_escala():
    """Con main, la clave llevaba el nivel del stop: 6 subidas = 6 mensajes, y los 6 al ESCALADO pagado."""
    bot, mandados = _bot()
    escala = []
    for k in range(6):
        s = 104.0 + k
        escala += await bot.seguridad([_pos(1, 100.0, s, s + 0.3, actualizada=k)])
    assert len(mandados) == 1 and "del stop" in mandados[0], mandados
    assert escala == [], escala
    # se rearma cuando la marca se aleja mas de 2 varas, y vuelve a avisar UNA vez al volver a la zona
    s = 109.0
    assert await bot.seguridad([_pos(1, 100.0, s, s + 3 * cen.vara_stop(_pos(1, 100.0, s, s)))]) == []
    escala += await bot.seguridad([_pos(1, 100.0, s, s + 0.3)])
    escala += await bot.seguridad([_pos(1, 100.0, s + 1, s + 1.3)])
    assert len(mandados) == 2 and escala == [], mandados


async def test_h1_el_stop_en_perdida_sigue_escalando():
    bot, mandados = _bot()
    assert [t for _c, t, _x in await bot.seguridad([_pos(1, 100.0, 96.0, 96.5)])] == ["stop"]
    assert len(mandados) == 1


# ---------- H2 · seguimiento sin «A FAVOR / EN CONTRA» ----------
def test_h2_el_mensaje_no_dice_a_favor_ni_en_contra():
    for lado in (1, -1, None):
        t = seg._mensaje("SOL", CORTO, [[M0 * 60, "OI", "el interes abierto sube / sin lado medido.", lado]], [])
        assert "A FAVOR" not in t and "EN CONTRA" not in t and "el interes abierto sube" in t, t


# ---------- H3 · ningun texto de estructura ni de seguimiento anuncia direccion ----------
def _literales(modulo) -> list[str]:
    """Las cadenas del modulo que pueden acabar en un texto: todas menos los docstrings."""
    arbol = ast.parse(pathlib.Path(modulo.__file__).read_text(encoding="utf-8"))
    docs = {id(n.body[0].value) for n in ast.walk(arbol)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    return [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def test_h3_las_cadenas_de_estructura_y_seguimiento_no_nombran_direccion():
    for modulo in (est, seg):
        malas = {x: _prohibidas(x) for x in _literales(modulo) if _prohibidas(x)
                 and not re.fullmatch(r"(reacumulacion|redistribucion)_silenciosa|alcista|bajista", x)}  # valores del sobre
        assert not malas, (modulo.__name__, malas)


async def test_h3_los_textos_de_estructura_no_nombran_direccion(monkeypatch):
    bot, mandados, rutas = montado("sombra")
    vistos = []
    async for _i, _d, nuevos in _corre(bot, mandados, rutas, monkeypatch, DORADO["sombra"]):
        vistos += [x["detalle"]["texto"] for x in nuevos]
    assert len(vistos) == 5 and all(t.startswith("ESTRUCTURA / LIQUIDACIONES (") for t in vistos), vistos
    for t in vistos:
        assert not _prohibidas(t), t
    todo = "\n".join(vistos)
    for hecho in ("maximos y minimos mas altos", "maximos y minimos mas bajos", "sobre todo de largos", "sobre todo de cortos",
                  "ventas agresivas absorbidas", "compras agresivas absorbidas"):
        assert hecho in todo, hecho


async def test_h3_los_textos_de_seguimiento_no_nombran_direccion():
    liq = LIQ_HIST + [(M0 - 5, 1.5e6, 0.0)]
    oi_sube = [(m, 1e6) for m in range(M0 - 43200, M0 - 5, 5)] + [(M0 - 5, 1.01e6)]
    baja = {M0 - 6: plano(M0 - 6, 100.0)} | {m: plano(m, 99.95) for m in range(M0 - 5, M0)}
    rompe = {m: plano(m, 101.0) for m in range(M0 - 5, M0)}
    escenarios = (Base(M0, liq5=liq), Base(M0, velas=velas(M0, baja), oi=oi_sube), Base(M0, velas=velas(M0, rompe)),
                  Base(M0, grandes=GRA_HIST + [(M0 - 1, "binance_usdm", True, 2e6)]))
    todo = [textos(await tic(b, seg.nuevo(), {}, M0)) for b in escenarios]
    assert all(todo), todo
    for t in todo:
        assert not _prohibidas(t), t
