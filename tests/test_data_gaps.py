from datetime import UTC, date, datetime, timedelta

import pytest

import app.api as api
from app.api import mask_gapped_series_rows
from app.data_gaps import (
    DataGap,
    RecoveryObservation,
    RecoveryValidationError,
    align_down,
    coverage_entry,
    expected_buckets,
    missing_cadence_windows,
    record_data_gap,
    validate_recovery,
)
from app.metrics import session_bounds


def test_missing_cadence_windows_use_the_supplied_feed_cadence() -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)
    assert missing_cadence_windows(
        [start, start + timedelta(minutes=3)],
        start=start,
        end=start + timedelta(minutes=4),
        cadence=timedelta(minutes=1),
    ) == [(start + timedelta(minutes=1), start + timedelta(minutes=3))]


async def test_event_stream_silence_cannot_be_recorded_as_missing_cadence() -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)

    class NoQueryConnection:
        async def fetchval(self, *_args):
            raise AssertionError("invalid event-stream evidence must fail before SQL")

    with pytest.raises(ValueError, match="silence"):
        await record_data_gap(
            NoQueryConnection(),  # type: ignore[arg-type]
            feed="liquidations",
            feed_class="event_stream",
            exchange="binance",
            market="perpetual",
            symbol="BTCUSDT_PERP.A",
            granularity="event",
            start=start,
            end=start + timedelta(minutes=5),
            evidence_type="missing_interval",
            detection_reason="no events arrived",
            detection_source="silence detector",
        )


class _Adapter:
    name = "exact"
    feed = "ohlcv_1min"
    exchange = "binance"
    market = "perpetual"
    granularity = "1min"


def test_recovery_rejects_wrong_symbol_even_when_http_source_fields_match() -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)
    gap = DataGap(
        1,
        "ohlcv_1min",
        "cadence",
        "binance",
        "perpetual",
        "BTCUSDT_PERP.A",
        "1min",
        start,
        start + timedelta(minutes=1),
        timedelta(minutes=1),
        "unresolved",
    )
    observation = RecoveryObservation(
        start,
        "one",
        "ohlcv_1min",
        "binance",
        "perpetual",
        "ETHUSDT_PERP.A",
        "1min",
        {},
    )
    with pytest.raises(RecoveryValidationError, match="identity"):
        validate_recovery(gap, _Adapter(), [observation])  # type: ignore[arg-type]


async def test_chart_gap_nulls_the_bucket_and_all_later_cumulative_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)
    rows = [
        {"bucket": start + timedelta(minutes=index), "delta": 1.0, "cvd": index + 1.0}
        for index in range(3)
    ]

    async def blocked(_conn, _requirements):
        return {"value:1", "cumulative:1", "cumulative:2"}

    monkeypatch.setattr(api, "blocking_requirement_keys", blocked)
    await mask_gapped_series_rows(
        object(),  # type: ignore[arg-type]
        rows,
        bucket=timedelta(minutes=1),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        value_keys=("delta",),
        cumulative_keys=("cvd",),
    )

    assert rows == [
        {"bucket": start, "delta": 1.0, "cvd": 1.0},
        {"bucket": start + timedelta(minutes=1), "delta": None, "cvd": None},
        {"bucket": start + timedelta(minutes=2), "delta": 1.0, "cvd": None},
    ]


# --------------------------------------------------------------------------------
# LA VENTANA DE /api/daily NO ES UN DIA UTC, y enmascararla como si lo fuera es peor
# que no enmascararla: pondria a null un dia sano y dejaria intacto el roto.
# session_bounds (app/metrics.py:31) define la sesion de 09:30 a 09:30 de Nueva York,
# asi que ni empieza a medianoche ni mide siempre 24 h -en los cambios de horario mide
# 23 o 25-. Estos tests fijan que la ventana que se le pide a data_gap es ESA.
# --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_la_ventana_de_una_sesion_diaria_es_la_de_nueva_york(monkeypatch) -> None:
    from app.api import _session_window

    filas = [{"session_date": date(2026, 8, 14), "price_close": 62956.0}]
    pedidas: list[tuple[datetime, datetime]] = []

    async def blocked(_conn, requirements):
        pedidas.extend((r.start, r.end) for r in requirements)
        return set()

    monkeypatch.setattr(api, "blocking_requirement_keys", blocked)
    await mask_gapped_series_rows(
        object(),  # type: ignore[arg-type]
        filas,
        bucket=timedelta(days=1),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        value_keys=("price_close",),
        row_window=_session_window,
    )

    assert pedidas == [session_bounds(date(2026, 8, 14))]
    inicio, fin = pedidas[0]
    # Lo que este test existe para impedir: que alguien "simplifique" a medianoche UTC.
    assert (inicio.hour, inicio.minute) != (0, 0), "la sesion no empieza a medianoche UTC"
    assert fin - inicio == timedelta(days=1)


@pytest.mark.asyncio
async def test_el_cambio_de_horario_no_dura_24_h_y_la_ventana_lo_respeta(monkeypatch) -> None:
    """La sesion que CONTIENE el cambio de hora no mide 24 h. Comprobado: la del
    2026-03-08 mide 23 h y la del 2026-11-01 mide 25. Un bucket fijo de 24 h pediria
    una ventana falsa en las dos."""
    from app.api import _session_window

    filas = [{"session_date": date(2026, 3, 8), "price_close": 1.0}]
    pedidas: list[tuple[datetime, datetime]] = []

    async def blocked(_conn, requirements):
        pedidas.extend((r.start, r.end) for r in requirements)
        return set()

    monkeypatch.setattr(api, "blocking_requirement_keys", blocked)
    await mask_gapped_series_rows(
        object(),  # type: ignore[arg-type]
        filas,
        bucket=timedelta(days=1),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        value_keys=("price_close",),
        row_window=_session_window,
    )

    inicio, fin = pedidas[0]
    assert fin - inicio == timedelta(hours=23), (
        "con bucket fijo de 24 h esta ventana seria falsa, y por eso se pide fila a fila"
    )


@pytest.mark.asyncio
async def test_una_fila_sin_sesion_resoluble_no_se_enmascara(monkeypatch) -> None:
    """Antes que inventar una ventana, no enmascarar: un null falso tambien miente."""
    from app.api import _session_window

    filas = [{"session_date": "no-es-una-fecha", "price_close": 7.0}]

    async def blocked(_conn, requirements):
        raise AssertionError("no se puede pedir nada sin ventana resoluble")

    monkeypatch.setattr(api, "blocking_requirement_keys", blocked)
    await mask_gapped_series_rows(
        object(),  # type: ignore[arg-type]
        filas,
        bucket=timedelta(days=1),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        value_keys=("price_close",),
        row_window=_session_window,
    )
    assert filas[0]["price_close"] == 7.0


# --- K03 · el hueco declarado ----------------------------------------------------
# Lo que estos tests sostienen: (1) la ventana servida se cuenta, y por eso aparece el
# bucket que NO ESTA -el que no deja fila que poner a null-, (2) "no hay huecos
# declarados" y "no falta nada" son dos respuestas distintas, y (3) la cobertura de un
# agregado es la conjuncion de sus patas, no la de la que mejor salio.


def test_align_down_usa_la_rejilla_de_la_epoca() -> None:
    """La misma rejilla que date_bin con origen 1970-01-01, o las cuentas no cuadran."""
    momento = datetime(2026, 8, 25, 12, 3, 47, 512000, tzinfo=UTC)
    assert align_down(momento, timedelta(minutes=5)) == datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
    assert align_down(momento, timedelta(minutes=1)) == datetime(2026, 8, 25, 12, 3, tzinfo=UTC)
    ya_alineado = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
    assert align_down(ya_alineado, timedelta(minutes=5)) == ya_alineado


def test_expected_buckets_exige_cadencia_positiva_y_ventana_valida() -> None:
    inicio = datetime(2026, 8, 25, tzinfo=UTC)
    assert expected_buckets(inicio, inicio + timedelta(hours=1), timedelta(minutes=5)) == 12
    with pytest.raises(ValueError):
        expected_buckets(inicio, inicio + timedelta(hours=1), timedelta(0))
    with pytest.raises(ValueError):
        expected_buckets(inicio, inicio, timedelta(minutes=5))


def test_coverage_entry_suma_las_patas_y_complete_es_la_conjuncion() -> None:
    inicio = datetime(2026, 8, 25, tzinfo=UTC)
    entrada = coverage_entry(
        inicio,
        inicio + timedelta(hours=1),
        sources=(("open_interest_5min", 12, 12), ("ohlcv_1min", 60, 47)),
    )
    assert entrada["expected_buckets"] == 72
    assert entrada["observed_buckets"] == 59
    # Una pata completa no salva la ventana: el numero se calculo con 47 de 60 minutos.
    assert entrada["complete"] is False
    assert entrada["sources"]["open_interest_5min"] == {
        "expected_buckets": 12,
        "observed_buckets": 12,
    }


def test_coverage_entry_no_recorta_un_observado_imposible() -> None:
    """Si observado > esperado la cadencia declarada esta mal, y eso hay que VERLO."""
    inicio = datetime(2026, 8, 25, tzinfo=UTC)
    entrada = coverage_entry(
        inicio, inicio + timedelta(hours=1), sources=(("funding_rate_5min", 12, 13),)
    )
    assert entrada["observed_buckets"] == 13
    assert entrada["complete"] is False


@pytest.mark.asyncio
async def test_el_bucket_ausente_sale_en_la_cobertura_aunque_no_deje_fila(monkeypatch) -> None:
    """El caso medido en 140: 16:00 y 18:00 existen, las 17:00 NO, y nadie lo decia.

    Un null no puede ensenar esta perdida porque no hay fila que anular. La unica forma
    de verla es contar los buckets servidos contra los esperados de la ventana.
    """
    inicio = datetime(2026, 8, 14, 15, tzinfo=UTC)
    filas = [
        {"bucket": inicio, "close": 1.0},
        {"bucket": inicio + timedelta(hours=1), "close": None},
        {"bucket": inicio + timedelta(hours=3), "close": None},
        {"bucket": inicio + timedelta(hours=4), "close": 2.0},
    ]

    async def declarados(_conn, **_kwargs):
        return [
            {
                "start": (inicio + timedelta(hours=1, minutes=47)).isoformat(),
                "end": (inicio + timedelta(hours=3, minutes=13)).isoformat(),
                "status": "unrecoverable",
                "declarations": 86,
            }
        ]

    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    sobre = await api.declared_series_response(
        object(),  # type: ignore[arg-type]
        filas,
        interval="1hour",
        bucket=timedelta(hours=1),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
    )
    cobertura = sobre["coverage"]["served_window"]
    assert (cobertura["expected_buckets"], cobertura["observed_buckets"]) == (5, 4)
    assert cobertura["complete"] is False
    # El bucket ausente cae dentro del hueco declarado, asi que esta EXPLICADO.
    assert sobre["data_gaps"]["status"] == "declared"
    assert sobre["data_gaps"]["undeclared_buckets"] == 0
    assert sobre["data_gaps"]["declared"][0]["declarations"] == 86
    assert sobre["rows"] is filas


@pytest.mark.asyncio
async def test_faltar_sin_detector_no_es_lo_mismo_que_no_faltar(monkeypatch) -> None:
    """/api/whale/delta: spot_trades_agg pierde buckets y NADIE los apunta.

    Sin esta distincion, un feed sin detector se lee igual que un feed sano, que es la
    forma mas barata de que una perdida no la vea nunca nadie.
    """
    inicio = datetime(2026, 8, 14, 12, tzinfo=UTC)
    filas = [
        {"bucket": inicio, "whale_delta": 1.0},
        {"bucket": inicio + timedelta(minutes=30), "whale_delta": 2.0},
    ]

    async def declarados(_conn, **_kwargs):
        return []

    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    sobre = await api.declared_series_response(
        object(),  # type: ignore[arg-type]
        filas,
        interval="15min",
        bucket=timedelta(minutes=15),
        feed="spot_trades",
        exchanges=("binance", "bybit", "combined"),
        market="spot",
        symbol="BTCUSDT_PERP.A",
        gap_symbol="BTCUSDT",
    )
    assert sobre["data_gaps"]["status"] == "undeclared"
    assert sobre["data_gaps"]["undeclared_buckets"] == 1
    # La identidad del hueco es la del websocket, no la del simbolo pedido.
    assert sobre["data_gaps"]["symbol"] == "BTCUSDT"
    assert sobre["symbol"] == "BTCUSDT_PERP.A"


@pytest.mark.asyncio
async def test_una_serie_completa_y_sin_huecos_se_declara_limpia(monkeypatch) -> None:
    inicio = datetime(2026, 8, 14, 12, tzinfo=UTC)
    filas = [{"bucket": inicio + timedelta(minutes=15 * i)} for i in range(4)]

    async def declarados(_conn, **_kwargs):
        return []

    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    sobre = await api.declared_series_response(
        object(),  # type: ignore[arg-type]
        filas,
        interval="15min",
        bucket=timedelta(minutes=15),
        feed="open_interest_5min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
    )
    assert sobre["data_gaps"]["status"] == "clean"
    assert sobre["coverage"]["served_window"]["complete"] is True


@pytest.mark.asyncio
async def test_una_serie_vacia_dice_no_data_y_no_inventa_ventana(monkeypatch) -> None:
    async def declarados(_conn, **_kwargs):
        raise AssertionError("sin filas no hay ventana que consultar")

    monkeypatch.setattr(api, "declared_gap_windows", declarados)
    sobre = await api.declared_series_response(
        object(),  # type: ignore[arg-type]
        [],
        interval="5min",
        bucket=timedelta(minutes=5),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
    )
    assert sobre["data_gaps"]["status"] == "no_data"
    assert sobre["data_gaps"]["window_start"] is None
    assert sobre["coverage"]["served_window"] is None
