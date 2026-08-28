#!/bin/bash
# K66  UN HUECO DECLARADO SOBRE UN DATO QUE YA TENEMOS NO ES UN HUECO.
#
# Un hueco es un dato que NO TENEMOS. Que la fuente no lo mande en UNA pasada concreta es
# una propiedad de la RESPUESTA, no del dato: si ya esta guardado, no falta nada.
#
# MEDIDO EN 140 el 2026-08-28, y es lo que obliga a escribir este check. Los 17 huecos sin
# resolver salen de dos detectores, y no se parecen en nada:
#     historical_ingest_response_cadence_v2   8 filas · 8 buckets · 0 ya guardados
#     historical_resweep_cadence_v1           9 filas · 1325 buckets · 1312 YA GUARDADOS
# El detector vivo acierta el 100 %: sus 8 buckets faltan de verdad, y son 40 minutos en 11
# dias. El rebarrido se equivoca en el 99.0 %: de los 1325 buckets que declara ausentes,
# 1312 estan en long_short_ratio ahora mismo. Reclama 6625 minutos donde faltan 65.
# Por eso el orden esta invertido respecto del traspaso viejo: llamar al motor de
# recuperacion para 6625 minutos que en su mayoria no faltan es trabajar sobre una cifra
# falsa. Primero que la cifra sea verdad.
#
# LA CAUSA, LOCALIZADA Y NO RAZONADA. reconcile_cadence_coverage decide con lo que el
# llamante le pasa en `observations`, y su propio docstring dice que eso puede venir "from
# the current provider response OR from canonical persisted storage". El rebarrido solo le
# pasa lo PRIMERO -- lo que acepto en esa pasada --, nunca lo segundo. Si el proveedor
# contesta truncado, todo lo demas de la ventana le parece ausente aunque lo tengamos.
# NO es missing_cadence_windows: esa funcion rompe la racha en cuanto encuentra un bucket
# presente (data_gaps.py:392), asi que jamas cruza un hueco falso. La lei antes de acusarla.
# Y NO es falta de idempotencia en el INSERT: data_gaps.py:313 ya trae
# ON CONFLICT(...) DO UPDATE. Correr dos veces con las MISMAS ventanas no duplica; lo que
# duplica es que las ventanas cambien entre pasadas, y cambian porque dependen de una
# respuesta que varia. La idempotencia se arregla arreglando la ventana, no al reves.
#
# QUE EXIGE, INDUCIDO CONTRA EL ESPEJO Y DENTRO DE UNA TRANSACCION QUE SE REVIERTE:
#   1 · con el almacenamiento LLENO para la ventana y la fuente contestando truncado, el
#       rebarrido NO puede declarar ni un bucket ausente. Es el caso que produjo los 1312.
#   2 · CONTROL POSITIVO, obligatorio: un bucket que falta DE VERDAD -- ni en la respuesta
#       ni en el almacenamiento -- tiene que seguir declarandose. Un detector que no declara
#       nada esta tan roto como el que lo declara todo, y sin este brazo la forma mas facil
#       de poner el check en VERDE seria dejar de detectar.
#   3 · IDEMPOTENCIA: reconciliar DOS VECES la misma ventana no puede dejar mas filas que
#       una. Se corre el mismo escenario del brazo 2 por segunda vez y la cuenta no sube.
#
# NO TOCA 140 NI DEJA RASTRO EN EL ESPEJO: todo ocurre dentro de una transaccion que
# termina en ROLLBACK siempre, incluso si un assert falla. Las filas de data_gap del espejo
# se cuentan antes y despues para probarlo, y esa comprobacion es parte del veredicto.
#
# DE QUE ARBOL: codigo del repo de 143, base ESPEJO de 143. Produccion no se toca.
set -uo pipefail
B=/srv/coinanalyze/harness
REPO=/srv/coinanalyze/repo
. "$B/env"

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

cd "$REPO" || { echo "NO MEDIDO: no se pudo entrar en $REPO"; exit 2; }

ESPEJO_DB="$ESPEJO_DB" "$PY" - <<'PY'
import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "/srv/coinanalyze/repo")

try:
    import asyncpg
    from app.data_gaps import reconcile_cadence_coverage
    from scripts.resweep_cadence_gaps import (
        PLANS,
        RESWEEP_DETECTION_SOURCE,
        observaciones_conocidas,
    )
except ImportError as exc:
    print(f"NO MEDIDO: no se pudo importar el rebarrido ({exc})")
    sys.exit(2)
except Exception as exc:  # noqa: BLE001
    print(f"NO MEDIDO: fallo al importar ({type(exc).__name__}: {exc})")
    sys.exit(2)

PLAN = PLANS[("long_short_ratio", "5min")]
CADENCIA = PLAN.cadence
IDENT = {
    "feed": "long_short_ratio",
    "exchange": "K66",
    "market": "K66",
    "symbol": "K66_PERP.A",
    "granularity": "5min",
}
# Ventana de laboratorio, lejos de cualquier dato real y con identidad propia, para que
# nada de lo sembrado se pueda confundir con produccion aunque el rollback fallara.
INICIO = datetime(2020, 1, 1, tzinfo=UTC)
BUCKETS = 12
FIN = INICIO + CADENCIA * BUCKETS


async def siembra(conn, presentes):
    # long_short_ratio.symbol -> symbols.symbol -> market_assets.base_asset. La identidad
    # de laboratorio se siembra ENTERA dentro de la misma transaccion revertida, asi que
    # no queda nada en el espejo y no se reutiliza ningun simbolo real.
    await conn.execute(
        "INSERT INTO market_assets(base_asset) VALUES('K66') ON CONFLICT DO NOTHING"
    )
    await conn.execute(
        "INSERT INTO symbols(symbol,base_asset) VALUES($1,'K66') "
        "ON CONFLICT(symbol) DO NOTHING",
        IDENT["symbol"],
    )
    for ts in presentes:
        await conn.execute(
            """
            INSERT INTO long_short_ratio(ts,symbol,interval,long_pct,short_pct,ratio)
            VALUES($1,$2,'5min',50,50,1)
            ON CONFLICT(symbol,interval,ts) DO NOTHING
            """,
            ts, IDENT["symbol"],
        )


async def cuenta_huecos(conn):
    return await conn.fetchval(
        """
        SELECT count(*) FROM data_gap
        WHERE feed=$1 AND exchange=$2 AND symbol=$3
          AND detection_source=$4
        """,
        IDENT["feed"], IDENT["exchange"], IDENT["symbol"], RESWEEP_DETECTION_SOURCE,
    )


async def reconcilia(conn, aceptados, devueltos):
    conocidas = await observaciones_conocidas(
        conn, PLAN, IDENT, INICIO, FIN, set(aceptados)
    )
    await reconcile_cadence_coverage(
        conn,
        observations=conocidas,
        feed=IDENT["feed"], exchange=IDENT["exchange"], market=IDENT["market"],
        symbol=IDENT["symbol"], granularity=IDENT["granularity"],
        start=INICIO, end=FIN, cadence=CADENCIA,
        detection_source=RESWEEP_DETECTION_SOURCE,
        source_response_buckets=set(devueltos),
    )
    return len(conocidas)


class Revertir(Exception):
    """Se lanza SIEMPRE al final para que la transaccion no persista nada."""


async def principal():
    todos = [INICIO + CADENCIA * i for i in range(BUCKETS)]
    conn = await asyncpg.connect(
        database=os.environ["ESPEJO_DB"], host="/var/run/postgresql", user="root"
    )
    try:
        antes = await conn.fetchval("SELECT count(*) FROM data_gap")
        veredicto = None
        try:
            async with conn.transaction():
                # --- 1 · ALMACENAMIENTO LLENO, FUENTE TRUNCADA -------------------------
                # Es el caso que produjo los 1312: la fuente solo devuelve dos buckets y
                # todo lo demas de la ventana ya lo tenemos guardado.
                await siembra(conn, todos)
                devueltos = todos[:2]
                conocidas = await reconcilia(conn, aceptados=devueltos, devueltos=devueltos)
                falsos = await cuenta_huecos(conn)
                if falsos:
                    veredicto = (
                        1,
                        f"EL REBARRIDO DECLARA HUECO SOBRE DATO QUE YA TENEMOS: con los "
                        f"{BUCKETS} buckets de la ventana GUARDADOS y la fuente devolviendo "
                        f"solo {len(devueltos)}, crea {falsos} fila(s) de hueco. Solo "
                        f"considero presentes {conocidas} de {BUCKETS}: no mira el "
                        f"almacenamiento, solo la respuesta de la pasada. Es la forma exacta "
                        f"de los 1312 buckets falsos de 140"
                    )
                    raise Revertir

                # --- 2 · CONTROL POSITIVO: lo que falta DE VERDAD se sigue declarando ---
                await conn.execute(
                    "DELETE FROM long_short_ratio WHERE symbol=$1 AND ts=$2",
                    IDENT["symbol"], todos[5],
                )
                await reconcilia(conn, aceptados=devueltos, devueltos=todos)
                reales = await cuenta_huecos(conn)
                if reales != 1:
                    veredicto = (
                        1,
                        f"CONTROL POSITIVO ROTO: el bucket {todos[5]:%H:%M} no esta ni en la "
                        f"respuesta aceptada ni en el almacenamiento, y el rebarrido declara "
                        f"{reales} huecos en vez de 1. Un detector que no declara nada esta "
                        f"tan roto como el que lo declara todo"
                    )
                    raise Revertir

                # --- 3 · IDEMPOTENCIA: la segunda pasada no anade filas -----------------
                await reconcilia(conn, aceptados=devueltos, devueltos=todos)
                repetido = await cuenta_huecos(conn)
                if repetido != reales:
                    veredicto = (
                        1,
                        f"EL REBARRIDO NO ES IDEMPOTENTE: reconciliar la MISMA ventana dos "
                        f"veces pasa de {reales} a {repetido} filas",
                    )
                    raise Revertir

                veredicto = (
                    0,
                    f"un hueco declarado sobre dato que ya tenemos NO SE DECLARA: con los "
                    f"{BUCKETS} buckets guardados y la fuente devolviendo solo "
                    f"{len(devueltos)}, el rebarrido crea 0 huecos -- porque cuenta como "
                    f"presentes {conocidas} de {BUCKETS}, uniendo respuesta y "
                    f"almacenamiento. CONTROL POSITIVO: al borrar un bucket de verdad "
                    f"vuelve a declararlo, {reales} fila. IDEMPOTENTE: la segunda pasada "
                    f"sigue en {repetido}. Todo dentro de una transaccion revertida",
                )
                raise Revertir
        except Revertir:
            pass

        despues = await conn.fetchval("SELECT count(*) FROM data_gap")
        if despues != antes:
            print(
                f"NO MEDIDO: el laboratorio dejo rastro en el espejo ({antes} -> {despues} "
                f"filas en data_gap); el veredicto no es fiable"
            )
            return 2
        if veredicto is None:
            print("NO MEDIDO: el laboratorio no llego a emitir veredicto")
            return 2
        codigo, mensaje = veredicto
        print(mensaje)
        return codigo
    finally:
        await conn.close()


try:
    sys.exit(asyncio.run(principal()))
except asyncpg.PostgresError as exc:
    print(f"NO MEDIDO: el espejo no dejo correr el laboratorio ({type(exc).__name__}: {exc})")
    sys.exit(2)
except OSError as exc:
    print(f"NO MEDIDO: no se pudo conectar al espejo ({exc})")
    sys.exit(2)
PY
exit $?
