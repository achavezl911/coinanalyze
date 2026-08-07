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
