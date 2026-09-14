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
# COMO MIDE · MUTACION, y no un grep. Siempre se muta el payload que la tarjeta LEE DE VERDAD
# -que no siempre es el que uno supondria: los setups los trae la ruta suelta y no el sobre,
# aunque el sobre tambien los tenga-. Hay DOS MODOS y el segundo existe por un defecto que tuvo
# este check:
#
#   MARCA    se sustituye el valor por una cadena reconocible y se busca ESA cadena en el DOM.
#            Vale para textos y listas de textos. Buscar el valor ORIGINAL no valdria: puede
#            coincidir con cualquier otro numero o rotulo de la pagina.
#   NUMERO   se muta el valor y se exige que cambie el TEXTO DEL CONTENEDOR de su tarjeta -o de
#            SU FILA-. No se busca ningun valor, asi que no hay coincidencia posible.
#
# POR QUE HIZO FALTA EL SEGUNDO. La version anterior marcaba las cifras anadiendo una CLAVE al
# objeto de ventanas. Eso prueba que la tarjeta ENUMERA las ventanas, NO que escriba sus
# numeros: con la celda del numero borrada, o con el valor escrito como un «—» fijo, el check
# decia VERDE y su linea seguia afirmando que la cifra llegaba ESCRITA.
#
# Y POR QUE ALGUNAS FILAS SE VIGILAN UNA A UNA: una fila DERIVADA enmascara a las suyas. En la
# rafaga de liquidaciones, «Rafaga vs mediana» usa `total` y `baseline_5m`, asi que con la fila
# del Total sin su cifra el texto de la TARJETA seguia moviendose y el check no condenaba. Por
# eso esas cinco apuntan a `fila-liq-*` y no al contenedor.
#
# LOS DOS CONTROLES QUE SOSTIENEN A LOS DEMAS, uno por modo y en la MISMA pasada: junto a los
# campos que si se pintan van `setup.daily_flow_source` (marca) y `operator_read.edge` (numero),
# dos campos SERVIDOS que ninguna tarjeta pinta. Si cualquiera de los dos llegara, este check
# estaria diciendo que si a todo: tienen que salir `llega=false`, y si salen `true` el veredicto
# es NO MEDIDO -el instrumento esta roto- y no VERDE.
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
