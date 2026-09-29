#!/bin/bash
# K102 · «QUE HACER» ES LO PRIMERO QUE SE LEE, TODO LO QUE DICE SALE DEL BACKEND, Y LO QUE DICE
#        DE SU EDAD ES VERDAD EN CADA INSTANTE
#
# QUE CONDENA ESTA RED, y por que cada brazo necesita un navegador de verdad:
#
#   B1 · DECIDE cabe ENTERO en el primer pliegue, a 1920x1080 y a 1440x900. Es una pregunta de
#        MAQUETA: un check que mirase el ORDEN del DOM daria VERDE con DECIDE empujado fuera de
#        la pantalla por una seccion que creciera encima.
#   B2 · el sesgo es el GLIFO MAS GRANDE del primer pliegue. Caber no basta.
#   B3 · cada campo que el sobre sirve con valor se pinta, con SU valor y con SU `source_key`.
#   B4 · ninguna celda declara una clave que el sobre NO sirva.
#   B5 · la regla del handoff, en las dos direcciones.
#   B7 · LA LECTURA DEL SCALP NO SE PRESENTA COMO DEL MARCO. En SWING y en LARGO el veredicto
#        servido es NO EVALUABLE con su motivo, y lo que sale del scalp vive en `lectura_scalp`
#        y se pinta en SU tarjeta, no dentro de DECIDE.
#   B8 · LA EDAD AVANZA SIN RECARGAR, y pasada `max_age_s` la pantalla lo dice. Un brazo de una
#        sola foto no puede ver esto: el defecto solo existe DESPUES del render.
#   B6 · errores de consola. HOY NO PUEDE CONDENAR y la salida lo dice.
#
# TRES COSAS QUE ESTA RED HACIA MAL Y QUE COSTARON UNA RONDA DE CORRECCION DEL OPERADOR:
#
#   · COMPARABA CONTRA UN SOBRE QUE NADIE PINTO. Pedia `/api/mesa/decide` una SEGUNDA vez para
#     tener con que comparar, y DECIDE cambia entre peticiones -20 de 20 parejas de
#     `/api/scalp/summary` separadas 2 s traen `edge` distinto, medido en 140 el 06:03Z-. Ahora
#     el patron es el CUERPO QUE LA PAGINA RECIBIO, leido por `Network.getResponseBody`.
#   · EXIGIA IGUALDAD A CUATRO DECIMALES sobre una pantalla que redondea al pintar, y condenaba
#     paginas impecables. Ahora se juzga A LA PRECISION CON QUE LA PANTALLA PINTA.
#   · MEDIA CON LA BARRA DE DESPLAZAMIENTO OCULTA, o sea en una ventana mas alta que la de
#     cualquier navegador de escritorio. Ahora mide con la barra puesta, y lo dice.
#
# A QUIEN JUZGA, Y LO DICE SIEMPRE. Por omision PRODUCCION; con `MESA_BASE=<url>`, el ARBOL.
# Y el tercer estado: si el ARBOL trae la ruta y produccion no la sirve, sale NO MEDIDO con
# motivo FALTA DESPLEGAR -no ROJO, que acusaria a un codigo que esta bien, y no VERDE-.
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

ACTIVO="${K102_ACTIVO:-BTC}"
# 18 s para que la ventana CUBRA la cadencia de refresco de la mesa (15 s) y el brazo B8 pueda
# exigir haber visto al menos un refresco. Con menos, ese tramo se declara no juzgado.
OBSERVA="${K102_OBSERVA:-18}"

# --- A QUIEN MIRO ----------------------------------------------------------------------
ARBOL_TIENE=0
grep -q '"/api/mesa/decide"' "$REPO/app/api.py" 2>/dev/null && ARBOL_TIENE=1

BASE="${MESA_BASE:-}"
CAB=""
if [ -n "$BASE" ]; then
  SUJETO="el ARBOL, servido en $BASE"
else
  SUJETO="PRODUCCION ($API_PROD)"
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
print("Authorization: Basic "
      + base64.b64encode(f"{cred[0]}:{cred[2]}".encode()).decode(), end="")
PY
  [ -s "$CAB" ] || { echo "NO MEDIDO: el netrc no dio credencial usable"; exit 2; }
  if ! "$B/bin/api" "/api/mesa/decide?symbol=BTCUSDT_PERP.A&frame=scalp" >/dev/null 2>&1; then
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

# --- LA MEDIDA -------------------------------------------------------------------------
# CON LA BARRA DE DESPLAZAMIENTO PUESTA: se juzga la ventana que tiene quien usa la mesa.
corre() {  # corre <ancho> <alto> <marco> <observa> <fichero>
  local w="$1" h="$2" m="$3" obs="$4" f="$5"
  if [ -n "$CAB" ]; then
    "$PY" "$SONDA" --base "$BASE" --marco "$m" --activo "$ACTIVO" \
      --ancho "$w" --alto "$h" --frio --repite 1 --espera 30 --observa "$obs" \
      --cabecera-fichero "$CAB" --salida "$f" >/dev/null 2>"$f.err"
  else
    "$PY" "$SONDA" --base "$BASE" --marco "$m" --activo "$ACTIVO" \
      --ancho "$w" --alto "$h" --frio --repite 1 --espera 30 --observa "$obs" \
      ${K102_CABECERA:+--cabecera "$K102_CABECERA"} --salida "$f" >/dev/null 2>"$f.err"
  fi
}

corre 1920 1080 scalp "$OBSERVA" "$TMP/g.json" || true
corre 1440 900  scalp 0          "$TMP/p.json" || true
corre 1920 1080 swing 0          "$TMP/sw.json" || true
corre 1920 1080 largo 0          "$TMP/lg.json" || true
for f in "$TMP/g.json" "$TMP/p.json" "$TMP/sw.json" "$TMP/lg.json"; do
  [ -s "$f" ] || { echo "NO MEDIDO: la sonda no midio ($(head -c 150 "$f.err" 2>/dev/null))"; exit 2; }
done

"$PY" - "$TMP/g.json" "$TMP/p.json" "$TMP/sw.json" "$TMP/lg.json" "$SUJETO" "$ACTIVO" <<'PY'
import json, sys

g, p, sw, lg = (json.load(open(x)) for x in sys.argv[1:5])
sujeto, activo = sys.argv[5], sys.argv[6]
fallos, lineas = [], []

def cosecha(d, rot):
    c = d.get("cosecha") or {}
    if not c or c.get("error"):
        print(f"NO MEDIDO: {rot}: la cosecha no se pudo leer ({(c or {}).get('error')})")
        raise SystemExit(2)
    return c

# --- B1 y B2 ---------------------------------------------------------------------------
for d, rot in ((g, "1920x1080"), (p, "1440x900")):
    c = cosecha(d, rot)
    pl = c.get("pliegue") or {}
    if not pl.get("visible"):
        fallos.append(f"B1 {rot}: #decide no se pinta (visible=false)")
    elif not pl.get("cabe_entero"):
        fallos.append(
            f"B1 {rot}: DECIDE NO cabe en el primer pliegue (top {pl.get('top')}, "
            f"bottom {pl.get('bottom')}, alto de ventana {pl.get('innerHeight')})"
        )
    else:
        lineas.append(
            f"{rot}: DECIDE entero en el pliegue (top {pl.get('top'):.0f} -> "
            f"bottom {pl.get('bottom'):.0f} de {pl.get('innerHeight')})"
        )
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

# --- B3 y B4 ---------------------------------------------------------------------------
r = g.get("reparto") or {}
if not g.get("sobre"):
    print(f"NO MEDIDO: no se pudo leer el sobre que recibio la pagina ({g.get('sobre_origen')})")
    raise SystemExit(2)
if r.get("n_casan", 0) == 0:
    print("NO MEDIDO: 0 campos emparejados: o el sobre no llego o el contrato de DOM cambio")
    raise SystemExit(2)
for x in (r.get("discrepan") or [])[:6]:
    fallos.append(
        f"B3: {x.get('campo')}: {x.get('motivo')} "
        f"(pantalla {x.get('pantalla', x.get('clave_pantalla'))!r} / "
        f"sobre {x.get('sobre', x.get('clave_sobre'))!r})"
    )
for x in (r.get("no_pintados") or [])[:6]:
    fallos.append(f"B3: {x.get('campo')} lo SIRVE el sobre y la pantalla no lo pinta")
for x in (r.get("sin_clave") or [])[:6]:
    fallos.append(f"B3: {x.get('campo')} se pinta SIN declarar su source_key")
if not (r.get("n_discrepan") or r.get("n_no_pintados") or r.get("n_sin_clave")):
    lineas.append(
        f"los {r['n_casan']} campos servidos casan pareja (source_key, valor), a la precision "
        "con que la pantalla los pinta"
    )
huerf = g.get("claves_de_pantalla_que_el_sobre_no_sirve") or []
if huerf:
    fallos.append(f"B4: la pantalla declara {len(huerf)} clave(s) que el sobre NO sirve: "
                  + " ".join(huerf[:5]))
else:
    lineas.append("ninguna celda declara una clave que el sobre no sirva")

# --- B5 --------------------------------------------------------------------------------
dec = (g.get("sobre") or {}).get("decide") or {}
ev = (dec.get("evaluable") or {}).get("value")
texto_sesgo = ((cosecha(g, "1920x1080").get("sesgo") or {}).get("texto") or "").strip()
if ev is None:
    fallos.append("B5: el sobre no trae `decide.evaluable`: la regla de <70 no se puede juzgar")
elif ev is False and texto_sesgo != "NO EVALUABLE":
    fallos.append(f"B5: el sobre dice evaluable=false y la pantalla pone {texto_sesgo!r}")
elif ev is True and texto_sesgo == "NO EVALUABLE":
    fallos.append("B5: el sobre dice evaluable=true y la pantalla pone NO EVALUABLE")
else:
    lineas.append(
        f"la regla del handoff se cumple: data_confidence "
        f"{(dec.get('data_confidence') or {}).get('value')} contra umbral "
        f"{(dec.get('evaluable') or {}).get('threshold')} -> sesgo {texto_sesgo!r}"
    )

# --- B7 · LA LECTURA DEL SCALP NO ES EL VEREDICTO DE OTRO MARCO ------------------------
# Las claves que salen de la lectura del scalp. Si alguna aparece dentro de `decide` en un
# marco que no es scalp, ese marco esta publicando la lectura del scalp como suya.
DEL_SCALP = ("state", "reason", "confidence", "edge", "evidence", "confirms",
             "invalidates", "invalidation_level", "horizon")
for d, marco in ((sw, "swing"), (lg, "largo")):
    sobre = d.get("sobre") or {}
    if not sobre:
        fallos.append(f"B7 {marco}: no se pudo leer el sobre que recibio la pagina")
        continue
    dd = sobre.get("decide") or {}
    bias = (dd.get("bias") or {})
    intrusas = [k for k in DEL_SCALP if k in dd]
    if bias.get("value") != "NO EVALUABLE":
        fallos.append(
            f"B7 {marco}: el veredicto servido es {bias.get('value')!r}, y la lectura del "
            f"operador es del SCALP: en {marco.upper()} tiene que ser NO EVALUABLE"
        )
    elif bias.get("source_key") != "mesa.decide.frame":
        fallos.append(
            f"B7 {marco}: sale NO EVALUABLE pero por {bias.get('source_key')!r}, no por el "
            "marco: el motivo que se ensena no seria el de verdad"
        )
    elif intrusas:
        fallos.append(
            f"B7 {marco}: {len(intrusas)} clave(s) de la lectura del scalp dentro de `decide`: "
            + " ".join(intrusas)
        )
    elif not sobre.get("lectura_scalp"):
        fallos.append(f"B7 {marco}: no se sirve `lectura_scalp`: la lectura se pierde en vez "
                      "de ensenarse como lo que es")
    else:
        # y en la PANTALLA: sus celdas tienen que estar fuera de #decide
        c = cosecha(d, marco)
        dentro = [x["campo"] for x in (c.get("parejas") or [])
                  if x["campo"].split("[")[0] in DEL_SCALP]
        if dentro:
            fallos.append(
                f"B7 {marco}: la pantalla pinta DENTRO de DECIDE {len(dentro)} celda(s) de la "
                "lectura del scalp: " + " ".join(dentro[:5])
            )
        else:
            lineas.append(
                f"{marco}: veredicto NO EVALUABLE por el marco, la lectura del scalp va aparte "
                f"({len(sobre['lectura_scalp'])} claves en `lectura_scalp`) y no se pinta "
                "dentro de DECIDE"
            )

# --- B8 · LA EDAD AVANZA SIN RECARGAR ---------------------------------------------------
obs = g.get("observacion") or {}
m = obs.get("muestras") or []
if len(m) < 3:
    fallos.append("B8: no hay observacion suficiente para juzgar si la edad avanza")
else:
    edades = [x.get("edad_s") for x in m if x.get("edad_s") is not None]
    if len(edades) < 3:
        fallos.append("B8: la pantalla no publica una edad legible durante la observacion")
    else:
        # avanza si sube en algun tramo. Un RESET a la baja es legitimo: es un refresco.
        subidas = sum(1 for a, b in zip(edades, edades[1:]) if b > a)
        if subidas == 0:
            fallos.append(
                f"B8: la edad NO avanza en {obs.get('segundos')} s sin recargar: se quedo en "
                f"{edades[0]} s. La pantalla dice una frescura que no tiene"
            )
        else:
            refrescos = max(x.get("peticiones_decide") or 0 for x in m)
            rancios = sum(1 for x in m if x.get("dice_rancio"))
            # QUE LA EDAD AVANCE NO BASTA. Una mesa que cuenta los segundos pero no vuelve a
            # preguntar es HONESTA y a la vez inutil: dice bien que lleva una hora sin
            # refrescar, y sigue sin refrescar. Si la ventana de observacion cubre la cadencia,
            # se exige haber visto al menos un refresco; si no la cubre, se DECLARA que este
            # tramo no se ha podido juzgar en vez de darlo por bueno.
            if obs.get("segundos", 0) >= 16:
                if refrescos < 1:
                    fallos.append(
                        f"B8: en {obs.get('segundos')} s la pantalla NO volvio a pedir DECIDE "
                        "ni una vez: la edad avanza pero el dato no se renueva"
                    )
                else:
                    lineas.append(
                        f"la edad avanza sin recargar: {edades[0]} -> {edades[-1]} s en "
                        f"{obs.get('segundos')} s ({subidas} subidas, {refrescos} refresco(s) "
                        f"de DECIDE, {rancios} de {len(m)} muestras dicen RANCIO)"
                    )
            else:
                lineas.append(
                    f"la edad avanza sin recargar: {edades[0]} -> {edades[-1]} s en "
                    f"{obs.get('segundos')} s ({subidas} subidas, {rancios} de {len(m)} "
                    f"muestras dicen RANCIO). El REFRESCO no se juzga: la observacion "
                    f"({obs.get('segundos')} s) no cubre la cadencia"
                )
        # y si alguna muestra paso del tope, TIENE que decirlo
        tope = (g.get("sobre") or {}).get("max_age_s")
        if tope is not None:
            malas = [x for x in m
                     if x.get("edad_s") is not None and x["edad_s"] > float(tope)
                     and not x.get("dice_rancio")]
            if malas:
                fallos.append(
                    f"B8: {len(malas)} muestra(s) por encima del tope ({tope} s) sin decir "
                    f"RANCIO; la peor, {max(x['edad_s'] for x in malas)} s"
                )

# --- B6 · SIN PODER CONDENAR -----------------------------------------------------------
errc = g.get("errores_consola") or []
sin_poder = None
if errc:
    fallos.append(f"B6: la mesa dejo {len(errc)} error(es) de consola: {errc[0][:80]}")
else:
    sin_poder = ("B6 (errores de consola): 0, y NO se cuenta como aprobado. Este brazo no ha "
                 "demostrado que pueda condenar en esta corrida")

# --- EL VEREDICTO, CON SU ALCANCE -------------------------------------------------------
print(f"K102 · lo que juzgo: {sujeto}")
print(f"  alcance: activo {activo} · marcos scalp (1920x1080 y 1440x900), swing y largo "
      f"(1920x1080) · {g.get('barra_de_desplazamiento')}")
print(f"  el patron de comparacion: {g.get('sobre_origen')}")
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
