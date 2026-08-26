#!/bin/bash
# K13  vacio y rancio no se pueden ver igual. /api/scalp/orderbook filtra
# ts >= now()-30s (app/api.py:1403-1416): cuando el libro se queda viejo la consulta
# devuelve CERO filas y la respuesta es {"rows": [], "symbol": ...}, que es
# indistinguible de "no hay datos". El operador ve una tabla vacia en los dos casos.
#
# Medido el 2026-08-25 con el libro fresco: la respuesta trae exactamente dos claves,
# rows y symbol. Ni edad, ni as_of, ni estado.
#
# LA SENYAL TIENE QUE IR FUERA DE rows, y este es el punto entero de la unidad: con
# cero filas no queda NADA de donde inferir la edad. Un ts por fila no sirve, porque
# el caso que hay que distinguir es justo aquel en el que no hay filas. Por eso el
# check exige la marca en el nivel de arriba y no acepta que este dentro de rows.
#
# TRES DIENTES, y los dos ultimos son de 2026-08-26, apretados ANTES de tocar codigo
# porque con solo el primero bastaba una clave puesta de adorno:
#   1  hay una marca de frescura en el nivel de arriba
#   2  dice el ESTADO y dice la EDAD. Estado de un vocabulario cerrado -fresh, stale,
#      empty- porque son TRES casos y no dos: "no hay libro" y "el libro es viejo" son
#      hechos distintos y el que decide es el que mira. La edad vale como age_seconds
#      o como as_of; sin una de las dos, "stale" no dice cuanto
#   3  el estado CUADRA con rows. Con filas tiene que decir fresh, y sin filas no
#      puede decir fresh. Sin este diente, devolver "fresh" siempre pasaria el check
#      sin haber mirado el reloj
#
# No hace falta esperar a que el libro se ponga rancio para medir esto: si la clave
# no existe estando fresco, tampoco existira estando viejo.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
SIM=${K13_SIMBOLO:-BTCUSDT_PERP.A}

cuerpo=$(curl -sS -k --netrc-file "$NETRC" --max-time 20 "$API_PROD/api/scalp/orderbook?symbol=$SIM" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: /api/scalp/orderbook no respondio"; exit 2; }

veredicto=$(printf '%s' "$cuerpo" | python3 -c '
import sys, json

ESTADOS = ("fresh", "stale", "empty")
MARCAS = ("age_seconds", "lag_seconds", "as_of", "observed_at", "stale", "freshness", "status")

try:
    d = json.load(sys.stdin)
except Exception:
    print("NOMED json ilegible"); raise SystemExit(0)
if not isinstance(d, dict):
    print("NOMED la respuesta no es un objeto"); raise SystemExit(0)

filas = d.get("rows")
n = len(filas) if isinstance(filas, list) else -1
if n < 0:
    print("NOMED la respuesta no trae rows"); raise SystemExit(0)

# Las marcas del nivel de arriba. Si una de ellas es un objeto, sus claves cuentan como
# del nivel de arriba: lo que no vale es que la frescura viva DENTRO de rows.
marcadas = {k: v for k, v in d.items() if any(m in k.lower() for m in MARCAS)}
if not marcadas:
    print("FALTA claves=%s filas=%d" % (",".join(sorted(d)), n)); raise SystemExit(0)

plano = {}
for k, v in marcadas.items():
    if isinstance(v, dict):
        for k2, v2 in v.items():
            plano[k2.lower()] = v2
    else:
        plano[k.lower()] = v

estado = next((v for k, v in plano.items() if k in ("status", "state", "estado")), None)
edad = next((v for k, v in plano.items()
             if ("age" in k or "lag" in k) and isinstance(v, (int, float))), None)
sello = next((v for k, v in plano.items()
              if k in ("as_of", "observed_at") and isinstance(v, str)), None)

faltan = []
if estado not in ESTADOS:
    faltan.append("estado=%r no es uno de %s" % (estado, "/".join(ESTADOS)))
if edad is None and sello is None:
    faltan.append("sin age_seconds ni as_of")
if not faltan:
    if n > 0 and estado != "fresh":
        faltan.append("%d filas y dice %s" % (n, estado))
    if n == 0 and estado == "fresh":
        faltan.append("cero filas y dice fresh")
if faltan:
    print("FALTA %s (marcas=%s filas=%d)" % ("; ".join(faltan), ",".join(sorted(marcadas)), n))
    raise SystemExit(0)
print("OK estado=%s filas=%d edad=%s as_of=%s" % (estado, n, edad, sello))
' 2>/dev/null)

case "$veredicto" in
  NOMED*) echo "NO MEDIDO: ${veredicto#NOMED }"; exit 2 ;;
  FALTA*)
    echo "/api/scalp/orderbook no distingue vacio de rancio: ${veredicto#FALTA }"; exit 1 ;;
  OK*)
    echo "/api/scalp/orderbook declara frescura: ${veredicto#OK }"; exit 0 ;;
  *) echo "NO MEDIDO: sin veredicto"; exit 2 ;;
esac
