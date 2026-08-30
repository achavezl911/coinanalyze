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
# v3, 2026-08-25: SE DEJA DE JUZGAR LA CADENA Y SE VERIFICA LA PRUEBA.
#
# La v2 contaba como excusa el motivo que casara con una lista negra
# ("no exact historical source|no adapter|sin adaptador|unsupported"). Ese diseno
# tiene el defecto que su propio comentario admitia: una lista escrita a mano
# envejece sin avisar, y "not supported" o "adapter missing" no casaban. Ademas
# juzgaba la PROSA del archivado, que es lo mas facil de maquillar: basta escribir
# otro motivo para pasar.
#
# Ahora se exige EVIDENCIA RE-DERIVABLE. Cada fila archivada guarda en
# recovery_metadata como se comprobo, y el check rehace esa comprobacion desde la
# propia fila. Un archivado sin prueba, o con una prueba que no se sostiene, es un
# archivado en falso, se llame como se llame. Esto tapa la lista negra entera: el
# _mark_unrecoverable de app/data_gaps.py escribe recovery_metadata='{}', asi que
# se queda sin method y cae por "sin prueba" sin necesidad de mirar su texto.
#
# Metodos que este check sabe re-derivar, y que tiene que cumplir cada fila:
#   source_response_absence      la fuente CUBRIO el hueco y no lo mando.
#                                response_first_bucket < start_ts
#                                AND response_last_bucket >= end_ts
#                                AND window_returned_rows = 0
#                                AND response_returned_rows > 0
#   provider_horizon_exhausted   la fuente ya no sirve esa ventana, y no es que
#                                este caida: window_returned_rows = 0
#                                AND control_returned_rows > 0 (control reciente)
# Un method desconocido es "sin prueba" A PROPOSITO: el dia que alguien invente un
# tercer camino de archivado, este check lo para hasta que se le ensene a
# verificarlo. Es lo contrario de la lista negra, que dejaba pasar lo que no conocia.
#
# v4, 2026-08-30: LA RAMA DE AUSENCIA NO RE-DERIVABA SU AFIRMACION CENTRAL, y el fallo
# es de esta misma jornada. El straddle prueba la mitad IZQUIERDA de la frase -- que la
# fuente cubrio el tramo -- y jamas la derecha, que es la que la frase de verdad afirma:
# que DENTRO no vino nada. Inducido sobre filas sinteticas con el predicado literal:
#     real de hoy (44-48 de 49 alrededor, 0 dentro) ......... aceptaba
#     metadata que DECLARA 12 filas dentro del hueco ........ aceptaba   <- falsa
#     CONTROL NEG: la respuesta no rodea el hueco ........... rechazaba
# Censo que lo remata: 492 filas de ausencia con CERO conteos, frente a 409 de horizonte
# con 409. La rama de horizonte si re-derivaba lo suyo; esta no.
#
# EL LEGADO SE DISCRIMINA POR TIEMPO, NUNCA POR NULIDAD. Las 484 filas viejas del motor
# vivo no llevan los conteos porque cuando se escribieron no existian, y exigirselos
# pondria K04 ROJO sobre 492 filas SANAS -- un rojo que no es un fallo, y un rojo falso
# repetido ensena a ignorar el que si lo es. El corte es min(resolved_at) de las filas
# que YA traen la clave: todo lo archivado antes de que el escritor supiera escribirla
# queda dispensado, y todo lo posterior tiene que traerla. Es una subconsulta SIN
# correlacion, asi que Postgres la evalua una sola vez. Si nadie la trae todavia, el
# coalesce a 'infinity' dispensa a todas: el dia que se escriba la primera, el corte se
# fija solo y ya no se mueve, porque un min sobre filas nuevas nunca baja.
#
# LO QUE ESTE CHECK SIGUE SIN EXIGIR, Y SE DICE EN VEZ DE DESCUBRIRSE DESPUES: no pide
# DENSIDAD en la ventana ancha. Una respuesta de dos buckets con cuatro horas de hueco
# en medio rodea el tramo y pasa. Es evidencia fina de "cubrio", pero es exactamente el
# mismo raser que usa el detector vivo, y ponerle un umbral aqui seria inventarme una
# cifra que nadie ha medido. Las 8 filas del 2026-08-30 se auditaron contra el proveedor
# y dan 48, 45, 48, 44 y 44 de 49 con cero dentro, o sea que hoy la densidad sobra; el
# dia que alguien archive con dos buckets, esto es lo que hay que volver a mirar.
#
# Se cuentan tres cosas y cualquiera lo pone ROJO:
#   1. huecos 'unresolved' de mas de 24 h
#   2. huecos archivados SIN resolution_reason escrito
#   3. huecos archivados cuya prueba no se sostiene al re-derivarla
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
# LA PRUEBA, RE-DERIVADA DESDE LA PROPIA FILA. El CASE fija el orden de evaluacion
# por method; el coalesce(...,false) es obligatorio porque NOT NULL es NULL y la fila
# no se contaria, o sea que un metadata a medias se colaria como bueno. Si algun dia
# hay un metadata con basura donde va una fecha, el cast revienta, la consulta no
# devuelve numero y `leer` saca NOMED: "no pude medir" no es "no hay problema".
sin_prueba=$(leer sin_prueba "SELECT count(*) FROM data_gap
  WHERE status='unrecoverable'
    AND NOT coalesce(
      CASE recovery_metadata->>'method'
        WHEN 'source_response_absence' THEN
              recovery_metadata->>'response_first_bucket' IS NOT NULL
          AND recovery_metadata->>'response_last_bucket'  IS NOT NULL
          AND (recovery_metadata->>'response_first_bucket')::timestamptz <  start_ts
          AND (recovery_metadata->>'response_last_bucket')::timestamptz  >= end_ts
          AND (
                resolved_at < coalesce(
                  (SELECT min(resolved_at) FROM data_gap
                    WHERE recovery_metadata ? 'response_returned_rows'),
                  'infinity'::timestamptz)
             OR (    recovery_metadata->>'window_returned_rows'   IS NOT NULL
                 AND recovery_metadata->>'response_returned_rows' IS NOT NULL
                 AND (recovery_metadata->>'window_returned_rows')::int   = 0
                 AND (recovery_metadata->>'response_returned_rows')::int > 0)
              )
        WHEN 'provider_horizon_exhausted' THEN
              recovery_metadata->>'window_returned_rows'  IS NOT NULL
          AND recovery_metadata->>'control_returned_rows' IS NOT NULL
          AND (recovery_metadata->>'window_returned_rows')::int  =  0
          AND (recovery_metadata->>'control_returned_rows')::int >  0
        ELSE false
      END, false)") || exit 2

fallos=""
[ "$viejos" -eq 0 ] || fallos="$viejos sin resolver de mas de 24 h"
[ "$mudos" -eq 0 ] || fallos="${fallos:+$fallos; }$mudos archivados SIN motivo escrito"
[ "$sin_prueba" -eq 0 ] || fallos="${fallos:+$fallos; }$sin_prueba archivados cuya prueba no se sostiene al re-derivarla"

[ -z "$fallos" ] || { echo "$fallos"; exit 1; }
echo "0 sin resolver de mas de 24 h, 0 archivados mudos y 0 archivados sin prueba re-derivable"
