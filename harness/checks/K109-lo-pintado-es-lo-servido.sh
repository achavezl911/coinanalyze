#!/bin/bash
# K109  LO PINTADO == LO SERVIDO, para el FOOTPRINT (OF-2, campana 142).
#
# La pagina /flujo pinta en un LIENZO, asi que lo pintado no esta en el DOM: lo declara la propia pagina en
# `window.FLUJO_PINTADO` (static/flujo/flujo-dibujo.js), apuntado en el mismo sitio donde dibuja, y esta red lo lee por
# CDP en un Chromium sin cabeza, como K106. No se lo cree a pies juntillas: cada numero que el contrato dice pintado
# tiene que estar en el registro de fillText del lienzo, que la sonda intercepta antes de que cargue la pagina.
# Tres vistas FIJAS del pasado (reproducibles), y cinco brazos, cualquiera lo pone ROJO:
#   (P) la pagina pinta su vista, sin excepciones, y pide el footprint de SU hash
#   (V) pide los venues de UNA familia, la de su hash: dos familias sumadas es ROJO
#   (S) lo servido == lo recalculado desde las CELDAS: niveles, totales, POC, value area de cada vela, cobertura y el
#       paso automatico
#   (F) lo pintado == lo servido: cada nivel en su fila, sus numeros, el color del delta, el POC, la value area, el
#       resumen y el ESTADO de cada vela (abierta, hueco, incompleta con cuantos le faltan, vacia, completa)
#   (D) los desequilibrios pintados == los de la regla de la campana (diagonal x3, minimo la media por nivel, apilado 3)
# Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO (sin la pagina: «FALTA DESPLEGAR»; sin Chromium; sin dato en la ventana).
#
#   por omision                       PRODUCCION: la pagina por https con el netrc, las celdas por bin/prodsql
#   K109_BASE=<url> K109_DB=<dsn>     el ARBOL servido ahi (K109-banco.py) y la base de sus celdas
# Ayudante: harness/checks/K109-footprint.py · banco: K109-banco.py · control: K109-control.bash.
set -u
REPO=${K109_REPO:-/srv/coinanalyze/repo}
B=${K109_HARNESS:-/srv/coinanalyze/harness}
PY=${K109_PY:-$REPO/.venv/bin/python}
AYUDANTE="$REPO/harness/checks/K109-footprint.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K109_HARNESS="$B" "$PY" "$AYUDANTE" juzga
