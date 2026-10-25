"""BOT-2 · remates 6 y 7: el SIMULADOR (tests/simulador_bot.py) sobre el bot de la rama. En el modelo, 2000 secuencias por
semilla y 3 semillas; cada VARIANTE fuera de S1-S4 (desfase de closed-pnl, ordenes de varias ejecuciones, updatedTime que no
se mueve, retrasos de 30 min, vacias falsas seguidas, anadidos a un tick, reaperturas a la misma entrada, cobertura,
despliegue desde R5, la base que no apunta un cierre, excepciones en la identidad), 1000 por semilla y 3 semillas; los casos
de los cuatro validadores con su cifra ESPERADA; y el CONTROL POSITIVO: cada mutante del validador hace caer al simulador.
Con el app/bot de main@7870ae8 (R5) y de 2e253f1 (R6) cae: x1-tmp/bot2/r7-viejo-sim.sh. Sin red y sin base: en memoria."""

from __future__ import annotations

import time
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
    """0 GRAVES (I2, I4, I1 doble, I3, reventon) e I5-I8 en cada variante: lo que no se puede separar sale ambiguo o sin
    puntuar (cuanto, en la entrega)."""
    r = S.lote(sv, semilla, 1000, variante)
    assert r["graves"] == [], f"{variante}: {len(r['graves'])} secuencias con graves: {r['graves'][:3]}"
    assert r["fallos"] == [], f"{variante}: {len(r['fallos'])} secuencias rompen alguna invariante: {r['fallos'][:3]}"
    assert r["cerradas"] > 300


@pytest.mark.parametrize("sec", S.fijas(), ids=lambda s: s.nombre)
def test_los_casos_de_los_validadores(sec):
    assert S.comprueba(S.simula(sec, sv)) == []


def test_una_excepcion_en_decide_no_calla_los_avisos_de_seguridad():
    """I8 / punto 1: con Libro.decide reventando en CADA tic, el aviso sin_stop sale en los dos simbolos, nada se paga y el
    tic no revienta."""
    sec = S.Secuencia(nombre="decide revienta", desfase=0, minutos=6, vidas=[
        S._v(1, "BTCUSDT:Buy", [(0.9, "abre", 0.004, 110000), (5.0, "cierra", 0, 110300)], 0),
        S._v(2, "ETHUSDT:Sell", [(1.2, "abre", 0.05, 3900), (5.5, "cierra", 0, 3880)], 0)])

    def revienta(self, ahora):
        raise RuntimeError("identidad rota")
    with mock.patch.object(vidas.Libro, "decide", revienta):
        s = S.simula(sec, sv)
    avisos = [t for _ts, t in s.reg.textos if "sin stop" in t]
    assert any("BTCUSDT LARGO" in t for t in avisos) and any("ETHUSDT CORTO" in t for t in avisos), avisos
    assert s.reg.errores == [] and s.reg.pagos == []


# ---- EL CONTROL POSITIVO: cada mutante del validador hace caer al simulador (si no cae, el simulador no mide eso)
def _sin_resultados(filtro):
    original = vidas.Libro.decide

    def decide(self, ahora):
        out = original(self, ahora)
        out["resultados"] = [x for x in out["resultados"] if not filtro(x)]
        return out
    return mock.patch.object(vidas.Libro, "decide", decide)


def _evalua_tarde(minutos):
    original = vidas.Libro.decide

    def decide(self, ahora):
        out = original(self, ahora)
        out["firmes"] = {i: f for i, f in out["firmes"].items() if ahora - f["desde"] >= minutos * 60_000}
        return out
    return mock.patch.object(vidas.Libro, "decide", decide)


def _sin_punto_1():
    """La seguridad DETRAS de la identidad (como en R6): decide revienta y los avisos no llegan a calcularse."""
    original = sv.Bot.seguridad

    def revienta(self, ahora):
        raise RuntimeError("identidad rota")

    async def seguridad(self, lista):
        self.libro.decide(int(time.time() * 1000))
        return await original(self, lista)
    return [mock.patch.object(vidas.Libro, "decide", revienta), mock.patch.object(sv.Bot, "seguridad", seguridad)]


MUTANTES = {
    "no puntuar nunca": (lambda: [_sin_resultados(lambda x: True)], "I7"),
    "no evaluar nunca": (lambda: [mock.patch.object(sv.Bot, "evalua_una", lambda self, p, m: _nada())], "I1"),
    "sin puntuar en vez de cifra": (lambda: [mock.patch.object(vidas.Libro, "_resultado", staticmethod(
        lambda v: {"pnl": None, "ordenes": [f["orden"] for f in v["filas"]], "nota": "sin puntuar"}))], "I6"),
    "sin_stop por clave": (lambda: [mock.patch.object(sv.Bot, "clave_aviso", lambda self, p: p["clave"])], "I3"),
    "sin CERRADA con mas de un tramo": (lambda: [_sin_resultados(lambda x: x[1]["tramos"] > 1)], "I7"),
    "evaluar solo pasados 11 min": (lambda: [_evalua_tarde(11)], "I1"),
    "excepcion en decide sin el punto 1": (_sin_punto_1, "I3"),
}


async def _nada():
    return None


@pytest.mark.parametrize("nombre", list(MUTANTES))
def test_cada_mutante_hace_caer_al_simulador(nombre):
    parches, invariante = MUTANTES[nombre]
    ps = parches()
    for p in ps:
        p.start()
    try:
        r = S.lote(sv, 1, 300)
    finally:
        for p in ps:
            p.stop()
    vistos = {x.split(" ")[0] for _n, f in r["fallos"] for x in f}
    assert invariante in vistos, f"el mutante «{nombre}» no hace caer {invariante}: cae {sorted(vistos)}"
