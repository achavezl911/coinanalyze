#!/bin/bash
# K25  signal_outcome_final_visibility son 636166 filas: CERTIFICADOS de que el estado
# final de un signal_outcome ya estaba escrito y era visible desde fuera no mas tarde de
# verified_visible_at. Productor funcionando -K06 lo desatasco-, cero API.
#
# QUE CERTIFICA ESTA TABLA, EN SUS PROPIAS PALABRAS (app/signal_visibility.py:20-32): una
# transaccion NUEVA, posterior al COMMIT del productor, lee el estado ya comprometido y
# SOLO DESPUES pide clock_timestamp(). No es el commit timestamp de PostgreSQL y no se
# puede documentar como tal: es una COTA SUPERIOR conservadora.
#
# QUE CAPA CIERRA ESTE CHECK Y CUAL DEJA ABIERTA.
#
#   CERRADA · el certificado concuerda con lo que certifica. source_status,
#     source_finalized_at y outcome_version contra la fila VIVA de signal_outcome, leida
#     por ssh+psql y no por la ruta. No es tautologico y es la comprobacion central:
#     signal_outcome es una tabla que se ACTUALIZA -las filas nacen pending y se evaluan
#     al vencer su horizonte, K22- mientras el certificado es append-only por trigger.
#     Un certificado es una copia congelada de algo que se mueve; si el original cambiara
#     despues de certificarlo, el certificado quedaria mintiendo y nadie se enteraria.
#   CERRADA · la regla de elegibilidad, que el productor aplica y nadie comprobaba desde
#     fuera: solo outcome_version=1 y solo observaciones con evidence_version=6. Ningun
#     certificado puede apuntar a un outcome no final, ni a una version que no sea esa.
#   CERRADA · el orden de relojes QUE NO IMPONE EL ESQUEMA: verified_visible_at <=
#     created_at, porque el productor pide el reloj y DESPUES inserta. El otro orden
#     -source_finalized_at <= verified_visible_at- si lo impone un CHECK de
#     sql/schema.sql:2418, asi que se comprueba pero se declara: eso lo garantiza la base
#     y no este check. Vender como hallazgo lo que impone una restriccion seria inflar.
#   CERRADA · LA COBERTURA, que es la que impide elegir a dedo. Toda fila elegible y
#     final de la ventana tiene certificado. Una tabla de certificados incompleta no es
#     un error de aritmetica: es poder decidir DESPUES cuales de tus resultados declaras
#     probados. Se mide contra el conjunto elegible completo, no contra los que ya tienen
#     certificado.
#     Y AQUI ESTA POR QUE ESTA UNIDAD EXISTE, que alguien podria discutir mirando el
#     esquema: sql/schema.sql:2418 ya trae dos CHECK -source_finalized_at <=
#     verified_visible_at, y visibility_version<>1 OR outcome_version=1- que imponen
#     parte de esto. No basta, y el motivo es exacto: UN CHECK IMPIDE ESCRIBIR UNA FILA
#     MALA, NO IMPIDE OMITIR UNA FILA BUENA. La base no puede detectar una AUSENCIA. Por
#     eso la cobertura se mide derivando el conjunto elegible COMPLETO desde la regla, y
#     no hay atajo por el esquema para cazar "certifico solo lo que me conviene".
#     El append-only tampoco se queda en intencion: pg_trigger da DOS disparadores sobre
#     la tabla a reject_signal_outcome_final_visibility_mutation, tgtype 27 -BEFORE ROW
#     UPDATE OR DELETE- y tgtype 34 -BEFORE STATEMENT TRUNCATE-, que es el que se suele
#     olvidar en las tablas que se declaran append-only. Pero un trigger tampoco impide
#     una ausencia: solo impide reescribir el pasado.
#   ABIERTA · que la lectura ocurriera de verdad en ese instante. verified_visible_at
#     afirma algo sobre el pasado -"esto ya se podia leer"- y el pasado no se vuelve a
#     observar: no hay forma de repetir aquella lectura. Es cota superior POR
#     CONSTRUCCION, no por medicion. Este check cierra todo lo que la rodea -que
#     concuerda, que es elegible, que los relojes van en orden y que no falta ninguna-
#     pero NO afirma que el instante sea el mas ajustado posible.
#
# LO QUE SE MIDIO ANTES DE ESCRIBIR EL CHECK (140, tabla entera, 2026-08-26T20:35Z):
#   636166 certificados, visibility_version unica (1), del 08-13 00:52Z a AHORA MISMO.
#   contra la fila viva de signal_outcome: 0 descuadres de status, 0 de finalized_at,
#     0 de outcome_version, 0 con finalized_at nulo hoy.
#   0 certificados apuntando a un outcome no final o a evidence_version<>6.
#   0 con verified_visible_at > created_at.
#   COBERTURA: 636205 elegibles y CERO sin certificado. El atasco que K06 desatasco
#     drenó del todo.
#   EL RETRASO DE CERTIFICACION, que es lo que fija la ventana: en las ultimas 24 h va de
#     0.8 s a 2.2 s con p50 0.9 y p95 1.2. En el tramo viejo llega a 299043 s -3.46
#     dias-, que es la parada del 08-20 al 08-25 vista desde el otro lado. Por eso la
#     ventana va a una hora YA CERRADA: con 2.2 s de retraso maximo, exigir cobertura
#     completa sobre una hora cerrada no es exigir que el certificador sea instantaneo.
#   Y EL RETRASO NO SE USA PARA CLASIFICAR NADA, solo se declara. Un umbral sobre el
#     reloj seria la trampa 4 otra vez, y ademas ya hay quien vigila que el productor no
#     se pare: K06. Aqui se gatea sobre la COBERTURA, que es un conjunto, no un instante.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
RUTA=/api/signals/visibility
TOPE_FILAS=1200

ventana=$("$B/bin/prodsql" "
  SELECT o.symbol,
         to_char(date_trunc('hour', v.verified_visible_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:00:00\"Z\"'),
         count(*)
  FROM signal_outcome_final_visibility v
  JOIN signal_outcome so USING (outcome_id)
  JOIN signal_observation o USING (observation_id)
  WHERE v.verified_visible_at >= now() - interval '5 hours'
    AND v.verified_visible_at <  date_trunc('hour', now())
  GROUP BY 1,2 HAVING count(*) BETWEEN 20 AND $TOPE_FILAS
  ORDER BY 2 DESC, 3 DESC LIMIT 1" 2>/dev/null | grep -E '^[A-Z0-9_.]+\|' | head -1)
[ -n "$ventana" ] || { echo "NO MEDIDO: ninguna hora cerrada de las ultimas 5 h tiene entre 20 y $TOPE_FILAS certificados"; exit 2; }

simbolo=${ventana%%|*}; resto=${ventana#*|}
desde=${resto%%|*}; esperadas=${resto##*|}
hasta=$(date -u -d "$desde +1 hour" +%Y-%m-%dT%H:00:00Z 2>/dev/null)
[ -n "$hasta" ] || { echo "NO MEDIDO: no se pudo calcular el final de la ventana"; exit 2; }

ref=$("$B/bin/prodsql" "
  SELECT count(*), count(DISTINCT v.outcome_id), count(DISTINCT v.visibility_version),
         count(*) FILTER (WHERE v.source_status='evaluated'),
         count(*) FILTER (WHERE v.source_status='not_evaluable'),
         count(DISTINCT so.horizon_minutes)
  FROM signal_outcome_final_visibility v
  JOIN signal_outcome so USING (outcome_id)
  JOIN signal_observation o USING (observation_id)
  WHERE o.symbol='$simbolo' AND v.verified_visible_at >= timestamptz '$desde'
    AND v.verified_visible_at < timestamptz '$hasta'" 2>/dev/null | grep -E '^[0-9]+\|' | head -1)
[ -n "$ref" ] || { echo "NO MEDIDO: la consulta de referencia no devolvio nada"; exit 2; }

# LA COBERTURA. Conjunto elegible COMPLETO de la ventana -definido sobre finalized_at,
# que es cuando el outcome se hizo final- contra los que tienen certificado. Si sale
# distinto de cero, alguien puede elegir despues que resultados declara probados.
huecos=$("$B/bin/prodsql" "
  SELECT count(*), coalesce(min(so.outcome_id)::text,'-')
  FROM signal_outcome so
  JOIN signal_observation o USING (observation_id)
  WHERE o.symbol='$simbolo' AND so.outcome_version=1
    AND so.status IN ('evaluated','not_evaluable')
    AND so.finalized_at >= timestamptz '$desde' AND so.finalized_at < timestamptz '$hasta'
    AND NOT EXISTS (
      SELECT 1 FROM signal_outcome_final_visibility v
      WHERE v.outcome_id=so.outcome_id AND v.visibility_version=1)" 2>/dev/null \
  | grep -E '^[0-9]+\|' | head -1)
[ -n "$huecos" ] || { echo "NO MEDIDO: no se pudo contar el conjunto elegible sin certificado"; exit 2; }

# La fila VIVA de cada outcome certificado, por ssh+psql: es lo que impide que la ruta
# se valide a si misma.
ORIGEN=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de origen"; exit 2; }
CUERPO=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de respuesta"; exit 2; }
trap 'rm -f "$ORIGEN" "$CUERPO"' EXIT

TODO=1 "$B/bin/prodsql" "
  SELECT v.outcome_id, so.status, to_char(so.finalized_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.USOF'),
         so.outcome_version, o.evidence_version, so.horizon_minutes
  FROM signal_outcome_final_visibility v
  JOIN signal_outcome so USING (outcome_id)
  JOIN signal_observation o USING (observation_id)
  WHERE o.symbol='$simbolo' AND v.verified_visible_at >= timestamptz '$desde'
    AND v.verified_visible_at < timestamptz '$hasta'" 2>/dev/null \
  | grep -E '^[0-9]+\|' > "$ORIGEN"

TODO=1 "$B/bin/api" "$RUTA?symbol=$simbolo&since=$desde&until=$hasta&limit=$((TOPE_FILAS+1))" > "$CUERPO" 2>/dev/null
[ -s "$CUERPO" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }

python3 -c '
import json, sys
from datetime import datetime, UTC

ref = sys.argv[1].split("|")
simbolo, desde, esperadas, ruta = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
camino_cuerpo, camino_origen, huecos = sys.argv[6], sys.argv[7], sys.argv[8]

crudo = open(camino_cuerpo).read()
try:
    d = json.loads(crudo)
except Exception as e:
    print(f"NO MEDIDO: {ruta} no devolvio JSON ({e}): {crudo[:80]!r}"); sys.exit(2)
if isinstance(d, dict) and "certificates" not in d and set(d) <= {"detail"}:
    print(f"la capacidad no tiene API: {ruta} devuelve {d} en 140 ({esperadas} certificados solo en {desde} de {simbolo})"); sys.exit(1)
if not isinstance(d, dict) or "certificates" not in d:
    print(f"{ruta} responde pero no sirve los certificados: sin clave certificates"); sys.exit(1)
filas = d["certificates"]
if d.get("truncated"):
    print(f"NO MEDIDO: {ruta} declara truncated=true"); sys.exit(2)
if d.get("count") is not None and d["count"] != len(filas):
    print(f"{ruta} declara count={d["count"]} y sirve {len(filas)} certificados"); sys.exit(1)

CLAVES = ("final_visibility_id","outcome_id","observation_id","symbol","horizon_minutes",
          "visibility_version","outcome_version","source_status","source_finalized_at",
          "verified_visible_at","created_at")
faltan = sorted({k for k in CLAVES for f in filas if k not in f})
if faltan:
    print(f"{ruta} sirve certificados sin las claves {faltan[:6]}"); sys.exit(1)

def hora(v):
    return None if v in (None, "") else datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(UTC)

vivo = {}
for linea in open(camino_origen):
    p = linea.rstrip("\n").split("|")
    if len(p) < 6: continue
    vivo[int(p[0])] = p[1:6]

fallos, concordados = [], 0
for f in filas:
    oid = f["outcome_id"]

    # --- CAPA CERRADA 1: el certificado contra la fila VIVA que certifica --------------
    o = vivo.get(oid)
    if o is not None:
        concordados += 1
        if f["source_status"] != o[0]:
            fallos.append(f"outcome {oid}: el certificado dice {f["source_status"]} y la fila viva dice {o[0]}")
        if hora(f["source_finalized_at"]) != hora(o[1]):
            fallos.append(f"outcome {oid}: source_finalized_at {f["source_finalized_at"]} y la fila viva {o[1]}")
        if int(f["outcome_version"]) != int(o[2]):
            fallos.append(f"outcome {oid}: outcome_version {f["outcome_version"]} y la fila viva {o[2]}")
        # --- CAPA CERRADA 2: la regla de elegibilidad ---------------------------------
        if int(o[3]) != 6:
            fallos.append(f"outcome {oid}: certificado sobre una observacion con evidence_version={o[3]}, y solo la 6 es certificable")
        if o[0] not in ("evaluated", "not_evaluable"):
            fallos.append(f"outcome {oid}: certificado sobre un outcome que HOY esta en {o[0]}, que no es final")
        if int(f["horizon_minutes"]) != int(o[4]):
            fallos.append(f"outcome {oid}: horizon_minutes {f["horizon_minutes"]} y la fila viva {o[4]}")

    # --- CAPA CERRADA 3: el orden de relojes ------------------------------------------
    fin, visto, creado = hora(f["source_finalized_at"]), hora(f["verified_visible_at"]), hora(f["created_at"])
    if None in (fin, visto, creado):
        fallos.append(f"outcome {oid}: un certificado sin alguna de sus tres horas")
        continue
    if visto > creado:
        fallos.append(f"outcome {oid}: verified_visible_at {visto} es POSTERIOR a created_at {creado}: el reloj se pidio antes de insertar")
    if fin > visto:
        fallos.append(f"outcome {oid}: source_finalized_at {fin} es posterior a verified_visible_at {visto}")
    if int(f["visibility_version"]) != 1:
        fallos.append(f"outcome {oid}: visibility_version {f["visibility_version"]}, y solo existe la 1")

# --- CAPA CERRADA 4: la cobertura, medida sobre el conjunto elegible completo ----------
try:
    sin_certificado, primero = huecos.split("|")[0], huecos.split("|")[1]
    sin_certificado = int(sin_certificado)
except Exception:
    print(f"NO MEDIDO: no se pudo contar el conjunto elegible sin certificado"); sys.exit(2)
if sin_certificado:
    print(f"{sin_certificado} outcomes finales de {simbolo} en {desde} no tienen certificado -el primero es {primero}-: la tabla de certificados esta incompleta, y elegir cuales se certifican es elegir que resultados se declaran probados"); sys.exit(1)

if fallos:
    print(f"{len(fallos)} comprobaciones fallan sobre {len(filas)} certificados: " + " · ".join(fallos[:3])); sys.exit(1)
if concordados == 0:
    print(f"NO MEDIDO: ningun certificado de la ventana tiene fila viva con la que comparar"); sys.exit(2)
if concordados != len(filas):
    print(f"{len(filas)-concordados} certificados de {len(filas)} no tienen fila en signal_outcome: un certificado sin original"); sys.exit(1)

agregados = [len(filas), len({f["outcome_id"] for f in filas}),
             len({f["visibility_version"] for f in filas}),
             sum(1 for f in filas if f["source_status"] == "evaluated"),
             sum(1 for f in filas if f["source_status"] == "not_evaluable"),
             len({f["horizon_minutes"] for f in filas})]
NOMBRES = ("certificados","outcomes distintos","versiones de visibilidad",
           "evaluated","not_evaluable","horizontes distintos")
descuadres = []
for nombre, esperado, obtenido in zip(NOMBRES, ref, agregados):
    e, o2 = esperado.strip(), str(obtenido)
    try: iguales = abs(float(e) - float(o2)) < 1e-6
    except ValueError: iguales = e == o2
    if not iguales: descuadres.append(f"{nombre} {o2} != {e}")
if descuadres:
    print(f"{len(descuadres)} de {len(NOMBRES)} conteos no cuadran: " + " · ".join(descuadres[:4])); sys.exit(1)
if len(filas) != esperadas:
    print(f"la ruta sirve {len(filas)} certificados y la hora tiene {esperadas}"); sys.exit(1)

retrasos = sorted((hora(f["verified_visible_at"]) - hora(f["source_finalized_at"])).total_seconds() for f in filas)
print(f"{concordados} certificados contra la fila VIVA de signal_outcome -estado, finalizacion, version y horizonte-, {len(filas)} con relojes en orden y elegibilidad comprobada, y CERO elegibles sin certificar en la ventana + {len(NOMBRES)} conteos: {simbolo} {desde}, {len(filas)} certificados enteros. Retraso de certificacion declarado, no gateado: {retrasos[0]:.1f} s a {retrasos[-1]:.1f} s. ABIERTO a proposito: que la lectura ocurriera en ese instante, que no se puede volver a observar")
' "$ref" "$simbolo" "$desde" "$esperadas" "$RUTA" "$CUERPO" "$ORIGEN" "$huecos"
exit $?
