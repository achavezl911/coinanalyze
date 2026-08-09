from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ClosedCutoff:
    """Upper bounds for history whose buckets are fully closed.

    Coinalyze's ``to`` parameter is inclusive, while local SQL uses the exclusive
    boundary. Keeping both representations together prevents either caller from
    accidentally including the bucket that has just opened.
    """

    interval_seconds: int
    boundary_ts: int

    @classmethod
    def at(cls, now_utc: datetime, interval_seconds: int) -> ClosedCutoff:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if now_utc.tzinfo is None:
            raise ValueError("now_utc must be timezone-aware")
        epoch = int(now_utc.timestamp())
        return cls(interval_seconds, epoch // interval_seconds * interval_seconds)

    @property
    def api_end_ts(self) -> int:
        """Inclusive history-API upper bound, one second before the open bucket."""
        return self.boundary_ts - 1

    @property
    def latest_bucket_ts(self) -> int:
        """Start timestamp of the newest bucket that is fully closed."""
        return self.boundary_ts - self.interval_seconds

    @property
    def exclusive_boundary(self) -> datetime:
        return datetime.fromtimestamp(self.boundary_ts, tz=UTC)
