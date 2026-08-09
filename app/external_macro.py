from __future__ import annotations

import asyncio
import csv
import json
import logging
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from html import unescape
from io import StringIO
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
import httpx

from app.config import Settings
from app.db import ServiceOwnership, fenced_transaction

LOGGER = logging.getLogger(__name__)
USER_AGENT = "CoinalyzeOperatorDashboard/1.5.0 (market-context; contact: local-operator)"
FRED_SERIES = {
    "treasury_2y": ("DGS2", "Treasury 2Y"),
    "real_yield_10y": ("DFII10", "Tasa real 10Y"),
    "usd_broad": ("DTWEXBGS", "Dolar amplio"),
    "nasdaq": ("NASDAQCOM", "Nasdaq Composite"),
    "sp500": ("SP500", "S&P 500"),
    "vix": ("VIXCLS", "VIX"),
}
CORE_SERIES = (*FRED_SERIES, "stablecoin_supply_usd")
EASTERN = ZoneInfo("America/New_York")
MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
    )
    if name
}


def parse_fred_csv(text: str, series_id: str, target: str) -> list[tuple[str, date, float, str]]:
    rows: list[tuple[str, date, float, str]] = []
    for row in csv.DictReader(StringIO(text)):
        raw_value = row.get(series_id)
        raw_date = row.get("observation_date") or row.get("DATE")
        if not raw_date or raw_value in (None, "", "."):
            continue
        try:
            value = float(raw_value)
            observed = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            continue
        rows.append((target, observed, value, f"FRED:{series_id}"))
    return rows


def parse_stablecoin_history(text: str, cutoff: date) -> list[tuple[str, date, float, str]]:
    payload = json.loads(text)
    rows: list[tuple[str, date, float, str]] = []
    for item in payload if isinstance(payload, list) else []:
        try:
            observed = datetime.fromtimestamp(int(item["date"]), tz=UTC).date()
            value = float(item["totalCirculatingUSD"]["peggedUSD"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if observed >= cutoff and value > 0:
            rows.append(("stablecoin_supply_usd", observed, value, "DefiLlama stablecoins"))
    return rows


def parse_coinglass_etf(text: str) -> list[tuple[str, date, float, str]]:
    payload = json.loads(text)
    if str(payload.get("code")) not in {"0", "200"}:
        raise ValueError(payload.get("msg") or "CoinGlass ETF response rejected")
    rows: list[tuple[str, date, float, str]] = []
    for item in payload.get("data") or []:
        try:
            observed = datetime.fromtimestamp(int(item["timestamp"]) / 1000, tz=UTC).date()
            value = float(item["flow_usd"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        rows.append(("btc_etf_flow_usd", observed, value, "CoinGlass ETF"))
    return rows


def _unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def parse_bls_calendar(text: str) -> list[tuple[str, datetime, str, int, str]]:
    wanted = {
        "employment situation": "NFP / Empleo EE.UU.",
        "consumer price index": "CPI EE.UU.",
        "producer price index": "PPI EE.UU.",
        "job openings and labor turnover survey": "JOLTS EE.UU.",
    }
    events: list[tuple[str, datetime, str, int, str]] = []
    block: dict[str, str] | None = None
    for line in _unfold_ics(text):
        if line == "BEGIN:VEVENT":
            block = {}
        elif line == "END:VEVENT" and block is not None:
            summary = unescape(block.get("SUMMARY", "")).replace("\\,", ",")
            label = next((value for key, value in wanted.items() if key in summary.lower()), None)
            raw = block.get("DTSTART")
            if label and raw:
                try:
                    local = datetime.strptime(raw.rstrip("Z"), "%Y%m%dT%H%M%S").replace(
                        tzinfo=EASTERN
                    )
                    event_at = local.astimezone(UTC)
                    key = f"bls-{label.split()[0].lower()}-{event_at:%Y%m%d%H%M}"
                    events.append((key, event_at, label, 3, "BLS calendar"))
                except ValueError:
                    pass
            block = None
        elif block is not None and ":" in line:
            key, value = line.split(":", 1)
            block[key.split(";", 1)[0]] = value
    return events


def _plain_html(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value)).strip()


def parse_fomc_calendar(text: str) -> list[tuple[str, datetime, str, int, str]]:
    events: list[tuple[str, datetime, str, int, str]] = []
    headings = list(
        re.finditer(
            r"<h4[^>]*>.*?(?P<year>20\d{2})\s+FOMC Meetings.*?</h4>",
            text,
            re.I | re.S,
        )
    )
    entry_pattern = re.compile(
        r'fomc-meeting__month[^>]*>(?P<month>.*?)</div>.*?'
        r'fomc-meeting__date[^>]*>(?P<days>.*?)</div>',
        re.I | re.S,
    )
    for index, heading in enumerate(headings):
        year = int(heading.group("year"))
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        for match in entry_pattern.finditer(text[heading.end() : end]):
            month_name = _plain_html(match.group("month")).lower()
            day_numbers = re.findall(r"\d{1,2}", _plain_html(match.group("days")))
            if month_name not in MONTHS or not day_numbers:
                continue
            decision_day = int(day_numbers[-1])
            try:
                local = datetime.combine(
                    date(year, MONTHS[month_name], decision_day), time(14, 0), EASTERN
                )
            except ValueError:
                continue
            event_at = local.astimezone(UTC)
            events.append((f"fomc-{event_at:%Y%m%d}", event_at, "Decisión FOMC", 3, "Federal Reserve"))
    return events


def _pct_change(values: Sequence[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] == 0:
        return None
    return (values[-1] / values[-periods - 1] - 1) * 100


def _direction(value: float | None, threshold: float, *, inverse: bool = False) -> int:
    if value is None or abs(value) < threshold:
        return 0
    direction = 1 if value > 0 else -1
    return -direction if inverse else direction


def _state(votes: Sequence[int]) -> str:
    active = [vote for vote in votes if vote]
    if not active:
        return "mixto"
    total = sum(active)
    return "favorable" if total > 0 else "restrictivo" if total < 0 else "mixto"


def _metric(
    key: str,
    label: str,
    values: Sequence[float],
    dates: Sequence[date],
    *,
    change_period: int,
    change_kind: str = "pct",
    threshold: float,
    inverse: bool = False,
) -> dict[str, Any]:
    change = _pct_change(values, change_period)
    if change_kind == "bps" and len(values) > change_period:
        change = (values[-1] - values[-change_period - 1]) * 100
    vote = _direction(change, threshold, inverse=inverse)
    return {
        "key": key,
        "label": label,
        "value": values[-1] if values else None,
        "observed_on": dates[-1].isoformat() if dates else None,
        "change": change,
        "change_kind": change_kind,
        "state": "favorable" if vote > 0 else "restrictivo" if vote < 0 else "mixto",
        "vote": vote,
    }


def _pillar(label: str, metrics: list[dict[str, Any]], narratives: Mapping[str, str]) -> dict[str, Any]:
    state = _state([int(metric["vote"]) for metric in metrics])
    return {"label": label, "state": state, "narrative": narratives[state], "metrics": metrics}


def build_external_macro_context(
    observations: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    btc_closes: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    etf_configured: bool = False,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    grouped: dict[str, list[tuple[date, float, str, datetime | None]]] = defaultdict(list)
    for row in observations:
        observed = row["observed_on"]
        if isinstance(observed, datetime):
            observed = observed.date()
        grouped[str(row["series"])].append(
            (observed, float(row["value"]), str(row["source"]), row.get("fetched_at"))
        )
    for rows in grouped.values():
        rows.sort(key=lambda item: item[0])

    def series(key: str) -> tuple[list[float], list[date]]:
        rows = grouped.get(key, [])
        return [row[1] for row in rows], [row[0] for row in rows]

    y2, y2_dates = series("treasury_2y")
    real, real_dates = series("real_yield_10y")
    usd, usd_dates = series("usd_broad")
    nasdaq, nasdaq_dates = series("nasdaq")
    sp500, sp500_dates = series("sp500")
    vix, vix_dates = series("vix")
    stable, stable_dates = series("stablecoin_supply_usd")

    monetary_metrics = [
        _metric("treasury_2y", "Treasury 2Y", y2, y2_dates, change_period=5, change_kind="bps", threshold=5, inverse=True),
        _metric("real_yield_10y", "Tasa real 10Y", real, real_dates, change_period=5, change_kind="bps", threshold=5, inverse=True),
        _metric("usd_broad", "Dólar amplio", usd, usd_dates, change_period=5, threshold=0.3, inverse=True),
    ]
    risk_metrics = [
        _metric("nasdaq", "Nasdaq", nasdaq, nasdaq_dates, change_period=5, threshold=1),
        _metric("sp500", "S&P 500", sp500, sp500_dates, change_period=5, threshold=1),
        _metric("vix", "VIX", vix, vix_dates, change_period=5, threshold=8, inverse=True),
    ]
    liquidity_metrics = [
        _metric("stablecoin_supply_usd", "Stablecoins", stable, stable_dates, change_period=30, threshold=0.5)
    ]
    pillars = {
        "monetary": _pillar(
            "Presión monetaria",
            monetary_metrics,
            {
                "favorable": "Tasas y dólar alivian presión sobre activos de riesgo.",
                "restrictivo": "Tasas o dólar endurecen las condiciones para cripto.",
                "mixto": "Tasas y dólar no entregan una dirección conjunta.",
            },
        ),
        "risk": _pillar(
            "Apetito por riesgo",
            risk_metrics,
            {
                "favorable": "Renta variable y volatilidad respaldan toma de riesgo.",
                "restrictivo": "Renta variable o VIX favorecen protección y menor exposición.",
                "mixto": "El mercado tradicional no confirma un régimen risk-on u off.",
            },
        ),
        "liquidity": _pillar(
            "Liquidez cripto",
            liquidity_metrics,
            {
                "favorable": "La oferta de stablecoins está expandiéndose.",
                "restrictivo": "La liquidez en stablecoins está contrayéndose.",
                "mixto": "La liquidez en stablecoins permanece sin expansión clara.",
            },
        ),
    }
    regime = _state([1 if p["state"] == "favorable" else -1 if p["state"] == "restrictivo" else 0 for p in pillars.values()])

    etf_values, etf_dates = series("btc_etf_flow_usd")
    flow_1d = etf_values[-1] if etf_values else None
    flow_5d = sum(etf_values[-5:]) if etf_values else None
    flow_20d = sum(etf_values[-20:]) if etf_values else None
    rolling_abs = [abs(sum(etf_values[max(0, index - 4) : index + 1])) for index in range(len(etf_values))]
    significant = max(100_000_000.0, median(rolling_abs[-60:]) if rolling_abs else 0.0)
    btc_values = [float(row["price_close"]) for row in btc_closes]
    btc_5d = _pct_change(btc_values, 5)
    if not etf_values:
        etf_interpretation = "Flujo ETF no conectado; no se usa para el régimen."
    elif flow_5d is not None and flow_5d >= significant and (btc_5d or 0) <= 0:
        etf_interpretation = "Entradas ETF sin avance de BTC: la demanda está siendo absorbida por oferta; no confirma ruptura."
    elif flow_5d is not None and flow_5d <= -significant and (btc_5d or 0) >= 0:
        etf_interpretation = "Salidas ETF sin caída de BTC: fortaleza relativa y demanda no visible en ese flujo."
    elif flow_5d is not None and flow_5d >= significant:
        etf_interpretation = "Entradas ETF y precio respondiendo: demanda institucional confirmada por el precio."
    elif flow_5d is not None and flow_5d <= -significant:
        etf_interpretation = "Salidas ETF y precio débil: presión institucional alineada con el movimiento."
    else:
        etf_interpretation = "Flujo ETF de cinco sesiones sin desequilibrio material."

    upcoming = []
    for item in events:
        event_at = item["event_at"]
        if event_at.tzinfo is None:
            event_at = event_at.replace(tzinfo=UTC)
        hours = (event_at - now).total_seconds() / 3600
        if hours >= 0:
            upcoming.append(
                {
                    "title": item["title"],
                    "event_at": event_at.isoformat(),
                    "hours": round(hours, 1),
                    "importance": int(item["importance"]),
                    "source": item["source"],
                }
            )
    upcoming.sort(key=lambda item: item["hours"])
    next_event = upcoming[0] if upcoming else None
    event_level = "alto" if next_event and next_event["hours"] <= 24 else "elevado" if next_event and next_event["hours"] <= 72 else "normal"
    event_narrative = (
        f'{next_event["title"]} en {next_event["hours"]:.1f} h: evita abrir una tesis de varias sesiones sin margen para volatilidad.'
        if event_level in {"alto", "elevado"}
        else "Sin evento macro de alto impacto dentro de las próximas 72 horas."
    )

    available_core = sum(bool(grouped.get(key)) for key in CORE_SERIES)
    coverage = round(available_core / len(CORE_SERIES) * 100)
    confidence = "alta" if coverage >= 86 else "media" if coverage >= 60 else "baja"
    latest_dates = [rows[-1][0] for key, rows in grouped.items() if key in CORE_SERIES and rows]
    latest_fetches = [rows[-1][3] for key, rows in grouped.items() if key in CORE_SERIES and rows and rows[-1][3]]
    limitations = []
    if not etf_configured:
        limitations.append("Flujos ETF requieren COINGLASS_API_KEY; el régimen se calcula sin esa pata.")
    elif not etf_values:
        limitations.append("La fuente ETF está configurada pero todavía no entregó observaciones.")
    missing = [key for key in CORE_SERIES if not grouped.get(key)]
    if missing:
        limitations.append("Series núcleo ausentes: " + ", ".join(missing) + ".")

    return {
        "available": available_core >= 4,
        "regime": regime if available_core >= 4 else "sin_datos",
        "regime_label": {"favorable": "Favorable", "restrictivo": "Restrictivo", "mixto": "Mixto", "sin_datos": "Datos insuficientes"}[regime if available_core >= 4 else "sin_datos"],
        "coverage_pct": coverage,
        "data_confidence": confidence,
        "as_of": max(latest_dates).isoformat() if latest_dates else None,
        "fetched_at": max(latest_fetches).isoformat() if latest_fetches else None,
        "pillars": pillars,
        "institutional_flows": {
            "available": bool(etf_values),
            "configured": etf_configured,
            "flow_1d_usd": flow_1d,
            "flow_5d_usd": flow_5d,
            "flow_20d_usd": flow_20d,
            "btc_return_5d_pct": btc_5d,
            "materiality_threshold_usd": significant,
            "observed_on": etf_dates[-1].isoformat() if etf_dates else None,
            "interpretation": etf_interpretation,
        },
        "event_risk": {
            "level": event_level,
            "next_event": next_event,
            "narrative": event_narrative,
            "upcoming": upcoming[:6],
        },
        "alignment": {"state": "pendiente", "reading": "Se requiere el sesgo interno del activo para evaluar alineación."},
        "limitations": limitations,
        "sources": ["FRED / Federal Reserve", "BLS", "Federal Reserve FOMC", "DefiLlama", *( ["CoinGlass"] if etf_values else [])],
        "method": "Reglas deterministas de cambio a 5/30 sesiones; no es probabilidad ni señal de entrada.",
    }


def align_with_internal(context: dict[str, Any], swing: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(context)
    bias = str(swing.get("bias") or "NEUTRAL").upper()
    regime = str(context.get("regime") or "sin_datos")
    event_level = str((context.get("event_risk") or {}).get("level") or "normal")
    if event_level in {"alto", "elevado"}:
        state = "esperar_evento"
        reading = (context.get("event_risk") or {}).get("narrative")
    elif regime == "favorable" and bias == "LONG":
        state, reading = "alineado", "Macro externo e impulso interno alcista están alineados; permite sostener tras confirmar el nivel técnico."
    elif regime == "restrictivo" and bias == "SHORT":
        state, reading = "alineado", "Macro externo e impulso interno bajista están alineados; favorece mantener cortos tras confirmación."
    elif regime == "restrictivo" and bias == "LONG":
        state, reading = "conflicto", "Impulso interno LONG contra régimen restrictivo: tratarlo como táctico, con menor tamaño y salida rápida."
    elif regime == "favorable" and bias == "SHORT":
        state, reading = "conflicto", "Impulso interno SHORT contra régimen favorable: exige confirmación fuerte; aumenta el riesgo de rebote o trampa."
    else:
        state, reading = "mixto", "El filtro externo no confirma el sesgo interno; esperar estructura y flujo antes de ampliar horizonte."
    result["alignment"] = {"state": state, "reading": reading, "internal_bias": bias}
    return result


async def external_macro_context(
    conn: asyncpg.Connection, *, etf_configured: bool = False
) -> dict[str, Any]:
    observations = await conn.fetch(
        """
        SELECT series, observed_on, value, source, fetched_at
        FROM external_macro_observation
        WHERE observed_on >= current_date - 800
        ORDER BY series, observed_on
        """
    )
    events = await conn.fetch(
        """
        SELECT event_at, title, importance, source
        FROM macro_event
        WHERE event_at >= now() AND event_at < now() + interval '180 days'
        ORDER BY event_at
        """
    )
    btc_closes = await conn.fetch(
        """
        SELECT session_date, price_close
        FROM daily_session_agg
        WHERE symbol = 'BTCUSDT_PERP.A'
        ORDER BY session_date DESC LIMIT 31
        """
    )
    return build_external_macro_context(
        observations,
        events,
        list(reversed(btc_closes)),
        etf_configured=etf_configured,
    )


async def _get(client: httpx.AsyncClient, url: str, **kwargs: Any) -> str:
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    return response.text


async def refresh_external_macro(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    force: bool = False,
    ownership: ServiceOwnership | None = None,
) -> dict[str, Any]:
    if not settings.EXTERNAL_MACRO_ENABLED:
        return {"status": "disabled"}
    async with pool.acquire() as conn:
        last_fetch = await conn.fetchval("SELECT max(fetched_at) FROM external_macro_observation")
    if last_fetch and not force:
        age = (datetime.now(UTC) - last_fetch).total_seconds()
        if age < settings.EXTERNAL_MACRO_REFRESH_SECONDS:
            return {"status": "fresh", "age_seconds": round(age)}

    cutoff = datetime.now(UTC).date() - timedelta(days=800)
    requests: list[tuple[str, Any]] = []
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/csv,text/calendar,text/html"},
    ) as client:
        for target, (fred_id, _label) in FRED_SERIES.items():
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_id}&cosd={cutoff.isoformat()}"
            requests.append((target, _get(client, url)))
        requests.extend(
            [
                ("stablecoins", _get(client, "https://stablecoins.llama.fi/stablecoincharts/all")),
                ("bls", _get(client, "https://www.bls.gov/schedule/news_release/bls.ics", headers={"Accept": "text/calendar", "User-Agent": USER_AGENT})),
                ("fomc", _get(client, "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")),
            ]
        )
        if settings.COINGLASS_API_KEY:
            requests.append(
                (
                    "etf",
                    _get(
                        client,
                        "https://open-api-v4.coinglass.com/api/etf/bitcoin/flow-history",
                        headers={"CG-API-KEY": settings.COINGLASS_API_KEY},
                        params={"limit": 500},
                    ),
                )
            )
        results = await asyncio.gather(*(request for _name, request in requests), return_exceptions=True)

    observations: list[tuple[str, date, float, str]] = []
    calendar_events: list[tuple[str, datetime, str, int, str]] = []
    errors: list[str] = []
    for (name, _request), result in zip(requests, results, strict=True):
        if isinstance(result, BaseException):
            errors.append(f"{name}: {type(result).__name__}")
            continue
        try:
            if name in FRED_SERIES:
                observations.extend(parse_fred_csv(result, FRED_SERIES[name][0], name))
            elif name == "stablecoins":
                observations.extend(parse_stablecoin_history(result, cutoff))
            elif name == "bls":
                calendar_events.extend(parse_bls_calendar(result))
            elif name == "fomc":
                calendar_events.extend(parse_fomc_calendar(result))
            elif name == "etf":
                observations.extend(parse_coinglass_etf(result))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{name}: parse {type(exc).__name__}")

    observations = list({(row[0], row[1]): row for row in observations}.values())
    calendar_events = list({(row[0], row[1]): row for row in calendar_events}.values())
    async with pool.acquire() as conn:
        async with fenced_transaction(conn, ownership):
            if observations:
                await conn.executemany(
                    """
                    INSERT INTO external_macro_observation(
                      series, observed_on, value, source, fetched_at
                    ) VALUES($1,$2,$3,$4,now())
                    ON CONFLICT(series, observed_on) DO UPDATE SET
                      value=EXCLUDED.value, source=EXCLUDED.source, fetched_at=now()
                    """,
                    observations,
                )
            if calendar_events:
                await conn.executemany(
                    """
                    INSERT INTO macro_event(
                      event_key,event_at,title,importance,source,fetched_at
                    ) VALUES($1,$2,$3,$4,$5,now())
                    ON CONFLICT(event_key,event_at) DO UPDATE SET
                      title=EXCLUDED.title, importance=EXCLUDED.importance,
                      source=EXCLUDED.source, fetched_at=now()
                    """,
                    calendar_events,
                )
            await conn.execute(
                "DELETE FROM external_macro_observation WHERE observed_on < current_date - 800"
            )
            await conn.execute("DELETE FROM macro_event WHERE event_at < now() - interval '30 days'")
    if errors:
        LOGGER.warning("external_macro_partial errors=%s", errors)
    result = {"status": "ok" if not errors else "partial", "observations": len(observations), "events": len(calendar_events), "errors": errors}
    LOGGER.info("external_macro_refresh result=%s", result)
    return result
