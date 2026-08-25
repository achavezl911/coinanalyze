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
# SUJETO CORREGIDO el 2026-08-25: de nueve a siete. /api/funding-context y
# /api/oi-context NO devuelven serie. Medido en el arbol: funding_context devuelve
# current_pct, annualized_pct e history_avg_pct{8h,24h,7d} (scalp_logic.py:3166) y
# oi_context devuelve oi_total_usd y windows{5m,15m,1h,4h,24h} (scalp_logic.py:2908).
# Ningun array de filas con bucket, o sea que mask_gapped_series_rows no tiene sobre
# que operar: meterles la llamada seria una llamada hueca puesta para que pase el grep
# de este mismo check.
#
# ESTO NO ES AFLOJAR EL CHECK, y se demuestra con la cuenta en vez de con la palabra:
# quitar dos del denominador NO sube el numerador. Medido justo antes del cambio:
#     sujeto de 9 -> "5 de 9", rc=1
#     sujeto de 7 -> "5 de 7", rc=1
# Un criterio aflojado sube la cuenta de VERDE. Este no la sube: sigue ROJO con dos
# huecos reales (/api/whale/delta y /api/daily), y ninguno de ellos es de criterio.
#
# Y LA OBLIGACION NO DESAPARECE: los dos escalares YA ESTAN en el sujeto de
# K03-hueco-declarado.sh, que es donde tienen que estar, porque su pregunta no es "por
# donde pasan" sino "que declaran". K03 crece a la vez para exigirles lo que un
# agregado tiene que decir: la COMPLETITUD DE LA VENTANA que agrego. Un promedio de 7d
# calculado sobre una ventana con huecos es PEOR que una serie con huecos, porque la
# serie ensena sus agujeros y el promedio los esconde detras de un numero con
# decimales. Mover sin eso seria aparcarlos donde no se pueden probar.
SERIE="/api/ohlcv /api/oi /api/liquidations /api/whale/delta /api/daily /api/cvd /api/cvd/spot"

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
  echo "$n de 7 endpoints de serie pasan por el enmascarado; sin cubrir:$faltan" | cut -c1-220
  exit 1
}
echo "los 7 endpoints de serie pasan por mask_gapped_series_rows"
