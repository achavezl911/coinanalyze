#!/bin/bash
# K107 · EL RESULTADO QUE NO SALE DE SU PLAN · campana 139 (E3 de las entradas)
#
# QUE JUZGA. Como acabo cada DISPARADO, recalculado DESDE LA BASE Y LAS VELAS con el resolutor del ARBOL
# (app/entradas/resolutor.py): lo que el sujeto GUARDA en entrada_resultado y lo que SIRVE en /api/entradas.
# Condena un resultado que no sale de su plan, un DISPARADO servido VIVO que ya acabo, uno FINAL sin guardar,
# unas cuentas o una cuenta de papel que no son las de sus resultados, y una tabla que no es solo-anadir por
# catalogo. Lo que ya no puede recalcular (sus velas se podaron) lo dice NO MEDIDO para esos, sin absolver ni
# condenar. Los brazos (A-F) los juzga harness/checks/K107-resultado.py; este guion elige el sujeto y llama.
#
# SUJETOS. K107_SUJETO=produccion (por defecto: bin/prodsql, solo lectura, y bin/api /api/entradas sobre 140)
# o local (K107_BASE = DSN de psql, K107_ESQUEMA y K107_RELOJ si la base trae el reloj plantado de los
# controles, K107_SERVIDO = fichero con la respuesta de /api/entradas). Solo lee. En produccion, mientras la
# rama no este desplegada, sale ROJO «FALTA DESPLEGAR»: 140 no tiene entrada_resultado ni sirve resultados.
#
# rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u

REPO=${K107_REPO:-/srv/coinanalyze/repo}
B=${K107_HARNESS:-/srv/coinanalyze/harness}
PY=${K107_PY:-$REPO/.venv/bin/python}
SUJETO=${K107_SUJETO:-produccion}
AYUDANTE="$REPO/harness/checks/K107-resultado.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }

D=$(mktemp -d) || { echo "NO MEDIDO: sin directorio temporal"; exit 2; }
trap 'rm -rf "$D"' EXIT

case "$SUJETO" in
  produccion)
    K107_HARNESS="$B" "$PY" "$AYUDANTE" junta "$D" --produccion > "$D/junta" 2>&1
    rc=$?
    [ "$rc" = 0 ] || { echo "$(head -1 "$D/junta" | cut -c1-200)"; exit 2; }
    TODO=1 "$B/bin/api" /api/entradas > "$D/servido.json" 2> "$D/api.err"
    rc=$?
    [ "$rc" = 0 ] || { echo "NO MEDIDO (CANAL): /api/entradas no contesto (rc=$rc): $(head -c 160 "$D/api.err")"; exit 2; }
    ;;
  local)
    [ -n "${K107_BASE:-}" ] || { echo "NO MEDIDO: K107_SUJETO=local pide K107_BASE"; exit 2; }
    [ -r "${K107_SERVIDO:-}" ] || { echo "NO MEDIDO: K107_SUJETO=local pide K107_SERVIDO legible"; exit 2; }
    args=(--dsn "$K107_BASE")
    [ -n "${K107_ESQUEMA:-}" ] && args+=(--esquema "$K107_ESQUEMA")
    [ -n "${K107_RELOJ:-}" ] && args+=(--reloj "$K107_RELOJ")
    "$PY" "$AYUDANTE" junta "$D" "${args[@]}" > "$D/junta" 2>&1
    rc=$?
    [ "$rc" = 0 ] || { echo "$(head -1 "$D/junta" | cut -c1-200)"; exit 2; }
    cp "$K107_SERVIDO" "$D/servido.json"
    ;;
  *) echo "NO MEDIDO: K107_SUJETO=$SUJETO no es produccion ni local"; exit 2 ;;
esac

"$PY" "$AYUDANTE" juzga "$D" "$REPO" > "$D/juicio" 2>&1
rc=$?
cat "$D/juicio"
exit $rc
