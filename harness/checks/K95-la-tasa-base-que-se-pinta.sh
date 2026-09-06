#!/bin/bash
# K95  LA CIFRA QUE LA TARJETA PINTA TIENE QUE SALIR DE signal_outcome, Y COINCIDIR.
#
# POR QUE EXISTE. Esta es la primera vuelta en siete paquetes en que el trabajo cambia lo que
# un trader VE. Una tarjeta que publica una tasa base es una promesa: si el numero que se
# pinta no es el que sale de la tabla, el producto miente con mas autoridad que antes de
# tener tarjeta. Lo que este check compara son DOS CAMINOS al mismo hecho.
#
# DEFINICION, ANTES DE NINGUN COMANDO.
#   *tasa base de la señal* = sobre los minutos periodicos de un simbolo, en el arco que el
#   propio payload declara, y para el horizonte que declara:
#     ventaja bruta   dentro de cada bloque de H minutos, media(retorno direccional de los
#                     minutos ACCIONABLES) menos signo x media(retorno de mercado de los NO
#                     accionables); promediada sobre los bloques con los dos lados presentes.
#     coste de entrada  media, con el signo del lado, de (precio de referencia - precio medio
#                     del bloque) / precio medio del bloque.
#     ventaja neta    la misma comparacion midiendo el retorno DESDE el precio medio del
#                     bloque en vez de desde el precio de entrada.
#     n efectiva      numero de BLOQUES con los dos lados. No es una formula: es un recuento.
#
# LOS DOS BRAZOS, y por que son dos:
#   A · la consulta que la ruta lleva dentro (`BASE_RATE_SQL`, extraida de app/api.py y no
#       tecleada aqui) contra otra escrita EN ESTE FICHERO desde la definicion de arriba.
#       Prueba que la formula publicada es la formula de la definicion.
#   B · el payload VIVO de /api/dashboard/state contra el brazo A, sobre LA VENTANA que el
#       propio payload declara (`ventana_pedida_desde`/`_hasta`) y CONGELANDO el estado de
#       evaluacion en su `as_of`. Las dos cosas juntas son lo que hace la comparacion una
#       IGUALDAD EXACTA en vez de una tolerancia inventada.
#
# LO QUE PASA MIENTRAS NO ESTE DESPLEGADO, y se dice en vez de callarse: si 140 todavia no
# publica el bloque, el brazo B no tiene sujeto. Eso NO es un fallo del arreglo y NO enrojece
# -es el mismo distingo que hace K80 entre "no funciona" y "falta desplegar"-, pero SI se
# publica en el mensaje. Y en cuanto el bloque exista, el brazo B pasa a ser exigible solo:
# si esta y no cuadra, es ROJO. El check se vuelve mas estricto sin que nadie lo toque.
#
# DE QUE ARBOL: el brazo A saca la consulta del REPO y la corre contra 140; el brazo B pide a
# 140 por la API. El VERDE exige A, y B cuando haya sujeto.
set -uo pipefail
B=/srv/coinanalyze/harness; [ -r "$B/env" ] && . "$B/env"
REPO=${K95_REPO:-${REPO:-/srv/coinanalyze/repo}}
API=$REPO/app/api.py
[ -r "$API" ] || { echo "NO MEDIDO: no se puede leer $API, de donde sale la consulta de la ruta"; exit 2; }
grep -q 'BASE_RATE_SQL' "$API" || { echo "NO MEDIDO: app/api.py no define BASE_RATE_SQL: la ruta ya no publica la tasa base por este camino"; exit 2; }

# NO HAY TOLERANCIA, Y ESO ES EL ARREGLO.
#
# LA HABIA: `TOL=0.0001`, con el comentario «se comparan con esa misma resolucion». Y era el
# defecto: con un margen EXACTAMENTE IGUAL al paso de la resolucion, dos valores que difieren
# en UNA unidad del ultimo decimal caen justo en el borde y el binario decide por el error de
# coma flotante — `abs(-0.053 - (-0.0531)) = 0.00010000000000000286 > 0.0001`. Medido por el
# operador sobre 2 000 valores del rango real: **1 482 de los pares que difieren en una unidad
# del cuarto decimal fallan la comparacion, el 74.1 %**.
#
# SUBIR EL MARGEN LO ESCONDERIA Y ADEMAS AFLOJARIA EL CHECK. La causa no era el margen: era que
# los dos lados podian diferir de verdad. Congelado el estado de evaluacion (ver abajo), los
# dos lados ven el MISMO conjunto y la comparacion pasa a ser una IGUALDAD. Se compara en
# decimal exacto, no en coma flotante: los dos valores salen de un `ROUND(...,4)`, asi que son
# decimales de cuatro cifras y `Decimal("-0.0531") == Decimal("-0.0531")` es una igualdad.

# --- el arco. Se toma del payload si lo hay, y si no del reloj -------------------------
# TODO=1 NO ES OPCIONAL AQUI, Y ME MORDIO: `bin/api` corta la salida a 8 KB y el payload de
# /api/dashboard/state pasa de eso. Sin TODO=1 llega un JSON truncado, `json.load` revienta y
# el check publicaba «/api/dashboard/state no contesto en 140» — que es falso: contesto, y
# entero. Un instrumento que deja de medir con un mensaje que nombra otra causa es
# exactamente lo que este arnes lleva una semana cazando, cometido aqui por mi.
PAY=$(TODO=1 "$B/bin/api" "/api/dashboard/state?symbol=BTCUSDT_PERP.A" 2>/dev/null)
LEIDO=$(printf '%s' "$PAY" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('SIN_PAYLOAD'); raise SystemExit
b=d.get('signal_base_rate')
if not isinstance(b,dict): print('SIN_BLOQUE'); raise SystemExit
if not b.get('available'): print('NO_DISPONIBLE|'+str(b.get('motivo'))); raise SystemExit
print('|'.join(str(b.get(k)) for k in ('ventana_pedida_desde','ventana_pedida_hasta','horizonte_min',
      'ventaja_bruta_pct','ventaja_neta_pct','coste_entrada_pct','n_efectiva','observaciones','as_of')))
" 2>/dev/null)

case "$LEIDO" in
  SIN_PAYLOAD) echo "NO MEDIDO: /api/dashboard/state no contesto en 140"; exit 2 ;;
esac

if [ "$LEIDO" = "SIN_BLOQUE" ]; then
  DESPLEGADO=no
  # arco de referencia para el brazo A: 30 dias hasta ahora, que es lo que la ruta pediria
  A_HASTA=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  A_DESDE=$(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ)
  CORTE=$A_HASTA
  HOR=60
else
  DESPLEGADO=si
  IFS='|' read -r A_DESDE A_HASTA HOR P_BRUTA P_NETA P_ENTRADA P_NEF P_OBS CORTE <<EOF
$LEIDO
EOF
fi

# EL ESTADO DE EVALUACION SE CONGELA, Y ESTA ES LA MITAD DE ESTE REMATE.
#
# EL DEFECTO, encontrado por el operador el 2026-09-06 a las 18:19Z: K95 corrido cinco veces
# seguidas sobre el mismo arbol y la misma base daba rc=0, 0, 0, 1, 1. El payload era estable;
# lo que se movia era la RECOMPUTACION. El arco si estaba fijado, pero el ESTADO no: la
# consulta exige `o.status='evaluated'`, y un minuto de DENTRO del arco cuyo horizonte de 60
# min se completa DESPUES de calcularse el payload entra en la recomputacion y no estaba en el
# payload. Medido: 24 filas se evaluan cada 5 min y 309 cada hora, sobre 13 843 -y el corte de
# 5 min mueve `observaciones` de 13 843 a 13 842 y la `t` de 0.074 a 0.073-. Justo el orden del
# ultimo decimal publicado.
#
# LA ELECCION, y es la rama (a): CONGELAR, no tolerar. K95 afirma que la cifra pintada ES la
# que sale de la tabla. Si acepto que los dos lados pueden diferir, lo mas que puedo afirmar es
# «se parecen», y eso exige un umbral que hay que rejustificar cada vez que cambie el volumen o
# el horizonte: una constante con fecha de caducidad y sin nadie vigilandola. Congelar hace la
# comparacion EXACTA y elimina el umbral en vez de calibrarlo.
#
# `finalized_at <= as_of` reproduce EXACTAMENTE el conjunto que el payload vio: el payload
# filtra `status='evaluated'` en el instante de su calculo, y esas son las filas cuyo
# `finalized_at` es anterior a ese instante. MEDIDO ANTES DE APOYARME EN ELLO: de las 165 055
# filas `evaluated` de horizonte 60, **cero** tienen `finalized_at` nulo (las 520 nulas son
# todas `pending`, que este filtro ya excluye).
#
# Y SE ARREGLA UNA SEGUNDA FUGA QUE ENCONTRE AL MIRAR ESTO: el brazo B pasaba
# `arco_desde`/`arco_hasta` -el minimo y el maximo REALES observados- como si fueran la ventana
# que la ruta pidio. No lo son: la ruta filtra por `ventana_pedida_*`, y `observed_at <
# arco_hasta` excluye justo la ultima observacion, que en el payload SI estaba. Una fila de
# 13 843, o sea otra vez el cuarto decimal. Ahora se usan las dos claves que el payload publica
# para eso.
CONGELA="AND o.finalized_at <= '$CORTE'::timestamptz"

# --- BRAZO A · la consulta DE LA RUTA, extraida del repo -------------------------------
SQL_RUTA=$(python3 - "$API" "$A_DESDE" "$A_HASTA" "$HOR" "$CONGELA" <<'PY'
import sys, pathlib
t = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
sql = t.split('BASE_RATE_SQL = """')[1].split('"""')[0]
# el congelado se inyecta JUNTO al filtro de estado, que es donde esta la fuga
viejo = "AND o.status = 'evaluated'"
if viejo not in sql:
    sys.exit("K95: no encuentro el filtro de estado en BASE_RATE_SQL")
sql = sql.replace(viejo, viejo + " " + sys.argv[5], 1)
print(sql.replace("$1", "'BTCUSDT_PERP.A'")
         .replace("$2", f"'{sys.argv[2]}'::timestamptz")
         .replace("$3", f"'{sys.argv[3]}'::timestamptz")
         .replace("$4", sys.argv[4]))
PY
) || { echo "NO MEDIDO: no se pudo preparar la consulta de la ruta ($?)"; exit 2; }
R_RUTA=$(TODO=1 "$B/bin/prodsql" "$SQL_RUTA" 2>/dev/null | head -1)
case "$R_RUTA" in
  *'|'*'|'*'|'*) ;;
  *) echo "NO MEDIDO: la consulta de la ruta no devolvio fila contra 140 (salio '$R_RUTA')"; exit 2 ;;
esac

# --- BRAZO A (bis) · la MIA, escrita aqui desde la definicion ---------------------------
# NO es una copia: agrupa por lado y promedia los dos al final, en vez de mezclarlos en el
# mismo GROUP BY. Si las dos formas de escribirlo no dieran lo mismo, una de las dos no seria
# la definicion de arriba. LO QUE ESTE BRAZO NO PRUEBA, y lo digo: las dos consultas leen las
# mismas columnas de las mismas tablas, asi que un error EN LA DEFINICION saldria igual en las
# dos. Prueba la traduccion, no la eleccion.
SQL_MIA="
WITH p AS (
  SELECT s.direction, s.actionable, s.reference_price, o.end_price,
         o.directional_return_pct, o.market_return_pct,
         (EXTRACT(EPOCH FROM o.window_start)/60/$HOR)::bigint AS blk
  FROM signal_outcome o JOIN signal_observation s ON s.observation_id=o.observation_id
  WHERE s.symbol='BTCUSDT_PERP.A' AND s.is_periodic IS TRUE AND o.status='evaluated' $CONGELA
    AND o.horizon_minutes=$HOR AND o.end_price IS NOT NULL AND s.reference_price IS NOT NULL
    AND s.observed_at >= '$A_DESDE'::timestamptz AND s.observed_at < '$A_HASTA'::timestamptz
), pm AS (SELECT blk, AVG(reference_price) pm FROM p GROUP BY 1),
l AS (SELECT p.blk, AVG(p.directional_return_pct) br,
             AVG(100.0*(p.end_price-m.pm)/m.pm) ne, AVG(100.0*(p.reference_price-m.pm)/m.pm) en,
             COUNT(*) n
      FROM p JOIN pm m ON m.blk=p.blk WHERE p.actionable IS TRUE AND p.direction='long'
      GROUP BY 1),
c AS (SELECT p.blk, AVG(p.directional_return_pct) br,
             AVG(-100.0*(p.end_price-m.pm)/m.pm) ne, AVG(-100.0*(p.reference_price-m.pm)/m.pm) en,
             COUNT(*) n
      FROM p JOIN pm m ON m.blk=p.blk WHERE p.actionable IS TRUE AND p.direction='short'
      GROUP BY 1),
b AS (SELECT p.blk, AVG(p.market_return_pct) br, AVG(100.0*(p.end_price-m.pm)/m.pm) ne
      FROM p JOIN pm m ON m.blk=p.blk WHERE p.actionable IS NOT TRUE GROUP BY 1),
u AS (SELECT l.blk, l.n, l.br-b.br AS d_br, l.ne-b.ne AS d_ne, l.en FROM l JOIN b ON b.blk=l.blk
      UNION ALL
      SELECT c.blk, c.n, c.br+b.br AS d_br, c.ne+b.ne AS d_ne, c.en FROM c JOIN b ON b.blk=c.blk),
-- UNA FILA POR BLOQUE, NO POR (bloque, lado). La primera version de este check agrupaba
-- igual que la ruta -por par- asi que las dos coincidian EN EL MISMO ERROR y el check no
-- podia cazarlo: 1 191 pares publicados como si fueran 1 191 bloques, cuando son 604.
-- Lo encontro el operador, no este check, y es literalmente el riesgo que la cabecera de
-- este fichero declara: «las dos consultas leen las mismas columnas de las mismas tablas».
-- Ahora el check agrupa por bloque POR SU CUENTA, asi que si la ruta volviera a contar
-- pares, los recuentos dejarian de cuadrar.
w AS (SELECT blk, SUM(n) n, AVG(d_br) d_br, AVG(d_ne) d_ne, AVG(en) en FROM u GROUP BY blk)
SELECT COUNT(*), SUM(n), ROUND(AVG(d_br)::numeric,4), ROUND(AVG(d_ne)::numeric,4),
       ROUND(AVG(en)::numeric,4)
FROM w"
R_MIA=$(TODO=1 "$B/bin/prodsql" "$SQL_MIA" 2>/dev/null | head -1)
case "$R_MIA" in
  *'|'*'|'*'|'*) ;;
  *) echo "NO MEDIDO: mi consulta no devolvio fila contra 140 (salio '$R_MIA')"; exit 2 ;;
esac

# IGUALDAD DECIMAL EXACTA, sin epsilon. `Decimal` y no `float`: `float('-0.053')` y
# `float('-0.0531')` arrastran el error binario que produjo el parpadeo, y aqui no hay ninguna
# razon para pagarlo -los dos lados son decimales de cuatro cifras salidos de un ROUND-.
# Se normaliza para que «-0.053» y «-0.0530» sean el mismo numero, que es lo que son: el
# payload los serializa como float de JSON y el SQL como texto, y la representacion no es el
# valor. Un valor que no se pueda leer como decimal falla, no pasa: `None` no es igual a nada.
cmp3() { python3 -c "
import sys
from decimal import Decimal, InvalidOperation
try:
    a, b = Decimal('$1'), Decimal('$2')
except InvalidOperation:
    sys.exit(1)
sys.exit(0 if a == b else 1)"; }

FALLOS=""
# EL ORDEN DE LAS COLUMNAS SE COMPRUEBA ANTES DE LEERLAS. Al añadir `pares_bloque_lado` a la
# consulta de la ruta, todos los `cut -f` se corrieron una posicion y el check comparo
# ventaja_bruta contra el recuento de bloques: publico «1191 != -0.0535», que es un ROJO
# cierto por una razon falsa. Un check que lee por posicion tiene que verificar la posicion.
N_COLS=$(printf '%s' "$R_RUTA" | tr '|' '\n' | grep -c .)
[ "$N_COLS" -eq 10 ] || {
  echo "NO MEDIDO: la consulta de la ruta devuelve $N_COLS columnas y este check espera 10 en un orden fijo (bloques, observaciones, pares, bruta, neta, entrada, entrada_obs, t, arco_desde, arco_hasta). Si el orden cambio, hay que actualizar el check y NO adivinar"
  exit 2
}
RU_NEF=$(echo "$R_RUTA" | cut -d'|' -f1); RU_OBS=$(echo "$R_RUTA" | cut -d'|' -f2)
RU_BR=$(echo "$R_RUTA" | cut -d'|' -f4);  RU_NE=$(echo "$R_RUTA" | cut -d'|' -f5)
RU_EN=$(echo "$R_RUTA" | cut -d'|' -f6)
MI_NEF=$(echo "$R_MIA" | cut -d'|' -f1);  MI_OBS=$(echo "$R_MIA" | cut -d'|' -f2)
MI_BR=$(echo "$R_MIA" | cut -d'|' -f3);   MI_NE=$(echo "$R_MIA" | cut -d'|' -f4)
MI_EN=$(echo "$R_MIA" | cut -d'|' -f5)

[ "$RU_NEF" = "$MI_NEF" ] || FALLOS="$FALLOS n_efectiva($RU_NEF!=$MI_NEF)"
[ "$RU_OBS" = "$MI_OBS" ] || FALLOS="$FALLOS observaciones($RU_OBS!=$MI_OBS)"
cmp3 "$RU_BR" "$MI_BR" || FALLOS="$FALLOS ventaja_bruta($RU_BR!=$MI_BR)"
cmp3 "$RU_NE" "$MI_NE" || FALLOS="$FALLOS ventaja_neta($RU_NE!=$MI_NE)"
cmp3 "$RU_EN" "$MI_EN" || FALLOS="$FALLOS coste_entrada($RU_EN!=$MI_EN)"

# CERO BLOQUES NO ES CERO DEFECTOS: sin muestra, las dos consultas «coinciden» en nada.
[ "${RU_NEF:-0}" -ge 100 ] || { echo "NO MEDIDO: solo $RU_NEF bloque(s) en el arco; con menos de 100 la comparacion no prueba nada"; exit 2; }

# --- BRAZO B · el payload vivo, si lo hay ----------------------------------------------
# EL RECUENTO SE COMPRUEBA CONTRA SU DEFINICION, no solo entre las dos consultas. Si las dos
# contaran pares, coincidirian y las dos estarian mal -que es exactamente lo que paso-. Aqui
# se le pregunta a la base cuantos BLOQUES DISTINTOS hay, sin pasar por ninguna de las dos.
BLK=$(TODO=1 "$B/bin/prodsql" "
  SELECT COUNT(*) FROM (
    SELECT (EXTRACT(EPOCH FROM o.window_start)/60/$HOR)::bigint AS blk
    FROM signal_outcome o JOIN signal_observation s ON s.observation_id=o.observation_id
    WHERE s.symbol='BTCUSDT_PERP.A' AND s.is_periodic IS TRUE AND o.status='evaluated' $CONGELA
      AND o.horizon_minutes=$HOR AND o.end_price IS NOT NULL AND s.reference_price IS NOT NULL
      AND s.observed_at >= '$A_DESDE'::timestamptz AND s.observed_at < '$A_HASTA'::timestamptz
    GROUP BY 1
    HAVING BOOL_OR(s.actionable IS TRUE AND s.direction IN ('long','short'))
       AND BOOL_OR(s.actionable IS NOT TRUE)) q" 2>/dev/null | tr -d ' ' | head -1)
case "$BLK" in
  ''|*[!0-9]*) echo "NO MEDIDO: no se pudo contar los bloques distintos (salio '$BLK')"; exit 2 ;;
esac
[ "$RU_NEF" = "$BLK" ] || FALLOS="$FALLOS n_efectiva_no_son_bloques($RU_NEF!=$BLK)"

if [ "$DESPLEGADO" = si ]; then
  cmp3 "$P_BRUTA"   "$RU_BR" || FALLOS="$FALLOS payload_bruta($P_BRUTA!=$RU_BR)"
  cmp3 "$P_NETA"    "$RU_NE" || FALLOS="$FALLOS payload_neta($P_NETA!=$RU_NE)"
  cmp3 "$P_ENTRADA" "$RU_EN" || FALLOS="$FALLOS payload_entrada($P_ENTRADA!=$RU_EN)"
  [ "$P_NEF" = "$RU_NEF" ]   || FALLOS="$FALLOS payload_n_efectiva($P_NEF!=$RU_NEF)"
fi

if [ -n "${FALLOS# }" ]; then
  echo "la cifra que se pinta NO coincide con la que sale de signal_outcome:$FALLOS"
  echo "  arco comparado: $A_DESDE .. $A_HASTA · horizonte $HOR min · payload en 140: $DESPLEGADO"
  exit 1
fi

if [ "$DESPLEGADO" = si ]; then
  echo "la tasa base publicada coincide con signal_outcome sobre $RU_NEF bloques y $RU_OBS observaciones (bruta $RU_BR, neta $RU_NE, entrada $RU_EN), por los DOS caminos: la consulta de la ruta y una escrita aparte, y ademas contra el payload vivo de /api/dashboard/state"
else
  echo "la consulta de la ruta y una escrita aparte coinciden sobre $RU_NEF bloques y $RU_OBS observaciones (bruta $RU_BR, neta $RU_NE, entrada $RU_EN). El payload de 140 AUN NO trae signal_base_rate: falta DESPLEGAR, y por eso el brazo del payload no tiene sujeto todavia (no es un fallo del arreglo)"
fi
exit 0
