#!/bin/bash
# K102 · «QUE HACER» ES LO PRIMERO QUE SE LEE, Y TODO LO QUE DICE SALE DEL BACKEND
#
# QUE CONDENA ESTA RED (campana 130). Dos promesas del producto, y las dos se podian romper sin
# que nada se quejara:
#
#   1 · que DECIDE sea LO PRIMERO que se lee, sin desplazarse, a 1920x1080 y a 1440x900.
#       Se mide con Chromium porque es una pregunta de MAQUETA: jsdom no maqueta, y un check
#       que solo mirase el ORDEN del DOM daria VERDE con DECIDE empujado fuera de la pantalla
#       por una seccion que creciera encima.
#   2 · que cada cosa que DECIDE ensena salga de una clave del backend QUE SE PUEDA NOMBRAR.
#       No se comprueba buscando el valor por la pantalla -«Long» esta en `bias`, en `state`
#       («Long Pullback») y en `invalidates_long`, y una coincidencia por homonimia absuelve
#       sin medir (A41/A42)-: se comprueba la PAREJA (source_key, valor) celda a celda contra
#       el sobre servido. Y como cada entrada de lista lleva SU clave al lado, un INTERCAMBIO
#       entre dos etiquetas que ya estan en pantalla tampoco cuela (A43).
#
# A QUIEN JUZGA, Y LO DICE SIEMPRE. Por omision juzga PRODUCCION. Con `MESA_BASE=<url>` juzga
# lo que sirva esa url -el ARBOL-. El veredicto NOMBRA cual de los dos ha mirado, porque desde
# la 130 hay DOS pantallas y dos arboles, y «lo mide la sonda» ya no identifica a nadie.
#
# Y EL TERCER ESTADO, que aqui hace falta de verdad: si el ARBOL ya trae la ruta y PRODUCCION
# no la sirve, esto NO es ROJO -el codigo esta bien- ni VERDE -no se ha medido la pantalla-:
# es NO MEDIDO con el motivo «FALTA DESPLEGAR». No condenar no es dar verde.
set -u
B=/srv/coinanalyze/harness
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # ABSOLUTA ANTES de cualquier cd (A56)
SONDA="$D/K102-mesa.py"
. "$B/env"
REPO="${REPO:-/srv/coinanalyze/repo}"
PY="$REPO/.venv/bin/python"

[ -x "$PY" ]     || { echo "NO MEDIDO: no hay interprete en $PY"; exit 2; }
[ -r "$SONDA" ]  || { echo "NO MEDIDO: falta la sonda $SONDA"; exit 2; }

TMP="$(mktemp -d)" || exit 2
trap 'rm -rf "$TMP"' EXIT INT TERM

# --- A QUIEN MIRO ----------------------------------------------------------------------
# El ARBOL declara la ruta? Se mira en el codigo, no se supone.
ARBOL_TIENE=0
grep -q '"/api/mesa/decide"' "$REPO/app/api.py" 2>/dev/null && ARBOL_TIENE=1

BASE="${MESA_BASE:-}"
if [ -n "$BASE" ]; then
  SUJETO="el ARBOL, servido en $BASE"
else
  SUJETO="PRODUCCION ($API_PROD)"
  # Produccion va detras de nginx con auth_basic: la cabecera se construye en EJECUCION desde
  # el netrc y se deja en un fichero modo 600. Asi no aparece en la linea de ordenes ni en el
  # entorno del proceso (A55).
  [ -r "$NETRC" ] || { echo "NO MEDIDO: falta $NETRC y produccion pide auth_basic"; exit 2; }
  CAB="$TMP/cab"; : > "$CAB"; chmod 600 "$CAB"
  "$PY" - "$NETRC" > "$CAB" <<'PY' || { echo "NO MEDIDO: no se pudo leer el netrc"; exit 2; }
import base64, netrc, sys
n = netrc.netrc(sys.argv[1])
cred = None
for h in n.hosts:
    cred = n.authenticators(h)
    if cred:
        break
if not cred:
    raise SystemExit(1)
par = f"{cred[0]}:{cred[2]}".encode()
print("Authorization: Basic " + base64.b64encode(par).decode(), end="")
PY
  [ -s "$CAB" ] || { echo "NO MEDIDO: el netrc no dio credencial usable"; exit 2; }

  # PRODUCCION SIRVE LA RUTA? Se pregunta por el canal, no por la sonda.
  code=$("$B/bin/api" "/api/mesa/decide?symbol=BTCUSDT_PERP.A&frame=scalp" >/dev/null 2>&1; echo $?)
  if [ "$code" != "0" ]; then
    if [ "$ARBOL_TIENE" = "1" ]; then
      echo "NO MEDIDO: FALTA DESPLEGAR. El arbol declara /api/mesa/decide (app/api.py) y"
      echo "  $SUJETO no la sirve todavia. El codigo no esta mal: no esta desplegado."
      echo "  para juzgar el arbol:  MESA_BASE=http://127.0.0.1:PUERTO $0"
      exit 2
    fi
    echo "NO MEDIDO: ni el arbol ni $SUJETO traen /api/mesa/decide"
    exit 2
  fi
  BASE="$API_PROD"
fi

# --- LA MEDIDA · dos tamanos, los dos del encargo --------------------------------------
corre() {  # corre <ancho> <alto> <fichero>
  local w="$1" h="$2" f="$3"
  if [ -n "${CAB:-}" ]; then
    "$PY" "$SONDA" --base "$BASE" --marco scalp --activo BTC \
      --ancho "$w" --alto "$h" --frio --repite 1 --espera 30 \
      --cabecera-fichero "$CAB" --salida "$f" >/dev/null 2>"$f.err"
  else
    "$PY" "$SONDA" --base "$BASE" --marco scalp --activo BTC \
      --ancho "$w" --alto "$h" --frio --repite 1 --espera 30 \
      ${K102_CABECERA:+--cabecera "$K102_CABECERA"} --salida "$f" >/dev/null 2>"$f.err"
  fi
}

corre 1920 1080 "$TMP/g.json" || true
corre 1440 900  "$TMP/p.json" || true
for f in "$TMP/g.json" "$TMP/p.json"; do
  [ -s "$f" ] || { echo "NO MEDIDO: la sonda no midio ($(head -c 150 "$f.err" 2>/dev/null))"; exit 2; }
done

# --- EL VEREDICTO ----------------------------------------------------------------------
"$PY" - "$TMP/g.json" "$TMP/p.json" "$SUJETO" <<'PY'
import json, sys

g = json.load(open(sys.argv[1]))
p = json.load(open(sys.argv[2]))
sujeto = sys.argv[3]
fallos, lineas = [], []

def cosecha(d, rot):
    c = d.get("cosecha") or {}
    if not c or c.get("error"):
        return None, f"{rot}: la cosecha no se pudo leer ({(c or {}).get('error')})"
    return c, None

# BRAZO 1 · DECIDE CABE ENTERO EN EL PRIMER PLIEGUE, en los dos tamanos.
for d, rot in ((g, "1920x1080"), (p, "1440x900")):
    c, err = cosecha(d, rot)
    if err:
        print(f"NO MEDIDO: {err}")
        raise SystemExit(2)
    pl = c.get("pliegue") or {}
    if not pl.get("visible"):
        fallos.append(f"B1 {rot}: #decide no se pinta (visible=false)")
    elif not pl.get("cabe_entero"):
        fallos.append(
            f"B1 {rot}: DECIDE NO cabe en el primer pliegue "
            f"(top {pl.get('top')}, bottom {pl.get('bottom')}, alto de ventana {pl.get('innerHeight')})"
        )
    else:
        lineas.append(
            f"{rot}: DECIDE entero en el pliegue (top {pl.get('top'):.0f} -> "
            f"bottom {pl.get('bottom'):.0f} de {pl.get('innerHeight')})"
        )

# BRAZO 2 · EL SESGO ES EL GLIFO MAS GRANDE DEL PRIMER PLIEGUE. Caber no basta: si DECIDE cabe
# pero algo lo grita mas alto arriba, lo primero que se lee ya no es DECIDE.
for d, rot in ((g, "1920x1080"), (p, "1440x900")):
    c, _ = cosecha(d, rot)
    s = c.get("sesgo") or {}
    mayor = c.get("letra_mayor_px") or 0
    if not s:
        fallos.append(f"B2 {rot}: no hay #decide-sesgo")
    elif not s.get("dentro"):
        fallos.append(f"B2 {rot}: el sesgo no esta dentro del primer pliegue")
    elif (s.get("px") or 0) < mayor:
        fallos.append(
            f"B2 {rot}: el sesgo ({s.get('px')}px) NO es el texto mas grande del pliegue "
            f"({mayor}px en {c.get('letra_mayor_texto')!r})"
        )
    else:
        lineas.append(f"{rot}: el sesgo es el glifo mayor del pliegue ({s.get('px')}px)")

# BRAZO 3 · CADA VALOR DE DECIDE SALE DEL BACKEND. Pareja (source_key, valor) contra el sobre.
r = g.get("reparto") or {}
if r.get("n_casan", 0) == 0:
    # UN CERO EN LAS DOS DIRECCIONES NO ES UN APROBADO (A35): si no caso NADA, no he medido.
    print("NO MEDIDO: 0 campos emparejados: o el sobre no llego o el contrato de DOM cambio")
    raise SystemExit(2)
if r.get("n_discrepan"):
    for x in r["discrepan"][:6]:
        fallos.append(f"B3: {x.get('campo')}: {x.get('motivo')} "
                      f"(pantalla {x.get('pantalla', x.get('clave_pantalla'))!r} / "
                      f"sobre {x.get('sobre', x.get('clave_sobre'))!r})")
if r.get("n_no_pintados"):
    for x in r["no_pintados"][:6]:
        fallos.append(f"B3: {x.get('campo')} lo SIRVE el sobre y la pantalla no lo pinta")
if r.get("n_sin_clave"):
    for x in r["sin_clave"][:6]:
        fallos.append(f"B3: {x.get('campo')} se pinta SIN declarar su source_key")
if not (r.get("n_discrepan") or r.get("n_no_pintados") or r.get("n_sin_clave")):
    lineas.append(f"los {r['n_casan']} campos servidos casan pareja (source_key, valor)")

# BRAZO 4 · NINGUNA CLAVE DE PANTALLA QUE EL SOBRE NO SIRVA. Es la otra direccion: una celda
# que declara una procedencia inventada.
huerf = g.get("claves_de_pantalla_que_el_sobre_no_sirve") or []
if huerf:
    fallos.append(f"B4: la pantalla declara {len(huerf)} clave(s) que el sobre NO sirve: "
                  + " ".join(huerf[:5]))
else:
    lineas.append("ninguna celda declara una clave que el sobre no sirva")

# BRAZO 5 · LA REGLA DEL HANDOFF. Si el sobre dice que no es evaluable, la pantalla dice
# NO EVALUABLE; y si dice que si, NO puede decirlo.
sobre = g.get("sobre") or {}
dec = (sobre or {}).get("decide") or {}
ev = (dec.get("evaluable") or {}).get("value")
c, _ = cosecha(g, "1920x1080")
texto_sesgo = ((c.get("sesgo") or {}).get("texto") or "").strip()
if ev is None:
    fallos.append("B5: el sobre no trae `decide.evaluable`: la regla de <70 no se puede juzgar")
elif ev is False and texto_sesgo != "NO EVALUABLE":
    fallos.append(f"B5: el sobre dice evaluable=false y la pantalla pone {texto_sesgo!r}")
elif ev is True and texto_sesgo == "NO EVALUABLE":
    fallos.append("B5: el sobre dice evaluable=true y la pantalla pone NO EVALUABLE")
else:
    umbral = (dec.get("evaluable") or {}).get("threshold")
    dc = (dec.get("data_confidence") or {}).get("value")
    lineas.append(f"la regla del handoff se cumple: data_confidence {dc} contra umbral "
                  f"{umbral} -> sesgo {texto_sesgo!r}")

# BRAZO 6 · SIN PODER CONDENAR, Y SE DICE. Este brazo mira que la mesa NO deje errores de
# consola. Hoy no puede condenar nada: la mesa no escribe en consola ni en el peor camino, asi
# que un 0 aqui no distingue «limpio» de «no he mirado». Se declara y NO se cuenta como
# aprobado -es A35 escrito en la propia salida-.
errc = g.get("errores_consola") or []
if errc:
    fallos.append(f"B6: la mesa dejo {len(errc)} error(es) de consola: {errc[0][:80]}")
    sin_poder = None
else:
    sin_poder = ("B6 (errores de consola): 0, y NO se cuenta como aprobado. Este brazo no ha "
                 "demostrado que pueda condenar en esta corrida")

print(f"K102 · lo que juzgo: {sujeto}")
for x in lineas:
    print(f"  {x}")
if sin_poder:
    print(f"  SIN PODER CONDENAR · {sin_poder}")
if fallos:
    print(f"  {len(fallos)} hallazgo(s):")
    for x in fallos:
        print(f"   - {x}")
    raise SystemExit(1)
raise SystemExit(0)
PY
