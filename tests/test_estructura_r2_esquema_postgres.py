"""ESTRUCTURA R2 · bot_evento admite el tipo 'estructura' por el esquema que aplica el despliegue (sin ALTER a mano).

ESTRUCTURA R1 registra cada aviso en sombra como bot_evento tipo 'estructura' (app/bot/servicio.py, evento()), pero
el CHECK de bot_evento.tipo no lo admitia: en 140 el INSERT caia y /estado decia CAUSA=BASE. El despliegue re-aplica
sql/schema.sql (cada orden por esquema_ddl), asi que el cambio va ahi: la lista en el CREATE TABLE (base nueva) y un
paso idempotente que sustituye el CHECK de una base existente solo si no admite ya 'estructura'.
(a) base nueva: el INSERT del bot con tipo 'estructura' entra.
(b) actualizacion: base con el schema.sql de main (b460c4c) y una fila de cada tipo viejo; aplicar el de la rama DOS
    veces: no falla, las filas siguen, la segunda pasada no toca bot_evento y el INSERT 'estructura' entra.
(c) el CHECK viejo con otro nombre: aplicar no rompe, el viejo se va y queda uno solo que admite 'estructura'.
"""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
# El schema.sql de main (b460c4c) sale del de la rama: sin el bloque de ESTRUCTURA R2 y con la lista vieja. La CI
# clona con profundidad 1 (sin b460c4c): donde el objeto existe, test_main_es_b460c4c comprueba que son los mismos bytes.
MAIN_SQL = re.sub(r"-- ESTRUCTURA R2 >>>.*?-- <<< ESTRUCTURA R2\n", "", SCHEMA_SQL, flags=re.S).replace(
    "'validacion', 'vigia', 'estructura')),", "'validacion', 'vigia')),")
VIEJOS = ("rafaga", "clase", "stop", "liquidacion", "sin_stop", "bybit", "arranque", "parte", "informe", "validacion",
          "vigia")
# La sentencia de app/bot/servicio.py (evento), tal cual
INSERTA = ("INSERT INTO bot_evento (tipo, symbol, minuto, lado, clase, enviada, detalle)"
           " VALUES ($1, $2, to_timestamp($3::bigint * 60), $4, $5, $6, $7::jsonb) ON CONFLICT DO NOTHING")


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"estructura_r2_{uuid.uuid4().hex}"
    admin = await asyncpg.connect(_dsn())
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    c = await asyncpg.connect(_dsn())
    await c.execute(f'SET search_path TO "{schema}", public')
    await c.execute("SET TIME ZONE 'UTC'")
    try:
        yield c
    finally:
        await c.close()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


async def _aplica(c: asyncpg.Connection, sql: str) -> list[str]:
    avisos: list[str] = []

    def oye(_c, m):
        avisos.append(m.message)

    c.add_log_listener(oye)
    try:
        await c.execute(sql)
    finally:
        c.remove_log_listener(oye)
    return avisos


async def _estructura(c: asyncpg.Connection) -> None:
    await c.execute(INSERTA, "estructura", None, None, None, None, False,
                    '{"modo": "sombra", "generated_at": "2026-11-26T18:00:00Z", "texto": "giro"}')
    assert await c.fetchval("SELECT detalle->>'modo' FROM bot_evento WHERE tipo = 'estructura'") == "sombra"


async def _checks_de_tipo(c: asyncpg.Connection) -> list[tuple[str, str]]:
    filas = await c.fetch("SELECT conname, pg_get_constraintdef(oid) AS d FROM pg_constraint"
                          " WHERE conrelid = 'bot_evento'::regclass AND contype = 'c' ORDER BY conname")
    return [(f["conname"], f["d"]) for f in filas if re.search(r"\btipo\b", f["d"])]


def test_main_es_b460c4c():
    r = subprocess.run(["git", "-C", str(ROOT), "show", "b460c4c:sql/schema.sql"], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("b460c4c no esta en este clon (la CI clona con profundidad 1)")
    assert MAIN_SQL == r.stdout


async def test_a_base_nueva_admite_estructura(conn):
    await _aplica(conn, SCHEMA_SQL)
    await _estructura(conn)
    assert [n for n, _ in await _checks_de_tipo(conn)] == ["bot_evento_tipo_check"]


async def test_b_actualizacion_desde_main_dos_veces(conn):
    await _aplica(conn, MAIN_SQL)
    for i, t in enumerate(VIEJOS):
        await conn.execute(INSERTA, t, "BTCUSDT" if t in ("rafaga", "clase") else None,
                           29_000_000 + i if t in ("rafaga", "clase") else None, None, None, True, f'{{"i": {i}}}')
    with pytest.raises(asyncpg.CheckViolationError):  # main: el INSERT del bot cae, como en 140
        await conn.execute(INSERTA, "estructura", None, None, None, None, False, "{}")
    antes = [tuple(f) for f in await conn.fetch("SELECT tipo, symbol, minuto, detalle FROM bot_evento ORDER BY tipo")]
    assert len(antes) == len(VIEJOS)

    primera = await _aplica(conn, SCHEMA_SQL)
    segunda = await _aplica(conn, SCHEMA_SQL)
    assert any("ADD CONSTRAINT bot_evento_tipo_check" in a for a in primera), primera
    assert not [a for a in segunda if "bot_evento" in a], segunda  # idempotente: la segunda no toca la tabla

    assert [tuple(f) for f in await conn.fetch("SELECT tipo, symbol, minuto, detalle FROM bot_evento ORDER BY tipo")] == antes
    await _estructura(conn)
    checks = await _checks_de_tipo(conn)
    assert [n for n, _ in checks] == ["bot_evento_tipo_check"] and "'estructura'::text" in checks[0][1]
    with pytest.raises(asyncpg.CheckViolationError):  # la lista sigue cerrada
        await conn.execute(INSERTA, "otro", None, None, None, None, False, "{}")


async def test_c_check_viejo_con_otro_nombre(conn):
    await _aplica(conn, MAIN_SQL)
    await conn.execute(INSERTA, "vigia", None, None, None, None, True, "{}")
    await conn.execute("ALTER TABLE bot_evento RENAME CONSTRAINT bot_evento_tipo_check TO bot_evento_tipo_viejo")
    await _aplica(conn, SCHEMA_SQL)
    await _aplica(conn, SCHEMA_SQL)
    await _estructura(conn)
    assert [n for n, _ in await _checks_de_tipo(conn)] == ["bot_evento_tipo_check"]
    assert await conn.fetchval("SELECT count(*) FROM bot_evento") == 2
