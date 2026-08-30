"""K69b · la herramienta que le faltaba al ohlcv historico.

Lo que aqui se fija son las dos cosas que no puede comprobar upsert_ohlcv por su cuenta:
que el intervalo este DECLARADO -- porque cada uno tiene su propio horizonte y tratarlos
como el mismo numero ya costo un tramo de datos -- y que la cuenta de cobertura sea la
del intervalo pedido y no la de otro.

La validacion de cada vela (precios coherentes, volumenes, y marcas DENTRO de la ventana)
vive en upsert_ohlcv y ya esta probada en tests/test_ingest.py; no se duplica aqui.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from scripts.backfill_ohlcv import CADENCIA_SEGUNDOS, buckets_esperados

INICIO = datetime(2026, 8, 28, 7, 45, tzinfo=UTC)
FIN = datetime(2026, 8, 28, 21, 5, tzinfo=UTC)


def test_la_cobertura_se_cuenta_con_la_cadencia_del_intervalo_pedido():
    """13 h 20 min son 800 minutos: 800 buckets de 1min y 160 de 5min. Contar con la
    cadencia equivocada da una cobertura que parece medida y no lo esta."""
    assert buckets_esperados(INICIO, FIN, "1min") == 800
    assert buckets_esperados(INICIO, FIN, "5min") == 160


def test_una_ventana_vacia_o_invertida_da_cero_y_no_un_negativo():
    """Un negativo se propagaria al informe como 'siguen_ausentes' absurdo y haria que
    un rescate vacio pareciera un exito."""
    assert buckets_esperados(FIN, INICIO, "5min") == 0
    assert buckets_esperados(INICIO, INICIO, "5min") == 0


def test_los_buckets_parciales_no_se_cuentan():
    """Medio bucket no es un bucket. Se trunca hacia abajo para que la cobertura nunca
    prometa mas de lo que cabe."""
    casi = datetime(2026, 8, 28, 7, 49, tzinfo=UTC)
    assert buckets_esperados(INICIO, casi, "5min") == 0
    assert buckets_esperados(INICIO, casi, "1min") == 4


def test_solo_se_declaran_los_intervalos_cuyo_horizonte_se_ha_medido():
    """Guarda contra el crecimiento distraido: el horizonte del proveedor es un numero
    POR INTERVALO -- ~29 h en 1min, mas de 96 h en 5min -- y anadir uno aqui sin medirlo
    reproduce exactamente la fecha limite falsa del tramo mudo."""
    assert set(CADENCIA_SEGUNDOS) == {"1min", "5min"}
    assert CADENCIA_SEGUNDOS == {"1min": 60, "5min": 300}


@pytest.mark.parametrize("interval", sorted(CADENCIA_SEGUNDOS))
def test_la_cadencia_declarada_divide_la_hora_exacta(interval):
    """Una cadencia que no divide la hora produce buckets desalineados con date_bin, que
    es como el barrido de 5min no casaba ni una marca antes de alinearlo."""
    assert 3600 % CADENCIA_SEGUNDOS[interval] == 0
