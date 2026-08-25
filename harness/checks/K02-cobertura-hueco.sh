#!/bin/bash
# K02  la API tiene que declarar el hueco en LOS NUEVE endpoints de serie, no en
# unos pocos. Hoy el enmascarado (mask_gapped_series_rows, app/api.py:230) solo lo
# aplica la familia CVD. Medido el 2026-08-25 resolviendo la ruta que envuelve cada
# llamada: /api/cvd, /api/cvd/spot y /api/cvd/divergence. Tres de nueve.
# Fuera quedan ohlcv, oi, liquidations, whale/delta, daily, funding-context y
# oi-context, que es donde vive casi todo lo que mira el operador.
#
# La cobertura NO se escribe a mano aqui: se DERIVA de app/api.py resolviendo, para
# cada llamada a mask_gapped_series_rows, el @app.get que la contiene. Asi el dia que
# alguien enmascare /api/ohlcv el check se entera solo, y el dia que alguien mueva
# una ruta no se queda mintiendo con una lista vieja. Es la leccion de K05: una lista
# escrita a mano envejece sin avisar.
#
# K03 mide otra cosa y las dos hacen falta: K03 pregunta si la RESPUESTA declara el
# hueco con ventana y estado; esta pregunta cuantos endpoints pasan siquiera por el
# enmascarado. Enmascarar deja nulos -que es lo que K03 dice que no basta-, asi que
# esta unidad es el suelo y K03 el techo.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
API="$REPO/app/api.py"
SERIE="/api/ohlcv /api/oi /api/liquidations /api/whale/delta /api/daily /api/cvd /api/cvd/spot /api/funding-context /api/oi-context"

[ -r "$API" ] || { echo "NO MEDIDO: no se puede leer app/api.py"; exit 2; }

grep -q 'async def mask_gapped_series_rows' "$API" \
  || { echo "NO MEDIDO: mask_gapped_series_rows ya no existe: el check hay que reescribirlo"; exit 2; }

# Rutas que SI pasan por el enmascarado, derivadas del arbol.
cubiertas=$(awk '
  /@app\.(get|post)\("/ { if (match($0, /"[^"]+"/)) ruta = substr($0, RSTART+1, RLENGTH-2) }
  /mask_gapped_series_rows\(/ && !/async def/ { if (ruta != "") print ruta }
' "$API" | sort -u)

[ -n "$cubiertas" ] || { echo "NO MEDIDO: no se pudo resolver ninguna ruta con enmascarado"; exit 2; }

faltan=""
n=0
for ruta in $SERIE; do
  case " $(printf '%s' "$cubiertas" | tr '\n' ' ') " in
    *" $ruta "*) n=$((n+1)) ;;
    *) faltan="$faltan $ruta" ;;
  esac
done

[ -z "${faltan// /}" ] || {
  echo "$n de 9 endpoints de serie pasan por el enmascarado; sin cubrir:$faltan" | cut -c1-220
  exit 1
}
echo "los 9 endpoints de serie pasan por mask_gapped_series_rows"
