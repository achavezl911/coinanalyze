from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

import asyncpg

GapStatus = Literal["unresolved", "recovered", "unrecoverable"]
FeedClass = Literal["cadence", "event_stream"]
EvidenceType = Literal[
    "missing_interval",
    "queue_full",
    "disconnect",
    "sequence_discontinuity",
    "collector_outage",
    "source_failure",
]

BLOCKING_GAP_STATUSES = frozenset({"unresolved", "unrecoverable"})
EVENT_LOSS_EVIDENCE = frozenset(
    {
        "queue_full",
        "disconnect",
        "sequence_discontinuity",
        "collector_outage",
        "source_failure",
    }
)


def _aware_utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _validated_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start = _aware_utc(start, "start")
    end = _aware_utc(end, "end")
    if start >= end:
        raise ValueError("gap and metric windows must satisfy start < end")
    return start, end


@dataclass(frozen=True, slots=True)
class GapRequirement:
    """One exact source required by a metric over a half-open ``[start,end)`` window."""

    key: str
    feed: str
    exchange: str
    market: str
    symbol: str
    start: datetime
    end: datetime

    def normalized(self) -> GapRequirement:
        start, end = _validated_window(self.start, self.end)
        if not all((self.key, self.feed, self.exchange, self.market, self.symbol)):
            raise ValueError("gap requirement identity fields cannot be empty")
        return GapRequirement(
            self.key,
            self.feed,
            self.exchange,
            self.market,
            self.symbol,
            start,
            end,
        )


async def blocking_requirement_keys(
    conn: asyncpg.Connection,
    requirements: Sequence[GapRequirement],
) -> set[str]:
    """Return requirements overlapped by unresolved or unrecoverable gaps.

    Both the stored gap and requested metric window are half-open. Therefore
    ``gap.start_ts < window.end AND gap.end_ts > window.start`` is the only overlap
    predicate used by the application. Recovered gaps never block evaluation.
    """
    normalized = [item.normalized() for item in requirements]
    if not normalized:
        return set()
    rows = await conn.fetch(
        """
        WITH required(key,feed,exchange,market,symbol,start_ts,end_ts) AS (
          SELECT * FROM unnest(
            $1::text[], $2::text[], $3::text[], $4::text[], $5::text[],
            $6::timestamptz[], $7::timestamptz[]
          )
        )
        SELECT DISTINCT required.key
        FROM required
        JOIN data_gap AS gap
          ON gap.feed=required.feed
         AND gap.exchange=required.exchange
         AND gap.market=required.market
         AND gap.symbol=required.symbol
         AND gap.start_ts < required.end_ts
         AND gap.end_ts > required.start_ts
        WHERE gap.status IN ('unresolved','unrecoverable')
        """,
        [item.key for item in normalized],
        [item.feed for item in normalized],
        [item.exchange for item in normalized],
        [item.market for item in normalized],
        [item.symbol for item in normalized],
        [item.start for item in normalized],
        [item.end for item in normalized],
    )
    return {str(row["key"]) for row in rows}


async def record_data_gap(
    conn: asyncpg.Connection,
    *,
    feed: str,
    feed_class: FeedClass,
    exchange: str,
    market: str,
    symbol: str,
    granularity: str,
    start: datetime,
    end: datetime,
    evidence_type: EvidenceType,
    detection_reason: str,
    detection_source: str,
    expected_cadence: timedelta | None = None,
) -> int:
    """Persist one gap idempotently after validating cadence/event semantics."""
    start, end = _validated_window(start, end)
    identity = (feed, exchange, market, symbol, granularity)
    if not all(identity) or not detection_reason or not detection_source:
        raise ValueError("gap identity and detection metadata cannot be empty")
    if feed_class == "cadence":
        if evidence_type != "missing_interval":
            raise ValueError("cadence gaps require missing_interval evidence")
        if expected_cadence is None or expected_cadence <= timedelta(0):
            raise ValueError("cadence gaps require their real positive cadence")
    elif feed_class == "event_stream":
        if evidence_type not in EVENT_LOSS_EVIDENCE:
            raise ValueError("event-stream silence is not positive evidence of data loss")
        if expected_cadence is not None:
            raise ValueError("event streams cannot declare an invented cadence")
    else:
        raise ValueError(f"unsupported feed class: {feed_class}")
    gap_id = await conn.fetchval(
        """
        INSERT INTO data_gap(
          feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,
          expected_cadence,evidence_type,detection_reason,detection_source
        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ON CONFLICT(
          feed,exchange,market,symbol,granularity,
          start_ts,end_ts,evidence_type,detection_source
        ) DO UPDATE SET detection_reason=EXCLUDED.detection_reason
        RETURNING id
        """,
        feed,
        feed_class,
        exchange,
        market,
        symbol,
        granularity,
        start,
        end,
        expected_cadence,
        evidence_type,
        detection_reason[:500],
        detection_source[:120],
    )
    return int(gap_id)


async def record_event_stream_loss(
    conn: asyncpg.Connection,
    *,
    feed: str,
    exchange: str,
    market: str,
    symbol: str,
    start: datetime,
    end: datetime,
    evidence_type: EvidenceType,
    detection_reason: str,
    detection_source: str,
) -> int:
    """Record positive event-loss evidence without deriving anything from silence."""
    return await record_data_gap(
        conn,
        feed=feed,
        feed_class="event_stream",
        exchange=exchange,
        market=market,
        symbol=symbol,
        granularity="event",
        start=start,
        end=end,
        evidence_type=evidence_type,
        detection_reason=detection_reason,
        detection_source=detection_source,
    )


def missing_cadence_windows(
    observations: Iterable[datetime],
    *,
    start: datetime,
    end: datetime,
    cadence: timedelta,
) -> list[tuple[datetime, datetime]]:
    """Collapse missing expected cadence buckets into half-open gap intervals.

    The caller must pass the feed's configured cadence. There is intentionally no
    universal default.
    """
    start, end = _validated_window(start, end)
    if cadence <= timedelta(0):
        raise ValueError("cadence must be positive")
    present = {_aware_utc(item, "observation") for item in observations}
    missing: list[datetime] = []
    expected = start
    while expected < end:
        if expected not in present:
            missing.append(expected)
        expected += cadence
    if not missing:
        return []
    windows: list[tuple[datetime, datetime]] = []
    gap_start = previous = missing[0]
    for item in missing[1:]:
        if item != previous + cadence:
            windows.append((gap_start, min(previous + cadence, end)))
            gap_start = item
        previous = item
    windows.append((gap_start, min(previous + cadence, end)))
    return windows


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    timestamp: datetime
    key: str
    feed: str
    exchange: str
    market: str
    symbol: str
    granularity: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DataGap:
    id: int
    feed: str
    feed_class: FeedClass
    exchange: str
    market: str
    symbol: str
    granularity: str
    start: datetime
    end: datetime
    expected_cadence: timedelta | None
    status: GapStatus

    @classmethod
    def from_record(cls, row: asyncpg.Record) -> DataGap:
        return cls(
            id=int(row["id"]),
            feed=str(row["feed"]),
            feed_class=row["feed_class"],
            exchange=str(row["exchange"]),
            market=str(row["market"]),
            symbol=str(row["symbol"]),
            granularity=str(row["granularity"]),
            start=row["start_ts"],
            end=row["end_ts"],
            expected_cadence=row["expected_cadence"],
            status=row["status"],
        )


class RecoveryAdapter(Protocol):
    name: str
    feed: str
    exchange: str
    market: str
    granularity: str

    async def fetch(self, gap: DataGap) -> Sequence[RecoveryObservation]: ...

    async def persist(
        self,
        conn: asyncpg.Connection,
        observations: Sequence[RecoveryObservation],
    ) -> None: ...


class RecoveryValidationError(ValueError):
    pass


def validate_recovery(
    gap: DataGap,
    adapter: RecoveryAdapter,
    observations: Sequence[RecoveryObservation],
) -> None:
    """Validate exact source identity, coverage, timestamps, cadence and duplicates."""
    adapter_identity = (adapter.feed, adapter.exchange, adapter.market, adapter.granularity)
    gap_identity = (gap.feed, gap.exchange, gap.market, gap.granularity)
    if adapter_identity != gap_identity:
        raise RecoveryValidationError("recovery adapter does not exactly match the gap source")
    if gap.feed_class != "cadence" or gap.expected_cadence is None:
        raise RecoveryValidationError("event streams have no validated historical adapter")
    if not observations:
        raise RecoveryValidationError("historical source returned no observations")

    seen_keys: set[str] = set()
    timestamps: set[datetime] = set()
    for observation in observations:
        timestamp = _aware_utc(observation.timestamp, "recovery timestamp")
        if not gap.start <= timestamp < gap.end:
            raise RecoveryValidationError("recovery timestamp is outside the requested interval")
        identity = (
            observation.feed,
            observation.exchange,
            observation.market,
            observation.symbol,
            observation.granularity,
        )
        if identity != (*gap_identity[:3], gap.symbol, gap_identity[3]):
            raise RecoveryValidationError("recovery observation source identity mismatch")
        if observation.key in seen_keys or timestamp in timestamps:
            raise RecoveryValidationError("duplicate recovery observation")
        seen_keys.add(observation.key)
        timestamps.add(timestamp)

    expected: set[datetime] = set()
    timestamp = gap.start
    while timestamp < gap.end:
        expected.add(timestamp)
        timestamp += gap.expected_cadence
    if timestamps != expected:
        raise RecoveryValidationError("historical source does not completely cover the gap cadence")


async def _load_gap(conn: asyncpg.Connection, gap_id: int, *, locked: bool = False) -> DataGap | None:
    suffix = " FOR UPDATE" if locked else ""
    row = await conn.fetchrow(
        "SELECT id,feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,"
        "expected_cadence,status FROM data_gap WHERE id=$1" + suffix,
        gap_id,
    )
    return DataGap.from_record(row) if row else None


async def _mark_unrecoverable(
    conn: asyncpg.Connection,
    gap_id: int,
    reason: str,
) -> GapStatus:
    async with conn.transaction():
        gap = await _load_gap(conn, gap_id, locked=True)
        if gap is None:
            raise LookupError(f"data gap {gap_id} does not exist")
        if gap.status != "unresolved":
            return gap.status
        await conn.execute(
            """
            UPDATE data_gap SET
              status='unrecoverable',resolved_at=now(),recovered_at=NULL,
              recovery_attempts=recovery_attempts+1,last_recovery_attempt_at=now(),
              resolution_reason=$2,recovery_metadata='{}'::jsonb
            WHERE id=$1
            """,
            gap_id,
            reason[:500],
        )
    return "unrecoverable"


async def _record_recovery_failure(
    conn: asyncpg.Connection,
    gap_id: int,
    reason: str,
) -> None:
    await conn.execute(
        """
        UPDATE data_gap SET
          recovery_attempts=recovery_attempts+1,last_recovery_attempt_at=now(),
          resolution_reason=$2
        WHERE id=$1 AND status='unresolved'
        """,
        gap_id,
        reason[:500],
    )


async def recover_gap(
    conn: asyncpg.Connection,
    gap_id: int,
    adapter: RecoveryAdapter | None,
) -> GapStatus:
    """Recover one gap transactionally; success means validated data was persisted."""
    gap = await _load_gap(conn, gap_id)
    if gap is None:
        raise LookupError(f"data gap {gap_id} does not exist")
    if gap.status != "unresolved":
        return gap.status
    if adapter is None:
        return await _mark_unrecoverable(conn, gap_id, "no exact historical source available")

    try:
        observations = list(await adapter.fetch(gap))
        validate_recovery(gap, adapter, observations)
    except RecoveryValidationError as exc:
        await _record_recovery_failure(conn, gap_id, str(exc))
        return "unresolved"
    except Exception as exc:
        await _record_recovery_failure(
            conn,
            gap_id,
            f"historical source failed: {type(exc).__name__}",
        )
        return "unresolved"

    try:
        async with conn.transaction():
            current = await _load_gap(conn, gap_id, locked=True)
            if current is None:
                raise LookupError(f"data gap {gap_id} does not exist")
            if current.status != "unresolved":
                return current.status
            validate_recovery(current, adapter, observations)
            await adapter.persist(conn, observations)
            await conn.execute(
                """
                UPDATE data_gap SET
                  status='recovered',resolved_at=now(),recovered_at=now(),recovered_by=$2,
                  recovery_attempts=recovery_attempts+1,last_recovery_attempt_at=now(),
                  resolution_reason='validated exact-source recovery',
                  recovery_metadata=$3::jsonb
                WHERE id=$1
                """,
                gap_id,
                adapter.name[:120],
                json.dumps(
                    {"observations": len(observations), "granularity": current.granularity}
                ),
            )
    except RecoveryValidationError as exc:
        await _record_recovery_failure(conn, gap_id, str(exc))
        return "unresolved"
    return "recovered"


AdapterResolver = Callable[[DataGap], RecoveryAdapter | None]


async def recover_unresolved_gaps(
    conn: asyncpg.Connection,
    resolver: AdapterResolver,
    *,
    gap_id: int | None = None,
    limit: int = 100,
) -> dict[GapStatus, int]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    rows = await conn.fetch(
        """
        SELECT id,feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,
               expected_cadence,status
        FROM data_gap
        WHERE status='unresolved' AND ($1::bigint IS NULL OR id=$1)
        ORDER BY detected_at,id
        LIMIT $2
        """,
        gap_id,
        limit,
    )
    counts: dict[GapStatus, int] = {"unresolved": 0, "recovered": 0, "unrecoverable": 0}
    for row in rows:
        gap = DataGap.from_record(row)
        status = await recover_gap(conn, gap.id, resolver(gap))
        counts[status] += 1
    return counts
