#!/bin/bash
# K114-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA GESTO, CADA CELDA Y CADA COLOR QUE K114 DICE MIRAR
#
# EL SUJETO BUENO ES DE VERDAD: la pagina del ARBOL servida por K111-banco.py sobre una base desechable k114_ctl_<pid>
# cargada con las fotos de produccion (K111-fotos.tsv.xz) y alimentada con los avisos REALES (K111-avisos.jsonl.xz).
# Sobre el, K114 tiene que salir VERDE. Cada plantado cambia UNA cosa de LA PAGINA, en un fichero del --sobre del banco
# (el arbol no se toca; cada `sed` tiene que morder exactamente una linea o el plantado no cuenta), y K114 tiene que
# salir ROJO por el brazo que lo mira, con la ultima linea de su condena a la vista. Al final, el bueno otra vez VERDE
# y el arbol intacto. Corre solo (flock), en su puerto 8141; tarda ~105 s por corrida, 15 corridas.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K114-el-raton-del-libro.sh"
BANCO="$AQUI/K111-banco.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
HASTA=2026-10-18T03:30:00Z
for f in "$CHK" "$BANCO" "$AQUI/K114-raton-libro.py" "$AQUI/K113-raton.py" "$AQUI/K111-libro.py" \
         "$AQUI/K111-fotos.tsv.xz" "$AQUI/K111-avisos.jsonl.xz" "$AQUI/K102-mesa.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
exec 9>/tmp/k114-control.lock
flock -n 9 || { echo "K114-control: otro K114-control esta corriendo; no se pisan"; exit 2; }
PID=$$
DB="k114_ctl_${PID}"
P=8141
ss -ltn 2>/dev/null | grep -q ":$P " && { echo "control: el puerto $P esta ocupado: no arranco"; exit 2; }
T=$(mktemp -d) || exit 2
SERV=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  [ -n "$SERV" ] && { kill "$SERV" 2>/dev/null; wait "$SERV" 2>/dev/null; }
  SERV=""
  psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$DB\" WITH (FORCE)" > /dev/null 2>&1
  echo "bases $DB que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname = '$DB'")"
  echo "banco del control vivo: $(ss -ltn 2>/dev/null | grep -c ":$P ")"
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
k114() {  # -> rc; la salida en $T/sal
  K114_BASE="http://127.0.0.1:$P" K111_DB="$(dsn "$DB")" K114_HASTA="$HASTA" K114_ETH=okx_swap \
    /bin/bash "$CHK" > "$T/sal" 2>&1; echo $?
}
GUARDA=${K114_CTL_GUARDA:-/tmp/k114-control-salidas}
rm -rf "$GUARDA"; mkdir -p "$GUARDA"
guarda() { cp "$T/sal" "$GUARDA/$1.sal"; }

echo "== el sujeto: las fotos de produccion en una base desechable y el banco del ARBOL en $P"
createdb -h "$H" "$DB" || exit 2
"$PY" "$BANCO" carga "$(dsn "$DB")" > "$T/carga" 2>&1 || { echo "control: la carga fallo: $(tail -1 "$T/carga")"; exit 2; }
mkdir -p "$T/sobre/libro"
: > "$T/plantado"
"$PY" "$BANCO" sirve --puerto "$P" --db "$(dsn "$DB")" --sobre "$T/sobre" --plantado "$T/plantado" \
  --avisos "$AQUI/K111-avisos.jsonl.xz" > "$T/banco.log" 2>&1 &
SERV=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do sleep 1; ss -ltn 2>/dev/null | grep -q ":$P " && break; done
ss -ltn 2>/dev/null | grep -q ":$P " || { echo "control: el banco no arranco: $(tail -1 "$T/banco.log")"; exit 2; }

rc=$(k114); guarda el_bueno_es_verde
comprueba el_bueno_es_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K114' && echo 0 || echo 1)" \
  "rc=$rc · $(head -1 "$T/sal" | cut -c1-200)"

planta() {  # fichero(en static/) patron-sed -> 0 si mordio exactamente una linea
  mkdir -p "$(dirname "$T/sobre/$1")"
  cp "$REPO/static/$1" "$T/sobre/$1"
  sed -i "$2" "$T/sobre/$1"
  [ "$(diff "$REPO/static/$1" "$T/sobre/$1" | grep -c '^>')" = 1 ]
}
restaura() { rm -f "$T/sobre/libro.html" "$T/sobre/libro/"*; }
juzga() {  # nombre brazo fichero patron-sed -> ROJO de K114 por ese brazo, con la ultima linea de su condena
  if ! planta "$3" "$4"; then comprueba "$1" 1 "el sed no mordio una linea exacta en $3"; restaura; return; fi
  rc=$(k114); guarda "$1"
  ult=$(grep -E "^  ROJO \($2\)" "$T/sal" | tail -1 | cut -c1-400)
  comprueba "$1" "$([ "$rc" = 1 ] && head -1 "$T/sal" | grep -q '^ROJO  K114' && [ -n "$ult" ] && echo 0 || echo 1)" \
    "rc=$rc · ${ult:-NO SALE ($2): $(head -2 "$T/sal" | tail -1 | cut -c1-300)}"
  restaura
}
M=libro/libro-mapa.js; A=libro/libro-app.js
echo "== trece plantados en la pagina"
juzga zoom_sin_ancla R $M 's|horizontal(ja - 1 + ((ancho - xa) \* L.ver) / ancho);|horizontal(L.fin);|'
juzga cruz_de_otra_fila C $M 's|k = Math.floor(e.hi + 1 - y / e.fila);|k = Math.floor(e.hi + 2 - y / e.fila);|'
juzga ficha_de_otra_columna C $M 's|const f = fichaDe(m, j, k,|const f = fichaDe(m, Math.max(0, j - 1), k,|'
juzga ficha_honda_sin_edad C $M 's|edad_s: edad|edad_s: null|'
juzga desconocido_como_cero C $M "s|    f.estado = 'desconocido';|    f.estado = 'foto'; f.compra = 0; f.venta = 0;|"
juzga sigue_tras_arrastre R $M 's|        if (a.h) horizontal(a.fin - (dx \* L.ver) / (L.W - MAPA.DERECHA));|        if (a.h) { horizontal(a.fin - (dx * L.ver) / (L.W - MAPA.DERECHA)); L.sigue = true; }|'
juzga recentra_en_ninguno R $M "s|if (V.recentra !== 'ninguno' \&\& kRef !== null|if (kRef !== null|"
juzga separador_siguiendo R $M 's|    if (!L.sigue) {|    if (true) {|'
juzga menu_sin_efecto R $A 's|    EL_MAPA.recentra(r.value, true);|    void 0;|'
juzga ayuda_miente A libro.html 's|<b>Inicio</b>: la primera|<b>Alt + rueda</b>: gira el mapa · <b>Inicio</b>: la primera|'
juzga escalera_desincronizada C $A 's|LA_ESCALERA.resalta(f ? f.nivel : null)|LA_ESCALERA.resalta(f ? f.nivel + 1 : null)|'
juzga gesto_que_pide P $M "s|  L.cv.addEventListener('wheel', (ev) => {|  L.cv.addEventListener('wheel', (ev) => { fetch('/api/libro/fotos?k114=1').catch(() => {});|"
juzga comprador_distinto E $M "s|compra: '#60a5fa'|compra: '#4f8fe8'|"

echo "== restaurado"
rc=$(k114); guarda escenario_restaurado
comprueba el_bueno_otra_vez "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K114' && echo 0 || echo 1)" \
  "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K114-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
