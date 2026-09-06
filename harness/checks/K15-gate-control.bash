#!/usr/bin/env bash
# K15-gate-control · ¿el gate de la CI PUEDE fallar?
#
# Un gate que no puede fallar es lo que teniamos. Hasta el 2026-09-06 su lista era
# `CHECKS="harness/checks/K02-cobertura-hueco.sh"` con K02 en ROJO, y su propio comentario
# lo decia: «compara 0 con 0 y no protege nada». Ahora K02 esta VERDE y se le anadio K88.
#
# ESTE FICHERO NO ES UN CHECK DEL ARNES y por eso no lleva .sh: bin/verify globea checks/*.sh
# y su marcador es del operador. Aqui se REPLICA la logica del gate -leida de
# .github/workflows/ci.yml- sobre dos arboles locales, y se comprueba que distingue un arbol
# sano de uno roto. Corre sin red y sin base de datos.
#
# LO QUE NO AFIRMA: que la CI de GitHub se comporte igual. Replica su comparacion, no su
# entorno. Lo que si afirma es que la LISTA de checks elegida puede producir un fallo, que es
# justo lo que la lista anterior no podia.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
YML="$ORIG/.github/workflows/ci.yml"
[ -r "$YML" ] || { echo "NO MEDIDO: no encuentro $YML"; exit 2; }

# LA LISTA SE LEE DEL WORKFLOW, no se teclea aqui. Si alguien la cambia, este control mide la
# nueva; si la vacia, lo dice. Es la misma regla que el resto del arnes: el sujeto se deriva.
CHECKS=$(sed -n 's/^ *CHECKS="\(.*\)"$/\1/p' "$YML" | head -1)
[ -n "$CHECKS" ] || { echo "NO MEDIDO: no se pudo leer CHECKS= de ci.yml"; exit 2; }
n_checks=$(printf '%s\n' $CHECKS | grep -c .)

DIR=$(mktemp -d) || exit 2
[ "${K15_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

# --- el arbol de mentira, copia del real ------------------------------------------------
SANO="$DIR/sano"
mkdir -p "$SANO"
for d in app sql harness ARQUITECTURA static tests; do
  [ -e "$ORIG/$d" ] && cp -r "$ORIG/$d" "$SANO/$d"
done
cp "$ORIG/README.md" "$SANO/" 2>/dev/null || true
rm -rf "$SANO/app/__pycache__" "$SANO/tests/__pycache__" 2>/dev/null

# contar(): la funcion del gate, replicada. Devuelve 99 si algun check queda en NOMED,
# porque un gate que no puede medir no es un gate que pasa.
contar() {
  local arbol="$1" verde=0 rc salida c
  for c in $CHECKS; do
    salida=$(REPO="$arbol" bash "$ORIG/$c" 2>&1); rc=$?
    case "$rc" in
      0) verde=$((verde + 1)) ;;
      1) ;;
      2) printf '%s\n' 99; return ;;
      *) printf '%s\n' 99; return ;;
    esac
  done
  printf '%s\n' "$verde"
}

caso() {  # <nombre> <esperado> <valor>
  if [ "$3" = "$2" ]; then
    pasan=$((pasan + 1)); printf '  [ok   ] %-52s %s\n' "$1" "$3"
  else
    fallos=$((fallos + 1)); printf '  [FALLA] %-52s esperaba %s, dio %s\n' "$1" "$2" "$3"
  fi
}

echo "K15-gate-control · lista leida de ci.yml: $n_checks check(s)"
printf '%s\n' $CHECKS | sed 's/^/    /'
echo

echo "EL SUELO · el arbol sano tiene que dar el maximo"
base=$(contar "$SANO")
caso "G1 el arbol sano da VERDE en los $n_checks" "$n_checks" "$base"

echo
echo "LOS DIENTES · un arbol roto tiene que dar MENOS que el sano"
# G2 · se rompe lo que K88 vigila: una ficha derivada editada a mano. Es el defecto ordinario
# -alguien toca el mapa en vez de regenerarlo- y hasta hoy el gate no lo veia.
ROTO1="$DIR/roto1"; cp -r "$SANO" "$ROTO1"
f=$(ls "$ROTO1"/ARQUITECTURA/rutas/*.md | head -1)
printf '\nlinea anadida a mano que el generador no produce\n' >> "$f"
v=$(contar "$ROTO1")
caso "G2 una ficha derivada editada a mano baja la cuenta" "$((n_checks - 1))" "$v"

# G3 · y se rompe lo que K02 vigila: una ruta de serie que deja de publicar data_gaps.
ROTO2="$DIR/roto2"; cp -r "$SANO" "$ROTO2"
python3 - "$ROTO2" <<'PY'
import re, sys
from pathlib import Path
p = Path(sys.argv[1]) / "app/api.py"
t = p.read_text(encoding="utf-8")
# se le quita el bloque data_gaps a UNA ruta de serie: la primera que lo monte a mano.
t = t.replace('result["data_gaps"] = {', 'result["zzz_sin_gaps"] = {', 1)
p.write_text(t, encoding="utf-8")
PY
v=$(contar "$ROTO2")
caso "G3 una serie sin data_gaps baja la cuenta" "$((n_checks - 1))" "$v"

echo
echo "ANTI-FANTASMA · un gate que no puede medir no pasa"
# G4 · si un check queda en NOMED, contar() devuelve 99 y ninguna comparacion lo toma por
# bueno. Se induce borrando app/api.py, que deja a los dos checks sin sujeto.
ROTO3="$DIR/roto3"; cp -r "$SANO" "$ROTO3"; rm -f "$ROTO3/app/api.py"
v=$(contar "$ROTO3")
caso "G4 sin api.py: 99, no una cuenta baja" "99" "$v"

# G5 · la lista tiene que tener MAS de un check, o el gate depende de uno solo y un NOMED
# suyo lo deja ciego. Es la razon por la que se anadio K88.
caso "G5 la lista tiene mas de un check" "si" "$([ "$n_checks" -gt 1 ] && echo si || echo no)"

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
