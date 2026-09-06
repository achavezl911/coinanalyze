#!/bin/bash
# K16  particiones y retencion con red. app/partitioning.py es lo UNICO del arbol que
# borra datos por diseno y no lo importa ningun test.
#
# LO QUE ESTE CHECK LLAMABA «DUPLICADO» NO LO ERA, Y LO DEMUESTRA UN TEST QUE YA EXISTIA.
#
# Hasta el 2026-09-06 K16 enrojecia con «ensure_temporal_partitions declarada 2 veces en
# schema.sql» y llevaba ROJA 26 de 27 pasadas guardadas. Se midio y salieron CINCO objetos
# declarados dos veces, no uno. Se pidio puerta para borrar el segundo bloque, se concedio,
# se borro... y la CI del PR #151 fallo. **La puerta estaba mal concedida y el recorte esta
# deshecho.** Los dos tests que lo prohibian:
#
#   tests/test_partitioning_postgres.py::test_supported_deployment_path_includes_the_real_partition_migration
#   tests/test_pr20_semantics.py::test_pr20_schema_preserves_inline_partition_migration_as_exact_prior_transaction
#
# y el motivo esta escrito encima del primero (test_partitioning_postgres.py:245-252):
#
#   "schema.sql must be self-contained: the production deploy wrapper (deploy-coinalyze,
#    outside this repo) copies ONLY schema.sql to a scratch path before running `psql -f` on
#    it -- no sibling sql/migrations/ directory exists there. A relative \ir include would
#    silently fail to find its target in that environment (psql exits 0 on a missing \ir
#    target, so ON_ERROR_STOP does not catch it), which would make the deploy wrapper report
#    success while the real partition migration never ran. The migration is inlined directly
#    instead."
#
# O SEA QUE LAS LINEAS 1631-2165 NO SON UNA DUPLICACION: son
# sql/migrations/20260809_temporal_partitioning.sql copiado BYTE A BYTE como transaccion
# previa -535 lineas, de su BEGIN; a su COMMIT;-, y el test lo exige con
# `assert MIGRATION.strip() in schema`. Los cinco «duplicados» son objetos que esa migracion
# crea; sus primeras declaraciones (354, 377, 1470, 1541, 1593) estan todas FUERA.
#
# QUE HACE AHORA ESTE CHECK, Y QUE NO HACE:
#   · EXCLUYE la region incrustada y mide solo lo de FUERA. Medido el 2026-09-06: fuera hay
#     122 objetos CREATE y CERO duplicados.
#   · NO comprueba que la region siga igual al fichero de migracion. Se penso hacerlo y se
#     descarto al medirlo: `MIGRATION.strip() in schema` ya es exactamente esa pregunta, y la
#     contesta mejor -compara contra el FICHERO, no contra un marcador escrito a mano-.
#     Duplicar un test dentro de un check no es cobertura, es ruido.
#   · Los limites de la region se DERIVAN del fichero de migracion, con el mismo instrumento
#     que el test. Si alguien la mueve, el check la sigue; si alguien la edita, el que
#     enrojece es el test, que es su sitio.
#
# LO QUE SE GATEA, para lo de fuera: la DIVERGENCIA -dos cuerpos distintos donde el ultimo
# pisa al primero en silencio, y editar el equivocado no da error, simplemente no hace nada-.
# La duplicacion identica se CUENTA sin enrojecer. Los duplicados se derivan, no se teclean.
#
# LO QUE SE MIDIO Y SIGUE VALIENDO, aunque la conclusion fuera mala: entre las dos mitades,
# `:1993-1996` renombra las tablas, asi que el `CREATE TRIGGER` de :377 y el de dentro de la
# region tienen el MISMO TEXTO y tocan TABLAS DISTINTAS. Aplicando el esquema previo
# (91111f6~1) y encima el actual sobre bases desechables: con la region el trigger queda en 6
# relaciones, sin ella en 1 -solo el backup-. Sobre una base VACIA los dos casos dan lo mismo,
# porque sin tablas viejas no hay renombrado, y por eso la CI que aplica el fichero a una base
# desechable (ci.yml:65-72) es ciega a ESA diferencia. Guardado aqui para el dia que alguien
# cambie el contrato: la region no se puede quitar por rango.
#
# Las otras tres comprobaciones no se tocan: la cobertura de tests sobre partitioning, y el
# oraculo VIVO contra 140 -la funcion existe una sola vez y gestiona las cinco tablas que
# dice gestionar-.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PRODSQL=${K16_PRODSQL:-$B/bin/prodsql}
GESTIONADAS="futures_trades_realtime spot_trades_realtime orderbook_snapshot liquidations_realtime scalp_signal_snapshot"

[ -r "$REPO/sql/schema.sql" ] || { echo "NO MEDIDO: no se puede leer sql/schema.sql"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "NO MEDIDO: no hay python3"; exit 2; }

fallos=""

# --- 1 · DUPLICADOS DERIVADOS, FUERA DE LA REGION INCRUSTADA ---------------------------
MIGRACION="$REPO/sql/migrations/20260809_temporal_partitioning.sql"
[ -r "$MIGRACION" ] || { echo "NO MEDIDO: no se puede leer sql/migrations/20260809_temporal_partitioning.sql, y sin el no se sabe que tramo de schema.sql es la migracion incrustada"; exit 2; }
dup=$(python3 - "$REPO/sql/schema.sql" "$MIGRACION" <<'PY' 2>&1
import re, sys
from pathlib import Path
texto = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
L = texto.splitlines()

# LA REGION INCRUSTADA · sus limites salen del FICHERO DE MIGRACION, no de una lista aqui.
# Es el mismo instrumento que usa el test que la exige, asi que si alguien mueve la region,
# este check la sigue; y si alguien la edita, el que enrojece es el test, que es su sitio.
mig = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace").strip()
i = texto.find(mig)
if i < 0:
    print("SINREGION")
    raise SystemExit
r_ini = texto[:i].count("\n") + 1
r_fin = r_ini + mig.count("\n")

RE_C = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?"
    r"(TABLE|INDEX|UNIQUE\s+INDEX|FUNCTION|VIEW|MATERIALIZED\s+VIEW|TYPE|TRIGGER|SCHEMA|EXTENSION)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE)

def cuerpo(ini):
    i, trozo, dolar = ini - 1, [L[ini - 1]], 0
    while i + 1 < len(L):
        i += 1
        trozo.append(L[i])
        dolar += L[i].count("$$")
        if dolar >= 2 and L[i].rstrip().endswith(";"):
            break
        if dolar == 0 and L[i].rstrip().endswith(";") and len(trozo) > 1:
            break
    return trozo

def tokens(t):
    # SE COMPARA EL CUERPO ENTERO COMO FLUJO DE TOKENS, no linea a linea: medir por linea
    # cuenta como diferencia el sitio donde alguien partio la linea. Ademas se pegan los
    # literales adyacentes ('a' 'b' -> 'ab'), que es lo que hace PostgreSQL.
    #
    # EL SEGUNDO .split() NO SOBRA. La primera version juntaba las lineas ya colapsadas con
    # " ".join(...), y una linea EN BLANCO aporta "" y deja DOS espacios seguidos: dos
    # cuerpos identicos con los blancos en distinto sitio salian divergentes. Dio 2
    # divergencias donde hay 1, y el control no lo cazo porque ningun fixture tenia los
    # blancos desplazados. Ahora hay uno (N5).
    txt = " ".join(x for x in t if not x.strip().startswith("--"))
    txt = " ".join(txt.split())
    return re.sub(r"' '", "", txt)

# SOLO LO DE FUERA DE LA REGION. Dentro no se mira, y no por pereza: lo de dentro no es un
# duplicado sino la migracion copiada byte a byte, y ya lo vigila quien debe (ver cabecera).
obj = {}
for n, l in enumerate(L, 1):
    if r_ini <= n <= r_fin:
        continue
    m = RE_C.match(l)
    if m:
        obj.setdefault((" ".join(m.group(1).upper().split()), m.group(2).lower()), []).append(n)

total = len(obj)
dups = {k: v for k, v in obj.items() if len(v) > 1}
diverge, iguales = [], []
for (tipo, nom), ls in sorted(dups.items()):
    cuerpos = [tokens(cuerpo(x)) for x in ls]
    etq = f"{tipo.lower()} {nom} ({','.join(map(str, ls))})"
    (diverge if len(set(cuerpos)) > 1 else iguales).append(etq)
print(f"REGION {r_ini} {r_fin}")
print(f"TOTAL {total}")
print(f"DIVERGEN {len(diverge)}")
for d in diverge:
    print(f"  D {d}")
print(f"IGUALES {len(iguales)}")
for i in iguales:
    print(f"  I {i}")
PY
); rc_dup=$?
if [ "$rc_dup" != "0" ]; then
  echo "NO MEDIDO: no se pudo analizar schema.sql: $(printf '%s' "$dup" | tail -1 | cut -c1-110)"; exit 2
fi
# SI LA REGION NO ESTA, NO SE MIDE. Sin ella no se puede excluir, y el check reportaria como
# duplicados los cinco objetos que la migracion crea -que es justo el error que costo la
# puerta-. Ademas, si no esta, el que tiene que hablar es el test, no este check.
case "$dup" in
  SINREGION*) echo "NO MEDIDO: sql/schema.sql ya no contiene la migracion incrustada byte a byte; eso lo juzga tests/test_partitioning_postgres.py, no este check"; exit 2 ;;
esac
r_ini=$(printf '%s\n' "$dup" | awk '/^REGION/{print $2}')
r_fin=$(printf '%s\n' "$dup" | awk '/^REGION/{print $3}')
n_obj=$(printf '%s\n' "$dup" | awk '/^TOTAL/{print $2}')
n_div=$(printf '%s\n' "$dup" | awk '/^DIVERGEN/{print $2}')
n_ig=$(printf '%s\n' "$dup" | awk '/^IGUALES/{print $2}')
# CERO OBJETOS NO ES CERO DEFECTOS: si el analizador deja de reconocer los CREATE, cero
# duplicados es indistinguible de un fichero limpio. Sin sujeto, NOMED.
[ "${n_obj:-0}" -ge 50 ] || { echo "NO MEDIDO: solo $n_obj objetos CREATE en schema.sql; el analizador no esta reconociendolos"; exit 2; }
if [ "${n_div:-0}" -gt 0 ]; then
  fallos="$fallos $n_div objeto(s) de schema.sql declarados dos veces con cuerpos DISTINTOS -el ultimo pisa al primero en silencio-:$(printf '%s\n' "$dup" | sed -n 's/^  D /  /p' | tr '\n' ' ')"
fi

# --- 2 · lo unico que borra por diseno tiene que estar cubierto -------------------------
cubierto=$(grep -rl 'app\.partitioning\|from app import partitioning' "$REPO/tests/" 2>/dev/null | wc -l)
[ "$cubierto" -ge 1 ] || fallos="$fallos; ningun test importa app/partitioning, que es lo unico que borra por diseno"

# --- 3 y 4 · el oraculo VIVO contra 140 -------------------------------------------------
vivas=$("$PRODSQL" "SELECT count(*) FROM pg_proc WHERE proname='ensure_temporal_partitions'" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
[ -n "$vivas" ] || { echo "NO MEDIDO: prodsql no respondio (${fallos:-canal})"; exit 2; }
[ "$vivas" -eq 1 ] || fallos="$fallos; en 140 hay $vivas funciones ensure_temporal_partitions"

# Si manana alguien anade una tabla particionada y no entra aqui, se queda sin particiones
# nuevas y sin retencion, en silencio.
cuerpo=$("$PRODSQL" "SELECT replace(pg_get_functiondef(oid), E'\n', ' ') FROM pg_proc WHERE proname='ensure_temporal_partitions' LIMIT 1" 2>/dev/null)
for t in $GESTIONADAS; do
  case "$cuerpo" in *"$t"*) ;; *) fallos="$fallos; la funcion viva no gestiona $t" ;; esac
done

[ -z "${fallos# }" ] || { printf '%s\n' "${fallos#; }" | sed 's/^ //'; exit 1; }
echo "ningun objeto de schema.sql diverge consigo mismo (de $n_obj CREATE fuera de la migracion incrustada), $cubierto test(s) sobre partitioning, y la funcion viva gestiona las 5 tablas"
printf '  la migracion incrustada (lineas %s-%s) NO se mira aqui: es %s copiado byte a byte,\n' \
  "$r_ini" "$r_fin" "sql/migrations/20260809_temporal_partitioning.sql"
printf '  y que siga siendolo lo exige tests/test_partitioning_postgres.py:257 con MIGRATION.strip() in schema.\n'
if [ "${n_ig:-0}" -gt 0 ]; then
  printf '  DEUDA, no defecto: %s objeto(s) FUERA de la region declarados dos veces con el MISMO cuerpo. Se cuenta, no enrojece.\n' "$n_ig"
  printf '%s\n' "$dup" | sed -n 's/^  I /    /p'
fi
exit 0
