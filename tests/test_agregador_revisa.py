"""El rollup vuelve a mirar las sesiones que quedaron incompletas, y sólo esas.

QUE ESTABA ROTO, medido el 2026-09-08. `backfill()` recorría 13 días pero saltaba cualquier
sesión con fila en cuanto pasaba de dos días (`if exists and offset >= 2: continue`). O sea que
cada sesión tenía DOS oportunidades —offsets 0 y 1— y luego quedaba congelada. Se ve en el
reloj: todas las sesiones tienen su última escritura a 61 h de abrirse, que es el offset 1.

Las tres filas del 2026-08-28 se calcularon con 219 de 288 muestras. Hoy `funding_rate` tiene
las 288 sin un solo hueco, y la fila seguía diciendo 219. El panel lo repetía con toda
honestidad sobre su fuente y engañando sobre el mundo.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from app.daily_agg import backfill

FUENTE = (Path(__file__).resolve().parents[1] / "app" / "daily_agg.py").read_text(encoding="utf-8")


class ConexionQueApunta:
    """Anota qué sesiones se recalcularon. `filas` dice cuáles existen y si están completas."""

    def __init__(self, filas: dict[tuple[str, date], bool]):
        self.filas = filas          # (symbol, fecha) -> incompleta
        self.recalculadas: list[tuple[str, date]] = []

    async def fetchrow(self, sql, *args):
        if "incompleta" in sql:
            symbol, fecha = args
            if (symbol, fecha) not in self.filas:
                return None
            return {"incompleta": self.filas[(symbol, fecha)]}
        return None

    async def fetchval(self, *_a, **_k):
        return None


@pytest.mark.asyncio
async def test_una_sesion_completa_y_vieja_no_se_recalcula(monkeypatch):
    """Recalcular una fila completa no puede mejorarla, y consume una consulta contra 140."""
    import app.daily_agg as m

    hoy = date(2026, 9, 8)
    monkeypatch.setattr(m, "latest_closed_session_date", lambda: hoy)
    monkeypatch.setattr(m, "WS_SYMBOL_MAP", {"BTCUSDT_PERP.A": "BTC"})
    tocadas = []

    async def falso(_conn, symbol, _ws, fecha):
        tocadas.append((symbol, fecha))
        return True

    monkeypatch.setattr(m, "compute_session", falso)
    filas = {("BTCUSDT_PERP.A", date(2026, 9, 8 - i)): False for i in range(5)}
    await backfill(ConexionQueApunta(filas), ("BTCUSDT_PERP.A",), 5)

    # offsets 0 y 1 siempre; del 2 en adelante, nada, porque todas están completas.
    assert [f for _, f in tocadas] == [date(2026, 9, 8), date(2026, 9, 7)]


@pytest.mark.asyncio
async def test_una_sesion_INCOMPLETA_y_vieja_SI_se_revisa(monkeypatch):
    """EL BRAZO QUE IMPORTA. Es el caso del 2026-08-28: fila vieja, incompleta, y la fuente ya
    completa. Antes se saltaba para siempre."""
    import app.daily_agg as m

    monkeypatch.setattr(m, "latest_closed_session_date", lambda: date(2026, 9, 8))
    monkeypatch.setattr(m, "WS_SYMBOL_MAP", {"BTCUSDT_PERP.A": "BTC"})
    tocadas = []

    async def falso(_conn, symbol, _ws, fecha):
        tocadas.append((symbol, fecha))
        return True

    monkeypatch.setattr(m, "compute_session", falso)
    filas = {("BTCUSDT_PERP.A", date(2026, 9, 8 - i)): False for i in range(6)}
    filas[("BTCUSDT_PERP.A", date(2026, 9, 4))] = True   # la incompleta, a 4 días
    await backfill(ConexionQueApunta(filas), ("BTCUSDT_PERP.A",), 6)

    assert date(2026, 9, 4) in [f for _, f in tocadas], "la incompleta no se revisó"
    assert [f for _, f in tocadas] == [date(2026, 9, 8), date(2026, 9, 7), date(2026, 9, 4)]


@pytest.mark.asyncio
async def test_una_sesion_que_no_existe_se_calcula_igual_que_antes(monkeypatch):
    """No se cambia lo que ya funcionaba: un hueco sin fila se rellena a cualquier profundidad."""
    import app.daily_agg as m

    monkeypatch.setattr(m, "latest_closed_session_date", lambda: date(2026, 9, 8))
    monkeypatch.setattr(m, "WS_SYMBOL_MAP", {"BTCUSDT_PERP.A": "BTC"})
    tocadas = []

    async def falso(_conn, symbol, _ws, fecha):
        tocadas.append(fecha)
        return True

    monkeypatch.setattr(m, "compute_session", falso)
    filas = {("BTCUSDT_PERP.A", date(2026, 9, 8 - i)): False for i in range(6)}
    del filas[("BTCUSDT_PERP.A", date(2026, 9, 3))]      # sin fila
    await backfill(ConexionQueApunta(filas), ("BTCUSDT_PERP.A",), 6)
    assert date(2026, 9, 3) in tocadas


def test_la_revision_tardia_no_puede_convertir_un_valor_en_NULL():
    """CRITERIO 3, y por qué es seguro revisar filas viejas aunque su fuente se haya podado.

    `futures_trades_agg` sólo retiene 168 h, así que un recálculo tardío ve menos que el
    original. La defensa ya estaba en el upsert: para `session_coverage_version IN (1,2)` cada
    columna usa COALESCE(nuevo, viejo). MEDIDO el 2026-09-08: las 42 filas de la ventana de 13
    días son TODAS versión 2, y `SESSION_COVERAGE_VERSION` vale 2.

    ESTE TEST FIJA LA DEPENDENCIA. El día que alguien suba la versión a 3, manda EXCLUDED y una
    revisión tardía SÍ podría convertir en NULL lo que una fuente podada no puede recalcular:
    hay 30 filas dentro de la ventana con `cvd_fut_2v_usd` calculado y su fuente ya vacía. Que
    este test enrojezca es el aviso de que esa decisión hay que tomarla a la vista.
    """
    from app.daily_agg import SESSION_COVERAGE_VERSION

    assert SESSION_COVERAGE_VERSION in (1, 2), (
        "la revisión tardía de sesiones viejas se apoya en que el upsert use COALESCE para las "
        "versiones 1 y 2. Con una versión superior, revisar una sesión cuya fuente ya se podó "
        "BORRA valores buenos. Antes de subirla, hay que acotar la revisión."
    )
    assert "COALESCE(EXCLUDED.cvd_fut_2v_usd,daily_session_agg.cvd_fut_2v_usd)" in FUENTE


def test_solo_se_revisa_lo_incompleto_y_esta_escrito_en_el_codigo():
    """La condición es la que decide el coste, así que se fija: si alguien la relaja a «siempre»,
    el agregador pasa a recalcular 13 días en cada pasada."""
    assert re.search(r"if fila is not None and offset >= 2 and not fila\[.incompleta.\]", FUENTE)
