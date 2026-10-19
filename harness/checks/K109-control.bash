#!/bin/bash
# K109-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA BRAZO DE K109 Y POR CADA DECISION DEL FOOTPRINT QUE SE
# PUEDE ROMPER (campana 142, C4).
#
# EL SUJETO BUENO ES DE VERDAD: la pagina del ARBOL servida por K109-banco.py sobre una base desechable
# k109_ctl_<pid> con las celdas de PRODUCCION de K109-celdas.tsv.gz (bajadas una vez), que la ruta del ARBOL convierte en
# footprint. Sobre el, K109 tiene que salir VERDE. Cada plantado cambia LO SERVIDO (el banco lo tuerce despues de
# calcularlo) o LA PAGINA (un fichero en el --sobre del banco, que se sirve en vez del del arbol: el arbol no se toca),
# y K109 tiene que condenarlo POR SU BRAZO, con su frase, con la huella del escenario cambiada, y el escenario vuelve a
# ser el bueno despues:
#   (S) nivel_servido            una celda servida +0.5, la vela cuadrando consigo misma: solo las celdas lo ven
#   (S) va_servida               la value area servida de una vela aplastada a su VAL
#   (F) poc_en_otro_nivel        el marco del POC pintado un nivel por encima del servido
#   (F) numeros_cruzados         la compra escrita donde va la venta
#   (F) color_al_reves           el color del delta con el signo cambiado
#   (F) incompleta_como_completa una vela con minutos sin escuchar enteros pintada como completa
#   (F) hueco_como_vela          una vela que nadie escucho pintada como otra cosa
#   (D) umbral_cambiado          el desequilibrio a x2 en vez de x3
#   (V) familias_sumadas         perpetuos y spot pedidos juntos como si fueran una familia
#   (P) pagina_rota              una excepcion al arrancar: no pinta
#   (P) pide_otro_paso           pide un paso que su hash no dice
# OF-3 (campana 143), las capas y el TPO:
#   (F) banda_a_otra_sigma       la banda de 1 desviacion pintada donde se sirvio la de 2
#   (F) vah_pintada_movida       la linea de la VAH de un perfil, un nivel por encima de la servida
#   (F) incompleta_pintada_completa  una capa con minutos sin escuchar enteros pintada como completa
#   (F) letra_de_otro_periodo    cada letra del TPO, la del periodo siguiente
#   (P) sesion_partida_a_medianoche  las sesiones empiezan a medianoche: la que la cruza se pide partida
# Y los NO MEDIDO, que no son ni ROJO ni VERDE: sin_pagina (404, «FALTA DESPLEGAR») · sin_chromium · sin_dato (la
# ventana sin una celda, como en produccion cuando caduque) · sin_canal (la base de las celdas no contesta).
# Y un sujeto ANTERIOR a OF-3 (la pagina de ce5f485 y las rutas nuevas en 404, como produccion hasta desplegar la 143):
# VERDE en lo del footprint y las seis vistas de las capas y el TPO SIN JUZGAR, nunca ROJO.
# Y el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones; el escenario restaurado; el arbol intacto.
#
# No usa produccion ni el espejo. Puertos 8109 y 8110 (se niega a arrancar si estan ocupados). Al salir: 0 bases,
# ningun banco suyo vivo, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K109-lo-pintado-es-lo-servido.sh"
BANCO="$AQUI/K109-banco.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
for f in "$CHK" "$BANCO" "$AQUI/K109-footprint.py" "$AQUI/K109-celdas.tsv.gz" "$AQUI/K102-mesa.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
PID=$$
DB="k109_ctl_${PID}"
P1=8109; P2=8110
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "control: el puerto $p esta ocupado (otro control u otro servidor): no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SERV1=""; SERV2=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  for s in $SERV1 $SERV2; do kill "$s" 2>/dev/null; wait "$s" 2>/dev/null; done
  SERV1=""; SERV2=""
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k109_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k109_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k109_ctl_${PID}%'")"
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
k109() {  # puerto base [env extra...] -> rc; la salida en $T/sal
  local p=$1 b=$2; shift 2
  env "$@" K109_BASE="http://127.0.0.1:$p" K109_DB="$(dsn "$b")" /bin/bash "$CHK" > "$T/sal" 2>&1; echo $?
}
huella_k109() { head -1 "$T/sal" | grep -o 'huella [0-9a-f]*' | cut -d' ' -f2; }
escenario() {  # lo que el banco sirve distinto del arbol, y las celdas de las que parte
  { sha256sum < "$AQUI/K109-celdas.tsv.gz"; find "$T/sobre" -type f | sort | xargs -r sha256sum; cat "$T/plantado" 2>/dev/null; } \
    | sha256sum | cut -c1-12
}

echo "== el sujeto: dos bases con las celdas de produccion (una vaciada) y el banco del ARBOL"
for b in "$DB" "${DB}_vacia"; do
  createdb -h "$H" "$b" || exit 2
  "$PY" "$BANCO" carga "$(dsn "$b")" > "$T/carga" 2>&1 || { echo "control: la carga fallo: $(tail -1 "$T/carga")"; exit 2; }
done
psql -h "$H" -d "${DB}_vacia" -qc "TRUNCATE orderflow_celda, orderflow_cobertura" || exit 2
mkdir -p "$T/sobre/flujo"
"$PY" "$BANCO" sirve --puerto "$P1" --db "$(dsn "$DB")" --sobre "$T/sobre" --plantado "$T/plantado" > "$T/banco1.log" 2>&1 &
SERV1=$!
"$PY" "$BANCO" sirve --puerto "$P2" --db "$(dsn "${DB}_vacia")" > "$T/banco2.log" 2>&1 &
SERV2=$!
sleep 2
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " || { echo "control: el banco de $p no arranco: $(tail -1 "$T/banco1.log")"; exit 2; }
done
BUENO=$(escenario)
rc=$(k109 $P1 "$DB"); HK_BUENA=$(huella_k109)
comprueba el_bueno_es_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K109' && echo 0 || echo 1)" \
  "rc=$rc · escenario $BUENO · $(head -1 "$T/sal" | cut -c1-70) · huella $HK_BUENA"
grep -E '^   · \((S|F)' "$T/sal" | cut -c1-160 | sed 's/^/        /'

echo "== los brazos: cada plantado, por el brazo que lo tiene que condenar"
planta_pagina() {  # fichero(en static/flujo) patron-sed mordidas-esperadas -> 0 si mordio exactamente
  cp "$REPO/static/flujo/$1" "$T/sobre/flujo/$1"
  sed -i "$2" "$T/sobre/flujo/$1"
  [ "$(diff "$REPO/static/flujo/$1" "$T/sobre/flujo/$1" | grep -c '^>')" = "$3" ]
}
restaura() { rm -f "$T/sobre/flujo/"* "$T/plantado"; }
juzga_plantado() {  # nombre brazo patron mordio(0/1) que
  local antes despues rc visto hk
  antes=$BUENO; despues=$(escenario)
  rc=$(k109 $P1 "$DB"); hk=$(huella_k109)
  visto=$(grep -E "^   · \\($2\\) .*($3)" "$T/sal" | head -1 | cut -c1-150)
  comprueba "$1" "$([ "$4" = 0 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && [ "$hk" != "$HK_BUENA" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $antes -> $despues · huella $hk · ${visto:-NO SALE ($2) $3: $(grep -m1 '^   · ' "$T/sal" | cut -c1-110)} · $5"
  restaura
}
echo nivel > "$T/plantado"
juzga_plantado nivel_servido S "lo servido != las celdas: vela .*niveles servidos != celdas" 0 "una celda +0.5 y su vela con ella"
echo va > "$T/plantado"
juzga_plantado va_servida S "value area servida .* != celdas" 0 "VAH = VAL en la ultima vela"
planta_pagina flujo-dibujo.js 's/y(Number(v\.poc)/y(Number(v.poc) + paso/' 2; m=$?
juzga_plantado poc_en_otro_nivel F "el marco del POC no esta en la fila" $m "el marco un nivel arriba"
planta_pagina flujo-dibujo.js 's/const tv = cifraE04(l\.venta, dec);/const tv = cifraE04(l.compra, dec);/' 1; m=$?
juzga_plantado numeros_cruzados F "escribe venta" $m "la compra donde va la venta"
planta_pagina flujo-dibujo.js "s/const color = d > 0 ? 'compra' : d < 0 ? 'venta'/const color = d > 0 ? 'venta' : d < 0 ? 'compra'/" 1; m=$?
juzga_plantado color_al_reves F "color (venta|compra) con delta servido" $m "el signo del color cambiado"
planta_pagina flujo-calculo.js 's/if (!c\.completa) return/if (false) return/' 1; m=$?
juzga_plantado incompleta_como_completa F "pintada completa .*dice incompleta" $m "sin la rama de la incompleta"
planta_pagina flujo-calculo.js 's/if (!c\.minutos_con_fila) return/if (false) return/' 1; m=$?
juzga_plantado hueco_como_vela F "pintada incompleta .*dice hueco" $m "sin la rama del hueco"
planta_pagina flujo-calculo.js 's/^const DESEQ_RAZON = 3n;/const DESEQ_RAZON = 2n;/' 1; m=$?
juzga_plantado umbral_cambiado D "desequilibrios: vela .*la regla da" $m "x2 en vez de x3"
planta_pagina flujo-calculo.js "s/'okx_swap', 'bitget_usdt'\]/'okx_swap', 'bitget_usdt', 'binance_spot', 'bybit_spot', 'okx_spot']/" 1; m=$?
juzga_plantado familias_sumadas V "2 familia\\(s\\): perp, spot" $m "perpetuos + spot en la familia perp"
planta_pagina flujo-app.js 's/^function arranca() {$/function arranca() { throw new Error("plantado por K109-control");/' 1; m=$?
juzga_plantado pagina_rota P "lanzo 1 excepcion|no pinto la vista" $m "una excepcion al arrancar"
planta_pagina flujo-app.js 's/parametros(VISTA, w\.desde, w\.hasta, VISTA\.paso)/parametros(VISTA, w.desde, w.hasta, "auto")/' 1; m=$?
juzga_plantado pide_otro_paso P "pide lo que su hash no dice: paso=auto" $m "pide paso=auto con un paso fijado en el hash"
# OF-3 (campana 143): las capas y el TPO, cada decision que se pinta con su plantado
planta_pagina flujo-capas.js 's/const b = p\.bandas\[String(k)\];/const b = p.bandas[String(k === 1 ? 2 : k)];/' 1; m=$?
juzga_plantado banda_a_otra_sigma F "las capas pintan otra cosa .*banda" $m "la banda de 1 sigma pintada en la de 2"
planta_pagina flujo-capas.js "s/r\.vah = linea('VAH', va\.vah, y(Number(va\.vah) + paso)/r.vah = linea('VAH', va.vah, y(Number(va.vah) + 2 * paso)/" 1; m=$?
juzga_plantado vah_pintada_movida F "las capas pintan otra cosa .*la linea del VAH" $m "la linea de la VAH un nivel arriba"
planta_pagina flujo-calculo.js "s/if (esperados !== 0 && !c\.minutos_con_fila) estado = 'hueco';/if (false) estado = 'hueco';/; s/else if (esperados !== 0 && !c\.completa) estado = 'incompleta';/else if (false) estado = 'incompleta';/" 2; m=$?
juzga_plantado incompleta_pintada_completa F "su marca dice .*faltan" $m "una capa con minutos sin escuchar, como completa"
planta_pagina flujo-tpo.js 's/const letra = l\.letras\[i\];/const letra = m.letras[m.letras.indexOf(l.letras[i]) + 1] || l.letras[i];/' 1; m=$?
juzga_plantado letra_de_otro_periodo F "el TPO pintado no es el servido: .*escribe" $m "cada letra, la del periodo siguiente"
planta_pagina flujo-calculo.js 's/  const o = ses\.ini \* 60000;/  const o = 0;/' 1; m=$?
juzga_plantado sesion_partida_a_medianoche P "piden lo que su hash no dice: compuesto|pide lo que su hash no dice: desde" $m "las sesiones empiezan a medianoche"

echo "== lo que no se puede medir: NO MEDIDO, ni ROJO ni VERDE"
echo sin_pagina > "$T/plantado"
rc=$(k109 $P1 "$DB")
comprueba sin_pagina "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
restaura
mkdir -p "$T/vacio"
rc=$(k109 $P1 "$DB" PATH="$T/vacio")
comprueba sin_chromium "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin Chromium' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
rc=$(k109 $P2 "${DB}_vacia")
comprueba sin_dato "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: K109 · (S) .*sin dato en la ventana fija' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
rc=$(k109 $P1 "${DB}_no_existe")
comprueba sin_canal "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: K109 · (S) .*sin canal a las celdas' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"

echo "== un sujeto ANTERIOR a OF-3 (produccion hasta desplegar la 143): la pagina de ce5f485 y sus rutas nuevas en 404"
for f in flujo.html flujo/flujo-app.js flujo/flujo-calculo.js flujo/flujo-dibujo.js flujo/flujo.css; do
  git -C "$REPO" show "ce5f485:static/$f" > "$T/sobre/$f" 2>/dev/null || echo "control: no pude leer static/$f de ce5f485"
done
echo sin_of3 > "$T/plantado"
rc=$(k109 $P1 "$DB")
comprueba sujeto_anterior_a_of3 "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K109 .*SIN JUZGAR (el sujeto es anterior a OF-3: 6 vistas sin mirar)' && echo 0 || echo 1)" \
  "rc=$rc · VERDE en lo del footprint y $(head -1 "$T/sal" | grep -o 'las capas y el TPO, SIN JUZGAR[^)]*)')"
rm -f "$T/sobre/flujo.html"
restaura

echo "== el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones"
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo K109_BASE="http://127.0.0.1:$P1" K109_DB="$(dsn "$DB")" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K109' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
done
(env K109_BASE="http://127.0.0.1:$P1" K109_DB="$(dsn "$DB")" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd "$REPO" && env K109_BASE="http://127.0.0.1:$P1" K109_DB="$(dsn "$DB")" bash harness/checks/K109-lo-pintado-es-lo-servido.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd /tmp && env K109_BASE="http://127.0.0.1:$P1" K109_DB="$(dsn "$DB")" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"

echo "== restaurado"
FIN=$(escenario)
rc=$(k109 $P1 "$DB"); HK_FIN=$(huella_k109)
comprueba escenario_restaurado "$([ "$FIN" = "$BUENO" ] && [ "$rc" = 0 ] && [ "$HK_FIN" = "$HK_BUENA" ] && echo 0 || echo 1)" \
  "escenario $BUENO -> $FIN · huella de K109 $HK_BUENA -> $HK_FIN · rc=$rc"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K109-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
