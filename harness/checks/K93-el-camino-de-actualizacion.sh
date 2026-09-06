#!/bin/bash
# K93  EL ESQUEMA TIENE QUE SOBREVIVIR AL CAMINO POR EL QUE FUE PRODUCCION, NO SOLO AL LIMPIO.
#
# EL HECHO QUE LO MOTIVA, medido el 2026-09-06 y comprobado por el operador. La CI aplica
# sql/schema.sql a una base desechable y VACIA (.github/workflows/ci.yml:65-72). En una base
# vacia la migracion de particionado NO RENOMBRA NADA, porque no hay tablas viejas que migrar.
# Y el renombrado es justo lo que hace que las dos mitades del fichero signifiquen cosas
# distintas: `sql/schema.sql:1993-1996` convierte `liquidations_realtime` en
# `..._unpartitioned_backup` y asciende la particionada a `liquidations_realtime`, asi que
# `CREATE TRIGGER ... ON liquidations_realtime` toca UNA TABLA a un lado y OTRA al otro.
#
# MEDIDO, con el esquema previo aplicado y el actual encima:
#     base VACIA         entero: 5 triggers   recortado: 5   -> IGUALES
#     ACTUALIZACION      entero: 6 triggers   recortado: 1   -> la tabla VIVA sin unicidad
# La CI habria dado VERDE a un recorte que deja la tabla viva de liquidaciones sin control de
# unicidad. No es que la CI este mal: hace UNA de las dos preguntas -¿aplica sin error?- y no
# la otra -¿conserva los objetos?-. Aplicar sin error y quedarse sin un trigger son cosas
# distintas, y este check es la segunda pregunta.
#
# EL ELEGIBLE SE DERIVA, NO SE TECLEA: el esquema "previo" es el del commit ANTERIOR al que
# ANADIO sql/migrations/20260809_temporal_partitioning.sql. Si manana esa migracion se
# reescribe, el check sigue el fichero y no una fecha escrita a mano.
#
# EL SUJETO ES EL ARBOL y la base es desechable: se crean dos bases nuevas, se aplican, se
# inventarian con pg_catalog y se tiran. No toca 140, no toca el espejo.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; [ -r "$B/env" ] && . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PSQL=${K93_PSQL:-psql}
PREFIJO=${K93_PREFIJO:-k93_$$}

command -v "$PSQL" >/dev/null 2>&1 || { echo "NO MEDIDO: no hay psql en esta maquina"; exit 2; }
[ -r "$REPO/sql/schema.sql" ] || { echo "NO MEDIDO: no se puede leer sql/schema.sql"; exit 2; }
"$PSQL" -X -q -d postgres -c "SELECT 1" >/dev/null 2>&1 \
  || { echo "NO MEDIDO: no hay PostgreSQL alcanzable como esta identidad"; exit 2; }

MIG="sql/migrations/20260809_temporal_partitioning.sql"
[ -r "$REPO/$MIG" ] || { echo "NO MEDIDO: falta $MIG, de donde sale el esquema previo"; exit 2; }

# --- 1 · EL ESQUEMA PREVIO, derivado del historial --------------------------------------
alta=$(cd "$REPO" && git log --diff-filter=A --format=%H -- "$MIG" 2>/dev/null | tail -1)
[ -n "$alta" ] || { echo "NO MEDIDO: git no dice que commit anadio $MIG"; exit 2; }
previo=$(cd "$REPO" && git rev-parse "$alta^" 2>/dev/null)
[ -n "$previo" ] || { echo "NO MEDIDO: el commit que anadio la migracion no tiene padre"; exit 2; }
tmp=$(mktemp -d) || exit 2
trap 'rm -rf "$tmp"; for s in limpio actual; do "$PSQL" -X -q -d postgres -c "DROP DATABASE IF EXISTS ${PREFIJO}_$s" >/dev/null 2>&1; done' EXIT
(cd "$REPO" && git show "$previo:sql/schema.sql") > "$tmp/previo.sql" 2>/dev/null
[ -s "$tmp/previo.sql" ] || { echo "NO MEDIDO: no se pudo sacar sql/schema.sql de $previo"; exit 2; }
# CERO PARTICIONES EN EL PREVIO NO ES UN DETALLE: si el "previo" ya trajera particiones, el
# camino de actualizacion no ejercitaria ningun renombrado y este check no mediria nada.
n_part=$(grep -c 'PARTITION BY' "$tmp/previo.sql" || true)
[ "${n_part:-0}" -eq 0 ] || { echo "NO MEDIDO: el esquema previo ya trae $n_part PARTITION BY: no habria migracion que ejercitar"; exit 2; }

# --- 2 · los dos caminos ----------------------------------------------------------------
INVENTARIO="
SELECT 'func:'||proname FROM pg_proc
  WHERE proname IN ('enforce_liquidation_event_unique','ensure_temporal_partitions',
                    'drop_expired_temporal_partitions','apply_temporal_retention')
UNION ALL
SELECT 'trig:'||t.tgname||'@'||c.relname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
  WHERE NOT t.tgisinternal
UNION ALL
SELECT 'tabla:'||relname FROM pg_class WHERE relkind IN ('r','p') AND relnamespace='public'::regnamespace
ORDER BY 1;
"
aplica() {  # <sufijo> <fichero previo o ->
  local db="${PREFIJO}_$1" prev="$2"
  "$PSQL" -X -q -d postgres -c "DROP DATABASE IF EXISTS $db" >/dev/null 2>&1
  "$PSQL" -X -q -d postgres -c "CREATE DATABASE $db" >/dev/null 2>&1 || return 3
  if [ "$prev" != "-" ]; then
    "$PSQL" -X -q -v ON_ERROR_STOP=1 -d "$db" -f "$prev" >/dev/null 2>"$tmp/$1.err" || return 4
  fi
  "$PSQL" -X -q -v ON_ERROR_STOP=1 -d "$db" -f "$REPO/sql/schema.sql" >/dev/null 2>>"$tmp/$1.err" || return 5
  "$PSQL" -X -A -t -d "$db" -c "$INVENTARIO" 2>/dev/null
}

limpio=$(aplica limpio -);   rc_l=$?
actual=$(aplica actual "$tmp/previo.sql"); rc_a=$?
for par in "limpio:$rc_l" "actual:$rc_a"; do
  n=${par%%:*}; r=${par##*:}
  case "$r" in
    0) ;;
    3) echo "NO MEDIDO: no se pudo crear la base desechable ${PREFIJO}_$n"; exit 2 ;;
    *) echo "NO MEDIDO: el camino $n no aplico (rc=$r): $(grep -m1 ERROR "$tmp/$n.err" 2>/dev/null | cut -c1-110)"; exit 2 ;;
  esac
done
n_l=$(printf '%s\n' "$limpio" | grep -c . || true)
n_a=$(printf '%s\n' "$actual" | grep -c . || true)
# CERO OBJETOS NO ES CERO DEFECTOS: si el inventario sale vacio, "iguales" seria
# indistinguible de "no he mirado nada".
[ "${n_l:-0}" -ge 10 ] && [ "${n_a:-0}" -ge 10 ] \
  || { echo "NO MEDIDO: inventario demasiado corto (limpio=$n_l actual=$n_a): la sonda no esta midiendo"; exit 2; }

# --- 3 · el veredicto -------------------------------------------------------------------
# El camino de ACTUALIZACION tiene objetos que el limpio no puede tener -la tabla de respaldo
# y su trigger-, asi que no se exige igualdad: se exige que NADA del camino limpio FALTE en el
# de actualizacion. Un objeto que existe tras aplicar en vacio y NO existe tras actualizar es
# un objeto que produccion perdio al migrar, que es el defecto entero.
faltan=$(comm -23 <(printf '%s\n' "$limpio" | sort -u) <(printf '%s\n' "$actual" | sort -u) | tr '\n' ' ')
extra=$(comm -13 <(printf '%s\n' "$limpio" | sort -u) <(printf '%s\n' "$actual" | sort -u) | grep -c . || true)

if [ -n "${faltan// /}" ]; then
  n=$(printf '%s' "$faltan" | wc -w)
  echo "$n objeto(s) existen tras aplicar el esquema en VACIO y NO tras el camino de ACTUALIZACION:$faltan"
  echo "  esquema previo: $previo (padre de $alta, el commit que anadio la migracion)"
  echo "  la CI solo prueba el camino limpio (ci.yml:65-72), asi que esto no lo ve"
  exit 1
fi
echo "los $n_l objeto(s) del camino limpio sobreviven al de ACTUALIZACION (que anade $extra propios del migrado)"
echo "  previo=$previo · bases desechables ${PREFIJO}_limpio y ${PREFIJO}_actual, ya borradas"
exit 0
