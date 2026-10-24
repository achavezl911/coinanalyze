#!/bin/bash
# K117 · EL BOT · campana BOT-2
#
# QUE JUZGA, en PRODUCCION (140), el bot de Telegram (app/bot, unidad coinalyze-bot):
#   servicio  la unidad active/running (systemctl show por bin/prod)
#   latido    bot_estado con un latido de hace <= 180 s
#   bybit     la clave en SOLO LECTURA y atada a la IP segun el ESTADO que el bot publica (nadie lee la clave)
#   alertas   las rafagas y clases registradas (bot_evento) en las ultimas HORAS horas, menos 45 min (la ingesta re-escribe
#             las ultimas 40 velas, app/cutoffs.py:5), y desde el dia del primer arranque == las que da el detector de
#             app/rafagas.py (Z = 4, el resto congelado) sobre el ohlcv 1min de 140, reproducido con el pegamento de K117
#   gasto     la suma de bot_llamada de cada dia UTC de los ultimos 7 <= su tope
#   codigo    ninguna ruta de ordenes, retiros ni transferencias de Bybit en app/bot del ARBOL ni del RELEASE de 140
# Algo que condenar -> ROJO con la primera condena (y las demas debajo); si no, lo que no se pudo mirar -> NO MEDIDO
# (sin el servicio, todo lo de 140 es NO MEDIDO «FALTA DESPLEGAR»); todo mirado y bien -> VERDE.
#
# SUJETOS. K117_HARNESS (el arnes cuyos bin/prodsql y bin/prod se usan; los dobles de K117-control y de K97),
# K117_REPO (el arbol: su app/rafagas.py es el detector y su app/bot el codigo que se mira). Ayudante: K117-bot.py.
#
# rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u
HORAS=24
REPO=${K117_REPO:-/srv/coinanalyze/repo}
B=${K117_HARNESS:-/srv/coinanalyze/harness}
PY=${K117_PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=$(command -v python3)
AYUDANTE="$REPO/harness/checks/K117-bot.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: K117 no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: K117 sin python"; exit 2; }

D=$(mktemp -d) || { echo "NO MEDIDO: K117 sin directorio temporal"; exit 2; }
trap 'rm -rf "$D"' EXIT
# -S: sin site, para que el .venv editable no cambie el arbol que se importa (el ayudante lo comprueba)
K117_REPO="$REPO" K117_HARNESS="$B" K117_HORAS="$HORAS" "$PY" -S "$AYUDANTE" > "$D/juicio" 2>&1
rc=$?
case "$rc" in
  0|1|2) cat "$D/juicio"; exit "$rc" ;;
esac
echo "NO MEDIDO: K117 el ayudante cayo con rc=$rc: $(tail -1 "$D/juicio" | cut -c1-160)"
exit 2
