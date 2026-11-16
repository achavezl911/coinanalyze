#!/bin/bash
# K123 · EL ESPACIO DE VARIOS GRAFICOS (campana OF-6b, OF-6 segunda parte)
#
# Abre /espacio con 4 marcos (BTC 1m, BTC 5m, ETH 5m, BTC 1h, vistas del pasado) en el Chromium de K102-mesa (como
# K113 y K121) a 1366x768, lee cada marco por contentWindow y lo juzga con gestos reales (Input.dispatch*):
#   (P) los 4 marcos pintan la vista pedida, sin barras de desplazamiento y sin excepciones
#   (M) el arrastre (en cada marco), la rueda y Fin en un marco cambian ese marco y NO los otros tres (x, y, hash)
#   (F) un clic en un marco le da el foco y el borde, en 1 s
#   (H) tras cada gesto, el hash de /espacio lleva la vista de cada marco en 1 s
#   (T) un NIVEL puesto en BTC 1m sale en BTC 5m y BTC 1h en 1 s con el mismo (t, p), y no en ETH; borrado en BTC 5m
#       desaparece de los otros y no vuelve cuando BTC 1m pone otro
#   (R) recargar /espacio devuelve las cuatro vistas
#   (C) por HTTP: /flujo con frame-ancestors 'self' + SAMEORIGIN; /espacio, /mesa, /libro y una /api con 'none' + DENY
# NO MEDIDO: sin Chromium, o «FALTA DESPLEGAR» si el sujeto no sirve /espacio (404) o sus marcos no publican trazos.
#
#   por omision                 PRODUCCION por https con el netrc
#   K123_BASE=<url>             el ARBOL servido ahi (K123-banco.py); K123_HASTA=<iso> fija el final de las vistas
# Ayudante: harness/checks/K123-espacio.py · control: K123-control.bash.
set -u
REPO=${K123_REPO:-/srv/coinanalyze/repo}
B=${K123_HARNESS:-/srv/coinanalyze/harness}
PY=${K123_PY:-$REPO/.venv/bin/python}
AYUDANTE="$REPO/harness/checks/K123-espacio.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K123_HARNESS="$B" "$PY" "$AYUDANTE" juzga
