"""PR27-R04 adversarial PostgreSQL suite: A -> B -> A at the raw boundary.

R03's suite proves ``persist_signal_observations`` refuses to write under an
unregistered routing.  That is necessary and not sufficient: the raw collectors
had already written routing B's market data under the internal key the frozen
kernel reads, so restoring A produced an observation stamped with A's digest
whose context was partly B's.  Replay passed because it faithfully replayed the
contaminated context, and row-level provenance passed because the observation
itself really was created under A.

These tests drive the *real* collector flush paths against real PostgreSQL 17.
``test_residual_b_row_...`` deliberately reproduces the defect rather than
asserting the guard, so the rest of the suite is demonstrably load-bearing.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import timedelta
from functools import partial
from pathlib import Path

import asyncpg
import pytest

import app.scalp_collector as scalp
import app.ws_collector as ws
from app import config
from app.config import DEFAULT_MARKET_CATALOG
from app.scalp_collector import BookStats, TradeBucket, TradeStore
from app.scalp_logic import compute_scalp_summary, scalp_context
from app.signal_ledger import persist_signal_observations
from app.signal_replay import replay_signal_observation
from app.signal_runtime_contract import (
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    RawMarketProducerContractError,
    attest_raw_market_producer,
    scientific_runtime_contract,
)
from app.ws_collector import BucketStore, RtBucket
from tests.test_pr27_r04_raw_producer_closure import _bound_cycle, _swapped

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

SYMBOL = "BTCUSDT_PERP.A"
BASE_ASSET = "BTC"
EXCHANGES = ("binance", "bybit")

# Routing B swaps BTC's and ETH's selectors, so the BTC key would receive ETH's
# market. These prices make the contamination unmistakable in an assertion.
A_FUT_PX = 60_000.0
B_FUT_PX = 3_000.0
A_SPOT_PX = 60_010.0
B_SPOT_PX = 3_010.0


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _connect(prefix: str) -> tuple[asyncpg.Connection, str]:
    schema = f"{prefix}_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(SCHEMA_SQL)
    return conn, schema


async def _drop(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


class _Pool:
    """Hands the flush loops the one connection this test owns."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    def acquire(self) -> _Pool:
        return self

    async def __aenter__(self) -> asyncpg.Connection:
        return self._conn

    async def __aexit__(self, *_args) -> bool:
        return False


def _bounded_sleep(module, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run exactly one iteration of a flush loop, then stop it."""

    calls = {"n": 0}

    async def sleep(_delay: float) -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(module.asyncio, "sleep", sleep)


async def _run_once(module, name: str, pool: _Pool, monkeypatch, routing) -> None:
    _bounded_sleep(module, monkeypatch)
    with pytest.raises(asyncio.CancelledError):
        await getattr(module, name)(cycle=_bound_cycle(module, name, pool, routing))


def _activate_routing_b(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", _swapped(field))


def _restore_routing_a(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", DEFAULT_MARKET_CATALOG)


def _bucket_ts(age_seconds: int) -> int:
    return int((time.time() - age_seconds) // 5 * 5)


def _seed_futures(price: float, age_seconds: int = 20) -> TradeStore:
    """Populate the store directly: deterministic, and flush_trades is untouched."""

    store = TradeStore()
    ts = _bucket_ts(age_seconds)
    for exchange in EXCHANGES:
        store.realtime[(SYMBOL, exchange, ts)] = TradeBucket(
            buy_vol_usd=10.0,
            sell_vol_usd=4.0,
            trade_count=3,
            last_px=price,
            last_event_ms=ts * 1000,
        )
    return store


def _seed_spot(price: float, age_seconds: int = 20) -> BucketStore:
    store = BucketStore()
    ts = _bucket_ts(age_seconds)
    for exchange in EXCHANGES:
        store.realtime[(BASE_ASSET, exchange, ts)] = RtBucket(
            buy_vol_usd=10.0,
            sell_vol_usd=4.0,
            trade_count=3,
            last_px=price,
            last_event_ms=ts * 1000,
        )
    return store


def _book(price: float, age_seconds: int = 5) -> list[BookStats]:
    ts_ms = int((time.time() - age_seconds) * 1000)
    return [
        BookStats(
            ts_ms=ts_ms,
            symbol=SYMBOL,
            exchange=exchange,
            bid_px=price - 1,
            ask_px=price + 1,
            mid_px=price,
            spread_bps=3.0,
            bid_notional_l1=1000.0,
            ask_notional_l1=1000.0,
            bid_notional_l5=5000.0,
            ask_notional_l5=5000.0,
            bid_notional_l10=9000.0,
            ask_notional_l10=9000.0,
            imbalance_l1=0.5,
            imbalance_l5=0.5,
            imbalance_l10=0.5,
            wall_up_pct=None,
            wall_down_pct=None,
        )
        for exchange in EXCHANGES
    ]


class _BookStore:
    def __init__(self, rows: list[BookStats]) -> None:
        self._rows = rows

    async def snapshot(self) -> list[BookStats]:
        return self._rows

    async def ladders(self):
        return [
            (row.symbol, row.exchange, row.ts_ms, [[row.bid_px, 1.0]], [[row.ask_px, 1.0]])
            for row in self._rows
        ]


class _DrainOnceQueue(asyncio.Queue):
    """Lets flush_liquidations drain and write once, then ends the loop."""

    async def get(self):
        if self.empty():
            raise asyncio.CancelledError
        return await super().get()


async def _count(conn: asyncpg.Connection, table: str) -> int:
    return await conn.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608


# --------------------------------------------------------------------------
# The futures family: futures_pair selects the market, `symbol` is the key
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_futures_producer_writes_under_a_and_fails_closed_under_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr27_r04_futures")
    try:
        routing = attest_raw_market_producer("scalp_collector")

        # --- A: the raw producer is permitted and its rows are readable.
        monkeypatch.setattr(scalp, "TRADE_STORE", _seed_futures(A_FUT_PX))
        await _run_once(scalp, "flush_trades", _Pool(conn), monkeypatch, routing)
        written_under_a = await _count(conn, "futures_trades_realtime")
        assert written_under_a > 0

        # --- B: a result-material routing value changes and the producer must
        #     refuse *before* the data becomes scientific raw state.
        monkeypatch.setattr(scalp, "TRADE_STORE", _seed_futures(B_FUT_PX, age_seconds=15))
        _activate_routing_b(monkeypatch, "futures_pair")
        _bounded_sleep(scalp, monkeypatch)
        with pytest.raises(RawMarketProducerContractError):
            await scalp.flush_trades(
                cycle=_bound_cycle(scalp, "flush_trades", _Pool(conn), routing)
            )
        assert await _count(conn, "futures_trades_realtime") == written_under_a

        # --- restore A: no B row exists for scalp_context to consume.
        _restore_routing_a(monkeypatch)
        ctx = await scalp_context(conn, SYMBOL)
        assert ctx["fut_price"] == A_FUT_PX
        assert await conn.fetchval(
            "SELECT count(*) FROM futures_trades_realtime WHERE last_px=$1", B_FUT_PX
        ) == 0
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_orderbook_producer_fails_closed_under_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr27_r04_books")
    try:
        routing = attest_raw_market_producer("scalp_collector")

        monkeypatch.setattr(scalp, "BOOK_STORE", _BookStore(_book(A_FUT_PX)))
        await _run_once(scalp, "flush_books", _Pool(conn), monkeypatch, routing)
        snapshots = await _count(conn, "orderbook_snapshot")
        depth = await _count(conn, "orderbook_depth")
        assert snapshots > 0 and depth > 0

        monkeypatch.setattr(scalp, "BOOK_STORE", _BookStore(_book(B_FUT_PX)))
        _activate_routing_b(monkeypatch, "futures_pair")
        _bounded_sleep(scalp, monkeypatch)
        with pytest.raises(RawMarketProducerContractError):
            await scalp.flush_books(
                cycle=_bound_cycle(scalp, "flush_books", _Pool(conn), routing)
            )

        assert await _count(conn, "orderbook_snapshot") == snapshots
        assert await _count(conn, "orderbook_depth") == depth
        # orderbook_depth is upserted in place, so a blocked flush must also not
        # have overwritten the row the execution snapshot reads.
        assert await conn.fetchval(
            "SELECT count(*) FROM orderbook_depth WHERE bids::text LIKE $1",
            f"%{int(B_FUT_PX)}%",
        ) == 0
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_liquidation_producer_fails_closed_under_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr27_r04_liquidations")
    try:
        routing = attest_raw_market_producer("scalp_collector")
        now = await conn.fetchval("SELECT clock_timestamp()")

        queue = _DrainOnceQueue()
        queue.put_nowait((now, SYMBOL, "binance", "long", 500.0, A_FUT_PX, 0.1, "a-1"))
        monkeypatch.setattr(scalp, "LIQ_QUEUE", queue)
        with pytest.raises(asyncio.CancelledError):
            await scalp.flush_liquidations(
                cycle=partial(
                    scalp.flush_liquidations_cycle, _Pool(conn), None, routing
                )
            )
        assert await _count(conn, "liquidations_realtime") == 1

        queue_b = _DrainOnceQueue()
        queue_b.put_nowait((now, SYMBOL, "binance", "long", 900.0, B_FUT_PX, 0.2, "b-1"))
        monkeypatch.setattr(scalp, "LIQ_QUEUE", queue_b)
        _activate_routing_b(monkeypatch, "futures_pair")
        with pytest.raises(RawMarketProducerContractError):
            await scalp.flush_liquidations(
                cycle=partial(
                    scalp.flush_liquidations_cycle, _Pool(conn), None, routing
                )
            )

        assert await _count(conn, "liquidations_realtime") == 1
        assert await conn.fetchval(
            "SELECT count(*) FROM liquidations_realtime WHERE price=$1", B_FUT_PX
        ) == 0
    finally:
        await _drop(conn, schema)


# --------------------------------------------------------------------------
# The spot family: spot_pair selects the market, `base_asset` is the key
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spot_producer_writes_under_a_and_fails_closed_under_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr27_r04_spot")
    try:
        routing = attest_raw_market_producer("ws_collector")

        monkeypatch.setattr(ws, "STORE", _seed_spot(A_SPOT_PX))
        await _run_once(ws, "flush_realtime", _Pool(conn), monkeypatch, routing)
        written_under_a = await _count(conn, "spot_trades_realtime")
        assert written_under_a > 0

        monkeypatch.setattr(ws, "STORE", _seed_spot(B_SPOT_PX, age_seconds=15))
        _activate_routing_b(monkeypatch, "spot_pair")
        _bounded_sleep(ws, monkeypatch)
        with pytest.raises(RawMarketProducerContractError):
            await ws.flush_realtime(
                cycle=_bound_cycle(ws, "flush_realtime", _Pool(conn), routing)
            )
        assert await _count(conn, "spot_trades_realtime") == written_under_a

        _restore_routing_a(monkeypatch)
        ctx = await scalp_context(conn, SYMBOL)
        assert ctx["spot_price"] == A_SPOT_PX
        assert await conn.fetchval(
            "SELECT count(*) FROM spot_trades_realtime WHERE last_px=$1", B_SPOT_PX
        ) == 0
    finally:
        await _drop(conn, schema)


# --------------------------------------------------------------------------
# The defect itself, reproduced
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_residual_b_row_inside_the_three_minute_window_reaches_scalp_context() -> None:
    """Without the raw-producer guard, restoring A does not clean anything.

    This writes exactly what an unguarded collector under routing B would have
    written -- ETH's prices under the BTC key -- and shows scalp_context(A)
    consuming it. It is the reason the guard exists, and it must keep passing:
    the contamination is invisible to replay and to row-level provenance.
    """

    conn, schema = await _connect("test_pr27_r04_residual")
    try:
        now = await conn.fetchval("SELECT clock_timestamp()")
        residual = now - timedelta(seconds=30)
        event_ms = int(residual.timestamp() * 1000)
        for table, key, price, extra in (
            ("futures_trades_realtime", SYMBOL, B_FUT_PX, "large_buy_usd,large_sell_usd"),
            ("spot_trades_realtime", BASE_ASSET, B_SPOT_PX, "inst_buy_usd,inst_sell_usd"),
        ):
            await conn.execute(
                f"""
                INSERT INTO {table}(
                  ts,symbol,exchange,venue_count,buy_vol_usd,sell_vol_usd,
                  {extra},trade_count,last_px,last_event_ms
                ) VALUES($1,$2,'combined',2,10,4,0,0,3,$3,$4)
                """,  # noqa: S608
                residual,
                key,
                price,
                event_ms,
            )

        # Routing is back to A and the contract passes again...
        assert scientific_runtime_contract()["digest"]
        ctx = await scalp_context(conn, SYMBOL)

        # ...yet the context the kernel would stamp with A's digest is B's data.
        assert ctx["fut_price"] == B_FUT_PX
        assert ctx["spot_price"] == B_SPOT_PX
        assert ctx["fut_volume_3m"] == 14.0
        assert ctx["spot_volume_3m"] == 14.0
    finally:
        await _drop(conn, schema)


# --------------------------------------------------------------------------
# End to end: A -> B -> A, then an observation built from real raw rows
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_observation_after_a_b_a_is_built_only_from_a_routed_raw_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr27_r04_end_to_end")
    try:
        scalp_routing = attest_raw_market_producer("scalp_collector")
        ws_routing = attest_raw_market_producer("ws_collector")

        # A: both raw producers write.
        monkeypatch.setattr(scalp, "TRADE_STORE", _seed_futures(A_FUT_PX))
        await _run_once(scalp, "flush_trades", _Pool(conn), monkeypatch, scalp_routing)
        monkeypatch.setattr(ws, "STORE", _seed_spot(A_SPOT_PX))
        await _run_once(ws, "flush_realtime", _Pool(conn), monkeypatch, ws_routing)

        # B: both raw producers refuse, on both routing families.
        monkeypatch.setattr(scalp, "TRADE_STORE", _seed_futures(B_FUT_PX, age_seconds=15))
        monkeypatch.setattr(ws, "STORE", _seed_spot(B_SPOT_PX, age_seconds=15))
        _activate_routing_b(monkeypatch, "futures_pair")
        _bounded_sleep(scalp, monkeypatch)
        with pytest.raises(RawMarketProducerContractError):
            await scalp.flush_trades(
                cycle=_bound_cycle(scalp, "flush_trades", _Pool(conn), scalp_routing)
            )
        _activate_routing_b(monkeypatch, "spot_pair")
        _bounded_sleep(ws, monkeypatch)
        with pytest.raises(RawMarketProducerContractError):
            await ws.flush_realtime(
                cycle=_bound_cycle(ws, "flush_realtime", _Pool(conn), ws_routing)
            )

        # restore A.
        _restore_routing_a(monkeypatch)

        ctx = await scalp_context(conn, SYMBOL)
        assert ctx["fut_price"] == A_FUT_PX
        assert ctx["spot_price"] == A_SPOT_PX
        for table, price in (
            ("futures_trades_realtime", B_FUT_PX),
            ("spot_trades_realtime", B_SPOT_PX),
        ):
            assert await conn.fetchval(
                f"SELECT count(*) FROM {table} WHERE last_px=$1",  # noqa: S608
                price,
            ) == 0

        written = await persist_signal_observations(
            conn,
            SYMBOL,
            ctx,
            compute_scalp_summary(ctx),
            collector_generation=1,
            collector_shard_index=0,
            collector_shard_count=1,
        )
        assert written == 1

        row = await conn.fetchrow(
            """
            SELECT observation_id,runtime_contract_version,runtime_contract_digest
            FROM signal_observation
            """
        )
        contract = scientific_runtime_contract()
        assert row["runtime_contract_digest"] == contract["digest"]
        assert row["runtime_contract_version"] == SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1

        replay = await replay_signal_observation(conn, row["observation_id"])
        assert replay.context_hash_valid
        assert replay.evidence_match
        assert replay.observation_fields_match
        assert replay.mismatched_observation_fields == ()
    finally:
        await _drop(conn, schema)
