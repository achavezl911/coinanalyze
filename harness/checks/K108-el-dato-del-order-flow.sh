#!/bin/bash
# K108  EL DATO DEL ORDER-FLOW (OF-1, campana 140).
#
# El servicio app/orderflow.py guarda cada operacion de nueve mercados en celdas por minuto y nivel, la cinta, las
# grandes y la cobertura. Este check juzga ese dato por seis brazos, y cualquiera lo pone ROJO:
#   (a) TRIANGULA: binance_spot y bybit_spot contra spot_trades_agg, binance_usdm y bybit_linear contra
#       futures_trades_agg -colectores INDEPENDIENTES del mismo mercado-, minuto a minuto donde los dos cubren
#       60 s, el volumen comprador y vendedor en USD. Umbral declarado ANTES de medir (prediccion 0358, apuesta 5):
#       mediana de |dif| <= 0.5 % y no mas del 5 % de los minutos-lado con |dif| > 2 %.
#   (b) CONSISTENCIA: en los minutos completos, las celdas son la agregacion EXACTA de su cinta; todo nivel es
#       multiplo del paso y cae dentro del rango de precios de su minuto; los conteos de las celdas son las
#       operaciones de la cobertura; ningun negativo.
#   (c) COBERTURA por venue: ningun minuto incompleto o ausente sin declarar en data_gap; al menos el 90 % de los
#       minutos completos; y el servicio escribiendo (ultimo minuto con cobertura de hace menos de 10 min).
#   (d) LO SERVIDO == LO RECALCULADO: footprint 5m y perfil de la ultima media hora, a 10x el paso base, contra lo
#       que el ayudante recalcula de las celdas con su propia aritmetica y su propia value area.
#   (e) RETENCION: nada mas viejo que su retencion (+2 h), particiones de hoy y manana, y las funciones vivas de
#       particion gestionando celda y cinta.
#   (f) EL AGRESOR: en cada venue y activo, el lado tiene que concordar con el movimiento del precio mas que el
#       azar. Medido en P1: 0.745-1.000 con el convenio decidido; al reves sale 1 - x. Es el unico brazo que ve un
#       agresor invertido en los cinco venues que (a) no puede triangular.
# Salida: 0 VERDE · 1 ROJO · 2 NO MEDIDO (sin las tablas: «FALTA DESPLEGAR»; sin filas: el servicio no ha escrito).
#
#   K108_SUJETO=produccion (por omision)   140 por bin/prodsql y bin/api
#   K108_SUJETO=local K108_BASE=<dsn>      una base de 143; K108_SERVIDO=<dir> con lo servido (ayudante `sirve`);
#                                          K108_AGREGADOS=<dsn>|produccion (por omision la misma base); K108_RELOJ=<iso>
# Ayudante: harness/checks/K108-orderflow.py. Control: harness/checks/K108-control.bash.
set -u
REPO=${K108_REPO:-/srv/coinanalyze/repo}
B=${K108_HARNESS:-/srv/coinanalyze/harness}
PY=${K108_PY:-$REPO/.venv/bin/python}
HORAS=6
AYUDANTE="$REPO/harness/checks/K108-orderflow.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K108_HARNESS="$B" K108_REPO="$REPO" K108_HORAS="$HORAS" "$PY" "$AYUDANTE" juzga
