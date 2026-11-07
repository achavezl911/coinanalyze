#!/bin/bash
# K114  EL RATON, LA PANTALLA Y SU RED EN /libro (campana 149, ronda C).
#
# /libro se maneja como el mapa de liquidez de una plataforma profesional: la rueda que hace zoom con ancla, Mayus y
# Ctrl, los ejes que se arrastran, el doble clic que vuelve al modo de antes, el menu del eje (Ultimo, BBO, Ninguno),
# el teclado, PRESENTE y la linea del presente; la cruz con sus etiquetas y la ficha de la celda. Esta red lo hace con
# GESTOS REALES por CDP en un Chromium sin cabeza (la vista por omision en 1920x1080 y 1366x768, BTC perp 1 h del
# pasado, ETH en USD) y tras cada gesto mira el contrato (LIBRO_PINTADO.mapa.eje, LIBRO_CRUZ, EL_MAPA.estado()) contra
# las respuestas crudas de /api/libro/* y contra el DOM. Cinco brazos, cualquiera lo pone ROJO:
#   (P) la pagina    sin excepciones; ningun gesto dentro de lo cargado pide fotos ni honda
#   (C) la cruz      la celda bajo el cursor (recalculada con la junta de K111) = LIBRO_CRUZ = la ficha = #lectura;
#                    las etiquetas de los ejes al paso; la escalera resalta ese precio
#   (R) el raton     cada gesto mueve lo que debe y nada mas (I-01..I-06, H-10, el menu, con columnas vivas llegando)
#   (E) el aspecto   E-01, E-02 (el comprador de /flujo y la mesa, dE2000 >= 20), E-03, E-04
#   (A) la ayuda     se abre y se cierra; nombra lo que (R) ejerce y nada mas; los parrafos del pie no estan
# Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO (sin la pagina: «FALTA DESPLEGAR»; sin Chromium; sin canal).
#
#   por omision                       PRODUCCION: la pagina por https con el netrc
#   K114_BASE=<url>                   el ARBOL servido ahi (K111-banco.py); K114_HASTA=<iso> fija el pasado;
#                                     K114_ETH=<familia> la de ETH (por omision spot; el banco de K111 no trae spot de ETH)
# Ayudante: harness/checks/K114-raton-libro.py · control: K114-control.bash.
set -u
REPO=${K114_REPO:-/srv/coinanalyze/repo}
B=${K114_HARNESS:-/srv/coinanalyze/harness}
PY=${K114_PY:-$REPO/.venv/bin/python}
AYUDANTE="$REPO/harness/checks/K114-raton-libro.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K111_HARNESS="$B" K113_HARNESS="$B" "$PY" "$AYUDANTE" juzga
