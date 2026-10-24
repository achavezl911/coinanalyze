#!/bin/bash
# K116-control · LOS PLANTADOS QUE TIENEN QUE FALLAR EN K116 (campana BOT-1).
#
# EL ESCENARIO BUENO: el arbol de este control, K116-muestra.tsv.xz y K116-esperado.json tal cual -> VERDE; y una
# COPIA del codigo (app/rafagas.py, scripts/rafagas_estudio.py) en un directorio temporal -> VERDE. Cada plantado,
# en su copia:
#
#   umbral_movido     Z de los umbrales congelados a otro punto de la rejilla                    ROJO umbral movido
#   clase_invertida   el clasificador devuelve CASCADA donde decia BARRIDO y al reves            ROJO clase cambiada
#   rafaga_quitada    el detector se come la primera rafaga de cada activo                       ROJO falta la rafaga
#   rafaga_de_mas     la entrega sin su primera rafaga: el detector la sigue viendo              ROJO rafaga de mas
#   tabla_cambiada    una cifra de la tabla de la entrega (n de CASCADA, los tres activos) + 1   ROJO tabla
#   muestra_cambiada  un volumen de la primera barra de la muestra + 1 USD                       ROJO huella
#   sin_muestra       K116_MUESTRA a un fichero que no existe                                    NO MEDIDO
#   arbol_roto        K116_REPO a un directorio sin el codigo: el ayudante cae                    NO MEDIDO
#
# Y el check: sus tres invocaciones (A56) y los dos modos de SIGPIPE (A89) sobre el escenario bueno. No usa
# produccion, ni el espejo, ni una base. Al salir: el arbol y la muestra intactos, nada en el temporal.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K116-las-rafagas.sh"
MU="$AQUI/K116-muestra.tsv.xz"
ES="$AQUI/K116-esperado.json"
for f in "$CHK" "$AQUI/K116-rafagas.py" "$MU" "$ES" "$REPO/app/rafagas.py" "$REPO/scripts/rafagas_estudio.py"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
T=$(mktemp -d) || exit 2
trap 'rm -rf "$T"' EXIT
trap 'rm -rf "$T"; trap - EXIT; exit 143' INT TERM
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
SUJETO_ANTES=$(cat "$REPO/app/rafagas.py" "$REPO/scripts/rafagas_estudio.py" "$MU" "$ES" | sha256sum | cut -c1-12)

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-20s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-20s %s\n' "$1" "$3"; fi
}
arbol() {  # nombre -> una copia del codigo que K116 juzga
  local a="$T/$1"
  mkdir -p "$a/app" "$a/scripts"
  cp "$REPO/app/__init__.py" "$REPO/app/rafagas.py" "$a/app/"
  cp "$REPO/scripts/__init__.py" "$REPO/scripts/rafagas_estudio.py" "$a/scripts/"
  echo "$a"
}
huella() {  # arbol muestra esperado -> huella del sujeto
  cat "$1/app/rafagas.py" "$1/scripts/rafagas_estudio.py" "$2" "$3" 2>/dev/null | sha256sum | cut -c1-12
}
k116() {  # arbol muestra esperado -> rc; salida en $T/sal
  K116_REPO="$1" K116_MUESTRA="$2" K116_ESPERADO="$3" bash "$CHK" > "$T/sal" 2>&1
  echo $?
}
sustituye() {  # fichero viejo nuevo: falla si el texto viejo no esta
  python3 - "$@" <<'PY'
import sys
f, viejo, nuevo = sys.argv[1:]
t = open(f, encoding="utf-8").read()
if viejo not in t:
    sys.exit(f"control: no encuentro {viejo!r} en {f}")
open(f, "w", encoding="utf-8").write(t.replace(viejo, nuevo))
PY
}

echo "== el escenario bueno"
rc=$(k116 "$REPO" "$MU" "$ES")
comprueba base_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K116 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-150)"
BUENA=$(arbol buena)
H_BUENA=$(huella "$BUENA" "$MU" "$ES")
rc=$(k116 "$BUENA" "$MU" "$ES")
comprueba copia_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K116 ' && echo 0 || echo 1)" "rc=$rc · huella $H_BUENA · $(head -1 "$T/sal" | cut -c1-110)"

planta() {  # nombre esperado_rc patron detalle arbol muestra esperado
  local nombre=$1 rc_e=$2 patron=$3 que=$4 rc despues visto
  despues=$(huella "$5" "$6" "$7")
  rc=$(k116 "$5" "$6" "$7")
  visto=$(grep -E "$patron" "$T/sal" | head -1 | cut -c1-150)
  comprueba "$nombre" "$([ "$rc" = "$rc_e" ] && [ -n "$visto" ] && [ "$H_BUENA" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · $H_BUENA -> $despues · ${visto:-NO SALE: $(head -1 "$T/sal" | cut -c1-110)} · $que"
}

echo "== los plantados, cada uno en su copia"
a=$(arbol umbral)
z=$(grep -oP '^UMBRALES = Umbrales\(W=\d+, Z=\K[0-9.]+' "$a/app/rafagas.py")
case "$z" in 4.0) z2=5.0 ;; *) z2=4.0 ;; esac
sustituye "$a/app/rafagas.py" "UMBRALES = Umbrales(W=$(grep -oP '^UMBRALES = Umbrales\(W=\K\d+' "$a/app/rafagas.py"), Z=$z," \
  "UMBRALES = Umbrales(W=$(grep -oP '^UMBRALES = Umbrales\(W=\K\d+' "$a/app/rafagas.py"), Z=$z2,"
planta umbral_movido 1 "^ROJO  K116 umbral movido: Z $z -> $z2$" "Z $z -> $z2" "$a" "$MU" "$ES"

a=$(arbol clase)
sustituye "$a/app/rafagas.py" "return BARRIDO, m" "return @@, m"
sustituye "$a/app/rafagas.py" "return CASCADA, m" "return BARRIDO, m"
sustituye "$a/app/rafagas.py" "return @@, m" "return CASCADA, m"
planta clase_invertida 1 "^ROJO  K116 clase cambiada [A-Z]+USDT [0-9T:-]+Z: (CASCADA -> BARRIDO|BARRIDO -> CASCADA) " "CASCADA <-> BARRIDO" "$a" "$MU" "$ES"

a=$(arbol quitada)
sustituye "$a/app/rafagas.py" "            libre = i + calla
    return out" "            libre = i + calla
    return out[1:]"
planta rafaga_quitada 1 "^ROJO  K116 falta la rafaga [A-Z]+USDT [0-9T:-]+Z " "detecta_rasgos devuelve out[1:]" "$a" "$MU" "$ES"

python3 - "$ES" "$T/es-de-mas.json" <<'PY'
import json, sys
e = json.load(open(sys.argv[1]))
print("quito:", e["sin_liq"]["eventos"].pop(0))
open(sys.argv[2], "w").write(json.dumps(e, sort_keys=True, indent=1) + "\n")
PY
planta rafaga_de_mas 1 "^ROJO  K116 rafaga de mas [A-Z]+USDT [0-9T:-]+Z \([A-Z ]+\) \[sin_liq\]$" "la entrega sin su primera rafaga" "$BUENA" "$MU" "$T/es-de-mas.json"

python3 - "$ES" "$T/es-tabla.json" <<'PY'
import json, sys
e = json.load(open(sys.argv[1]))
e["sin_liq"]["tablas"]["CASCADA"]["TODOS"]["n"] += 1
open(sys.argv[2], "w").write(json.dumps(e, sort_keys=True, indent=1) + "\n")
PY
planta tabla_cambiada 1 "^ROJO  K116 tabla sin_liq\.CASCADA\.TODOS\.n: [0-9]+ -> [0-9]+$" "n de CASCADA (los tres) + 1 en la entrega" "$BUENA" "$MU" "$T/es-tabla.json"

python3 - "$MU" "$T/mu-cambiada.tsv.xz" <<'PY'
import lzma, sys
ls = lzma.open(sys.argv[1], "rt", encoding="ascii").read().split("\n")
x = ls[0].split("\t")
x[8] = str(int(x[8]) + 1)  # USD comprados de la primera barra
ls[0] = "\t".join(x)
with lzma.open(sys.argv[2], "wt", encoding="ascii", newline="\n") as w:
    w.write("\n".join(ls))
PY
planta muestra_cambiada 1 "^ROJO  K116 la muestra no es la de la entrega: huella " "un USD de mas en la primera barra" "$BUENA" "$T/mu-cambiada.tsv.xz" "$ES"

planta sin_muestra 2 "^NO MEDIDO: K116 sin la muestra $T/no-existe.tsv.xz$" "K116_MUESTRA a un fichero que no existe" "$BUENA" "$T/no-existe.tsv.xz" "$ES"

mkdir -p "$T/vacio"
planta arbol_roto 2 "^NO MEDIDO: K116 el ayudante cayo con rc=3: ModuleNotFoundError" "K116_REPO sin app/ ni scripts/" "$T/vacio" "$MU" "$ES"

echo "== el check: A89 los dos modos de SIGPIPE y A56 las tres invocaciones, sobre el escenario bueno"
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env "$modo" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K116 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
done
(bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K116 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd "$REPO" && bash harness/checks/K116-las-rafagas.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K116 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd /tmp && bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K116 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"

echo "== restaurado"
SUJETO_DESPUES=$(cat "$REPO/app/rafagas.py" "$REPO/scripts/rafagas_estudio.py" "$MU" "$ES" | sha256sum | cut -c1-12)
comprueba sujeto_intacto "$([ "$SUJETO_ANTES" = "$SUJETO_DESPUES" ] && echo 0 || echo 1)" "codigo, muestra y entrega $SUJETO_ANTES -> $SUJETO_DESPUES"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K116-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
