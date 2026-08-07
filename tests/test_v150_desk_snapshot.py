"""v1.5.0 — la Mesa se sirve de UN snapshot con un solo ancla temporal.

Antes cada panel pedia su endpoint y cada endpoint recalculaba `trend_matrix`,
`delta_matrix` y `scalp_context` con su propio `now()`: dos paneles contiguos podian estar
describiendo instantes distintos. Aqui se comprueba que el snapshot comparte `as_of`, que
declara la frescura por fuente y que no oculta los estados parciales.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from app import api


class _ConnFalsa:
    """Conexion de mentira: `desk_state` solo la usa para pasarla a funciones ya probadas."""

    async def fetch(self, *_args: Any, **_kwargs: Any) -> list:
        return []

    async def fetchrow(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def fetchval(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _PoolFalso:
    def acquire(self):
        conexion = _ConnFalsa()

        class _Ctx:
            async def __aenter__(self):
                return conexion

            async def __aexit__(self, *_exc):
                return False

        return _Ctx()


@pytest.fixture()
def desk(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(api.app.state, "pool", _PoolFalso(), raising=False)
    return asyncio.run(
        api.desk_state(symbol="BTCUSDT_PERP.A", profile="intradia", direction="long", setup="ruptura")
    )


def test_todos_los_componentes_comparten_el_mismo_ancla(desk: dict[str, Any]) -> None:
    as_of = desk["as_of"]
    assert as_of
    componentes = desk["components"]
    assert set(componentes) == {
        "trend_matrix", "delta_matrix", "profile", "hypothesis", "scalp", "data_quality",
    }
    sellos = {
        nombre: bloque.get("computed_at")
        for nombre, bloque in componentes.items()
        if isinstance(bloque, dict)
    }
    assert sellos, "ningun componente publica su ancla"
    assert set(sellos.values()) == {as_of}, f"anclas distintas: {sellos}"


def test_el_snapshot_declara_la_frescura_por_fuente(desk: dict[str, Any]) -> None:
    fuentes = desk["source_timestamps"]
    for clave in ("book_status", "basis_status", "collectors", "liquidations_measured"):
        assert clave in fuentes, clave
    # Un dato viejo no se vuelve actual por haberse leido ahora: la edad viaja aparte.
    assert "liquidations_last_event_age_s" in fuentes


def test_el_snapshot_no_oculta_los_estados_parciales(desk: dict[str, Any]) -> None:
    parcial = desk["partial"]
    assert "scalp_missing_components" in parcial
    assert "profile_missing_data" in parcial
    # Con la conexion vacia NADA se pudo medir: tiene que decirlo, no publicar 100%.
    assert parcial["scalp_coverage_pct"] == 0.0
    assert parcial["scalp_missing_components"]


def test_el_snapshot_respeta_direccion_y_setup(desk: dict[str, Any]) -> None:
    assert desk["direction"] == "long"
    assert desk["setup"] == "ruptura"
    assert desk["components"]["hypothesis"]["setup"] == "ruptura"


def test_los_componentes_compartidos_se_calculan_una_sola_vez() -> None:
    """`trend_matrix`, `delta_matrix` y `scalp_context` aparecen UNA vez en el endpoint."""
    fuente = inspect.getsource(api.desk_state)
    for funcion in ("trend_matrix(", "delta_matrix(", "scalp_context(", "data_quality("):
        assert fuente.count(f"await {funcion}") == 1, funcion


@pytest.mark.parametrize(
    ("kwargs", "detalle"),
    [
        ({"profile": "scalping"}, "perfil"),
        ({"direction": "moon"}, "direccion"),
        ({"setup": "cohete"}, "setup"),
    ],
)
def test_parametros_invalidos_son_422(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict, detalle: str
) -> None:
    monkeypatch.setattr(api.app.state, "pool", _PoolFalso(), raising=False)
    with pytest.raises(api.HTTPException) as error:
        asyncio.run(api.desk_state(symbol="BTCUSDT_PERP.A", **kwargs))
    assert error.value.status_code == 422
    assert detalle in error.value.detail


def test_los_endpoints_originales_siguen_existiendo() -> None:
    """No romper otras vistas: el snapshot AGREGA, no sustituye."""
    rutas = {getattr(r, "path", None) for r in api.app.routes}
    for ruta in ("/api/profile", "/api/hypothesis", "/api/trend-matrix", "/api/dashboard/state"):
        assert ruta in rutas, ruta
    assert "/api/desk/state" in rutas
