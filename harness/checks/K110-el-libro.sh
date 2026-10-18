#!/bin/bash
# K110  EL LIBRO (OF-4a, campana 144).
#
# El servicio app/libro.py reconstruye el libro de nueve mercados con la numeracion de cada venue y guarda cada 5 s
# una foto agregada por venue y activo (libro_foto) y su cobertura por minuto (libro_cobertura). Este check lo juzga
# por cinco brazos, y cualquiera lo pone ROJO:
#   (a) VALIDO: en cada foto la mejor compra < la mejor venta, el nivel de cada mejor es floor(mejor / paso) * paso y
#       tiene cantidad, ninguna cantidad negativa, como mucho la banda declarada, paso declarado y multiplo del base de
#       OF-1, ningun nivel fuera del alcance declarado, y la foto en su rejilla.
#   (b) TRIANGULA: la mejor compra y la mejor venta de binance_usdm y bybit_linear contra orderbook_snapshot (el
#       colector VIEJO, independiente, del mismo libro) en los segundos comunes de la hora del venue. Umbral DECLARADO
#       antes de medir (prediccion 2250): por venue y con >= 100 pares, mediana <= 0.5 bps y no mas del 5 % de los
#       pares-lado por encima de 5 bps.
#   (c) COBERTURA por venue: ningun minuto incompleto o ausente sin declarar en data_gap; >= 90 % completos; el
#       servicio escribiendo; y NUNCA RELLENADA: la cobertura cuenta las fotos que hay, un minuto completo tiene sus
#       60 / N fotos, ninguno tiene mas de las que caben en sus segundos, ninguna foto sin fila de cobertura, ningun
#       minuto completo con un hueco declarado encima.
#   (d) LO SERVIDO == LO GUARDADO: /api/libro/fotos de la ultima media hora (al paso guardado y a 5x) y
#       /api/libro/cobertura, contra lo que el ayudante recalcula de las filas con su propia aritmetica.
#   (e) RETENCION: nada mas viejo que su retencion (+2 h), particiones de hoy y de manana, y las funciones vivas de
#       particion gestionando libro_foto.
# Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO (sin las tablas: «FALTA DESPLEGAR»; sin filas: el servicio no ha escrito).
#
#   K110_SUJETO=produccion (por omision)   140 por bin/prodsql y bin/api
#   K110_SUJETO=local K110_BASE=<dsn>      una base de 143; K110_SERVIDO=<dir> con lo servido (ayudante `sirve`);
#                                          K110_VIEJO=<dsn>|produccion (orderbook_snapshot; por omision la misma base);
#                                          K110_RELOJ=<iso>
# Ayudante: harness/checks/K110-libro.py. Control: harness/checks/K110-control.bash.
set -u
REPO=${K110_REPO:-/srv/coinanalyze/repo}
B=${K110_HARNESS:-/srv/coinanalyze/harness}
PY=${K110_PY:-$REPO/.venv/bin/python}
HORAS=6
AYUDANTE="$REPO/harness/checks/K110-libro.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K110_HARNESS="$B" K110_REPO="$REPO" K110_HORAS="$HORAS" "$PY" "$AYUDANTE" juzga
