"""K43 — la foto declara la VENTANA en que se armo, no un instante suelto.

El snapshot se arma en ~3 s y cada seccion resuelve su propio reloj. Medido en 140 el
2026-08-26: ``generated_at`` cae a mitad del armado, con 13 secciones calculadas antes
de su propia etiqueta y dos despues (``liquidation_map`` a +2.650 s). Una etiqueta unica
sobre datos de vendimias distintas miente mas que ninguna, porque parece autoritativa.

Lo que describe la foto es un intervalo, y es lo que se declara. El bundle es el caso
extremo: arma N fotos EN SERIE, asi que su ventana tiene que cubrir la de todas.
"""

import asyncio
from datetime import UTC, datetime

import pytest

import app.ai_context as ai_context
from app.ai_context import build_ai_context

SIMBOLOS = ["BTCUSDT_PERP.A", "ETHUSDT_PERP.A"]


@pytest.mark.asyncio
async def test_la_ventana_del_bundle_cubre_la_de_cada_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada foto se arma en un instante distinto; la ventana del sobre las contiene."""
    marcas: list[datetime] = []

    async def fake(_conn, symbol, *, profile="default", bucket_bps=10):
        await asyncio.sleep(0.02)  # el armado real tarda; sin esto no habria ventana
        ahora = datetime.now(UTC)
        marcas.append(ahora)
        return {
            "symbol": symbol,
            "asset": symbol[:3],
            "generated_at": ahora.isoformat(),
            "local_alerts": [],
            "interpretation_prompt": "x",
        }

    monkeypatch.setattr(ai_context, "build_ai_symbol_context", fake)
    d = await build_ai_context(None, SIMBOLOS)

    t0 = datetime.fromisoformat(d["build_started_at"])
    t1 = datetime.fromisoformat(d["build_finished_at"])
    assert t0 <= t1
    assert len(marcas) == len(SIMBOLOS)
    for m in marcas:
        assert t0 <= m <= t1, "una foto se armo fuera de la ventana que la etiqueta"
    # y la ventana es ANCHA de verdad: si fuese un instante, esto seria 0
    assert (t1 - t0).total_seconds() >= 0.04


@pytest.mark.asyncio
async def test_generated_at_cae_dentro_de_la_ventana(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """generated_at se queda -lo consume el ai-bridge- pero no puede contradecir al sobre."""

    async def fake(_conn, symbol, *, profile="default", bucket_bps=10):
        return {"symbol": symbol, "asset": symbol[:3], "local_alerts": []}

    monkeypatch.setattr(ai_context, "build_ai_symbol_context", fake)
    d = await build_ai_context(None, SIMBOLOS)

    t0 = datetime.fromisoformat(d["build_started_at"])
    t1 = datetime.fromisoformat(d["build_finished_at"])
    assert t0 <= datetime.fromisoformat(d["generated_at"]) <= t1


@pytest.mark.asyncio
async def test_la_ventana_no_termina_antes_de_empezar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake(_conn, symbol, *, profile="default", bucket_bps=10):
        return {"symbol": symbol, "asset": symbol[:3], "local_alerts": []}

    monkeypatch.setattr(ai_context, "build_ai_symbol_context", fake)
    d = await build_ai_context(None, ["BTCUSDT_PERP.A"])

    assert d["build_started_at"] <= d["build_finished_at"]
