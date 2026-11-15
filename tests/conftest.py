"""La base de las pruebas en paralelo (CI rapida, C1 y C2).

`TEST_DATABASE_URL` apunta a una base con sql/schema.sql YA cargado (el paso «Create disposable test
database» de ci.yml lo carga UNA vez por corrida). En serie se usa tal cual, como siempre.

Con pytest-xdist (`-n N`) cada proceso `gwK` copia esa base con `CREATE DATABASE <base>_gwK TEMPLATE
<base>` -una copia de ficheros, el esquema no se vuelve a ejecutar- y reescribe `TEST_DATABASE_URL`
antes de recoger las pruebas: los `_dsn()` de cada fichero y los subprocesos que la heredan van a la
copia del proceso. Por que una base por proceso y no la compartida: los candados consultivos
(pg_advisory_lock de los tests de takeover) y lo que una prueba escribe en `public` son de la BASE;
dos procesos sobre la misma se pisarian. La copia se borra al acabar el proceso.

La base de origen no puede tener a NADIE conectado mientras se copia (Postgres lo exige): por eso la
copia se hace aqui, antes de la primera prueba, y el proceso coordinador no abre ninguna conexion.
"""

from __future__ import annotations

import asyncio
import os
import re
import urllib.parse
import uuid
from pathlib import Path

import asyncpg
import pytest

_CLONADA: dict[str, str] = {}


def _con_base(dsn: str, base: str) -> str:
    p = urllib.parse.urlsplit(dsn)  # a mano: urlunsplit se come el «//» vacio de postgresql:///db
    return f"{p.scheme}://{p.netloc}/{base}" + (f"?{p.query}" if p.query else "")


async def _copia(dsn: str, origen: str, destino: str) -> None:
    adm = await asyncpg.connect(_con_base(dsn, "postgres"))
    try:
        await adm.execute(f'DROP DATABASE IF EXISTS "{destino}" WITH (FORCE)')
        for intento in range(30):  # otro proceso copiando a la vez tiene la plantilla un instante
            try:
                await adm.execute(f'CREATE DATABASE "{destino}" TEMPLATE "{origen}"')
                return
            except asyncpg.ObjectInUseError:
                if intento == 29:
                    raise
                await asyncio.sleep(0.5)
    finally:
        await adm.close()


async def _borra(dsn: str, base: str) -> None:
    adm = await asyncpg.connect(_con_base(dsn, "postgres"))
    try:
        try:
            await adm.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')
        except asyncpg.InsufficientPrivilegeError:  # FORCE no puede echar a un autovacuum sin rol; el DROP a secas lo cancela solo
            await adm.execute(f'DROP DATABASE IF EXISTS "{base}"')
    finally:
        await adm.close()


def pytest_configure(config: pytest.Config) -> None:
    proceso = os.environ.get("PYTEST_XDIST_WORKER")
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not proceso or not dsn:
        return
    origen = urllib.parse.urlsplit(dsn).path.lstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]+", origen) or not re.fullmatch(r"gw[0-9]+", proceso):
        raise pytest.UsageError(f"TEST_DATABASE_URL con un nombre de base que no se copia: {origen!r}")
    destino = f"{origen}_{proceso}"
    asyncio.run(_copia(dsn, origen, destino))
    _CLONADA["origen"], _CLONADA["destino"] = dsn, destino
    os.environ["TEST_DATABASE_URL"] = _con_base(dsn, destino)


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


def pytest_unconfigure(config: pytest.Config) -> None:
    if _CLONADA:
        asyncio.run(_borra(_CLONADA["origen"], _CLONADA["destino"]))
        os.environ["TEST_DATABASE_URL"] = _CLONADA.pop("origen")
        _CLONADA.clear()
