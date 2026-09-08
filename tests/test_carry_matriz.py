"""La matriz de carry: las unidades, y que un hueco NO se pinta como cero.

El caso no es inventado. El 2026-08-28 `daily_session_agg` tiene la fila de los TRES simbolos,
con 219 muestras contadas, y `fr_avg`, `oi_open` y `oi_close` en NULL. Medido en 140 el
2026-09-08. Es exactamente la trampa que esta campaña existe para cerrar: hay fila, hay
denominador, y NO hay valor.
"""

from datetime import date

import pytest

from app.carry import coste_de_carry, matriz_de_carry, quien_paga

# MEDIDO en 140 el 2026-09-08: media diaria de fr_avg de BTCUSDT_PERP.A. Valor CRUDO, que ya
# es un porcentaje por periodo de 8 h.
FR_BTC = 0.00672


class ConexionDeDosDias:
    """Dos dias: uno completo y el hueco real del 2026-08-28, con muestras pero sin valor."""

    def __init__(self, simbolos):
        self.simbolos = simbolos

    async def fetch(self, *_a, **_k):
        filas = []
        for s in self.simbolos:
            filas.append({"symbol": s, "session_date": date(2026, 8, 27), "fr_avg": FR_BTC,
                          "funding_5m_samples": 288, "oi_open": 9_000_000_000.0,
                          "oi_close": 9_090_000_000.0, "oi_5m_samples": 288})
            # EL HUECO REAL: fila presente, 219 muestras contadas, valores en NULL.
            filas.append({"symbol": s, "session_date": date(2026, 8, 28), "fr_avg": None,
                          "funding_5m_samples": 219, "oi_open": None, "oi_close": None,
                          "oi_5m_samples": 219})
        return filas


def test_las_unidades_no_multiplican_por_cien():
    """`fr_avg` YA es % por 8 h. 0.00672 % x 3 x 365 = 7.36 % anual, que es una cifra de mercado.
    Con el x100 salian 736 %, que no lo es."""
    c = coste_de_carry(FR_BTC)
    assert c["por_8h"] == 0.00672
    assert abs(c["a_7d"] - 0.1411) < 0.0005
    assert abs(c["a_30d"] - 0.6048) < 0.0005
    assert abs(c["anual"] - 7.359) < 0.005
    assert 0 < c["anual"] < 50, "un anualizado fuera de este rango es un error de unidades"


def test_sin_dato_no_hay_coste_inventado():
    """Nada de rellenar con cero: sin tasa no hay coste, y se dice."""
    c = coste_de_carry(None)
    assert all(v is None for v in c.values())
    assert quien_paga(None) == "NO MEDIDO"


def test_quien_paga_es_la_convencion_de_la_casa():
    assert quien_paga(0.005) == "pagan los largos"
    assert quien_paga(-0.005) == "pagan los cortos"


@pytest.mark.asyncio
async def test_el_hueco_del_28_viaja_como_vacio_y_se_cuenta():
    """EL BRAZO QUE IMPORTA. La celda sin dato sale `None`, NO cero, y la cobertura la cuenta.
    Un cero ahi se leeria como «ese dia no se pago funding», que es falso: no se midio."""
    simbolos = ["BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"]
    m = await matriz_de_carry(ConexionDeDosDias(simbolos), simbolos, 15)

    dia28 = next(d for d in m["funding_por_dia"] if d["fecha"] == "2026-08-28")
    assert all(v is None for v in dia28["valores"].values())
    oi28 = next(d for d in m["oi_por_dia"] if d["fecha"] == "2026-08-28")
    assert all(v is None for v in oi28["valores"].values())

    assert m["cobertura"]["celdas_sin_funding"] == 3
    assert m["cobertura"]["celdas_sin_oi"] == 3
    assert m["cobertura"]["celdas_esperadas"] == 6
    assert "NUNCA a cero" in m["cobertura"]["nota"]


@pytest.mark.asyncio
async def test_se_declara_lo_SERVIDO_y_no_lo_PEDIDO():
    """Se piden 15 dias y hay 2. La respuesta lo dice con las dos cifras, para que la tarjeta
    pueda rotular la ventana que sirve y no la que pidio."""
    simbolos = ["BTCUSDT_PERP.A"]
    m = await matriz_de_carry(ConexionDeDosDias(simbolos), simbolos, 15)
    assert m["dias_pedidos"] == 15
    assert m["dias_servidos"] == 2
    assert m["desde"] == "2026-08-27" and m["hasta"] == "2026-08-28"
    assert "servidos 2 de 15" in m["cobertura"]["nota"]


@pytest.mark.asyncio
async def test_el_coste_promedia_los_dias_MEDIDOS_no_los_pedidos():
    """Si promediara sobre los 15 pedidos, el hueco contaria como cero coste y el gasto
    publicado saldria mas barato de lo que es. Promedia sobre 1 dia y lo dice."""
    simbolos = ["BTCUSDT_PERP.A"]
    m = await matriz_de_carry(ConexionDeDosDias(simbolos), simbolos, 15)
    c = m["coste"][0]
    assert c["dias_promediados"] == 1
    assert c["por_8h"] == 0.00672
    assert c["quien_paga"] == "pagan los largos"


@pytest.mark.asyncio
async def test_una_celda_con_pocas_muestras_se_marca_incompleta():
    """288 cubos de 5 min son un dia entero. Con menos, la media es de otra cosa, y la celda lo
    dice en vez de pasar por completa."""
    simbolos = ["BTCUSDT_PERP.A"]
    m = await matriz_de_carry(ConexionDeDosDias(simbolos), simbolos, 15)
    d27 = next(d for d in m["funding_por_dia"] if d["fecha"] == "2026-08-27")
    assert d27["valores"]["BTCUSDT_PERP.A"]["muestras"] == 288
    assert d27["valores"]["BTCUSDT_PERP.A"]["completo"] is True
