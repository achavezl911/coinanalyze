"""Los niveles de referencia dicen SOBRE CUANTAS VELAS se calculo cada uno.

POR QUE ESTE FICHERO. Medido contra `ohlcv` en 140 el 2026-09-07T17:15Z:

    asia      80410.8 / 78938.7   velas=480 de 480    sesion COMPLETA
    london    79655.1 / 78636.0   velas=540 de 540    sesion COMPLETA
    new_york  79613.8 / 78636.0   velas=215 de 216    EN CURSO, de 540 que dura la sesion

El «maximo de Nueva York» era el maximo de las primeras 3.6 h de una sesion de 9 h, y la mesa lo
presentaba igual que los otros dos. Un maximo de sesion sacado de un puñado de velas y uno sacado
de la sesion completa no son la misma cifra.

Aqui se prueba EJECUTANDO la funcion con una conexion de mentira: la API del espejo -que seria el
camino para ver el efecto antes de desplegar- no esta levantada (127.0.0.1:8001 no contesta).
Lo que esto prueba es la FORMA del sobre; que 140 lo sirva lo dira el despliegue.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.scalp_logic import reference_levels


class _Conn:
    """Devuelve siempre las mismas velas: lo que se mide aqui es el recuento, no el precio."""

    def __init__(self, n: int = 7) -> None:
        self.n = n

    async def fetchrow(self, _q, _sym, a, b):
        # `n` finge que hay una vela por minuto pero solo hasta un tope, para que el recuento y
        # el hueco sean distinguibles. El maximo y el minimo dan igual para este test.
        cabe = max(0, int((min(b, datetime.now(UTC)) - a).total_seconds() // 60))
        return {"h": 100.0, "l": 90.0, "n": min(self.n, cabe)}

    async def fetchval(self, _q, *_a):
        return 95.0


@pytest.mark.asyncio
async def test_cada_nivel_dice_sobre_cuantas_velas_se_calculo() -> None:
    d = await reference_levels(_Conn(), "BTCUSDT_PERP.A")
    for nombre, s in d["sessions_today_utc"].items():
        assert "velas" in s, f"{nombre} no dice sobre cuantas velas se calculo"
        assert "velas_posibles" in s, f"{nombre} no dice cuantas cabian"
        assert "duracion_min" in s, f"{nombre} no dice cuanto dura su ventana"
        assert isinstance(s["velas"], int) and s["velas"] >= 0


@pytest.mark.asyncio
async def test_una_ventana_en_curso_se_declara_en_curso() -> None:
    """EL BRAZO QUE IMPORTA: sin el, la tarjeta no puede distinguir una sesion cerrada de una a
    medias, que es justo el defecto que se arregla."""
    d = await reference_levels(_Conn(), "BTCUSDT_PERP.A")
    ahora = datetime.now(UTC)
    dia0 = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    for nombre, s in d["sessions_today_utc"].items():
        fin_h = int(s["window_utc"].split("-")[1].split(":")[0])
        esperado = ahora < dia0 + timedelta(hours=fin_h)
        assert s["en_curso"] is esperado, f"{nombre}: en_curso={s['en_curso']} y deberia ser {esperado}"


@pytest.mark.asyncio
async def test_velas_posibles_nunca_supera_la_duracion_de_la_ventana() -> None:
    """El denominador honesto de una ventana en curso es lo que va de ella, no su duracion
    entera. Si `velas_posibles` pasara de `duracion_min`, la tarjeta diria «215 de 216» de una
    sesion de 540 minutos y estaria tapando justo lo que este cambio destapa."""
    d = await reference_levels(_Conn(10_000), "BTCUSDT_PERP.A")
    for nombre, s in d["sessions_today_utc"].items():
        assert s["velas_posibles"] <= s["duracion_min"], nombre
        assert s["velas"] <= s["velas_posibles"], nombre


@pytest.mark.asyncio
async def test_la_nota_no_declara_una_retencion_que_no_controla() -> None:
    """LA NOTA ERA FALSA Y NADIE LA HABIA MEDIDO. Decia «retencion ~14d»; medido contra la tabla,
    `ohlcv` 1min va del 2026-07-23 al 2026-09-07: **45.7 dias**. Una nota es una afirmacion como
    cualquier otra. Este test no comprueba la retencion -eso es de 140-: comprueba que la ruta ya
    no afirma una cifra que no controla."""
    d = await reference_levels(_Conn(), "BTCUSDT_PERP.A")
    assert "14d" not in d["note"], "la nota vuelve a declarar una retencion sin medirla"
    assert "velas" in d["note"], "la nota tiene que decir que cada nivel trae su recuento"


@pytest.mark.asyncio
async def test_los_dias_tambien_traen_su_recuento() -> None:
    d = await reference_levels(_Conn(), "BTCUSDT_PERP.A")
    assert d["previous_day"]["en_curso"] is False
    assert d["current_day"]["en_curso"] is True
    assert d["previous_day"]["velas_posibles"] == 1440
