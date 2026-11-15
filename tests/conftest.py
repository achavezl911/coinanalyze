"""Lo comun de las bases de prueba (CI rapida, C1).

`plantilla_sql_ascii`: el esquema se carga UNA vez por sesion en una plantilla; cada prueba de
tests/test_bot.py que necesita una base SQL_ASCII se la copia con CREATE DATABASE ... TEMPLATE.
"""

from __future__ import annotations

import asyncio
import os
import urllib.parse
import uuid
from pathlib import Path

import asyncpg
import pytest


def _con_base(dsn: str, base: str) -> str:
    p = urllib.parse.urlsplit(dsn)  # a mano: urlunsplit se come el «//» vacio de postgresql:///db
    return f"{p.scheme}://{p.netloc}/{base}" + (f"?{p.query}" if p.query else "")


async def _borra(dsn: str, base: str) -> None:
    adm = await asyncpg.connect(_con_base(dsn, "postgres"))
    try:
        try:
            await adm.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')
        except asyncpg.InsufficientPrivilegeError:  # FORCE no puede echar a un autovacuum sin rol; el DROP a secas lo cancela solo
            await adm.execute(f'DROP DATABASE IF EXISTS "{base}"')
    finally:
        await adm.close()


@pytest.fixture(scope="session")
def plantilla_sql_ascii():
    """La plantilla de las bases SQL_ASCII de tests/test_bot.py (`base_ascii`): ENCODING 'SQL_ASCII'
    TEMPLATE template0, LC C, con sql/schema.sql entero, como la de 140. Se crea y se carga UNA vez
    por proceso; cada prueba se la copia con `CREATE DATABASE ... TEMPLATE` (la copia hereda la
    codificacion y el locale). Devuelve (dsn de la base de pruebas, nombre de la plantilla)."""
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    nombre = f"bot_sqlascii_tpl_{uuid.uuid4().hex[:10]}"
    esquema = (Path(__file__).resolve().parents[1] / "sql" / "schema.sql").read_text(encoding="utf-8")

    async def crea() -> bool:
        adm = await asyncpg.connect(dsn)
        try:
            await adm.execute(
                f"CREATE DATABASE {nombre} ENCODING 'SQL_ASCII' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C'"
            )
        except asyncpg.InsufficientPrivilegeError:
            return False
        finally:
            await adm.close()
        c = await asyncpg.connect(_con_base(dsn, nombre))
        try:
            await c.execute(esquema)
        finally:
            await c.close()
        return True

    if not asyncio.run(crea()):
        pytest.skip("el rol de las pruebas no puede crear bases")
    try:
        yield dsn, nombre
    finally:
        asyncio.run(_borra(dsn, nombre))
