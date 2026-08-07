"""P1: vela de 18 m determinista y pata spot del mismo venue.

Coinalyze NO sirve el intervalo de 18 min (la API responde 400), asi que la vela se
construye resampleando 1min. Y si sirve mercados spot con delta real, que hasta ahora no se
ingerian: el CVD spot dependia de los colectores WS propios, limitados por retencion.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.api import HISTORICAL_INTERVALS, scalp_delta_matrix
from app.config import SPOT_HISTORY_MAP, SUPPORTED_SYMBOLS
from app.scalp_logic import flow_confirmation

ROOT = Path(__file__).resolve().parents[1]
CANDLE_MINUTES = 18


def test_18m_esta_disponible_como_vela() -> None:
    assert HISTORICAL_INTERVALS["18min"] == timedelta(minutes=CANDLE_MINUTES)


def test_18m_tesela_el_dia_utc_sin_residuo() -> None:
    """1440/18 = 80 exacto: ninguna vela queda a caballo entre dos dias UTC."""
    assert 1440 % CANDLE_MINUTES == 0
    assert 1440 // CANDLE_MINUTES == 80


def test_el_anclaje_en_1970_cae_en_medianoche_utc() -> None:
    """date_bin ancla en 1970-01-01T00:00:00Z; hay que probar que eso alinea con medianoche.

    Si el tamanio de la vela no dividiera al dia, el borde derivaria un poco cada jornada.
    """
    anchor = datetime(1970, 1, 1, tzinfo=UTC)
    step = timedelta(minutes=CANDLE_MINUTES)
    for dias in (1, 366, 20_000):
        medianoche = anchor + timedelta(days=dias)
        transcurrido = medianoche - anchor
        assert transcurrido % step == timedelta(0), f"la vela deriva tras {dias} dias"


@pytest.mark.parametrize("otra", [15, 20, 25])
def test_no_se_sustituye_por_una_temporalidad_vecina(otra: int) -> None:
    """El prompt maestro lo marca como requisito: 18m no es 15m ni 20m."""
    assert HISTORICAL_INTERVALS["18min"] != timedelta(minutes=otra)


def test_la_matriz_distingue_ventana_movil_de_vela_cerrada() -> None:
    """18m en delta-matrix es una VENTANA MOVIL; la vela cerrada es /api/ohlcv?interval=18min."""
    source = (ROOT / "app" / "api.py").read_text(encoding="utf-8")
    matriz = source.split("async def scalp_delta_matrix")[1].split("@app.get")[0]
    assert '("18m", 1080)' in matriz
    assert "VENTANA MOVIL" in matriz.upper()
    # 3d no puede entrar: futures_trades_agg retiene 36 h y solo daria `partial`.
    assert '("3d"' not in matriz


@pytest.mark.asyncio
async def test_la_matriz_no_pide_ventanas_que_la_retencion_no_cubre() -> None:
    capturado: dict[str, object] = {}

    class FakePool:
        def acquire(self):
            class Ctx:
                async def __aenter__(self):
                    return object()

                async def __aexit__(self, *_):
                    return False

            return Ctx()

    async def fake_delta_matrix(_conn, _symbol, windows):
        capturado["windows"] = windows
        return []

    import app.api as api_module

    original_pool = getattr(api_module.app.state, "pool", None)
    original_fn = api_module.delta_matrix
    api_module.app.state.pool = FakePool()
    api_module.delta_matrix = fake_delta_matrix
    try:
        await scalp_delta_matrix(SUPPORTED_SYMBOLS[0])
    finally:
        api_module.delta_matrix = original_fn
        if original_pool is not None:
            api_module.app.state.pool = original_pool

    etiquetas = [label for label, _ in capturado["windows"]]  # type: ignore[union-attr]
    assert "18m" in etiquetas
    assert "1d" in etiquetas
    assert "3d" not in etiquetas
    segundos = dict(capturado["windows"])  # type: ignore[arg-type]
    assert segundos["18m"] == CANDLE_MINUTES * 60


def test_el_spot_se_toma_del_mismo_venue_que_el_perp() -> None:
    """La asimetria de v1.3.4 era perp de Binance contra spot de Binance+Bybit."""
    for perp, spot in SPOT_HISTORY_MAP.items():
        assert perp.endswith(".A"), perp
        assert spot.endswith(".A"), f"{spot} no es del venue del perp"
    assert set(SPOT_HISTORY_MAP) == set(SUPPORTED_SYMBOLS)


def test_los_simbolos_spot_no_entran_en_la_superficie_del_dashboard() -> None:
    """validate_symbol filtra contra SUPPORTED_SYMBOLS: el spot solo existe como dato."""
    for spot in SPOT_HISTORY_MAP.values():
        assert spot not in SUPPORTED_SYMBOLS


def test_la_direccion_no_sale_de_la_resta_spot_menos_perp() -> None:
    """spot_perp_flow vota con flow_confirmation, que mira el signo de AMBAS patas.

    Caso real: perp comprando fuerte y spot comprando poco. La resta da negativo, pero las
    dos patas compran; el diferencial no es una direccion.
    """
    spot, perp = 1_000_000.0, 9_000_000.0
    assert spot - perp < 0
    assert flow_confirmation(spot, perp)["vote"] == 1


def test_el_spot_se_ingiere_en_la_misma_rejilla_que_el_perp() -> None:
    source = (ROOT / "app" / "daily_agg.py").read_text(encoding="utf-8")
    assert "spot_daily_payload" in source and "spot_h4_payload" in source
    # Mismas ventanas que el perp: si divergen, las patas no se pueden restar bucket a bucket.
    assert "start_ts=start_ts" in source and "start_ts=start_4h" in source
