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
#     fuera: solo outcome_version=1 y solo las observaciones cuya evidence_version tenga
#     CONTRATO. Ningun certificado puede apuntar a un outcome no final, ni a una version
#     fuera de contrato. El conjunto certificable ya no se teclea aqui: sale de EJECUTAR
#     app.signal_visibility.visibility_version_for_evidence sobre las versiones VIVAS.
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
# v2, 2026-08-31: DOS NUMEROS, Y EL SEGUNDO NO ABSUELVE AL PRIMERO.
#
# QUE FALLABA. La v1 contaba bajo "sin certificado" dos hechos distintos: un outcome que
# DEBIA certificarse y no lo esta, y un outcome cuya evidence_version NO TIENE CONTRATO de
# certificacion. El segundo no es un fallo del certificador -- es deuda que nadie ha
# declarado --, y mezclarlos tiene un precio medido: el 2026-08-31, con la evidencia 7
# viva desde las 00:19Z, K25 informaba "304 outcomes ... no tienen certificado" mientras la
# cifra real crecia a ~1861/h. Informar el PRIMER grupo que incumple no deja distinguir un
# problema parado de uno acelerando.
#
# EL MECANISMO, leido y no deducido: _CERTIFIED_EVIDENCE_VERSION=6 viaja como PARAMETRO de
# la consulta que elige a quien certificar (signal_visibility.py:146 y :180), y la cabecera
# de ese modulo dice expresamente que RESEARCH_VISIBILITY_VERSION=1 solo se aplica a
# evidence_version=6 y que NO hay relleno hacia atras. No es un fallo: es el contrato
# congelado funcionando. K25 tiene razon en estar ROJO; lo que le faltaba era decir por que.
#
# LOS DOS NUMEROS:
#   (a) outcomes DENTRO de un contrato vigente sin certificado ....... tiene que ser 0
#   (b) outcomes cuya evidence_version NO tiene contrato ............. con su conteo y su
#       tasa, y pone ROJO si produccion SIGUE escribiendo esa version
#
# INDUCIDO CONTRA 140 CON EL PREDICADO LITERAL, porque un check que solo sabe salir ROJO
# esta tan roto como el que solo sabe salir VERDE:
#   A  contrato={6}, la vispera del corte ....... (a)=0     -> VERDE. Control POSITIVO
#   B  contrato={6}, hoy con la 7 viva .......... 100 % fuera de contrato -> ROJO
#   C  contrato={6,7}, declarado sin certificar .. (a)=837  -> ROJO
# C es el que prueba que (b) NO absuelve: declarar el contrato no borra las filas, las
# MUEVE al numero que gatea. Y A es el que prueba que esto no es un ROJO permanente.
#
# LO QUE SE ESTRECHA, Y SE DECLARA EN VEZ DE ESCONDERSE. La v1 habria gateado sobre
# CUALQUIER elegible sin certificado de la ventana; la v2 solo gatea (b) si esa version
# SIGUE VIVA. Motivo medido: la evidencia 5 dejo 2362 finales sin certificar que se
# pararon el 08-13 04:50 y que NUNCA tendran contrato -- "no v1-v5 backfill", lo dice
# signal_visibility.py:42 --, asi que la lectura literal de "(b) pone ROJO en cuanto
# exista" seria un ROJO permanente e inarreglable, y un rojo que no se puede arreglar
# ensena a ignorar el que si. No desaparecen: se informan como PARADA en cada pasada.
# El veredicto de HOY es el mismo con las dos lecturas -- ROJO --; la diferencia solo
# aparece el dia que la 7 tenga contrato.
set -uo pipefail
B=/srv/coinanalyze/harness; REPO=/srv/coinanalyze/repo; . "$B/env"
RUTA=/api/signals/visibility
TOPE_FILAS=1200
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

# --- EL CONTRATO, EJECUTADO SOBRE LAS VERSIONES VIVAS ------------------------------------
# Las versiones salen de 140 -lo que produccion escribe- y el contrato del REPO -lo que
# signal_visibility declara certificable-. Ninguna de las dos es una lista escrita aqui.
_crudo=$("$B/bin/prodsql" "
  SELECT DISTINCT evidence_version FROM signal_observation
   WHERE created_at >= date_trunc('hour', now()) - interval '1 hour'
   ORDER BY 1" 2>/dev/null) || { rc=$?; echo "NO MEDIDO: prodsql no contesto (rc=$rc). Esto NO es una ventana vacia: es que no se pudo preguntar."; exit 2; }
vivas=$(printf '%s\n' "$_crudo" | grep -E '^[0-9]+$' | tr '\n' ' ' | sed 's/ $//')
[ -n "$vivas" ] || { echo "NO MEDIDO: 140 no dice que evidence_version esta escribiendo"; exit 2; }

reparto=$(cd "$REPO" && "$PY" - $vivas <<'PY' 2>/dev/null
import sys
from app.signal_visibility import visibility_version_for_evidence

con, sin, visib = [], [], set()
for arg in sys.argv[1:]:
    v = int(arg)
    # SE EJECUTA la funcion, no se lee un diccionario: comprobar que existe un mapa no
    # distingue este check del que daba por bueno cualquier contrato. Leccion de K71.
    contrato = visibility_version_for_evidence(v)
    (con if contrato is not None else sin).append(v)
    if contrato is not None:
        visib.add(contrato)
# Dos visibility_version distintas a la vez NO se sabe juzgar, y eso si es NO MEDIDO.
# Que no haya NINGUNA es otra cosa muy distinta -- todo lo que produccion escribe hoy
# esta fuera de contrato -- y tiene que salir ROJO, no NOMED.
if len(visib) > 1:
    raise SystemExit(0)
print(f"{','.join(map(str, con))}|{','.join(map(str, sin))}|{visib.pop() if visib else 0}")
PY
)
[ -n "$reparto" ] || { echo "NO MEDIDO: no se pudo ejecutar el contrato de visibilidad sobre las versiones vivas ($vivas)"; exit 2; }
CON_CONTRATO=${reparto%%|*}; _r=${reparto#*|}
SIN_CONTRATO=${_r%%|*}; VISIB=${_r##*|}
arr() { if [ -n "${1:-}" ]; then printf 'ARRAY[%s]::int[]' "$1"; else printf 'ARRAY[]::int[]'; fi; }
CON_ARR=$(arr "$CON_CONTRATO"); SIN_ARR=$(arr "$SIN_CONTRATO")

# (b) LA DEUDA SIN CONTRATO, POR VERSION Y CON SU VELOCIDAD. El corte es min(
# verified_visible_at): lo finalizado ANTES de que existiera el certificador no es deuda
# suya, y exigirselo seria discriminar el legado por nulidad en vez de por tiempo -la
# misma correccion que ya se le hizo a K04-. La ultima columna dice si produccion SIGUE
# escribiendo esa version, y es lo unico que separa una deuda parada de una acelerando.
# LA TASA ES LA ULTIMA HORA CERRADA Y NO UN PROMEDIO LARGO, y esto se corrigio midiendo:
# con la evidencia 7 nacida a las 00:19Z, promediar 6 h daba 449.7/h para algo que el
# operador midio en ~2027/h instantaneos. Un promedio sobre una ventana mas larga que la
# vida del problema lo diluye justo cuando mas corre, que es el error opuesto al que este
# check acaba de arreglar.
deuda=$("$B/bin/prodsql" "
  WITH corte AS (SELECT min(verified_visible_at) c FROM signal_outcome_final_visibility)
  SELECT o.evidence_version, count(*),
         count(*) FILTER (
           WHERE so.finalized_at >= date_trunc('hour', now()) - interval '1 hour'
             AND so.finalized_at <  date_trunc('hour', now())),
         (o.evidence_version = ANY($SIN_ARR))
  FROM signal_outcome so JOIN signal_observation o USING (observation_id), corte
  WHERE so.outcome_version=1 AND so.status IN ('evaluated','not_evaluable')
    AND so.finalized_at >= corte.c
    AND NOT (o.evidence_version = ANY($CON_ARR))
    AND NOT EXISTS (
      SELECT 1 FROM signal_outcome_final_visibility v WHERE v.outcome_id=so.outcome_id)
  GROUP BY 1 ORDER BY 1" 2>/dev/null | grep -E '^[0-9]+\|')

deuda_viva=0; deuda_parada=0; detalle=""
while IFS='|' read -r v n tasa viva; do
  [ -n "${v:-}" ] || continue
  if [ "$viva" = "t" ]; then
    deuda_viva=$((deuda_viva + n))
    detalle="${detalle:+$detalle · }evidencia $v: $n sin contrato y VIVA, $tasa en la ultima hora cerrada"
  else
    deuda_parada=$((deuda_parada + n))
    detalle="${detalle:+$detalle · }evidencia $v: $n sin contrato, PARADA"
  fi
done <<DEUDA
$deuda
DEUDA
[ -n "$detalle" ] || detalle="ninguna"

# EL PORTON QUE NO EXISTIA, y es el caso de HOY: si NINGUNA version viva tiene contrato,
# el 100 % de lo que produccion escribe es incertificable y no hay ventana (a) que medir.
# Salir por NO MEDIDO aqui seria lo peor de todo: "no pude medir" leido como "no pasa
# nada" mientras la deuda corre.
[ -n "$CON_CONTRATO" ] || { echo "(b) el 100 % de lo que produccion escribe HOY esta fuera de contrato: evidencia viva $vivas y ninguna certificable · $detalle · (a) no se puede medir porque no hay conjunto elegible"; exit 1; }

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

# (a) LA COBERTURA DENTRO DEL CONTRATO. Conjunto elegible COMPLETO de la ventana
# -definido sobre finalized_at, que es cuando el outcome se hizo final- contra los que
# tienen certificado. Si sale distinto de cero, alguien puede elegir despues que
# resultados declara probados. Tiene que ser 0 y NADA lo absuelve.
huecos=$("$B/bin/prodsql" "
  SELECT count(*), coalesce(min(so.outcome_id)::text,'-')
  FROM signal_outcome so
  JOIN signal_observation o USING (observation_id)
  WHERE o.symbol='$simbolo' AND so.outcome_version=1
    AND so.status IN ('evaluated','not_evaluable')
    AND o.evidence_version = ANY($CON_ARR)
    AND so.finalized_at >= timestamptz '$desde' AND so.finalized_at < timestamptz '$hasta'
    AND NOT EXISTS (
      SELECT 1 FROM signal_outcome_final_visibility v
      WHERE v.outcome_id=so.outcome_id AND v.visibility_version=$VISIB)" 2>/dev/null \
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

TODO=1 "$B/bin/api" "$RUTA?symbol=$simbolo&since=$desde&until=$hasta&limit=$((TOPE_FILAS+1))" > "$CUERPO" 2>/dev/null || { rc=$?; echo "NO MEDIDO: la API no contesto (rc=$rc). Esto NO es una ventana vacia: es que no se pudo preguntar."; exit 2; }
[ -s "$CUERPO" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }

python3 -c '
import json, sys
from datetime import datetime, UTC

ref = sys.argv[1].split("|")
simbolo, desde, esperadas, ruta = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
camino_cuerpo, camino_origen, huecos = sys.argv[6], sys.argv[7], sys.argv[8]
# El contrato viaja EJECUTADO desde el repo, no tecleado aqui: son las versiones para las
# que signal_visibility.visibility_version_for_evidence devolvio algo.
certificables = {int(x) for x in sys.argv[9].split(",") if x}
visibilidad = int(sys.argv[10])
deuda_viva, deuda_parada, detalle_deuda = int(sys.argv[11]), int(sys.argv[12]), sys.argv[13]

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
        if int(o[3]) not in certificables:
            fallos.append(f"outcome {oid}: certificado sobre una observacion con evidence_version={o[3]}, y el contrato solo cubre {sorted(certificables)}")
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
    if int(f["visibility_version"]) != visibilidad:
        fallos.append(f"outcome {oid}: visibility_version {f["visibility_version"]}, y el contrato declara la {visibilidad}")

# --- CAPA CERRADA 4: la cobertura, medida sobre el conjunto elegible completo ----------
try:
    sin_certificado, primero = huecos.split("|")[0], huecos.split("|")[1]
    sin_certificado = int(sin_certificado)
except Exception:
    print(f"NO MEDIDO: no se pudo contar el conjunto elegible sin certificado"); sys.exit(2)
# --- LOS DOS NUMEROS, Y EL SEGUNDO NO ABSUELVE AL PRIMERO -----------------------------
# (a) es un fallo de CERTIFICACION: el contrato cubre esas filas y no estan certificadas.
# (b) es deuda DECLARADA: nadie ha escrito contrato para esa evidencia. Son cosas
# distintas y hasta el 2026-08-31 K25 las sumaba bajo "sin certificado", que es como un
# problema que acelera se lee igual que uno parado.
if sin_certificado:
    print(f"(a) {sin_certificado} outcomes finales de {simbolo} en {desde} DENTRO del contrato no tienen certificado -el primero es {primero}-: la tabla de certificados esta incompleta, y elegir cuales se certifican es elegir que resultados se declaran probados · (b) {deuda_viva} sin contrato vivos, {deuda_parada} parados: {detalle_deuda}"); sys.exit(1)
if deuda_viva:
    print(f"(b) {deuda_viva} outcomes finales sin CONTRATO de certificacion y produccion sigue escribiendo esa evidencia: {detalle_deuda}. No es que falte certificarlos: es que nadie ha declarado como se certifica esa forma, asi que no se certifican solos por mucho que el certificador corra. (a) queda en 0 · deuda parada {deuda_parada}"); sys.exit(1)

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
print(f"(a) 0 elegibles dentro del contrato sin certificar y (b) 0 sin contrato vivos -deuda parada {deuda_parada}: {detalle_deuda}-. {concordados} certificados contra la fila VIVA de signal_outcome -estado, finalizacion, version y horizonte-, {len(filas)} con relojes en orden y elegibilidad comprobada, y CERO elegibles sin certificar en la ventana + {len(NOMBRES)} conteos: {simbolo} {desde}, {len(filas)} certificados enteros. Retraso de certificacion declarado, no gateado: {retrasos[0]:.1f} s a {retrasos[-1]:.1f} s. ABIERTO a proposito: que la lectura ocurriera en ese instante, que no se puede volver a observar")
' "$ref" "$simbolo" "$desde" "$esperadas" "$RUTA" "$CUERPO" "$ORIGEN" "$huecos" "$CON_CONTRATO" "$VISIB" "$deuda_viva" "$deuda_parada" "$detalle"
exit $?
