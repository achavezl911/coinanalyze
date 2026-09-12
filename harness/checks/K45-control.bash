#!/usr/bin/env bash
# CONTROL DE K45. Ejercita el CRITERIO -sobre todo el de las excepciones, que es la puerta por
# la que se fuerza el verde- con la puerta `K45_SONDA`, sin pagar los ~156 s de la sonda.
# Los tres controles de campo -regresion contra el arbol de antes de la FASE 1, condena con
# plantado real, y discriminacion- estan en entregas/20260912-*-tarjeta-perdida.md y se
# corrieron con la sonda de verdad. Esto guarda el criterio en cada `verify`.
set -uo pipefail
R=${REPO:-/srv/coinanalyze/repo}
CHK="$R/harness/checks/K45-la-tarjeta-sin-dato.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; mal=0

# la familia FOTO sale de K43; el doble de sonda se construye con ESA lista, no con una mia.
mapfile -t FOTO < <("$R/.venv/bin/python" - "$R/harness/checks/K43-foto-unica.sh" <<'PY'
import re, sys
t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
a = re.search(r'^ASIGNACION="\n(.*?)^"$', t, re.S | re.M).group(1)
for r in sorted(x for x, f in re.findall(r"(/api/[\w/\-]+)=([A-Z]+)", a) if f == "FOTO"):
    print(r)
PY
)
N=${#FOTO[@]}
# LA RUTA DE PRUEBA SE TOMA DE LA LISTA, NO SE TECLEA -y su nombre NO se escribe tampoco en
# este comentario-. Dos motivos, los dos medidos:
#   1 · bin/arquitectura casa el nombre de una ruta ALLA DONDE APAREZCA, asi que teclearla
#       aqui acredita a este control como consumidor suyo y mueve su ficha. Medido: la
#       primera version de este fichero movio una ficha de ARQUITECTURA sin que el panel
#       hubiera cambiado. La cabecera de K31 ya avisaba de esto y aun asi cai.
#   2 · si manana esa ruta deja de ser FOTO, el control se cae solo en vez de mentir.
RUTA="${FOTO[0]}"
ELEM="zz-hueco-de-prueba"

sonda() {  # $@ = rutas que NO llegan
  local fuera=" $* "
  local llegan=()
  for r in "${FOTO[@]}"; do
    case "$fuera" in *" $r "*) continue ;; esac
    llegan+=("$r")
  done
  "$R/.venv/bin/python" - "$T/sonda.json" "${llegan[@]}" <<'PY'
import json, sys
json.dump({"control_determinista": True, "payloads_con_datos": 22, "secciones": 9,
           "llegan_a_la_pantalla": [], "llegan_por_el_sobre": sys.argv[2:]},
          open(sys.argv[1], "w"))
PY
}

caso() {  # $1 nombre · $2 rc esperado · $3 patron esperado en la salida
  local nombre="$1" esp="$2" pat="$3"
  local out; out=$(K45_SONDA="$T/sonda.json" K45_EXC="$T/exc.tsv" K45_HTML="$T/index.html" \
                   REPO="$R" bash "$CHK" 2>&1); local rc=$?
  if [ "$rc" = "$esp" ] && printf '%s' "$out" | grep -qE "$pat"; then
    printf '  [ok   ] %-52s rc=%s\n' "$nombre" "$rc"; ok=$((ok+1))
  else
    printf '  [FALLA] %-52s rc=%s (esperaba %s / %s)\n' "$nombre" "$rc" "$esp" "$pat"
    printf '          %s\n' "$(printf '%s' "$out" | head -c 200)"; mal=$((mal+1))
  fi
}

printf '<html><body><div id="otro-hueco"></div></body></html>\n' > "$T/index.html"
: > "$T/exc.tsv"

# V1 · el verde de verdad: llegan todas
sonda
caso "V1 llegan las $N: VERDE" 0 "las $N rutas FOTO llegan al operador"

# V2 · CONDENA Y NOMBRA. Sin este, el check no sirve para nada.
sonda "$RUTA"
caso "V2 una sin dato: ROJO y la NOMBRA" 1 "SIN DATO: $RUTA"

# V3 · la excepcion vale SOLO si su hueco no esta en la pagina
printf '%s\t%s\tretirada, cita de prueba\n' "$RUTA" "$ELEM" > "$T/exc.tsv"
caso "V3 excepcion con el hueco AUSENTE: VERDE" 0 "excepcion VIVA"

# V4 · EL CASO QUE SOSTIENE TODO EL DISENO: se devuelve el hueco y la excusa se cae sola.
printf '<html><body><div id="%s"></div></body></html>\n' "$ELEM" > "$T/index.html"
caso "V4 el hueco VUELVE: excepcion ANULADA y condena" 1 "ANULADA"

# V5 · la otra direccion: excusa rancia de algo que ya llega
printf '<html><body></body></html>\n' > "$T/index.html"
sonda
caso "V5 excepcion HUERFANA -su ruta ya llega-" 1 "HUERFANA"

# V6 · CONTROL POSITIVO DEL INSTRUMENTO: si no llega ninguna, es que no he medido
: > "$T/exc.tsv"
sonda "${FOTO[@]}"
caso "V6 no llega NINGUNA: NO MEDIDO, no $N condenas" 2 "ninguna de las $N rutas FOTO"

# V7 · una excepcion mal escrita no se ignora en silencio
sonda "$RUTA"
printf '%s\tsolo-dos-campos\n' "$RUTA" > "$T/exc.tsv"
caso "V7 excepcion sin cita: NO MEDIDO" 2 "mal formadas"

# V8 · la puerta misma tiene guardia
: > "$T/exc.tsv"
out=$(K45_SONDA="$T/no-existe.json" REPO="$R" bash "$CHK" 2>&1); rc=$?
if [ "$rc" = 2 ]; then printf '  [ok   ] %-52s rc=2\n' "V8 puerta a un fichero ausente: NO MEDIDO"; ok=$((ok+1))
else printf '  [FALLA] V8 puerta a un fichero ausente rc=%s\n' "$rc"; mal=$((mal+1)); fi

echo
echo "$ok de $((ok+mal)) pasan · $mal fallan"
[ "$mal" = 0 ]
