#!/bin/bash
# K92  EL MINUTO QUE MIENTE QUE ESTA COMPLETO.
#
# EL HECHO, medido en 140. En `spot_trades_agg`:
#   minuto 17:17 -> covered_seconds = 45   correcto (60 - 15)
#   minuto 17:16 -> covered_seconds = 60   y el colector estuvo parado sus ultimos 5 s
#                                          -> deberia decir 55
#
# EL BUCKET AUSENTE YA SE ARREGLO. El que sigue roto es el **corto del lado de la PARADA**,
# y es el caso peor de los dos: un hueco que se ve es un hueco, pero **un minuto que miente
# que esta completo no lo ve nadie**. La fila existe, K37 la cuenta como presente, y las
# derivadas de ese minuto no saben que van cortas.
#
# ESTA EN LAS DOS TABLAS que declaran cobertura por segundo -las unicas dos del sistema-:
# `spot_trades_agg` y `futures_trades_agg`. La fila `combined` se construye con
# `MIN(covered_seconds)` (`app/scalp_collector.py:801-812`, `app/ws_collector.py:284`).
# **EL `MIN` ESTA BIEN ELEGIDO** -el combinado no puede estar mejor cubierto que su peor
# pata- y solo HEREDA el defecto. **No se arregla ahi**: tocar el agregador taparia el
# sintoma dejando las patas mintiendo.
#
# EL ELEGIBLE SALE DE UN INSTRUMENTO EXTERNO, Y ESO ES LO QUE HACE HONESTO A ESTE CHECK.
# Las paradas se leen del JOURNAL, no de la propia tabla. Preguntarle a `spot_trades_agg`
# cuando se paro el colector seria preguntarle al sospechoso: si la tabla se equivoca al
# escribir la cobertura, no hay razon para creerle el resto. Es la regla que costo tres
# rondas asentar en este arnes.
#
# EL CRITERIO ESTUVO MAL APUNTADO HASTA EL 2026-09-05, y lo cazo su propio control.
# La primera version miraba «el minuto de la parada y el SIGUIENTE», y el defecto esta en el
# minuto ANTERIOR: en el ejemplo de arriba el que miente es 17:16 -el que contiene el
# instante en que el colector se fue- y 17:17 sale bien porque ya nace corto. Mirando el
# siguiente, el check habria dado por sano justo el minuto roto.
#
# EL SUJETO ES LA VENTANA `Stopping -> Started`, no un instante. `Stopped` solo marca el
# final del apagado; entre `Stopping` y `Started` el colector NO estaba recogiendo, y esa
# ventana puede cruzar dos minutos -17:16:55 -> 17:17:14 son 5 s del uno y 14 s del otro-.
# Se exigen los DOS marcadores: un `Stopping` sin su `Started` es una ventana abierta y no
# se juzga.
#
# LA COMPARACION ES UNA DESIGUALDAD, NO UNA RESTA. Se exige
#     covered_seconds <= 60 - segundos_caidos_en_ese_minuto
# y no la igualdad. Un minuto puede declarar MENOS de lo que la parada explica por otras
# razones -el arranque del 2026-09-03 tardo en recibir su primer trade y dejo el minuto en
# `covered_seconds=1` con solo 19 s de ventana- y eso NO es este defecto. La resta exacta
# habria dado ROJO ahi y el ROJO habria sido falso. Solo miente el minuto que declara MAS
# cobertura de la que la ventana permite.
#
# EL CONTROL, EN LA MISMA CONSULTA: se traen tambien los minutos del entorno (+-3) que
# NINGUNA ventana toca. Al menos uno tiene que declarar 60. Si ninguno llega a 60, la tabla
# va corta por todas partes y el hallazgo no seria atribuible a la parada: eso es NOMED, no
# ROJO. Es huella positiva -probar que el instrumento SABE decir «completo»-, no basta con
# que la consulta no falle.
#
# Corre contra 140 por prodsql y por el journal. Sin ninguno de los dos, NOMED.
set -uo pipefail
B=/srv/coinanalyze/harness
_repo_pedido=${REPO:-}
[ -r "$B/env" ] && . "$B/env"
REPO=${_repo_pedido:-${REPO:-/srv/coinanalyze/repo}}
PRODSQL=${K92_PRODSQL:-$B/bin/prodsql}
PROD=${K92_PROD:-$B/bin/prod}
DIAS=${K92_DIAS:-7}
UNIT=${K92_UNIT:-coinalyze-ws.service}
TABLA=${K92_TABLA:-spot_trades_agg}

command -v python3 >/dev/null 2>&1 || { echo "NO MEDIDO: no hay python3"; exit 2; }
[ -x "$PRODSQL" ] || { echo "NO MEDIDO: no hay canal a la base ($PRODSQL)"; exit 2; }
[ -x "$PROD" ]    || { echo "NO MEDIDO: no hay canal al journal ($PROD)"; exit 2; }

# --- 0 · LAS COLUMNAS EXISTEN · comprobado contra el esquema ANTES de consultar ---------
# Es la regla que sale del `ts` de K90 y del `wyckoff_phase`: dos consultas escritas contra
# un esquema supuesto en dos paquetes seguidos. Aqui se comprueba primero, y con el mismo
# catalogo que usa el mapa -que desde F4 conoce tambien las columnas de ALTER, sin las
# cuales `covered_seconds` seria invisible-.
faltan=$(python3 - "$REPO" "$TABLA" <<'PY'
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
repo, tabla = Path(sys.argv[1]), sys.argv[2]
try:
    m = SourceFileLoader("arq", str(repo / "harness/bin/arquitectura")).load_module()
    cols = set(m.lee_catalogo(repo)["tablas"].get(tabla, {}).get("columnas", []))
except Exception as e:
    print("ERRCAT", e); raise SystemExit
if not cols:
    print("SINTABLA"); raise SystemExit
print(" ".join(c for c in ("ts", "symbol", "exchange", "interval", "covered_seconds")
               if c not in cols))
PY
2>&1)
case "$faltan" in
  ERRCAT*)  echo "NO MEDIDO: no se pudo leer el catalogo: $(printf '%s' "$faltan" | cut -c1-100)"; exit 2 ;;
  SINTABLA) echo "NO MEDIDO: $TABLA no esta en sql/schema.sql"; exit 2 ;;
  "") ;;
  *) echo "NO MEDIDO: a $TABLA le faltan columnas en el esquema:$faltan"; exit 2 ;;
esac

# --- 1 · EL ELEGIBLE · las VENTANAS de parada, del JOURNAL ----------------------------
# Se piden los DOS marcadores. Se leen con -n acotado a proposito: un journalctl sin limite
# es la forma mas rapida de arruinar una sesion.
paradas=$("$PROD" "journalctl -u $UNIT --since '-$DIAS days' --utc -o short-iso --no-hostname -n 2000 | grep -E 'Stopping|Started'" 2>&1); rc=$?
if [ "$rc" != "0" ]; then
  echo "NO MEDIDO: no se pudo leer el journal (rc=$rc): $(printf '%s' "$paradas" | tail -1 | cut -c1-110)"
  exit 2
fi
# EMPAREJAR. Cada `Stopping` se casa con el PRIMER `Started` posterior. Un `Stopping` sin
# `Started` detras es una ventana que sigue abierta -el colector no ha vuelto- y no se
# juzga: sin final no hay segundos caidos que exigir. Un `Started` sin `Stopping` delante
# es el arranque de la maquina y tampoco abre ventana.
ventanas=$(printf '%s\n' "$paradas" | python3 -c '
import re, sys
RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\S*\s.*?(Stopping|Started)")
ini, out, abiertas = None, [], 0
for l in sys.stdin:
    m = RE.match(l)
    if not m:
        continue
    t, que = m.group(1), m.group(2)
    if que == "Stopping":
        if ini is not None:
            abiertas += 1
        ini = t
    elif ini is not None:
        out.append(f"{ini} {t}")
        ini = None
if ini is not None:
    abiertas += 1
print(abiertas)
print("\n".join(out))
' 2>&1); rc=$?
if [ "$rc" != "0" ]; then
  echo "NO MEDIDO: no se pudieron emparejar los marcadores: $(printf '%s' "$ventanas" | tail -1 | cut -c1-110)"
  exit 2
fi
abiertas=$(printf '%s\n' "$ventanas" | head -1)
pares=$(printf '%s\n' "$ventanas" | tail -n +2 | grep -E '^[0-9]{4}' || true)
n_par=$(printf '%s\n' "$pares" | grep -c . || true)

if [ "$n_par" -eq 0 ]; then
  # CERO VENTANAS NO ES CERO DEFECTOS: es que no hay con que medir. Sin ventana no hay
  # segundos caidos, y sin segundos caidos este check no tiene sujeto.
  echo "NO MEDIDO: ninguna ventana Stopping->Started de $UNIT en $DIAS dias: sin sujeto que medir"
  exit 2
fi

# --- 2 · LOS MINUTOS TOCADOS Y SU ENTORNO, EN LA MISMA CONSULTA ------------------------
# Sujeto y control viajan en la misma consulta para que no se pueda mirar uno sin el otro:
# la columna `caido` los separa -mayor que cero es sujeto, cero es control-.
lista=$(printf '%s\n' "$pares" | sed "s/^/('/; s/ /'::timestamptz,'/; s/\$/'::timestamptz)/" | paste -sd, -)
SQL="
WITH v(t0, t1) AS (VALUES $lista),
cand AS (
  SELECT DISTINCT m AS min
  FROM v, generate_series(date_trunc('minute', v.t0) - interval '3 minutes',
                          date_trunc('minute', v.t1) + interval '3 minutes',
                          interval '1 minute') m
),
-- SEGUNDOS DE PARADA QUE CAEN DENTRO DE CADA MINUTO. Si dos ventanas tocasen el mismo
-- minuto se coge el MAXIMO y no la suma: es la eleccion CONSERVADORA -exige menos- y por
-- tanto no puede fabricar un ROJO falso, que es lo unico que no se puede permitir aqui.
-- EL CASE WHEN v.t0 IS NULL NO ES DECORACION. LEAST y GREATEST de PostgreSQL IGNORAN los
-- NULL en vez de propagarlos, asi que sin el CASE un minuto que NINGUNA ventana toca -y que
-- por tanto trae v.t0 y v.t1 a NULL por el LEFT JOIN- calculaba
-- LEAST(NULL, min + 1 min) - GREATEST(NULL, min) = 60 s caidos. Los minutos de control
-- salian como sujetos, el control se quedaba en cero y el check daba NOMED. Lo cazo el
-- propio brazo de control la primera vez que se corrio.
-- (Sin acentos graves: este SQL vive en una cadena entre comillas dobles y bash los
--  ejecutaria como sustitucion de orden. Tambien lo enseño correr el check.)
sol AS (
  SELECT c.min,
         COALESCE(MAX(CASE WHEN v.t0 IS NULL THEN 0 ELSE GREATEST(0, EXTRACT(EPOCH FROM (
             LEAST(v.t1, c.min + interval '1 minute') - GREATEST(v.t0, c.min))))::int END), 0) AS caido
  FROM cand c
  LEFT JOIN v ON v.t1 > c.min AND v.t0 < c.min + interval '1 minute'
  GROUP BY c.min
)
SELECT to_char(s.min,'YYYY-MM-DD\"T\"HH24:MI') AS minuto,
       s.caido                                 AS caido,
       COUNT(a.ts)                             AS filas,
       COALESCE(MAX(a.covered_seconds), -1)    AS cov
FROM sol s
LEFT JOIN $TABLA a ON a.ts = s.min AND a.interval='1min' AND a.exchange<>'combined'
GROUP BY 1,2 ORDER BY 1;
"
salida=$(TODO=1 "$PRODSQL" "$SQL" 2>&1); rc=$?
if [ "$rc" != "0" ] || printf '%s\n' "$salida" | grep -q 'ERROR:'; then
  echo "NO MEDIDO: la consulta fallo (rc=$rc): $(printf '%s\n' "$salida" | grep -m1 'ERROR:' | cut -c1-130)"
  exit 2
fi

filas=$(printf '%s\n' "$salida" | grep -cE '^[[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}[[:space:]]*\|' || true)
if [ "$filas" -eq 0 ]; then
  echo "NO MEDIDO: la consulta no devolvio ninguna fila para las $n_par ventanas"
  echo "  primera linea: $(printf '%s\n' "$salida" | head -1 | cut -c1-100)"
  exit 2
fi

# --- 3 · EL VEREDICTO, Y SU CONTROL ----------------------------------------------------
mentirosos=''; sujetos=0; sanos=0; control_60=0; control_n=0; detalle=''
while IFS='|' read -r min caido nf cov; do
  min=$(printf '%s' "$min" | tr -d ' ');   caido=$(printf '%s' "$caido" | tr -d ' ')
  nf=$(printf '%s' "$nf" | tr -d ' ');     cov=$(printf '%s' "$cov" | tr -d ' ')
  [ -n "$min" ] || continue
  # Sin fila no hay nada que juzgar: ese es el caso AUSENTE, que ya se arreglo, y aqui no
  # es el sujeto. Vale igual para el control.
  [ "${nf:-0}" -gt 0 ] && [ "${cov:--1}" -ge 0 ] || continue
  if [ "${caido:-0}" -eq 0 ]; then
    # CONTROL · minuto que ninguna ventana toca. Tiene que poder decir 60.
    control_n=$((control_n+1))
    [ "$cov" -eq 60 ] && control_60=$((control_60+1))
    continue
  fi
  sujetos=$((sujetos+1))
  permitido=$((60 - caido))
  if [ "$cov" -gt "$permitido" ]; then
    # UNA LINEA POR MINUTO, no separado por espacios: el detalle lleva espacios dentro y
    # contando por palabras salian 3 mentirosos donde hay 1.
    mentirosos="${mentirosos}${min} caido=${caido}s permite<=${permitido} dice=${cov}
"
  else
    sanos=$((sanos+1))
    detalle="$detalle ${min}(caido=${caido}s cov=${cov})"
  fi
done <<EOF
$(printf '%s\n' "$salida" | grep -E '^[[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}[[:space:]]*\|')
EOF

if [ "$sujetos" -eq 0 ]; then
  echo "NO MEDIDO: ninguna de las $n_par ventanas toca un minuto CON fila: sin sujeto"
  exit 2
fi

# CONTROL · HUELLA POSITIVA. Si ningun minuto intacto llega a 60, la tabla va corta por
# todas partes y un minuto corto junto a una parada no seria atribuible a la parada.
if [ "$control_60" -eq 0 ]; then
  echo "NO MEDIDO: de $control_n minuto(s) que ninguna ventana toca, NINGUNO declara 60:"
  echo "  la tabla va corta por otra razon y el hallazgo no seria atribuible a la parada"
  exit 2
fi

if [ -n "$mentirosos" ]; then
  n=$(printf '%s' "$mentirosos" | grep -c . || true)
  echo "$n minuto(s) de $TABLA declaran MAS cobertura de la que su ventana de parada permite:"
  printf '%s' "$mentirosos" | grep . | head -6 | sed 's/^/  /'
  echo "  sobre $sujetos minuto(s) tocados por $n_par ventana(s) en $DIAS dias · $sanos correcto(s)"
  echo "  control: $control_60 de $control_n minutos intactos declaran 60, luego la tabla SABE decir completo"
  echo "  se arregla en quien escribe la pata, NO en el MIN del combinado"
  exit 1
fi

echo "los $sujetos minuto(s) tocados por $n_par ventana(s) declaran cobertura compatible con su parada"
echo "  control: $control_60 de $control_n minutos intactos declaran 60"
echo " $detalle"
exit 0
