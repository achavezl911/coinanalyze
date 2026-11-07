#!/bin/bash
# K120 · LAS LIQUIDACIONES EN EL PRECIO (campana 150)
#
# /flujo (BTC 1m, ind=...liqp) y /libro (BTC, liq=1) pintan cada liquidacion suelta >= 10 000 USD en su (tiempo, precio),
# con radio por raiz de los USD y el color de la orden forzada; la cascada M8 en el eje de tiempo; la ficha de la vela o la
# columna la cuenta. El juez (K120-liq.py) abre las dos paginas en Chromium (CDP), vuelve a pedir la MISMA
# /api/orderflow/indicadores que pidio la pagina y comprueba contra la regla escrita en el juez:
#   (P) pintadas = sueltas de la ruta >= umbral   (X) x/y del eje vigente, radio, color del lado
#   (F) ficha de 4 celdas (racimo «y N mas», hueco SIN DATO, una, ninguna)   (C) cascadas = M8 con n, s de app/anatomia.py
#   (R) el raton no mueve la geometria ni pide a /api   (T) la ruta retiene >= 720 h; con base, sirve toda la ventana
#   (D) 140 (solo lectura): desplegada la retencion hace >= 13 h, hay liquidaciones de mas de 12 h; sin desplegar, lo DICE
#
# Sujeto: PRODUCCION por defecto (sin desplegar las paginas: SIN DESPLEGAR, no condena). K120_FLUJO / K120_LIBRO: los bancos
# del arbol (K112-banco sirve y K120-banco libro) que monta K120-control.bash, con K120_*_HASTA y K120_*_DB.
# rc 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u
REPO=${K120_REPO:-/srv/coinanalyze/repo}
B=${K120_HARNESS:-/srv/coinanalyze/harness}
PY=${K120_PY:-$REPO/.venv/bin/python}
AYUDANTE="$REPO/harness/checks/K120-liq.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
K111_HARNESS="$B" K113_HARNESS="$B" "$PY" "$AYUDANTE" juzga
