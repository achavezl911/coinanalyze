#!/bin/bash
# K119 · LA SOMBRA ES EL ESTUDIO · campana BOT-5
#
# QUE JUZGA: que la candidata congelada que el bot cuenta en sombra (app/bot/sombra.py, tabla bot_sombra) es la
# MISMA que midio el estudio (scripts/anatomia_extrae.py + scripts/anatomia_estudio.py):
#   banco       base DESECHABLE con la muestra real de la cinta (2026-10-21 04-05Z, SOL, citada por sha256) y las
#               horas sinteticas de K119-sintetico.tsv.xz; las filas entran segun su ts, como si llegaran, y el camino
#               VIVO del bot (Sombra.tic, con tres reinicios y una parada de 30 min) recorre los minutos. VERDE si los
#               disparos, la entrada, el resultado, la salida y el neto (a 1e-12) son los de K119-esperado.json (lo que
#               dijo el estudio sobre los mismos TSV, harness/checks/K119-genera.py) y cada sin_dato cae en una
#               decision que el estudio deja sin etiqueta. Tambien: el recalculo desde la cinta da lo que el bot.
#   produccion  solo lectura por bin/prodsql: las filas de bot_sombra de las ultimas 24 h de su cursor contra el
#               mismo recalculo desde la cinta de 140. Sin la tabla en 140: SIN DESPLEGAR, SIN JUZGAR (no condena
#               ni falta). Sin canal: NO MEDIDO. K119_SIN_PRODUCCION=1 no lo mira (lo usa K119-control).
# Algo que condenar -> ROJO; si no, lo que no se pudo mirar -> NO MEDIDO; todo mirado y bien -> VERDE.
#
# SUJETOS. K119_REPO (el arbol: su app/ y su sql/schema.sql), K119_HARNESS (su bin/prodsql). Ayudante: K119-sombra.py.
# rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u
REPO=${K119_REPO:-/srv/coinanalyze/repo}
B=${K119_HARNESS:-/srv/coinanalyze/harness}
PY=${K119_PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=/srv/coinanalyze/repo/.venv/bin/python
AYUDANTE="$REPO/harness/checks/K119-sombra.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: K119 no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: K119 sin python"; exit 2; }
command -v createdb > /dev/null || { echo "NO MEDIDO: K119 sin createdb"; exit 2; }

D=$(mktemp -d) || { echo "NO MEDIDO: K119 sin directorio temporal"; exit 2; }
X="k119_$$_$(date +%s)"
trap 'dropdb -h /var/run/postgresql --if-exists "$X" > /dev/null 2>&1; rm -rf "$D"' EXIT
createdb -h /var/run/postgresql "$X" > "$D/db" 2>&1 || { echo "NO MEDIDO: K119 createdb: $(tail -1 "$D/db")"; exit 2; }
psql -X -q -h /var/run/postgresql -d "$X" -v ON_ERROR_STOP=1 -f "$REPO/sql/schema.sql" > "$D/db" 2>&1 \
  || { echo "ROJO: K119 el sql/schema.sql del arbol no se aplica a una base vacia: $(grep -m1 ERROR "$D/db" | cut -c1-200)"; exit 1; }
SITE=$("$PY" -c 'import sysconfig; print(sysconfig.get_path("purelib"))' 2> /dev/null)
# -S: sin site, para que el .venv editable no cambie el arbol que se importa (el ayudante lo comprueba)
K119_REPO="$REPO" K119_HARNESS="$B" K119_SITE="$SITE" K119_DB="postgresql:///$X?host=/var/run/postgresql" \
  timeout 1800 "$PY" -S "$AYUDANTE" > "$D/juicio" 2>&1
rc=$?
case "$rc" in
  0|1|2) cat "$D/juicio"; exit "$rc" ;;
esac
echo "NO MEDIDO: K119 el ayudante cayo con rc=$rc: $(tail -1 "$D/juicio" | cut -c1-300)"
exit 2
