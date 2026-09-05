#!/bin/bash
# K90  LA SENAL DE CORTO NO PERSISTE LO QUE SU ROTULO DECLARA.
#
# EL SUJETO NO ES UNA RUTA: ES UN PAR. La tarjeta de corto del panel anuncia un horizonte
# -"1-15 minutos"- y el calculo que la alimenta no tiene ninguna memoria. Ni la ruta ni el
# rotulo estan mal por separado: lo que esta mal es la pareja. Por eso el check mide los
# dos lados y ninguno de ellos solo.
#
#   el CALCULO   scalp_bias_label (app/scalp_logic.py:292-313) es una funcion pura de los
#                dos scores del instante. Censo completo de persist|hysteresis|debounce|
#                cooldown|estabil en sus 6170 lineas: ninguna es un mecanismo de duracion.
#                El colector recalcula cada 10 s (SCALP_SIGNAL_INTERVAL_SECONDS, config.py:188).
#   el ROTULO    static/app.js:1435, `time: '1-15 minutos'`, sobre scalp.state, que llega
#                por /api/dashboard/state (app.js:1362 y :1491) -no por /api/scalp/summary,
#                que es el mismo calculo por otra puerta-.
#
# POR QUE EL CHECK LEE EL ROTULO EN VEZ DE LLEVAR EL 8 ESCRITO.
# El umbral sale del rotulo, asi que clavarlo aqui seria congelar en el check una decision
# que vive en el panel. Si manana el rotulo dice "instantanea", el defecto desaparece y
# este check TIENE QUE PONERSE VERDE SOLO; si dice "5-30 minutos", el umbral sube con el.
# Un check con el numero grabado seguiria en rojo despues de arreglado, y un check que
# miente en rojo se apaga igual de rapido que uno que miente en verde.
#
# MEDIDO EL 2026-09-05 (operador, prodsql, 30 dias de signal_observation periodica):
#   p90 de la racha ACCIONABLE   BTC 3 · ETH 3 · SOL 4      <- los tres por debajo de 8
#   p90 de la racha NO accionable BTC 6 · ETH 6 · SOL 11    <- el control, por encima
#   cardinalidad 34356 filas = 34356 minutos en cada simbolo
# El control importa tanto como el hallazgo: si los dos lados salieran igual de cortos, el
# sujeto seria el muestreo y no la senal.
set -uo pipefail
B=/srv/coinanalyze/harness
# EL REPO RECIBIDO SE GUARDA ANTES DE CARGAR env, porque harness/env define REPO= y PISA
# lo que traiga el entorno. Se cazo con el caso F4 del control: se le pasaba un arbol de
# prueba con histeresis inyectada, el env lo sustituia por /srv/coinanalyze/repo, y el
# check media el arbol REAL creyendo medir el de prueba -o sea, un caso que no ejercitaba
# nada y ademas daba el veredicto de otro sujeto-.
_repo_pedido=${REPO:-}
[ -r "$B/env" ] && . "$B/env"
REPO=${_repo_pedido:-${REPO:-/srv/coinanalyze/repo}}
APPJS=${K90_APPJS:-$REPO/static/app.js}
PRODSQL=${K90_PRODSQL:-$B/bin/prodsql}
DIAS=${K90_DIAS:-30}

# --- 1 · EL ROTULO. Si no esta, no hay promesa que incumplir. --------------------------
[ -r "$APPJS" ] || { echo "NO MEDIDO: no encuentro $APPJS"; exit 2; }

# Se busca la tarjeta de corto plazo y su campo `time`. El guion puede ser '-' o el largo
# '–' (que es el que hay hoy en app.js:1435), y los dos tienen que casar: buscar solo uno
# haria que el check enrojeciera o enverdeciera por un caracter tipografico.
rotulo=$(grep -oE "name: *'Corto plazo', *time: *'[^']+'" "$APPJS" | head -1 \
         | sed "s/.*time: *'//; s/'$//")
if [ -z "$rotulo" ]; then
  # sin la tarjeta, o con otro nombre: NO es verde ni rojo, es que no se puede juzgar.
  echo "NO MEDIDO: no encuentro la tarjeta 'Corto plazo' con su campo time en $APPJS"
  echo "  si la tarjeta se retiro, este check sobra; si se renombro, hay que actualizarlo"
  exit 2
fi

lo=$(printf '%s' "$rotulo" | grep -oE '[0-9]+' | head -1)
hi=$(printf '%s' "$rotulo" | grep -oE '[0-9]+' | sed -n 2p)
if [ -z "$lo" ] || [ -z "$hi" ]; then
  # EL ROTULO YA NO PROMETE UN RANGO. Es la salida VERDE por cambio de producto: si dice
  # "instantanea" o "lectura del momento", no hay horizonte que incumplir.
  echo "el rotulo de la tarjeta de corto es '$rotulo': no anuncia un rango de minutos, asi que no hay horizonte que incumplir"
  exit 0
fi
umbral=$(( (lo + hi) / 2 ))

# --- 2 · EL CALCULO. Que siga sin memoria es la otra mitad del sujeto. -----------------
SL="$REPO/app/scalp_logic.py"
[ -r "$SL" ] || { echo "NO MEDIDO: no encuentro $SL"; exit 2; }
# -i NO es un detalle: las constantes de este repo van en MAYUSCULAS
# (SCALP_SIGNAL_INTERVAL_SECONDS, LIQUIDATION_INSERT_SQL), asi que un futuro
# HYSTERESIS_MINUTES no habria casado sin ella y el check habria seguido afirmando "no hay
# memoria" sobre un calculo que ya la tiene. Lo cazo el caso F4 del control.
mecanismos=$(grep -ciE "hysteresis|histeresis|debounce|min_duration|dwell_minutes|cooldown|min_hold" "$SL")
if [ "$mecanismos" -gt 0 ]; then
  # Alguien le ha puesto memoria al estado. El defecto puede estar arreglado por el otro
  # lado, y este check no puede seguir afirmando lo mismo sin volver a mirar.
  echo "NO MEDIDO: $SL ya tiene $mecanismos posible(s) mecanismo(s) de persistencia; hay que releer el criterio antes de juzgar"
  exit 2
fi

# --- 3 · LA MEDIDA. Por simbolo, con la cardinalidad como control. ---------------------
[ -x "$PRODSQL" ] || { echo "NO MEDIDO: no hay canal a produccion ($PRODSQL)"; exit 2; }

# LA COLUMNA ES observed_minute, NO ts. Y NO NECESITA date_trunc.
# La primera version de este check pedia `ts`, que NO EXISTE en signal_observation: las
# reales son `observed_at` (timestamptz) y `observed_minute` (ya truncada al minuto).
# Resultado: `ERROR: column "ts" does not exist`, que con el prodsql viejo llegaba como
# rc=0 y salida vacia, o sea que el check decia "no devolvio ninguna fila" -un diagnostico
# falso- en vez de "la consulta esta rota". Los DOS defectos se tapaban entre si.
SQL="
WITH base AS (
  SELECT symbol,
         observed_minute          AS m,
         (actionable IS TRUE)     AS acc
  FROM signal_observation
  WHERE is_periodic IS TRUE
    AND observed_minute >= now() - interval '$DIAS days'
),
u AS (SELECT DISTINCT symbol, m, acc FROM base),
g AS (
  SELECT symbol, m, acc,
         (EXTRACT(EPOCH FROM m)/60)::bigint
           - ROW_NUMBER() OVER (PARTITION BY symbol, acc ORDER BY m) AS grupo
  FROM u
),
ep AS (
  SELECT symbol, acc, COUNT(*) AS minutos
  FROM g GROUP BY symbol, acc, grupo
)
SELECT e.symbol,
       COUNT(*) FILTER (WHERE e.acc)                                           AS ep_acc,
       COALESCE(percentile_disc(0.9) WITHIN GROUP (ORDER BY e.minutos)
                FILTER (WHERE e.acc), 0)                                       AS p90_acc,
       COALESCE(percentile_disc(0.9) WITHIN GROUP (ORDER BY e.minutos)
                FILTER (WHERE NOT e.acc), 0)                                   AS p90_noacc,
       (SELECT COUNT(*) FROM u WHERE u.symbol = e.symbol)                      AS minutos_total
FROM ep e GROUP BY e.symbol ORDER BY e.symbol;
"

salida=$(TODO=1 "$PRODSQL" "$SQL" 2>&1); rc=$?

# EL rc NO BASTA, Y HASTA HOY NO SERVIA DE NADA. `prodsql` devolvia 0 aunque el SQL
# fallara -el rc se perdia en su pipe final- asi que este guardia era decorativo. Se
# arreglo el canal, pero el check mira TAMBIEN la salida: es el consumidor quien no puede
# permitirse confiar en que el canal este arreglado, y un `ERROR:` de psql viaja mezclado
# con las filas por el 2>&1.
if [ "$rc" != "0" ] || printf '%s\n' "$salida" | grep -q '^ERROR:'; then
  echo "NO MEDIDO: la consulta fallo (rc=$rc): $(printf '%s\n' "$salida" | grep -m1 '^ERROR:' | cut -c1-140)"
  echo "  ${salida:+salida: }$(printf '%s' "$salida" | tail -1 | cut -c1-100)"
  exit 2
fi

# EL SIMBOLO DE ESTA CASA ES BTCUSDT_PERP.A, NO BTCUSDT.
# El detector anterior era '^[[:space:]]*[A-Z0-9]+USDT[[:space:]]*\|' y exigia que tras
# USDT viniera el separador. Aqui viene `_PERP.A`, asi que reconocia 0 de 2 filas reales y
# 1 de 1 de las inventadas — o sea que el control lo daba por bueno y produccion no. Ahora
# se acepta cualquier sufijo hasta la barra, y las DOS formas van como control del check.
filas=$(printf '%s\n' "$salida" | grep -cE '^[[:space:]]*[A-Z][A-Z0-9]*USDT[A-Za-z0-9_.:-]*[[:space:]]*\|')
if [ "$filas" -eq 0 ]; then
  # CERO FILAS NO ES CERO MEDIDO. Es la leccion de K60: sin filas no hay veredicto.
  echo "NO MEDIDO: la consulta no devolvio ninguna fila de simbolo reconocible"
  echo "  primera linea de la salida: $(printf '%s\n' "$salida" | head -1 | cut -c1-100)"
  exit 2
fi

rojos=''; detalle=''; sospecha=''
while IFS='|' read -r sym ep p90a p90n mins; do
  sym=$(printf '%s' "$sym" | tr -d ' '); [ -n "$sym" ] || continue
  ep=$(printf '%s' "$ep" | tr -d ' '); p90a=$(printf '%s' "$p90a" | tr -d ' ')
  p90n=$(printf '%s' "$p90n" | tr -d ' '); mins=$(printf '%s' "$mins" | tr -d ' ')
  detalle="$detalle $sym:p90a=$p90a/p90n=$p90n(n=$ep,min=$mins)"
  # CONTROL EN LA MISMA CONSULTA: si el lado NO accionable fuera igual de corto, el sujeto
  # seria el muestreo y no la senal, y el hallazgo no se sostendria.
  if [ "$p90a" -lt "$umbral" ] && [ "$p90n" -le "$p90a" ]; then
    sospecha="$sospecha $sym"
  elif [ "$p90a" -lt "$umbral" ]; then
    rojos="$rojos $sym"
  fi
done <<EOF
$(printf '%s\n' "$salida" | grep -E '^[[:space:]]*[A-Z][A-Z0-9]*USDT[A-Za-z0-9_.:-]*[[:space:]]*\|')
EOF

if [ -n "$sospecha" ]; then
  echo "NO MEDIDO: en$sospecha el lado NO accionable es igual de corto que el accionable: el sujeto seria el muestreo, no la senal"
  echo "  detalle:$detalle"
  exit 2
fi

if [ -n "$rojos" ]; then
  n=$(printf '%s' "$rojos" | wc -w)
  echo "el rotulo dice '$rotulo' (umbral $umbral min) y en$rojos el p90 de la racha accionable no llega: $n simbolo(s) sobre $DIAS dias"
  echo "  detalle:$detalle"
  echo "  se cierra dando persistencia a scalp_bias_label o cambiando el rotulo; es decision de producto"
  exit 1
fi

echo "el rotulo dice '$rotulo' (umbral $umbral min) y el p90 accionable lo alcanza en los $filas simbolos:$detalle"
exit 0
