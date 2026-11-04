#!/bin/bash
# K111-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA BRAZO DE K111 Y POR CADA DECISION DEL LIBRO QUE SE PUEDE
# ROMPER (campana 145, C5).
#
# EL SUJETO BUENO ES DE VERDAD: la pagina del ARBOL servida por K111-banco.py sobre una base desechable k111_ctl_<pid>
# con las fotos de PRODUCCION de K111-fotos.tsv.xz (perpetuos de BTC 02:30-03:30Z del 2026-10-18, con 51 min de HUECO
# de antes del servicio; okx_swap ETH 03:00-03:30Z; y para las vistas de R1, hasta 06:00Z: binance_usdm de BTC
# 05:00-06:00Z entera, con el corte de las 05:33Z, y los perpetuos de BTC 02:00-06:00Z a cada 30 s), y el relevo
# alimentado con 40 s de avisos REALES (K111-avisos.jsonl.xz). Sobre el, K111 tiene que salir VERDE. Cada plantado cambia LO SERVIDO (el banco), LA BASE (una
# copia con un hueco en medio) o LA PAGINA (un fichero en el --sobre del banco: el arbol no se toca, y cada `sed` tiene
# que MORDER exactamente las lineas esperadas o el plantado cuenta como fallido); K111 tiene que condenarlo POR SU BRAZO,
# con su frase y con la huella del escenario y la suya cambiadas; y el escenario vuelve a ser el bueno:
#   (S) cantidad_servida          una cantidad de /api/libro/fotos +1 despues de calcularla
#   (F) desconocido_como_cero     un nivel que no conoce ningun venue, pintado del color del fondo (como un cero)
#   (F) hueco_rellenado           un instante sin ninguna foto, pintado con la foto anterior (la base con un hueco)
#   (F) sin_libro_con_su_ultimo   un venue que dejo de tener libro valido, sumado con su ultimo libro
#   (C) canal_mal_declarado       va por sondeo y escribe que va por websocket
#   (V) familias_sumadas          perpetuos y spot pedidos como una familia
#   (F) parcial_como_completo     un nivel que no conocen todos, declarado de todos (P2 = a: mismo color, el globo dice n de N)
#   (F) escala_lineal             el color en lineal desde cero y no entre los cortes p20/p98 de lo visible
#   (F) acumulada_sin_minimo      la acumulada que pasa por niveles parciales, escrita sin su «≥»
#   (P) cada_fuera_de_regla       la historia pedida con un cada que no es el de la regla
#   (P) pagina_rota               una excepcion al arrancar
#   (F) pagina_de_e0fb3fb         la pagina de antes del remate (libro.html y static/libro/* de e0fb3fb, por git show): sin
#                                 la forma profesional (#esc-totales) en su html, llegue o no a listo (149 r1)
#   (F) rejilla_sin_ancla         sin relleno ni compensacion: la fila bajo un raton quieto cambia con el borde (149 r1)
#   (F) 149 rB, el mapa: lado_cambiado · honda_rancia_pintada (75 -> 750 s) · honda_de_otro_paso (suelo -> redondeo)
#       honda_pisa_el_vivo · extension_de_otra_columna · perfil_desalineado · volumen_de_otro_minuto
#       rango_de_otra_ventana (cortes de toda la historia) · ausente_con_color
# Y tres escenarios BUENOS mas que tienen que salir VERDE: vivo_por_sondeo (el websocket rechazado), hueco_en_medio (la
# base con el hueco y la pagina buena) y sin_libro_dicho (el venue sin libro y la pagina buena: lo dice y no suma).
# NO MEDIDO, ni ROJO ni VERDE: sin_pagina («FALTA DESPLEGAR») · sin_chromium · sin_fotos (la base vacia) · sin_canal.
# Y el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones; el escenario restaurado; el arbol intacto.
#
# No usa produccion ni el espejo. Puertos 8111 y 8112 (se niega a arrancar si estan ocupados). Al salir: 0 bases,
# ningun banco suyo vivo, el arbol intacto.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K111-el-libro-pintado-es-el-servido.sh"
BANCO="$AQUI/K111-banco.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
HASTA=2026-10-18T03:30:00Z  # el final de las vistas del pasado: el del sujeto grabado
HASTA_R1=2026-10-18T06:00:00Z  # el de las vistas de R1 (la del operador: la hora del corte de 140)
for f in "$CHK" "$BANCO" "$AQUI/K111-libro.py" "$AQUI/K111-fotos.tsv.xz" "$AQUI/K111-avisos.jsonl.xz" \
         "$AQUI/K102-mesa.py" "$AQUI/K109-footprint.py" "$AQUI/K110-libro.py" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
exec 9>/tmp/k111-control.lock
flock -n 9 || { echo "K111-control: otro K111-control esta corriendo; no se pisan"; exit 2; }
PID=$$
DB="k111_ctl_${PID}"
P1=8111; P2=8112
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " && { echo "control: el puerto $p esta ocupado (otro control u otro servidor): no arranco"; exit 2; }
done
T=$(mktemp -d) || exit 2
SERV1=""; SERV2=""
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

limpia() {
  for s in $SERV1 $SERV2; do kill "$s" 2>/dev/null; wait "$s" 2>/dev/null; done
  SERV1=""; SERV2=""
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k111_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  echo "bases k111_ctl_${PID}* que quedan: $(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k111_ctl_${PID}%'")"
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
k111() {  # puerto base [env extra...] -> rc; la salida en $T/sal
  local p=$1 b=$2; shift 2
  env "$@" K111_BASE="http://127.0.0.1:$p" K111_DB="$(dsn "$b")" K111_HASTA="$HASTA" K111_HASTA_R1="$HASTA_R1" \
    /bin/bash "$CHK" > "$T/sal" 2>&1; echo $?
}
GUARDA=${K111_CTL_GUARDA:-/tmp/k111-control-salidas}
rm -rf "$GUARDA"; mkdir -p "$GUARDA"
guarda() { cp "$T/sal" "$GUARDA/$1.sal"; }  # la salida ENTERA de cada escenario, aparte: la siguiente corrida de K111 la pisa
huella_k111() { head -1 "$T/sal" | grep -o 'huella [0-9a-f]*' | cut -d' ' -f2; }
escenario() {  # [base] -> lo que el banco sirve distinto del arbol, y los sujetos de los que parte
  { sha256sum < "$AQUI/K111-fotos.tsv.xz"; sha256sum < "$AQUI/K111-avisos.jsonl.xz"; echo "base ${1:-buena}"
    find "$T/sobre" -type f | sort | xargs -r sha256sum; cat "$T/plantado" 2>/dev/null; } | sha256sum | cut -c1-12
}

echo "== el sujeto: las fotos de produccion en tres bases (la buena, una con un hueco en medio, una vacia) y dos bancos del ARBOL"
for b in "$DB" "${DB}_hueco" "${DB}_vacia"; do
  createdb -h "$H" "$b" || exit 2
  "$PY" "$BANCO" carga "$(dsn "$b")" > "$T/carga" 2>&1 || { echo "control: la carga fallo: $(tail -1 "$T/carga")"; exit 2; }
done
# el hueco: ningun venue de los perpetuos de BTC tiene foto de 03:25:00 a 03:26:00 (en la vista: 6 instantes de 10 s)
psql -h "$H" -d "${DB}_hueco" -qc "DELETE FROM libro_foto WHERE symbol='BTC' AND ts >= '2026-10-18 03:25:00+00' AND ts < '2026-10-18 03:26:00+00'" || exit 2
psql -h "$H" -d "${DB}_vacia" -qc "TRUNCATE libro_foto" || exit 2
mkdir -p "$T/sobre/libro" "$T/sobre/flujo"
: > "$T/plantado"
"$PY" "$BANCO" sirve --puerto "$P1" --db "$(dsn "$DB")" --sobre "$T/sobre" --plantado "$T/plantado" \
  --avisos "$AQUI/K111-avisos.jsonl.xz" > "$T/banco1.log" 2>&1 &
SERV1=$!
"$PY" "$BANCO" sirve --puerto "$P2" --db "$(dsn "${DB}_hueco")" --sobre "$T/sobre" --plantado "$T/plantado" \
  --avisos "$AQUI/K111-avisos.jsonl.xz" > "$T/banco2.log" 2>&1 &
SERV2=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  [ "$(ss -ltn 2>/dev/null | grep -cE ":($P1|$P2) ")" = 2 ] && break
done
for p in $P1 $P2; do
  ss -ltn 2>/dev/null | grep -q ":$p " || { echo "control: el banco de $p no arranco: $(tail -1 "$T/banco1.log") $(tail -1 "$T/banco2.log")"; exit 2; }
done
BUENO=$(escenario)
rc=$(k111 $P1 "$DB" K111_PIEZAS="$T/piezas_bueno"); HK_BUENA=$(huella_k111); guarda el_bueno_es_verde
comprueba el_bueno_es_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K111' && echo 0 || echo 1)" \
  "rc=$rc · escenario $BUENO · $(head -1 "$T/sal" | cut -c1-60) · huella $HK_BUENA"
grep -E '^   · \((S|F|C)' "$T/sal" | cut -c1-170 | sed 's/^/        /'

echo "== los brazos: cada plantado, por el brazo que lo tiene que condenar"
planta_pagina() {  # fichero(en static/) patron-sed mordidas-esperadas -> 0 si mordio exactamente
  cp "$REPO/static/$1" "$T/sobre/$1"
  sed -i "$2" "$T/sobre/$1"
  [ "$(diff "$REPO/static/$1" "$T/sobre/$1" | grep -c '^>')" = "$3" ]
}
restaura() { rm -f "$T/sobre/libro.html" "$T/sobre/libro/"* "$T/sobre/flujo/"*; : > "$T/plantado"; }
planta_e0fb3fb() {  # la pagina de e0fb3fb entera en el sobre -> 0 si salio de git y su mapa no es el del arbol
  local f
  git -C "$REPO" show e0fb3fb:static/libro.html > "$T/sobre/libro.html" 2>/dev/null || return 1
  for f in $(git -C "$REPO" ls-tree --name-only e0fb3fb static/libro/ 2>/dev/null); do
    git -C "$REPO" show "e0fb3fb:$f" > "$T/sobre/libro/${f##*/}" 2>/dev/null || return 1
  done
  [ -s "$T/sobre/libro/libro-mapa.js" ] && ! cmp -s "$REPO/static/libro/libro-mapa.js" "$T/sobre/libro/libro-mapa.js"
}
juzga_plantado() {  # nombre brazo patron mordio(0/1) que [puerto] [base] [etiqueta de la base]
  local antes despues rc visto hk p=${6:-$P1} b=${7:-$DB}
  antes=$BUENO; despues=$(escenario "${8:-buena}")
  rc=$(k111 "$p" "$b"); hk=$(huella_k111); guarda "$1"
  visto=$(grep -E "\\($2\\) .*($3)" "$T/sal" | head -1 | cut -c1-150)
  comprueba "$1" "$([ "$4" = 0 ] && [ "$rc" = 1 ] && [ -n "$visto" ] && [ "$antes" != "$despues" ] && [ "$hk" != "$HK_BUENA" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $antes -> $despues · huella $hk · ${visto:-NO SALE ($2) $3: $(grep -m1 '^   · ' "$T/sal" | cut -c1-110)} · $5"
  restaura
}
juzga_bueno() {  # nombre patron-de-info que [puerto] [base] [etiqueta]
  local despues rc visto hk p=${4:-$P1} b=${5:-$DB}
  despues=$(escenario "${6:-buena}")
  rc=$(k111 "$p" "$b"); hk=$(huella_k111); guarda "$1"
  visto=$(grep -E "$2" "$T/sal" | head -1 | cut -c1-150)
  comprueba "$1" "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K111' && [ -n "$visto" ] && [ "$BUENO" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · escenario $BUENO -> $despues · huella $hk · ${visto:-NO SALE: $2 · $(head -1 "$T/sal" | cut -c1-90)} · $3"
  restaura
}
echo cantidad > "$T/plantado"
juzga_plantado cantidad_servida S "lo servido no es libro_foto: foto .* compras servido" 0 "una cantidad +1 despues de calcularla"
planta_pagina libro/libro-mapa.js 's/!s\.n\[k - s\.lo\]) return \[MAPA_COLOR\.desconocido, null\];/!s.n[k - s.lo]) return [MAPA_COLOR.fondo, null];/' 1; m=$?
juzga_plantado desconocido_como_cero F "el mapa no pinta lo servido: .*tenia que ser \(26, 26, 26\) \(DESCONOCIDO\)" $m "lo desconocido del color del fondo"
planta_pagina libro/libro-calculo.js 's/    const fotos = porTs\.get(t) || \[\];/    const fotos = porTs.get(t) || globalThis.K111_ULT || []; globalThis.K111_ULT = fotos;/' 1; m=$?
juzga_plantado hueco_rellenado F "el mapa no pinta lo servido: columna .*pintada foto y lo servido dice hueco" $m "el hueco con la foto anterior" "$P2" "${DB}_hueco" hueco
planta_pagina libro/libro-app.js "s/\['libro', 'sin_libro', 'sin_dato'\]\.includes(m\.tipo)/['libro', 'sin_dato'].includes(m.tipo)/" 1; m=$?
echo sin_libro:okx_swap > "$T/plantado"
# (149 r2) vivo O rancio: la pagina que ignora el sin_libro se queda con su ultimo libro, y su propio reloj lo vuelve
# rancio a los pocos segundos; cual de los dos lee la sonda depende de la hora del aviso. Las dos son el mismo defecto
juzga_plantado sin_libro_con_su_ultimo F "la escalera no pinta lo servido: venue okx_swap: la escalera dice (vivo|rancio) y su ultimo mensaje sin_libro" $m "el aviso sin libro ignorado"
planta_pagina libro/libro-app.js "s/  if (VIVO\.canal === 'websocket') return 'vivo por WEBSOCKET' + hora;/  if (VIVO.canal !== 'ninguno') return 'vivo por WEBSOCKET' + hora;/" 1; m=$?
echo sin_ws > "$T/plantado"
juzga_plantado canal_mal_declarado C "escribe .vivo por WEBSOCKET" $m "va por sondeo y escribe websocket"
planta_pagina flujo/flujo-calculo.js "s/'okx_swap', 'bitget_usdt'\] },/'okx_swap', 'bitget_usdt', 'binance_spot', 'bybit_spot', 'okx_spot'] },/" 1; m=$?
juzga_plantado familias_sumadas V "2 familia\\(s\\): perp, spot" $m "perpetuos + spot en la familia perp"
planta_pagina libro/libro-mapa.js 's/s\.n\[i\], ix, lado ? /s.N, ix, lado ? /' 1; m=$?
juzga_plantado parcial_como_completo F "el mapa no pinta lo servido: columna .* nivel .*pinta compra .*y lo servido da" $m "lo parcial declarado como de todos (P2 = a: el mismo color y el globo dice n de N)"
planta_pagina libro/libro-calculo.js 's/      return Math\.min(255, Math\.floor((255 \* (q - a)) \/ (b - a)));/      return Math.min(255, Math.floor((255 * q) \/ b));/' 1; m=$?
juzga_plantado escala_lineal F "el mapa no pinta lo servido: .*(color [0-9]+ y el percentil|tenia que ser .*su color)" $m "lineal y no el percentil de la ventana"
planta_pagina libro/libro-calculo.js 's/      parcial = parcial || f\.n < s\.N;/      parcial = false;/' 1; m=$?
juzga_plantado acumulada_sin_minimo F "la escalera no pinta lo servido: fila .*acumulada" $m "la acumulada sin su minimo"
planta_pagina libro/libro-calculo.js 's/  let c = LIBRO_FOTO_S;/  let c = 2 * LIBRO_FOTO_S;/' 1; m=$?
juzga_plantado cada_fuera_de_regla P "pide lo que su hash no dice: cada=10 \\(su hash dice 5\\)" $m "un cada que no es el de la regla"
planta_pagina libro/libro-app.js 's/^function arranca() {$/function arranca() { throw new Error("plantado por K111-control");/' 1; m=$?
juzga_plantado pagina_rota P "lanzo 1 excepcion|no pinto su vista" $m "una excepcion al arrancar"
planta_e0fb3fb; m=$?
juzga_plantado pagina_de_e0fb3fb F "\[BTC [a-z_]+\] la escalera no tiene la forma profesional: falta #esc-totales" $m \
  "la pagina de e0fb3fb: su html no tiene la forma profesional, llegue o no a listo"

echo "== la escalera profesional (campana 149): barras, grandes, totales, ausente y el volumen reciente de la cinta"
planta_pagina libro/libro-calculo.js 's/  return tope > 0 ? Math\.min(1, q \/ tope) : 0;/  return tope > 0 ? Math.min(1, q \/ (2 * tope)) : 0;/' 1; m=$?
juzga_plantado barra_no_es_su_tamano F "la barra no es su tamaño: fila" $m "la barra a media escala del p95"
planta_pagina libro/libro-calculo.js "s/      const lado = o\.agresor === 'venta' ? 'b' : o\.agresor === 'compra' ? 'a' : null;/      const lado = o.agresor === 'venta' ? 'a' : o.agresor === 'compra' ? 'b' : null;/" 1; m=$?
juzga_plantado reciente_de_otro_lado F "el volumen reciente no es el de la cinta: fila" $m "la venta agresora en @ask"
planta_pagina libro/libro-calculo.js 's/  const nuevas = ops\.filter((x) => !s\.vistos\.has(x\.clave));/  const nuevas = ops.filter(() => true);/' 1; m=$?
juzga_plantado reciente_duplicado F "el volumen reciente no es el de la cinta: fila" $m "sin quitar lo ya contado de la pagina anterior"
planta_pagina libro/libro-escalera.js "s/^const AUSENTE = '';/const AUSENTE = '0';/" 1; m=$?
juzga_plantado ausente_como_cero F "lo ausente \\(DESCONOCIDO\\) se pinta «0»" $m "lo ausente escrito como cero"
planta_pagina libro/libro-calculo.js 's/^const ESC_GRANDE_X = 3;/const ESC_GRANDE_X = 2;/' 1; m=$?
juzga_plantado grande_con_otro_umbral F "una orden grande con otro umbral: fila" $m "grande a 2x la media y no a 3x"
planta_pagina libro/libro-escalera.js 's/      tot = totalesVisibles(vis, /      tot = totalesVisibles([...modelo.values()], /' 1; m=$?
juzga_plantado totales_de_otra_cosa F "los totales son de otra cosa" $m "los totales de todo el modelo y no de lo visible"
planta_pagina libro/libro-escalera.js 's/^const ESC_ANCLA = true;/const ESC_ANCLA = false;/' 1; m=$?
juzga_plantado rejilla_sin_ancla F "\[BTC perp vivo\] la fila se mueve bajo el raton quieto" $m "sin relleno ni compensacion: la rejilla resbala con el borde"
planta_pagina libro/libro-escalera.js "s/^const SIN_CINTA = '';/const SIN_CINTA = '0';/" 1; m=$?
echo sin_cinta > "$T/plantado"
juzga_plantado sin_cinta_como_cero F "la cinta caída se pinta como cifras" $m "la cinta caida pintada como ceros"

echo "== el mapa profesional (campana 149 ronda B): paleta por lado, rango, capa honda y lo de alrededor"
planta_pagina libro/libro-mapa.js 's/  return v > c ? 1 : 0;/  return v > c ? 0 : 1;/' 1; m=$?
juzga_plantado lado_cambiado F "el mapa no pinta lo servido: columna .* nivel .*: lado [cv] y [0-9.e-]+ de capa honda; lo servido da" $m "el lado que gana, al reves"
planta_pagina libro/libro-calculo.js 's/^const HONDA_RANCIA_S = 75;/const HONDA_RANCIA_S = 750;/' 1; m=$?
juzga_plantado honda_rancia_pintada F "\[BTC perp\] el mapa no pinta lo servido: (capa honda: la pagina dice|R1: ensena los niveles|columna .* nivel )" $m "la foto honda de hace mas de 75 s, pintada"
planta_pagina libro/libro-calculo.js 's/    const k = Math\.floor(ks \/ m);/    const k = Math.round(ks \/ m);/' 1; m=$?
juzga_plantado honda_de_otro_paso F "\[ETH okx_swap\] el mapa no pinta lo servido: (R1: ensena los niveles|columna .* nivel )" $m "la capa honda agrupada al paso de la vista por redondeo y no por suelo"
planta_pagina libro/libro-calculo.js 's/^    if (L && (lado === 0 ? k >= L\.lo : k <= L\.hi)) return;$/    if (L \&\& false) return;/' 1; m=$?
juzga_plantado honda_pisa_el_vivo F "el mapa no pinta lo servido: columna .* nivel .*(de capa honda; lo servido|pinta compra)" $m "la capa honda sumada dentro del alcance del vivo"
planta_pagina libro/libro-mapa.js 's/ctx\.drawImage(L\.bmp, 2 \* ja, /ctx.drawImage(L.bmp, 2 * (ja - 1), /' 1; m=$?
juzga_plantado extension_de_otra_columna F "el mapa no pinta lo servido: «ahora» nivel .*tenia que ser" $m "«ahora» estira la columna de antes"
planta_pagina libro/libro-mapa.js 's/ctx\.fillRect(xPerf + 2, yDe(k), b\.largo(q), fh);/ctx.fillRect(xPerf + 2, yDe(k + 1), b.largo(q), fh);/' 1; m=$?
juzga_plantado perfil_desalineado F "el mapa no pinta lo servido: el perfil del libro, nivel" $m "el perfil del libro una fila desplazado"
planta_pagina libro/libro-mapa.js 's/        const x0 = xT(t);/        const x0 = xT(t + 60000);/; s/        const x1 = xT(t + 60000);/        const x1 = xT(t + 120000);/' 2; m=$?
juzga_plantado volumen_de_otro_minuto F "el mapa no pinta lo servido: el volumen de debajo" $m "cada barra de abajo bajo el minuto siguiente"
planta_pagina libro/libro-mapa.js 's/escalaCortes(m\.columnas, j0, j1, /escalaCortes(m.columnas, 0, m.columnas.length - 1, /' 1; m=$?
juzga_plantado rango_de_otra_ventana F "el mapa no pinta lo servido: (la escala declara|columna .* nivel .*color [0-9-]+ y el percentil)" $m "los cortes de toda la historia y no de lo visible"
planta_pagina libro/libro-mapa.js 's/!s\.n\[k - s\.lo\]) return \[MAPA_COLOR\.desconocido, null\];/!s.n[k - s.lo]) return [MAPA_LUT_COMPRA[40], null];/' 1; m=$?
juzga_plantado ausente_con_color F "el mapa no pinta lo servido: .*tenia que ser \(26, 26, 26\) \(DESCONOCIDO\)" $m "lo desconocido con un color de la paleta"

echo "== tres escenarios buenos mas: tienen que salir VERDE"
echo sin_ws > "$T/plantado"
juzga_bueno vivo_por_sondeo '^   · \(C\) .*vivo por sondeo' "el websocket rechazado: la pagina se va al sondeo y lo dice"
juzga_bueno hueco_en_medio '^   · \(F\) \[BTC perp\] mapa: .*hueco [0-9]+\)' "la base con un hueco en medio y la pagina buena" "$P2" "${DB}_hueco" hueco
echo sin_libro:okx_swap > "$T/plantado"
juzga_bueno sin_libro_dicho '^   · \(F\) \[BTC perp vivo\] escalera: .*3 de 4 venues sumando.*okx_swap sin_libro' "el venue sin libro: dicho y sin sumar"

echo "== lo que no se puede medir: NO MEDIDO, ni ROJO ni VERDE"
echo sin_pagina > "$T/plantado"
rc=$(k111 $P1 "$DB")
comprueba sin_pagina "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: FALTA DESPLEGAR' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
restaura
mkdir -p "$T/vacio"
rc=$(k111 $P1 "$DB" PATH="$T/vacio")
comprueba sin_chromium "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin Chromium' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-110)"
rc=$(k111 $P1 "${DB}_vacia")
comprueba sin_fotos "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO: sin fotos en la ventana' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"
rc=$(k111 $P1 "${DB}_no_existe")
comprueba sin_canal "$([ "$rc" = 2 ] && head -1 "$T/sal" | grep -q '^NO MEDIDO (CANAL)' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/sal" | cut -c1-120)"

echo "== el check: A89 los dos modos de SIGPIPE, A56 las tres invocaciones"
ENV=(K111_BASE="http://127.0.0.1:$P1" "K111_DB=$(dsn "$DB")" "K111_HASTA=$HASTA" "K111_HASTA_R1=$HASTA_R1")
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K111' && ! grep -qi 'broken pipe' "$T/chk" && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
done
(env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd "$REPO" && env "${ENV[@]}" bash harness/checks/K111-el-libro-pintado-es-el-servido.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"
(cd /tmp && env "${ENV[@]}" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-80)"

echo "== restaurado"
FIN=$(escenario)
rc=$(k111 $P1 "$DB" K111_PIEZAS="$T/piezas_fin"); HK_FIN=$(huella_k111)
guarda escenario_restaurado  # (149 r2) su huella no repitio la del bueno en 3 de 4 corridas, y la causa NO SE SUPO
# (149 B) por eso K111 escribe cada pieza de su huella (K111_PIEZAS) y, si no repite, la linea dice DONDE: la vista, el
# caracter y lo que habia alrededor antes y despues
difpiezas() {
  awk -F'\t' 'NR == FNR { a[FNR] = $0; next }
    a[FNR] != $0 { x = a[FNR]; for (i = 1; i <= length($0) && substr($0, i, 1) == substr(x, i, 1); i++) ;
      print "difiere " $1 " en el caracter " i ": " substr(x, i < 60 ? 1 : i - 60, 120) " -> " substr($0, i < 60 ? 1 : i - 60, 120); exit }' "$1" "$2"
}
DIFP=$(difpiezas "$T/piezas_bueno" "$T/piezas_fin" 2>&1 | cut -c1-400)
comprueba escenario_restaurado "$([ "$FIN" = "$BUENO" ] && [ "$rc" = 0 ] && [ "$HK_FIN" = "$HK_BUENA" ] && echo 0 || echo 1)" \
  "escenario $BUENO -> $FIN · huella de K111 $HK_BUENA -> $HK_FIN · rc=$rc${DIFP:+ · $DIFP}"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K111-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
