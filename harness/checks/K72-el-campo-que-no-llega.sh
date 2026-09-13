#!/usr/bin/env bash
# K72 · EL CAMPO QUE EL BACKEND SIRVE Y LA TARJETA DEJA DE PINTAR
#
# QUE VIGILA. Que los campos que la FASE 3a puso en pantalla sigan LLEGANDO a ella. No que el
# backend los sirva -eso ya lo vigilan otros-, ni que el panel los nombre -nombrar no es
# pintar-: que su valor acabe ESCRITO en el DOM.
#
# POR QUE NO BASTA CON K45. `K45` vigila que las 22 rutas de la familia FOTO lleguen al
# operador, y lo mide mutando el BLOQUE entero. Eso no cubre esto: la tarjeta de setups se
# alimenta de `/api/dashboard/state`, que seguiria pintando `snapshot` y `scalp` aunque
# `missing`, `invalidation` y `horizon` desaparecieran; y el venue del OI sale de
# `data_gaps.exchanges`, que es un campo dentro de una ruta de la familia SERIE. Un bloque
# puede seguir llegando entero mientras el campo que a uno le importa se cae.
#
# COMO MIDE · MUTACION CON MARCA, y no un grep. Se sustituye el valor del campo por una cadena
# reconocible en el payload que la tarjeta LEE DE VERDAD -que no siempre es el que uno
# supondria: los setups los trae la ruta suelta y no el sobre, aunque el sobre tambien los
# tenga- y se busca ESA cadena en el texto del DOM. Buscar el valor original no valdria:
# puede coincidir con cualquier otro numero de la pagina.
#
# EL CONTROL QUE SOSTIENE A LOS DEMAS, y corre en la MISMA pasada: junto a los campos que si
# se pintan va uno que la tarjeta NO pinta (`setup.daily_flow_source`). Si ese tambien
# llegara, este check estaria diciendo que si a todo. Tiene que salir `llega=false`, y si sale
# `true` el veredicto es NO MEDIDO -el instrumento esta roto- y no VERDE.
set -uo pipefail

B=/srv/coinanalyze/harness
_repo_pedido=${REPO:-}
[ -r "$B/env" ] && . "$B/env"
REPO=${_repo_pedido:-${REPO:-/srv/coinanalyze/repo}}
PY="${VENV_PY:-$REPO/.venv/bin/python}"
PANEL="$REPO/harness/panel"
CANONICO=/srv/coinanalyze/repo/harness/panel
[ -f "$PANEL/render.js" ] || PANEL="$CANONICO"
MODULOS="$PANEL/node_modules"
[ -d "$MODULOS" ] || MODULOS="$CANONICO/node_modules"
CACHE="${K72_FIXTURES:-${K31_FIXTURES:-/srv/coinanalyze/harness/estado/k31-fixtures}}"
GUION="${K72_GUION:-$REPO/harness/checks/K72-campos.js}"
[ -f "$GUION" ] || GUION=/srv/coinanalyze/repo/harness/checks/K72-campos.js

command -v node >/dev/null || { echo "NO MEDIDO: no hay node en esta maquina"; exit 2; }
[ -d "$MODULOS" ]          || { echo "NO MEDIDO: falta jsdom; correr npm install en $PANEL"; exit 2; }
[ -f "$GUION" ]            || { echo "NO MEDIDO: falta $GUION"; exit 2; }
[ -d "$CACHE" ]            || { echo "NO MEDIDO: no hay payloads en $CACHE; sin payloads no hay medicion"; exit 2; }

err=$(mktemp)
salida=$(cd "$PANEL" && REPO="$REPO" NODE_PATH="$MODULOS" K72_FIXTURES="$CACHE" \
         timeout 1500 node "$GUION" 2>"$err")
rc=$?
if [ -z "$salida" ]; then
  echo "NO MEDIDO: la sonda no devolvio nada (rc=$rc): $(head -c 200 "$err" | tr '\n' ' ')"
  rm -f "$err"; exit 2
fi
rm -f "$err"
printf '%s\n' "$salida"
exit $rc
