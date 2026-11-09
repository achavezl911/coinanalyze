#!/bin/bash
# K121 · LOS TRAZOS DONDE SE PUSIERON (campana 146-D, OF-6 primera parte: el dibujo en /flujo)
#
# Abre /flujo en el Chromium de K102-mesa (como K113) a 1366x768 sobre una vista del pasado de BTC en 1m, pone con
# gestos reales un NIVEL, una LINEA, un FIBONACCI y un CANAL DE REGRESION, y los juzga tras ponerlos, tras un arrastre
# sin herramienta, tras la rueda (tiempo y precio), tras cambiar a 5m y tras recargar. La red le quita a cada respuesta
# del footprint UNA vela (la misma por marco): el servidor rellena los intervalos, y sin una vela que falte una x por
# indice no se distingue de la buena.
#
#   (X) cada punto en la x de su instante (sobre las velas recibidas) y la y de su precio, 1 px
#   (F) Fibonacci en 0 · 0.236 · 0.382 · 0.5 · 0.618 · 0.786 · 1, cada precio y su y
#   (C) el canal: su propia regresion de los cierres del tramo, pendiente y sigma (poblacional) a 1e-6 relativo, n y
#       los extremos de la media y las dos paralelas a +-2 sigma; con menos de 3 cierres, sin pintar y diciendolo
#   (G) los mismos trazos (id, tipo, puntos) tras cambiar de marco y tras recargar
#   (H) sin herramienta, un arrastre lejos de los trazos mueve el grafico y no pone nada
#   (P) cuatro gestos dejan cuatro trazos, Esc suelta la herramienta, la rueda cambia la vista, cero excepciones
#   (K) al poner, cada punto guardado cae en el pixel de su clic (1 px), con la escala y las velas que la pagina
#       tenia justo antes de ese clic (el instante y el precio que el clic quiere decir)
#
# NO MEDIDO: sin Chromium, sin celdas en la hora de la vista, o «FALTA DESPLEGAR» si el sujeto no sirve
# flujo-trazos.js o su FLUJO_PINTADO no trae `trazos`.
#
#   por omision                       PRODUCCION: la pagina por https con el netrc, las celdas por bin/prodsql
#   K121_BASE=<url> K121_DB=<dsn>     el ARBOL servido ahi (K112-banco.py con --mas K113-celdas.tsv.xz) y su base;
#                                     K121_HASTA=<iso> fija el final de la vista
# Ayudante: harness/checks/K121-trazos.py · control: K121-control.bash.
set -u
REPO=${K121_REPO:-/srv/coinanalyze/repo}
B=${K121_HARNESS:-/srv/coinanalyze/harness}
PY=${K121_PY:-$REPO/.venv/bin/python}
HORAS=1
AYUDANTE="$REPO/harness/checks/K121-trazos.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K121_HARNESS="$B" K121_HORAS="$HORAS" "$PY" "$AYUDANTE" juzga
