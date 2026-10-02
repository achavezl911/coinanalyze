#!/bin/bash
# K104  UN DIA YA CERRADO QUE ENCOGE. El 2026-09-16 produccion perdio 38 filas de un dia
# del 08-29 sin que nadie las borrara: sin DELETE posible (las guardas estan activas), sin
# error en el log de Postgres ni en el del nodo, y con data_checksums=off. NADIE LO VIO EN
# DOCE DIAS. Lo unico que lo destapo fue una relacion -4 FK con 128 hijas huerfanas- y lo
# unico que lo FECHO fue comparar dos respaldos consecutivos (A71).
#
# ESTE CHECK ES ESE SEGUNDO INSTRUMENTO, HECHO PERMANENTE: cuenta filas por (tabla, dia) y
# las compara con el censo anterior. Un dia cerrado solo puede CRECER (una fila que llega
# tarde) o quedarse igual. Si encoge, se condena con su tabla y su dia.
#
# LO QUE SE GUARDA ES UNA MARCA DE AGUA, NO UNA FOTO. Si el censo se re-tomara tal cual, la
# perdida se veria UNA vez y la corrida siguiente volveria a estar «de acuerdo» consigo misma
# -que es exactamente el silencio de doce dias que esto viene a cerrar-. Asi que para cada
# (tabla, dia) se guarda el MAXIMO visto: la condena se vuelve a derivar del dato en cada
# corrida y no se va hasta que las filas vuelven. Cuando vuelven, el maximo se actualiza solo
# y el check se pone VERDE sin que nadie lo edite.
#
# EL BORDE NO SALE DEL DATO (A68). El dia cerrado sale del RELOJ (todo lo anterior a hoy UTC)
# y la ventana de una tabla podada sale de su VARIABLE de retencion, leida del coinalyze.env
# de 140 en cada corrida. Un suelo sacado de min(ts) de la propia tabla podada no puede ver la
# perdida de las primeras filas -el hueco se come a si mismo- y ademas se mueve con la hora.
# Solo se juzga el dia que cabe ENTERO en la ventana: un dia a medio podar encoge por oficio.
#
# EL UNIVERSO TAMPOCO SALE DE LA TABLA PODADA: sale del catalogo del sujeto cruzado con
# K104-tablas.tsv, que declara columna, retencion y fuente. Una tabla del catalogo que no
# este declarada SALE NOMBRADA en cada corrida, para que nadie la juzgue por omision.
#
#   K104_SUJETO=produccion                 (por omision) 140 por bin/prodsql
#   K104_SUJETO=local K104_BASE=<base>     una base de 143 (el control, y las copias)
#   K104_RETENCIONES=<fichero>             VAR=valor; OBLIGATORIO con sujeto local
#   K104_CENSO=<fichero>                   el censo (por omision harness/estado/k104-censo-<sujeto>.tsv)
#   K104_TABLAS=<fichero>                  las declaraciones
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
SUJETO=${K104_SUJETO:-produccion}
BASE=${K104_BASE:-}
DECL=${K104_TABLAS:-$B/checks/K104-tablas.tsv}
CENSO=${K104_CENSO:-$B/estado/k104-censo-$SUJETO.tsv}
RETF=${K104_RETENCIONES:-}
TOPE=${K104_TIMEOUT_MS:-60000}
HOY=$(date -u +%F)
AHORA=$(date -u +%FT%TZ)

[ -r "$DECL" ] || { echo "NO MEDIDO: no puedo leer las declaraciones $DECL"; exit 2; }
command -v python3 >/dev/null || { echo "NO MEDIDO: no hay python3"; exit 2; }
case "$SUJETO" in
  produccion) QUIEN="produccion (140, por bin/prodsql)" ;;
  local) [ -n "$BASE" ] || { echo "NO MEDIDO: K104_SUJETO=local exige K104_BASE"; exit 2; }
         [ -n "$RETF" ] || { echo "NO MEDIDO: con sujeto local hay que declarar las retenciones" \
                                  "del sujeto en K104_RETENCIONES: leer las de 140 para otra base" \
                                  "seria poner un borde que no es el suyo"; exit 2; }
         QUIEN="la base local $BASE (143)" ;;
  *) echo "NO MEDIDO: K104_SUJETO solo acepta produccion o local (vino '$SUJETO')"; exit 2 ;;
esac

consulta() {
  if [ "$SUJETO" = produccion ]; then
    TODO=1 "$B/bin/prodsql" "SET statement_timeout=$TOPE; $1"
  else
    printf "SET statement_timeout=%s;\nSET timezone='UTC';\n%s\n" "$TOPE" "$1" \
      | psql -X -A -t -F'|' -v ON_ERROR_STOP=1 -q -d "$BASE" -f -
  fi
}

# --- 1 · EL CATALOGO DEL SUJETO, Y LO QUE NO ESTA DECLARADO ------------------------------
# VA PRIMERO, y no es un detalle de orden: las variables de retencion que hacen falta son las
# de las tablas que ESTE sujeto tiene. Con el orden al reves, el check exigia las siete
# variables de produccion para juzgar una copia de tres tablas y salia NO MEDIDO siempre.
CAT=$(consulta "SELECT 'T|'||c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p') AND c.relispartition=false
        ORDER BY 1" 2>/dev/null | sed -n 's/^T|//p')
[ -n "$CAT" ] || { echo "NO MEDIDO: el canal no devolvio el catalogo de tablas de $QUIEN"; exit 2; }
SIN_DECLARAR=""
for t in $CAT; do
  awk -F'\t' -v t="$t" '$1==t {f=1} END {exit !f}' "$DECL" || SIN_DECLARAR="$SIN_DECLARAR $t"
done
EN_SUJETO=$(printf '%s\n' "$CAT" | tr ' ' '\n' | sort -u)

# --- 2 · LAS RETENCIONES, DEL SUJETO Y NO DE UNA COPIA ----------------------------------
VARS=$(awk -F'\t' 'NR==FNR {hay[$1]=1; next} $3 ~ /^(horas|dias):[A-Z]/ && hay[$1] {split($3,p,":"); print p[2]}' \
       <(printf '%s\n' "$EN_SUJETO") "$DECL" | sort -u)
VALORES=""
if [ -n "$VARS" ]; then
  PAT=$(printf '%s' "$VARS" | tr '\n' '|' | sed 's/|$//')
  if [ -n "$RETF" ]; then
    [ -r "$RETF" ] || { echo "NO MEDIDO: no puedo leer $RETF"; exit 2; }
    VALORES=$(grep -hE "^($PAT)=" "$RETF" 2>/dev/null)
  else
    # Solo las variables de retencion: el coinalyze.env tiene secretos y de aqui no sale
    # ninguno. Si una no esta puesta, se cae al valor por omision del release -y los dos se
    # leen del MISMO arbol que corre-.
    VALORES=$("$B/bin/prod" "grep -hE '^($PAT)=' /etc/coinalyze/coinalyze.env" 2>/dev/null)
    DEFS=$("$B/bin/prod" "grep -hE '^ *($PAT) *:' /opt/coinalyze/current/app/config.py" 2>/dev/null)
    for v in $VARS; do
      printf '%s\n' "$VALORES" | grep -q "^$v=" && continue
      d=$(printf '%s\n' "$DEFS" | sed -n "s/^ *$v *:.*default=\([0-9]*\).*/\1/p" | head -1)
      [ -n "$d" ] && VALORES="$VALORES
$v=$d"
    done
  fi
fi
FALTAN_VAR=""
for v in $VARS; do
  printf '%s\n' "$VALORES" | grep -q "^$v=" || FALTAN_VAR="$FALTAN_VAR $v"
done
[ -z "${FALTAN_VAR// /}" ] || {
  echo "NO MEDIDO: no se pudo leer la retencion de$FALTAN_VAR, asi que no se sabe donde esta el"
  echo "borde de las tablas que dependen de ella y juzgarlas con un numero inventado seria peor."
  exit 2; }

# --- 3 · EL PISO DE CADA TABLA: RELOJ + VARIABLE, NUNCA min(ts) --------------------------
# Un dia D cabe ENTERO en una ventana de H horas si su medianoche es posterior al corte, o sea
# D >= date(ahora - H horas) + 1 dia. Con H=12 no hay NINGUN dia cerrado que quepa, y eso se
# dice en vez de juzgarlo a medias.
PLAN=""; SIN_DIA=""; NO_JUZGADAS=""
while IFS=$'\t' read -r t col ret _; do
  case "$t" in ''|'#'*) continue ;; esac
  printf '%s\n' "$CAT" | tr ' ' '\n' | grep -qx "$t" || continue
  case "$ret" in
    no_juzgada:*) NO_JUZGADAS="$NO_JUZGADAS $t(${ret#no_juzgada:})"; continue ;;
    sin_poda) piso=1970-01-01 ;;
    horas:*|dias:*)
      n=${ret#*:}
      case "$n" in [0-9]*) val=$n ;; *) val=$(printf '%s\n' "$VALORES" | sed -n "s/^$n=//p" | head -1) ;; esac
      case "$ret" in dias:*) horas=$((val*24)) ;; *) horas=$val ;; esac
      piso=$(date -u -d "$(date -u -d "-$horas hours" +%F) +1 day" +%F) ;;
    *) NO_JUZGADAS="$NO_JUZGADAS $t(retencion ilegible '$ret')"; continue ;;
  esac
  if ! printf '%s\n' "$piso" | grep -q '^[0-9]'; then
    NO_JUZGADAS="$NO_JUZGADAS $t(no se pudo calcular el piso)"; continue
  fi
  # Sin dia cerrado dentro de la ventana no hay nada que juzgar, y decirlo no es condenar.
  if [ "$piso" \> "$(date -u -d "$HOY -1 day" +%F)" ]; then
    SIN_DIA="$SIN_DIA $t(ventana ${ret#*:}, ni un dia cerrado entero)"; continue
  fi
  PLAN="$PLAN
$t|$col|$piso"
done < "$DECL"
N_PLAN=$(printf '%s\n' "$PLAN" | grep -c '|')
[ "$N_PLAN" -gt 0 ] || { echo "NO MEDIDO: ninguna tabla declarada tiene un dia cerrado que juzgar en $QUIEN"; exit 2; }

# --- 4 · EL CENSO ------------------------------------------------------------------------
# GROUP BY por la EXPRESION del dia, no por «1»: la columna 1 de salida lleva dentro el
# count(*) y Postgres rechaza agrupar por un agregado («aggregate functions are not allowed in
# GROUP BY»). Con el error tapado por el 2>/dev/null, el censo salia de 0 parejas y el check
# -por suerte- decia NO MEDIDO en vez de VERDE.
sent() { printf "SELECT 'C|%s|'||to_char(%s::date,'YYYY-MM-DD')||'|'||count(*) FROM %s WHERE %s >= '%s'::date AND %s < '%s'::date GROUP BY %s::date;\n" \
                "$1" "$2" "$1" "$2" "$3" "$2" "$HOY" "$2"; }
LOTE=""
while IFS='|' read -r t col piso; do
  [ -n "$t" ] || continue
  LOTE="$LOTE
$(sent "$t" "$col" "$piso")"
done <<EOF
$(printf '%s\n' "$PLAN" | grep '|')
EOF
t0=$(date -u +%s)
ACTUAL=$(consulta "$LOTE" 2>/dev/null | grep '^C|')
SIN_CONTAR=""
while IFS='|' read -r t col piso; do
  [ -n "$t" ] || continue
  printf '%s\n' "$ACTUAL" | grep -q "^C|$t|" && continue
  # Puede ser que la tabla este VACIA en la ventana (0 grupos) o que su sentencia reventara y
  # se llevara por delante al resto del lote. Las dos cosas NO son lo mismo, asi que se repesca.
  una=$(consulta "$(sent "$t" "$col" "$piso")SELECT 'FIN|$t';" 2>/dev/null)
  if printf '%s\n' "$una" | grep -q "^FIN|$t"; then
    ACTUAL="$ACTUAL
$(printf '%s\n' "$una" | grep "^C|$t|")"
  else
    SIN_CONTAR="$SIN_CONTAR $t"
  fi
done <<EOF
$(printf '%s\n' "$PLAN" | grep '|')
EOF
t1=$(date -u +%s)

# --- 5 · COMPARAR CON LA MARCA DE AGUA ---------------------------------------------------
PREVIO=""; [ -r "$CENSO" ] && PREVIO=$(cat "$CENSO")
RES=$(printf '%s\n' "$PLAN" "===" "$PREVIO" "===" "$ACTUAL" "===" "$SIN_CONTAR" | python3 -c '
import sys
plan, previo, actual, muda = {}, {}, {}, set()
modo = 0
for l in sys.stdin.read().splitlines():
    l = l.strip()
    if l == "===":
        modo += 1; continue
    if not l: continue
    if modo == 0:
        t, col, piso = l.split("|"); plan[t] = piso
    elif modo == 1:
        if l.startswith("#"): continue
        p = l.split("\t")
        if len(p) < 3: continue
        previo[(p[0], p[1])] = int(p[2])
    elif modo == 2:
        p = l.split("|")
        if len(p) != 4 or p[0] != "C": continue
        actual[(p[1], p[2])] = int(p[3])
    else:
        # Las tablas que NO SE PUDIERON CONTAR. Su marca de agua se conserva -no se rebaja por
        # no haber podido mirar- pero NO se comparan: sin cuenta de hoy, `actual` no las trae y
        # la resta las daria a CERO, o sea una perdida inventada. Y la salida ademas las
        # atribuia a «las que SI se contaron», que es decir una falsedad en el unico sitio donde
        # alguien la leeria. Lo que falta por contar se dice como lo que es: NO MEDIDO.
        muda.update(l.split())
perdidas, nuevo = [], {}
# La marca de agua solo vive mientras el dia cabe en la ventana de HOY: un dia que salio de
# su retencion se olvida, porque ahi encoger es el oficio de la poda y no una perdida.
for (t, d), n in previo.items():
    if t in plan and d >= plan[t]:
        nuevo[(t, d)] = n
for (t, d), n in actual.items():
    if nuevo.get((t, d), -1) < n:
        nuevo[(t, d)] = n
for (t, d), antes in sorted(nuevo.items()):
    if t in muda: continue
    hoy = actual.get((t, d), 0)
    if hoy < antes:
        perdidas.append((t, d, antes, hoy))
for t, d, a, h in perdidas:
    print("PERDIDA|%s|%s|%d|%d" % (t, d, a, h))
print("RESUMEN|%d|%d|%d" % (len(previo), len(nuevo), len(perdidas)))
for (t, d), n in sorted(nuevo.items()):
    print("CENSO|%s|%s|%d" % (t, d, n))
')
PERDIDAS=$(printf '%s\n' "$RES" | sed -n 's/^PERDIDA|//p')
RESUMEN=$(printf '%s\n' "$RES" | sed -n 's/^RESUMEN|//p')
N_PREV=$(printf '%s' "$RESUMEN" | cut -d'|' -f1)
N_PAR=$(printf '%s' "$RESUMEN" | cut -d'|' -f2)

# --- 6 · GUARDAR Y DECIR -----------------------------------------------------------------
mkdir -p "$(dirname "$CENSO")"
{ printf '# K104 · marca de agua por (tabla, dia) · sujeto %s · reescrito %s\n' "$SUJETO" "$AHORA"
  printf '%s\n' "$RES" | sed -n 's/^CENSO|//p' | tr '|' '\t'; } > "$CENSO.tmp" && mv "$CENSO.tmp" "$CENSO"

# LA PRIMERA LINEA ES EL VEREDICTO. `bin/verify` se queda con la PRIMERA linea para el marcador,
# que es lo que se cita durante semanas: con el contexto delante, este check aparecia como
# «sujeto: produccion ... hoy (UTC) ...» y lo que hubiera encontrado NO SALIA. Es el mismo
# sintoma que esta campana arregla en K01b. El contexto se acumula y va DESPUES, y el veredicto
# lleva el sujeto dentro, que es lo que K97 exige de un VERDE.
CONTEXTO="sujeto: $QUIEN · hoy (UTC) $HOY · el dia cerrado mas reciente que se juzga es $(date -u -d "$HOY -1 day" +%F)
tablas: $(printf '%s\n' "$CAT" | wc -w) en el catalogo · $N_PLAN juzgadas · censo de $N_PAR parejas (tabla,dia) en $((t1-t0)) s"
[ -n "${NO_JUZGADAS// /}" ] && CONTEXTO="$CONTEXTO
NO JUZGADAS por declaracion:$NO_JUZGADAS"
[ -n "${SIN_DIA// /}" ] && CONTEXTO="$CONTEXTO
SIN DIA CERRADO dentro de su retencion (no se juzgan hoy, y no es un VERDE sobre ellas):$SIN_DIA"
[ -n "${SIN_DECLARAR// /}" ] && CONTEXTO="$CONTEXTO
EN EL CATALOGO Y SIN DECLARAR (nadie las juzga; declararlas en $(basename "$DECL")):$SIN_DECLARAR"

# EL ORDEN DE LOS DOS ESTADOS MALOS, IGUAL QUE EN K103: una perdida CONTADA es un hecho y una
# laguna de al lado no lo borra. Si hay perdida, ROJO, y la tabla que no se pudo contar sale
# NOMBRADA dentro del mismo rojo. NO MEDIDO queda para cuando no hay ninguna perdida contada y
# ADEMAS falta algo por contar: ahi si es verdad que no se sabe.
FALTAN=""
[ -n "${SIN_CONTAR// /}" ] && FALTAN="  y NO SE PUDO CONTAR$SIN_CONTAR, asi que de esas no se sabe (su marca de agua se conserva, no se rebaja)"
if [ -n "$PERDIDAS" ]; then
  echo "PERDIDA SILENCIOSA en $QUIEN: $(printf '%s\n' "$PERDIDAS" | grep -c .) dia(s) CERRADO(S) con menos filas que antes"
  printf '%s\n' "$PERDIDAS" | awk -F'|' '{printf "  %-40s %s   antes %s  ahora %s   (-%d)\n", $1, $2, $3, $4, $3-$4}'
  [ -n "$FALTAN" ] && printf '%s\n' "$FALTAN"
  echo "un dia cerrado no encoge solo. Mientras no vuelvan, este check sigue ROJO: la marca de"
  echo "agua no se rebaja, que es lo que hizo invisible la perdida del 09-16 durante doce dias."
  printf '%s\n' "$CONTEXTO"
  exit 1
fi
if [ -n "${SIN_CONTAR// /}" ]; then
  echo "NO MEDIDO: en $QUIEN no se pudo contar$SIN_CONTAR, asi que de esas no se sabe si perdieron filas."
  echo "cero perdidas sobre lo que SI se conto no es un VERDE mientras quede algo sin contar."
  printf '%s\n' "$CONTEXTO"
  exit 2
fi
if [ "${N_PREV:-0}" -eq 0 ]; then
  echo "NO MEDIDO: no habia censo anterior de $QUIEN en $CENSO, asi que esta corrida solo ha podido SEMBRAR la marca de agua ($N_PAR parejas). Una perdida se ve comparando dos censos, no uno."
  printf '%s\n' "$CONTEXTO"
  exit 2
fi
echo "ningun dia cerrado encogio en $QUIEN: $N_PAR parejas (tabla,dia) comparadas contra la marca de agua anterior, en $N_PLAN de $(printf '%s\n' "$CAT" | wc -w) tablas"
printf '%s\n' "$CONTEXTO"
exit 0
