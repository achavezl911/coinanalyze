#!/usr/bin/env bash
# K08-control · el guardia de corte de K08, ¿puede dispararse?
#
#     bash harness/checks/K08-control.bash
#
# POR QUE EXISTE. Hasta el 2026-09-10 K08 pedia /api/healthz **con `TODO=1`** y ademas guardaba
# contra la marca `[CORTADO:` que deja el canal al truncar. Las dos mitades se cancelaban:
# `_corta` linea 4 es `[ "${TODO:-0}" = "1" ] && exec cat`, o sea que con TODO=1 no hay corte
# nunca y la marca no puede aparecer. **Un guardia inalcanzable no es proteccion: es adorno**, y
# encima su comentario decia que era «el mismo guardia de K05:138» -cierto del codigo y falso
# del patron, porque K05:127 pide SIN TODO=1-.
#
# EL CORTE SE INDUCE POR EL UNICO CAMINO QUE HAY, y esto se midio antes de escribir el control:
# `_corta` sourcea `harness/env` ANTES de leer MAX_BYTES, y `env:20` lo fija en 8000. Asi que
# `MAX_BYTES=100 _corta` NO corta -medido: 1000 B entran y 1000 B salen-. La unica forma de que
# la marca aparezca es un CUERPO mayor que el techo.
#
# Y EL CORTE LO HACE EL `_corta` DE VERDAD, no un `printf` que imprime la marca. Si el doble
# escribiera la marca a mano, esto probaria que K08 sabe leer una cadena, no que sabe ver un
# corte (A36: el control tiene que moverse ANTE EL FENOMENO que dice medir).
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K08-que-base.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
DIR=$(mktemp -d) || exit 2
[ "${K08_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

comprueba() {  # $1 = etiqueta   $2 = si|no
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-56s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-56s\n' "$1"; fi
}

# --- EL CANAL, ANTES DE NADA -------------------------------------------------------------
base=$(/srv/coinanalyze/harness/bin/api /api/healthz 2>&1) || true
case "$base" in
  *status*|*database*) ;;
  *) echo "NO MEDIDO: /api/healthz no contesta, asi que no hay cuerpo que cortar"
     exit 2 ;;
esac
BYTES=$(printf '%s' "$base" | wc -c)
printf 'K08-control · healthz sirve %s B · techo del canal MAX_BYTES=8000\n\n' "$BYTES"

# monta un arnes de mentira cuyo bin/api devuelve el cuerpo que se le diga, PASADO POR EL
# _corta DE VERDAD. $1 = dir, $2 = fichero con el cuerpo
monta() {
  rm -rf "$1"; mkdir -p "$1/bin"
  printf '. /srv/coinanalyze/harness/env\n' > "$1/env"
  { printf '#!/bin/bash\n'
    printf 'printf "LLAMADO\\n" >> "%s/senal"\n' "$1"
    printf 'cat "%s" | /srv/coinanalyze/harness/bin/_corta\n' "$2"
  } > "$1/bin/api"
  chmod +x "$1/bin/api"
  : > "$1/senal"
}
copia() {  # $1 = dir del arnes falso  [$2 = 1 para re-poner el TODO=1 viejo]
  local f="$1/K08.sh"
  sed "s#^B=/srv/coinanalyze/harness; . \"\$B/env\"#B=$1; . \"\$B/env\"#" "$CHK" > "$f"
  if cmp -s "$CHK" "$f"; then echo "SED-NO-MORDIO" >&2; return 1; fi
  if [ "${2:-0}" = 1 ]; then
    sed -i 's#^cuerpo=\$("\$B/bin/api" /api/healthz 2>/dev/null)#cuerpo=$(TODO=1 "$B/bin/api" /api/healthz 2>/dev/null)#' "$f"
    grep -q 'TODO=1 "\$B/bin/api"' "$f" || { echo "SED-TODO-NO-MORDIO" >&2; return 1; }
  fi
  printf '%s\n' "$f"
}

# los dos cuerpos: uno que cabe y otro que no. El grande es healthz de verdad con un relleno,
# asi que sigue siendo el MISMO JSON que K08 sabe leer -si el corte no ocurriera, pasaria-.
CABE="$DIR/cabe.json"; NOCABE="$DIR/nocabe.json"
printf '%s' "$base" > "$CABE"
python3 - "$CABE" "$NOCABE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["relleno_del_control"] = "z" * 6000
open(sys.argv[2], "w").write(json.dumps(d))
PY
printf 'cuerpo que CABE  : %s B\ncuerpo que NO cabe: %s B\n\n' \
  "$(wc -c < "$CABE")" "$(wc -c < "$NOCABE")"

echo "EL GUARDIA · con la forma de HOY (sin TODO=1) tiene que DISPARARSE"
monta "$DIR/g" "$NOCABE"
f=$(copia "$DIR/g") || exit 2
out=$(timeout -k 5 120 bash "$f" 2>&1); rc=$?
comprueba "G0 el plantado ocurrio (bin/api de mentira llamado)" \
  "$([ -s "$DIR/g/senal" ] && echo si || echo no)"
comprueba "G1 el cuerpo llega CORTADO por el _corta de verdad" \
  "$(printf '%s' "$(cat "$NOCABE" | /srv/coinanalyze/harness/bin/_corta)" | grep -q 'CORTADO:' && echo si || echo no)"
comprueba "G2 K08 declara NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "G3 y NOMBRA el transporte, no a la API" \
  "$(printf '%s' "$out" | grep -q 'el transporte corto la respuesta' && echo si || echo no)"
printf '        salida: %s\n' "$(printf '%s' "$out" | head -1 | cut -c1-120)"

echo
echo "EL NEGATIVO · sin el, lo de arriba seria una maquina de NO MEDIDO"
monta "$DIR/n" "$CABE"
f=$(copia "$DIR/n") || exit 2
out=$(timeout -k 5 120 bash "$f" 2>&1); rc=$?
comprueba "N1 con un cuerpo que cabe, K08 mide y no se queja (rc=$rc)" \
  "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "N2 y no menciona ningun corte" \
  "$(printf '%s' "$out" | grep -q 'CORTADO\|transporte corto' && echo no || echo si)"
printf '        salida: %s\n' "$(printf '%s' "$out" | head -1 | cut -c1-120)"

echo
echo "LA REGRESION · con el TODO=1 de antes, el MISMO cuerpo grande NO dispara el guardia"
monta "$DIR/v" "$NOCABE"
f=$(copia "$DIR/v" 1) || exit 2
out=$(timeout -k 5 120 bash "$f" 2>&1); rc=$?
comprueba "R1 con TODO=1 el guardia NO se dispara (rc=$rc, no 2)" \
  "$([ "$rc" != 2 ] && echo si || echo no)"
comprueba "R2 y por eso el cuerpo llega ENTERO, sin marca" \
  "$(printf '%s' "$out" | grep -q 'transporte corto' && echo no || echo si)"
printf '        salida: %s\n' "$(printf '%s' "$out" | head -1 | cut -c1-120)"
printf '        ESTO es lo que se arreglo: el mismo cuerpo, el mismo guardia, y con TODO=1 mudo.\n'

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
