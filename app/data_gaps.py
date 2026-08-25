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

# Motivo de archivado que afirma algo sobre EL DATO, no sobre nuestra herramienta. La
# diferencia no es de estilo: "no exact historical source available" (_mark_unrecoverable)
# dice que NOSOTROS no sabemos ir a buscarlo, y eso no cierra nada, solo lo esconde.
# Esto otro dice que el bucket no existe en la fuente, y ademas solo se escribe cuando
# la respuesta de la fuente lo cubria y lo salto. Es una comprobacion, no un default.
SOURCE_ABSENCE_REASON = (
    "source does not publish this bucket: absent from a source response covering it"
)

# OTRO hecho distinto, y por eso otro motivo: aqui la fuente no se salta un bucket,
# es que ya no sirve esa ventana entera. Medido el 2026-08-25: long_short_ratio 5min
# se sirve hasta 200 h atras y ni un bucket mas. La trampa es que "ya no lo sirve" y
# "esta caida" devuelven las dos lo mismo -vacio-, asi que archivar por respuesta
# vacia a secas convertiria una caida del proveedor en un barrido silencioso del
# atraso. Por eso hace falta un CONTROL reciente que SI devuelva serie.
PROVIDER_HORIZON_REASON = (
    "source no longer serves this window: it came back empty while a recent control "
    "window returned data"
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


# --- LO QUE EL SISTEMA YA SABE, DICHO EN VOZ ALTA -------------------------------
# blocking_requirement_keys responde "si o no" y con eso basta para poner un valor a
# null (K02). No basta para DECLARAR el hueco: para eso hay que devolver la ventana,
# su estado y de donde salio. Y hay una trampa medida el 2026-08-25 contra 140: el
# hueco NO esta guardado como una ventana. El del 2026-08-14 en ohlcv_1min de BTC son
# 86 FILAS ANIDADAS (16:47->18:13, 16:48->18:13, 16:49->18:13 ... todas acabando en el
# mismo punto), una por cada minuto que el barrido volvio a echar en falta. Devolverlas
# tal cual seria un bloque ilegible que ademas sugiere 86 incidentes donde hubo uno.
# Por eso se FUNDEN en islas. Se funden dentro de la misma identidad y el mismo estado
# -(feed, exchange, market, symbol, status)- y nunca entre estados distintos: que un
# tramo sea irrecuperable y el de al lado siga pendiente son dos hechos, no uno.
# Se conserva `declarations` para no perder cuantas filas lo sostienen.
GAP_ISLANDS_SQL = """
WITH solapan AS (
  SELECT feed, exchange, market, symbol, granularity, status,
         start_ts, end_ts, detection_source, resolution_reason
  FROM data_gap
  WHERE feed = $1 AND exchange = ANY($2::text[]) AND market = $3 AND symbol = $4
    AND status IN ('unresolved','unrecoverable')
    AND start_ts < $6 AND end_ts > $5
), marcado AS (
  SELECT *, CASE WHEN start_ts <= MAX(end_ts) OVER (
              PARTITION BY feed, exchange, market, symbol, status
              ORDER BY start_ts, end_ts
              ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
            THEN 0 ELSE 1 END AS abre_isla
  FROM solapan
), islas AS (
  SELECT *, SUM(abre_isla) OVER (
              PARTITION BY feed, exchange, market, symbol, status
              ORDER BY start_ts, end_ts
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS isla
  FROM marcado
)
SELECT feed, exchange, market, symbol, status,
       MIN(start_ts) AS start_ts, MAX(end_ts) AS end_ts,
       MIN(granularity) AS granularity,
       COUNT(*)::int AS declarations,
       array_agg(DISTINCT detection_source) AS detection_sources,
       MIN(resolution_reason) AS resolution_reason
FROM islas
GROUP BY feed, exchange, market, symbol, status, isla
ORDER BY MIN(start_ts)
"""


async def declared_gap_windows(
    conn: asyncpg.Connection,
    *,
    feed: str,
    exchanges: Sequence[str],
    market: str,
    symbol: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Ventanas de hueco que BLOQUEAN dentro de ``[start,end)``, ya fundidas en islas.

    Solo 'unresolved' y 'unrecoverable', las mismas que bloquean una evaluacion: un
    hueco 'recovered' ya no le falta a nadie y anunciarlo seria ruido.
    """
    start, end = _validated_window(start, end)
    rows = await conn.fetch(GAP_ISLANDS_SQL, feed, list(exchanges), market, symbol, start, end)
    return [
        {
            "feed": row["feed"],
            "exchange": row["exchange"],
            "market": row["market"],
            "symbol": row["symbol"],
            "granularity": row["granularity"],
            "start": row["start_ts"].astimezone(UTC).isoformat(),
            "end": row["end_ts"].astimezone(UTC).isoformat(),
            "status": row["status"],
            "declarations": row["declarations"],
            "detection_sources": sorted(row["detection_sources"] or ()),
            "reason": row["resolution_reason"],
        }
        for row in rows
    ]


def align_down(moment: datetime, cadence: timedelta) -> datetime:
    """El ultimo bucket cerrado de ``cadence`` en o antes de ``moment``, sobre la epoca.

    Sin esto, una ventana que acaba en ``now()`` no tiene un numero entero de buckets y
    "esperados" seria una opinion. Es la misma rejilla que usa date_bin con origen
    1970-01-01, asi que la cuenta cuadra con lo que hay en la tabla.
    """
    moment = _aware_utc(moment, "moment")
    if cadence <= timedelta(0):
        raise ValueError("cadence must be positive")
    return moment - (moment - datetime(1970, 1, 1, tzinfo=UTC)) % cadence


def expected_buckets(start: datetime, end: datetime, cadence: timedelta) -> int:
    """Cuantos buckets de ``cadence`` caben en ``[start,end)``. Sin cadencia no hay cuenta."""
    start, end = _validated_window(start, end)
    if cadence <= timedelta(0):
        raise ValueError("cadence must be positive")
    return int((end - start) / cadence)


def coverage_entry(
    start: datetime,
    end: datetime,
    *,
    sources: Sequence[tuple[str, int, int]],
) -> dict[str, Any]:
    """La cobertura de UNA ventana agregada, con sus patas separadas.

    ``sources`` son tripletas (etiqueta, esperados, observados). expected_buckets y
    observed_buckets son la SUMA de las patas, porque un promedio que necesita dos
    fuentes no esta completo si le falta una: complete es la conjuncion, no la de la
    pata mas afortunada. `sources` queda dentro para poder decir CUAL fallo.

    Los observados que reciba tienen que ser BUCKETS DISTINTOS, no filas. No se recorta
    observados a esperados a proposito: si sale mayor, la cadencia declarada no es la
    que tiene la tabla, y taparlo con un min() convertiria ese fallo en un numero
    tranquilizador.
    """
    start, end = _validated_window(start, end)
    esperados = sum(item[1] for item in sources)
    observados = sum(item[2] for item in sources)
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "expected_buckets": esperados,
        "observed_buckets": observados,
        "complete": observados == esperados,
        "sources": {
            etiqueta: {"expected_buckets": esperados_i, "observed_buckets": obs_i}
            for etiqueta, esperados_i, obs_i in sources
        },
    }


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
class CadenceCoverage:
    """Coverage proof for one exact cadence identity and half-open window."""

    start: datetime
    end: datetime
    cadence: timedelta
    expected_buckets: int
    observed_buckets: int
    missing_buckets: int
    missing_windows: tuple[tuple[datetime, datetime], ...]
    recovered_gaps: int
    # Cuantos huecos se archivaron como ausencia probada de la fuente en esta pasada.
    # Sin esto el repaso no puede decir lo que hizo, y un contador que no se incrementa
    # nunca es peor que no tenerlo: parece que no paso nada.
    archived_gaps: int = 0

    @property
    def complete(self) -> bool:
        return self.missing_buckets == 0


async def reconcile_cadence_coverage(
    conn: asyncpg.Connection,
    *,
    observations: Iterable[datetime],
    feed: str,
    exchange: str,
    market: str,
    symbol: str,
    granularity: str,
    start: datetime,
    end: datetime,
    cadence: timedelta,
    detection_source: str,
    source_response_buckets: Iterable[datetime] | None = None,
) -> CadenceCoverage:
    """Record missing cadence and recover only when every expected bucket is proven.

    ``observations`` are explicit proof supplied by the caller. They may come from accepted
    rows in the current provider response or from canonical persisted storage. Event feeds
    are deliberately excluded: silence in an event feed is never missing-cadence evidence.

    ``source_response_buckets`` are the buckets the SOURCE returned, before we validated
    anything. They are not the same as ``observations``: the difference between the two is
    exactly the row we dropped ourselves, and that one is never the source's fault. Given
    them, a bucket the source skipped inside a span it did answer is archived as absent at
    the source; everything else stays unresolved. Absence in our own storage proves nothing
    about the source, so callers reading persisted rows pass nothing here.
    """
    start, end = _validated_window(start, end)
    if cadence <= timedelta(0):
        raise ValueError("cadence must be positive")
    if not all((feed, exchange, market, symbol, granularity, detection_source)):
        raise ValueError("cadence coverage identity cannot be empty")

    present: set[datetime] = set()
    for item in observations:
        normalized = _aware_utc(item, "observation")
        if start <= normalized < end:
            present.add(normalized)

    expected: list[datetime] = []
    cursor = start
    while cursor < end:
        expected.append(cursor)
        cursor += cadence
    expected_set = set(expected)
    missing_windows = tuple(
        missing_cadence_windows(present, start=start, end=end, cadence=cadence)
    )

    # Hasta donde llego la respuesta de la fuente. Solo lo que cae ESTRICTAMENTE dentro
    # de ese tramo esta probado como ausencia suya: si contesto antes del hueco y volvio
    # a contestar en cuanto acabo, lo salto ella. Silencio total, corte por delante o
    # respuesta truncada por detras no prueban nada, y ahi el hueco sigue siendo nuestro.
    returned: set[datetime] = set()
    for item in source_response_buckets or ():
        normalized = _aware_utc(item, "source response bucket")
        if start <= normalized < end:
            returned.add(normalized)
    first_returned = min(returned) if returned else None
    last_returned = max(returned) if returned else None

    for gap_start, gap_end in missing_windows:
        gap_id = await record_data_gap(
            conn,
            feed=feed,
            feed_class="cadence",
            exchange=exchange,
            market=market,
            symbol=symbol,
            granularity=granularity,
            start=gap_start,
            end=gap_end,
            evidence_type="missing_interval",
            detection_reason="cadence reconciliation is missing expected source buckets",
            detection_source=detection_source,
            expected_cadence=cadence,
        )
        # If the same evidence interval had previously recovered and disappears again,
        # it must block again. Explicitly unrecoverable rows remain immutable.
        await conn.execute(
            """
            UPDATE data_gap
            SET status='unresolved', resolved_at=NULL, recovered_at=NULL,
                recovered_by=NULL, resolution_reason=NULL
            WHERE id=$1 AND status='recovered'
            """,
            gap_id,
        )

    def _source_skipped(gap_start: datetime, gap_end: datetime) -> bool:
        """La fuente cubrio este tramo entero y no mando ni uno de sus buckets.

        Las dos mitades importan. El straddle prueba que la respuesta LLEGABA hasta aqui:
        contesto antes del tramo y volvio a contestar en cuanto acabo. Y que ningun bucket
        del tramo este en lo devuelto descarta que el que falta lo tirasemos NOSOTROS al
        validar, que es la distincion returned/accepted de
        _liquidation_history_observation. Sin las dos, no hay prueba.
        """
        if first_returned is None:
            return False
        if not (first_returned < gap_start and last_returned >= gap_end):
            return False
        cursor = gap_start
        while cursor < gap_end:
            if cursor in returned:
                return False
            cursor += cadence
        return True

    # Any exact cadence proof may recover an unresolved cadence gap for this source identity,
    # regardless of which detector originally found it. This lets a later canonical scan
    # recover a gap first detected from a current provider response.
    rows = await conn.fetch(
        """
        SELECT id,start_ts,end_ts
        FROM data_gap
        WHERE feed=$1 AND feed_class='cadence'
          AND exchange=$2 AND market=$3 AND symbol=$4 AND granularity=$5
          AND evidence_type='missing_interval'
          AND status='unresolved'
          AND start_ts >= $6 AND end_ts <= $7
        ORDER BY start_ts,id
        """,
        feed, exchange, market, symbol, granularity, start, end,
    )

    recovered = 0
    archived = 0
    for row in rows:
        gap_start = _aware_utc(row["start_ts"], "gap_start")
        gap_end = _aware_utc(row["end_ts"], "gap_end")
        bucket = gap_start
        proven = True
        while bucket < gap_end:
            if bucket not in expected_set or bucket not in present:
                proven = False
                break
            bucket += cadence
        if not proven:
            # Un tramo que la fuente cubrio y se salto no es una tarea pendiente nuestra:
            # es un hecho sobre el dato. Se archiva AQUI, en el mismo barrido que la
            # recuperacion y por el mismo motivo: el atraso vive en filas apuntadas por
            # OTRO detection_source, y record_data_gap lleva detection_source en la clave
            # de conflicto, asi que el mismo bucket visto por dos detectores son dos filas.
            # Archivar solo la fila que este detector acaba de apuntar dejaria el atraso
            # intacto: medido en 140 el 2026-08-25, la primera pasada del repaso archivo
            # 172 filas recien creadas por el y dejo las 244 originales sin tocar.
            # Recuperar y archivar son excluyentes: una exige todos los buckets, la otra
            # ninguno.
            if _source_skipped(gap_start, gap_end):
                resultado = await conn.execute(
                    """
                    UPDATE data_gap
                    SET status='unrecoverable',
                        resolved_at=clock_timestamp(), recovered_at=NULL,
                        recovery_attempts=recovery_attempts+1,
                        last_recovery_attempt_at=clock_timestamp(),
                        resolution_reason=$2,
                        recovery_metadata=jsonb_build_object(
                            'method','source_response_absence',
                            'proof_source',$3::text,
                            'response_first_bucket',$4::timestamptz,
                            'response_last_bucket',$5::timestamptz
                        )
                    WHERE id=$1 AND status='unresolved'
                    """,
                    int(row["id"]), SOURCE_ABSENCE_REASON, detection_source,
                    first_returned, last_returned,
                )
                if resultado == "UPDATE 1":
                    archived += 1
            continue
        result = await conn.execute(
            """
            UPDATE data_gap
            SET status='recovered',
                resolved_at=clock_timestamp(), recovered_at=clock_timestamp(),
                recovered_by='cadence_reconciliation',
                recovery_attempts=recovery_attempts+1,
                last_recovery_attempt_at=clock_timestamp(),
                resolution_reason='all expected buckets are present in explicit cadence proof',
                recovery_metadata=jsonb_build_object(
                    'method','cadence_reconciliation',
                    'proof_source',$4::text,
                    'verified_start',$2::timestamptz,
                    'verified_end',$3::timestamptz
                )
            WHERE id=$1 AND status='unresolved'
            """,
            int(row["id"]), start, end, detection_source,
        )
        if result == "UPDATE 1":
            recovered += 1

    observed = len(expected_set & present)
    return CadenceCoverage(
        start=start,
        end=end,
        cadence=cadence,
        expected_buckets=len(expected),
        observed_buckets=observed,
        missing_buckets=len(expected) - observed,
        missing_windows=missing_windows,
        recovered_gaps=recovered,
        archived_gaps=archived,
    )


async def archive_beyond_source_horizon(
    conn: asyncpg.Connection,
    *,
    feed: str,
    exchange: str,
    market: str,
    symbol: str,
    granularity: str,
    window_start: datetime,
    window_end: datetime,
    control_start: datetime,
    control_end: datetime,
    control_returned_rows: int,
) -> int:
    """Archive a window the source no longer serves, proving the source is not merely down.

    ``reconcile_cadence_coverage`` deliberately abstains when the source answers nothing:
    no answer is not evidence of absence. That leaves gaps older than the source's horizon
    with no honest path out, so this is the other path, and it needs the other evidence.

    An exhausted horizon and an outage both come back empty. The only thing that tells them
    apart is a CONTROL: a recent window of the SAME identity that does return data. Without
    a positive control this refuses to touch anything, which is what stops a provider outage
    from silently sweeping the whole backlog into 'unrecoverable'.

    The proof is written to ``recovery_metadata`` so it can be re-derived from the row alone
    months later; harness/checks/K04-huecos.sh does exactly that.
    """
    window_start, window_end = _validated_window(window_start, window_end)
    control_start, control_end = _validated_window(control_start, control_end)
    if not all((feed, exchange, market, symbol, granularity)):
        raise ValueError("gap identity cannot be empty")
    if control_returned_rows <= 0:
        raise ValueError(
            "a silent source is not proof of an exhausted horizon: "
            "the control window must return rows"
        )
    if control_end <= window_end:
        raise ValueError("the control window must be more recent than the archived window")

    result = await conn.execute(
        """
        UPDATE data_gap
        SET status='unrecoverable',
            resolved_at=clock_timestamp(), recovered_at=NULL,
            recovery_attempts=recovery_attempts+1,
            last_recovery_attempt_at=clock_timestamp(),
            resolution_reason=$8,
            recovery_metadata=jsonb_build_object(
                'method','provider_horizon_exhausted',
                'window_start',$6::timestamptz,
                'window_end',$7::timestamptz,
                'window_returned_rows',0,
                'control_start',$9::timestamptz,
                'control_end',$10::timestamptz,
                'control_returned_rows',$11::int,
                'checked_at',clock_timestamp()
            )
        WHERE feed=$1 AND feed_class='cadence'
          AND exchange=$2 AND market=$3 AND symbol=$4 AND granularity=$5
          AND status='unresolved'
          AND start_ts >= $6 AND end_ts <= $7
        """,
        feed, exchange, market, symbol, granularity,
        window_start, window_end, PROVIDER_HORIZON_REASON,
        control_start, control_end, int(control_returned_rows),
    )
    return int(result.rsplit(" ", 1)[-1]) if result.startswith("UPDATE ") else 0


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
