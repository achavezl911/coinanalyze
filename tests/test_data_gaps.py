from datetime import UTC, date, datetime, timedelta

import pytest

import app.api as api
from app.api import mask_gapped_series_rows
from app.data_gaps import (
    DataGap,
    RecoveryObservation,
    RecoveryValidationError,
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
