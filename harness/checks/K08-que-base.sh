#!/bin/bash
# K08  la aplicacion tiene que saber -y decir- a que base se conecto. HOY LO SABE Y LO DICE,
# y este check existe para que siga siendo asi.
#
# POR QUE SE ESCRIBIO, y esto es historia y no se borra. Medido el 2026-08-25: app/db.py no
# mencionaba current_database() ni current_setting NI UNA VEZ, y /api/healthz no publicaba
# ninguna identidad de base. En create_pool lo PRIMERO que ocurria tras conectar era
# sync_market_catalog -que ESCRIBE en market_assets y symbols- y despues
# ensure_temporal_partitions -que crea particiones por DDL-: ninguna lectura de verificacion
# antes de escribir. O sea que un despliegue apuntando a la base equivocada no se distinguia
# de uno bueno: escribia igual, y encima escribia ANTES de que nadie pudiera mirar.
#
# MEDIDO EL 2026-09-09, cada afirmacion por la via que le toca:
#   1. el FICHERO: app/db.py:72-78 consulta current_database(), host(inet_server_addr()),
#      inet_server_port() y current_setting('server_version').
#   2. la RESPUESTA SERVIDA por 140 -no el fuente-: GET /api/healthz trae un bloque
#      `database` con SEIS campos. Van enumerados Y CONTADOS a proposito, y el numero es la
#      mitad que importa: hasta el 2026-09-11 esta linea enumeraba CINCO -se le habia quedado
#      fuera `schema_fingerprint`- y **el residuo fue invisible justamente por enumerar sin
#      decir cuantos**: un grep de «cinco|seis|N campos» sobre el arnes daba CERO, porque el
#      numero no estaba escrito en ninguna parte. Medido el 2026-09-11 contra la respuesta
#      servida, EN LAS DOS DIRECCIONES:
#        los SEIS que sirve:  database · db_user · db_host · db_port · server_version ·
#                             schema_fingerprint
#        enumerados aqui y NO servidos:  NINGUNO -conjunto vacio-
#      Que la direccion inversa este VACIA es la prueba de que aquello era una OMISION y no un
#      desajuste: no sobraba nada, faltaba uno.
# Las dos senales que este check exige estan, y por eso esta VERDE. La cabecera decia lo
# contrario en presente hasta hoy.
#
# Dos senales, y la segunda es la que importa de verdad:
#   1. app/db.py consulta la identidad de la base en algun sitio.
#   2. La identidad es OBSERVABLE DESDE FUERA. Que el codigo la consulte y se la
#      guarde no sirve de nada: si no sale por la API, nadie puede comprobar a que
#      base esta enganchado lo que corre. Esta es la que convierte K08 en verificable
#      sin leerse el arbol, y es la unica que sobrevive a un despliegue mal apuntado.
#
# El check NO exige que la huella coincida con nada: exige que EXISTA y se publique.
# Comparar contra lo esperado es el arreglo, no la medicion.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
API="$REPO/app/db.py"

[ -r "$API" ] || { echo "NO MEDIDO: no se puede leer app/db.py"; exit 2; }

fallos=""
[ "$(grep -c 'current_database()\|current_setting' "$API")" -ge 1 ] \
  || fallos="$fallos app/db.py no consulta nunca la identidad de la base"

# POR EL CANAL DE LA CASA, Y SIN TODO=1 A PROPOSITO. Aqui hubo un guardia que no podia
# dispararse, y merece quedar escrito porque el fallo era de forma y no de codigo:
#
#   el 2026-09-10 esto pedia CON `TODO=1` y ademas guardaba contra `[CORTADO:`. Las dos
#   mitades se cancelaban: `_corta` linea 4 es `[ "${TODO:-0}" = "1" ] && exec cat`, o sea que
#   con TODO=1 NO HAY CORTE NUNCA y la marca no puede aparecer. El comentario decia que era
#   «el mismo guardia de K05:138»: cierto del codigo y FALSO del patron, porque K05:127 pide
#   SIN TODO=1 y por eso el suyo si dispara. Proteccion simple mas adorno, no proteccion doble.
#
# Se elige dejar el guardia ALCANZABLE y no retirarlo, con la medida delante: healthz sirve
# 5237 B de los 8000 del techo -margen 2763 B, unos 7 servicios a 385 B cada uno-, asi que hoy
# el cuerpo llega entero igual. LO QUE CUESTA, dicho: el dia que healthz pase de 8000, este
# check dejara de medir y dira por que. Se acepta: un lector que sigue juzgando mientras el
# canal ya no puede llevar la carga no esta protegido, esta callado. Y K05 caeria a la vez, asi
# que la senal sale por dos sitios.
#
# NO se puede inducir bajando el techo: `_corta` sourcea harness/env ANTES de leer MAX_BYTES y
# env:20 lo fija en 8000, asi que `MAX_BYTES=100` desde fuera NO manda. El control lo induce
# por el unico camino que queda: un cuerpo mayor que el techo.
cuerpo=$("$B/bin/api" /api/healthz 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: /api/healthz no respondio"; exit 2; }
case "$cuerpo" in
  *"[CORTADO:"*)
    echo "NO MEDIDO: el transporte corto la respuesta de healthz. $(printf '%s' "$cuerpo" \
      | grep -o '\[CORTADO:[^]]*\]'). No es un healthz malo: es JSON partido, y juzgarlo\
 seria hacer depender el veredicto del transporte."
    exit 2 ;;
esac

publicada=$(printf '%s' "$cuerpo" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("nojson"); raise SystemExit(0)
marcas = ("database", "dbname", "db_host", "schema_fingerprint", "schema_hash", "pg_host")
def busca(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if any(m in k.lower() for m in marcas):
                return k
            r = busca(v)
            if r: return r
    elif isinstance(o, list):
        for x in o[:5]:
            r = busca(x)
            if r: return r
    return ""
print(busca(d) or "ausente")
' 2>/dev/null)

case "$publicada" in
  nojson)  echo "NO MEDIDO: healthz no devolvio JSON"; exit 2 ;;
  ausente) fallos="$fallos; la API no publica a que base esta conectada" ;;
esac

[ -z "${fallos# }" ] || { printf '%s\n' "${fallos#; }" | sed 's/^ //' | cut -c1-200; exit 1; }
echo "la base se verifica en db.py y se publica en la API (campo $publicada)"
