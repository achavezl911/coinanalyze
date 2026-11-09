#!/bin/bash
# K122-control · K122 TIENE QUE CONDENAR UN BANCO AL QUE LE FALTA UNA TABLA QUE LEEN SUS RUTAS, NOMBRANDOLA.
#
#   bueno              los bancos del arbol: VERDE
#   sin_hora_hecha     K112-banco sin orderflow_hora_hecha en TABLAS_OF (B1): ROJO nombrando la tabla y K112-banco.py
#   sin_cinta          K109-banco sin orderflow_cinta en TABLAS_OF (B2): ROJO nombrando la tabla y K109-banco.py
#   bancos_de_fdab736  los dos bancos de main@fdab736 (DDL a mano): ROJO, y nombra las cinco que les faltan
#   sin_python         NO MEDIDO (rc 2), ni ROJO ni VERDE
#   arbol_intacto      git status del arbol igual al empezar y al acabar
# Cada plantado es una COPIA en un directorio temporal (la del arbol no se toca) y su `sed` tiene que MORDER una linea
# exactamente o el plantado cuenta como fallido. Estatico: sin base, sin red, sin puertos. Tarda segundos.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K122-los-bancos-siguen-al-esquema.sh"
T=$(mktemp -d /tmp/k122-ctl.XXXXXX) || exit 2
trap 'rm -rf "$T"' EXIT
ESTADO0=$(git -C "$REPO" status --porcelain 2>&1)
pasa=0; total=0
juicio() {  # nombre ok(0/1) que
  total=$((total + 1))
  if [ "$2" = 1 ]; then pasa=$((pasa + 1)); echo "PASA  $1"; else echo "FALLA $1 · $3"; fi
}
corre() {  # dir_bancos -> $T/sal, $rc
  K122_REPO="$REPO" K122_BANCOS_DIR="$1" bash "$CHK" > "$T/sal" 2>&1; rc=$?
}
copia() {  # dir: los dos bancos del arbol y lo que necesitan, en dir/harness/checks
  mkdir -p "$1/harness/checks"
  cp "$AQUI/K109-banco.py" "$AQUI/K112-banco.py" "$1/harness/checks/"
  ln -s "$AQUI/K122-esquema.py" "$1/harness/checks/K122-esquema.py"
  ln -s "$REPO/sql" "$1/sql"
}
muerde() {  # fichero patron sustitucion -> 1 si cambia exactamente una linea
  local f=$1 antes
  antes=$(grep -c -- "$2" "$f")
  sed -i "s/$2/$3/" "$f"
  [ "$antes" = 1 ] && [ "$(diff "$AQUI/$(basename "$f")" "$f" | grep -c '^<')" = 1 ]
}

corre "$AQUI"
ok=0; [ $rc = 0 ] && head -1 "$T/sal" | grep -q '^VERDE' && ok=1
juicio bueno $ok "rc=$rc $(head -c 400 "$T/sal")"

copia "$T/p1"
m=0; muerde "$T/p1/harness/checks/K112-banco.py" ', "orderflow_hora_hecha")' ')' && m=1
corre "$T/p1/harness/checks"
ok=0; [ $m = 1 ] && [ $rc = 1 ] && head -1 "$T/sal" | grep -q '^ROJO: K112-banco.py no crea orderflow_hora_hecha, que leen footprint' && ok=1
juicio sin_hora_hecha $ok "mordio=$m rc=$rc $(head -c 400 "$T/sal")"

copia "$T/p2"
m=0; muerde "$T/p2/harness/checks/K109-banco.py" '"orderflow_cinta", ' '' && m=1
corre "$T/p2/harness/checks"
ok=0; [ $m = 1 ] && [ $rc = 1 ] && head -1 "$T/sal" | grep -q '^ROJO: K109-banco.py no crea orderflow_cinta, que leen footprint' && ok=1
juicio sin_cinta $ok "mordio=$m rc=$rc $(head -c 400 "$T/sal")"

mkdir -p "$T/p3/harness/checks"
git -C "$REPO" show fdab736:harness/checks/K109-banco.py > "$T/p3/harness/checks/K109-banco.py" 2>/dev/null
git -C "$REPO" show fdab736:harness/checks/K112-banco.py > "$T/p3/harness/checks/K112-banco.py" 2>/dev/null
corre "$T/p3/harness/checks"
ok=0
if [ $rc = 1 ] && head -1 "$T/sal" | grep -q '^ROJO: K109-banco.py no crea .* (y 4 mas)'; then
  ok=1
  for x in "K109-banco.py no crea orderflow_cinta" "K109-banco.py no crea orderflow_hora_hecha" \
           "K109-banco.py no crea orderflow_celda_hora" "K112-banco.py no crea orderflow_hora_hecha" \
           "K112-banco.py no crea orderflow_celda_hora"; do
    grep -q "$x" "$T/sal" || ok=0
  done
fi
juicio bancos_de_fdab736 $ok "rc=$rc $(head -c 400 "$T/sal")"

K122_REPO="$REPO" K122_PY=/nonexistent/python bash "$CHK" > "$T/sal" 2>&1; rc=$?
ok=0; [ $rc = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO' && ok=1
juicio sin_python $ok "rc=$rc $(head -c 400 "$T/sal")"

ok=0; [ "$(git -C "$REPO" status --porcelain 2>&1)" = "$ESTADO0" ] && ok=1
juicio arbol_intacto $ok "git status cambio durante el control"

echo "K122-control: $pasa de $total"
[ "$pasa" = "$total" ]
