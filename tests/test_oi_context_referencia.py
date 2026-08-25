"""La barra de referencia de /api/oi-context se resuelve por TIEMPO, no por posicion.

El fallo que fijan estos tests: ``series[max(0, len-1-round(sec/cadencia))]`` solo cae
donde debe si la serie es contigua. Con un hueco devuelve una barra mas vieja sin
decirlo, asi que el "cambio de 5m" puede estar midiendo 20m con la etiqueta de 5m, y esa
cifra viaja al contexto que se le manda al modelo (app/ai_context.py, app/analysis_prompt.py).

Las series se sirven con una conexion falsa que no toca ninguna base. El valor de cada
barra codifica su distancia a la ultima (1000-k para OI, 50000-k para precio), de modo
que del porcentaje devuelto se deduce QUE barra se uso. Ese es el sujeto.
"""

from datetime import datetime, timedelta

import pytest

from app.data_gaps import align_down
from app.scalp_logic import _OI_WINDOWS, OI_CADENCE, PRICE_CADENCE, oi_context

VALOR_OI = 1000.0
VALOR_PX = 50000.0


def _ultima(fin: datetime, cadencia: timedelta) -> datetime:
    """El ultimo bucket ESTRICTAMENTE anterior a fin, que es lo que devuelve la consulta."""
    ultima = align_down(fin, cadencia)
    return ultima - cadencia if ultima >= fin else ultima


class ConexionDeSerie:
    """Sirve open_interest y ohlcv desde memoria, con los huecos que se le pidan.

    ``huecos`` son distancias en buckets desde la ultima barra: {1,2,3} en OI es un
    agujero de 15 min pegado al presente. ``vida`` acota cuantos buckets hacia atras
    existe la serie, para el caso de un feed recien nacido.
    """

    def __init__(
        self,
        *,
        huecos_oi: set[int] | None = None,
        huecos_px: set[int] | None = None,
        vida_oi: int = 10**6,
        vida_px: int = 10**6,
    ) -> None:
        self.huecos_oi = huecos_oi or set()
        self.huecos_px = huecos_px or set()
        self.vida_oi = vida_oi
        self.vida_px = vida_px
        self.fin: datetime | None = None

    def _serie(self, inicio, fin, cadencia, huecos, vida, base, clave):
        ultima = _ultima(fin, cadencia)
        filas, k = [], 0
        while ultima - k * cadencia >= inicio and k <= vida:
            if k not in huecos:
                filas.append({"ts": ultima - k * cadencia, clave: base - k})
            k += 1
        return list(reversed(filas))

    async def fetch(self, sql, *args):
        if "FROM open_interest" in sql:
            self.fin = args[2]
            return self._serie(
                args[1], args[2], OI_CADENCE, self.huecos_oi, self.vida_oi, VALOR_OI, "oi_close"
            )
        if "FROM ohlcv" in sql:
            return self._serie(
                args[1], args[2], PRICE_CADENCE, self.huecos_px, self.vida_px, VALOR_PX, "close"
            )
        return []

    async def fetchval(self, *_args):
        return None


def _posicional(valores: list[float], cadencia_s: int, sec: int) -> float:
    """El indexado por POSICION que habia antes. Se conserva para poder demostrar que
    devolvia otra ventana: sin esta funcion, "lo arreglamos" seria una afirmacion sin
    contraste."""
    return valores[max(0, len(valores) - 1 - round(sec / cadencia_s))]


def _pct(desde: float, hasta: float) -> float:
    return round((hasta / desde - 1) * 100, 3)


async def _contexto(conn) -> dict:
    salida = await oi_context(conn, "BTCUSDT_PERP.A")
    assert salida["available"] is True
    return salida


@pytest.mark.parametrize("sec_esperado", [sec for _, sec in _OI_WINDOWS])
async def test_toda_referencia_esta_exactamente_a_su_distancia(sec_esperado) -> None:
    """Sobre una serie completa, ninguna ventana puede salir null ni descuadrada.

    La de 24 h es la que prueba el margen de historia: su referencia esta 86400 s antes
    de la ULTIMA barra, que va por detras de fin, asi que cae fuera de [fin-86400, fin).
    """
    salida = await _contexto(ConexionDeSerie())
    lab = next(lab for lab, sec in _OI_WINDOWS if sec == sec_esperado)
    ventana = salida["windows"][lab]
    for ancla, referencia, cifra in (
        ("oi_latest_ts", "oi_reference_ts", "oi_change_pct"),
        ("price_latest_ts", "price_reference_ts", "price_change_pct"),
    ):
        assert ventana[cifra] is not None, f"{lab}/{cifra} null con la serie completa"
        distancia = datetime.fromisoformat(salida[ancla]) - datetime.fromisoformat(
            ventana[referencia]
        )
        assert distancia.total_seconds() == sec_esperado


async def test_con_un_hueco_de_15m_la_referencia_de_5m_no_es_una_barra_de_20m() -> None:
    """El caso que da nombre a la unidad: hueco en k=1,2,3 (los 15 min anteriores).

    5m y 15m piden barras que no existen -> null. 1h y 4h existen y tienen que salir
    sobre SU barra, no sobre la que caiga en la posicion desplazada por el hueco.
    """
    conn = ConexionDeSerie(huecos_oi={1, 2, 3})
    salida = await _contexto(conn)
    w = salida["windows"]

    assert w["5m"]["oi_change_pct"] is None
    assert w["5m"]["oi_reference_ts"] is None
    assert w["15m"]["oi_change_pct"] is None
    assert w["15m"]["oi_reference_ts"] is None

    # 1h son 12 buckets de 5 min hacia atras: la barra existe y vale 1000-12.
    assert w["1h"]["oi_change_pct"] == _pct(VALOR_OI - 12, VALOR_OI)
    assert w["4h"]["oi_change_pct"] == _pct(VALOR_OI - 48, VALOR_OI)

    # Y la version anterior devolvia OTRA ventana: con tres barras menos delante, la
    # posicion len-1-12 cae en la barra de hace 75 min y no en la de hace 60.
    valores = [VALOR_OI - k for k in range(300) if k not in {1, 2, 3}][::-1]
    antes = _pct(_posicional(valores, 300, 3600), VALOR_OI)
    assert antes != w["1h"]["oi_change_pct"]
    assert _posicional(valores, 300, 3600) == VALOR_OI - 15

    # La pata de precio no tiene huecos en este caso y no se ve afectada.
    assert w["5m"]["price_change_pct"] == _pct(VALOR_PX - 5, VALOR_PX)


async def test_el_hueco_de_precio_solo_anula_la_pata_de_precio() -> None:
    """Las dos patas se resuelven por separado: un hueco en ohlcv no puede llevarse por
    delante la cifra de OI, que se calculo sobre barras que si estaban."""
    salida = await _contexto(ConexionDeSerie(huecos_px={15}))
    w = salida["windows"]
    assert w["15m"]["price_change_pct"] is None
    assert w["15m"]["price_reference_ts"] is None
    assert w["15m"]["oi_change_pct"] == _pct(VALOR_OI - 3, VALOR_OI)
    assert w["5m"]["price_change_pct"] == _pct(VALOR_PX - 5, VALOR_PX)


async def test_una_serie_mas_corta_que_la_ventana_no_inventa_un_cambio_de_24h() -> None:
    """El otro lado del mismo fallo: max(0, ...) recortaba al indice 0, o sea que un feed
    con dos horas de vida devolvia un "cambio de 24 h" calculado sobre esas dos horas."""
    salida = await _contexto(ConexionDeSerie(vida_oi=24, vida_px=120))
    w = salida["windows"]
    assert w["1h"]["oi_change_pct"] == _pct(VALOR_OI - 12, VALOR_OI)
    for lab in ("4h", "24h"):
        assert w[lab]["oi_change_pct"] is None
        assert w[lab]["oi_reference_ts"] is None
        assert w[lab]["price_change_pct"] is None
        assert w[lab]["price_reference_ts"] is None


async def test_la_cobertura_no_cuenta_el_margen_de_historia() -> None:
    """El margen que se pide de mas es para resolver la referencia, no para inflar la
    cobertura: coverage sigue midiendo sobre [fin-sec, fin)."""
    salida = await _contexto(ConexionDeSerie())
    cobertura = salida["coverage"]["24h"]
    assert cobertura["sources"]["open_interest_5min"]["expected_buckets"] == 288
    assert cobertura["sources"]["open_interest_5min"]["observed_buckets"] == 288
    assert cobertura["sources"]["ohlcv_1min"]["expected_buckets"] == 1440
    assert cobertura["sources"]["ohlcv_1min"]["observed_buckets"] == 1440
