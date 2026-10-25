"""BOT-2 · remate 6: el SIMULADOR (tests/simulador_bot.py) sobre el bot de la rama: N = 2000 secuencias al azar por semilla y
3 semillas, y los casos de los tres validadores, con las invariantes I1-I6 contra la verdad (ver su docstring). Con el
app/bot de main@7870ae8 (R5) cae: x1-tmp/bot2/r6-viejo-sim.sh. Sin red y sin base: todo en memoria."""

from __future__ import annotations

import pytest
import simulador_bot as S

from app.bot import servicio as sv


@pytest.mark.parametrize("semilla", [1, 2, 3])
def test_el_simulador_no_rompe_ninguna_invariante(semilla):
    r = S.lote(sv, semilla, 2000)
    assert r["fallos"] == [], f"{len(r['fallos'])} secuencias rompen alguna invariante: {r['fallos'][:3]}"
    assert r["cerradas_simples"] > 100 and r["cerradas"] > 300  # que de verdad haya vidas que puntuar


@pytest.mark.parametrize("sec", S.fijas(), ids=lambda s: s.nombre)
def test_los_casos_de_los_validadores(sec):
    assert S.comprueba(S.simula(sec, sv)) == []
