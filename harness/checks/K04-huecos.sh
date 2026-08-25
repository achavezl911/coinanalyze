#!/bin/bash
# K04  un hueco o se resuelve o queda escrito por que no.
#
# LA TRAMPA QUE ESTE CHECK TIENE QUE CERRAR, medida el 2026-08-25. La version
# anterior contaba SOLO status='unresolved'. El motor de recuperacion ya existe y
# funciona (app/data_gaps.py + scripts/recover_gaps.py), y exact_adapter_for
# (recover_gaps.py:87-100) devuelve None cuando no hay adaptador de identidad exacta,
# con lo que recover_gap marca el hueco 'unrecoverable'. Solo hay UN adaptador,
# CoinalyzeOhlcv1mAdapter. O sea que un simple
#     scripts/recover_gaps.py --limit 1000
# habria marcado los 265 huecos de long_short_ratio como irrecuperables, habria
# puesto este check en VERDE EN EL ACTO, no habria recuperado un solo dato y habria
# dejado la fuga diaria invisible. Nos lo habriamos hecho nosotros con una orden.
#
# La regla, y es la que sostiene la unidad: UNRECOVERABLE NO ES UN CAMINO A VERDE.
#
# Exigir solo "que tenga motivo escrito" NO BASTA, y esto esta medido, no supuesto:
# app/data_gaps.py:568 archiva con el motivo literal
#     "no exact historical source available"
# que pone resolved_at, cumple el CHECK del esquema y deja resolution_reason no
# nulo. Un check que solo mirase "hay motivo" habria pasado a VERDE con los 265
# huecos archivados y cero datos recuperados.
# Y ese motivo es una afirmacion sobre NOSOTROS -no tenemos adaptador-, no sobre el
# dato. No dice que el dato no exista: dice que no sabemos ir a buscarlo. Eso no
# resuelve nada, solo lo hace invisible.
#
# Se cuentan tres cosas y cualquiera lo pone ROJO:
#   1. huecos 'unresolved' de mas de 24 h
#   2. huecos archivados SIN resolution_reason escrito
#   3. huecos archivados con un motivo que habla de nuestra limitacion en vez de
#      del dato. Para archivar honradamente hace falta haber COMPROBADO contra el
#      proveedor que el dato no esta -"fuera del horizonte del proveedor", "la
#      fuente no publica ese bucket"-, y eso es una comprobacion, no un default.
set -uo pipefail
B=/srv/coinanalyze/harness

# Cada conteo se valida POR SEPARADO y aborta con 2 si no es un numero. Validarlos
# concatenados era un fallo de clasificacion: con "" + 0 + 0 la cadena "00" pasaba
# por numerica, el check salia ROJO con un mensaje sin cifra y solo daba NOMED si
# fallaban las TRES consultas. "No pude medir" no es "hay problema", y el diente de
# NOMED del gate de K15 depende justo de que esto salga con 2.
leer() {
  local etiqueta="$1" sql="$2" n
  n=$("$B/bin/prodsql" "$sql" 2>/dev/null | tr -d ' ' | grep -E '^[0-9]+$' | head -1)
  case "${n:-}" in
    ''|*[!0-9]*) echo "NO MEDIDO: la consulta '$etiqueta' no devolvio un numero" >&2; return 2 ;;
  esac
  printf '%s' "$n"
}

viejos=$(leer viejos "SELECT count(*) FROM data_gap
          WHERE status='unresolved' AND start_ts < now()-interval '24 hours'") || exit 2
mudos=$(leer mudos "SELECT count(*) FROM data_gap
         WHERE status IN ('unrecoverable','recovered')
           AND (resolution_reason IS NULL OR btrim(resolution_reason)='')") || exit 2
# LISTA NEGRA A PROPOSITO, y hay que saberlo: cubre el unico motivo que el motor
# escribe hoy (app/data_gaps.py:568) y sus variantes obvias, pero "not supported" o
# "adapter missing" NO casarian. La forma que no envejece es la inversa -lista BLANCA
# de motivos que afirman algo sobre EL DATO y exigen comprobacion contra el
# proveedor-, y es la misma leccion que costo K05. Se deja negra por ahora porque hoy
# hay UN solo emisor de motivos; el dia que haya dos, hay que darle la vuelta.
excusas=$(leer excusas "SELECT count(*) FROM data_gap
          WHERE status='unrecoverable'
            AND resolution_reason ~* '(no exact historical source|no adapter|sin adaptador|unsupported)'") || exit 2

fallos=""
[ "$viejos" -eq 0 ] || fallos="$viejos sin resolver de mas de 24 h"
[ "$mudos" -eq 0 ] || fallos="${fallos:+$fallos; }$mudos archivados SIN motivo escrito"
[ "$excusas" -eq 0 ] || fallos="${fallos:+$fallos; }$excusas archivados por falta de adaptador, que no es un motivo sobre el dato"

[ -z "$fallos" ] || { echo "$fallos"; exit 1; }
echo "0 sin resolver de mas de 24 h, 0 archivados mudos y 0 archivados por falta de adaptador"
