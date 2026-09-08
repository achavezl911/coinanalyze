"""Dos rutas del mismo producto que publican LA MISMA MAGNITUD tienen que coincidir.

POR QUE ASI Y NO CONTRA UNA CONSTANTE. El fallo -`app/rango.py:95` multiplicaba el funding por
cien- vivio meses en el repo. Un test que comparase cada ruta contra un numero escrito a mano NO
lo habria cazado: quien escribio la ruta habria escrito la misma constante equivocada, porque el
error estaba en su idea de la ESCALA, no en su aritmetica. **La constante habria sido la
equivocada.** Lo unico que lo caza es enfrentar dos implementaciones INDEPENDIENTES de la misma
magnitud y exigir que se den la mano.

Aqui corren LAS DOS DE VERDAD, no una copia de ninguna:

  app.scalp_logic.funding_context   -> `current_pct`   (sirve /api/funding-context)
  app.rango._ventana                -> `funding_medio_pct_8h` (sirve /api/rango/estructura)

Las dos leen `funding_rate.fr_close` y las dos dicen «porcentaje por periodo de 8 h». Se les da
EL MISMO `fr_close` en el MISMO instante -una conexion falsa que responde lo mismo a las dos- de
modo que cualquier diferencia en la salida es diferencia de ESCALA y de nada mas. El funding se
mueve, asi que compararlas contra la base en dos momentos mediria la deriva, no la escala.
"""

import math
from datetime import UTC, datetime

import pytest

from app.rango import _ventana
from app.scalp_logic import funding_context

# MEDIDO en 140 el 2026-09-07: avg(fr_close) = 0.002760 para BTCUSDT_PERP.A sobre 954 muestras
# de 5 min en la ventana del viernes. Es el valor CRUDO de la columna, sin tocar.
FR_CLOSE_CRUDO = 0.002760

# La fila que `_ventana` espera de su consulta unica.
FILA_RANGO = {
    "velas": 4770, "px_ini": 81000.1, "px_fin": 78989.3,
    "cvd_spot": -113_608_752.0, "n_spot": 9540, "ballena": 0.0,
    "oi_ini": 9_050_247_714.0, "oi_fin": 8_520_487_323.0, "n_oi": 954,
    "funding": FR_CLOSE_CRUDO, "n_fund": 954,
    "liq_long": 60_862_490.0, "liq_short": 20_465_735.0, "n_liq": 482,
}


class ConexionDeLaMismaLectura:
    """Responde EL MISMO `fr_close` a quien lo pida, venga de la ruta que venga.

    Reparte por el texto de la consulta y NO por el orden de las llamadas: si dependiera del
    orden, reordenar el codigo de cualquiera de las dos rutas rompería el test por un motivo que
    no tiene nada que ver con la escala.
    """

    def __init__(self):
        self.consultas = []

    async def fetchval(self, sql, *_a):
        self.consultas.append(sql)
        if "fr_close" in sql:
            return FR_CLOSE_CRUDO
        if "pfr_close" in sql:
            return FR_CLOSE_CRUDO      # predicho igual que el actual: divergencia cero
        return None

    async def fetchrow(self, sql, *_a):
        self.consultas.append(sql)
        # Se reparte por «AS velas», que solo tiene la consulta de `_ventana`. Repartir por
        # «avg(fr_close)» NO valia: la consulta de `_ventana` TAMBIEN lo contiene, asi que se
        # llevaba la fila del historial y el funding salia None. Un discriminador que casa con
        # las dos ramas no discrimina.
        if "AS velas" in sql:
            return dict(FILA_RANGO)
        return {"media": FR_CLOSE_CRUDO, "observados": 96}


@pytest.mark.asyncio
async def test_las_dos_rutas_publican_la_misma_escala_de_funding():
    """EL TEST QUE FALTABA. Con el *100 puesto daba 0.276 contra 0.00276: factor 100 exacto."""
    conn = ConexionDeLaMismaLectura()
    contexto = await funding_context(conn, "BTCUSDT_PERP.A")
    rango = await _ventana(
        conn, "BTCUSDT_PERP.A", "BTC",
        datetime(2026, 9, 4, 9, 30, tzinfo=UTC), datetime(2026, 9, 7, 17, 0, tzinfo=UTC),
    )
    de_contexto = contexto["current_pct"]
    de_rango = rango["funding_medio_pct_8h"]
    assert de_contexto is not None and de_rango is not None
    assert math.isclose(de_rango, de_contexto, rel_tol=1e-6), (
        f"las dos rutas discrepan en la escala del funding con el MISMO fr_close: "
        f"/api/rango/estructura publica {de_rango} y /api/funding-context {de_contexto}; "
        f"el cociente es {de_rango / de_contexto:g}"
    )


@pytest.mark.asyncio
async def test_el_anualizado_de_las_dos_tambien_coincide_y_es_creible():
    """El control que hace falsable lo anterior: dos escalas coherentes ENTRE SI podrian estar
    las dos mal. Anualizar lo delata, porque el resultado tiene sentido fisico y se puede juzgar.

    Con el *100 salian 302 % anuales solo por estar dentro, que no es una cifra de mercado: es un
    error de unidades. Sin el, 3.0 %.
    """
    conn = ConexionDeLaMismaLectura()
    contexto = await funding_context(conn, "BTCUSDT_PERP.A")
    rango = await _ventana(
        conn, "BTCUSDT_PERP.A", "BTC",
        datetime(2026, 9, 4, 9, 30, tzinfo=UTC), datetime(2026, 9, 7, 17, 0, tzinfo=UTC),
    )
    anual_contexto = contexto["annualized_pct"]
    anual_rango = rango["funding_medio_pct_8h"] * 3 * 365
    assert math.isclose(anual_rango, anual_contexto, rel_tol=1e-3), (
        f"anualizados distintos: rango {anual_rango:.4f}% contra contexto {anual_contexto:.4f}%"
    )
    assert 0.0 < anual_contexto < 50.0, (
        f"{anual_contexto:.2f}% anual no es una cifra de funding creible: es un error de unidades"
    )


@pytest.mark.asyncio
async def test_el_nombre_del_campo_dice_el_periodo():
    """El nombre viejo, `funding_medio_pct`, decia «pct» y callaba el PERIODO. Eso es lo que
    invitaba a multiplicar por cien. Que el nombre lo diga es parte del arreglo, no cosmetica."""
    rango = await _ventana(
        ConexionDeLaMismaLectura(), "BTCUSDT_PERP.A", "BTC",
        datetime(2026, 9, 4, 9, 30, tzinfo=UTC), datetime(2026, 9, 7, 17, 0, tzinfo=UTC),
    )
    assert "funding_medio_pct_8h" in rango
    assert "funding_medio_pct" not in rango
