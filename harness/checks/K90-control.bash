#!/bin/bash
# K90-control · LOS DOS BRAZOS, INDUCIDOS SIN RED Y SIN BASE.
#
# K90 corre contra 140 por prodsql y esta sesion no llega a ese canal, asi que el control
# INYECTA el canal: un prodsql falso que imprime la tabla que se le pida, y una copia de
# app.js con el rotulo que se le pida. Asi se ejercitan las dos mitades del sujeto -el
# rotulo y la medida- por separado y en combinacion, que es lo que un solo dato real no
# permitiria.
#
# EL BRAZO QUE MAS IMPORTA AQUI ES EL NEGATIVO, y no es el habitual: no basta con que K90
# no enrojezca cuando el p90 es alto. Tiene que ponerse VERDE **SOLO** cuando el rotulo
# deje de prometer un rango, porque esa es una de las dos salidas legitimas del defecto
# -la otra es dar persistencia al calculo- y un check que siguiera en rojo despues de
# arreglado se apagaria igual que uno que miente en verde.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh. Mismo patron que K88-control.
set -uo pipefail

ORIG=${K90_CONTROL_REPO:-/srv/coinanalyze/repo}
CHK="$(cd "$(dirname "$0")" && pwd)/K90-la-senal-no-dura-su-rotulo.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K90_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
cd "$DIR" || exit 2          # como K88-control: se demuestra que no depende del cwd
fallos=0; pasan=0

mkdir -p "$DIR/repo/static" "$DIR/repo/app" "$DIR/bin"
# scalp_logic.py de mentira, SIN mecanismos de persistencia (el estado real hoy)
printf 'def scalp_bias_label(a, b):\n    return "No Trade", "baja"\n' > "$DIR/repo/app/scalp_logic.py"

rotulo_en() {   # $1 = texto del campo time
  printf "      name: 'Corto plazo', time: '%s', action: shortAction,\n" "$1" \
    > "$DIR/repo/static/app.js"
}

# prodsql falso: imprime la tabla que se le pase por K90C_TABLA, con el formato de psql
cat > "$DIR/bin/prodsql" <<'PY'
#!/bin/sh
[ -n "${K90C_TABLA:-}" ] || exit 0
printf '%s\n' "$K90C_TABLA"
PY
chmod +x "$DIR/bin/prodsql"

# prodsql que FALLA, para el brazo de canal
cat > "$DIR/bin/prodsql-roto" <<'PY'
#!/bin/sh
echo "could not connect to server" >&2
exit 4
PY
chmod +x "$DIR/bin/prodsql-roto"

caso() {  # <nombre> <rc esperado> <patron> <rotulo> <tabla> [prodsql]
  local nombre="$1" esperado="$2" patron="$3" rot="$4" tabla="$5" psql="${6:-$DIR/bin/prodsql}"
  rotulo_en "$rot"
  local out rc
  out=$(REPO="$DIR/repo" K90_APPJS="$DIR/repo/static/app.js" K90_PRODSQL="$psql" \
        K90C_TABLA="$tabla" bash "$CHK" 2>&1); rc=$?
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

# Las cifras REALES medidas por el operador el 2026-09-05 contra 140, 30 dias:
REAL=' BTCUSDT | 11452 | 3 | 6 | 34356
 ETHUSDT | 11380 | 3 | 6 | 34356
 SOLUSDT | 10990 | 4 | 11 | 34356'
# Las mismas filas con el p90 accionable POR ENCIMA del umbral: es el mundo arreglado.
SANO=' BTCUSDT | 11452 | 9 | 6 | 34356
 ETHUSDT | 11380 | 10 | 6 | 34356
 SOLUSDT | 10990 | 12 | 11 | 34356'

echo "K90-control · sujeto: $CHK"
echo

echo "POSITIVO · con el rotulo de hoy y las cifras de hoy, ROJO"
caso "P1 rotulo 1-15 y p90 3/3/4 (el caso real)" 1 "p90 de la racha accionable no llega" \
     "1–15 minutos" "$REAL"
caso "P2 guion normal en vez del largo, mismo veredicto" 1 "p90 de la racha accionable no llega" \
     "1-15 minutos" "$REAL"
caso "P3 un solo simbolo por debajo" 1 "SOLUSDT" \
     "1–15 minutos" ' BTCUSDT | 11452 | 9 | 6 | 34356
 SOLUSDT | 10990 | 4 | 11 | 34356'

echo
echo "NEGATIVO · el check NO puede enrojecer cuando el defecto no esta"
caso "N1 mismas cifras, p90 por encima del umbral" 0 "lo alcanza en los" \
     "1–15 minutos" "$SANO"
# N2 · LA SALIDA POR PRODUCTO. Si el rotulo deja de prometer un rango, no hay horizonte que
# incumplir y el check se pone VERDE SOLO, con las MISMAS cifras rojas de hoy.
caso "N2 rotulo 'lectura instantanea' con las cifras de HOY" 0 "no anuncia un rango" \
     "lectura instantanea" "$REAL"
# N3 · y si el rotulo sube el rango, el umbral sube con el: 20-40 -> umbral 30, sigue rojo;
# pero 1-4 -> umbral 2, y un p90 de 3 YA LO CUMPLE.
caso "N3 rotulo 1-4 (umbral 2): el p90 de 3 lo cumple" 0 "lo alcanza en los" \
     "1–4 minutos" "$REAL"
caso "N4 rotulo 20-40 (umbral 30): sigue rojo" 1 "umbral 30" \
     "20–40 minutos" "$REAL"

echo
echo "CONTROL EN LA MISMA CONSULTA · si el lado no accionable es igual de corto, NO MEDIDO"
# Es el control que decide entre dos hipotesis: "la senal parpadea" contra "el muestreo
# trocea las dos series igual". Sin el, K90 afirmaria lo primero sin haber descartado lo
# segundo.
caso "C1 p90 no accionable IGUAL de corto" 2 "el sujeto seria el muestreo" \
     "1–15 minutos" ' BTCUSDT | 11452 | 3 | 3 | 34356
 ETHUSDT | 11380 | 3 | 2 | 34356'

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, nunca VERDE"
caso "F1 no existe la tarjeta 'Corto plazo'" 2 "NO MEDIDO" \
     "" "$REAL"
caso "F2 la consulta no devuelve ninguna fila" 2 "ninguna fila de simbolo" \
     "1–15 minutos" ""
caso "F3 prodsql falla" 2 "NO MEDIDO" \
     "1–15 minutos" "$REAL" "$DIR/bin/prodsql-roto"

# F4 · si alguien le pone histeresis al calculo, el sujeto cambia y K90 no puede seguir
# afirmando lo mismo sin releer el criterio. NOMED, no verde ni rojo.
printf 'HYSTERESIS_MINUTES = 3\ndef scalp_bias_label(a, b):\n    return "No Trade", "baja"\n' \
  > "$DIR/repo/app/scalp_logic.py"
caso "F4 aparece histeresis en scalp_logic" 2 "mecanismo\(s\) de persistencia" \
     "1–15 minutos" "$REAL"
printf 'def scalp_bias_label(a, b):\n    return "No Trade", "baja"\n' > "$DIR/repo/app/scalp_logic.py"

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
