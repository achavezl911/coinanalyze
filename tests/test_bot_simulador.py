"""BOT-2 · remates 6, 7 y 8: el SIMULADOR (tests/simulador_bot.py) sobre el bot de la rama. En el modelo, 2000 secuencias
por semilla y 3 semillas; cada VARIANTE fuera de S1-S4 (desfase de closed-pnl, ordenes de varias ejecuciones, updatedTime
que no se mueve, retrasos de 30 min y de 2 h, vacias falsas seguidas, anadidos a un tick, reaperturas a la misma entrada,
cobertura, despliegue desde R5, la base que no apunta un cierre, excepciones en la identidad, position/list perdiendo el
2-20 % de los tics), 1000 por semilla y 3 semillas; los casos de los validadores con su cifra ESPERADA; y el CONTROL
POSITIVO: cada mutante de los validadores hace caer al simulador. Con el app/bot de main@7870ae8 (R5), de 2e253f1 (R6) y
de 50d4c00 (R7) cae: x1-tmp/bot2/r8-viejo-sim.sh. Sin red y sin base: en memoria."""

from __future__ import annotations

import pathlib
import time
import types
from unittest import mock

import pytest
import simulador_bot as S

from app.bot import servicio as sv
from app.bot import vidas


@pytest.mark.parametrize("semilla", [1, 2, 3])
def test_el_simulador_no_rompe_ninguna_invariante(semilla):
    r = S.lote(sv, semilla, 2000)
    assert r["fallos"] == [], f"{len(r['fallos'])} secuencias rompen alguna invariante: {r['fallos'][:3]}"
    assert r["cerradas_simples"] > 100 and r["cerradas"] > 300  # que de verdad haya vidas que puntuar
    assert r["mirado"].get("I1 cota baja", 0) > 1000 and r["mirado"].get("I7", 0) > 1000 and r["mirado"].get("I3", 0) > 500


@pytest.mark.parametrize("variante", S.VARIANTES)
@pytest.mark.parametrize("semilla", [1, 2, 3])
def test_fuera_del_modelo_ningun_grave(variante, semilla):
    """0 GRAVES (I2, I4, I1 doble, I3, I9, reventon), I5-I8 y «ninguna mas» en cada variante: lo que no se puede separar
    sale ambiguo o sin puntuar (cuanto, en la entrega). Perdiendo lecturas (remate 8, R1), toda CERRADA llega con un
    retraso ACOTADO: como mucho las 2 h de «sin puntuar» desde que la vida cerro, y unos minutos."""
    r = S.lote(sv, semilla, 1000, variante)
    assert r["graves"] == [], f"{variante}: {len(r['graves'])} secuencias con graves: {r['graves'][:3]}"
    assert r["fallos"] == [], f"{variante}: {len(r['fallos'])} secuencias rompen alguna invariante: {r['fallos'][:3]}"
    assert r["cerradas"] > 300
    if variante in S.PERDIDAS:
        assert r["perdidos"] > 0.01 * r["tics"] and max(r["retrasos"]) <= 135, (r["perdidos"], r["tics"], max(r["retrasos"]))
    if variante == "retraso_120":
        assert r["correcciones"] > 0  # (que de verdad haya cifras tardias que corregir)


@pytest.mark.parametrize("sec", S.fijas(), ids=lambda s: s.nombre)
def test_los_casos_de_los_validadores(sec):
    assert S.comprueba(S.simula(sec, sv)) == []


def test_una_excepcion_en_decide_no_calla_los_avisos_de_seguridad():
    """I8 / punto 1: con el libro reventando en CADA tic, el aviso sin_stop sale en los dos simbolos, nada se paga y el tic
    no revienta."""
    sec = S.Secuencia(nombre="decide revienta", desfase=0, minutos=6, vidas=[
        S._v(1, "BTCUSDT:Buy", [(0.9, "abre", 0.004, 110000), (5.0, "cierra", 0, 110300)], 0),
        S._v(2, "ETHUSDT:Sell", [(1.2, "abre", 0.05, 3900), (5.5, "cierra", 0, 3880)], 0)])

    def revienta(self, ahora):
        raise RuntimeError("identidad rota")
    with mock.patch.object(vidas.Libro, "calcula", revienta):
        s = S.simula(sec, sv)
    avisos = [t for _ts, t in s.reg.textos if "sin stop" in t]
    assert any("BTCUSDT LARGO" in t for t in avisos) and any("ETHUSDT CORTO" in t for t in avisos), avisos
    assert s.reg.errores == [] and s.reg.pagos == []


def test_una_excepcion_en_la_poda_no_se_lleva_ninguna_cerrada():
    """Remate 8 (sospecha del quinto validador): decide es transaccional; con la poda reventando en CADA tic (antes,
    despues de borrar los tramos puntuados: I7 en 63 de 100) nada se pierde."""
    def poda(self, ahora):
        raise S.FalloInyectado("poda rota")
    with mock.patch.object(vidas.Libro, "_poda", poda):
        r = S.lote(sv, 1, 200)
    assert r["fallos"] == [], r["fallos"][:3]
    assert r["mirado"].get("I7", 0) > 100


# ---- EL CONTROL POSITIVO: cada mutante de los validadores hace caer al simulador (si no cae, el simulador no mide eso)
def _sin_resultados(filtro):
    original = vidas.Libro.calcula

    def calcula(self, ahora):
        cambios, out = original(self, ahora)
        out["resultados"] = [x for x in out["resultados"] if not filtro(x)]
        return cambios, out
    return mock.patch.object(vidas.Libro, "calcula", calcula)


def _evalua_tarde(minutos):
    original = vidas.Libro.calcula

    def calcula(self, ahora):
        cambios, out = original(self, ahora)
        out["firmes"] = {i: f for i, f in out["firmes"].items() if ahora - f["desde"] >= minutos * 60_000}
        return cambios, out
    return mock.patch.object(vidas.Libro, "calcula", calcula)


def _sin_punto_1():
    """La seguridad DETRAS de la identidad (como en R6): el libro revienta y los avisos no llegan a calcularse."""
    original = sv.Bot.seguridad

    def revienta(self, ahora):
        raise RuntimeError("identidad rota")

    async def seguridad(self, lista):
        self.libro.calcula(int(time.time() * 1000))
        return await original(self, lista)
    return [mock.patch.object(vidas.Libro, "calcula", revienta), mock.patch.object(sv.Bot, "seguridad", seguridad)]


def _typeerror_de_r6():
    """El TypeError de R6, reintroducido como lo midio el quinto validador: en la rama A5 la vida nueva con cadena=False y
    firme_run None, y sin el respaldo de su primera lectura (k["runs"][None]). Un vidas.py MUTADO en un modulo aparte."""
    src = pathlib.Path(vidas.__file__).read_text(encoding="utf-8")
    for viejo, nuevo in (
            ('fr = ultima["firme_run"] if ultima["firme_run"] is not None else ultima["runs"][0]', 'fr = ultima["firme_run"]'),
            ('if v["cadena"] or len(v["runs"]) == 1:', 'if v["cadena"]:'),
            ('v = nueva(r, [], "A5: un registro anterior la separa aqui sin una fila que la cierre", None)',
             'v = nueva(r, [], "A5: un registro anterior la separa aqui sin una fila que la cierre", None)\n'
             '                    v["cadena"] = False')):
        assert src.count(viejo) == 1, f"el mutante ya no casa con vidas.py: {viejo[:60]}"
        src = src.replace(viejo, nuevo)
    mod = types.ModuleType("vidas_r6")
    exec(compile(src, "vidas_r6", "exec"), mod.__dict__)  # noqa: S102 - el mutante del control positivo
    return [mock.patch.object(sv, "vidas", mod)]


def _ambigua_falsa(motivo):
    """Toda vida que se iba a puntuar sale «ambigua» por un motivo que no es verdad (el validador: 0 de 300 caian)."""
    original = vidas.Libro._resultado

    def resultado(v):
        r = original(v)
        return r | {"pnl": None, "nota": f"ambigua: {motivo}"} if r["pnl"] is not None else r
    return [mock.patch.object(vidas.Libro, "_resultado", staticmethod(resultado))]


MUTANTES = {  # nombre: (parches, la invariante que tiene que caer, la variante del lote)
    "no puntuar nunca": (lambda: [_sin_resultados(lambda x: True)], "I7", None),
    "no evaluar nunca": (lambda: [mock.patch.object(sv.Bot, "evalua_una", lambda self, p, m: _nada())], "I1", None),
    "sin puntuar en vez de cifra": (lambda: [mock.patch.object(vidas.Libro, "_resultado", staticmethod(
        lambda v: {"pnl": None, "ordenes": [f["orden"] for f in v["filas"]], "nota": "sin puntuar"}))], "I6", None),
    "sin_stop por clave": (lambda: [mock.patch.object(sv.Bot, "clave_aviso", lambda self, p, tipo="sin_stop": p["clave"])], "I3", None),
    "sin CERRADA con mas de un tramo": (lambda: [_sin_resultados(lambda x: x[1]["tramos"] > 1)], "I7", None),
    "evaluar solo pasados 11 min": (lambda: [_evalua_tarde(11)], "I1", None),
    "excepcion en decide sin el punto 1": (_sin_punto_1, "I3", None),
    # remate 8: el quinto validador
    "el TypeError de R6 reintroducido": (_typeerror_de_r6, "I9", "migracion"),
    "ambigua: S1 con motivo falso": (lambda: _ambigua_falsa(vidas.S1), "ninguna", None),
    "ambigua: A7 con motivo falso": (lambda: _ambigua_falsa(vidas.A7), "ninguna", None),
}


async def _nada():
    return None


@pytest.mark.parametrize("nombre", list(MUTANTES))
def test_cada_mutante_hace_caer_al_simulador(nombre):
    parches, invariante, variante = MUTANTES[nombre]
    ps = parches()
    for p in ps:
        p.start()
    try:
        r = S.lote(sv, 1, 300, variante)
    finally:
        for p in ps:
            p.stop()
    vistos = {x.split(" ")[0] for _n, f in r["fallos"] for x in f}
    assert invariante in vistos, f"el mutante «{nombre}» no hace caer {invariante}: cae {sorted(vistos)}"
