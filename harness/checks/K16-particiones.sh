#!/bin/bash
# K16  particiones y retencion con red. app/partitioning.py es lo UNICO del arbol que
# borra datos por diseno y no lo importa ningun test.
#
# EL CRITERIO DE LA DUPLICACION CAMBIO EL 2026-09-06, y esta es la razon. La version
# anterior enrojecia con «ensure_temporal_partitions declarada 2 veces en schema.sql» y
# llevaba ROJA 26 de 27 pasadas guardadas sin que nadie actuara. Al medirlo salieron tres
# cosas que el criterio viejo no podia ver:
#
#   1. NO ES UN OBJETO DUPLICADO, SON CINCO. En sql/schema.sql hay 123 objetos CREATE y
#      cinco estan declarados dos veces: las funciones enforce_liquidation_event_unique
#      (354, 2004), ensure_temporal_partitions (1470, 2028),
#      drop_expired_temporal_partitions (1541, 2089) y apply_temporal_retention
#      (1593, 2136), mas el trigger liquidations_realtime_event_unique_trigger (377, 2024).
#      El check viejo preguntaba por UNO tecleado a mano, asi que solo podia encontrar ese.
#
#   2. LOS CINCO PARES SON SEMANTICAMENTE IDENTICOS. Cuatro son iguales token a token.
#      El quinto -ensure_temporal_partitions- difiere solo en que la primera parte el
#      literal de format() en dos cadenas adyacentes y la segunda lo escribe entero;
#      PostgreSQL las concatena, asi que la cadena resultante es la misma. Medirlo linea a
#      linea decia «3 de 5 distintas» y las tres diferencias eran saltos de linea.
#
#   3. GANA LA SEGUNDA, y no se deduce: se le pregunta a 140. pg_get_functiondef conserva
#      el texto fuente, y esa particion del literal sobrevive en la base:
#        bool_or(... LIKE '%PARTITION OF %I.%I ''%')        -> f   (la de :1470 NO esta)
#        bool_or(... LIKE '%PARTITION OF %I.%I FOR VALUES%') -> t   (la de :2028 SI)
#      Las dos entraron en el MISMO commit, 91111f6 del 2026-08-09 (PR #9).
#
# QUE SE GATEA AHORA, Y POR QUE. Una duplicacion con cuerpos identicos no puede producir una
# base incorrecta: aplique el desplegador la que aplique, el resultado es el mismo. Lo que SI
# la produce es la DIVERGENCIA -dos cuerpos distintos donde el ultimo pisa al primero en
# silencio, y editar el equivocado no da error, simplemente no hace nada-. Asi que:
#   ROJO   si dos declaraciones del mismo objeto DIVERGEN.
#   CUENTA -sin enrojecer- la duplicacion identica, que es deuda y no defecto vivo.
# Los duplicados se DERIVAN del fichero, no se teclean: un sexto duplicado entra solo.
#
# LO QUE ESTE CHECK NO ARREGLA: el bloque duplicado sigue ahi. Borrarlo es un cambio NO
# aditivo a sql/schema.sql y eso es la puerta 1 de CLAUDE.md §5, asi que va a la mesa de
# Alejandro y no lo hago yo.
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

# --- 1 · DUPLICADOS DERIVADOS · rojo por DIVERGENCIA, cuenta por duplicacion identica ---
dup=$(python3 - "$REPO/sql/schema.sql" <<'PY' 2>&1
import re, sys
from pathlib import Path
L = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()

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

obj = {}
for n, l in enumerate(L, 1):
    m = RE_C.match(l)
    if m:
        obj.setdefault((" ".join(m.group(1).upper().split()), m.group(2).lower()), []).append(n)

total = len(obj)
dups = {k: v for k, v in obj.items() if len(v) > 1}
diverge, iguales = [], []
for (tipo, nom), ls in sorted(dups.items()):
    cuerpos = [tokens(cuerpo(x)) for x in ls]
    (diverge if len(set(cuerpos)) > 1 else iguales).append(f"{tipo.lower()} {nom} ({','.join(map(str, ls))})")
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
echo "ningun objeto de schema.sql diverge consigo mismo (de $n_obj CREATE), $cubierto test(s) sobre partitioning, y la funcion viva gestiona las 5 tablas"
printf '  DEUDA, no defecto: %s objeto(s) declarados dos veces con el MISMO cuerpo. Se cuenta, no enrojece.\n' "$n_ig"
printf '%s\n' "$dup" | sed -n 's/^  I /    /p'
echo "  borrar el bloque duplicado es un cambio NO aditivo a schema.sql: puerta 1, pendiente de Alejandro"
exit 0
