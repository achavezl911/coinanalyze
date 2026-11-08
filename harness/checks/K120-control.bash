#!/bin/bash
# K120-control · que K120 condena cada manera concreta de pintar mal las liquidaciones, y aprueba la buena (campana 150).
#
# EL SUJETO BUENO ES DE VERDAD: las paginas del ARBOL servidas sobre dos bases desechables k120_ctl_{f,l}_<pid>:
#   /flujo  K112-banco.py carga + K120-banco.py siembra flujo <K112_HASTA>, servido por K112-banco.py sirve (puerto 8120)
#   /libro  K111-banco.py carga + K120-banco.py siembra libro 2026-10-18T04:00:00Z, servido por K120-banco.py libro (8121)
# Cada plantado cambia UNA linea de una copia de static/ (--sobre) o el fichero --plantado, y K120 tiene que salir ROJO por
# su brazo con la ultima linea de su condena; la base VERDE antes y despues; el arbol intacto. El brazo de 140 (D) no entra
# (K120_SIN_PROD=1): es de produccion y aqui el sujeto es el banco. Corre solo (flock); salidas en $K120_CTL_GUARDA.
# K120_CTL_SOLO=base: solo el sujeto bueno (para desarrollar).
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K120-las-liquidaciones-en-el-precio.sh"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
HL=2026-10-18T04:00:00Z
for f in "$CHK" "$AQUI/K120-liq.py" "$AQUI/K120-banco.py" "$AQUI/K112-banco.py" "$AQUI/K111-banco.py" "$AQUI/K114-raton-libro.py" \
         "$AQUI/K113-raton.py" "$AQUI/K111-libro.py" "$AQUI/K102-mesa.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
exec 9>/tmp/k120-control.lock
flock -n 9 || { echo "K120-control: otro K120-control esta corriendo; no se pisan"; exit 2; }
PID=$$
DBF="k120_ctl_f_${PID}"; DBL="k120_ctl_l_${PID}"
PF=8120; PL=8121
for P in $PF $PL; do
  ss -ltn 2>/dev/null | grep -q ":$P " && { echo "control: el puerto $P esta ocupado: no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SF=""; SL=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  for s in $SF $SL; do kill "$s" 2>/dev/null; wait "$s" 2>/dev/null; done
  SF=""; SL=""
  for d in "$DBF" "$DBL"; do psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$d\" WITH (FORCE)" > /dev/null 2>&1; done
  echo "bases k120_ctl_*_$PID que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname IN ('$DBF', '$DBL')")"
  echo "bancos del control vivos: $(ss -ltn 2>/dev/null | grep -c ":$PF \|:$PL ")"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-22s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-22s %s\n' "$1" "$3"; fi
}
dsn() { echo "postgresql:///$1?host=$H"; }
GUARDA=${K120_CTL_GUARDA:-/tmp/k120-control-salidas}
rm -rf "$GUARDA"; mkdir -p "$GUARDA"
k120() {  # nombre -> rc; la salida en $T/sal y en $GUARDA/nombre.sal
  K120_FLUJO="http://127.0.0.1:$PF" K120_LIBRO="http://127.0.0.1:$PL" K120_FLUJO_HASTA="$HF" K120_LIBRO_HASTA="$HL" \
    K120_FLUJO_DB="$(dsn "$DBF")" K120_LIBRO_DB="$(dsn "$DBL")" K120_SIN_PROD=1 /bin/bash "$CHK" > "$T/sal" 2>&1
  local rc=$?
  cp "$T/sal" "$GUARDA/$1.sal"
  echo $rc
}
espera() {  # puerto log
  for _ in $(seq 1 30); do sleep 1; ss -ltn 2>/dev/null | grep -q ":$1 " && return 0; done
  echo "control: el banco de $1 no arranco: $(tail -1 "$2")"; exit 2
}

echo "== el sujeto: dos bases desechables sembradas y los bancos del ARBOL en $PF (/flujo) y $PL (/libro)"
createdb -h "$H" "$DBF" || exit 2
createdb -h "$H" "$DBL" || exit 2
"$PY" "$AQUI/K112-banco.py" carga "$(dsn "$DBF")" > "$T/carga_f" 2>&1 || { echo "control: carga flujo: $(tail -1 "$T/carga_f")"; exit 2; }
HF=$(grep -o 'K112_HASTA=[^ ]*' "$T/carga_f" | head -1 | cut -d= -f2)
[ -n "$HF" ] || { echo "control: la carga de flujo no dio K112_HASTA"; exit 2; }
"$PY" "$AQUI/K111-banco.py" carga "$(dsn "$DBL")" > "$T/carga_l" 2>&1 || { echo "control: carga libro: $(tail -1 "$T/carga_l")"; exit 2; }
"$PY" "$AQUI/K120-banco.py" siembra "$(dsn "$DBF")" "$HF" flujo || exit 2
"$PY" "$AQUI/K120-banco.py" siembra "$(dsn "$DBL")" "$HL" libro || exit 2
mkdir -p "$T/sobre/flujo" "$T/sobre/libro"
: > "$T/plantado"
"$PY" "$AQUI/K112-banco.py" sirve --puerto "$PF" --db "$(dsn "$DBF")" --sobre "$T/sobre" --plantado "$T/plantado" > "$T/bf.log" 2>&1 &
SF=$!
"$PY" "$AQUI/K120-banco.py" libro --puerto "$PL" --db "$(dsn "$DBL")" --sobre "$T/sobre" --plantado "$T/plantado" > "$T/bl.log" 2>&1 &
SL=$!
espera $PF "$T/bf.log"; espera $PL "$T/bl.log"

base() {  # nombre
  rc=$(k120 "$1")
  comprueba "$1" "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K120' && echo 0 || echo 1)" \
    "rc=$rc · $(head -1 "$T/sal" | cut -c1-400) $(sed -n 2p "$T/sal" | cut -c1-300)"
}
base el_bueno_es_verde
[ "${K120_CTL_SOLO:-}" = base ] && { echo; echo "K120-control (solo base): $pasan de $total"; [ "$pasan" = "$total" ]; exit $?; }

restaura() { rm -f "$T/sobre/flujo/"* "$T/sobre/libro/"*; : > "$T/plantado"; }
planta() {  # fichero(en static/) patron-sed -> 0 si mordio exactamente una linea
  cp "$REPO/static/$1" "$T/sobre/$1"
  sed -i "$2" "$T/sobre/$1"
  [ "$(diff "$REPO/static/$1" "$T/sobre/$1" | grep -c '^>')" = 1 ]
}
condena() {  # nombre brazo -> ROJO por ese brazo con la ultima linea de su condena
  rc=$(k120 "$1")
  ult=$(grep -E "^  ROJO \($2\)" "$T/sal" | tail -1 | cut -c1-400)
  comprueba "$1" "$([ "$rc" = 1 ] && head -1 "$T/sal" | grep -q '^ROJO  K120' && [ -n "$ult" ] && echo 0 || echo 1)" \
    "rc=$rc · ${ult:-NO SALE ($2): $(head -2 "$T/sal" | tail -1 | cut -c1-300)}"
  restaura
}
juzga() {  # nombre brazo fichero patron-sed
  if ! planta "$3" "$4"; then comprueba "$1" 1 "el sed no mordio una linea exacta en $3"; restaura; return; fi
  condena "$1" "$2"
}
I=flujo/flujo-indicadores.js; L=flujo/flujo-liq.js
echo "== once plantados"
juzga lado_cambiado X $I "s|const c = e.lado === 'long' ? COLOR.venta : COLOR.compra;|const c = e.lado === 'long' ? COLOR.compra : COLOR.venta;|"
juzga precio_de_la_vela X $I 's|const yy = y(e.ejecucion);|const yy = y(Number(m.velas[Math.min(m.velas.length - 1, Math.max(0, i))].cierre \|\| e.ejecucion * 1.002));|'
juzga precio_de_quiebra X $I 's|const yy = y(e.ejecucion);|const yy = y(e.precio);|'
juzga radio_lineal X $L 's|LIQ_RADIO.r0 \* Math.sqrt(Math.max(0, Number(usd)) / LIQ_RADIO.u0);|LIQ_RADIO.r0 * Math.max(0, Number(usd)) / LIQ_RADIO.u0;|'
juzga umbral_ignorado P $L 's|return eventos.filter((e) => e.usd >= u);|return eventos;|'
echo retencion_de_12h > "$T/plantado"; condena retencion_de_12h T
juzga cascada_de_4 C $L 's|cierra: hi - j0 + 1 >= n }|cierra: hi - j0 + 1 >= n - 1 }|'
juzga ficha_de_otra_celda F $I 's|  const t = Date.parse(ts);|  const t = Date.parse(ts) + IND.liq.mMs;|'
juzga ficha_del_minuto F libro/libro-mapa.js 's|fichaLiq(m.liq.eventos, m.liq.sinDato, t0, t1,|fichaLiq(m.liq.eventos, m.liq.sinDato, Math.floor(t0 / 6e4) * 6e4, Math.floor(t0 / 6e4) * 6e4 + 6e4,|'
echo cinta_del_otro_lado > "$T/plantado"; condena cinta_del_otro_lado E
juzga hueco_como_cero F $L "s|(sueltas.huecos \|\| \[\]).filter((h) => h.estado !== 'recovered')|(sueltas.huecos \|\| []).filter(() => false)|"

echo "== restaurado"
base el_bueno_otra_vez
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K120-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
