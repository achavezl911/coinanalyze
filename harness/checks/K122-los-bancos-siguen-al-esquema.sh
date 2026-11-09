#!/bin/bash
# K122 · LOS BANCOS SIGUEN AL ESQUEMA (remate de los bancos de /flujo, sobre main@fdab736)
#
# K109-banco.py y K112-banco.py escribian su esquema a mano y la app crecio sin ellos: K112 sin orderflow_hora_hecha (la
# 1h de K113, K121 y cualquier sonda, sin medir) y K109 sin orderflow_cinta (la pagina no pintaba en su banco). Este
# check saca de app/orderflow_lectura.py las tablas que leen las funciones que cada banco sirve (sus RUTAS), cruzadas
# con las CREATE TABLE de sql/schema.sql, y las compara con las que crea el DDL del banco (`ddl_banco()`):
#   VERDE  cada tabla leida la crea el banco
#   ROJO   nombrando la primera tabla que falta (y cuantas mas), con las funciones que la leen
#   NOMED  sin python o sin el ayudante
# Estatico: no abre base ni red. Ayudante y juez: K122-esquema.py · control: K122-control.bash.
set -u
REPO=${K122_REPO:-/srv/coinanalyze/repo}
PY=${K122_PY:-$REPO/.venv/bin/python}
AQUI="$REPO/harness/checks"
[ -r "$AQUI/K122-esquema.py" ] || { echo "NO MEDIDO: no encuentro $AQUI/K122-esquema.py"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
BANCOS=${K122_BANCOS_DIR:-$AQUI}  # el control lo apunta a una copia con un banco plantado
"$PY" "$AQUI/K122-esquema.py" juzga "$BANCOS/K109-banco.py" "$BANCOS/K112-banco.py"
rc=$?
case $rc in 0|1) exit $rc ;; *) echo "NO MEDIDO: el juez salio rc=$rc"; exit 2 ;; esac
