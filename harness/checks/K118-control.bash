#!/bin/bash
# K118-control · LOS PLANTADOS QUE TIENEN QUE FALLAR EN K118 (campana 151-A).
#
# EL ESCENARIO BUENO: el arbol de este control y la muestra -> VERDE; y una COPIA de app/ en un temporal -> VERDE.
# Cada plantado, en su copia (o en su muestra):
#
#   cubo_no_parte      parte() acepta cualquier cubo: scale3 (100 contra 10) deja niveles     ROJO nivel a medias
#   venta_por_techo    la venta de merge-depth se declara por suelo: se guardan sus niveles    ROJO nivel a medias
#   escalera_movida    la compra honda empieza un paso mas abajo del borde del vivo            ROJO escalera distinta
#   rancia_nunca       RANCIA_S = 10**6: una foto de 75.001 s se sirve como conocida            ROJO cuenta como conocida
#   rancia_corta       RANCIA_S = 30: a 75 s justos ya se sirve sin niveles                     ROJO no es la decision C
#   fila_cambiada      una cantidad de una fila GUARDADA de la muestra + 1                      ROJO escalera distinta
#   sin_muestra        K118_MUESTRA a un fichero que no existe                                  NO MEDIDO
#   arbol_roto         K118_REPO a un directorio sin app/                                       NO MEDIDO
#
# No usa produccion, ni el espejo, ni una base. Al salir: el arbol y la muestra intactos, nada en el temporal.
# Uso: K118-control.bash [MUESTRA]
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K118-libro-honda.sh"
MU=${1:-/srv/coinanalyze/evidencia/c151-libro-honda-muestra.json.xz}
for f in "$CHK" "$AQUI/K118-honda.py" "$MU" "$REPO/app/libro_honda.py"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
T=$(mktemp -d) || exit 2
trap 'rm -rf "$T"' EXIT
trap 'rm -rf "$T"; trap - EXIT; exit 143' INT TERM
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
SUJETO_ANTES=$(cat "$REPO/app/libro_honda.py" "$REPO/app/libro_lectura.py" "$MU" | sha256sum | cut -c1-12)

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-18s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-18s %s\n' "$1" "$3"; fi
}
arbol() {  # nombre -> una copia de app/ que K118 juzga
  mkdir -p "$T/$1"; cp -r "$REPO/app" "$T/$1/app"; echo "$T/$1"
}
k118() {  # arbol muestra -> rc; salida en $T/sal
  K118_REPO="$1" K118_MUESTRA="$2" K118_PY="$REPO/.venv/bin/python" bash "$CHK" > "$T/sal" 2>&1
  echo $?
}
sustituye() {  # fichero viejo nuevo: falla si el texto viejo no esta
  python3 - "$@" <<'PY'
import sys
f, viejo, nuevo = sys.argv[1:]
t = open(f, encoding="utf-8").read()
if viejo not in t:
    sys.exit(f"control: no encuentro {viejo!r} en {f}")
open(f, "w", encoding="utf-8").write(t.replace(viejo, nuevo, 1))
PY
}
caso() {  # nombre rc_esperado patron arbol muestra
  local rc; rc=$(k118 "$4" "$5")
  if [ "$rc" = "$2" ] && grep -q -- "$3" "$T/sal"; then
    comprueba "$1" 0 "rc=$rc: $(head -c 260 "$T/sal" | tr '\n' ' ')"
  else
    comprueba "$1" 1 "rc=$rc (esperaba $2 con «$3»): $(head -c 400 "$T/sal" | tr '\n' ' ')"
  fi
}

caso base 0 "VERDE: K118" "$REPO" "$MU"
B=$(arbol copia); caso copia 0 "VERDE: K118" "$B" "$MU"

A=$(arbol cubo_no_parte)
sustituye "$A/app/libro_honda.py" 'return agrupa in ("exacto", "suelo") and c is not None' 'return True or agrupa in ("exacto", "suelo") and c is not None' || exit 2
caso cubo_no_parte 1 "nivel a medias guardado: el cubo no parte el paso" "$A" "$MU"

A=$(arbol venta_por_techo)
sustituye "$A/app/libro_honda.py" '{"b": "suelo", "a": "techo"})' '{"b": "suelo", "a": "suelo"})' || exit 2
caso venta_por_techo 1 "bitget_usdt .* venta recalculada por el arbol: nivel a medias" "$A" "$MU"

A=$(arbol escalera_movida)
sustituye "$A/app/libro_honda.py" 'desde = _techo(vivo, paso) - paso' 'desde = _techo(vivo, paso) - 2 * paso' || exit 2
caso escalera_movida 1 "compra recalculada por el arbol: escalera distinta" "$A" "$MU"

A=$(arbol rancia_nunca)
sustituye "$A/app/libro_honda.py" 'RANCIA_S = 75' 'RANCIA_S = 10**6' || exit 2
caso rancia_nunca 1 "CUENTA como conocida" "$A" "$MU"

A=$(arbol rancia_corta)
sustituye "$A/app/libro_honda.py" 'RANCIA_S = 75' 'RANCIA_S = 30' || exit 2
caso rancia_corta 1 "no es el de la decision C" "$A" "$MU"

"$REPO/.venv/bin/python" - "$MU" "$T/fila_cambiada.json.xz" <<'PY' || exit 2
import json, lzma, sys
from decimal import Decimal
c = json.loads(lzma.decompress(open(sys.argv[1], "rb").read()))
f = next(x["fila"] for x in c if x["fila"] and x["fila"]["compras"])
f["compras"][0] = str(Decimal(f["compras"][0]) + 1)
open(sys.argv[2], "wb").write(lzma.compress(json.dumps(c).encode()))
PY
caso fila_cambiada 1 "compra guardada: escalera distinta" "$REPO" "$T/fila_cambiada.json.xz"

caso sin_muestra 2 "NO MEDIDO: K118 sin la muestra" "$REPO" "$T/no-existe.json.xz"
mkdir -p "$T/vacio"; caso arbol_roto 2 "NO MEDIDO: K118 no importo el arbol" "$T/vacio" "$MU"

ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
SUJETO_DESPUES=$(cat "$REPO/app/libro_honda.py" "$REPO/app/libro_lectura.py" "$MU" | sha256sum | cut -c1-12)
[ "$ARBOL_ANTES $SUJETO_ANTES" = "$ARBOL_DESPUES $SUJETO_DESPUES" ]; comprueba intacto $? "arbol $ARBOL_DESPUES, sujeto $SUJETO_DESPUES"
echo "K118-control: $pasan de $total pasan${fallan:+ · fallan:$fallan}"
[ "$pasan" = "$total" ]
