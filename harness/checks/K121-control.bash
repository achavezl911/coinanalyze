#!/bin/bash
# K121-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA BRAZO DE K121 (campana 146-D).
#
# EL SUJETO BUENO ES DE VERDAD: la pagina del ARBOL servida por K112-banco.py (--sobre, como K113-control) sobre una
# base desechable k121_ctl_<pid> con K112-sujeto.tsv.xz y K113-celdas.tsv.xz desplazados a ahora. Sobre el, K121 tiene
# que salir VERDE. Cada plantado cambia LA PAGINA (un fichero en el --sobre: el arbol no se toca, y cada `sed` tiene que
# MORDER exactamente las lineas esperadas o el plantado cuenta como fallido); K121 tiene que condenarlo POR SU BRAZO,
# con su frase y con la huella del escenario y la suya cambiadas; y el escenario vuelve a ser el bueno:
#   (X) x_por_indice           la x de un instante es (t - t0) / marco: tras la vela que falta, todo una vela a la derecha
#   (F) fib_0650               la razon 0.618 pasa a 0.65
#   (C) sigma_n_menos_1        sigma con n - 1 (la muestral) en vez de n
#   (G) guardado_por_marco     lo guardado va por activo Y marco: en 5m no esta lo puesto en 1m
#   (H) gesto_sin_herramienta  sin herramienta, un clic pone un nivel (y el grafico no se arrastra)
#   (K) punto_12px_a_la_derecha cada punto se guarda 12 px a la derecha de su clic (`G.t(p.x + 12)`)
# NO MEDIDO, ni ROJO ni VERDE: sin_pagina (404) y pagina_sin_trazos (el flujo.html de main@1767616, que no carga
# flujo-trazos.js): «FALTA DESPLEGAR» · sin_chromium · sin_dato · sin_canal. Y el check: A89 los dos modos de SIGPIPE,
# A56 las tres invocaciones; el escenario restaurado; el arbol intacto.
#
# No usa produccion ni el espejo. Puertos 8131 y 8132 (se niega a arrancar si estan ocupados). Al salir: 0 bases,
# ningun banco suyo vivo, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K121-los-trazos-donde-se-pusieron.sh"
BANCO="$AQUI/K112-banco.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$BANCO" "$AQUI/K121-trazos.py" "$AQUI/K113-raton.py" "$AQUI/K113-celdas.tsv.xz" "$AQUI/K112-sujeto.tsv.xz" \
         "$AQUI/K102-mesa.py" "$AQUI/K112-indicadores.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
exec 9>/tmp/k121-control.lock
flock -n 9 || { echo "K121-control: otro K121-control esta corriendo; no se pisan"; exit 2; }
PID=$$
DB="k121_ctl_${PID}"
P1=8131; P2=8132
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "control: el puerto $p esta ocupado (otro control u otro servidor): no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SERV1=""; SERV2=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  for s in $SERV1 $SERV2; do kill "$s" 2>/dev/null; wait "$s" 2>/dev/null; done
  SERV1=""; SERV2=""
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k121_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k121_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k121_ctl_${PID}%'")"
  echo "bancos del control vivos: $(ss -ltn 2>/dev/null | grep -cE ":($P1|$P2) ")"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-24s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-24s %s\n' "$1" "$3"; fi
}
dsn() { echo "postgresql:///$1?host=$H"; }
k121() {  # puerto base [env extra...] -> rc; la salida en $T/sal
  local p=$1 b=$2; shift 2
  env "$@" K121_BASE="http://127.0.0.1:$p" K121_DB="$(dsn "$b")" K121_HASTA="$HASTA" \
    /bin/bash "$CHK" > "$T/sal" 2>&1; echo $?
}
huella_k121() { head -1 "$T/sal" | grep -o 'huella [0-9a-f]*' | cut -d' ' -f2; }
escenario() {  # lo que el banco sirve distinto del arbol, y el sujeto del que parte
  { sha256sum < "$AQUI/K112-sujeto.tsv.xz"; sha256sum < "$AQUI/K113-celdas.tsv.xz"
    find "$T/sobre" -type f | sort | xargs -r sha256sum; cat "$T/plantado" 2>/dev/null; } | sha256sum | cut -c1-12
}

echo "== el sujeto: el de produccion en dos bases (la buena y una sin celdas) y un banco del ARBOL"
for b in "$DB" "${DB}_vacia"; do
  createdb -h "$H" "$b" || exit 2
  "$PY" "$BANCO" carga "$(dsn "$b")" --mas "$AQUI/K113-celdas.tsv.xz" > "$T/carga" 2>&1 \
    || { echo "control: la carga fallo: $(tail -1 "$T/carga")"; exit 2; }
done
HASTA=$(grep -o 'K112_HASTA=[^ ]*' "$T/carga" | cut -d= -f2)
[ -n "$HASTA" ] || { echo "control: la carga no dijo su K112_HASTA"; exit 2; }
psql -h "$H" -d "${DB}_vacia" -qc "TRUNCATE orderflow_celda, orderflow_cobertura" || exit 2
mkdir -p "$T/sobre/flujo"
: > "$T/plantado"
SCALP_TRADE_RETENTION_HOURS=72 "$PY" "$BANCO" sirve --puerto "$P1" --db "$(dsn "$DB")" --sobre "$T/sobre" \
  --plantado "$T/plantado" > "$T/banco1.log" 2>&1 &
SERV1=$!
SCALP_TRADE_RETENTION_HOURS=72 "$PY" "$BANCO" sirve --puerto "$P2" --db "$(dsn "${DB}_vacia")" > "$T/banco2.log" 2>&1 &
SERV2=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  [ "$(ss -ltn 2>/dev/null | grep -cE ":($P1|$P2) ")" = 2 ] && break
done
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " || { echo "control: el banco de $p no arranco: $(tail -1 "$T/banco1.log")"; exit 2; }
done
BUENO=$(escenario)
rc=$(k121 $P1 "$DB"); HK_BUENA=$(huella_k121)
comprueba el_bueno_es_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K121' && echo 0 || echo 1)" \
  "rc=$rc · escenario $BUENO · $(head -1 "$T/sal" | cut -c1-110) · huella $HK_BUENA"
grep -E '^   · ' "$T/sal" | cut -c1-300 | sed 's/^/        /'

echo "== los brazos: cada plantado, por el brazo que lo tiene que condenar"
planta_pagina() {  # fichero(en static/) patron-sed mordidas-esperadas -> 0 si mordio exactamente
  cp "$REPO/static/$1" "$T/sobre/$1"
  sed -i "$2" "$T/sobre/$1"
  [ "$(diff "$REPO/static/$1" "$T/sobre/$1" | grep -c '^>')" = "$3" ]
}
restaura() { rm -rf "$T/sobre/"*; mkdir -p "$T/sobre/flujo"; : > "$T/plantado"; }
juzga_plantado() {  # nombre brazo patron mordio(0/1) que
  local antes despues rc visto hk
  antes=$BUENO; despues=$(escenario)
  rc=$(k121 $P1 "$DB"); hk=$(huella_k121)
  visto=$(grep -m1 -E "^   · \\($2\\) .*($3)" "$T/sal" | cut -c1-300)
  comprueba "$1" "$([ "$4" = 0 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && [ "$hk" != "$HK_BUENA" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $antes -> $despues · huella $hk · ${visto:-NO SALE ($2) $3: $(head -1 "$T/sal" | cut -c1-200) $(grep -m1 '^   · ' "$T/sal" | cut -c1-200)} · $5"
  restaura
}
TRZ=flujo/flujo-trazos.js
planta_pagina $TRZ 's/^  const izq = (i) => x0 + (i - 0\.5) \* bs;$/&\n  return izq(0) + ((t - ts[0]) \/ marcoMs) * bs;/' 1; m=$?
juzga_plantado x_por_indice X "el punto [0-9] esta en" $m "la x por indice desde la primera vela"
planta_pagina $TRZ 's/^const RAZONES_FIB = \[0, 0\.236, 0\.382, 0\.5, 0\.618, 0\.786, 1\];$/const RAZONES_FIB = [0, 0.236, 0.382, 0.5, 0.65, 0.786, 1];/' 1; m=$?
juzga_plantado fib_0650 F "las razones son .*0\\.65|falta la linea de 0\\.618" $m "0.618 pasa a 0.65"
planta_pagina $TRZ 's/sigma: Math\.sqrt(ss \/ n), n }/sigma: Math.sqrt(ss \/ (n - 1)), n }/' 1; m=$?
juzga_plantado sigma_n_menos_1 C ": sigma [0-9]" $m "sigma con n - 1"
planta_pagina $TRZ "s/^  if (TRZ\\.activo !== m\\.activo) cargaTrazos(m\\.activo);\$/  if (TRZ.activo !== m.activo + '\\/' + m.marco) cargaTrazos(m.activo + '\\/' + m.marco);/" 1; m=$?
juzga_plantado guardado_por_marco G "tras cambiar a 5m: habia 4 trazos y hay 0" $m "lo guardado por activo y marco"
planta_pagina $TRZ 's/^  if (TRZ\.herramienta) {$/  if (true) {/; s/^    const h = TRZ\.herramienta;$/    const h = TRZ.herramienta || '"'nivel'"';/' 2; m=$?
juzga_plantado gesto_sin_herramienta H "un gesto sin herramienta puso" $m "sin herramienta, un clic pone un nivel"
planta_pagina $TRZ 's/^  const punto = { t: G\.t(p\.x), p: G\.p(p\.y) };$/  const punto = { t: G.t(p.x + 12), p: G.p(p.y) };/' 1; m=$?
juzga_plantado punto_12px_a_la_derecha K "el clic [0-9] fue en" $m "cada punto 12 px a la derecha de su clic"

echo "== lo que no se puede medir: NO MEDIDO, ni ROJO ni VERDE"
echo sin_pagina > "$T/plantado"
rc=$(k121 $P1 "$DB")
comprueba sin_pagina "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR .*no sirve los trazos (/flujo 404' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-140)"
restaura
git -C "$REPO" show "1767616:static/flujo.html" > "$T/sobre/flujo.html" 2>/dev/null || echo "control: no pude leer static/flujo.html de 1767616"
rc=$(k121 $P1 "$DB")
comprueba pagina_sin_trazos "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR .*no publica FLUJO_PINTADO.trazos' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-140)"
restaura
mkdir -p "$T/vacio"
rc=$(k121 $P1 "$DB" PATH="$T/vacio")
comprueba sin_chromium "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin Chromium' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
rc=$(k121 $P2 "${DB}_vacia")
comprueba sin_dato "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin dato' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
rc=$(k121 $P1 "${DB}_no_existe")
comprueba sin_canal "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO (CANAL)' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"

echo "== el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones"
ENV=(K121_BASE="http://127.0.0.1:$P1" "K121_DB=$(dsn "$DB")" "K121_HASTA=$HASTA")
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K121' && ! grep -qi 'broken pipe' "$T/chk" && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"
done
(env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"
(cd "$REPO" && env "${ENV[@]}" bash harness/checks/K121-los-trazos-donde-se-pusieron.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"
(cd /tmp && env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"

echo "== restaurado"
FIN=$(escenario)
rc=$(k121 $P1 "$DB"); HK_FIN=$(huella_k121)
comprueba escenario_restaurado "$([ "$FIN" = "$BUENO" ] && [ "$rc" = 0 ] && [ "$HK_FIN" = "$HK_BUENA" ] && echo 0 || echo 1)" \
  "escenario $BUENO -> $FIN · huella de K121 $HK_BUENA -> $HK_FIN · rc=$rc $(grep -m1 '^   · (' "$T/sal" | cut -c1-400)"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K121-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
