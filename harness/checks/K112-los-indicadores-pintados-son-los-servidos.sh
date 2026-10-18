#!/bin/bash
# K112  LOS INDICADORES PINTADOS == LOS SERVIDOS (OF-5a, campana 146).
#
# /flujo pinta, DEBAJO del footprint y con su mismo eje de tiempo, los paneles de indicadores (delta por vela, CVD,
# interes abierto de Binance y de Bybit con su cambio, funding y predicho, largos/cortos, liquidaciones de 5 min y
# sueltas), las marcas de las operaciones GRANDES sobre el footprint, y a su derecha la CINTA de ordenes agregadas.
# Lo pintado lo declara la pagina (window.FLUJO_INDICADORES, FLUJO_PINTADO.grandes; la cinta es el propio DOM) y esta
# red lo lee por CDP en un Chromium sin cabeza, como K109 y K111, sin creerselo a pies juntillas (el fillText de cada
# lienzo, el eje recalculado del footprint, lo que el navegador dice que hay encima). Cinco vistas RELATIVAS A AHORA (la
# hora entera que acabo hace una hora: no caducan): la vista POR OMISION en vivo en dos pantallas, 1 h y 24 h con todos
# los paneles, y otra familia con otro filtro. Cinco brazos, cualquiera lo pone ROJO:
#   (P) la pagina pide lo de su hash (la ventana y el marco del footprint; la cinta con su filtro; en vivo SOLO lo nuevo)
#   (V) las grandes y la cinta, de UNA familia
#   (S) lo servido == lo recalculado de las tablas (cubos de 5 min y su estado, el cero certificado, sueltas, ordenes,
#       grandes)
#   (F) lo pintado == lo servido: cada panel con su fuente escrita, sus puntos y sus HUECOS (nunca un cero, ni en el
#       CVD), las grandes en su vela, cada fila de la cinta
#   (G) ningun panel tapa el footprint, van debajo con su mismo eje de tiempo, la cinta a la derecha
# Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO (sin dato en la ventana; sin la pagina o sus rutas: «FALTA DESPLEGAR»; sin
# Chromium).
#
#   por omision                       PRODUCCION: la pagina por https con el netrc, las tablas por bin/prodsql
#   K112_BASE=<url> K112_DB=<dsn>     el ARBOL servido ahi (K112-banco.py) y su base; K112_HASTA=<iso> fija el final de
#                                     las vistas del pasado
# Ayudante: harness/checks/K112-indicadores.py · banco: K112-banco.py · control: K112-control.bash.
set -u
REPO=${K112_REPO:-/srv/coinanalyze/repo}
B=${K112_HARNESS:-/srv/coinanalyze/harness}
PY=${K112_PY:-$REPO/.venv/bin/python}
HORAS=1
AYUDANTE="$REPO/harness/checks/K112-indicadores.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K112_HARNESS="$B" K112_HORAS="$HORAS" "$PY" "$AYUDANTE" juzga
