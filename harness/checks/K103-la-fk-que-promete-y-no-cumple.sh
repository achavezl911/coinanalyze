#!/bin/bash
# K103  UNA FK VALIDADA CON HIJAS HUERFANAS. La FK dice «para cada hija hay un padre» y
# Postgres dice que esa promesa esta COMPROBADA (convalidated). Las dos cosas pueden ser
# falsas a la vez: el 2026-09-16 produccion perdio 38 filas padre sin que nadie las borrara
# -sin DELETE posible, sin error en el log, con data_checksums=off- y dejo 128 hijas
# huerfanas bajo 4 FK que siguen marcadas como validadas. Nadie lo vio en DOCE DIAS.
#
# POR QUE ESTE CHECK Y NO EL CATALOGO. `convalidated` no se vuelve a comprobar nunca: es la
# fecha en que se valido, no el estado de hoy. La unica forma de saber si la promesa se
# cumple es CONTAR. Es A71: una perdida sin error solo la ve una relacion o un respaldo
# anterior, y esta es la relacion.
#
# EL ALCANCE, DECLARADO, con su coste medido (140, 2026-10-02T01:5xZ, reloj del servidor):
#   · Se juzgan las FK de PRIMER NIVEL (`conparentid=0`). Una FK sobre una tabla particionada
#     se juzga UNA vez en la tabla padre y el NOT EXISTS recorre TODAS sus particiones; las
#     copias por particion (`conparentid<>0`) no se cuentan dos veces, y su numero se dice.
#   · Se juzgan tambien las NO VALIDADAS, pero NO CONDENAN y salen aparte: una FK que nacio
#     NOT VALID no promete nada sobre las filas viejas, y cobrarle una promesa que no hizo
#     seria un rojo falso. Si alguna aparece, sale con su nombre y su cuenta.
#   · Las compuestas se juzgan con TODAS sus columnas (semantica MATCH SIMPLE: la fila solo
#     esta sujeta a la FK si ninguna de sus columnas es NULL). Hoy hay 0, y el generador las
#     cubre para que la primera que entre no pase de largo en silencio.
#   · Coste medido: las 34 de primer nivel en 4.101 s de servidor; la mas cara,
#     signal_outcome_final_visibility_outcome_id_fkey, 1.054 s. Ninguna llega a 1.1 s, asi que
#     NO hay ninguna excluida por coste. El dia que una pase del timeout, sale NOMBRADA como
#     NO JUZGADA y el veredicto es NO MEDIDO, no VERDE.
#
# LAS CUENTAS NO ESTAN EN EL CODIGO A PROPOSITO. Este check tiene que ponerse VERDE el dia
# que Alejandro meta las 38 filas SIN QUE NADIE LO EDITE, y tiene que ver la huerfana numero
# 129 si aparece otra. Por eso el universo sale del catalogo del sujeto y las cuentas de la
# consulta: aqui no hay ni un 80 ni un 24 escritos.
#
#   K103_SUJETO=produccion   (por omision)  juzga 140 por bin/prodsql
#   K103_SUJETO=local K103_BASE=<base>      juzga una base de 143 (lo que usa el control)
#   K103_TIMEOUT_MS=<n>                     el tope por sentencia (60000 por omision)
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
SUJETO=${K103_SUJETO:-produccion}
BASE=${K103_BASE:-}
TOPE=${K103_TIMEOUT_MS:-60000}

case "$SUJETO" in
  produccion) QUIEN="produccion (140, por bin/prodsql)" ;;
  local) [ -n "$BASE" ] || { echo "NO MEDIDO: K103_SUJETO=local exige K103_BASE"; exit 2; }
         QUIEN="la base local $BASE (143)" ;;
  *) echo "NO MEDIDO: K103_SUJETO solo acepta produccion o local (vino '$SUJETO')"; exit 2 ;;
esac

consulta() {  # $1 = SQL. Devuelve filas por stdout; rc != 0 = el canal o el SQL fallaron.
  if [ "$SUJETO" = produccion ]; then
    TODO=1 "$B/bin/prodsql" "SET statement_timeout=$TOPE; $1"
  else
    printf 'SET statement_timeout=%s;\n%s\n' "$TOPE" "$1" \
      | psql -X -A -t -F'|' -v ON_ERROR_STOP=1 -q -d "$BASE" -f -
  fi
}

# --- 1 · EL UNIVERSO, DEL CATALOGO DEL SUJETO -------------------------------------------
CENSO=$(consulta "SELECT 'CENSO|'||count(*)
                         ||'|'||count(*) FILTER (WHERE conparentid=0)
                         ||'|'||count(*) FILTER (WHERE conparentid=0 AND NOT convalidated)
                         ||'|'||count(*) FILTER (WHERE conparentid=0 AND array_length(conkey,1) > 1)
                    FROM pg_constraint WHERE contype='f'" 2>&1 | grep '^CENSO|' | head -1)
[ -n "$CENSO" ] || { echo "NO MEDIDO: el canal no devolvio el censo de FK de $QUIEN"; exit 2; }
IFS='|' read -r _ N_TOT N_RAIZ N_NOVAL N_COMP <<EOF
$CENSO
EOF
[ "${N_RAIZ:-0}" -gt 0 ] || {
  echo "NO MEDIDO: $QUIEN no tiene ninguna FK de primer nivel que juzgar ($N_TOT en el catalogo)."
  exit 2; }

# --- 2 · LAS SENTENCIAS, GENERADAS POR EL CATALOGO --------------------------------------
# El predicado de NULL y el del enganche los escribe el propio SQL con format()/%I, asi que
# un nombre raro o una FK compuesta no rompen la generacion ni se saltan.
GEN=$(consulta "SELECT 'FK|'||c.conname
       ||'|'||quote_ident(nh.nspname)||'.'||quote_ident(h.relname)
       ||'|'||quote_ident(np.nspname)||'.'||quote_ident(p.relname)
       ||'|'||(CASE WHEN c.convalidated THEN 'VAL' ELSE 'NOVAL' END)
       ||'|'||(SELECT string_agg(format('c.%I IS NOT NULL', ha.attname), ' AND ' ORDER BY z.ord)
                 FROM unnest(c.conkey) WITH ORDINALITY AS z(att,ord)
                 JOIN pg_attribute ha ON ha.attrelid=c.conrelid AND ha.attnum=z.att)
       ||'|'||(SELECT string_agg(format('p.%I = c.%I', pa.attname, ha.attname), ' AND ' ORDER BY z.ord)
                 FROM unnest(c.conkey) WITH ORDINALITY AS z(att,ord)
                 JOIN unnest(c.confkey) WITH ORDINALITY AS w(att,ord) ON w.ord=z.ord
                 JOIN pg_attribute ha ON ha.attrelid=c.conrelid AND ha.attnum=z.att
                 JOIN pg_attribute pa ON pa.attrelid=c.confrelid AND pa.attnum=w.att)
  FROM pg_constraint c
  JOIN pg_class h ON h.oid=c.conrelid JOIN pg_namespace nh ON nh.oid=h.relnamespace
  JOIN pg_class p ON p.oid=c.confrelid JOIN pg_namespace np ON np.oid=p.relnamespace
 WHERE c.contype='f' AND c.conparentid=0
 ORDER BY c.conname, h.relname" 2>&1 | grep '^FK|')
n_gen=$(printf '%s\n' "$GEN" | grep -c '^FK|')
[ "$n_gen" = "$N_RAIZ" ] || {
  echo "NO MEDIDO: el generador saco $n_gen sentencias para $N_RAIZ FK de primer nivel de $QUIEN."
  exit 2; }

sentencia() {  # $1 = linea FK|...  ->  la consulta que cuenta sus huerfanas
  printf '%s' "$1" | awk -F'|' '{printf "SELECT %c%s|%s|%s|%s|%c||count(*) FROM %s c WHERE %s AND NOT EXISTS (SELECT 1 FROM %s p WHERE %s);\n", 39, "HU", $2, $3, $5, 39, $3, $6, $4, $7}'
}

LOTE=""
while IFS= read -r l; do
  [ -n "$l" ] || continue
  LOTE="$LOTE
SELECT 'TS|'||clock_timestamp();
$(sentencia "$l")"
done <<EOF
$GEN
EOF
LOTE="$LOTE
SELECT 'TS|'||clock_timestamp();"

# --- 3 · CONTAR. El lote va de una vez; si algo lo aborta, se repesca una a una ----------
SAL=$(consulta "$LOTE" 2>/dev/null | grep -E '^(HU|TS)\|')
n_hu=$(printf '%s\n' "$SAL" | grep -c '^HU|')
NO_JUZGADAS=""
if [ "$n_hu" != "$N_RAIZ" ]; then
  # EL LOTE SE ABORTO. Con ON_ERROR_STOP=1 una sentencia que revienta se lleva por delante a
  # las de atras, asi que lo que falta NO es «sin huerfanas»: es SIN MEDIR. Se repesca una a
  # una y lo que siga fallando sale con su nombre.
  while IFS= read -r l; do
    [ -n "$l" ] || continue
    fk=$(printf '%s' "$l" | cut -d'|' -f2)
    printf '%s\n' "$SAL" | grep -q "^HU|$fk|" && continue
    una=$(consulta "$(sentencia "$l")" 2>/dev/null | grep "^HU|$fk|" | head -1)
    if [ -n "$una" ]; then SAL="$SAL
$una"; else NO_JUZGADAS="$NO_JUZGADAS $fk"; fi
  done <<EOF
$GEN
EOF
  n_hu=$(printf '%s\n' "$SAL" | grep -c '^HU|')
fi

# --- 4 · EL VEREDICTO --------------------------------------------------------------------
# LA MARCA ES 'VAL'/'NOVAL' Y NO EL BOOLEANO, Y ESO ES UNA CORRECCION MEDIDA. La primera
# version imprimia `c.convalidated::text` y comparaba contra "t": psql escribe `true`, asi que
# NINGUNA FK casaba como validada, las 4 de produccion cayeron en el cubo «no condena» y el
# check dio VERDE citando 80/24/17/7 en la pantalla. Un veredicto no puede depender de como
# escribe un booleano el cliente: la marca la pone el SQL y es una palabra que no se parece a
# la otra.
CONDENA=$(printf '%s\n' "$SAL" | awk -F'|' '/^HU\|/ && $4=="VAL" && $5+0 > 0 {printf "  %-56s %-46s %s\n", $2, $3, $5}')
TOTAL=$(printf '%s\n'  "$SAL" | awk -F'|' '/^HU\|/ && $4=="VAL" {s+=$5} END {print s+0}')
N_FK_MAL=$(printf '%s\n' "$SAL" | awk -F'|' '/^HU\|/ && $4=="VAL" && $5+0 > 0' | grep -c .)
DECLARA=$(printf '%s\n' "$SAL" | awk -F'|' '/^HU\|/ && $4=="NOVAL" && $5+0 > 0 {printf "  %-56s %-46s %s (NO VALIDADA: no condena)\n", $2, $3, $5}')
# Y UNA MARCA QUE NO ES NI UNA NI OTRA NO SE PUEDE CALLAR: seria la misma trampa por otro lado.
RAROS=$(printf '%s\n' "$SAL" | awk -F'|' '/^HU\|/ && $4!="VAL" && $4!="NOVAL" {print $2"("$4")"}' | tr '\n' ' ')
SEG=$(printf '%s\n' "$SAL" | awk -F'|' '/^TS\|/ {print $2}' | head -1)
FIN=$(printf '%s\n' "$SAL" | awk -F'|' '/^TS\|/ {print $2}' | tail -1)

OTRAS=$((N_TOT - N_RAIZ))
echo "sujeto: $QUIEN"
echo "FK en el catalogo: $N_TOT · de primer nivel: $N_RAIZ (las otras $OTRAS son copias por particion, cubiertas por la suya) · NO validadas: $N_NOVAL · compuestas: $N_COMP"
echo "juzgadas: $n_hu de $N_RAIZ · tope por sentencia ${TOPE} ms"
[ -n "$SEG" ] && [ -n "$FIN" ] && echo "reloj del servidor: de $SEG a $FIN"
[ -n "${DECLARA// /}" ] && { echo "DECLARADAS y NO condenan (la FK no prometio nada):"; printf '%s\n' "$DECLARA"; }

if [ -n "${RAROS// /}" ]; then
  echo "NO MEDIDO: la marca de validada salio con un valor que no es VAL ni NOVAL, asi que no se"
  echo "puede decir cual promesa se rompio: $RAROS"
  exit 2
fi
# EL ORDEN DE LOS DOS ESTADOS MALOS NO ES INDIFERENTE. Una huerfana CONTADA es un hecho, y un
# hecho no lo borra una laguna de al lado: si hay condena, el veredicto es ROJO y la FK que no
# se pudo contar sale NOMBRADA dentro del mismo rojo. NO MEDIDO queda para cuando no hay
# ninguna condena y ADEMAS falta por contar: ahi es verdad que no se sabe.
FALTAN=""
[ -n "${NO_JUZGADAS// /}" ] && FALTAN="  y $(printf '%s' "$NO_JUZGADAS" | wc -w) FK NO SE PUDIERON CONTAR, asi que de esas no se sabe:$NO_JUZGADAS"
if [ -n "${CONDENA// /}" ]; then
  echo "HUERFANAS: $TOTAL filas hijas sin padre bajo $N_FK_MAL FK VALIDADA(S) de $QUIEN:"
  printf '%s\n' "$CONDENA"
  [ -n "$FALTAN" ] && printf '%s\n' "$FALTAN"
  echo "una FK validada con huerfanas no es una contradiccion que se discuta: es una perdida de"
  echo "filas padre que ya ocurrio (A71). Se repara metiendo las filas que faltan, no tocando la FK."
  exit 1
fi
if [ -n "${NO_JUZGADAS// /}" ]; then
  echo "NO MEDIDO: $(printf '%s' "$NO_JUZGADAS" | wc -w) FK no se pudieron contar y por tanto no se" \
       "sabe si tienen huerfanas:$NO_JUZGADAS"
  echo "cero condenas sobre lo que SI se conto no es un VERDE mientras quede algo sin contar."
  exit 2
fi
echo "las $n_hu FK de primer nivel de $QUIEN cumplen: 0 filas hijas sin padre"
exit 0
