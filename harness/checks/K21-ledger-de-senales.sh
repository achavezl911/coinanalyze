#!/bin/bash
# K21  signal_observation es el LEDGER de senales: 102180 filas en 140, un productor
# que lleva meses escribiendo y CERO API. La capacidad existe en la base y no existe
# para nadie que no tenga un psql.
#
# El VERDE son DOS cosas, y la segunda es la que cuesta: que el endpoint responda, y
# que lo que devuelve sea CORRECTO. "200 con filas > 0" no basta: un endpoint que
# devuelva las filas equivocadas, o la mitad de ellas, tambien responde 200.
#
# COMO SE EVITA PREGUNTARLE AL ACUSADO
# El SQL de referencia de este check NO es la consulta del endpoint. Se escribe desde
# lo que el ledger DEBE contener -las columnas de signal_observation en sql/schema.sql-
# y se compara contra cifras RECALCULADAS desde el JSON que sirve la ruta. Si el check
# corriera la consulta del endpoint contra la base y la comparara con su propia salida,
# lo unico demostrado seria que asyncpg y FastAPI funcionan. Es el agujero que tuvo K05.
#
# EL RELOJ
# El endpoint pega a 140, que esta VIVO: si la ventana llega hasta now(), entre la
# consulta de referencia y la llamada HTTP entran filas nuevas y el check falla por
# motivos que no son correccion. Por eso la ventana es una hora YA CERRADA y con al
# menos una hora de margen por detras. La misma ventana, al segundo, va a las dos vias.
#
# EL CORTE DE SALIDA
# Una hora de un simbolo son ~75-160 observaciones y no caben en los 8 KB de bin/api.
# Va con TODO=1 y el motivo escrito al lado, como en K42: lo que se verifica es que
# estan TODAS las filas, asi que un LIMIT recortaria justo la afirmacion. Los frenos
# son dos: TOPE_FILAS, por encima del cual el check dice NO MEDIDO en vez de mirar
# hacia otro lado, y la comparacion de count declarado contra filas recibidas, que es
# lo que caza un truncado silencioso.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
RUTA=/api/signals/ledger
TOPE_FILAS=400

# --- la ventana: se elige con SQL propio, no preguntandole a la ruta ----------------
# Hora cerrada con >=1 h de margen: ninguna escritura tardia la puede mover ya.
ventana=$("$B/bin/prodsql" "
  SELECT symbol,
         to_char(date_trunc('hour', observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:00:00\"Z\"'),
         count(*)
  FROM signal_observation
  WHERE observed_at >= now() - interval '12 hours'
    AND observed_at <  date_trunc('hour', now()) - interval '1 hour'
  GROUP BY 1,2
  HAVING count(*) >= 20
  ORDER BY 2 DESC, 3 DESC
  LIMIT 1" 2>/dev/null | grep -E '^[A-Z0-9_.]+\|' | head -1)

[ -n "$ventana" ] || { echo "NO MEDIDO: ninguna hora cerrada de las ultimas 12 h tiene >=20 observaciones en signal_observation"; exit 2; }

simbolo=${ventana%%|*}
resto=${ventana#*|}
desde=${resto%%|*}
esperadas=${resto##*|}

[ "$esperadas" -le "$TOPE_FILAS" ] || { echo "NO MEDIDO: la hora $desde de $simbolo trae $esperadas observaciones, por encima del tope de $TOPE_FILAS que este check sabe recalcular entero"; exit 2; }

hasta=$(date -u -d "$desde +1 hour" +%Y-%m-%dT%H:00:00Z 2>/dev/null)
[ -n "$hasta" ] || { echo "NO MEDIDO: no se pudo calcular el final de la ventana desde '$desde'"; exit 2; }

# --- referencia: escrita desde el esquema, no desde el endpoint ---------------------
ref=$("$B/bin/prodsql" "
  SELECT count(*),
         count(*) FILTER (WHERE is_transition),
         count(*) FILTER (WHERE is_periodic),
         count(*) FILTER (WHERE direction='long'),
         count(*) FILTER (WHERE direction='short'),
         count(*) FILTER (WHERE direction='neutral'),
         count(*) FILTER (WHERE decision_status='evaluable'),
         count(*) FILTER (WHERE reference_price IS NULL),
         count(DISTINCT state),
         round(sum(long_score)::numeric,6),
         round(sum(short_score)::numeric,6),
         to_char(min(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'),
         to_char(max(observed_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')
  FROM signal_observation
  WHERE symbol='$simbolo'
    AND observed_at >= timestamptz '$desde'
    AND observed_at <  timestamptz '$hasta'" 2>/dev/null | grep -E '^[0-9]+\|' | head -1)

[ -n "$ref" ] || { echo "NO MEDIDO: la consulta de referencia contra signal_observation no devolvio nada"; exit 2; }

# --- la ruta. TODO=1 porque se verifica que estan TODAS las filas (ver cabecera) ----
cuerpo=$(TODO=1 "$B/bin/api" "$RUTA?symbol=$simbolo&since=$desde&until=$hasta" 2>/dev/null)

# NO SE OLFATEA EL CUERPO. Este guardia decia case "$cuerpo" in *'404'*) y afirmaba "la
# capacidad no tiene API" en cuanto la cadena 404 aparecia EN CUALQUIER SITIO del JSON.
# El 2026-08-26, con la ruta ya desplegada y sirviendo 189 observaciones correctas, salio
# ROJO porque un observation_id valia 124404. Un check que dice "no responde" sobre una
# respuesta buena es peor que no tenerlo. Lo cazo la contradiccion con K20, que barrio esa
# misma ruta sin un solo 4xx.
# La ausencia de la ruta se decide abajo, sobre el JSON ya parseado: FastAPI contesta un
# 404 con {"detail":"Not Found"}, que es una forma concreta y no una subcadena.
[ -n "$cuerpo" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }

printf '%s' "$cuerpo" | python3 -c '
import json,sys
ref = sys.argv[1].split("|")
simbolo, desde, hasta, esperadas = sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
crudo = sys.stdin.read()
try:
    d = json.loads(crudo)
except Exception as e:
    print(f"NO MEDIDO: {sys.argv[6]} no devolvio JSON ({e}): {crudo[:80]!r}"); sys.exit(2)
# FastAPI contesta el 404 con exactamente {"detail":"Not Found"}. Es una FORMA, no una
# subcadena: un JSON valido sin observations pero con detail es la ruta ausente.
if isinstance(d, dict) and "observations" not in d and set(d) <= {"detail"}:
    print(f"la capacidad no tiene API: {sys.argv[6]} devuelve {d} en 140 ({esperadas} observaciones solo en {desde} de {simbolo})"); sys.exit(1)
if not isinstance(d, dict) or "observations" not in d:
    print(f"{sys.argv[6]} responde pero no sirve el ledger: sin clave observations (claves: {sorted(d)[:8] if isinstance(d,dict) else type(d).__name__})"); sys.exit(1)
obs = d["observations"]
if d.get("truncated"):
    print(f"NO MEDIDO: {sys.argv[6]} declara truncated=true, no se puede verificar la ventana entera"); sys.exit(2)
declarado = d.get("count")
if declarado is not None and declarado != len(obs):
    print(f"{sys.argv[6]} declara count={declarado} y sirve {len(obs)} observaciones"); sys.exit(1)

# claves que el ledger tiene que servir. Ausente NO es null: si falta la clave, la
# ruta esta borrando el "no lo se" en vez de servirlo -mismo defecto que persigue K48-.
CLAVES = ("observation_id","observed_at","symbol","is_periodic","is_transition",
          "decision_status","direction","state","confidence","long_score",
          "short_score","reference_price")
faltan = sorted({k for k in CLAVES for o in obs if k not in o})
if faltan:
    print(f"{sys.argv[6]} sirve observaciones sin las claves {faltan[:6]}"); sys.exit(1)

def n(v): return 0 if v is None else v
recalc = [
    len(obs),
    sum(1 for o in obs if o["is_transition"]),
    sum(1 for o in obs if o["is_periodic"]),
    sum(1 for o in obs if o["direction"] == "long"),
    sum(1 for o in obs if o["direction"] == "short"),
    sum(1 for o in obs if o["direction"] == "neutral"),
    sum(1 for o in obs if o["decision_status"] == "evaluable"),
    sum(1 for o in obs if o["reference_price"] is None),
    len({o["state"] for o in obs}),
    round(sum(n(o["long_score"]) for o in obs), 6),
    round(sum(n(o["short_score"]) for o in obs), 6),
    min((o["observed_at"] or "") for o in obs)[:19].replace(" ","T")+"Z" if obs else "",
    max((o["observed_at"] or "") for o in obs)[:19].replace(" ","T")+"Z" if obs else "",
]
NOMBRES = ("filas","transiciones","periodicas","long","short","neutral","evaluables",
           "sin precio de referencia","estados distintos","suma long_score",
           "suma short_score","primera observacion","ultima observacion")
malas = []
for nombre, esperado, obtenido in zip(NOMBRES, ref, recalc):
    e = esperado.strip()
    o = str(obtenido)
    try:
        iguales = abs(float(e) - float(o)) < 1e-6
    except ValueError:
        iguales = e == o
    if not iguales:
        malas.append(f"{nombre} {o} != {e}")
if malas:
    print(f"{len(malas)} de {len(NOMBRES)} cifras del ledger no cuadran contra signal_observation en {simbolo} {desde}: " + " · ".join(malas[:4])); sys.exit(1)
if len(obs) != esperadas:
    print(f"la ruta sirve {len(obs)} observaciones y la hora tiene {esperadas}"); sys.exit(1)
print(f"{len(NOMBRES)} cifras del ledger recalculadas desde el JSON cuadran con signal_observation: {simbolo} {desde}, {len(obs)} observaciones enteras")
' "$ref" "$simbolo" "$desde" "$hasta" "$esperadas" "$RUTA"
exit $?
