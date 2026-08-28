#!/bin/bash
# K67  EL RESUMEN DIARIO DE OI SE RECALCULA DESDE LOS 5min, O NO ES UN RESUMEN.
#
# POR QUE EXISTE ESTA TABLA, con la fecha delante. apply_retention borra open_interest y
# oi_bybit con un DELETE liso por antiguedad (daily_agg.py) y en 140
# HARD_DATA_RETENTION_DAYS=90 -leido de /etc/coinalyze/coinalyze.env, no el 14 de config.py-.
# La recoleccion de OI arranco el 2026-07-23 17:10 -min(ts) medido, no supuesto-, asi que el
# primer dia se pierde el 2026-10-21 y a partir de ahi la serie empieza un dia mas tarde
# cada dia. NINGUNA CONSULTA DARIA ERROR: el hueco aparece por el extremo VIEJO, que es el
# que nadie mira. Es la misma forma que este laboratorio lleva toda la semana cazando.
# ohlcv ya lo resolvio EXIMIENDO interval='daily' de su DELETE -"son 3 filas por dia y
# sostienen market_memory_2y"-, dos lineas mas arriba en la misma funcion. Por eso el CVD
# diario tiene dos anos y el OI cinco semanas.
#
# QUE COMPRUEBA, y es eslabon 6: no que la tabla exista, sino que su contenido SE SOSTIENE
# al rehacerlo desde la fuente que todavia vive.
#   1 · NINGUN DIA CERRADO SE QUEDA SIN RESUMIR. Por cada simbolo y fuente, todos los dias
#       UTC cerrados que siguen en los 5min tienen su fila. Un dia que se pierde aqui se
#       pierde para siempre en cuanto el purgado muerda.
#   2 · RECALCULO EXACTO. Se rehacen open/high/low/close y samples desde los 5min vivos y
#       tienen que cuadrar AL BIT. open y close son el PRIMER y el ULTIMO bucket del dia,
#       no el minimo ni el maximo: un min(oi_open) daria un numero que nunca existio, y ese
#       es justo el error que un recalculo perezoso no veria.
#   3 · EL DIA EN CURSO NO PUEDE ESTAR ESCRITO. Su oi_close todavia va a cambiar; una fila
#       que se reescribe sola no es un resumen.
#   NOMED, no VERDE, si no queda NI UN dia con las dos cosas -resumen y 5min-: sin
#       solapamiento no hay nada que recalcular, y un check que no pudo comparar no ha
#       comprobado nada. Es la regla de K60 aplicada a este check.
#
# Y DECLARA EL HORIZONTE aunque no lo juzgue: imprime el dia mas viejo del resumen contra el
# mas viejo de los 5min. Mientras el purgado no muerda son casi el mismo; el dia que muerda,
# esa distancia es LITERALMENTE lo que esta tabla salvo, y se lee de un vistazo.
#
# DE QUE ARBOL: datos de 140, en solo lectura. No escribe nada en ningun sitio.
set -uo pipefail
B=/srv/coinanalyze/harness
. "$B/env"

existe=$("$B/bin/prodsql" "SELECT to_regclass('public.open_interest_daily') IS NOT NULL" 2>/dev/null | tr -d ' ' | head -1)
case "$existe" in
  t) : ;;
  f) echo "NO EXISTE open_interest_daily: el DELETE liso de apply_retention se llevara el 2026-07-23 el 2026-10-21 y la serie empezara un dia mas tarde cada dia, sin que ninguna consulta falle"; exit 1 ;;
  *) echo "NO MEDIDO: no se pudo preguntar por la tabla open_interest_daily"; exit 2 ;;
esac

# Un solo viaje: el recalculo entero se hace en SQL contra 140 y vuelve resumido. Comparar
# en el cliente obligaria a traerse los 5min, que es justo lo que la regla de contexto
# prohibe, y ademas el redondeo del transporte podria inventar una diferencia que no existe.
SALIDA=$("$B/bin/prodsql" "
WITH vivos AS (
  SELECT (ts AT TIME ZONE 'UTC')::date AS day, symbol, 'coinalyze' AS source,
         oi_open, oi_high, oi_low, oi_close, ts
    FROM open_interest WHERE interval='5min'
  UNION ALL
  SELECT (ts AT TIME ZONE 'UTC')::date, symbol, 'bybit',
         oi_open, oi_high, oi_low, oi_close, ts
    FROM oi_bybit WHERE interval='5min'
),
rehecho AS (
  SELECT day, symbol, source,
         (array_agg(oi_open  ORDER BY ts ASC))[1]  AS oi_open,
         max(oi_high)                              AS oi_high,
         min(oi_low)                               AS oi_low,
         (array_agg(oi_close ORDER BY ts DESC))[1] AS oi_close,
         count(*)::int                             AS samples
    FROM vivos
   WHERE day < (now() AT TIME ZONE 'UTC')::date
   GROUP BY 1,2,3
),
cotejo AS (
  SELECT r.day, r.symbol, r.source, d.day AS resumido,
         (d.oi_open IS NOT DISTINCT FROM r.oi_open
          AND d.oi_high IS NOT DISTINCT FROM r.oi_high
          AND d.oi_low  IS NOT DISTINCT FROM r.oi_low
          AND d.oi_close IS NOT DISTINCT FROM r.oi_close
          AND d.samples IS NOT DISTINCT FROM r.samples) AS cuadra
    FROM rehecho r
    LEFT JOIN open_interest_daily d
      ON d.day=r.day AND d.symbol=r.symbol AND d.source=r.source
)
SELECT
  (SELECT count(*) FROM cotejo)                                            AS comparables,
  (SELECT count(*) FROM cotejo WHERE resumido IS NULL)                     AS sin_resumir,
  (SELECT count(*) FROM cotejo WHERE resumido IS NOT NULL AND NOT cuadra)  AS no_cuadran,
  (SELECT count(*) FROM open_interest_daily
     WHERE day >= (now() AT TIME ZONE 'UTC')::date)                        AS dia_en_curso,
  (SELECT count(*) FROM open_interest_daily)                               AS filas_resumen,
  coalesce((SELECT min(day)::text FROM open_interest_daily), 'ninguno')     AS resumen_desde,
  coalesce((SELECT min((ts AT TIME ZONE 'UTC')::date)::text FROM open_interest), 'ninguno') AS cinco_min_desde
" 2>/dev/null | head -1)

[ -n "$SALIDA" ] || { echo "NO MEDIDO: el recalculo contra 140 no devolvio nada"; exit 2; }

IFS='|' read -r comparables sin_resumir no_cuadran dia_en_curso filas desde_resumen desde_5min <<< "$(printf '%s' "$SALIDA" | tr -d ' ')"
case "${comparables:-}${sin_resumir:-}${no_cuadran:-}" in
  ''|*[!0-9]*) echo "NO MEDIDO: el recalculo devolvio algo que no son numeros: $(printf '%s' "$SALIDA" | head -c 120)"; exit 2 ;;
esac

if [ "$comparables" -eq 0 ]; then
  echo "NO MEDIDO: no queda ningun dia cerrado con 5min vivos contra el que recalcular; sin solapamiento no hay nada que comprobar"
  exit 2
fi
if [ "$sin_resumir" -gt 0 ]; then
  echo "$sin_resumir dias cerrados con 5min vivos NO tienen resumen (de $comparables comparables): lo que no se consolide antes de que el purgado muerda se pierde entero, y en silencio"
  exit 1
fi
if [ "$no_cuadran" -gt 0 ]; then
  echo "$no_cuadran resumenes NO cuadran al recalcularlos desde sus 5min (de $comparables comparables): el resumen diverge de la fuente y ninguna consulta lo notaria"
  exit 1
fi
if [ "$dia_en_curso" -gt 0 ]; then
  echo "$dia_en_curso filas del dia UTC EN CURSO ya estan escritas: su oi_close todavia va a cambiar, y una fila que se reescribe sola no es un resumen"
  exit 1
fi

echo "los $comparables dias-simbolo-fuente cerrados con 5min vivos estan resumidos y los $comparables RECALCULADOS cuadran al bit -open y close por primer y ultimo bucket, no por minimo-, 0 filas del dia en curso. El resumen tiene $filas filas desde $desde_resumen y los 5min desde $desde_5min: cuando el purgado de 90 dias muerda el 2026-10-21, esa distancia es lo que esta tabla salva"
