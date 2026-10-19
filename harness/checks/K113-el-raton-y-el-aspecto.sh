#!/bin/bash
# K113  EL RATON Y EL ASPECTO DE /flujo (OF-6a, campana 148).
#
# /flujo se usa como el footprint de una plataforma profesional (entregas/20261018-2130-INVESTIGACION-plataformas.md,
# la especificacion que esta campana toma): la rueda, Mayus+rueda y Ctrl+rueda, los ejes que se arrastran, el doble
# clic que vuelve a AUTO, seguir la ultima vela, el teclado, el menu del eje, la regla; la cruz con sus etiquetas, la
# ficha junto al cursor, las cifras que salen cuando caben, las filas de resumen. Esta red lo hace con GESTOS REALES
# por CDP (Input.dispatchMouseEvent y dispatchKeyEvent) en un Chromium sin cabeza, en la vista POR OMISION en dos
# pantallas y en otras, y tras cada gesto mira el contrato de la pagina (window.FLUJO_PINTADO, FLUJO_CRUZ, FLUJO_FICHA,
# FLUJO_REGLA, FLUJO_TPO) sin creerselo: el registro de fillText de cada lienzo, el DOM y las respuestas que llegaron
# por la red. Seis brazos, cualquiera lo pone ROJO:
#   (P) la pagina    carga sin excepciones y NINGUN gesto vuelve a pedir la historia: lo servido no cambia por el raton
#   (F) lo pintado   == lo servido tras cada gesto: cada nivel en la fila de su precio y con sus cifras, el color y su
#                    paso, los desequilibrios, los POC, las filas de resumen (el CVD de sesion recalculado EXACTO)
#   (C) la cruz      y la ficha dicen la vela y la celda bajo el cursor (y la cruz sigue por los paneles)
#   (T) el texto     cada cifra sale si cabe (fila >= 10 px y la semicelda con 4 px) y no sale si no (F-09)
#   (R) el raton     la geometria cambia como el gesto manda: el eje que tenia que moverse se movio y el otro no
#   (E) el aspecto   los corchetes de la investigacion: E-01, E-02 (con las tres simulaciones de daltonismo y el mismo
#                    comprador en /libro y la mesa), E-03, E-04, F-01, F-02, F-04, F-07, F-08, I-04, I-05, I-07, I-08
# Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO (sin la pagina o anterior a OF-6a: «FALTA DESPLEGAR»; sin Chromium; sin dato).
#
#   por omision                       PRODUCCION: la pagina por https con el netrc, las celdas por bin/prodsql
#   K113_BASE=<url> K113_DB=<dsn>     el ARBOL servido ahi (K112-banco.py con --mas K113-celdas.tsv.xz) y su base;
#                                     K113_HASTA=<iso> fija el final de las vistas del pasado
# Ayudante: harness/checks/K113-raton.py · control: K113-control.bash.
set -u
REPO=${K113_REPO:-/srv/coinanalyze/repo}
B=${K113_HARNESS:-/srv/coinanalyze/harness}
PY=${K113_PY:-$REPO/.venv/bin/python}
HORAS=1
AYUDANTE="$REPO/harness/checks/K113-raton.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K113_HARNESS="$B" K113_HORAS="$HORAS" "$PY" "$AYUDANTE" juzga
