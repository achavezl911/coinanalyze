#!/bin/bash
# K119-control · LOS PLANTADOS QUE TIENEN QUE FALLAR EN K119 (campana BOT-5).
#
# EL ESCENARIO BUENO: K119 sobre el arbol (K119_SIN_PRODUCCION=1: no mira 140) -> VERDE, y sobre una copia del arbol
# (app/, sql/schema.sql, config/anatomia/ y los K119-* de harness/checks) -> VERDE. Cada plantado, en su copia:
#
#   umbral_estricto        A.cumple: la cola baja con < en vez de <= (F1 esta EXACTAMENTE en el umbral)   ROJO falta 01:14
#   ventana_de_59          sombra.decide suma w-1 minutos en vez de w (F2 solo se junta con 60)           ROJO falta 10:39
#   perp_como_contado      la candidata de contado lee y SUMA tambien el flujo de perpetuo (dp100k): las
#                          ventas de perpetuo de la muestra real la disparan a las 05:39 (solo ensanchar las venues
#                          no muerde: A.cinta_fila ya separa contado y perpetuo por venue)                ROJO 05:39
#   impreso_de_99k         GRANDE_100K = 99999 (senuelo: 6 impresos de 99999 a las 07:20)                 ROJO 07:24
#   entrada_al_cierre      la entrada al cierre del minuto siguiente, no a su apertura                     ROJO entrada 01:14
#   solape                 decide sin esperar a la salida de la anterior                                  ROJO 01:19
#   sin_dato_como_fracaso  un minuto de precio que falta en el camino se cuenta como fracaso (F4)         ROJO 16:44
#   comision_de_un_lado    5.5 bps en vez de 2 x 5.5 en recorre/vence/etiqueta_entera                     ROJO neto 01:14
#   candidata_reescrita    el umbral redondeado a -479834.7 en el json, con su sha nuevo en el bot        ROJO 08:34
#
# Y el check: los dos modos de SIGPIPE y la invocacion desde otro directorio, sobre el escenario bueno. Al salir: el
# arbol intacto y nada en el temporal. No toca produccion ni el espejo: cada corrida de K119 crea y borra su base.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K119-la-sombra-es-el-estudio.sh"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY=/srv/coinanalyze/repo/.venv/bin/python
for f in "$CHK" "$AQUI/K119-sombra.py" "$AQUI/K119-esperado.json" "$AQUI/K119-sintetico.tsv.xz" "$REPO/app/bot/sombra.py" \
         "$REPO/app/anatomia.py" "$REPO/config/anatomia/congeladas-20261103.json" "$PY"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
T=$(mktemp -d) || exit 2
trap 'rm -rf "$T"' EXIT
trap 'rm -rf "$T"; trap - EXIT; exit 143' INT TERM
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
export K119_SIN_PRODUCCION=1 K119_PY="$PY"

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-22s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-22s %s\n' "$1" "$3"; fi
}
arbol() {  # nombre -> una copia de lo que K119 juzga
  local a="$T/a/$1"
  mkdir -p "$a/sql" "$a/config" "$a/harness/checks"
  cp -r "$REPO/app" "$a/" && cp "$REPO/sql/schema.sql" "$a/sql/" && cp -r "$REPO/config/anatomia" "$a/config/" \
    && cp "$AQUI"/K119-* "$a/harness/checks/" || { echo "control: no copio el arbol"; exit 2; }
  echo "$a"
}
huella() {  # arbol -> huella del sujeto
  cat "$1"/app/*.py "$1"/app/bot/*.py "$1"/config/anatomia/* 2>/dev/null | sha256sum | cut -c1-12
}
k119() {  # arbol -> rc; salida en $T/sal
  K119_REPO="$1" bash "$CHK" > "$T/sal" 2>&1
  echo $?
}
sustituye() {  # fichero viejo nuevo n: falla si el texto viejo no esta EXACTAMENTE n veces
  "$PY" -S - "$@" <<'PY'
import sys
f, viejo, nuevo, n = sys.argv[1:5]
t = open(f, encoding="utf-8").read()
if t.count(viejo) != int(n):
    sys.exit(f"control: {viejo!r} esta {t.count(viejo)} veces en {f}, no {n}")
open(f, "w", encoding="utf-8").write(t.replace(viejo, nuevo))
PY
}

echo "== el escenario bueno"
rc=$(k119 "$REPO")
comprueba base_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE: K119 .*banco: 4 operaciones = las del estudio, 1 sin_dato' && echo 0 || echo 1)" \
  "rc=$rc · $(head -1 "$T/sal" | cut -c1-300)"
BUENA=$(arbol buena)
H_BUENA=$(huella "$BUENA")
rc=$(k119 "$BUENA")
comprueba copia_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE: K119 ' && echo 0 || echo 1)" "rc=$rc · huella $H_BUENA"

planta() {  # nombre patron detalle -- fichero viejo nuevo n [fichero viejo nuevo n ...]
  local nombre=$1 patron=$2 que=$3 a rc despues visto
  [ -n "${K119C_SOLO:-}" ] && [[ " $K119C_SOLO " != *" $nombre "* ]] && return  # K119C_SOLO="a b": solo esos
  shift 4
  a=$(arbol "$nombre")
  while [ $# -ge 4 ]; do
    sustituye "$a/$1" "$2" "$3" "$4" > "$T/sus" 2>&1 \
      || { comprueba "$nombre" 1 "NO MUERDE: $(tail -1 "$T/sus" | cut -c1-300)"; rm -rf "$a"; return; }
    shift 4
  done
  despues=$(huella "$a")
  rc=$(k119 "$a")
  visto=$(grep -E "$patron" "$T/sal" | head -1 | cut -c1-400)
  comprueba "$nombre" "$([ "$rc" = 1 ] && [ -n "$visto" ] && [ "$H_BUENA" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · $H_BUENA -> $despues · ${visto:-NO SALE: $(head -1 "$T/sal" | cut -c1-300)} · $que"
  rm -rf "$a"
}

echo "== los plantados"
planta umbral_estricto "^ROJO: K119 banco: disparo 10-21 10:39Z \(exito\) contra el estudio 10-21 01:14Z" "x < u en la cola baja" -- \
  app/anatomia.py "return x < u if estricto else x <= u" "return x < u" 1
planta ventana_de_59 "^ROJO: K119 banco: disparo 10-21 12:44Z \(fracaso\) contra el estudio 10-21 10:39Z" "59 minutos" -- \
  app/bot/sombra.py "(c.w - 1) * MIN" "(c.w - 2) * MIN" 1
planta perp_como_contado "^ROJO: K119 banco: disparo 10-21 05:39Z \(fracaso\) contra el estudio 10-21 10:39Z" "contado + perpetuo" -- \
  app/bot/sombra.py 'A.VENUES_SPOT if v.group(1) == "s"' 'A.VENUES_SPOT + A.VENUES_PERP if v.group(1) == "s"' 1 \
  app/bot/sombra.py 'return f[c.columna] if f' 'return f[c.columna] + f[A.COL["dp100k"]] if f' 1
planta impreso_de_99k "^ROJO: K119 banco: disparo 10-21 07:24Z \(exito\) contra el estudio 10-21 10:39Z" "GRANDE_100K = 99999" -- \
  app/anatomia.py "GRANDE_100K = 100_000.0" "GRANDE_100K = 99_999.0" 1
planta entrada_al_cierre "^ROJO: K119 banco: 10-21 01:14Z bot \(entrada 105.6887, .* contra el estudio \(entrada 105.6929," "b[3]" -- \
  app/bot/sombra.py 'f["entrada"] = b[0]' 'f["entrada"] = b[3]' 1
planta solape "^ROJO: K119 banco: disparo 10-21 01:19Z \(fracaso\) contra el estudio 10-21 10:39Z" "sin esperar la salida" -- \
  app/bot/sombra.py "if ok and t >= libre:" "if ok:" 1
planta sin_dato_como_fracaso "^ROJO: K119 banco: disparo 10-21 16:44Z \(fracaso\) contra el estudio -$" "sin precio = fracaso" -- \
  app/bot/sombra.py 'estado="sin_dato", exito=None, neto=None' 'estado="fracaso", exito=0, neto=-0.0071' 1
planta comision_de_un_lado "^ROJO: K119 banco: 10-21 01:14Z bot \(entrada 105.6929, exito 0, neto -0.002604064180280868," "una comision" -- \
  app/anatomia.py "- 2 * COMISION" "- COMISION" 5
NUEVA=$("$PY" -S -c 'import hashlib,sys; t=open(sys.argv[1]).read(); n=t.count("-479834.70166359004")
assert n == 1, n; print(hashlib.sha256(t.replace("-479834.70166359004", "-479834.7").encode()).hexdigest())' \
  "$REPO/config/anatomia/congeladas-20261103.json" 2>&1)
planta candidata_reescrita "^  banco: disparo 10-21 08:34Z \(" "umbral -479834.7, sha ${NUEVA:0:12}" -- \
  config/anatomia/congeladas-20261103.json "-479834.70166359004" "-479834.7" 1 \
  app/bot/sombra.py "be13350c09e7c993687a7bbc961a9038ae8c09ae19d5a72fbbfb304f970f7844" "$NUEVA" 1

echo "== el check: los dos modos de SIGPIPE y la invocacion ajena, sobre el escenario bueno"
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  [ -n "${K119C_SOLO:-}" ] && break
  env "$modo" K119_REPO="$REPO" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE: K119 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-120)"
done
[ -z "${K119C_SOLO:-}" ] && { (cd /tmp && K119_REPO="$REPO" bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE: K119 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-120)"; }

echo "== restaurado"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K119-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
