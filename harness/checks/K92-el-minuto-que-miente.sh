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
# EL CONTROL VA EN LA MISMA CONSULTA: el minuto SIGUIENTE a una parada tiene que salir
# **ausente o corto**. Si los dos salieran completos, el sujeto seria el registro de paradas
# -o el reloj- y no la cobertura, y el hallazgo no se sostendria.
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

# --- 1 · EL ELEGIBLE · las paradas, del JOURNAL --------------------------------------
# `Stopped` es la linea que systemd escribe al terminar la unidad. Se piden con -n acotado
# a proposito: un journalctl sin limite es la forma mas rapida de arruinar una sesion.
paradas=$("$PROD" "journalctl -u $UNIT --since '-$DIAS days' --utc -o short-iso --no-hostname -n 2000 | grep -E 'Stopped|Deactivated successfully'" 2>&1); rc=$?
if [ "$rc" != "0" ]; then
  echo "NO MEDIDO: no se pudo leer el journal (rc=$rc): $(printf '%s' "$paradas" | tail -1 | cut -c1-110)"
  exit 2
fi
inst=$(printf '%s\n' "$paradas" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}' | sort -u)
n_par=$(printf '%s\n' "$inst" | grep -c . || true)

if [ "$n_par" -eq 0 ]; then
  # CERO PARADAS NO ES CERO DEFECTOS: es que no hay con que medir. Sin parada no hay
  # minuto de parada, y sin minuto de parada este check no tiene sujeto.
  echo "NO MEDIDO: ninguna parada de $UNIT en $DIAS dias: sin sujeto que medir"
  exit 2
fi

# --- 2 · EL MINUTO DE LA PARADA Y EL SIGUIENTE, EN LA MISMA CONSULTA -------------------
# Se construye una lista de instantes y se pregunta por los dos minutos de cada uno. El
# control -el minuto siguiente- viaja en la misma fila para que no se pueda mirar uno sin
# el otro.
lista=$(printf '%s\n' "$inst" | sed "s/^/('/; s/\$/'::timestamptz)/" | paste -sd, -)
SQL="
WITH paradas(t) AS (VALUES $lista),
m AS (
  SELECT date_trunc('minute', t) AS min_parada,
         date_trunc('minute', t) + interval '1 minute' AS min_siguiente,
         EXTRACT(SECOND FROM t)::int AS seg
  FROM paradas
)
SELECT to_char(m.min_parada,'YYYY-MM-DD\"T\"HH24:MI') AS parada,
       m.seg                                          AS segundo,
       MAX(a.covered_seconds)                         AS cov_parada,
       MAX(b.covered_seconds)                         AS cov_siguiente,
       COUNT(a.ts)                                    AS filas_parada,
       COUNT(b.ts)                                    AS filas_siguiente
FROM m
LEFT JOIN $TABLA a ON a.ts = m.min_parada    AND a.interval='1min' AND a.exchange<>'combined'
LEFT JOIN $TABLA b ON b.ts = m.min_siguiente AND b.interval='1min' AND b.exchange<>'combined'
GROUP BY 1,2 ORDER BY 1;
"
salida=$(TODO=1 "$PRODSQL" "$SQL" 2>&1); rc=$?
if [ "$rc" != "0" ] || printf '%s\n' "$salida" | grep -q 'ERROR:'; then
  echo "NO MEDIDO: la consulta fallo (rc=$rc): $(printf '%s\n' "$salida" | grep -m1 'ERROR:' | cut -c1-130)"
  exit 2
fi

filas=$(printf '%s\n' "$salida" | grep -cE '^[[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}[[:space:]]*\|' || true)
if [ "$filas" -eq 0 ]; then
  echo "NO MEDIDO: la consulta no devolvio ninguna fila para las $n_par paradas"
  echo "  primera linea: $(printf '%s\n' "$salida" | head -1 | cut -c1-100)"
  exit 2
fi

# --- 3 · EL VEREDICTO, Y SU CONTROL ----------------------------------------------------
mentirosos=''; sospecha=''; sanos=0; detalle=''
while IFS='|' read -r par seg covp covs fp fs; do
  par=$(printf '%s' "$par" | tr -d ' '); seg=$(printf '%s' "$seg" | tr -d ' ')
  covp=$(printf '%s' "$covp" | tr -d ' '); covs=$(printf '%s' "$covs" | tr -d ' ')
  fp=$(printf '%s' "$fp" | tr -d ' '); fs=$(printf '%s' "$fs" | tr -d ' ')
  [ -n "$par" ] || continue
  # Sin fila en el minuto de la parada no hay nada que juzgar: ese es el caso AUSENTE, que
  # ya se arreglo, y aqui no es el sujeto.
  [ "${fp:-0}" -gt 0 ] || continue
  detalle="$detalle ${par}(s=$seg cov=$covp sig=${covs:-ausente})"
  # CONTROL: si el minuto SIGUIENTE tambien sale completo, el sujeto no es la cobertura.
  if [ "${fs:-0}" -gt 0 ] && [ "${covs:-0}" = "60" ]; then
    sospecha="$sospecha $par"
  elif [ "$covp" = "60" ] && [ "${seg:-0}" -gt 0 ]; then
    # el minuto de la parada dice 60 y la parada ocurrio DENTRO de el
    mentirosos="$mentirosos $par"
  else
    sanos=$((sanos+1))
  fi
done <<EOF
$(printf '%s\n' "$salida" | grep -E '^[[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}[[:space:]]*\|')
EOF

if [ -n "$sospecha" ]; then
  n=$(printf '%s' "$sospecha" | wc -w)
  echo "NO MEDIDO: en $n parada(s) el minuto SIGUIENTE tambien sale completo: el sujeto seria el registro de paradas, no la cobertura"
  echo "  $detalle"
  exit 2
fi

if [ -n "$mentirosos" ]; then
  n=$(printf '%s' "$mentirosos" | wc -w)
  echo "$n minuto(s) de $TABLA dicen covered_seconds=60 con el colector parado dentro: $mentirosos"
  echo "  sobre $filas parada(s) con fila, de $n_par paradas en $DIAS dias · $sanos correcto(s)"
  echo "  se arregla en quien escribe la pata, NO en el MIN del combinado"
  exit 1
fi

echo "las $filas parada(s) con fila declaran su cobertura corta (de $n_par paradas en $DIAS dias)"
echo "  $detalle"
exit 0
