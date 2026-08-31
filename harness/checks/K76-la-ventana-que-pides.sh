#!/bin/bash
# K76  LA VENTANA QUE PIDES TIENE QUE SER LA VENTANA QUE MIRAS.
#
# ohlcv.ts es timestamptz y TODAS las barras diarias estan estampadas a 00:00:00 UTC
# (2355 de 2355, medido en 140 el 2026-08-31). La sesion de PostgreSQL de 140 corre en
# America/Mexico_City (UTC-6) porque app/db.py:151 pasa server_settings SOLO con
# application_name y el pool hereda la zona del servidor. Por eso ts::date resta un dia al
# 100 % de las barras diarias, no solo en los bordes:
#       2026-08-30 00:00Z  ->  ts::date  2026-08-29
#
# NO SE CAE EL PRIMER DIA: LA VENTANA ENTERA SE CORRE UNO, y eso es peor, porque el
# resultado tiene el mismo numero de barras que pediste y parece completo. Medido en 140
# el 2026-08-31 sobre BTCUSDT_PERP.A pidiendo 2026-08-20..2026-08-29:
#       tramo   :1534   10 barras con la TZ de sesion -> arco UTC 08-21..08-30
#                       10 barras con el cast en UTC  -> arco UTC 08-20..08-29
#                       2 filas cambian de conjunto (1 entra, 1 sale), 9 comunes
#       prior90 :1548   90 y 90 · 2 filas cambian · arco 05-23..08-20 vs 05-22..08-19
#       memoria :1661   730 filas · 0 CAMBIAN DE CONJUNTO · 730 de 730 etiquetas distintas
#
# LAS DOS CIFRAS SON DISTINTAS Y LAS DOS SON CIERTAS: el ARCO se desplaza un dia entero,
# y la DIFERENCIA SIMETRICA del conjunto es 2. Este check mide la segunda, que es la que
# no se puede satisfacer por accidente.
#
# POR QUE EL CRITERIO NO PUEDE SER "from == start_date": una ventana VACIA lo cumple. El
# espejo de 143 acaba el 2026-08-13, asi que pedirle 08-20..08-29 devuelve cero barras y
# un criterio ingenuo lo cantaria VERDE sobre nada. Aqui el criterio es de CONJUNTOS y
# ademas lleva clausula anti-vacio explicita: caso sin barras = ROJO, nunca VERDE.
#
# QUE HACE OBSERVABLE ESTO SIN INSTRUMENTAR CODIGO: scalp_logic.py:1594-1595 saca from/to
# con .date() de Python sobre un timestamptz de asyncpg, que decodifica en UTC. O sea la
# SELECCION esta mal y el ROTULO de la respuesta es UTC honesto: la respuesta declara
# exactamente que barras uso. Comprobado el 2026-08-31: la ruta contesta
# from=2026-08-21 to=2026-08-30 bars=10, identico al conjunto que elige psql con esa TZ.
#
# LOS TRES BRAZOS:
#   A · FILTRO (:1534). El conjunto de barras que la ruta usa contra el conjunto cuya
#       FECHA UTC cae en la ventana pedida. Diferencia simetrica > 0 = ROJO.
#   B · PROYECCION (:1661). market-memory rotula sus barras con ts::date, asi que su
#       coverage.to dice 2026-08-29 cuando la barra mas nueva que tiene es UTC 08-30.
#       Aqui NO cambia el conjunto -el cast no esta en el WHERE-: cambia la ETIQUETA de
#       todas. Medir "cuantas filas cambian de conjunto" en esta ruta da 0 y NO significa
#       que este sana; significa que la pregunta no aplica.
#   C · ATOMICIDAD (:1548). El prior de 90 NO es observable desde la respuesta:
#       prior_bars vale 90 con los dos cast. Pero hoy :1534 y :1548 son MUTUAMENTE
#       CONSISTENTES -prior acaba UTC 08-20, tramo empieza UTC 08-21: adyacentes, sin
#       solape-. Arreglar SOLO :1534 dejaria la barra UTC 08-20 EN LOS DOS conjuntos: la
#       referencia de volatilidad contaminada con un dia del tramo que juzga. Como no hay
#       observable de comportamiento, este brazo es ESTRUCTURAL y lo dice: los tres cast
#       se mueven juntos o ninguno.
#
# DE QUE ARBOL: por omision ruta y base de 140 (solo GET y SELECT de solo lectura; no
# escribe nada). Con ESPEJO=1 usa la API y la base del espejo de 143. El espejo corre la
# MISMA zona America/Mexico_City -medido-, asi que reproduce el fallo en vez de taparlo.
set -uo pipefail

B=/srv/coinanalyze/harness
SIMBOLOS="BTCUSDT_PERP.A ETHUSDT_PERP.A SOLUSDT_PERP.A"

if [ "${ESPEJO:-0}" = "1" ]; then
  sql() { "$B/bin/espejosql" "$1"; }
  get() { TODO=1 "$B/bin/api" --espejo "$1"; }
  DONDE="espejo de 143"
else
  sql() { "$B/bin/prodsql" "$1"; }
  get() { TODO=1 "$B/bin/api" "$1"; }
  DONDE="140"
fi

fallos=()   # lineas de ROJO
notas=()    # lo que se midio, para que la salida sea citable

for s in $SIMBOLOS; do
  # La ventana SALE DE LOS DATOS del entorno, no esta escrita a mano: 10 sesiones que
  # acaban UN DIA ANTES de la barra madura mas nueva, para que los dos extremos tengan
  # barra alrededor y el desplazamiento sea visible por los dos lados.
  # low/high TAMBIEN salen de los datos: la ruta rechaza un tramo que abarque mas de 3x
  # ("range spans more than 3x; narrow it"), asi que un 1..999999999 "neutro" sale NOMED,
  # y un 100000..130000 fijo solo valdria para BTC. Se usan el minimo y el maximo reales
  # de la propia ventana.
  fechas=$(sql "
    WITH m AS (
      SELECT (ts AT TIME ZONE 'UTC')::date AS d, low, high FROM ohlcv
      WHERE symbol='$s' AND interval='daily' AND ts + interval '1 day' <= now()
    ), u AS (SELECT max(d) AS ult FROM m)
    SELECT ((SELECT ult FROM u) - 10)::text || '|' || ((SELECT ult FROM u) - 1)::text
        || '|' || (SELECT ult FROM u)::text
        || '|' || round(min(low)::numeric, 2)::text
        || '|' || round(max(high)::numeric, 2)::text
    FROM m WHERE d BETWEEN (SELECT ult - 10 FROM u) AND (SELECT ult - 1 FROM u);")
  case "$fechas" in
    *\|*\|*\|*\|*) ;;
    *) fallos+=("$s: NOMED no pude derivar la ventana de los datos: '$fechas'"); continue ;;
  esac
  IFS='|' read -r S E ULTIMA LOW HIGH <<<"$fechas"

  # --- BRAZO A · el FILTRO (:1534) -------------------------------------------------
  resp=$(get "/api/range/validate?symbol=$s&low=$LOW&high=$HIGH&start_date=$S&end_date=$E")
  lectura=$(printf '%s' "$resp" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception as e: print('PARSE|'+str(e)[:80]); sys.exit()
# Un payload de error trae 'detail' y ningun from/to. Eso es CANAL, no defecto: si se
# contase como ROJO, un parametro mal puesto se leeria como fallo de fechas.
if 'detail' in d and 'from' not in d:
    print('DETALLE|'+str(d['detail'])[:90]); sys.exit()
print('OK|%s|%s|%s' % (d.get('from'), d.get('to'), d.get('bars')))
" 2>/dev/null)
  case "$lectura" in
    DETALLE\|*) fallos+=("$s brazo A: NOMED la ruta rechazo la peticion: ${lectura#DETALLE|}"); continue ;;
  esac
  case "$lectura" in
    OK\|*) ;;
    *) fallos+=("$s brazo A: NOMED la ruta no devolvio JSON legible ($lectura)"); continue ;;
  esac
  IFS='|' read -r _ RFROM RTO RBARS <<<"$lectura"
  if [ "$RFROM" = "None" ] || [ "$RTO" = "None" ]; then
    fallos+=("$s brazo A: la ruta devolvio from/to nulos sobre la ventana $S..$E")
    continue
  fi

  # Diferencia simetrica EXACTA, sobre las filas reales, sin suponer que no hay huecos:
  # pertenencia al conjunto que la ruta declara [from..to] contra pertenencia al conjunto
  # correcto (fecha UTC dentro de la ventana pedida, y madura).
  m=$(sql "
    WITH b AS (
      SELECT (ts AT TIME ZONE 'UTC')::date AS d, (ts + interval '1 day' <= now()) AS madura
      FROM ohlcv WHERE symbol='$s' AND interval='daily'
    ), c AS (
      SELECT d,
             (d BETWEEN DATE '$RFROM' AND DATE '$RTO')            AS en_ruta,
             (d BETWEEN DATE '$S' AND DATE '$E' AND madura)       AS en_correcto
      FROM b
    )
    SELECT count(*) FILTER (WHERE en_ruta <> en_correcto)::text || '|' ||
           count(*) FILTER (WHERE en_correcto)::text            || '|' ||
           count(*) FILTER (WHERE en_ruta)::text
    FROM c;")
  case "$m" in
    *\|*\|*) ;;
    *) fallos+=("$s brazo A: NOMED la comparacion de conjuntos no devolvio cifras: '$m'"); continue ;;
  esac
  IFS='|' read -r DIF NCORR NRUTA <<<"$m"

  # ANTI-VACIO. Sin esto, una ventana sin barras da diferencia 0 y saldria VERDE sobre
  # nada. Es exactamente el caso del espejo, que acaba el 2026-08-13.
  if [ "$NCORR" -eq 0 ]; then
    fallos+=("$s brazo A: CASO VACIO sobre $S..$E, 0 barras correctas. No prueba nada.")
    continue
  fi
  # El conjunto de la ruta se reconstruye desde [from..to]; si su tamano no cuadra con
  # las bars que ella misma declara, la reconstruccion no vale y no puedo juzgar.
  if [ "$NRUTA" -ne "$RBARS" ]; then
    fallos+=("$s brazo A: NOMED [$RFROM..$RTO] tiene $NRUTA barras en base y la ruta declara $RBARS")
    continue
  fi
  if [ "$DIF" -ne 0 ]; then
    fallos+=("$s brazo A: pedida $S..$E · la ruta uso $RFROM..$RTO · $DIF de $NCORR barras difieren")
  else
    notas+=("$s brazo A OK: $S..$E · $NCORR barras · 0 difieren")
  fi

  # --- BRAZO B · la PROYECCION (:1661) ---------------------------------------------
  mm=$(get "/api/market-memory?symbol=$s")
  cov=$(printf '%s' "$mm" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception as e: print('PARSE'); sys.exit()
c=d.get('coverage') or {}
print('OK|%s|%s' % (c.get('from'),c.get('to')))
" 2>/dev/null)
  case "$cov" in
    OK\|*) IFS='|' read -r _ CFROM CTO <<<"$cov" ;;
    *) fallos+=("$s brazo B: NOMED market-memory no devolvio coverage legible"); continue ;;
  esac
  if [ "$CTO" = "None" ]; then
    fallos+=("$s brazo B: market-memory no declara coverage.to"); continue
  fi
  # coverage.to rotula la barra mas nueva que la ruta tiene. Tiene que ser su fecha UTC.
  if [ "$CTO" != "$ULTIMA" ]; then
    fallos+=("$s brazo B: market-memory rotula su cierre mas nuevo como $CTO y la barra es UTC $ULTIMA")
  else
    notas+=("$s brazo B OK: coverage.to $CTO = barra UTC mas nueva")
  fi
done

# --- BRAZO C · ATOMICIDAD (:1548) ---------------------------------------------------
# Estructural a proposito, y declarado como tal: el prior de 90 no se puede observar desde
# ninguna respuesta. Lo que se exige es que los tres cast de scalp_logic.py sean del MISMO
# tipo. Mezclarlos mete la primera barra del tramo dentro de su propia referencia.
FUENTE=/srv/coinanalyze/repo/app/scalp_logic.py
if [ ! -r "$FUENTE" ]; then
  fallos+=("brazo C: NOMED no puedo leer $FUENTE")
else
  # Ocurrencias, no lineas: :1534 lleva DOS cast en la misma linea. "ts::date" no es
  # subcadena de "(ts AT TIME ZONE 'UTC')::date", asi que los dos conteos no se pisan.
  crudos=$(grep -o "ts::date" "$FUENTE" | wc -l)
  utc=$(grep -o "(ts AT TIME ZONE 'UTC')::date" "$FUENTE" | wc -l)
  if [ "$crudos" -ne 0 ] && [ "$utc" -ne 0 ]; then
    fallos+=("brazo C: MEZCLA en scalp_logic.py: $crudos cast crudos y $utc en UTC. El prior de :1548 y el tramo de :1534 tienen que moverse juntos o la referencia de volatilidad se contamina con el primer dia del tramo.")
  else
    notas+=("brazo C OK: los cast de scalp_logic.py son homogeneos ($crudos crudos, $utc en UTC)")
  fi
fi

# --- veredicto ----------------------------------------------------------------------
for n in "${notas[@]:-}"; do [ -n "$n" ] && printf '  %s\n' "$n"; done
if [ "${#fallos[@]}" -eq 0 ]; then
  printf 'VERDE: la ventana pedida es la usada en %s ' "$DONDE"
  printf 'y las etiquetas son la fecha UTC de su barra, en los %d simbolos\n' "$(echo $SIMBOLOS | wc -w)"
  exit 0
fi
for f in "${fallos[@]}"; do printf '  %s\n' "$f"; done
case "${fallos[*]}" in
  *NOMED*) printf 'NO MEDIDO: %d incidencias en %s, alguna por canal\n' "${#fallos[@]}" "$DONDE"; exit 2 ;;
esac
printf 'ROJO: %d desajustes de ventana en %s · ts::date usa la TZ de sesion, no UTC\n' "${#fallos[@]}" "$DONDE"
exit 1
