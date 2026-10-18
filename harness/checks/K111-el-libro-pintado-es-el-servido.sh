#!/bin/bash
# K111  EL LIBRO PINTADO == EL SERVIDO (OF-4b, campana 145).
#
# La pagina /libro pinta la ESCALERA en el DOM y el MAPA DE LIQUIDEZ en un lienzo. Lo pintado lo declara la propia pagina
# en `window.LIBRO_PINTADO` (el mapa, con su eje y sus celdas; la escalera, con sus venues) y en los data-* de cada fila
# de la escalera; esta red lo lee por CDP en un Chromium sin cabeza, como K109, y no se lo cree a pies juntillas: lee los
# PIXELES del lienzo en cada cuadrito de cada celda y el TEXTO de cada fila de la escalera. Tres vistas, RELATIVAS A
# AHORA (la hora entera que acabo hace una hora: las fotos se guardan 3 dias, asi que no caducan como las fijas de K109)
# y declaradas en su salida: 1 h de perpetuos de BTC, 30 min de un venue solo (okx_swap, ETH, al paso 1, en USD) y el
# vivo de BTC. Cinco brazos, cualquiera lo pone ROJO:
#   (P) la pagina pinta su vista sin excepciones y pide la historia de SU hash (con el `cada` de la regla)
#   (V) pide, sirve y pinta UNA familia (o un venue): dos familias sumadas es ROJO
#   (S) lo servido (/api/libro/fotos) == lo recalculado de libro_foto
#   (F) lo pintado == lo servido: cada celda con la suma de los venues que la conocen y cuantos son, ningun nivel
#       desconocido pintado (ni como cero), los HUECOS como huecos, el color (el percentil de lo visible) y sus pixeles,
#       la mejor compra y venta; la escalera con sus niveles, cantidades, acumuladas y mejores, y un venue sin libro
#       valido dicho y sin sumar
#   (C) el canal del vivo que la pagina dice (websocket o sondeo) == el de la red, con la hora de su ultimo libro
# Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO (sin fotos en la ventana; sin la pagina: «FALTA DESPLEGAR»; sin Chromium).
#
#   por omision                       PRODUCCION: la pagina por https con el netrc, las fotos por bin/prodsql
#   K111_BASE=<url> K111_DB=<dsn>     el ARBOL servido ahi (K111-banco.py) y la base de sus fotos; K111_HASTA=<iso> fija
#                                     el final de las vistas del pasado
# Ayudante: harness/checks/K111-libro.py · banco: K111-banco.py · control: K111-control.bash.
set -u
REPO=${K111_REPO:-/srv/coinanalyze/repo}
B=${K111_HARNESS:-/srv/coinanalyze/harness}
PY=${K111_PY:-$REPO/.venv/bin/python}
HORAS=1
AYUDANTE="$REPO/harness/checks/K111-libro.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K111_HARNESS="$B" K111_HORAS="$HORAS" "$PY" "$AYUDANTE" juzga
