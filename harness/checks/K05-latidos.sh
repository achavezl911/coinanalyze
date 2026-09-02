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
# CRITERIO 1 (COBERTURA, el de siempre): la tabla tiene que estar contenida en el
# conjunto que healthz DECLARA vigilar. Mientras healthz no declare nada, no hay forma
# honrada de saber desde fuera que se vigila, y eso ya es el fallo.
#
# CRITERIO 2 (ESTADO), anadido el 2026-09-02 Y NO SUSTITUYE AL 1: ROJO si algun servicio
# GOBERNADO publica status distinto de ok, con su detail LITERAL en el mensaje.
#
# POR QUE HIZO FALTA, y es la clase de fallo que este arnes existe para no repetir: el
# 2026-09-02, de 14:40Z a 15:11Z, produccion perdio Binance -el venue principal- durante 31
# minutos en un bucle de reconexion (35 disconnected contra 2 connected, backoff de 1 a
# 60 s), con la tabla de trades a CERO mientras bybit seguia a 36/min. EL ARNES DIO CERO
# ROJO. K05 era el UNICO check que toca la palabra degraded y solo comprobaba que la CLAVE
# status EXISTIERA: nunca leia su VALOR. El colector SI lo ve -ws_collector.py:552, age >
# 90 s sobre eventos de mercado- y nadie consumia ese juicio.
#
# LECCION DE METODO QUE VA AQUI PORQUE AQUI SE PAGO: yo mire healthz a las 14:56Z, vi
# "ws-binance ok, last_event=28s" y escribi que se habia recuperado. Era UNA CONEXION QUE
# DURO 45 SEGUNDOS dentro del bucle. Una MUESTRA no es un ESTADO. Por eso el control
# positivo de este check es una SERIE -harness/bin/capta-healthz, una linea por minuto- y
# no un fixture: K05_CAPTURA=<fichero> re-juega el criterio contra un minuto guardado.
#
# Salida 2 = NO MEDIDO, solo si el canal no responde. Que FALTE el campo no es
# NOMED: el canal contesta perfectamente, lo que falta es la respuesta. Eso es ROJO.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"

tabla=$("$B/bin/prodsql" "SELECT service FROM pipeline_heartbeat ORDER BY 1" 2>/dev/null \
        | tr -d ' ' | grep -E '^[a-z][a-z0-9_:/.-]*$' | sort -u)
[ -n "$tabla" ] || { echo "NO MEDIDO: prodsql no devolvio servicios"; exit 2; }

# K05_CAPTURA re-juega el criterio contra un minuto GUARDADO por bin/capta-healthz, que es
# el control positivo real. Acepta la linea entera {"t":...,"h":{...}} o el healthz suelto.
# La TABLA sigue viniendo de prodsql: la captura solo guarda healthz, y eso va dicho.
if [ -n "${K05_CAPTURA:-}" ]; then
  [ -r "$K05_CAPTURA" ] || { echo "NO MEDIDO: no se puede leer la captura $K05_CAPTURA"; exit 2; }
  cuerpo=$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1]))
print(json.dumps(d.get("h", d)))' "$K05_CAPTURA" 2>/dev/null)
else
  cuerpo=$("$B/bin/api" /api/healthz 2>/dev/null)
fi

veredicto=$(printf '%s' "$cuerpo" | python3 -c '
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
malos = []
for s in d.get("services") or []:
    if not isinstance(s, dict):
        continue
    nombre = str(s.get("service") or "")
    # SOLO LOS GOBERNADOS: un latido que healthz no declara vigilar ya lo caza el
    # criterio 1, y contarlo aqui seria juzgar dos veces la misma falta.
    estado = str(s.get("status") or "")
    if nombre in nombres and estado != "ok":
        det = str(s.get("detail") or "sin detail").replace("\n", " ")
        # EL DETAIL SE ACOTA A 110 Y LOS NOMBRES VAN PRIMERO, y no es cosmetica: el detail
        # de scalp pasa de 300 caracteres y en la primera version se comia el corte de la
        # linea dejando fuera a ws-binance, que era EL servicio que habia que ver. Un
        # mensaje que esconde al culpable detras del mas hablador no sirve de nada.
        malos.append((nombre, estado, det[:110]))
print("VIGILA " + " ".join(sorted(n for n in nombres if n)))
print("MALOS " + ", ".join(n + "=" + e for n, e, _ in sorted(malos)))
print("DETALLE " + " · ".join(n + ": " + d for n, _, d in sorted(malos)))
' 2>/dev/null)

case "$veredicto" in
  NOMED*)    echo "NO MEDIDO: ${veredicto#NOMED }"; exit 2 ;;
  SINCAMPO)  echo "healthz no declara que vigila: sin campo governed_services. $(printf '%s\n' "$tabla" | wc -l) latidos en la tabla, 7 con umbral en api.py:1992-2002"; exit 1 ;;
  VIGILA*)   ;;
  *)         echo "NO MEDIDO: /api/healthz no respondio"; exit 2 ;;
esac

vigilados=$(printf '%s\n' "$veredicto" | sed -n 's/^VIGILA //p' | tr ' ' '\n' | grep -v '^$' | sort -u)
malos=$(printf '%s\n' "$veredicto" | sed -n 's/^MALOS //p')
detalle=$(printf '%s\n' "$veredicto" | sed -n 's/^DETALLE //p')
falta=$(comm -23 <(printf '%s\n' "$tabla") <(printf '%s\n' "$vigilados") | tr '\n' ' ')

# LOS DOS CRITERIOS SE SUMAN, NO SE SUSTITUYEN, y si fallan los dos se dicen los dos: son
# faltas distintas -no vigilar algo, y vigilarlo y callarse lo que dice-.
fallos=""
[ -z "${falta// /}" ] || fallos="sin vigilar: $falta"
[ -z "$malos" ] || fallos="${fallos:+$fallos · }servicios gobernados que NO publican ok: $malos · detalle literal: $detalle"
[ -z "$fallos" ] || { printf '%s\n' "$fallos" | cut -c1-700; exit 1; }

echo "$(printf '%s\n' "$tabla" | wc -l) latidos, todos vigilados y TODOS publicando ok"
