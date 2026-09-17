#!/bin/bash
# leer-control · ¿para `bin/leer` por TAMANO, y en las dos direcciones?
#
#     bash harness/checks/leer-control.bash
#
# POR QUE ESTE CONTROL. `leer` paraba por una LISTA DE NOMBRES que incluia `app.js` -borrado en
# la FASE 2- y NO incluia modulos de `static/js/` que pesan mas que varios de la lista. Una
# regla que envejece con cada refactor y no avisa. La regla nueva es de tamano y hay que verla
# disparar Y CALLAR: un control que solo enseña el no no distingue «para siempre» de «para
# cuando toca».
#
# LOS FICHEROS SON DE MENTIRA Y SE FABRICAN AQUI: asi el control no depende de que el repo tenga
# hoy un fichero grande con un nombre concreto, que es el error que se esta arreglando.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
LEER="$ORIG/harness/bin/leer"
[ -x "$LEER" ] || { echo "NO MEDIDO: no encuentro $LEER"; exit 2; }
LIM=$( . /srv/coinanalyze/harness/env 2>/dev/null; echo "${MAX_BYTES:-8000}" )
DIR=$(mktemp -d) || exit 2
trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-60s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-60s\n' "$1"; fi; }

echo "leer-control · sujeto: $LEER · MAX_BYTES=$LIM"
echo

# Dos ficheros que solo se diferencian en el TAMANO. Van en LINEAS CORTAS a proposito: con un
# solo renglon gigante, el `grep -C3` del brazo L3 arrastra esa linea entera y `_corta` se come
# la marca -fallo del fixture, no de `leer`, y lo canto el propio control-.
: > "$DIR/pequeno.js"
i=0; while [ "$(wc -c < "$DIR/pequeno.js")" -lt $((LIM - 200)) ]; do
  printf 'linea %04d aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n' "$i" >> "$DIR/pequeno.js"; i=$((i+1))
done
cp "$DIR/pequeno.js" "$DIR/grande.js"
while [ "$(wc -c < "$DIR/grande.js")" -le "$LIM" ]; do
  printf 'linea %04d aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n' "$i" >> "$DIR/grande.js"; i=$((i+1))
done
printf 'zzMARCAzz\n' >> "$DIR/grande.js"
printf '   pequeno.js %s B · grande.js %s B\n\n' "$(wc -c < "$DIR/pequeno.js")" "$(wc -c < "$DIR/grande.js")"

echo "L1 · por DEBAJO del corte se lee entero"
out=$("$LEER" "$DIR/pequeno.js" 2>&1); rc=$?
comprueba "L1a rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "L1b y NO dice que no se lee entero" \
  "$(printf '%s' "$out" | grep -q 'NO se lee entero' && echo no || echo si)"

echo
echo "L2 · por ENCIMA del corte para, y dice las dos cifras"
out=$("$LEER" "$DIR/grande.js" 2>&1); rc=$?
comprueba "L2a rc=3 (rc=$rc)" "$([ "$rc" = 3 ] && echo si || echo no)"
comprueba "L2b y nombra el tamano y el corte" \
  "$(printf '%s' "$out" | grep -qE "$(wc -c < "$DIR/grande.js") B, y esta herramienta corta en $LIM B" && echo si || echo no)"
comprueba "L2c y NO escupe el contenido" \
  "$(printf '%s' "$out" | grep -q 'zzMARCAzz' && echo no || echo si)"

echo
echo "L3 · el mismo fichero grande CON patron si se lee"
out=$("$LEER" "$DIR/grande.js" zzMARCAzz 2>&1); rc=$?
comprueba "L3a rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "L3b y trae la linea que se pidio" \
  "$(printf '%s' "$out" | grep -q 'zzMARCAzz' && echo si || echo no)"

echo
echo "L4 · y CON rango tambien"
out=$("$LEER" "$DIR/grande.js" 1 2 2>&1); rc=$?
comprueba "L4a rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"

echo
echo "L5 · TODO=1 lo salta, como salta el corte"
out=$(TODO=1 "$LEER" "$DIR/grande.js" 2>&1); rc=$?
comprueba "L5a rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "L5b y entonces SI sale el contenido entero" \
  "$(printf '%s' "$out" | grep -q 'zzMARCAzz' && echo si || echo no)"

echo
echo "L6 · EL CONTROL DEL CONTROL · el nombre NO manda: uno grande llamado como los de antes"
echo "     se para igual, y uno PEQUENO llamado app.js se lee"
cp "$DIR/grande.js" "$DIR/scalp_logic.py"; cp "$DIR/pequeno.js" "$DIR/app.js"
"$LEER" "$DIR/scalp_logic.py" >/dev/null 2>&1; rcg=$?
"$LEER" "$DIR/app.js" >/dev/null 2>&1; rcp=$?
comprueba "L6a un grande con nombre de la lista vieja para (rc=$rcg)" "$([ "$rcg" = 3 ] && echo si || echo no)"
comprueba "L6b un PEQUENO llamado app.js se lee (rc=$rcp)" "$([ "$rcp" = 0 ] && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
