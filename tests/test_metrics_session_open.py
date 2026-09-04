"""El minuto de apertura de la sesion NYSE no puede tumbar el snapshot entero.

ROJO ANTES DEL ARREGLO. compute_snapshot pide un GapRequirement sobre
[session_start, price_cutoff). current_nyse_start() devuelve las 09:30 de Nueva York
-una frontera de minuto exacta- y price_cutoff es floor(now, 60 s), asi que durante los
60 s siguientes a la apertura los dos son el MISMO instante y la ventana es [t,t).
_validated_window (app/data_gaps.py:77) la rechaza, y hace bien; lo que estaba mal era
pedirsela. El ValueError sube hasta run_aligned_feed (app/ingest.py:1023) y se lleva por
delante el snapshot de todos los simbolos y el latido del feed, que se escribe DESPUES de
publish_snapshot.

Medido en 140 por el operador sobre 30 dias de journal: 46 tracebacks, dos por dia -uno
por ciclo, 13:30:05Z ohlcv y 13:30:19Z metrics-, 23 dias elegibles de 23, ninguna otra
hora recurrente.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.data_gaps import GapRequirement
from app.metrics import compute_snapshot, current_nyse_start

# Una apertura en cada regimen horario. El fallo NO esta atado a las 13:30Z: en EST la
# apertura es a las 14:30Z. Un check o un arreglo que fije la hora se cae en noviembre.
APERTURA_EDT = datetime(2026, 9, 3, 13, 30, tzinfo=UTC)  # el dia del traceback medido
APERTURA_EST = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
APERTURAS = [
    pytest.param(APERTURA_EDT, id="edt-1330Z"),
    pytest.param(APERTURA_EST, id="est-1430Z"),
]

# El SQL real devuelve NULL sobre la ventana vacia -SUM() FILTER sobre cero filas-. Aqui
# van NUMEROS a proposito: asi "sale None" solo puede venir del arreglo, nunca del fixture.
_FILA = {
    "price": 100.0,
    "price_ts": datetime(2026, 9, 3, 13, 29, tzinfo=UTC),
    "price_1h": 99.0,
    "oi_now": 250.0,
    "oi_ts": datetime(2026, 9, 3, 13, 25, tzinfo=UTC),
    "oi_old": 100.0,
    "cvd_session": 1234.0,
    "spot_cvd_session": 567.0,
}


class _EspiaDeRequisitos:
    """Conn falsa que anota las claves que llegan a blocking_requirement_keys."""

    def __init__(self) -> None:
        self.claves: list[str] = []

    async def fetchrow(self, _query, *_args):
        return dict(_FILA)

    async def fetch(self, query, *args):
        # liquidation_history_observation tambien llama a fetch, contra pipeline_heartbeat
        # y con UN argumento. La de requisitos es la unica que menciona data_gap.
        if "data_gap" in query:
            self.claves = list(args[0])
        return []


@pytest.mark.parametrize("apertura", APERTURAS)
async def test_el_minuto_de_apertura_no_tumba_el_snapshot(apertura):
    assert current_nyse_start(apertura) == apertura, "el fixture no cae en la apertura"
    conn = _EspiaDeRequisitos()

    # SIN EL ARREGLO esta llamada levanta ValueError("gap and metric windows must satisfy
    # start < end") y el test muere en esta linea.
    snap = await compute_snapshot(
        conn, "BTCUSDT_PERP.A", "BTC", apertura + timedelta(seconds=5)
    )

    # La ventana de sesion no tiene un solo bucket cerrado: no hay requisito que pedir.
    assert "fut_session" not in conn.claves
    assert "spot_session" not in conn.claves
    # Y el resto del snapshot SI se publica. No se tira la foto entera por una pata.
    assert "price" in conn.claves
    assert conn.claves.count("spot_24h") == 3
    assert snap["price"] == 100.0
    # NO MEDIDO, no cero: la sesion no tiene todavia ni un minuto que medir.
    assert snap["cvd_nyse_session"] is None
    assert snap["cvd_spot_session"] is None
    assert snap["cvd_diff_ses"] is None


@pytest.mark.parametrize("apertura", APERTURAS)
async def test_control_el_minuto_siguiente_si_pide_la_sesion(apertura):
    """CONTROL. La omision dura UN minuto; no se come el requisito para siempre."""
    conn = _EspiaDeRequisitos()

    snap = await compute_snapshot(
        conn, "BTCUSDT_PERP.A", "BTC", apertura + timedelta(seconds=65)
    )

    assert "fut_session" in conn.claves
    assert conn.claves.count("spot_session") == 3
    assert snap["cvd_nyse_session"] == 1234.0
    assert snap["cvd_spot_session"] == 567.0


def test_control_el_validador_sigue_rechazando_la_ventana_vacia():
    """CONTROL. El arreglo no relaja _validated_window: [t,t) sigue siendo un error."""
    with pytest.raises(ValueError, match="start < end"):
        GapRequirement(
            "x", "ohlcv_1min", "binance", "perpetual", "BTCUSDT_PERP.A",
            APERTURA_EDT, APERTURA_EDT,
        ).normalized()
