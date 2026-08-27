#!/bin/bash
# K31  LA CIFRA LLEGA A LA PANTALLA  ·  eslabones 5 y 6 de la cadena
#
# CRITERIO REESCRITO EL 2026-08-27, y el motivo esta medido. El criterio viejo era
#   grep -qF "$ruta" static/app.js
# o sea: TEXTO. Se cumple escribiendo la ruta en un comentario, que es exactamente el
# defecto de K44 -un criterio que se cumplia BORRANDO un comentario-. Y no puede
# sostener la decision de producto de Alejandro del 2026-08-27T17:05:32Z: "lo calculado
# tiene que LLEGAR AL DASHBOARD". Que una ruta se mencione no es que su cifra se pinte.
#
# AHORA SE MIDE EJECUTANDO EL PANEL. harness/panel/ monta el static/index.html y el
# static/app.js REALES en un DOM (jsdom, node), sirve los payloads REALES de produccion
# y abre las ocho secciones como hace un operador. De ahi salen las dos mitades:
#
#   ESLABON 5 · que rutas PIDE el panel. Ya no se grepea: se observa.
#   ESLABON 6 · si la cifra LLEGA A LA PANTALLA, por MUTACION: se cambia el valor en el
#               payload y se vuelve a pintar. Si el DOM no se mueve, no llega. Un
#               comentario no puede cumplir esto.
#
# POR QUE LA MUTACION ES DE FIAR, y como se protege de las dos tautologias:
#   · el reloj se CONGELA. Medido: sin congelarlo dos renders del mismo payload dan
#     "497s" y "501s", asi que cualquier mutacion "movia" la pantalla y todo salia
#     cableado. Congelado, el render es funcion pura del payload.
#   · el CONTROL exige que dos renders sin mutar sean IDENTICOS byte a byte. Si no lo
#     son, el instrumento es inestable y esto sale NO MEDIDO, no VERDE.
#   · la mutacion PRESERVA EL TIPO. Si rompiera el JSON la seccion fallaria entera y
#     todos los campos pareceria que llegan a la pantalla.
#   · los NULOS se rellenan, porque un nulo no se puede mover. Medido: los horizontes
#     3d/1d de /api/structure-detail vienen todos en null, el panel pinta "Sin nivel
#     estructural" y al rellenarlos pasa a "Tesis invalida al perder $4.24K en 3D": el
#     cable esta bien y lo que falta es el DATO. Sin rellenar, saldria como no cableado.
#
# LO QUE ESTE CHECK NO PUEDE AFIRMAR, y se declara en vez de disimularse:
#   · jsdom NO MAQUETA. Prueba que el valor se escribe en el DOM de su seccion, no que
#     el pixel sea visible: un display:none se le escapa. Cierra el eslabon 5 entero y
#     el 6 hasta el DOM; del DOM al pixel no hay instrumento en 143.
#   · lo que se pinta en CANVAS queda fuera. El motor de graficos es un doble, asi que
#     las series de lightweight-charts no se pueden medir por DOM.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PANEL="$REPO/harness/panel"
PY="${VENV_PY:-$REPO/.venv/bin/python}"

# NO PUBLICADAS EN EL PANEL, cada una con su motivo medido. No es una lista de
# conveniencia: sin cita, el proximo que la lea no sabra si es real.
#   ai/context, ai/context/bundle   los consume el ai-bridge
#                                   (coinalyze_client.py:34,:42 en /opt/coinalyze-ai-bridge)
#   ai/profiles                     lo llama la smoke() del desplegador (deploy-coinalyze:73-88)
#   stream                          lo consume el panel por EventSource, no por fetch
#                                   (app.js:1648); la sonda solo observa fetch()
#   zone/analysis, level/breakout, range/validate
#                                   las pide el panel SOLO ante una accion del operador
#                                   (app.js:2578, :2740, :2865), no al abrir la seccion
# $(echo ...) sin comillas COLAPSA el salto de linea a un espacio. Sin eso la lista
# parece correcta y no lo es: el case busca *" /api/stream "* y detras de /api/stream
# habia un \n, asi que la excepcion no casaba y la ruta se contaba como huerfana. Una
# ruta de mas en el veredicto por un espacio en blanco.
NO_PANEL=$(echo /api/ai/context /api/ai/context/bundle /api/ai/profiles /api/stream \
                /api/zone/analysis /api/level/breakout /api/range/validate)
# SE PINTAN EN CANVAS, fuera del alcance del DOM. Medido: mutar el payload entero no
# mueve una sola letra del DOM porque su destino es la serie de velas (app.js:227).
CANVAS="/api/ohlcv"

CANONICO=/srv/coinanalyze/repo/harness/panel
# EL INSTRUMENTO NO ES PARTE DEL ARBOL QUE SE MIDE, y el gate de K15 lo demostro: corre
# el check del PR contra un worktree de origin/main, donde harness/panel todavia NO
# existe, y salia NO MEDIDO -"el PR ha roto la capacidad de medir"- sin que nada
# estuviera roto. La sonda cae al instrumento canonico cuando el arbol medido no lo
# trae. Lo que SIGUE saliendo de $REPO es el SUJETO: static/index.html y static/app.js.
[ -f "$PANEL/probe.js" ] || PANEL="$CANONICO"
MODULOS="$PANEL/node_modules"
[ -d "$MODULOS" ] || MODULOS="$CANONICO/node_modules"

[ -f "$PANEL/probe.js" ]         || { echo "NO MEDIDO: no hay sonda de panel ni en $REPO ni en $CANONICO"; exit 2; }
[ -d "$MODULOS" ]                || { echo "NO MEDIDO: falta jsdom; correr npm install en $PANEL"; exit 2; }
command -v node >/dev/null       || { echo "NO MEDIDO: no hay node en esta maquina"; exit 2; }
[ -x "$PY" ]                     || { echo "NO MEDIDO: falta el venv del repo"; exit 2; }

rutas=$(cd "$REPO" && "$PY" -c "
from app.api import app
print('\n'.join(sorted(r for r in app.openapi()['paths'] if r.startswith('/api/'))))
" 2>/dev/null)
[ -n "$rutas" ] || { echo "NO MEDIDO: no se pudieron enumerar las rutas"; exit 2; }

# LOS PAYLOADS SE CACHEAN 30 MINUTOS, Y LA EDAD SE IMPRIME. Capturar de cero son 32 GET
# a produccion y 2m40s en cada verify; con cache son 104s. Lo que se cachea es el DATO,
# no el veredicto: el panel se EJECUTA siempre, asi que el eslabon 5 -que rutas pide- y
# el 6 -si mutar mueve el DOM- se miden de nuevo cada vez. Si la cache envejece, se
# recaptura. Un 5xx nuevo lo caza K20, que barre las rutas en cada corrida.
CACHE="${K31_FIXTURES:-$B/estado/k31-fixtures}"
TTL=${K31_TTL:-1800}
edad=""
if [ -f "$CACHE/_urls.json" ]; then
  edad=$(( $(date +%s) - $(stat -c %Y "$CACHE/_urls.json") ))
  [ "$edad" -gt "$TTL" ] && { rm -rf "$CACHE"; edad=""; }
fi
# REPO se EXPORTA: render.js lee $REPO/static/app.js y sin exportarlo caeria al valor
# por defecto, o sea que el gate de K15 mediria el app.js del arbol de trabajo creyendo
# medir el de origin/main. El sujeto tiene que salir del arbol que se esta midiendo.
err=$(mktemp)
salida=$(cd "$PANEL" && REPO="$REPO" NODE_PATH="$MODULOS" K31_FIXTURES="$CACHE" timeout 900 node probe.js 2>"$err")
# EL STDERR NO SE TIRA. Antes iba a /dev/null y una excepcion de la sonda se publicaba
# como "no devolvio nada", que no dice ni donde ni por que. La causa viaja en la linea.
[ -n "$salida" ] || { echo "NO MEDIDO: la sonda del panel no devolvio nada: $(tr "\n" " " < "$err" | cut -c1-200)"; rm -f "$err"; exit 2; }
rm -f "$err"

leer() { printf '%s' "$salida" | "$PY" -c "import json,sys;d=json.load(sys.stdin);print(d.get('$1',''))"; }
lista() { printf '%s' "$salida" | "$PY" -c "import json,sys;d=json.load(sys.stdin);print(' '.join(d.get('$1',[])))"; }

[ -z "$(leer error)" ]                    || { echo "NO MEDIDO: $(leer error)"; exit 2; }
[ "$(leer control_determinista)" = "True" ] || { echo "NO MEDIDO: el instrumento no es determinista; dos renders sin mutar difieren"; exit 2; }
[ "$(leer secciones)" -ge 8 ] 2>/dev/null || { echo "NO MEDIDO: el panel expuso $(leer secciones) secciones, se esperaban 8"; exit 2; }

pedidas=" $(lista rutas_pedidas) "
llegan=" $(lista llegan_a_la_pantalla) "
segundos=$(leer segundos)

# ESLABON 5 · toda ruta declarada o la pide el panel, o esta declarada como no-panel.
huerfanas=""; total=0
for r in $rutas; do
  total=$((total+1))
  case " $NO_PANEL " in *" $r "*) continue ;; esac
  case "$pedidas" in *" $r "*) continue ;; esac
  huerfanas="$huerfanas $r"
done

# ESLABON 6 · todo payload que el panel pide llega a la pantalla, o esta declarado canvas.
mudas=""
for r in $(lista no_llegan); do
  case " $CANVAS " in *" $r "*) continue ;; esac
  mudas="$mudas $r"
done

nh=$(printf '%s' "$huerfanas" | wc -w)
nm=$(printf '%s' "$mudas" | wc -w)
np=$(printf '%s' "$llegan" | wc -w)

if [ "$nh" -gt 0 ] || [ "$nm" -gt 0 ]; then
  {
    printf 'ROJO: %d de %d rutas calculadas NO llegan a la pantalla' "$nh" "$total"
    [ "$nm" -gt 0 ] && printf ' y %d payloads pedidos no mueven un pixel:%s' "$nm" "$mudas"
    printf ' · %d payloads SI llegan, probados por mutacion en %ss (payloads de hace %ss)\n' "$np" "$segundos" "${edad:-0}"
    printf 'sin cablear:%s\n' "$huerfanas"
  } | cut -c1-600
  exit 1
fi
echo "las $total rutas de /api/ o las pide el panel o estan declaradas, y los $np payloads pedidos mueven el DOM al mutarlos (${segundos}s, payloads de hace ${edad:-0}s)"
