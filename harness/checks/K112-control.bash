#!/bin/bash
# K112-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA BRAZO DE K112 Y POR CADA DECISION DE LOS INDICADORES QUE SE
# PUEDE ROMPER (campana 146, C4).
#
# EL SUJETO BUENO ES DE VERDAD: la pagina del ARBOL servida por K112-banco.py sobre una base desechable k112_ctl_<pid>
# con K112-sujeto.tsv.xz (celdas, series de 5 min de Coinalyze, sueltas, grandes y cinta de PRODUCCION, bajados una vez)
# DESPLAZADO A AHORA al cargarlo: la vista del pasado de K112 cae en sus datos y el vivo recibe ordenes nuevas mientras
# corre. Sobre el, K112 tiene que salir VERDE. Cada plantado cambia LO SERVIDO (el banco lo tuerce despues de
# calcularlo), LA BASE (una copia con huecos) o LA PAGINA (un fichero en el --sobre del banco: el arbol no se toca, y
# cada `sed` tiene que MORDER exactamente las lineas esperadas o el plantado cuenta como fallido); K112 tiene que
# condenarlo POR SU BRAZO, con su frase y con la huella del escenario y la suya cambiadas; y el escenario vuelve:
#   (S) punto_servido_alterado    un cubo del OI de Binance servido +1 despues de calcularlo
#   (F) hueco_pintado_como_cero   un cubo sin dato pintado como un punto a 0 (la base con huecos)
#   (F) cvd_sin_reinicio          el CVD sigue sumando tras un hueco en vez de volver a 0 (la base con huecos)
#   (F) fuente_mal_escrita        la cabecera del OI dice «Binance + Bybit»
#   (F) grande_en_otra_vela       la marca de cada grande en la vela siguiente
#   (S) orden_mal_sumada          la primera orden agregada servida +1 USD
#   (G) panel_tapa_el_footprint   los paneles suben 240 px encima del footprint
#   (P) pide_otra_ventana         los indicadores pedidos desde la segunda vela, no desde la del footprint
#   (V) familias_sumadas          perpetuos y spot pedidos como una familia
#   (P) cinta_pide_todo           el vivo de la cinta vuelve a pedir la ultima hora en vez de solo lo nuevo
#   (F) fila_de_otra_cifra        la cinta escribe la cantidad en base donde va el tamano en USD
#   (F) escalon_desplazado        los escalones de 5 min una vela a la derecha de su hora
#   (P) pagina_rota               una excepcion al arrancar
# OF-6a (campana 148), los dos defectos del juez que encontro el ataque de la 146:
#   (F) unidad_mal_escrita        la cabecera del delta dice «en ETH» en la vista EN USD (P146-1)
#   (F) filtro_agrupado           el filtro de 4 cifras escrito «5.000» en vez de como la pagina, «5000» (P146-2)
#   V   k112_de_d91d935           el K112 de antes, con las vistas nuevas, contra la pagina buena: ROJO (el defecto era suyo)
# Y un escenario BUENO mas que tiene que salir VERDE: hueco_en_medio (la base con huecos y la pagina buena: los dice).
# NO MEDIDO, ni ROJO ni VERDE: sin_pagina y sujeto_anterior_a_of5a («FALTA DESPLEGAR») · sin_chromium · sin_dato ·
# sin_canal. Y el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones; el escenario restaurado; el arbol
# intacto.
#
# No usa produccion ni el espejo. Puertos 8113 y 8114 (se niega a arrancar si estan ocupados). Al salir: 0 bases,
# ningun banco suyo vivo, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K112-los-indicadores-pintados-son-los-servidos.sh"
BANCO="$AQUI/K112-banco.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$BANCO" "$AQUI/K112-indicadores.py" "$AQUI/K112-sujeto.tsv.xz" "$AQUI/K102-mesa.py" \
         "$AQUI/K109-footprint.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
exec 9>/tmp/k112-control.lock
flock -n 9 || { echo "K112-control: otro K112-control esta corriendo; no se pisan"; exit 2; }
PID=$$
DB="k112_ctl_${PID}"
P1=8113; P2=8114
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "control: el puerto $p esta ocupado (otro control u otro servidor): no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SERV1=""; SERV2=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  for s in $SERV1 $SERV2; do kill "$s" 2>/dev/null; wait "$s" 2>/dev/null; done
  SERV1=""; SERV2=""
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k112_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k112_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k112_ctl_${PID}%'")"
  echo "bancos del control vivos: $(ss -ltn 2>/dev/null | grep -cE ":($P1|$P2) ")"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-26s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-26s %s\n' "$1" "$3"; fi
}
dsn() { echo "postgresql:///$1?host=$H"; }
k112() {  # puerto base [env extra...] -> rc; la salida en $T/sal
  local p=$1 b=$2; shift 2
  env "$@" K112_BASE="http://127.0.0.1:$p" K112_DB="$(dsn "$b")" K112_HASTA="$HASTA" \
    /bin/bash "$CHK" > "$T/sal" 2>&1; echo $?
}
huella_k112() { head -1 "$T/sal" | grep -o 'huella [0-9a-f]*' | cut -d' ' -f2; }
escenario() {  # [base] -> lo que el banco sirve distinto del arbol, y el sujeto del que parte
  { sha256sum < "$AQUI/K112-sujeto.tsv.xz"; echo "base ${1:-buena}"
    find "$T/sobre" -type f | sort | xargs -r sha256sum; cat "$T/plantado" 2>/dev/null; } | sha256sum | cut -c1-12
}

echo "== el sujeto: el de produccion en tres bases (la buena, una con huecos, una vacia) y dos bancos del ARBOL"
for b in "$DB" "${DB}_hueco" "${DB}_vacia"; do
  createdb -h "$H" "$b" || exit 2
  "$PY" "$BANCO" carga "$(dsn "$b")" > "$T/carga" 2>&1 || { echo "control: la carga fallo: $(tail -1 "$T/carga")"; exit 2; }
done
HASTA=$(grep -o 'K112_HASTA=[^ ]*' "$T/carga" | cut -d= -f2)
[ -n "$HASTA" ] || { echo "control: la carga no dijo su K112_HASTA"; exit 2; }
# los huecos, en la vista de 1 h de BTC: dos puntos del OI de Binance (dos cubos de 5 min sin dato) y un minuto entero
# de los cuatro perpetuos (una vela HUECO: el delta lo dice y el CVD vuelve a 0)
psql -h "$H" -d "${DB}_hueco" -q -v ON_ERROR_STOP=1 \
  -c "DELETE FROM open_interest WHERE symbol='BTCUSDT_PERP.A' AND ts >= timestamptz '$HASTA' - interval '30 minutes' AND ts < timestamptz '$HASTA' - interval '20 minutes'" \
  -c "DELETE FROM orderflow_celda WHERE symbol='BTC' AND ts >= timestamptz '$HASTA' - interval '15 minutes' AND ts < timestamptz '$HASTA' - interval '14 minutes'" \
  -c "DELETE FROM orderflow_cobertura WHERE symbol='BTC' AND ts >= timestamptz '$HASTA' - interval '15 minutes' AND ts < timestamptz '$HASTA' - interval '14 minutes'" || exit 2
psql -h "$H" -d "${DB}_vacia" -qc "TRUNCATE open_interest" || exit 2
mkdir -p "$T/sobre/flujo"
: > "$T/plantado"
# las sueltas, con la retencion larga: su ventana no se mueve con el reloj y la huella de las vistas del pasado tampoco
SCALP_TRADE_RETENTION_HOURS=72 "$PY" "$BANCO" sirve --puerto "$P1" --db "$(dsn "$DB")" --sobre "$T/sobre" \
  --plantado "$T/plantado" > "$T/banco1.log" 2>&1 &
SERV1=$!
SCALP_TRADE_RETENTION_HOURS=72 "$PY" "$BANCO" sirve --puerto "$P2" --db "$(dsn "${DB}_hueco")" --sobre "$T/sobre" \
  --plantado "$T/plantado" > "$T/banco2.log" 2>&1 &
SERV2=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  [ "$(ss -ltn 2>/dev/null | grep -cE ":($P1|$P2) ")" = 2 ] && break
done
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " || { echo "control: el banco de $p no arranco: $(tail -1 "$T/banco1.log") $(tail -1 "$T/banco2.log")"; exit 2; }
done
BUENO=$(escenario)
rc=$(k112 $P1 "$DB"); HK_BUENA=$(huella_k112)
comprueba el_bueno_es_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K112' && echo 0 || echo 1)" \
  "rc=$rc · escenario $BUENO · $(head -1 "$T/sal" | cut -c1-60) · huella $HK_BUENA"
grep -E '^   · \((S|F)' "$T/sal" | cut -c1-170 | sed 's/^/        /'

echo "== los brazos: cada plantado, por el brazo que lo tiene que condenar"
planta_pagina() {  # fichero(en static/) patron-sed mordidas-esperadas -> 0 si mordio exactamente
  cp "$REPO/static/$1" "$T/sobre/$1"
  sed -i "$2" "$T/sobre/$1"
  [ "$(diff "$REPO/static/$1" "$T/sobre/$1" | grep -c '^>')" = "$3" ]
}
restaura() { rm -f "$T/sobre/flujo/"*; : > "$T/plantado"; }
juzga_plantado() {  # nombre brazo patron mordio(0/1) que [puerto] [base] [etiqueta de la base]
  local antes despues rc visto hk p=${6:-$P1} b=${7:-$DB}
  antes=$BUENO; despues=$(escenario "${8:-buena}")
  rc=$(k112 "$p" "$b"); hk=$(huella_k112)
  visto=$(grep -E "\\($2\\) .*($3)" "$T/sal" | head -1 | cut -c1-150)
  comprueba "$1" "$([ "$4" = 0 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && [ "$hk" != "$HK_BUENA" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $antes -> $despues · huella $hk · ${visto:-NO SALE ($2) $3: $(grep -m1 '^   · ' "$T/sal" | cut -c1-110)} · $5"
  restaura
}
juzga_bueno() {  # nombre patron-de-info que [puerto] [base] [etiqueta]
  local despues rc visto hk p=${4:-$P1} b=${5:-$DB}
  despues=$(escenario "${6:-buena}")
  rc=$(k112 "$p" "$b"); hk=$(huella_k112)
  visto=$(grep -E "$2" "$T/sal" | head -1 | cut -c1-150)
  comprueba "$1" "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K112' && [ -n "$visto" ] && [ "$BUENO" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $BUENO -> $despues · huella $hk · ${visto:-NO SALE: $2 · $(head -1 "$T/sal" | cut -c1-90)} · $3"
  restaura
}
echo serie > "$T/plantado"
juzga_plantado punto_servido_alterado S "oi_binance: los cubos servidos no son los de open_interest" 0 "un cubo del OI +1 despues de calcularlo"
planta_pagina flujo/flujo-indicadores.js "s/^    visibles(s)\.forEach((c) => {\$/    visibles(s).map((c) => (c.valores ? c : Object.assign({}, c, { valores: { [campo]: '0' } }))).forEach((c) => {/" 1; m=$?
juzga_plantado hueco_pintado_como_cero F "es HUECO .*se pinta 0: un hueco no es un cero" $m "un cubo sin dato pintado a 0" "$P2" "${DB}_hueco" hueco
planta_pagina flujo/flujo-indicadores.js 's/^      origen = null;$/      \/\/ plantado por K112-control: sin reinicio/' 1; m=$?
juzga_plantado cvd_sin_reinicio F "CVD .*tras un hueco vuelve a 0" $m "el CVD no vuelve a 0 tras el hueco" "$P2" "${DB}_hueco" hueco
planta_pagina flujo/flujo-indicadores.js "s/      return s(IND_SERIE\[clave\]\[0\])\.fuente + /      return 'interes abierto · Binance + Bybit (Coinalyze, cada 5 min)' + /" 1; m=$?
juzga_plantado fuente_mal_escrita F "oi: su cabecera dice .*Binance \+ Bybit" $m "la fuente del OI mal escrita"
planta_pagina flujo/flujo-indicadores.js 's/^    const i = Math\.floor((t - t0) \/ mMs);$/    const i = Math.floor((t - t0) \/ mMs) + 1;/' 1; m=$?
juzga_plantado grande_en_otra_vela F "grande .*(es de la vela|no pintada)" $m "cada grande en la vela siguiente"
echo orden > "$T/plantado"
juzga_plantado orden_mal_sumada S "la orden .*servida .* y sus operaciones suman" 0 "la primera orden +1 USD"
planta_pagina flujo/flujo.css 's/^  border-top: 0;$/  border-top: 0; margin-top: -240px; z-index: 5;/' 1; m=$?
juzga_plantado panel_tapa_el_footprint G "del footprint lo que hay encima es" $m "los paneles encima del footprint"
planta_pagina flujo/flujo-app.js 's/desde: MODELO\.velas\[0\]\.ts/desde: MODELO.velas[1].ts/' 1; m=$?
juzga_plantado pide_otra_ventana P "pide /api/orderflow/indicadores .* y la ventana del footprint es" $m "los indicadores de otra ventana"
planta_pagina flujo/flujo-calculo.js "s/'okx_swap', 'bitget_usdt'\] },/'okx_swap', 'bitget_usdt', 'binance_spot', 'bybit_spot', 'okx_spot'] },/" 1; m=$?
juzga_plantado familias_sumadas V "no es UNA familia, la perp" $m "perpetuos + spot en la familia perp"
planta_pagina flujo/flujo-cinta.js 's/ desde: CINTA\.hasta,//' 1; m=$?
juzga_plantado cinta_pide_todo P "el vivo de la cinta no pide SOLO lo nuevo" $m "el vivo vuelve a pedir la ultima hora"
planta_pagina flujo/flujo-cinta.js 's/cifraE04(o\.usd, 0),/cifraE04(o.base, 0),/' 1; m=$?
juzga_plantado fila_de_otra_cifra F "la fila 1 de la cinta escribe" $m "la cantidad en base donde va el tamano en USD"
planta_pagina flujo/flujo-indicadores.js 's/^  const xT = (ms) => g\.x(0) - g\.bs \/ 2 + ((ms - t0) \/ mMs) \* g\.bs;$/  const xT = (ms) => g.x(0) + g.bs \/ 2 + ((ms - t0) \/ mMs) * g.bs;/' 1; m=$?
juzga_plantado escalon_desplazado F "no esta en el eje de tiempo del footprint" $m "los escalones una vela a la derecha"
planta_pagina flujo/flujo-app.js 's/^function arranca() {$/function arranca() { throw new Error("plantado por K112-control");/' 1; m=$?
juzga_plantado pagina_rota P "lanzo 1 excepcion|no pinto su vista" $m "una excepcion al arrancar"
# OF-6a: los dos arreglos del juez, cada uno con su plantado
planta_pagina flujo/flujo-indicadores.js "s/  const ctxTit = { familia: FAMILIAS\[m\.familia\]\.rotulo, unidad: m\.unidad === 'usd' ? 'USD' : m\.activo,/  const ctxTit = { familia: FAMILIAS[m.familia].rotulo, unidad: m.activo,/" 1; m=$?
juzga_plantado unidad_mal_escrita F "delta: su cabecera dice .*en ETH" $m "la vista en USD con la cabecera en ETH"
planta_pagina flujo/flujo-cinta.js "s/Number(filtro)\.toLocaleString('es-ES')/Number(filtro).toLocaleString('de-DE')/" 1; m=$?
juzga_plantado filtro_agrupado F "la cinta dice .*5\.000 USD" $m "el filtro de 4 cifras con punto de miles"

echo "== V: el K112 de d91d935 (antes de arreglar P146-1 y P146-2) con las vistas nuevas, contra la pagina buena"
mkdir -p "$T/viejo/harness/checks"
git -C "$REPO" show d91d935:harness/checks/K112-indicadores.py > "$T/viejo/harness/checks/K112-indicadores.py" 2>/dev/null
cp "$AQUI/K102-mesa.py" "$AQUI/K109-footprint.py" "$T/viejo/harness/checks/"
sed -i -e 's|#ETH/15m/perp/hasta={h}/ver=96|#ETH/15m/perp/unidad=usd/hasta={h}/ver=96|' \
       -e 's|/cinta=20000", 1280|/cinta=5000", 1280|' "$T/viejo/harness/checks/K112-indicadores.py"
m=$([ "$(git -C "$REPO" show d91d935:harness/checks/K112-indicadores.py | diff - "$T/viejo/harness/checks/K112-indicadores.py" | grep -c '^>')" = 2 ] && echo 0 || echo 1)
rc=$(k112 $P1 "$DB" K112_REPO="$T/viejo" K112_PY="$PY")
visto=$(grep -E '^   · \(F\) .*(tiene que decir .*en ETH|tiene que decir .*5\.000 USD)' "$T/sal" | head -1 | cut -c1-150)
comprueba k112_de_d91d935 "$([ "$m" = 0 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && echo 0 || echo 1)" \
  "rc=$rc · sed $m · ${visto:-NO SALE: $(head -1 "$T/sal" | cut -c1-110)} · el juez viejo pide «en ETH» y «5.000»"
rm -rf "$T/viejo"

echo "== un escenario bueno mas: tiene que salir VERDE"
juzga_bueno hueco_en_medio '^   · \(F\)\(G\) \[BTC 1m perp 1920x1080\] .*\(([1-9][0-9]*) huecos\)' "la base con huecos y la pagina buena" "$P2" "${DB}_hueco" hueco

echo "== lo que no se puede medir: NO MEDIDO, ni ROJO ni VERDE"
echo sin_pagina > "$T/plantado"
rc=$(k112 $P1 "$DB")
comprueba sin_pagina "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR .*no sirve /flujo' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
echo sin_of5a > "$T/plantado"
rc=$(k112 $P1 "$DB")
comprueba sujeto_anterior_a_of5a "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR .*no sirve /api/orderflow/indicadores' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
restaura
mkdir -p "$T/vacio"
rc=$(k112 $P1 "$DB" PATH="$T/vacio")
comprueba sin_chromium "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin Chromium' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
rc=$(k112 $P1 "${DB}_vacia")
comprueba sin_dato "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin dato en la ventana' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
rc=$(k112 $P1 "${DB}_no_existe")
comprueba sin_canal "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO (CANAL)' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"

echo "== el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones"
ENV=(K112_BASE="http://127.0.0.1:$P1" "K112_DB=$(dsn "$DB")" "K112_HASTA=$HASTA")
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K112' && ! grep -qi 'broken pipe' "$T/chk" && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
done
(env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd "$REPO" && env "${ENV[@]}" bash harness/checks/K112-los-indicadores-pintados-son-los-servidos.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd /tmp && env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"

echo "== restaurado"
FIN=$(escenario)
rc=$(k112 $P1 "$DB"); HK_FIN=$(huella_k112)
comprueba escenario_restaurado "$([ "$FIN" = "$BUENO" ] && [ "$rc" = 0 ] && [ "$HK_FIN" = "$HK_BUENA" ] && echo 0 || echo 1)" \
  "escenario $BUENO -> $FIN · huella de K112 $HK_BUENA -> $HK_FIN · rc=$rc"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K112-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
