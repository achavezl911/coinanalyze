"""Regresiones de la auditoria v1.3.1.

/metrics devolvia 500 (KeyError: 'detail') porque prometheus_metrics leia una columna
que su propio SELECT no pedia. El smoke test no cubria /metrics, asi que paso inadvertido
durante varias versiones. Estos tests ejercitan el endpoint de verdad, no su texto.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import api
from app.scalp_logic import classify_absorption

ROOT = Path(__file__).resolve().parents[1]


class FakeRecord(dict):
    """dict lanza KeyError igual que asyncpg.Record ante una columna no pedida."""


class FakeConnection:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def fetch(self, query: str, *_args: object) -> list[FakeRecord]:
        self.queries.append(query)
        if "pipeline_heartbeat" in query:
            row = {"service": "scalp", "status": "ok", "lag_seconds": 1.0}
            # Solo se expone lo que el SELECT realmente pide.
            if "detail" in query:
                row["detail"] = "liq_dropped:3,trade_buckets_rt:12,binance_reconnects:7"
            return [FakeRecord(row)]
        if "metrics_snapshot" in query:
            return [FakeRecord({"symbol": "BTCUSDT_PERP.A", "lag_seconds": 2.0})]
        return [FakeRecord({"table_name": "futures_trades_realtime", "rows": 10})]


class FakePool:
    def __init__(self) -> None:
        self.conn = FakeConnection()

    def acquire(self):
        pool = self

        class Ctx:
            async def __aenter__(self):
                return pool.conn

            async def __aexit__(self, *_exc: object) -> None:
                return None

        return Ctx()


@pytest.mark.asyncio
async def test_prometheus_metrics_renders_scalp_runtime_values(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool()
    monkeypatch.setattr(api.app.state, "pool", pool, raising=False)
    monkeypatch.setattr(api.SETTINGS, "METRICS_ENABLED", True)

    response = await api.prometheus_metrics()
    body = response.body.decode()

    assert response.status_code == 200
    assert 'coinalyze_heartbeat_lag_seconds{service="scalp"} 1.000' in body
    assert 'coinalyze_service_ok{service="scalp"} 1' in body
    assert 'coinalyze_symbol_snapshot_lag_seconds{symbol="BTCUSDT_PERP.A"} 2.000' in body
    assert 'coinalyze_table_rows{table="futures_trades_realtime"} 10' in body
    # Estas solo aparecen si el detail del heartbeat llego hasta el render.
    assert "coinalyze_scalp_liquidations_dropped_total 3" in body
    assert "coinalyze_scalp_tradestore_realtime_buckets 12" in body
    assert "coinalyze_scalp_binance_book_reconnect_total 7" in body


# ---------------------------------------------------------------------------
# EXTRACT(EPOCH ...) TIENE QUE LLEGAR AL JSON COMO NUMERO, NO COMO Decimal
# ---------------------------------------------------------------------------
# LA INTENCION NO CAMBIA Y SIGUE SIENDO BUENA: `EXTRACT(EPOCH ...)` devuelve `numeric`,
# asyncpg lo entrega como `Decimal`, y un `Decimal` NO es serializable a JSON. Esta regla
# protege hoy 25 lineas reales de lag, edad y span en tres modulos.
#
# LO QUE CAMBIA ES LA REGLA, y el motivo se midio contra el espejo por asyncpg el 2026-09-06
# -no por psql, que devuelve texto y no distingue-:
#
#     sin cast    -> Decimal   json.dumps FALLA
#     ::numeric   -> Decimal   json.dumps FALLA          <- igual de peligroso que sin cast
#     ::float8    -> float     json.dumps ok
#     ::real      -> float     json.dumps ok
#     ::bigint    -> int       json.dumps ok
#     ::int       -> int       json.dumps ok
#
# O sea que **los casts que salvan del Decimal son varios, no uno**. Exigir literalmente
# `::float8` no era la regla: era UNO de sus casos.
#
# Y POR QUE SE TOCA AHORA, con el caso que lo destapo: `signal_base_rate` usa
# `(EXTRACT(EPOCH FROM o.window_start)/60/$4)::bigint AS blk` como CLAVE DE AGRUPACION de una
# cadena de CTEs. `blk` no sale en la respuesta -el SELECT final publica 10 columnas y
# ninguna es `blk`- y `::bigint` da un `int`, asi que el peligro que esta regla describe no
# puede materializarse ahi. Pero lo decisivo no es eso: **obedecer la regla literal ROMPE la
# consulta**. Medido contra 140, la misma consulta con `::float8` en vez de `::bigint`:
#
#     ::bigint  -> 605 bloques, 13 717 observaciones, todas las cifras
#     ::float8  -> 0 bloques, todo null
#
# Con un `float8` la clave deja de ser un entero, cada fila cae en su propio grupo, el JOIN
# entre señal y base no encuentra nada y la tarjeta publicaria `available: false` **sin
# error**. El cast que la regla exigia no era innecesario: era incorrecto.
#
# LO QUE NO SE HACE, y se dice para que nadie lo intente luego: no se afloja a «cualquier
# cast» -`::numeric` y `::text` siguen fallando- y no hay lista de excepciones por linea ni
# por nombre de columna, que envejeceria en silencio. La regla se escribe mejor y punto.
#
# `\b` al final de la alternancia NO es adorno: sin el, `::INT` casaria dentro de
# `::INTERVAL`, que no es un numero.
CASTS_QUE_ASYNCPG_DA_COMO_NUMERO = re.compile(
    r"::\s*(float8|float4|double\s+precision|real|bigint|integer|int8|int4|int)\b",
    re.IGNORECASE,
)


def _publica_epoch_sin_cast_numerico(line: str) -> bool:
    """True si la linea saca un EXTRACT(EPOCH ...) con nombre y NO lo lleva a un tipo que
    asyncpg entregue como numero nativo de Python."""
    upper = line.upper()
    if "EXTRACT(EPOCH" not in upper or " AS " not in upper:
        return False
    return CASTS_QUE_ASYNCPG_DA_COMO_NUMERO.search(line) is None


def test_extract_epoch_llega_al_json_como_numero_y_no_como_decimal() -> None:
    """EXTRACT(EPOCH ...) devuelve numeric -> asyncpg da Decimal -> el JSON no se puede serializar.

    (Antes se llamaba `test_lag_columns_are_cast_to_float8_so_json_stays_numeric`. Se renombro
    porque el nombre decia `float8` y la regla acepta varios tipos: una etiqueta que dice una
    cosa y un criterio que comprueba otra es justo lo que este arnes persigue.)
    """
    for name in ("app/api.py", "app/ai_context.py", "app/scalp_logic.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        for line in source.splitlines():
            assert not _publica_epoch_sin_cast_numerico(line), (
                f"{name}: EXTRACT(EPOCH ...) con nombre y sin cast a un tipo que asyncpg "
                f"entregue como numero (float8/real/bigint/int): {line.strip()}"
            )


def test_el_guardia_del_epoch_sigue_cazando_lo_que_se_escribio_para_cazar() -> None:
    """EL CONTROL DE LA REGLA, y sin el la regla nueva no se puede defender.

    Al ensanchar un guardia hay que demostrar que sigue atrapando el caso original. Estas
    son lineas de mentira con veredicto conocido: las cuatro primeras TIENEN que enrojecer.
    """
    debe_fallar = [
        # el caso para el que se escribio la regla: sin cast ninguno
        "EXTRACT(EPOCH FROM now()-updated_at) AS lag_seconds",
        # el otro camino al mismo Decimal, y por eso «cualquier cast» no vale
        "EXTRACT(EPOCH FROM now()-updated_at)::numeric AS lag_seconds",
        # un cast que no es numero: `::INT` no puede casar dentro de `::INTERVAL`
        "EXTRACT(EPOCH FROM now()-updated_at)::interval AS ventana",
        "EXTRACT(EPOCH FROM now()-updated_at)::text AS lag_seconds",
    ]
    debe_pasar = [
        "EXTRACT(EPOCH FROM now()-updated_at)::float8 AS lag_seconds",
        "EXTRACT(EPOCH FROM now()-ts)::real AS age_seconds",
        "(EXTRACT(EPOCH FROM o.window_start)/60/$4)::bigint AS blk",
        "(EXTRACT(EPOCH FROM ts)/86400)::integer AS dia",
        # sin nombre no publica nada: la regla no aplica
        "WHERE EXTRACT(EPOCH FROM now()-ts) > 60",
    ]
    for linea in debe_fallar:
        assert _publica_epoch_sin_cast_numerico(linea), f"deberia enrojecer: {linea}"
    for linea in debe_pasar:
        assert not _publica_epoch_sin_cast_numerico(linea), f"NO deberia enrojecer: {linea}"


@pytest.mark.parametrize(
    ("delta", "move", "volume", "expected_score", "expected_label"),
    [
        (0.0, 0.0, 1_000.0, 0.0, "Neutra"),
        (None, 1.0, 1_000.0, 0.0, "Neutra"),
        # El delta pesa el 20% del volumen: por encima de ABSORPTION_MIN_RATIO.
        (1_000.0, 0.01, 5_000.0, -1.0, "Absorción de compras"),
        (-1_000.0, -0.01, 5_000.0, 1.0, "Absorción de ventas"),
        (1_000.0, -0.5, 5_000.0, -1.0, "Absorción fuerte de compras"),
        (-1_000.0, 0.5, 5_000.0, 1.0, "Absorción fuerte de ventas"),
        (1_000.0, 0.5, 5_000.0, 0.0, "Neutra"),
        # Sin volumen la magnitud no se puede juzgar: no se inventa una lectura.
        (1_000.0, 0.01, None, 0.0, "Sin datos"),
        (1_000.0, 0.01, 0.0, 0.0, "Sin datos"),
    ],
)
def test_classify_absorption(delta, move, volume, expected_score, expected_label) -> None:
    score, label = classify_absorption(delta, move, volume)
    assert (score, label) == (expected_score, expected_label)


@pytest.mark.parametrize("move", [0.01, -0.5, 0.5])
def test_absorption_requires_meaningful_magnitude(move) -> None:
    """1 USD de delta neto sobre 10M de volumen es ruido de redondeo, no absorcion.

    Antes bastaba con que delta y precio tuvieran signos opuestos para publicar
    "Absorcion fuerte", sin mirar cuanto pesaba ese delta.
    """
    score, label = classify_absorption(1.0, move, 10_000_000.0)
    assert (score, label) == (0.0, "Sin señal")


def test_absorption_has_a_single_definition() -> None:
    """El endpoint y el resumen de scalp usaban umbrales distintos (0.02 vs 0.04).

    Desde P2 el umbral ya no es una constante compartida sino el p75 MEDIDO de cada ventana
    (`metric_baseline`). Lo que hay que fijar es que ninguna de las dos rutas se quede con un
    literal: ambas tienen que leer la baseline.
    """
    api_source = (ROOT / "app" / "api.py").read_text(encoding="utf-8")
    logic_source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    # Se fija el CONTRATO, no el formato exacto de la llamada: ambas rutas tienen que leer
    # el p75 de la baseline y ninguna puede clasificar sin delta y sin movimiento medidos.
    # Desde el 2026-08-26 las DOS rutas viven en scalp_logic: la del endpoint se movio alli
    # para que /api/ai/context pueda servir la misma respuesta sin ciclo de imports (api.py
    # importa ai_context). El contrato se fija donde vive el calculo, y de api.py se exige
    # ademas que DELEGUE: sin SQL propio, sin umbral propio y sin clasificar por su cuenta.
    assert "classify_absorption(" in logic_source
    assert '(baseline or {}).get("p75")' in logic_source
    assert "if delta is None or move is None:" in logic_source
    assert '(baseline_3m or {}).get("p75"),' in logic_source
    assert "if price_move_3m is None:" in logic_source
    assert logic_source.count("Absorción fuerte de compras") == 1
    cuerpo = api_source.split('@app.get("/api/scalp/absorption")')[1].split("@app.get")[0]
    assert "scalp_absorption_read(conn, selected)" in cuerpo
    assert "SELECT" not in cuerpo
    assert "classify_absorption(" not in cuerpo
    assert "0.02" not in cuerpo
    # La constante sigue existiendo SOLO como fallback declarado, definida una vez.
    assert logic_source.count("ABSORPTION_MIN_RATIO = ") == 1
    assert "FALLBACK" in logic_source.split("ABSORPTION_MIN_RATIO = ")[1][:200]


def test_trend_matrix_oi_window_matches_the_timeframe() -> None:
    """1d/3d median el OI sobre n sesiones, no sobre toda la ventana cargada."""
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    start = source.index("async def trend_matrix")
    body = source[start:source.index("def compute_swing_score", start)]
    assert "daily[-n_back - 1][\"oi_close\"]" in body
    assert 'ds[0]["oi_close"]' not in body


def test_smoke_test_covers_metrics_and_a_symbol_endpoint() -> None:
    source = (ROOT / "scripts" / "smoke_test.sh").read_text(encoding="utf-8")
    assert "$BASE_URL/metrics" in source
    assert "/api/dashboard/state" in source


def test_update_refuses_an_incomplete_source_tree() -> None:
    """rsync --delete con un paquete solo-app borraba sql/, scripts/ y deploy/."""
    source = (ROOT / "scripts" / "update.sh").read_text(encoding="utf-8")
    guard = source.split("rsync -a --delete")[0]
    assert "REQUIRED_PATHS=(" in guard
    for path in ("requirements.lock", "sql/schema.sql", "scripts/backup.sh", "scripts/update.sh"):
        assert path in guard
    assert "Directorio fuente incompleto" in guard
    # el historico local de despliegues no vive en el repo: --delete lo borraria
    assert "--exclude '.deploy-backups'" in source


def test_vendor_checksums_are_verifiable_from_the_repo() -> None:
    """SHA256SUMS traia la ruta absoluta de la maquina de build; no verificaba nada."""
    sums = (ROOT / "static" / "vendor" / "SHA256SUMS").read_text(encoding="utf-8")
    for line in sums.splitlines():
        if not line.strip():
            continue
        name = line.split(maxsplit=1)[1].lstrip("*")
        assert not name.startswith("/"), f"ruta absoluta en SHA256SUMS: {name}"
        assert (ROOT / "static" / "vendor" / name).is_file()
