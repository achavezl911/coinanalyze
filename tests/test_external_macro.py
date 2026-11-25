from datetime import UTC, date, datetime, timedelta

from app.external_macro import (
    align_with_internal,
    build_external_macro_context,
    parse_bls_calendar,
    parse_fomc_calendar,
    parse_fred_csv,
)


def test_official_source_parsers_preserve_date_and_timezone():
    fred = parse_fred_csv(
        "observation_date,DGS2\n2026-08-03,3.71\n2026-08-04,.\n", "DGS2", "treasury_2y"
    )
    assert fred == [("treasury_2y", date(2026, 8, 3), 3.71, "FRED:DGS2")]

    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;TZID=US-Eastern:20260812T083000
SUMMARY:Consumer Price Index
END:VEVENT
END:VCALENDAR
"""
    bls = parse_bls_calendar(ics)
    assert bls[0][2] == "CPI EE.UU."
    assert bls[0][1] == datetime(2026, 8, 12, 12, 30, tzinfo=UTC)

    fomc = """<h4 id="2026">2026 FOMC Meetings</h4>
<div class="fomc-meeting__month"><strong>September</strong></div>
<div class="fomc-meeting__date">15-16*</div>
"""
    meeting = parse_fomc_calendar(fomc)[0]
    assert meeting[0] == "fomc-20260916"
    assert meeting[1] == datetime(2026, 9, 16, 18, 0, tzinfo=UTC)


def test_regime_is_explainable_and_event_risk_blocks_multi_session_entry():
    start = date(2026, 6, 1)
    observations = []
    series = {
        "treasury_2y": [5 - index * 0.02 for index in range(31)],
        "real_yield_10y": [2.5 - index * 0.01 for index in range(31)],
        "usd_broad": [110 - index * 0.1 for index in range(31)],
        "nasdaq": [20_000 + index * 100 for index in range(31)],
        "sp500": [5_000 + index * 20 for index in range(31)],
        "vix": [25 - index * 0.3 for index in range(31)],
        "stablecoin_supply_usd": [200_000_000_000 + index * 200_000_000 for index in range(31)],
        "btc_etf_flow_usd": [50_000_000 for _ in range(31)],
    }
    fetched = datetime(2026, 7, 1, tzinfo=UTC)
    for key, values in series.items():
        observations.extend(
            {
                "series": key,
                "observed_on": start + timedelta(days=index),
                "value": value,
                "source": "test",
                "fetched_at": fetched,
            }
            for index, value in enumerate(values)
        )
    btc = [{"price_close": 100.0} for _ in range(31)]
    now = datetime(2026, 7, 1, tzinfo=UTC)
    events = [
        {
            "event_at": now + timedelta(hours=12),
            "title": "CPI EE.UU.",
            "importance": 3,
            "source": "BLS",
        }
    ]

    context = build_external_macro_context(
        observations, events, btc, now=now, etf_configured=True
    )
    assert context["regime"] == "favorable"
    assert context["coverage_pct"] == 100
    assert "absorbida por oferta" in context["institutional_flows"]["interpretation"]
    aligned = align_with_internal(context, {"bias": "LONG"})
    assert aligned["alignment"]["state"] == "esperar_evento"
    assert "12.0 h" in aligned["alignment"]["reading"]


def _rising(series: str, last: date, days: int, step: float = 1.01) -> list[dict]:
    return [
        {
            "series": series,
            "observed_on": last - timedelta(days=days - 1 - index),
            "value": 100.0 * step**index,
            "source": "test",
            "fetched_at": None,
        }
        for index in range(days)
    ]


def test_m04_series_parada_91_dias_ni_vota_ni_cuenta():
    # M-04 (fable-dz2, caso del banco): con main, seis series FRED paradas hace 91 dias votaban
    # y daban confianza alta, porque el cambio se medía por FILAS y la cobertura por EXISTIR.
    now = datetime(2026, 11, 20, 12, tzinfo=UTC)
    vieja = now.date() - timedelta(days=91)
    observations = []
    for key in ("treasury_2y", "real_yield_10y", "usd_broad", "nasdaq", "sp500", "vix"):
        observations += _rising(key, vieja, 30)
    observations += _rising("stablecoin_supply_usd", now.date(), 40)
    context = build_external_macro_context(observations, [], [], now=now)

    metrics = {m["key"]: m for p in context["pillars"].values() for m in p["metrics"]}
    nasdaq = metrics["nasdaq"]
    # Primero lo que main dice mal (vota 1, confianza alta); despues los campos nuevos.
    assert nasdaq["vote"] == 0 and nasdaq["change"] is None
    assert context["coverage_pct"] == 14 and context["data_confidence"] == "baja"
    assert nasdaq["stale"] is True
    assert nasdaq["observed_on"] == vieja.isoformat() and nasdaq["age_days"] == 91
    assert context["pillars"]["risk"]["state"] == "mixto"
    assert context["regime"] == "sin_datos" and context["available"] is False
    assert context["stale_series"] == ["treasury_2y", "real_yield_10y", "usd_broad", "nasdaq", "sp500", "vix"]
    assert context["as_of"] == now.date().isoformat()
    assert any("usd_broad (91 d > 12)" in item for item in context["limitations"])
    stable = metrics["stablecoin_supply_usd"]
    assert stable["stale"] is False and stable["vote"] == 1
    assert stable["change_base_on"] == (now.date() - timedelta(days=30)).isoformat()


def test_m04_cambio_por_fecha_hueco_y_serie_sana():
    now = datetime(2026, 11, 20, 12, tzinfo=UTC)
    ayer = now.date() - timedelta(days=1)
    # Hueco de 60 dias antes de las 7 ultimas observaciones: la base de 7 dias cae a 66 dias,
    # pasa de 2N y no hay cambio (con main, «5 periodos» medía contra hace 2 meses y votaba).
    hueco = _rising("nasdaq", ayer, 30)
    for row in hueco[:-7]:
        row["observed_on"] -= timedelta(days=60)
    # Serie sana diaria: mismo cambio que 7 periodos (1.01**7) y vota.
    sana = _rising("sp500", ayer, 30)
    # usd_broad semanal con 9 dias (su edad en 140 el 2026-11-22) sigue votando.
    usd = _rising("usd_broad", now.date() - timedelta(days=9), 30, step=0.99)
    context = build_external_macro_context([*hueco, *sana, *usd], [], [], now=now)
    metrics = {m["key"]: m for p in context["pillars"].values() for m in p["metrics"]}
    assert metrics["nasdaq"]["change"] is None and metrics["nasdaq"]["vote"] == 0
    assert metrics["nasdaq"]["stale"] is False
    assert abs(metrics["sp500"]["change"] - (1.01**7 - 1) * 100) < 1e-9
    assert metrics["sp500"]["vote"] == 1 and metrics["sp500"]["age_days"] == 1
    assert metrics["usd_broad"]["stale"] is False and metrics["usd_broad"]["vote"] == 1
    assert context["as_of"] == (now.date() - timedelta(days=9)).isoformat()
