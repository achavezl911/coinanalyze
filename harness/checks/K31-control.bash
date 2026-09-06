#!/usr/bin/env bash
# K31-control · ¿el criterio nuevo enrojece por lo que dice?
#
# K31 dejo de enrojecer por CONTAR huecos el 2026-09-06 -esa cifra no se movia y la respuesta
# no es de un check- y pasa a enrojecer por HUECOS SIN DUEÑO. El caso que importa, y el que
# el encargo pide explicitamente, es: **una ruta HUECO nueva sin disposicion enrojece**. Y su
# negativo: **con disposicion, no**.
#
# ES LENTO A PROPOSITO Y SE DICE: cada caso vuelve a correr la sonda de jsdom, ~100 s. No se
# stubea la sonda porque entonces el control probaria un K31 que no existe. Cuatro casos,
# unos siete minutos. Un control que miente rapido no vale mas que uno lento que no miente.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K31-eslabon5.sh"
REAL="$ORIG/harness/checks/K31-disposiciones.tsv"
[ -r "$CHK" ]  || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
[ -r "$REAL" ] || { echo "NO MEDIDO: no encuentro las disposiciones en $REAL"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K31_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT

fallos=0; pasan=0
caso() {  # <nombre> <rc esperado> <patron> <fichero de disposiciones>
  local nombre="$1" esperado="$2" patron="$3" disp="$4" out rc ok=1
  out=$(REPO="$ORIG" K31_DISP="$disp" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  # HUELLA POSITIVA: el rc solo no basta. K31 tambien enrojece por payloads mudos, asi que
  # sin exigir el mensaje un ROJO por otra razon contaria como acierto.
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-52s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -1 | cut -c1-180)"
  fi
}

echo "K31-control · sujeto: $CHK"
echo "  (cada caso vuelve a correr la sonda: ~100 s por caso)"
echo

echo "EL CASO QUE IMPORTA · una ruta HUECO sin dueño enrojece"
# N1 · el arbol de hoy: las once dispuestas. Es el negativo que pide el encargo.
caso "N1 las 11 dispuestas: VERDE" 0 "TIENEN DUE" "$REAL"

# P1 · se le quita el dueño a UNA. El resto del arbol no cambia, asi que lo unico que puede
# mover el veredicto es la disposicion.
#
# LA VICTIMA SE ELIGE POR SU GRUPO, NO POR SU NOMBRE, y por dos razones. La primera es que el
# caso no caduca si manana se redistribuyen. La segunda la enseño el mapa: la primera version
# escribia el camino literal dos veces y el detector de consumidores acreditaba a ESTE CONTROL
# como consumidor de esa ruta -medido contra origin/main tras regenerar: llamadas 0 -> 2-.
# Es la sexta autocontaminacion de estas campañas y la segunda en un control mio. Aqui no hace
# falta inventar nombres como en K02-control: basta con no escribirlos.
victima=$(grep -E '^/api/' "$REAL" | awk -F'\t' '$2=="ENCHUFAR"{print $1; exit}')
[ -n "$victima" ] || { echo "NO MEDIDO: no hay ninguna linea ENCHUFAR de la que quitar el dueño"; exit 2; }
grep -v -F "$victima	" "$REAL" > "$DIR/sin-una.tsv"
caso "P1 una HUECO pierde su disposicion: ROJO" 1 "sin disposicion" "$DIR/sin-una.tsv"
caso "P2 y la nombra" 1 "$victima" "$DIR/sin-una.tsv"

# P3 · LA OTRA DIRECCION, que es la que envejece sola: una disposicion cuya ruta ya no es
# hueco. Sin este brazo el fichero se vuelve un cementerio que exime rutas que ya no existen.
# Es la declaracion HUERFANA de K88 aplicada aqui.
{ cat "$REAL"; printf '/api/zzz-k31-fantasma\tEXENTA\truta inventada por el control: no existe en api.py\n'; } > "$DIR/con-fantasma.tsv"
caso "P3 disposicion HUERFANA -su ruta no es hueco-: ROJO" 1 "HUERFANA" "$DIR/con-fantasma.tsv"

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, jamas VERDE"
# F1 · CERO DISPOSICIONES NO ES CERO HUECOS SIN DUEÑO. Si el fichero se vacia o cambia de
# formato, "todo dispuesto" seria indistinguible de "no he leido nada". Es la leccion de K60
# aplicada al elegible, y sin este caso el check daria VERDE con el fichero borrado.
printf '# solo comentarios, ninguna linea /api/\n' > "$DIR/vacio.tsv"
caso "F1 disposiciones sin ninguna linea /api/: NOMED" 2 "o esta vacio o cambio de formato" "$DIR/vacio.tsv"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
