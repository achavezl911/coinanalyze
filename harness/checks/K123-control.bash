#!/bin/bash
# K123-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA BRAZO DE K123 (campana OF-6b).
#
# EL SUJETO BUENO ES DE VERDAD: la pagina del ARBOL servida por K123-banco.py (que envuelve K112-banco.py, con las
# cabeceras de app/api.py) sobre una base desechable k123_ctl_<pid> con K112-sujeto.tsv.xz y K113-celdas.tsv.xz
# desplazados a ahora. Sobre el, K123 tiene que salir VERDE. Cada plantado cambia LA PAGINA (un fichero en el --sobre:
# el arbol no se toca, y cada `sed` tiene que MORDER exactamente las lineas esperadas o el plantado cuenta como fallido)
# o EL BANCO (--plantado); K123 tiene que condenarlo POR SU BRAZO, con su frase y con la huella del escenario y la suya
# cambiadas; y el escenario vuelve a ser el bueno:
#   (T) sin_oyente_storage      flujo-trazos.js sin `window.addEventListener('storage', ...)`: el nivel no llega
#   (T) fusion_sin_lapidas      la fusion no mira las lapidas: lo borrado en BTC 5m vuelve
#   (R) hash_sin_marco          /espacio escribe las vistas sin el marco temporal: al recargar vuelven en el de omision
#   (M) teclado_a_todos         /espacio reparte cada tecla de un marco a los demas: Fin mueve los cuatro
#   (C) banco_enmarca_mesa      el banco sirve /mesa con frame-ancestors 'self' + SAMEORIGIN
# NO MEDIDO, ni ROJO ni VERDE: sin_espacio (404, «FALTA DESPLEGAR») · sin_chromium · sin_canal. Y el check: A89 los dos
# modos de SIGPIPE, A56 las tres invocaciones; el escenario restaurado; el arbol intacto.
#
# No usa produccion ni el espejo. Puertos 8151 y 8152 (se niega a arrancar si estan ocupados). Al salir: 0 bases,
# ningun banco suyo vivo, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K123-el-espacio-de-varios-graficos.sh"
CARGA="$AQUI/K112-banco.py"
BANCO="$AQUI/K123-banco.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$CARGA" "$BANCO" "$AQUI/K123-espacio.py" "$AQUI/K113-raton.py" "$AQUI/K113-celdas.tsv.xz" \
         "$AQUI/K112-sujeto.tsv.xz" "$AQUI/K102-mesa.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
exec 9>/tmp/k123-control.lock
flock -n 9 || { echo "K123-control: otro K123-control esta corriendo; no se pisan"; exit 2; }
PID=$$
DB="k123_ctl_${PID}"
P1=8151; P2=8152
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "control: el puerto $p esta ocupado (otro control u otro servidor): no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SERV1=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  for s in $SERV1; do kill "$s" 2>/dev/null; wait "$s" 2>/dev/null; done
  SERV1=""
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k123_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k123_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k123_ctl_${PID}%'")"
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
k123() {  # puerto [env extra...] -> rc; la salida en $T/sal
  local p=$1; shift
  env "$@" K123_BASE="http://127.0.0.1:$p" K123_HASTA="$HASTA" K123_REPO="$REPO" /bin/bash "$CHK" > "$T/sal" 2>&1; echo $?
}
huella_k123() { head -1 "$T/sal" | grep -o 'huella [0-9a-f]*' | cut -d' ' -f2; }
escenario() {  # lo que el banco sirve distinto del arbol, y el sujeto del que parte
  { sha256sum < "$AQUI/K112-sujeto.tsv.xz"; sha256sum < "$AQUI/K113-celdas.tsv.xz"
    find "$T/sobre" -type f | sort | xargs -r sha256sum; cat "$T/plantado" 2>/dev/null; } | sha256sum | cut -c1-12
}

echo "== el sujeto: el de produccion en una base desechable y un banco del ARBOL con las cabeceras de app/api.py"
createdb -h "$H" "$DB" || exit 2
"$PY" "$CARGA" carga "$(dsn "$DB")" --mas "$AQUI/K113-celdas.tsv.xz" > "$T/carga" 2>&1 \
  || { echo "control: la carga fallo: $(tail -1 "$T/carga")"; exit 2; }
HASTA=$(grep -o 'K112_HASTA=[^ ]*' "$T/carga" | cut -d= -f2)
[ -n "$HASTA" ] || { echo "control: la carga no dijo su K112_HASTA"; exit 2; }
mkdir -p "$T/sobre/flujo" "$T/sobre/espacio"
: > "$T/plantado"
SCALP_TRADE_RETENTION_HOURS=72 "$PY" "$BANCO" sirve --puerto "$P1" --db "$(dsn "$DB")" --sobre "$T/sobre" \
  --plantado "$T/plantado" > "$T/banco1.log" 2>&1 &
SERV1=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  ss -ltn 2>/dev/null | grep -q ":$P1 " && break
done
ss -ltn 2>/dev/null | grep -q ":$P1 " || { echo "control: el banco de $P1 no arranco: $(tail -1 "$T/banco1.log")"; exit 2; }
BUENO=$(escenario)
rc=$(k123 $P1); HK_BUENA=$(huella_k123)
comprueba el_bueno_es_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K123' && echo 0 || echo 1)" \
  "rc=$rc · escenario $BUENO · $(head -1 "$T/sal" | cut -c1-110) · huella $HK_BUENA"
grep -E '^   · ' "$T/sal" | cut -c1-400 | sed 's/^/        /'

echo "== los brazos: cada plantado, por el brazo que lo tiene que condenar"
planta_pagina() {  # fichero(en static/) patron-sed lineas-cambiadas-esperadas -> 0 si mordio exactamente
  cp "$REPO/static/$1" "$T/sobre/$1"
  sed -i "$2" "$T/sobre/$1"
  [ "$(diff "$REPO/static/$1" "$T/sobre/$1" | grep -c '^[<>]')" = "$3" ]
}
restaura() { rm -rf "$T/sobre/"*; mkdir -p "$T/sobre/flujo" "$T/sobre/espacio"; : > "$T/plantado"; }
juzga_plantado() {  # nombre brazo patron mordio(0/1) que
  local antes despues rc visto hk
  antes=$BUENO; despues=$(escenario)
  rc=$(k123 $P1); hk=$(huella_k123)
  visto=$(grep -m1 -E "^   · \\($2\\) .*($3)" "$T/sal" | cut -c1-300)
  comprueba "$1" "$([ "$4" = 0 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && [ "$hk" != "$HK_BUENA" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $antes -> $despues · huella $hk · ${visto:-NO SALE ($2) $3: $(head -1 "$T/sal" | cut -c1-200) $(grep -m1 '^   · ' "$T/sal" | cut -c1-200)} · $5"
  restaura
}
TRZ=flujo/flujo-trazos.js
ESP=espacio/espacio.js
planta_pagina $TRZ "/^  window\\.addEventListener('storage', oyeGuardado);\$/d" 1; m=$?
juzga_plantado sin_oyente_storage T "el nivel puesto en BTC 1m no sale en BTC 5m" $m "sin el oyente de storage"
planta_pagina $TRZ 's/^    \.filter((z) => !(z\.id in lapidas) || lapidas\[z\.id\] < z\.m)$/    .filter(() => true)/' 2; m=$?
juzga_plantado fusion_sin_lapidas T "el nivel borrado en BTC 5m (sigue|volvio) en" $m "la fusion sin lapidas"
planta_pagina $ESP '/vs\.push(/s@\.replace(/^#/, @.replace(/\\/(1m|5m|15m|1h|4h|1d)\\//, String.fromCharCode(47)).replace(/^#/, @' 2; m=$?
juzga_plantado hash_sin_marco R "tras recargar el marco [0-9] volvio con" $m "/espacio pierde el marco temporal al recargar"
planta_pagina $ESP "/^    f\\.src = srcMarco(ESP\\.todas\\[i\\]);\$/a\\    f.addEventListener('load', () => f.contentWindow.addEventListener('keydown', (ev) => ev.isTrusted \\&\\& ESP.marcos.forEach((o) => o !== f \\&\\& o.contentDocument.dispatchEvent(new KeyboardEvent('keydown', { key: ev.key, code: ev.code, bubbles: true })))));" 1; m=$?
juzga_plantado teclado_a_todos M "Fin en BTC 5m cambio el marco" $m "el teclado repartido a todos los marcos"
echo enmarca_mesa > "$T/plantado"
juzga_plantado banco_enmarca_mesa C "/mesa \\(200\\) da «frame-ancestors 'self'»" 0 "el banco deja enmarcar /mesa"

echo "== lo que no se puede medir: NO MEDIDO, ni ROJO ni VERDE"
echo sin_espacio > "$T/plantado"
rc=$(k123 $P1)
comprueba sin_espacio "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR .*no sirve /espacio (404)' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-140)"
restaura
mkdir -p "$T/vacio"
rc=$(k123 $P1 PATH="$T/vacio")
comprueba sin_chromium "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin Chromium' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
rc=$(k123 $P2)
comprueba sin_canal "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO (CANAL)' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"

echo "== el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones"
ENV=(K123_BASE="http://127.0.0.1:$P1" "K123_HASTA=$HASTA" "K123_REPO=$REPO")
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K123' && ! grep -qi 'broken pipe' "$T/chk" && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"
done
(env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"
(cd "$REPO" && env "${ENV[@]}" bash harness/checks/K123-el-espacio-de-varios-graficos.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"
(cd /tmp && env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80) $(grep -m1 '^   · (' "$T/chk" | cut -c1-400)"

echo "== restaurado"
FIN=$(escenario)
rc=$(k123 $P1); HK_FIN=$(huella_k123)
comprueba escenario_restaurado "$([ "$FIN" = "$BUENO" ] && [ "$rc" = 0 ] && [ "$HK_FIN" = "$HK_BUENA" ] && echo 0 || echo 1)" \
  "escenario $BUENO -> $FIN · huella de K123 $HK_BUENA -> $HK_FIN · rc=$rc $(grep -m1 '^   · (' "$T/sal" | cut -c1-400)"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K123-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
