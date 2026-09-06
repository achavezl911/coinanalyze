#!/usr/bin/env bash
# K96-control · K96 nacio VERDE, asi que sin este fichero no probaria nada.
#
# LA REGLA DEL BUCLE dice que un check se escribe y se observa ROJO ANTES del arreglo. Aqui el
# orden fue el contrario -la capa de auditoria se escribio bien a la primera- y un VERDE de
# nacimiento es indistinguible de un check que no sabe mirar. Lo que hace este control es
# provocar el defecto a mano sobre un arbol de mentira y exigir que K96 lo cace.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto es el criterio.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K96-la-auditoria-no-inventa.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K96_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

caso() {  # <nombre> <rc esperado> <patron> <arbol>
  local nombre="$1" esperado="$2" patron="$3" arbol="$4" out rc ok=1
  out=$(K96_REPO="$arbol" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-54s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-54s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -1 | cut -c1-150)"
  fi
}

arbol() {  # <destino>
  mkdir -p "$1/app" "$1/static"
  cp "$ORIG/app/api.py"    "$1/app/api.py"
  cp "$ORIG/static/app.js" "$1/static/app.js"
}

echo "K96-control · sujeto: $CHK"
echo

echo "NEGATIVO · el arbol de verdad no puede enrojecer"
SANO="$DIR/sano"; arbol "$SANO"
caso "N1 la capa no lee ningun campo inventado" 0 "no pinta ninguno inventado" "$SANO"

echo
echo "POSITIVO · el defecto que K96 existe para cazar"
# P1 · SE INVENTA UN CAMPO. Es el error real y barato: escribir de memoria `spread` donde la
# columna se llama `spread_bps`. En el navegador no se ve -undefined se pinta 'N/D'-, asi que
# si K96 no lo caza no lo caza nadie.
INV="$DIR/inventado"; arbol "$INV"
python3 - "$INV/static/app.js" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
viejo = "s.spread_bps == null ? 'N/D' : number(s.spread_bps, 2)"
assert viejo in t, "no encuentro la lectura del spread"
p.write_text(t.replace(viejo, "s.spread_medio == null ? 'N/D' : number(s.spread_medio, 2)"), encoding="utf-8")
PY
caso "P1 un campo que la ruta no publica: ROJO" 1 "NO publica" "$INV"
caso "P2 y lo NOMBRA"                           1 "spread_medio" "$INV"

# P3 · EL OTRO SENTIDO, que es el que muerde con el tiempo: la columna se RENOMBRA en el
# servidor y el panel se queda con el nombre viejo. Es el mismo desajuste visto del otro lado.
REN="$DIR/renombrado"; arbol "$REN"
python3 - "$REN/app/api.py" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
assert "s.spread_bps," in t, "no encuentro la columna en EXECUTION_COLUMNS"
p.write_text(t.replace("s.spread_bps,", "s.spread_bps_v2,", 1), encoding="utf-8")
PY
caso "P3 si la ruta renombra la columna: ROJO"  1 "spread_bps" "$REN"

echo
echo "ANTI-FANTASMA · sin sujeto no hay veredicto"
SINCAPA="$DIR/sincapa"; arbol "$SINCAPA"
python3 - "$SINCAPA/static/app.js" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
i, f = t.index("async function pedir("), t.index("const LEGACY_HYPOTHESIS")
p.write_text(t[:i] + t[f:], encoding="utf-8")
PY
caso "F1 sin capa de auditoria en app.js: NOMED" 2 "no encuentro la capa" "$SINCAPA"

SINSQL="$DIR/sinsql"; mkdir -p "$SINSQL/app" "$SINSQL/static"
printf 'x = 1\n' > "$SINSQL/app/api.py"
cp "$ORIG/static/app.js" "$SINSQL/static/app.js"
caso "F2 sin las columnas en api.py: NOMED"      2 "no encuentro LEDGER_COLUMNS" "$SINSQL"

VACIO="$DIR/vacio"; mkdir -p "$VACIO"
caso "F3 sin ficheros: NOMED"                    2 "no se puede leer" "$VACIO"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
