#!/bin/bash
# K106-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA COSA QUE LA VISTA DE ENTRADAS PROMETE
# (campana 137, C1-C5).
#
# EL ESCENARIO BUENO SALE DE LA PILA DE VERDAD: una base desechable k105_ctl_k106_<pid> con schema.sql
# del arbol, sembrada por K105-control-siembra (BTC con un DISPARADO vivo por version, evaluado con
# el generador real), y la respuesta que da sobre ella la ruta del arbol (vista.construir). El banco
# (K106-banco.py) sirve la mesa del ARBOL con esa respuesta; cada plantado cambia la RESPUESTA o la
# PANTALLA (un fichero que el banco sirve en vez del del arbol: el arbol no se toca) y K106-vista.py
# tiene que condenarlo POR SU BRAZO. Los brazos, con lo que plantan: K106-plantados.py lista.
#
#   C1  un DISPARADO vivo (entero, con su cuenta atras corriendo) · el mismo ya caducado · caducando
#       en pantalla · la ruta caida, al cargar y con la vista abierta · «no disponible» · el generador
#       parado, y parandose en pantalla · un plan de v1 y otro de v2 sobre la misma zona
#   C2  «3/7» · «43 %» · «0.43 de acierto» · «3 de 7» · «43 por ciento» · «favorable» · «alta
#       probabilidad» · «buena entrada» · un «43 %» SERVIDO · color y orden por resultado. Y sus
#       gemelos PERMITIDOS: «x0,43 del objetivo» y «0,43 %» de distancia. Y la NO INTERFERENCIA:
#       dos respuestas que solo difieren en el resultado dan la MISMA pantalla
#   C3  las cinco respuestas de DECIDE, cada una con su frase · la palabra rancia · la frase de una
#       servida para otra · NO EVALUABLE como un «no», y en rojo · un plan en contra, callado
#   C4  la vista principal pidiendo la ruta de entradas · la de entradas pidiendo una PARTE ·
#       K102 con DECIDE empujado fuera del pliegue por la cabecera
#   C5  la misma ruta trayendo el peso del registro entero · una vista que no obedece su cadencia
#   y del remate: R2  un coste de 0,002 del objetivo, pintado («x0,002») y redondeado a «x0,00» como
#       antes · su gemelo, un cero servido que se pinta como cero.  R3  la tabla de recuentos sin su
#       frase (callada por la pantalla, y sin servir por la ruta) · con la cabecera VIGILANDO de antes
#   y el check: sus tres invocaciones (A56), los dos modos de SIGPIPE (A89), y una mesa sin la vista
#   (NO MEDIDO, ni ROJO ni VERDE). Y el lector de cifras de la propia red: «63.385» son sesenta y
#   tres mil, y una variante de la sonda que lo lea como K102 tiene que condenar una pagina fiel.
#
# No usa produccion ni el espejo. Puertos: 8106 (el banco) y 8107 (el sobre plantado de K102); se
# niega a arrancar si estan ocupados. Al salir: 0 bases, ningun servidor suyo vivo, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K106-la-pantalla-de-entradas.sh"
SONDA="$AQUI/K106-vista.py"
BANCO="$AQUI/K106-banco.py"
PLANTA="$AQUI/K106-plantados.py"
SIEMBRA="$AQUI/K105-control-siembra.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$SONDA" "$BANCO" "$PLANTA" "$SIEMBRA" "$PY" "$AQUI/K102-decide-lo-primero.sh" "$AQUI/K102-sobre-plantado.py"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
PID=$$
DB="k105_ctl_k106_${PID}"
P1=8106; P2=8107
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "control: el puerto $p esta ocupado (otro control u otro servidor): no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SERV=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

para() { [ -n "$SERV" ] && { kill "$SERV" 2>/dev/null; wait "$SERV" 2>/dev/null; }; SERV=""; }
limpia() {
  para
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k105_ctl_k106_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k105_ctl_k106_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k105_ctl_k106_${PID}%'")"
  echo "servidores del control vivos: $(ss -ltn 2>/dev/null | grep -cE ":($P1|$P2) ")"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-28s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-28s %s\n' "$1" "$3"; fi
}
sonda() { "$PY" "$SONDA" --base "http://127.0.0.1:$P1" --activo BTC "$@" > "$T/sal" 2>&1; echo $?; }
hallazgo() { grep -E "^   - .*($1)" "$T/sal" | head -1 | cut -c1-150; }

echo "== la base: schema.sql del arbol, la siembra de K105 y la ruta de verdad"
createdb -h "$H" "$DB" || exit 2
psql -h "$H" -d "$DB" -X -q -v ON_ERROR_STOP=1 -f "$REPO/sql/schema.sql" > /dev/null 2>&1 || { echo "control: schema.sql no aplica"; exit 2; }
"$PY" "$SIEMBRA" escenario "postgresql:///$DB?host=$H" "$T/release" > "$T/siembra" 2>&1 || { echo "control: la siembra fallo: $(tail -1 "$T/siembra")"; exit 2; }
mkdir -p "$T/b"
"$PY" "$PLANTA" base "postgresql:///$DB?host=$H" "$T/b" || { echo "control: no hay base"; exit 2; }
"$PY" "$PLANTA" planta vivo "$T/b" > /dev/null || exit 2
: > "$T/diario"
"$PY" "$BANCO" --puerto "$P1" --respuesta "$T/b/respuesta.json" --sobre "$T/b/sobre" --diario "$T/diario" > "$T/banco.log" 2>&1 &
SERV=$!
sleep 1.5
ss -ltn 2>/dev/null | grep -q ":$P1 " || { echo "control: el banco no arranco: $(tail -1 "$T/banco.log")"; exit 2; }

echo "== los brazos: cada plantado, por el brazo que lo tiene que condenar"
"$PY" "$PLANTA" lista > "$T/lista" || exit 2
HUELLA_BUENA=""
while IFS=$'\t' read -r nombre veredicto patron opciones que <&3; do
  linea=$("$PY" "$PLANTA" planta "$nombre" "$T/b") || { comprueba "$nombre" 1 "no se pudo plantar"; continue; }
  antes=${linea#*huella }; antes=${antes%% *}; despues=${linea##* }
  [ -z "$HUELLA_BUENA" ] && HUELLA_BUENA="$despues"
  [ "$opciones" = "-" ] && opciones=""
  # shellcheck disable=SC2086 - las opciones de la sonda van separadas por espacios, sin espacios dentro
  rc=$(sonda ${opciones//\{D\}/$T/b})
  if [ "$veredicto" = "PASA" ]; then
    comprueba "$nombre" "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $antes -> $despues · $que$([ "$rc" = 0 ] || echo " · $(grep -m1 '^   - ' "$T/sal" | cut -c1-140)")"
  else
    visto=$(hallazgo "$patron")
    comprueba "$nombre" "$([ "$rc" = 1 ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && echo 0 || echo 1)" \
      "rc=$rc · $antes -> $despues · ${visto:-NO SALE el hallazgo esperado: $(grep -m1 '^   - ' "$T/sal" | cut -c1-110)}"
  fi
done 3< "$T/lista"

echo "== C2 · la NO INTERFERENCIA: dos respuestas que solo difieren en el RESULTADO, la misma pantalla"
"$PY" "$PLANTA" resueltos "$T/b" objetivo,stop,objetivo > /dev/null; sonda --firma > /dev/null; fa=$(grep '^firma ' "$T/sal")
"$PY" "$PLANTA" resueltos "$T/b" stop,objetivo,stop > /dev/null;     sonda --firma > /dev/null; fb=$(grep '^firma ' "$T/sal")
comprueba no_interferencia "$([ -n "$fa" ] && [ "$fa" = "$fb" ] && echo 0 || echo 1)" "la vista real: $fa y $fb"
"$PY" "$PLANTA" planta color_por_resultado "$T/b" > /dev/null; sonda --firma > /dev/null; fc=$(grep '^firma ' "$T/sal")
comprueba la_firma_ve_el_color "$([ -n "$fc" ] && [ "$fc" != "$fa" ] && echo 0 || echo 1)" "con el color plantado: $fc"

echo "== el lector de cifras: en es-ES «63.385» son sesenta y tres mil. La variante que lo lee como K102 tiene que CONDENAR una pagina fiel"
# Una copia de la sonda con UNA linea cambiada: compara las cifras con K102.casan_valores, que solo
# quita los puntos de miles cuando hay coma. Si el brazo precio_de_miles no la condena, no mide nada.
ln -s "$AQUI/K102-mesa.py" "$T/K102-mesa.py"; ln -s "$AQUI/K44-contrato-mesa.tsv" "$T/K44-contrato-mesa.tsv"
sed 's|^        return abs(float(servido) - pintado) <= 0.5 \* 10 \*\* -len(decimales) + 1e-9$|        return K.casan_valores(numero.group(0), servido)|' "$SONDA" > "$T/K106-vista.py"
mordio=$(grep -c 'return K.casan_valores(numero.group(0), servido)' "$T/K106-vista.py")
"$PY" "$PLANTA" planta precio_de_miles "$T/b" > /dev/null
"$PY" "$T/K106-vista.py" --base "http://127.0.0.1:$P1" --activo BTC > "$T/sal" 2>&1; rc=$?
visto=$(hallazgo "E2 .*zona.low: pinta '63.385'")
comprueba lector_viejo_condena "$([ "$mordio" = 1 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && echo 0 || echo 1)" "variante plantada ($mordio linea) · rc=$rc · ${visto:-NO SALE: $(grep -m1 '^   - ' "$T/sal" | cut -c1-100)}"

echo "== el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones, y una mesa SIN la vista"
"$PY" "$PLANTA" planta vivo "$T/b" > /dev/null
corre() { env "$@" MESA_BASE="http://127.0.0.1:$P1" K106_ACTIVOS=BTC K106_OBSERVA=0 bash "$CHK" > "$T/chk" 2>&1; }
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  corre $modo; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^K106 · VERDE' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
done
(env MESA_BASE="http://127.0.0.1:$P1" K106_ACTIVOS=BTC K106_OBSERVA=0 bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd "$REPO" && env MESA_BASE="http://127.0.0.1:$P1" K106_ACTIVOS=BTC K106_OBSERVA=0 bash harness/checks/K106-la-pantalla-de-entradas.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd /tmp && env MESA_BASE="http://127.0.0.1:$P1" K106_ACTIVOS=BTC K106_OBSERVA=0 bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
"$PY" "$PLANTA" planta fraccion "$T/b" > /dev/null
corre; rc=$?
comprueba el_check_condena "$([ "$rc" = 1 ] && head -1 "$T/chk" | grep -q '^K106 · ROJO' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
# una mesa SIN la vista (los bytes de main@aa5ad6f, de antes de la campana): NO MEDIDO, nunca ROJO ni VERDE
"$PY" "$PLANTA" planta vivo "$T/b" > /dev/null
if git -C "$REPO" archive aa5ad6f static 2>/dev/null | tar -x -C "$T" 2>/dev/null && [ -r "$T/static/mesa.html" ]; then
  cp -a "$T/static/." "$T/b/sobre/"
  corre; rc=$?
  comprueba sin_la_vista_no_medido "$([ "$rc" = 2 ] && head -1 "$T/chk" | grep -q '^NO MEDIDO: FALTA DESPLEGAR' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-100)"
else
  comprueba sin_la_vista_no_medido 1 "no pude sacar static/ de aa5ad6f del historial"
fi
para

echo "== C4 · K102: DECIDE empujado fuera del pliegue por la cabecera"
k102() {  # dir del arbol que se sirve -> rc de K102 sobre el
  sed "s|^REPO = pathlib.Path(\"/srv/coinanalyze/repo\")|REPO = pathlib.Path(\"$1\")|" "$AQUI/K102-sobre-plantado.py" > "$T/k106-sobre-plantado.py"
  grep -q "REPO = pathlib.Path(\"$1\")" "$T/k106-sobre-plantado.py" || { echo 9; return; }
  "$PY" "$T/k106-sobre-plantado.py" --puerto "$P2" --lag 3 --tope 600 --bias LONG --dc 100 > "$T/plantado.log" 2>&1 &
  SERV=$!
  sleep 3
  MESA_BASE="http://127.0.0.1:$P2" K102_OBSERVA=4 K102_ACTIVOS=SOL bash "$AQUI/K102-decide-lo-primero.sh" > "$T/k102" 2>&1
  local rc=$?
  para
  echo $rc
}
mkdir -p "$T/k102arbol"; cp -a "$REPO/static" "$T/k102arbol/static"
rc=$(k102 "$T/k102arbol")
comprueba k102_el_arbol_pasa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/k102" | cut -c1-100)"
h1=$(sha256sum < "$T/k102arbol/static/mesa/mesa.css" | cut -c1-12)
printf '\n/* PLANTADO por K106-control: la cabecera crece con su enlace */\n.cabecera { height: auto; flex-wrap: wrap; }\n#ir-entradas { flex-basis: 100%%; height: 760px; }\n' >> "$T/k102arbol/static/mesa/mesa.css"
h2=$(sha256sum < "$T/k102arbol/static/mesa/mesa.css" | cut -c1-12)
rc=$(k102 "$T/k102arbol")
visto=$(grep -E '^   - B1 .*DECIDE NO cabe en el primer pliegue' "$T/k102" | head -1 | cut -c1-120)
comprueba k102_condena_la_cabecera "$([ "$rc" = 1 ] && [ -n "$visto" ] && [ "$h1" != "$h2" ] && echo 0 || echo 1)" "rc=$rc · mesa.css $h1 -> $h2 · ${visto:-NO SALE B1: $(head -1 "$T/k102" | cut -c1-90)}"

echo "== restaurado"
"$PY" "$PLANTA" planta vivo "$T/b" > "$T/fin"; fin=$(sed 's/.* //' "$T/fin")
comprueba escenario_restaurado "$([ "$fin" = "$HUELLA_BUENA" ] && echo 0 || echo 1)" "huella del escenario bueno $HUELLA_BUENA y al final $fin"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K106-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
