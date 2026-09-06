#!/usr/bin/env bash
# K95-control · ¿el check CAZA una cifra que no cuadra, o solo sabe decir que si?
#
# UN CHECK QUE COMPARA DOS CIFRAS TIENE UN MODO DE FALLO OBVIO: que las dos salgan del mismo
# sitio. K95 corre la consulta de la ruta -extraida de app/api.py- contra otra escrita a mano
# en el propio check; si el que compara estuviera roto, o si la extraccion devolviera la
# consulta equivocada, el VERDE no probaria nada.
#
# COMO SE INDUCE UN DEFECTO CONOCIDO SIN TOCAR NADA: se monta un arbol de mentira con una
# COPIA de app/api.py y se le cambia UN operador dentro de BASE_RATE_SQL. La consulta de la
# ruta pasa a medir otra cosa, la del check no cambia, y K95 tiene que enrojecer Y NOMBRAR EL
# CAMPO que difiere. Se le apunta con K95_REPO, que es la variable que el check ya acepta.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto es el criterio.
# Necesita 140 por prodsql y por la API, igual que su sujeto; sin eso, NOMED.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K95-la-tasa-base-que-se-pinta.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K95_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

caso() {  # <nombre> <rc esperado> <patron> <arbol>
  local nombre="$1" esperado="$2" patron="$3" arbol="$4" out rc ok=1
  out=$(K95_REPO="$arbol" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-52s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -1 | cut -c1-150)"
  fi
}

arbol() {  # <destino>  copia minima con lo que K95 lee
  mkdir -p "$1/app" "$1/harness/checks"
  cp "$ORIG/app/api.py" "$1/app/api.py"
  cp "$CHK" "$1/harness/checks/"
}

echo "K95-control · sujeto: $CHK"
echo

echo "NEGATIVO · el arbol sano no puede enrojecer"
SANO="$DIR/sano"; arbol "$SANO"
caso "N1 la consulta de la ruta y la del check coinciden" 0 "coinciden sobre" "$SANO"

echo
echo "POSITIVO · si la ruta mide otra cosa, tiene que verse"
# P1 · se cambia el signo del lado corto DENTRO de BASE_RATE_SQL. Es un error plausible -es
# justo el que convierte una tasa base en su contraria- y no toca ninguna otra cosa.
ROTO="$DIR/roto"; arbol "$ROTO"
python3 - "$ROTO/app/api.py" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
cab, resto = t.split('BASE_RATE_SQL = """', 1)
sql, cola = resto.split('"""', 1)
viejo = "(CASE WHEN p.direction='long' THEN 1 ELSE -1 END)\n             * 100.0*(p.reference_price - m.pm)/m.pm"
assert viejo in sql, "no encuentro la expresion del coste de entrada"
sql = sql.replace(viejo, "(CASE WHEN p.direction='long' THEN 1 ELSE 1 END)\n             * 100.0*(p.reference_price - m.pm)/m.pm")
p.write_text(cab + 'BASE_RATE_SQL = """' + sql + '"""' + cola, encoding="utf-8")
PY
caso "P1 el coste de entrada mal firmado: ROJO" 1 "NO coincide" "$ROTO"
caso "P2 y NOMBRA el campo que difiere"         1 "coste_entrada" "$ROTO"

echo
echo "ANTI-FANTASMA · sin sujeto no hay veredicto"
SIN="$DIR/sin"; mkdir -p "$SIN/app"
printf 'x = 1\n' > "$SIN/app/api.py"
caso "F1 api.py sin BASE_RATE_SQL: NOMED" 2 "ya no publica la tasa base" "$SIN"

VACIO="$DIR/vacio"; mkdir -p "$VACIO"
caso "F2 sin api.py: NOMED" 2 "no se puede leer" "$VACIO"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
