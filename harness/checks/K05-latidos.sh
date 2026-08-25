#!/bin/bash
# K05  /api/healthz tiene que vigilar TODAS las filas de pipeline_heartbeat.
#
# El fallo real NO era el parseo del check anterior. Es este: "services" en la
# respuesta es records(heartbeats) (app/api.py:2029), o sea un ECO de la tabla.
# Comparar la tabla contra "services" es una tautologia y nace VERDE siempre.
# Quien decide si un latido esta rancio es el dict thresholds (app/api.py:1992-2002):
# 7 claves = ingest, ws, scalp, daily, api, mas las 2 de INGEST_COMPONENT_MAX_AGES
# (app/db.py:14). required_heartbeat_failures (app/db.py:21-47) itera SOLO sobre
# esas 7, asi que una fila que no este ahi no puede poner degraded jamas.
#
# Prueba viva medida el 2026-08-25 contra 140: ws-binance y ws-bybit llevan
# 1303034 s (15.08 dias) sin latir, con status 'ok', y healthz nunca dijo nada.
# Se quedaron congeladas el 2026-08-09 19:00:59, que es cuando 5ed802f
# ("make collectors horizontally safe") renombro el servicio a ws-<ex>:<shard>/<n>.
#
# CRITERIO: la tabla tiene que estar contenida en el conjunto que healthz DECLARA
# vigilar. Mientras healthz no declare nada, no hay forma honrada de saber desde
# fuera que se vigila, y eso ya es el fallo.
#
# Salida 2 = NO MEDIDO, solo si el canal no responde. Que FALTE el campo no es
# NOMED: el canal contesta perfectamente, lo que falta es la respuesta. Eso es ROJO.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"

tabla=$("$B/bin/prodsql" "SELECT service FROM pipeline_heartbeat ORDER BY 1" 2>/dev/null \
        | tr -d ' ' | grep -E '^[a-z][a-z0-9_:/.-]*$' | sort -u)
[ -n "$tabla" ] || { echo "NO MEDIDO: prodsql no devolvio servicios"; exit 2; }

veredicto=$("$B/bin/api" /api/healthz 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("NOMED json ilegible"); raise SystemExit(0)
if not isinstance(d, dict) or "status" not in d:
    print("NOMED respuesta sin status"); raise SystemExit(0)
g = d.get("governed_services")
if g is None:
    print("SINCAMPO"); raise SystemExit(0)
try:
    nombres = {x["service"] if isinstance(x, dict) else str(x) for x in g}
except Exception:
    print("SINCAMPO"); raise SystemExit(0)
print("VIGILA " + " ".join(sorted(n for n in nombres if n)))
' 2>/dev/null)

case "$veredicto" in
  NOMED*)    echo "NO MEDIDO: ${veredicto#NOMED }"; exit 2 ;;
  SINCAMPO)  echo "healthz no declara que vigila: sin campo governed_services. $(printf '%s\n' "$tabla" | wc -l) latidos en la tabla, 7 con umbral en api.py:1992-2002"; exit 1 ;;
  VIGILA*)   ;;
  *)         echo "NO MEDIDO: /api/healthz no respondio"; exit 2 ;;
esac

vigilados=$(printf '%s\n' "${veredicto#VIGILA }" | tr ' ' '\n' | grep -v '^$' | sort -u)
falta=$(comm -23 <(printf '%s\n' "$tabla") <(printf '%s\n' "$vigilados") | tr '\n' ' ')
[ -z "${falta// /}" ] || { echo "sin vigilar: $falta"; exit 1; }
echo "$(printf '%s\n' "$tabla" | wc -l) latidos, todos vigilados"
