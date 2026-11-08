#!/bin/bash
# Corre entregas/cuarto_borde.py contra un arbol, con base desechable.
#   entregas/cuarto_borde.sh main  -> worktree congelado de 0f73414 (el test de main)
#   entregas/cuarto_borde.sh rama  -> el arbol de trabajo
# Salida y progreso en x1-tmp/cuarto-borde-<arbol>.txt; la ultima linea, «FIN rc=..».
REPO=/srv/coinanalyze/repo
X=/srv/coinanalyze/x1-tmp
OUT=$X/cuarto-borde-$1.txt
: > "$OUT"
case "$1" in
  main) ARBOL=$X/cb-main
        [ -d "$ARBOL" ] || git -C "$REPO" worktree add --detach "$ARBOL" 0f73414 >> "$OUT" 2>&1 ;;
  rama) ARBOL=$REPO ;;
  *) echo "uso: $0 main|rama"; exit 2 ;;
esac
DB=cb_borde_$$
createdb --host=/var/run/postgresql "$DB" >> "$OUT" 2>&1
TEST_DATABASE_URL="postgresql:///$DB?host=/var/run/postgresql" \
  "$REPO/.venv/bin/python" "$REPO/entregas/cuarto_borde.py" "$ARBOL" >> "$OUT" 2>&1
rc=$?
dropdb --host=/var/run/postgresql --if-exists "$DB" >> "$OUT" 2>&1
echo "FIN rc=$rc" >> "$OUT"
