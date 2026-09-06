#!/bin/bash
# K92-control · LOS BRAZOS, INDUCIDOS SIN RED Y SIN BASE.
#
# K92 necesita DOS canales -el journal para las paradas y prodsql para la cobertura- y esta
# sesion no llega a ninguno, asi que el control los inyecta los dos. Eso permite ejercitar
# combinaciones que un solo dato real no daria: parada sin fila, minuto siguiente completo,
# journal vacio, esquema sin la columna.
#
# EL BRAZO QUE MAS IMPORTA ES EL CONTROL DEL SUJETO: si el minuto SIGUIENTE a la parada
# tambien sale completo, el defecto no esta en la cobertura sino en el registro de paradas o
# en el reloj, y el check tiene que decir NO MEDIDO en vez de acusar. Un check que acusa sin
# haber descartado la explicacion alternativa es el que produce los K falsos que este arnes
# lleva seis paquetes evitando.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail

ORIG=${K92_CONTROL_REPO:-/srv/coinanalyze/repo}
CHK="$(cd "$(dirname "$0")" && pwd)/K92-el-minuto-que-miente.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K92_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
cd "$DIR" || exit 2
fallos=0; pasan=0
mkdir -p "$DIR/bin"

# --- el journal de mentira ----------------------------------------------------------------
cat > "$DIR/bin/prod" <<'PY'
#!/bin/sh
printf '%s\n' "${K92C_JOURNAL:-}"
exit "${K92C_PRODRC:-0}"
PY
chmod +x "$DIR/bin/prod"
cat > "$DIR/bin/prod-roto" <<'PY'
#!/bin/sh
echo "ssh: connect to host: No route to host" >&2
exit 255
PY
chmod +x "$DIR/bin/prod-roto"

# --- la base de mentira -------------------------------------------------------------------
cat > "$DIR/bin/prodsql" <<'PY'
#!/bin/sh
[ -n "${K92C_FILAS:-}" ] || exit 0
printf '%s\n' "$K92C_FILAS"
PY
chmod +x "$DIR/bin/prodsql"
cat > "$DIR/bin/prodsql-roto" <<'PY'
#!/bin/sh
echo 'psql:<stdin>:1: ERROR:  column "covered_seconds" does not exist' >&2
exit 3
PY
chmod +x "$DIR/bin/prodsql-roto"

# LA VENTANA, no el instante. Se necesitan los DOS marcadores: `Stopping` abre y `Started`
# cierra. Es la correccion del 2026-09-05: el criterio viejo miraba el minuto de la parada y
# el SIGUIENTE, y el minuto que miente es el ANTERIOR -el que contiene el `Stopping`-.
JOURNAL_OK='2026-09-05T17:16:55+00:00 systemd[1]: Stopping coinalyze-ws.service...
2026-09-05T17:17:14+00:00 systemd[1]: Started coinalyze-ws.service.'

# formato de la consulta, ahora CUATRO columnas: minuto|caido|filas|cov
#   caido > 0  -> SUJETO   (minuto que la ventana toca)
#   caido = 0  -> CONTROL  (minuto intacto: tiene que poder declarar 60)
# La ventana 17:16:55 -> 17:17:14 deja 5 s en el minuto 17:16 y 14 s en el 17:17.
CTRL='       2026-09-05T17:13|  0|  6| 60
 2026-09-05T17:20|  0|  6| 60'
FILA_MIENTE=" 2026-09-05T17:16|  5|  6| 60
 2026-09-05T17:17| 14|  6| 45
$CTRL"
FILA_SANA="   2026-09-05T17:16|  5|  6| 55
 2026-09-05T17:17| 14|  6| 45
$CTRL"
FILA_AUSENTE="2026-09-05T17:16|  5|  0| -1
 2026-09-05T17:17| 14|  0| -1
$CTRL"

# --- LOS FIXTURES DE LA CADUCIDAD, anadidos el 2026-09-06 ---------------------------------
# Desde hoy, "ningun minuto miente" NO basta para un verde: hacen falta >= 7 OCASIONES que
# pudieran exhibirlo. Una ocasion es una ventana que CRUZA el borde del minuto -unica forma de
# que el drenaje de apagado escriba un minuto que estaba abierto- y cuyo minuto tiene fila.
# Sin estos fixtures el check no tendria ningun camino a verde y el brazo positivo estaria
# muerto: un check que solo sabe decir rojo y nomed no mide, veta.
JOURNAL_7=$(for h in 01 02 03 04 05 06 07; do
  printf '2026-09-05T%s:16:55+00:00 systemd[1]: Stopping coinalyze-ws.service...\n' "$h"
  printf '2026-09-05T%s:17:14+00:00 systemd[1]: Started coinalyze-ws.service.\n' "$h"
done)
FILAS_7=$(for h in 01 02 03 04 05 06 07; do
  printf ' 2026-09-05T%s:16|  5|  6| 55\n' "$h"
  printf ' 2026-09-05T%s:17| 14|  6| 45\n' "$h"
  printf ' 2026-09-05T%s:13|  0|  6| 60\n' "$h"
done)
# El mismo, con SEIS ventanas: una menos que el suelo. Es la frontera, que es donde un umbral
# se equivoca si esta mal escrito.
JOURNAL_6=$(printf '%s\n' "$JOURNAL_7" | head -12)
FILAS_6=$(printf '%s\n' "$FILAS_7" | head -18)
# Y el que prueba que el CONTADOR no es el sujeto: siete ventanas que NO cruzan el borde.
# Tienen minutos tocados y filas, pero ninguna pudo exhibir el defecto: no son ocasiones.
JOURNAL_7NC=$(for h in 01 02 03 04 05 06 07; do
  printf '2026-09-05T%s:16:20+00:00 systemd[1]: Stopping coinalyze-ws.service...\n' "$h"
  printf '2026-09-05T%s:16:39+00:00 systemd[1]: Started coinalyze-ws.service.\n' "$h"
done)
FILAS_7NC=$(for h in 01 02 03 04 05 06 07; do
  printf ' 2026-09-05T%s:16| 19|  6| 41\n' "$h"
  printf ' 2026-09-05T%s:13|  0|  6| 60\n' "$h"
done)
FILAS_7NC_MIENTE=$(printf ' 2026-09-05T01:16| 19|  6| 60\n'; printf '%s\n' "$FILAS_7NC" | tail -n +2)

caso() {  # <nombre> <rc> <patron> <journal> <filas> [prodsql] [prod]
  local nombre="$1" esperado="$2" patron="$3" jr="$4" fl="$5"
  local psql="${6:-$DIR/bin/prodsql}" prod="${7:-$DIR/bin/prod}"
  local out rc
  out=$(REPO="$ORIG" K92_PRODSQL="$psql" K92_PROD="$prod" \
        K92C_JOURNAL="$jr" K92C_FILAS="$fl" bash "$CHK" 2>&1); rc=$?
  local ok=1
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-52s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-150)"
  fi
}

echo "K92-control · sujeto: $CHK"
echo

echo "POSITIVO · el minuto que miente"
# P1 · EL CASO REAL, con las cifras medidas en 140 el 2026-09-04: la ventana deja 5 s en el
# minuto 17:16, que declara 60 cuando lo mas que puede declarar es 55.
caso "P1 cov=60 con 5s de ventana dentro del minuto" 1 "declaran MAS cobertura" \
     "$JOURNAL_OK" "$FILA_MIENTE"
# P2 · dos ventanas, una miente y otra no: tiene que nombrar solo la que miente.
caso "P2 dos ventanas, solo una miente" 1 "17:16" \
     "$JOURNAL_OK
2026-09-04T09:30:20+00:00 systemd[1]: Stopping coinalyze-ws.service...
2026-09-04T09:30:40+00:00 systemd[1]: Started coinalyze-ws.service." \
     " 2026-09-05T17:16|  5|  6| 60
 2026-09-04T09:30| 20|  6| 40
$CTRL"

echo
echo "NEGATIVO · cuando la cobertura SI se escribe corta"
caso "N1 cov=55 en el limite: no miente, pero 1 ocasion no prueba" 2 "CALLADO SIN PROBAR" \
     "$JOURNAL_OK" "$FILA_SANA"
# N2 · los minutos intactos son CONTROL, no sujeto. Se afirma sobre el RECUENTO -«2 minuto(s)
# tocados» con cuatro filas en la consulta-, porque con el mismo fixture que N1 este caso
# pasaria siempre que pasara N1 y no probaria nada por su cuenta.
caso "N2 los 2 intactos no entran en el recuento de sujetos" 2 "2 minuto\(s\) tocados" \
     "$JOURNAL_OK" "$FILA_SANA"
# N3 · sin fila es el caso AUSENTE, que YA se arreglo y no es el sujeto de este check.
caso "N3 minuto tocado AUSENTE: no es el sujeto" 2 "sin sujeto" \
     "$JOURNAL_OK" "$FILA_AUSENTE"

echo
echo "LA DESIGUALDAD · declarar de MENOS no es este defecto"
# D1 · EL CASO QUE OBLIGO A CAMBIAR EL CRITERIO. El 2026-09-03 la ventana fue de 19 s y el
# minuto declaro covered_seconds=1: el colector tardo en recibir su primer trade despues del
# arranque. La RESTA EXACTA -exigir cov = 60-19 = 41- daria ROJO aqui, y seria un ROJO
# FALSO: declarar de menos no es mentir que estas completo. La DESIGUALDAD lo deja pasar.
caso "D1 cov=1 con 19s de ventana: corto de mas, no miente" 2 "CALLADO SIN PROBAR" \
     "2026-09-03T05:20:39+00:00 systemd[1]: Stopping coinalyze-ws.service...
2026-09-03T05:20:58+00:00 systemd[1]: Started coinalyze-ws.service." \
     " 2026-09-03T05:20| 19|  3|  1
 2026-09-03T05:17|  0|  6| 60"
# D2 · y un solo segundo por encima del limite SI es ROJO: la desigualdad no es un colador.
caso "D2 cov=56 con 5s de ventana: un segundo de mas ya miente" 1 "permite<=55 dice=56" \
     "$JOURNAL_OK" " 2026-09-05T17:16|  5|  6| 56
$CTRL"

echo
echo "LA VENTANA QUE CRUZA DOS MINUTOS"
# V1 · una sola ventana produce DOS sujetos con limites distintos -5 s y 14 s-, y el segundo
# sale sano con 45. El criterio viejo, que miraba «el siguiente», habria dado por bueno el
# primero -el unico roto- exactamente al reves.
caso "V1 una ventana, dos minutos, limites distintos" 1 "permite<=55" \
     "$JOURNAL_OK" "$FILA_MIENTE"
# V2 · un `Stopping` sin su `Started` es una ventana abierta: no se juzga. Si se juzgara,
# habria que inventarle un final.
caso "V2 Stopping sin Started: ventana abierta, no se juzga" 2 "sin sujeto que medir" \
     "2026-09-05T17:16:55+00:00 systemd[1]: Stopping coinalyze-ws.service..." \
     "$FILA_MIENTE"

echo
echo "EL CONTROL DEL SUJETO · en la misma consulta"
# C1 · HUELLA POSITIVA. Si NINGUN minuto intacto llega a 60, la tabla va corta por todas
# partes y un minuto corto junto a una parada no seria atribuible a la parada. NOMED, jamas
# ROJO: el hallazgo no se sostendria.
caso "C1 ningun minuto intacto declara 60" 2 "NINGUNO declara 60" \
     "$JOURNAL_OK" " 2026-09-05T17:16|  5|  6| 60
 2026-09-05T17:13|  0|  6| 58
 2026-09-05T17:20|  0|  6| 59"

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, jamas VERDE"
# F1 · CERO VENTANAS NO ES CERO DEFECTOS. Sin ventana no hay segundos caidos y el check no
# tiene sujeto. Es la leccion de K60 aplicada al elegible.
caso "F1 ninguna ventana en el periodo" 2 "sin sujeto que medir" \
     "" "$FILA_MIENTE"
caso "F2 el journal no se puede leer" 2 "no se pudo leer el journal" \
     "$JOURNAL_OK" "$FILA_MIENTE" "$DIR/bin/prodsql" "$DIR/bin/prod-roto"
caso "F3 el SQL falla" 2 "la consulta fallo" \
     "$JOURNAL_OK" "$FILA_MIENTE" "$DIR/bin/prodsql-roto"
caso "F4 la consulta no devuelve filas" 2 "ninguna fila para las" \
     "$JOURNAL_OK" "total | nada"

echo
echo "ESQUEMA REAL · las columnas se comprueban ANTES de consultar"
# E1 · el sujeto NO es un doble: se lee sql/schema.sql de verdad, con el catalogo que desde
# F4 conoce tambien las columnas de ALTER -sin las cuales covered_seconds es invisible-.
res=$(python3 - "$ORIG" <<'PY'
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
repo = Path(sys.argv[1])
m = SourceFileLoader("arq", str(repo / "harness/bin/arquitectura")).load_module()
cat = m.lee_catalogo(repo)
out = []
for t in ("spot_trades_agg", "futures_trades_agg"):
    cols = set(cat["tablas"].get(t, {}).get("columnas", []))
    falta = [c for c in ("ts", "symbol", "exchange", "interval", "covered_seconds") if c not in cols]
    out.append((t, falta))
malas = [t for t, f in out if f]
print("OK" if not malas else "FALTAN " + str(out))
PY
2>&1)
if [ "$res" = "OK" ]; then
  pasan=$((pasan+1)); printf '  [ok   ] %-52s las 5 en las DOS tablas\n' "E1 columnas de las dos tablas del defecto"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-52s %s\n' "E1 columnas" "$res"
fi

# E2 · CONTROL NEGATIVO DEL PROPIO E1: una tabla que NO existe tiene que salir SINTABLA, no
# pasar por buena. Sin esto, E1 pasaria tambien con un catalogo vacio.
out=$(REPO="$ORIG" K92_TABLA="tabla_que_no_existe" K92_PRODSQL="$DIR/bin/prodsql" \
      K92_PROD="$DIR/bin/prod" K92C_JOURNAL="$JOURNAL_OK" K92C_FILAS="$FILA_MIENTE" \
      bash "$CHK" 2>&1); rc=$?
if [ "$rc" = "2" ] && printf '%s' "$out" | grep -q "no esta en sql/schema.sql"; then
  pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "E2 tabla inventada: NOMED, no pasa por buena" "$rc"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-52s rc=%s\n' "E2 tabla inventada" "$rc"
fi

echo
echo "LA CADUCIDAD · un verde tiene que GANARSE, y un rojo no puede caducar"
# Este check se iba a poner VERDE SOLO el 09-11: su rojo descansa sobre un unico minuto y la
# ventana son 7 dias. Estos brazos cierran las dos formas de mentir por el paso del tiempo.
caso "K1 siete ocasiones limpias -> VERDE, y ganado"      0 "REMITIDO Y PROBADO" \
     "$JOURNAL_7" "$FILAS_7"
caso "K1b y no afirma que nadie lo arreglara"             0 "NO DICE QUE NADIE LO ARREGLARA" \
     "$JOURNAL_7" "$FILAS_7"
caso "K2 seis ocasiones, una menos que el suelo -> NOMED" 2 "solo hubo 6 ocasion" \
     "$JOURNAL_6" "$FILAS_6"
# K3 · EL BRAZO QUE SEPARA EL SUJETO DEL CONTADOR. Siete ventanas con sus minutos tocados y sus
# filas, pero NINGUNA cruza el borde: no pudieron exhibir el defecto ni existiendo. Si el check
# contara "minutos tocados" como prueba, esto saldria VERDE sin haber probado nada, que es
# exactamente el verde no ganado que esta campania persigue.
caso "K3 siete ventanas que NO cruzan: 0 ocasiones -> NOMED" 2 "solo hubo 0 ocasion" \
     "$JOURNAL_7NC" "$FILAS_7NC"
caso "K3b y lo explica: los tocados no son prueba"        2 "no podian exhibir el defecto" \
     "$JOURNAL_7NC" "$FILAS_7NC"
# K4 · Y EL SUJETO NO SE ESTRECHA. Si un minuto miente en una ventana que NO cruza el borde,
# sigue siendo ROJO. Estrechar el sujeto habria sido el atajo barato -y habria escondido esto-.
caso "K4 miente sin cruzar el borde: sigue siendo ROJO"    1 "ROJO \(VIVO\)" \
     "$JOURNAL_7NC" "$FILAS_7NC_MIENTE"
caso "K4b y publica los DOS denominadores"                 1 "poblacion equivocada" \
     "$JOURNAL_7NC" "$FILAS_7NC_MIENTE"

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
