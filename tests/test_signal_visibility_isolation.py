"""Una pasada de certificacion que falla no puede dejar a la otra sin correr.

El 2026-08-20 las dos tablas de visibilidad se pararon a la vez. La causa no era que
las dos estuvieran rotas: run_certification_cycle llamaba a certify_research_bundles
y despues a certify_final_outcomes como dos await seguidos, asi que cuando la primera
empezo a lanzar TimeoutError -por un plan que degenero al crecer las tablas- la
segunda dejo de ejecutarse. Medido en 140 el 2026-08-25: 206884 outcomes
certificables esperando detras de un fallo que no era suyo.
"""

from __future__ import annotations

import pytest

import app.signal_visibility as visibility
from app.db import ServiceOwnershipLost


async def test_un_fallo_certificando_bundles_no_impide_certificar_outcomes(
    monkeypatch: pytest.MonkeyPatch,
):
    llamadas: list[str] = []

    async def bundles_que_revientan(*_args, **_kwargs):
        llamadas.append("bundles")
        raise TimeoutError

    async def outcomes_ok(*_args, **_kwargs):
        llamadas.append("outcomes")
        return 7

    monkeypatch.setattr(visibility, "certify_research_bundles", bundles_que_revientan)
    monkeypatch.setattr(visibility, "certify_final_outcomes", outcomes_ok)

    # El error se sigue propagando: el que llama tiene que poder registrarlo.
    with pytest.raises(TimeoutError):
        await visibility.run_certification_cycle(conn=None)  # type: ignore[arg-type]

    # Y esto es lo que no pasaba: la segunda pasada corrio igualmente.
    assert llamadas == ["bundles", "outcomes"]


async def test_perder_la_propiedad_del_servicio_sigue_cortando_en_seco(
    monkeypatch: pytest.MonkeyPatch,
):
    """ServiceOwnershipLost es la excepcion que NO se puede tragar: si este proceso
    ya no es el duenyo del shard, no puede seguir escribiendo certificados."""

    llamadas: list[str] = []

    async def bundles_sin_propiedad(*_args, **_kwargs):
        llamadas.append("bundles")
        raise ServiceOwnershipLost

    async def outcomes_ok(*_args, **_kwargs):
        llamadas.append("outcomes")
        return 0

    monkeypatch.setattr(visibility, "certify_research_bundles", bundles_sin_propiedad)
    monkeypatch.setattr(visibility, "certify_final_outcomes", outcomes_ok)

    with pytest.raises(ServiceOwnershipLost):
        await visibility.run_certification_cycle(conn=None)  # type: ignore[arg-type]

    assert llamadas == ["bundles"]
