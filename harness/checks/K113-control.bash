#!/bin/bash
# K113-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA BRAZO DE K113 (campana 148, C5).
#
# EL SUJETO BUENO ES DE VERDAD: la pagina del ARBOL servida por K112-banco.py sobre una base desechable k113_ctl_<pid>
# con K112-sujeto.tsv.xz y K113-celdas.tsv.xz (celdas, series, grandes y cinta de PRODUCCION, bajadas una vez) DESPLAZADO
# A AHORA: el vivo recibe velas nuevas mientras corre y la vista del pasado cae en sus datos. Sobre el, K113 tiene que
# salir VERDE. Cada plantado cambia LA PAGINA (un fichero en el --sobre del banco: el arbol no se toca, y cada `sed`
# tiene que MORDER exactamente las lineas esperadas o el plantado cuenta como fallido); K113 tiene que condenarlo POR SU
# BRAZO, con su frase y con la huella del escenario y la suya cambiadas; y el escenario vuelve a ser el bueno:
#   (R) rueda_mueve_el_precio     la rueda acerca el PRECIO en vez del tiempo: el eje equivocado
#   (C) ficha_de_otra_celda       la ficha dice la celda del nivel de encima del cursor
#   (C) cruz_desplazada           la vertical de la cruz (y su hora) en la vela siguiente
#   (T) cifra_que_no_sale         la cifra pide 14 px de holgura en vez de 4: no sale aunque quepa
#   (T) cifra_que_sale_sin_sitio  el alto minimo de fila baja de 10 a 6 px: sale con filas de 9
#   (F) fila_de_resumen_ajena     la fila del delta escribe la compra
#   (P) arrastre_que_vuelve_a_pedir  cada gesto vuelve a cargar la vista: lo servido cambia por el raton
#   (R) seguir_que_no_para        con el seguimiento parado, una vela nueva mueve la vista igual
#   (E) comprador_verde           el comprador vuelve al verde de antes, que no pasa la deuteranopia
# NO MEDIDO, ni ROJO ni VERDE: sin_pagina (404) y pagina_anterior_a_of6a (la de main@d91d935): «FALTA DESPLEGAR» ·
# sin_chromium · sin_dato · sin_canal. Y el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones; el
# escenario restaurado; el arbol intacto.
#
# No usa produccion ni el espejo. Puertos 8115 y 8116 (se niega a arrancar si estan ocupados). Al salir: 0 bases,
# ningun banco suyo vivo, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K113-el-raton-y-el-aspecto.sh"
BANCO="$AQUI/K112-banco.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$BANCO" "$AQUI/K113-raton.py" "$AQUI/K113-celdas.tsv.xz" "$AQUI/K112-sujeto.tsv.xz" "$AQUI/K102-mesa.py" \
         "$AQUI/K109-footprint.py" "$AQUI/K112-indicadores.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
exec 9>/tmp/k113-control.lock
flock -n 9 || { echo "K113-control: otro K113-control esta corriendo; no se pisan"; exit 2; }
PID=$$
DB="k113_ctl_${PID}"
P1=8115; P2=8116
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "control: el puerto $p esta ocupado (otro control u otro servidor): no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SERV1=""; SERV2=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  for s in $SERV1 $SERV2; do kill "$s" 2>/dev/null; wait "$s" 2>/dev/null; done
  SERV1=""; SERV2=""
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k113_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k113_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k113_ctl_${PID}%'")"
  echo "bancos del control vivos: $(ss -ltn 2>/dev/null | grep -cE ":($P1|$P2) ")"
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
dsn() { echo "postgresql:///$1?host=$H"; }
k113() {  # puerto base [env extra...] -> rc; la salida en $T/sal
  local p=$1 b=$2; shift 2
  env "$@" K113_BASE="http://127.0.0.1:$p" K113_DB="$(dsn "$b")" K113_HASTA="$HASTA" \
    /bin/bash "$CHK" > "$T/sal" 2>&1; echo $?
}
huella_k113() { head -1 "$T/sal" | grep -o 'huella [0-9a-f]*' | cut -d' ' -f2; }
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
rc=$(k113 $P1 "$DB"); HK_BUENA=$(huella_k113)
comprueba el_bueno_es_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K113' && echo 0 || echo 1)" \
  "rc=$rc · escenario $BUENO · $(head -1 "$T/sal" | cut -c1-70) · huella $HK_BUENA"
grep -E '^   · ' "$T/sal" | cut -c1-170 | sed 's/^/        /'

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
  rc=$(k113 $P1 "$DB"); hk=$(huella_k113)
  visto=$(grep -E "^   · \\($2\\) .*($3)" "$T/sal" | head -1 | cut -c1-160)
  comprueba "$1" "$([ "$4" = 0 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && [ "$hk" != "$HK_BUENA" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $antes -> $despues · huella $hk · ${visto:-NO SALE ($2) $3: $(grep -m1 '^   · ' "$T/sal" | cut -c1-110)} · $5"
  restaura
}
planta_pagina flujo/flujo-dibujo.js 's/^    else zoomTiempo(f, p\.x);$/    else zoomPrecio(1 \/ f, p.y);/' 1; m=$?
juzga_plantado rueda_mueve_el_precio R "la rueda: ver" $m "la rueda acerca el precio, no el tiempo"
planta_pagina flujo/flujo-dibujo.js 's/pin\.niveles\.find((x) => Number(x\.nivel) === Number(b\.nivel))/pin.niveles.find((x) => Number(x.nivel) === Number(b.nivel) + Number(L.modelo.paso))/' 1; m=$?
juzga_plantado ficha_de_otra_celda C "la ficha dice" $m "la ficha de la celda de encima"
planta_pagina flujo/flujo-dibujo.js 's/const xv = Math\.round(dx + g\.x(b\.i)) + 0\.5;/const xv = Math.round(dx + g.x(b.i + 1)) + 0.5;/' 1; m=$?
juzga_plantado cruz_desplazada C "la etiqueta de hora de la cruz" $m "la vertical de la cruz en la vela siguiente"
planta_pagina flujo/flujo-dibujo.js 's/if (wv + 4 <= w \/ 2 \&\& wc + 4 <= w \/ 2) {/if (wv + 14 <= w \/ 2 \&\& wc + 14 <= w \/ 2) {/' 1; m=$?
juzga_plantado cifra_que_no_sale T "tiene que escribir" $m "14 px de holgura en vez de 4"
planta_pagina flujo/flujo-dibujo.js 's/^  FILA_TEXTO: 10,/  FILA_TEXTO: 6,/' 1; m=$?
juzga_plantado cifra_que_sale_sin_sitio T "con filas de .* px el lienzo escribe|tiene que escribir" $m "el alto minimo de fila, 6 px"
planta_pagina flujo/flujo-calculo.js 's/^  return { vol: v\.total, delta: v\.delta,/  return { vol: v.total, delta: v.compra,/' 1; m=$?
juzga_plantado fila_de_resumen_ajena F "la fila delta vale" $m "la fila del delta escribe la compra"
planta_pagina flujo/flujo-app.js "s/^  if (window\\.location\\.hash !== h) window\\.history\\.replaceState(null, '', h);\$/  if (window.location.hash !== h) window.history.replaceState(null, '', h); carga();/" 1; m=$?
juzga_plantado arrastre_que_vuelve_a_pedir P "la historia del footprint se pidio" $m "cada gesto vuelve a cargar la vista"
planta_pagina flujo/flujo-dibujo.js 's/^      if (L\.sigue) L\.fin = L\.modelo\.velas\.length - 1;$/      L.fin = L.modelo.velas.length - 1;/' 1; m=$?
juzga_plantado seguir_que_no_para R "con el seguimiento parado llego una vela nueva" $m "una vela nueva mueve la vista parada"
planta_pagina flujo/flujo.css 's/^  --comprador: #60a5fa;$/  --comprador: #3ecf8e;/' 1; m=$?
juzga_plantado comprador_verde E "E-02" $m "el comprador vuelve al verde de antes"

echo "== lo que no se puede medir: NO MEDIDO, ni ROJO ni VERDE"
echo sin_pagina > "$T/plantado"
rc=$(k113 $P1 "$DB")
comprueba sin_pagina "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR .*no sirve /flujo' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
restaura
for f in flujo.html flujo/flujo-app.js flujo/flujo-calculo.js flujo/flujo-dibujo.js flujo/flujo-capas.js flujo/flujo-tpo.js \
         flujo/flujo-indicadores.js flujo/flujo-cinta.js flujo/flujo.css; do
  git -C "$REPO" show "d91d935:static/$f" > "$T/sobre/$f" 2>/dev/null || echo "control: no pude leer static/$f de d91d935"
done
rc=$(k113 $P1 "$DB")
comprueba pagina_anterior_a_of6a "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR .*anterior a OF-6a' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
restaura
mkdir -p "$T/vacio"
rc=$(k113 $P1 "$DB" PATH="$T/vacio")
comprueba sin_chromium "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin Chromium' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
rc=$(k113 $P2 "${DB}_vacia")
comprueba sin_dato "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin dato en la ventana' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
rc=$(k113 $P1 "${DB}_no_existe")
comprueba sin_canal "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO (CANAL)' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"

echo "== el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones"
ENV=(K113_BASE="http://127.0.0.1:$P1" "K113_DB=$(dsn "$DB")" "K113_HASTA=$HASTA")
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K113' && ! grep -qi 'broken pipe' "$T/chk" && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
done
(env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd "$REPO" && env "${ENV[@]}" bash harness/checks/K113-el-raton-y-el-aspecto.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd /tmp && env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"

echo "== restaurado"
FIN=$(escenario)
rc=$(k113 $P1 "$DB"); HK_FIN=$(huella_k113)
comprueba escenario_restaurado "$([ "$FIN" = "$BUENO" ] && [ "$rc" = 0 ] && [ "$HK_FIN" = "$HK_BUENA" ] && echo 0 || echo 1)" \
  "escenario $BUENO -> $FIN · huella de K113 $HK_BUENA -> $HK_FIN · rc=$rc"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K113-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
