#!/bin/bash
# K77  EL POOL NO PUEDE BORRAR SU PROPIA CONFIGURACION.
#
# POR QUE EXISTE. K76 arreglo tres ::date crudos que leian la fecha en la zona de la sesion.
# La ATRIBUCION que acompano a ese arreglo era falsa -culpaba a app/db.py:151, que es la
# conexion de CERROJO y la API no la usa- y la causa verdadera sigue viva y es mas ancha.
#
# EL MECANISMO, medido en el espejo de 143 el 2026-08-31 y no deducido del codigo:
#   app/db.py:95-100  init_connection pone CINCO cosas con SET/set_config: zona UTC,
#     statement_timeout 20s, lock_timeout 3s, idle_in_transaction 30s y application_name.
#   app/db.py:102-110 asyncpg.create_pool(... init=init_connection) va SIN server_settings.
#   asyncpg 0.31.0 (repo/.venv/lib/python3.13/site-packages/asyncpg):
#     connection.py:1746-1754  arma la consulta de reset y mete RESET ALL;
#     pool.py:239              la ejecuta al DEVOLVER la conexion al pool (release)
#     pool.py:558-560          init corre SOLO en _get_new_connection: UNA vez por conexion
#     pool.py:174-176          setup SI correria en cada acquire -- y db.py no pasa setup=
#   Un pool identico al de hoy, con las dos adquisiciones seguidas:
#     1a (init recien corrido, sin release)  UTC · 20s · 3s · 30s · coinalyze-k77
#     2a (despues de UN release)             America/Mexico_City · 0 · 0 · 0 · ''
#   O sea: init SI corre. RESET ALL se lo lleva entero en cada devolucion, y el default del
#   servidor de 140 es America/Mexico_City (pg_db_role_setting tiene 0 filas: no hay ajuste
#   por rol ni por base que lo tape).
#   ESA CIFRA SE CITA DEL FICHERO Y YA NO DE pg_settings, y el motivo importa: hasta el
#   2026-08-31 se leia con prodsql como reset_val=America/Mexico_City source=configuration
#   file, pero desde que prodsql lleva -c timezone=UTC en su PGOPTIONS su propia sesion
#   tapa ese valor (pasa a reset_val=UTC source=client). El comando que SI se reproduce:
#     prod "grep -rn '^timezone' /etc/postgresql/17/main/postgresql.conf"
#       -> 743:timezone = 'America/Mexico_City'
#   Y NO vale sustituirlo por boot_val, que es GMT: el boot_val es el default COMPILADO,
#   no el del servidor.
#
# LO QUE SE PIERDE ES MAS QUE LA ZONA, y es lo que sube esto por delante del coste:
#     pide                            recibe (boot_val del servidor)
#     statement_timeout 20s   ....... 0  = SIN LIMITE
#     lock_timeout 3s         ....... 0  = SIN LIMITE
#     idle_in_transaction 30s ....... 0  = SIN LIMITE
# La app cree que tiene tres frenos y no tiene ninguno. Y ademas INVIERTE la lectura del
# codigo: quien abra db.py a preguntar en que zona corre la API lee SET TIME ZONE 'UTC' y
# concluye lo contrario de lo que pasa.
#
# AVISO DE INSTRUMENTO, que es como se mide esto mal. En una sesion de prodsql
# statement_timeout sale 60000 con source=client, y TimeZone sale UTC con source=client:
# los dos son el PGOPTIONS del propio prodsql, no lo que ve la app. El numero que hereda una
# conexion del pool tras RESET ALL es su PROPIO reset_val, que sin opciones de arranque es
# el boot_val (0 para los timeouts). Por eso el brazo B no pregunta por pg_settings: abre
# una conexion POR EL CAMINO DE LA APP y lee desde dentro.
# Y ESE MISMO ESTORBO ES EL CONTROL POSITIVO DEL MECANISMO DEL ARREGLO, que es lo que cierra
# el unico paso inferencial del brazo A -pg_stat_activity no lleva GUCs, asi que A ve el
# NOMBRE y no la zona-: statement_timeout sale reset_val=60000 con boot_val=0, y TimeZone
# reset_val=UTC con boot_val=GMT. Que el reset_val NO sea el boot_val demuestra EN 140 que
# un valor del paquete de arranque se convierte en el reset_val de la sesion, que es
# exactamente lo que sobrevive a un RESET ALL. Son dos instancias vivas del mecanismo.
#
# DONDE SE PONE LA MEDICION, que es lo unico no obvio. Hay una ventana en la que una
# conexion SI conserva lo que init le puso: entre init y su primer release. Esa ventana NO
# dura hasta el primer uso de la app -- se cierra DENTRO de create_pool, porque db.py:111-114
# llama a sync_market_catalog y a ensure_temporal_partitions y las dos adquieren y sueltan.
# Medido: con el create_pool de la app, YA LA PRIMERA adquisicion del llamante sale limpia.
# Un check que midiera sobre una conexion recien creada saldria VERDE con el fallo puesto.
# Por eso el brazo B mide en la SEGUNDA adquisicion, despues de un release comprobado.
#
# LOS TRES BRAZOS. Cada uno pone ROJO por separado y ninguno sobra:
#   A · 140, LO OBSERVABLE. Ninguna conexion agrupada puede tener application_name vacio.
#       No se puede leer la zona de otro backend desde fuera -- pg_stat_activity no lleva
#       GUCs --, pero application_name viaja por el MISMO camino que la zona y los timeouts,
#       asi que un nombre vacio es la huella de que el RESET ALL paso por encima. Es el unico
#       brazo que gatea sobre PRODUCCION, y es el que decide el VERDE de verdad.
#       CONTROL POSITIVO, y viene gratis en los mismos datos: las conexiones coinalyze-lock-*
#       SI conservan su nombre, porque el suyo viaja en el paquete de arranque (db.py:151,
#       server_settings). Dos mecanismos, dos resultados, en la misma consulta. Si NO se ve
#       ni un cerrojo, el instrumento no ha demostrado que sepa leer nombres: NOMED, no ROJO.
#       IDENTIFICADOR: "ni cerrojo, ni yo". NO se usa la huella de la consulta de reset, y
#       eso es medido: a las 19:1xZ solo 5 de las 10 agrupadas la mostraban -- las otras 5
#       estaban sirviendo --, y 40 s despues la mostraban las 10. Un identificador que
#       parpadea con el trafico convierte el conteo en ruido.
#   B · ESPEJO, EL COMPORTAMIENTO. Por el create_pool DE LA APP, tras un release, la conexion
#       tiene que dar UTC y 20s/3s/30s. Es el unico brazo que ve los VALORES; A solo ve la
#       huella. Va contra el espejo porque create_pool ESCRIBE -- market_assets, symbols y DDL
#       de particiones --, y contra 140 eso no se hace. El check se niega a correrlo si la
#       base no se llama *espejo*.
#   C · CONTROL NEGATIVO DEL INSTRUMENTO. Un pool construido COMO HOY (init= y nada mas)
#       tiene que PERDER la configuracion en el espejo. Sin este brazo, B se pondria VERDE
#       solo con que alguien pusiera el postgresql.conf del espejo en UTC, y el check pasaria
#       a presumir de un arreglo que no ha probado. Que B sea informativo es una propiedad
#       del banco de pruebas, no del codigo, y hay que volver a medirla en cada pasada.
#
# EL ARREGLO NO ES MOVER EL SET DE SITIO. Las dos vias que sobreviven a RESET ALL son
# server_settings -- viaja en el paquete de arranque, es lo que ya hace el cerrojo -- o
# ALTER ROLE/ALTER DATABASE, que es PUERTA 1 por tocar la base viva. Medido en el espejo: la
# primera basta, y por eso la segunda no se pide.
#
# DE QUE ARBOL: el brazo A mide 140 por prodsql. Los brazos B y C corren el codigo del REPO
# de 143 contra el ESPEJO de 143. El VERDE completo exige los tres.
#
# Se comprueba con: bash harness/checks/K77-el-pool-borra-su-configuracion.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"

# ---------------------------------------------------------------- BRAZO A · 140
SALIDA=$("$B/bin/prodsql" "
  SELECT
    count(*) FILTER (WHERE application_name = '')                              AS sin_nombre,
    count(*) FILTER (WHERE application_name LIKE 'coinalyze-lock-%')           AS cerrojos,
    count(*) FILTER (WHERE application_name LIKE 'coinalyze-%'
                       AND application_name NOT LIKE 'coinalyze-lock-%')       AS agrupadas_ok,
    count(*) FILTER (WHERE application_name <> ''
                       AND application_name NOT LIKE 'coinalyze-%')            AS ajenas
  FROM pg_stat_activity
  WHERE backend_type = 'client backend'
    AND pid <> pg_backend_pid()
    AND datname = current_database()
" 2>/dev/null | tr -d ' ' | head -1)

case "$SALIDA" in
  [0-9]*\|[0-9]*\|[0-9]*\|[0-9]*) : ;;
  *) echo "NO MEDIDO: 140 no contesto a pg_stat_activity: $(printf '%s' "$SALIDA" | head -c 120)"; exit 2 ;;
esac
IFS='|' read -r SIN_NOMBRE CERROJOS AGRUPADAS_OK AJENAS <<EOF
$SALIDA
EOF

# El control positivo va ANTES del veredicto: sin un solo cerrojo con nombre, esta sonda no
# ha demostrado que sepa distinguir un nombre puesto de un nombre borrado.
[ "$CERROJOS" -gt 0 ] || {
  echo "NO MEDIDO: 0 conexiones coinalyze-lock-* en 140. Sin el control positivo, un nombre vacio no prueba nada: la sonda no ha demostrado que sepa leer nombres"
  exit 2
}
# Y el caso vacio: cero conexiones agrupadas es cero filas medidas, no una buena noticia.
[ "$((SIN_NOMBRE + AGRUPADAS_OK))" -gt 0 ] || {
  echo "NO MEDIDO: 0 conexiones agrupadas en 140 (solo $CERROJOS cerrojos y $AJENAS ajenas). Un check sobre cero filas no ha comprobado nada"
  exit 2
}

# ------------------------------------------------------- BRAZOS B y C · espejo de 143
DB="${ESPEJO_DB:-coinalyze_espejo}"
case "$DB" in
  *espejo*) : ;;
  *) echo "NO MEDIDO: ESPEJO_DB='$DB' no parece el espejo. create_pool ESCRIBE (market_assets, symbols y DDL de particiones) y no se apunta a 140"; exit 2 ;;
esac

ESPEJO=$(cd "$REPO" && PYTHONPATH="$REPO" PG_HOST=/var/run/postgresql PG_USER=root PG_DB="$DB" \
  timeout 120 ./.venv/bin/python - <<'PY' 2>&1
import asyncio, asyncpg, sys
from app.config import Settings
from app.db import create_pool

ESPERADO = {
    "TimeZone": "UTC",
    "statement_timeout": "20s",
    "lock_timeout": "3s",
    "idle_in_transaction_session_timeout": "30s",
}

async def leer(c):
    return {g: await c.fetchval("SELECT current_setting($1)", g) for g in ESPERADO}

async def main():
    fallos = []

    # BRAZO C · el control negativo, PRIMERO: si el banco de pruebas no puede perder la
    # configuracion, el brazo B no informa de nada aunque salga VERDE.
    async def init_como_hoy(conn):
        await conn.execute("SET TIME ZONE 'UTC'")
        await conn.execute("SET statement_timeout = '20s'")
        await conn.execute("SET lock_timeout = '3s'")
        await conn.execute("SET idle_in_transaction_session_timeout = '30s'")

    s = Settings()
    roto = await asyncpg.create_pool(dsn=s.pg_dsn, min_size=1, max_size=1, init=init_como_hoy)
    async with roto.acquire() as c:
        antes = await leer(c)
    async with roto.acquire() as c:
        despues = await leer(c)
    await roto.close()
    if antes != ESPERADO:
        print(f"NOMED|el control negativo no llego a poner la configuracion: {antes}")
        return 2
    if despues == ESPERADO:
        print(f"NOMED|CONTROL NEGATIVO ROTO: un pool construido COMO HOY (init= y nada mas) "
              f"CONSERVA {despues} tras un release en el espejo. O asyncpg dejo de hacer "
              f"RESET ALL, o el default del espejo ya es lo que pedimos. En cualquiera de los "
              f"dos casos el brazo B no prueba el arreglo: no puede fallar")
        return 2

    # BRAZO B · el codigo de la app, y se mide en la SEGUNDA adquisicion.
    pool = await create_pool(s, application_name="coinalyze-k77")
    async with pool.acquire() as c:
        primera = await leer(c)
    async with pool.acquire() as c:
        segunda = await leer(c)
    await pool.close()

    if segunda != ESPERADO:
        malas = " · ".join(f"{k}: pide {v} y tiene {segunda[k]}"
                           for k, v in ESPERADO.items() if segunda[k] != v)
        fallos.append(f"el pool de la app pierde su configuracion al devolver la conexion -- {malas}")

    if fallos:
        print("ROJO|" + " · ".join(fallos))
        return 1
    # La ventana se declara aunque no se juzgue: dice DONDE se mide y por que.
    igual = "igual que la 2a" if primera == segunda else f"DISTINTA de la 2a ({primera})"
    print(f"VERDE|el pool de la app conserva UTC y 20s/3s/30s tras un release, y el control "
          f"negativo confirma que en este espejo se pierden ({despues['TimeZone']}, "
          f"{despues['statement_timeout']}/{despues['lock_timeout']}/"
          f"{despues['idle_in_transaction_session_timeout']}). 1a adquisicion {igual}")
    return 0

sys.exit(asyncio.run(main()))
PY
)
RC_ESPEJO=$?
# El veredicto se lee del PREFIJO, no del codigo de salida: una excepcion tambien sale con 1,
# y confundirla con un ROJO medido es publicar como fallo del sistema un fallo de la sonda.
LINEA=$(printf '%s\n' "$ESPEJO" | grep -m1 -E '^(VERDE|ROJO|NOMED)\|')
[ -n "$LINEA" ] || {
  echo "NO MEDIDO: la sonda del espejo no llego a dar veredicto (salida $RC_ESPEJO): $(printf '%s' "$ESPEJO" | tail -c 200)"
  exit 2
}
VEREDICTO=${LINEA%%|*}
DETALLE=${LINEA#*|}
[ "$VEREDICTO" = NOMED ] && { echo "NO MEDIDO: $DETALLE"; exit 2; }

# ---------------------------------------------------------------- VEREDICTO
# El ROJO dice CUAL de las dos cosas falta. Con el arbol ya arreglado y 140 todavia no, la
# lectura facil es "el arreglo no funciono", y lo que pasa es que no se ha desplegado.
FALLOS=""
[ "$SIN_NOMBRE" -gt 0 ] && FALLOS="140: $SIN_NOMBRE de $((SIN_NOMBRE + AGRUPADAS_OK)) conexiones agrupadas con application_name VACIO -- el RESET ALL del release les borro tambien la zona y los tres timeouts -- mientras los $CERROJOS cerrojos conservan el suyo$([ "$VEREDICTO" = VERDE ] && printf '%s' ' (el arbol YA lo tiene arreglado: el brazo del espejo pasa. Falta DESPLEGAR)')"
[ "$VEREDICTO" = ROJO ] && FALLOS="${FALLOS:+$FALLOS · }espejo: $DETALLE"

if [ -n "$FALLOS" ]; then
  echo "$FALLOS"
  exit 1
fi

echo "las $AGRUPADAS_OK conexiones agrupadas de 140 conservan su application_name igual que los $CERROJOS cerrojos ($AJENAS ajenas, no juzgadas), y en el espejo $DETALLE"
