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
caso "N1 la consulta de la ruta y la del check coinciden" 0 "coincide" "$SANO"

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
echo "LA n EFECTIVA SON BLOQUES · el caso que el operador tuvo que encontrar por nosotros"
# EL DEFECTO: `dif` sale de `senal`, que agrupa por (bloque, LADO), asi que un bloque con
# señal larga y corta daba DOS filas. La ruta publicaba 1 191 pares llamandolos bloques donde
# hay 604. Y K95 NO LO CAZABA porque su propia consulta agrupaba igual: las dos coincidian en
# el mismo error. Ahora K95 pregunta el recuento de bloques a la base POR SEPARADO.
# Aqui se le quita a la ruta el colapso por bloque -se le hace contar pares otra vez- y K95
# tiene que enrojecer nombrando la n.
PARES="$DIR/pares"; arbol "$PARES"
python3 - "$PARES/app/api.py" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
cab, resto = t.split('BASE_RATE_SQL = """', 1)
sql, cola = resto.split('"""', 1)
assert "FROM porbloque" in sql, "no encuentro el colapso por bloque"
# se deshace el colapso: la consulta vuelve a agregar sobre `dif`, o sea sobre PARES
sql = sql.replace("FROM porbloque", "FROM dif")
sql = sql.replace("(SELECT COUNT(*) FROM dif)", "(SELECT COUNT(*) FROM porbloque)")
p.write_text(cab + 'BASE_RATE_SQL = """' + sql + '"""' + cola, encoding="utf-8")
PY
caso "P3 si la ruta cuenta PARES en vez de bloques: ROJO" 1 "NO coincide" "$PARES"
caso "P4 y lo nombra como lo que es"                      1 "n_efectiva_no_son_bloques|observaciones" "$PARES"

echo
echo "EL BORDE QUE HACIA PARPADEAR · y el contraste contra el K95 de 64704d4"
# EL DEFECTO, medido por el operador el 2026-09-06 a las 18:19Z: K95 corrido cinco veces
# seguidas sobre el mismo arbol y la misma base dio rc=0,0,0,1,1. El comparador tenia un margen
# EXACTAMENTE IGUAL al paso de la resolucion publicada -TOL=0.0001 sobre cuatro decimales-, asi
# que dos valores que difieren en UNA unidad del ultimo decimal caian en el borde y decidia el
# error de coma flotante: abs(-0.053 - (-0.0531)) = 0.00010000000000000286 > 0.0001.
#
# SE PRUEBA SOBRE `cmp3`, que es donde vive el borde, sacando la funcion de CADA VERSION del
# fichero -la de git y la de ahora- en vez de reescribirla. Si el brazo no pudiera enseniar que
# la version anterior falla con el mismo par, no habria probado que el arreglo arregla algo.
# `caso` compara VEREDICTOS de un arbol; estos brazos comparan VALORES. Son dos cosas y por eso
# hay dos ayudantes: llamar a `caso` con tres argumentos dejaba `$4` sin definir y con `set -u`
# el control moria en vez de fallar. Me paso al escribirlo.
casov() {  # <nombre> <esperado> <obtenido>
  if [ "$3" = "$2" ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s %s\n' "$1" "$3"
  else
    fallos=$((fallos+1)); printf '  [FALLA] %-52s esperaba %s, dio %s\n' "$1" "$2" "$3"
  fi
}

compara() {  # <fuente del check> <a> <b>  -> rc de su cmp3
  local src="$1" f; f=$(mktemp)
  { printf 'set -u\nTOL=${K95_TOL:-0.0001}\n'
    printf '%s\n' "$src" | sed -n '/^cmp3() {/,/^sys.exit(0 if .*)\"; }$/p'
    printf 'cmp3 "$1" "$2"\n'
  } > "$f"
  bash "$f" "$2" "$3"; local rc=$?; rm -f "$f"; return $rc
}
VIEJO_SRC=$(cd "$ORIG" && git show 64704d4:harness/checks/K95-la-tasa-base-que-se-pinta.sh 2>/dev/null || true)
NUEVO_SRC=$(cat "$CHK")
if [ -n "$VIEJO_SRC" ]; then
  compara "$VIEJO_SRC" -0.053 -0.0531 && v=pasa || v=FALLA
  compara "$NUEVO_SRC" -0.053 -0.0531 && n=pasa || n=FALLA
  casov "B1 el cmp de 64704d4 FALLA con -0.053 vs -0.0531" "FALLA" "$v"
  casov "B2 y el nuevo tambien FALLA: ya no se toleran"    "FALLA" "$n"
else
  printf '  [....] %-52s\n' "B1/B2 no se pudo sacar 64704d4 de git"
fi
# B3 · LA MITAD QUE IMPORTA: el nuevo NO puede rechazar dos escrituras del MISMO numero.
# «-0.053» y «-0.0530» son el mismo valor; el payload lo serializa como float de JSON y el SQL
# como texto, y la representacion no es el valor.
compara "$NUEVO_SRC" -0.0530 -0.053 && n=pasa || n=FALLA
casov "B3 el nuevo acepta -0.0530 == -0.053"             "pasa"  "$n"
compara "$NUEVO_SRC" -0.0531 -0.0531 && n=pasa || n=FALLA
casov "B3b y acepta la igualdad estricta"                "pasa"  "$n"
# B4 · y NO se ha aflojado: una diferencia de verdad sigue fallando.
compara "$NUEVO_SRC" -0.0531 -0.0631 && n=pasa || n=FALLA
casov "B4 una diferencia real sigue fallando"            "FALLA" "$n"
# B5 · un valor ilegible NO pasa por igual. `None` no es igual a nada.
compara "$NUEVO_SRC" None -0.0531 && n=pasa || n=FALLA
casov "B5 un valor ilegible no pasa"                     "FALLA" "$n"

echo
echo "EL CONGELADO · los dos lados tienen que mirar el mismo conjunto"
grep -q 'finalized_at <=' "$CHK" && c=si || c=no
casov "C1 el check acota por finalized_at"               "si" "$c"
grep -q 'ventana_pedida_desde' "$CHK" && c=si || c=no
casov "C2 y usa la ventana PEDIDA, no el arco medido"    "si" "$c"
if [ -n "$VIEJO_SRC" ]; then
  printf '%s' "$VIEJO_SRC" | grep -q 'finalized_at <=' && c=si || c=no
  casov "C3 el de 64704d4 NO lo hacia (el contraste)"      "no" "$c"
fi

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
