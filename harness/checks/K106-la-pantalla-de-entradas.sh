#!/bin/bash
# K106 · LA PANTALLA DE ENTRADAS · lo que la vista `#<marco>/<activo>/entradas` de la mesa PINTA,
# mirado con un Chromium de verdad (campana 137, E2).
#
# QUE ESTABA SIN VIGILAR. El registro de planes de entrada tiene desde la 137 una pantalla. Una
# pantalla puede ser fiel a su ruta y aun asi decir lo que no puede: una fraccion de aciertos, una
# palabra que promete, un plan caducado que sigue «vivo», un DECIDE en NO EVALUABLE leido como un
# «no». Nada de eso lo ve una sonda de la RESPUESTA: hay que mirar la pantalla.
#
# QUE JUZGA (los brazos estan en K106-vista.py, con las cifras permitidas nombradas una a una):
#   E1 existe · E2 fiel a la respuesta que pinto (A76, A77) · E3 el reloj · E4 sin dato ·
#   E5 lo que no puede decir · E6 orden y color · E7 la palabra de DECIDE y SU frase (A83) ·
#   E8 que pide, cuanto pesa y cada cuanto
# en los TRES activos; en el primero se queda mirando hasta ver UN refresco (la edad tiene que
# correr y la segunda respuesta tiene que casar con SU pantalla). Y abre la vista principal para
# comprobar que no pide lo que solo es de ENTRADAS (los papeles salen de K44-contrato-mesa.tsv).
#
# A QUIEN JUZGA, y lo dice en su primera linea:
#   por defecto        PRODUCCION ($API_PROD), con la credencial del netrc en una cabecera
#   MESA_BASE=<url>    el ARBOL servido ahi (K106-banco.py, o la app del arbol)
# Si el arbol trae la vista y produccion no la sirve: NO MEDIDO por FALTA DESPLEGAR. Ni ROJO -el
# codigo no esta mal- ni VERDE -nadie ha mirado la pantalla que el operador abre-.
#
# Salida 0 VERDE · 1 ROJO · 2 NO MEDIDO. Control: K106-control.bash.
set -u
B=/srv/coinanalyze/harness
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # ABSOLUTA antes de cualquier cd (A56)
SONDA="$D/K106-vista.py"
. "$B/env"
REPO="${REPO:-/srv/coinanalyze/repo}"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ]    || { echo "NO MEDIDO: no hay interprete en $PY"; exit 2; }
[ -r "$SONDA" ] || { echo "NO MEDIDO: falta la sonda $SONDA"; exit 2; }
TMP="$(mktemp -d)" || exit 2
trap 'rm -rf "$TMP"' EXIT INT TERM

ACTIVOS="${K106_ACTIVOS:-BTC ETH SOL}"
OBSERVA="${K106_OBSERVA:-52}"      # segundos mirando el primer activo: la cadencia servida es de 45
RUTA="/api""/mesa/entradas"
ARBOL_TIENE=0
grep -q 'id="vista-entradas"' "$REPO/static/mesa.html" 2>/dev/null && ARBOL_TIENE=1

BASE="${MESA_BASE:-}"
CAB=()
falta_desplegar() {
  if [ "$ARBOL_TIENE" = "1" ]; then
    echo "NO MEDIDO: FALTA DESPLEGAR. El arbol trae la vista de entradas y $SUJETO no ($1)."
    echo "  El codigo no esta mal: no esta desplegado. Para juzgar el arbol: MESA_BASE=http://127.0.0.1:PUERTO $0"
  else
    echo "NO MEDIDO: ni el arbol ni $SUJETO traen la vista de entradas ($1)"
  fi
  exit 2
}
if [ -n "$BASE" ]; then
  SUJETO="el ARBOL, servido en $BASE"
  PUERTA="${K106_PUERTA:-/}"
else
  SUJETO="PRODUCCION ($API_PROD)"
  PUERTA=/
  [ -r "$NETRC" ] || { echo "NO MEDIDO: falta $NETRC y produccion pide auth_basic"; exit 2; }
  : > "$TMP/cab"; chmod 600 "$TMP/cab"
  "$PY" - "$NETRC" > "$TMP/cab" <<'PY' || { echo "NO MEDIDO: no se pudo leer el netrc"; exit 2; }
import base64, netrc, sys
n = netrc.netrc(sys.argv[1])
cred = next((n.authenticators(h) for h in n.hosts if n.authenticators(h)), None)
if not cred:
    raise SystemExit(1)
print("Authorization: Basic " + base64.b64encode(f"{cred[0]}:{cred[2]}".encode()).decode(), end="")
PY
  [ -s "$TMP/cab" ] || { echo "NO MEDIDO: el netrc no dio credencial usable"; exit 2; }
  CAB=(--cabecera-fichero "$TMP/cab")
  "$B/bin/api" "$RUTA?symbol=BTCUSDT_PERP.A" > /dev/null 2>&1 || falta_desplegar "no sirve $RUTA"
  BASE="$API_PROD"
fi

rojo=0; nomed=0; n=0
: > "$TMP/todo"
for a in $ACTIVOS; do
  n=$((n + 1))
  extra=()
  [ "$n" = "1" ] && [ "$OBSERVA" != "0" ] && extra=(--luego "@$OBSERVA")
  "$PY" "$SONDA" --base "$BASE" --puerta "$PUERTA" --activo "$a" "${CAB[@]}" "${extra[@]}" > "$TMP/s-$a" 2>&1
  rc=$?
  cat "$TMP/s-$a" >> "$TMP/todo"
  case "$rc" in
    0) ;;
    1) rojo=$((rojo + 1)) ;;
    3) falta_desplegar "su mesa no trae #vista-entradas" ;;
    *) nomed=$((nomed + 1)) ;;
  esac
done
PRIMERO="${ACTIVOS%% *}"
"$PY" "$SONDA" --base "$BASE" --puerta "$PUERTA" --activo "$PRIMERO" --vista mesa "${CAB[@]}" > "$TMP/s-mesa" 2>&1
rc=$?
cat "$TMP/s-mesa" >> "$TMP/todo"
case "$rc" in 0) ;; 1) rojo=$((rojo + 1)) ;; *) nomed=$((nomed + 1)) ;; esac

hallazgos=$(grep -c '^   - ' "$TMP/todo")
resumen=$(grep -E '^entradas \[' "$TMP/todo" | sed -E 's/^entradas \[([A-Z]+)\] [0-9x]+: ([0-9]+) planes.*, ([0-9]+) B la mayor.*/\1 \2 planes \3 B/' | paste -sd';' - | sed 's/;/ · /g')
if [ "$rojo" -gt 0 ]; then
  echo "K106 · ROJO, $hallazgos hallazgo(s) · la vista de entradas · sujeto: $SUJETO · ${resumen:-sin resumen}"
elif [ "$nomed" -gt 0 ]; then
  echo "NO MEDIDO: la sonda no pudo mirar la vista de entradas en $nomed de $((n + 1)) pasada(s) · sujeto: $SUJETO · $(grep -m1 '^NO MEDIDO' "$TMP/todo" | cut -c1-120)"
else
  echo "K106 · VERDE · la vista de entradas pinta lo que su ruta sirve y nada que no pueda decir · sujeto: $SUJETO · $resumen"
fi
sed 's/^/  /' "$TMP/todo"
[ "$rojo" -gt 0 ] && exit 1
[ "$nomed" -gt 0 ] && exit 2
exit 0
