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
#   B5 · la regla del handoff, en las dos direcciones, sobre el RAYADO de la tarjeta. Que la
#        PALABRA siga ese mismo umbral lo juzga B9, que la recomputa entera.
#   B7 · LA LECTURA DEL SCALP NO SE PRESENTA COMO DEL MARCO. En SWING y en LARGO el veredicto
#        servido es NO EVALUABLE con su motivo, y lo que sale del scalp vive en `lectura_scalp`
#        y se pinta en SU tarjeta, no dentro de DECIDE.
#   B8 · LA EDAD AVANZA SIN RECARGAR, y pasada `max_age_s` la pantalla lo dice. Un brazo de una
#        sola foto no puede ver esto: el defecto solo existe DESPUES del render.
#   B9 · LA PALABRA DICE LA DECISION DEL SISTEMA. Ninguno de los ocho de arriba puede ver esto,
#        y eso es el defecto que costo la campana 132: B3 prueba que la pantalla pinta FIEL la
#        clave que dice pintar, y una clave fielmente pintada puede seguir siendo la palabra
#        equivocada (A83). B9 RECOMPUTA la palabra con la regla completa -el umbral del handoff
#        que el sobre sirve, y `classify_signal_observation` de `app/signal_ledger.py` IMPORTADA-
#        sobre las cifras de LA MISMA respuesta, y la contrasta con la servida Y con la pintada.
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

# EL ACTIVO DE LOS BRAZOS PROFUNDOS (B3, B4, B5, B7, B8), que piden una observacion larga.
ACTIVO="${K102_ACTIVO:-SOL}"

# EL PLIEGUE SE JUZGA EN LOS TRES ACTIVOS, Y ANTES NO (A81).
#
# Esto decia: «se juzga UN activo y se elige el de menos holgura, SOL, con 49 px medidos el
# 2026-09-29 sobre las 18 vistas». Los 49 px se midieron en el ESPEJO, congelado desde el
# 08-13. En PRODUCCION, a las 11:28Z del 09-29, SOL tenia 157 px y BTC 41 -859 de 900 en scalp
# 1440x900-: la holgura depende del largo de `scalp.reason` y de la zona, y las dos dependen
# del mercado. O sea que el check miraba el HOLGADO y declaraba que miraba el estrecho.
# El peor caso de una magnitud que se mueve con el mercado no es un SUJETO, es una HORA: se
# juzgan los TRES, y el margen de cada uno se publica.
ACTIVOS="${K102_ACTIVOS:-BTC ETH SOL}"
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
corre_a() {  # corre_a <activo> <ancho> <alto> <marco> <observa> <fichero>
  local a="$1" w="$2" h="$3" m="$4" obs="$5" f="$6"
  if [ -n "$CAB" ]; then
    "$PY" "$SONDA" --base "$BASE" --marco "$m" --activo "$a" \
      --ancho "$w" --alto "$h" --frio --repite 1 --espera 30 --observa "$obs" \
      --cabecera-fichero "$CAB" --salida "$f" >/dev/null 2>"$f.err"
  else
    "$PY" "$SONDA" --base "$BASE" --marco "$m" --activo "$a" \
      --ancho "$w" --alto "$h" --frio --repite 1 --espera 30 --observa "$obs" \
      ${K102_CABECERA:+--cabecera "$K102_CABECERA"} --salida "$f" >/dev/null 2>"$f.err"
  fi
}

corre() {  # corre <ancho> <alto> <marco> <observa> <fichero>   (el activo de los profundos)
  corre_a "$ACTIVO" "$1" "$2" "$3" "$4" "$5"
}

# LOS TRES MARCOS A LOS DOS TAMANOS. Antes solo se juzgaba el pliegue en SCALP, y en swing y
# largo se miraba la palabra pero NO el pliegue: por ahi se colo que DECIDE saliera del primer
# pliegue en esos dos marcos -bottom 1145 en largo/BTC a 1440x900- sin que nada se quejara.
# El criterio del encargo es «a 1920x1080 y a 1440x900», y no dice «en scalp».
corre 1920 1080 scalp "$OBSERVA" "$TMP/g.json"  || true
corre 1440 900  scalp 0          "$TMP/p.json"  || true
corre 1920 1080 swing 0          "$TMP/sw.json" || true
corre 1440 900  swing 0          "$TMP/swp.json" || true
corre 1920 1080 largo 0          "$TMP/lg.json" || true
corre 1440 900  largo 0          "$TMP/lgp.json" || true
for f in "$TMP/g.json" "$TMP/p.json" "$TMP/sw.json" "$TMP/swp.json" "$TMP/lg.json" "$TMP/lgp.json"; do
  [ -s "$f" ] || { echo "NO MEDIDO: la sonda no midio ($(head -c 150 "$f.err" 2>/dev/null))"; exit 2; }
done

# LOS OTROS DOS ACTIVOS, SOLO PARA EL PLIEGUE Y PARA LA PALABRA (A81). No repiten la
# observacion larga de B8 -que es del reloj, no del activo- asi que cuestan una carga cada una.
# Van a un subdirectorio propio: si uno no midio, se DECLARA por su nombre y no se da por bueno.
OTROS="$TMP/otros"; mkdir -p "$OTROS"
for a in $ACTIVOS; do
  [ "$a" = "$ACTIVO" ] && continue
  for m in scalp swing largo; do
    corre_a "$a" 1920 1080 "$m" 0 "$OTROS/${a}__${m}__1920x1080.json" || true
    corre_a "$a" 1440 900  "$m" 0 "$OTROS/${a}__${m}__1440x900.json"  || true
  done
done

"$PY" - "$TMP/g.json" "$TMP/p.json" "$TMP/sw.json" "$TMP/swp.json" "$TMP/lg.json" \
       "$TMP/lgp.json" "$SUJETO" "$ACTIVO" "$REPO" \
       "$REPO/app/ai_context.py" "$OTROS" "$ACTIVOS" <<'PY'
import json, os, re, sys

g, p, sw, swp, lg, lgp = (json.load(open(x)) for x in sys.argv[1:7])
sujeto, activo = sys.argv[7], sys.argv[8]
raiz_repo, ruta_ctx = sys.argv[9], sys.argv[10]
dir_otros, activos_pedidos = sys.argv[11], sys.argv[12].split()
fallos, lineas = [], []

# LAS VISTAS DE LOS OTROS ACTIVOS. Cada fichero se llama <activo>__<marco>__<ancho>x<alto>.json,
# asi que el rotulo de cada hallazgo sale del NOMBRE del fichero y no de un indice.
otros = []
for nombre in sorted(os.listdir(dir_otros) if os.path.isdir(dir_otros) else []):
    if not nombre.endswith(".json"):
        continue
    a, m, t = nombre[: -len(".json")].split("__")
    try:
        otros.append((json.load(open(os.path.join(dir_otros, nombre))), f"{m} {t} [{a}]", m, a))
    except (OSError, ValueError) as e:
        fallos.append(f"B1 {m} {t} [{a}]: la sonda no dejo una vista legible ({e})")
faltan = [a for a in activos_pedidos
          if a != activo and not any(x[3] == a for x in otros)]
if faltan:
    fallos.append(
        "B1: no se midio NINGUNA vista de " + " ni ".join(faltan)
        + ": el pliegue de esos activos queda SIN JUZGAR, y eso no es un aprobado"
    )

def cosecha(d, rot):
    c = d.get("cosecha") or {}
    if not c or c.get("error"):
        print(f"NO MEDIDO: {rot}: la cosecha no se pudo leer ({(c or {}).get('error')})")
        raise SystemExit(2)
    return c

# TODAS LAS VISTAS, con su activo dentro del rotulo. Las seis del activo profundo primero: son
# las que alimentan a B3, B4, B5, B7 y B8, que necesitan la observacion larga.
VISTAS = [
    (g, f"scalp 1920x1080 [{activo}]", "scalp", activo),
    (p, f"scalp 1440x900 [{activo}]", "scalp", activo),
    (sw, f"swing 1920x1080 [{activo}]", "swing", activo),
    (swp, f"swing 1440x900 [{activo}]", "swing", activo),
    (lg, f"largo 1920x1080 [{activo}]", "largo", activo),
    (lgp, f"largo 1440x900 [{activo}]", "largo", activo),
] + otros

# --- B1 y B2 · LOS TRES MARCOS, LOS DOS TAMANOS, LOS TRES ACTIVOS -----------------------
margenes = {}
for d, rot, _marco, act in VISTAS:
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
        # LA HOLGURA SE PUBLICA, no solo el si/no. Un «cabe» con 3 px de margen y uno con 300
        # dicen cosas muy distintas sobre lo que pasara la proxima vez que DECIDE crezca, y el
        # veredicto binario los cuenta igual.
        holgura = (pl.get("innerHeight") or 0) - (pl.get("bottom") or 0)
        margenes.setdefault(act, []).append((holgura, rot, pl))
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

# EL MARGEN DE CADA ACTIVO, POR SU NOMBRE. La vista mas estrecha de cada uno, y cual es: sin
# esto «se juzgan los tres» seria una promesa sin cifra, que es de donde salio A81.
for act in sorted(margenes):
    peor = min(margenes[act])
    lineas.append(
        f"[{act}] {len(margenes[act])} vista(s) con DECIDE entero en el pliegue; la mas "
        f"estrecha, {peor[1]}: bottom {peor[2].get('bottom'):.0f} de "
        f"{peor[2].get('innerHeight')}, holgura {peor[0]:.0f} px"
    )
if margenes:
    pg = min(min(v) for v in margenes.values())
    lineas.append(
        f"el sesgo es el glifo mayor del pliegue en las {len(VISTAS)} vistas · la mas estrecha "
        f"de TODAS: {pg[1]} con {pg[0]:.0f} px"
    )

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

# --- B5 · LA REGLA DEL HANDOFF, SOBRE EL RAYADO DE LA TARJETA ---------------------------
#
# ESTE BRAZO JUZGA EL RAYADO, Y B9 JUZGA LA PALABRA. El umbral del handoff decide las DOS cosas
# -la tarjeta rayada y, en primer lugar, la palabra-, pero cada una tiene su brazo: aqui se mide
# que `evaluable` sale de su propia regla (`data_confidence` contra su umbral) y que la tarjeta
# lleva la marca que le toca; que la PALABRA siga ese mismo umbral lo recomputa B9 desde el
# sobre. Separarlos es lo que hace que un hallazgo diga cual de las dos cosas esta rota.
dec = (g.get("sobre") or {}).get("decide") or {}
ev = (dec.get("evaluable") or {}).get("value")
umbral_ev = (dec.get("evaluable") or {}).get("threshold")
dc_val = (dec.get("data_confidence") or {}).get("value")
cg = cosecha(g, f"scalp 1920x1080 [{activo}]")
clases = str(cg.get("clases_decide") or "").split()
marcada = "no-evaluable" in clases
if ev is None:
    fallos.append("B5: el sobre no trae `decide.evaluable`: la regla del umbral no se puede juzgar")
elif cg.get("clases_decide") is None:
    print("NO MEDIDO: B5: la sonda no cosecho las clases de #decide")
    raise SystemExit(2)
elif ev is False and not marcada:
    fallos.append(
        f"B5: el sobre dice evaluable=false (data_confidence {dc_val} contra umbral "
        f"{umbral_ev}) y la tarjeta NO lleva la marca `no-evaluable`: clases {clases}"
    )
elif ev is True and marcada:
    fallos.append(
        f"B5: el sobre dice evaluable=true (data_confidence {dc_val} contra umbral "
        f"{umbral_ev}) y la tarjeta se pinta rayada de NO EVALUABLE igualmente"
    )
elif (
    dc_val is not None and umbral_ev is not None
    and bool(float(dc_val) >= float(umbral_ev)) is not bool(ev)
):
    fallos.append(
        f"B5: `evaluable` no sale de su propia regla: data_confidence {dc_val}, umbral "
        f"{umbral_ev}, y el sobre dice evaluable={ev}"
    )
else:
    lineas.append(
        f"la regla del handoff se cumple: data_confidence {dc_val} contra umbral {umbral_ev} "
        f"-> evaluable={ev} -> tarjeta {'rayada' if marcada else 'sin rayar'} "
        f"(y la PALABRA sale de este mismo umbral, en primer lugar; eso lo juzga B9)"
    )

# --- B7 · LA LECTURA DEL SCALP NO ES EL VEREDICTO DE OTRO MARCO ------------------------
# Las claves que salen de la lectura del scalp. Si alguna aparece dentro de `decide` en un
# marco que no es scalp, ese marco esta publicando la lectura del scalp como suya.
DEL_SCALP = ("state", "reason", "confidence", "edge", "evidence", "confirms",
             "invalidates", "invalidation_level", "horizon",
             # `evidence_balance` sale de `operator_read.bias`, o sea de la lectura del scalp:
             # publicarlo dentro de `decide` en SWING seria presentar un balance de scores de un
             # minuto como del marco, que es el defecto de la 130 en otra clave.
             "evidence_balance")
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

# --- B9 · LA PALABRA DICE LA DECISION DEL SISTEMA ---------------------------------------
# LA REGLA NO SE COPIA AQUI: SE IMPORTA, y son las DOS mitades.
#
#   1 · el umbral del handoff, que el propio sobre sirve (`decide.evaluable.threshold`)
#   2 · `classify_signal_observation` de `app/signal_ledger.py`, ENTERA
#
# Reescribir aqui cualquiera de las dos dejaria que las versiones se separasen en silencio, que
# es la forma exacta del defecto que esta campana vino a arreglar. Y son las DOS: una version que
# solo mirase los conjuntos de estados diria un lado donde el registro dice «no se» -el registro
# cierra la puerta antes, por libro o por cobertura-.
#
# Y SE RECOMPUTA DESDE LO QUE LA PROPIA RESPUESTA SIRVE: `data_confidence`, el umbral, `state`,
# `book_status` y `evidence`. Si alguna no viaja, la palabra no es auditable y eso es un hallazgo.
# Si el import falla, NO MEDIDO: una regla que no se pudo cargar no absuelve a nadie.
sys.path.insert(0, raiz_repo)
try:
    from app.signal_ledger import classify_signal_observation
except Exception as e:  # noqa: BLE001
    print(f"NO MEDIDO: B9 no pudo importar classify_signal_observation de {raiz_repo}: {e}")
    raise SystemExit(2) from None

PALABRA_POR_DIRECCION = {"long": "LONG", "short": "SHORT", "neutral": "NO OPERAR"}

def palabra_esperada(dc, umbral, estado, libro, cobertura):
    """La palabra que ESA respuesta tendria que estar sirviendo, con la regla completa."""
    if dc is None or umbral is None:
        return None, "no llega data_confidence o su umbral"
    try:
        if float(dc) < float(umbral):
            return "NO EVALUABLE", f"data_confidence {dc} < {umbral}"
    except (TypeError, ValueError):
        return None, f"data_confidence o umbral no son numeros: {dc!r} / {umbral!r}"
    _d, direccion, _a = classify_signal_observation(
        {"state": estado, "book_status": libro, "evidence_coverage_pct": cobertura}
    )
    return PALABRA_POR_DIRECCION.get(direccion, "NO EVALUABLE"), direccion

# LA PISTA DE DESPLIEGUE, no una excusa. Si el sujeto sirve un `schema_version` distinto del que
# el ARBOL declara, lo que se esta juzgando son bytes viejos. Sigue siendo ROJO -el sujeto tiene
# el defecto- pero la linea dice POR QUE, para que nadie salga a buscar un fallo en el arbol.
m_sch = re.search(r'MESA_DECIDE_SCHEMA\s*=\s*"([^"]+)"', open(ruta_ctx, encoding="utf-8").read())
sch_arbol = m_sch.group(1) if m_sch else None
sch_sujeto = (g.get("sobre") or {}).get("schema_version")
pista = ""
if sch_arbol and sch_sujeto and sch_arbol != sch_sujeto:
    pista = (f" · FALTA DESPLEGAR: el sujeto sirve {sch_sujeto} y el arbol declara {sch_arbol}")

b9_ok, b9_sin_tarjeta = [], []
for d, rot, marco, _act in VISTAS:
    sob = d.get("sobre") or {}
    if not sob:
        fallos.append(f"B9 {rot}: no se pudo leer el sobre que recibio la pagina")
        continue
    c = cosecha(d, rot)
    dec_v = sob.get("decide") or {}
    if marco == "scalp":
        origen = dec_v
        pintada = ((c.get("sesgo") or {}).get("texto") or "").strip()
        donde = "#decide-sesgo"
    else:
        # En swing y largo la palabra del SCALP vive en `lectura_scalp` y se pinta en su tarjeta
        # -B7 exige que no este en `decide`-, asi que la pareja se juzga ALLI. Si la tarjeta no
        # se sirve, el dueno del hallazgo es B7 y B9 no lo duplica.
        origen = sob.get("lectura_scalp") or {}
        if not origen:
            b9_sin_tarjeta.append(rot)
            continue
        tj = c.get("tarjeta_scalp") or {}
        cel = {x.get("campo"): x for x in (tj.get("parejas") or [])}
        pintada = ((cel.get("scalp.bias") or {}).get("valor") or "").strip()
        donde = "#lectura-scalp [data-campo=scalp.bias]"
    servida = (origen.get("bias") or {}).get("value")
    # LAS CUATRO ENTRADAS DE LA REGLA, LEIDAS DEL SOBRE. `data_confidence` y su umbral viven
    # SIEMPRE en `decide` -son del simbolo, no del marco-; las otras tres viajan con la lectura
    # del scalp, o sea en `decide` en scalp y en `lectura_scalp` en los otros dos.
    estado = (origen.get("state") or {}).get("value")
    libro = (origen.get("book_status") or {}).get("value")
    cobertura = (origen.get("evidence") or {}).get("value")
    dc_v = (dec_v.get("data_confidence") or {}).get("value")
    umbral_v = (dec_v.get("evaluable") or {}).get("threshold")
    faltan = [k for k, v in (("bias", servida), ("state", estado), ("book_status", libro),
                             ("data_confidence", dc_v), ("evaluable.threshold", umbral_v))
              if v is None]
    if faltan:
        fallos.append(
            f"B9 {rot}: la respuesta no sirve {' '.join(faltan)}: sin eso la palabra mas grande "
            f"no se puede contrastar con la regla que dice seguir{pista}"
        )
        continue
    esperada, por_que = palabra_esperada(dc_v, umbral_v, estado, libro, cobertura)
    if esperada is None:
        fallos.append(f"B9 {rot}: no se pudo recomputar la palabra: {por_que}{pista}")
    elif str(servida) != esperada:
        fallos.append(
            f"B9 {rot}: la palabra SERVIDA dice {servida!r} y la regla sobre lo que ESA MISMA "
            f"respuesta sirve da {esperada!r} por {por_que!r} (data_confidence {dc_v} contra "
            f"umbral {umbral_v}; ESTADO {estado!r}, libro {libro!r}, evidencia {cobertura})"
            f"{pista}"
        )
    elif pintada != esperada:
        fallos.append(
            f"B9 {rot}: la palabra PINTADA en {donde} dice {pintada!r} y la regla sobre lo que la "
            f"MISMA carga sirve da {esperada!r}"
        )
    else:
        b9_ok.append((rot, pintada, str(estado), str(por_que)))

# LAS PAREJAS QUE SALIERON BIEN, AGRUPADAS POR LO QUE DICEN. Dieciocho lineas iguales no se
# leen; lo que importa es CUANTAS parejas distintas se llegaron a ver. Si solo se vio una
# -«NO EVALUABLE» contra «Sin datos suficientes», que es lo que da el espejo- este brazo no ha
# ejercido la mitad que condena un lado callado, y la salida lo dice en vez de sugerir que si.
if b9_ok:
    vistos = {}
    for rot, pal, est, motivo in b9_ok:
        vistos.setdefault((pal, est, motivo), []).append(rot)
    lineas.append(
        f"la palabra coincide con la regla completa -umbral del handoff + "
        f"classify_signal_observation- en {len(b9_ok)} de "
        f"{len(VISTAS) - len(b9_sin_tarjeta)} vista(s) juzgada(s), con "
        f"{len(vistos)} caso(s) distinto(s):"
    )
    for (pal, est, motivo), rots in sorted(vistos.items()):
        lineas.append(
            f"  palabra {pal!r} · state {est!r} · {motivo} · {len(rots)} vista(s): "
            + " ".join(rots[:3]) + (" ..." if len(rots) > 3 else "")
        )
    con_lado = [k for k in vistos if k[0] in ("LONG", "SHORT")]
    if not con_lado:
        lineas.append(
            "  y NINGUNA de las palabras vistas tenia lado: en esta corrida B9 no ha ejercido "
            "la mitad que condena una palabra que CALLA un lado que el sistema si toma"
        )
if b9_sin_tarjeta:
    lineas.append(
        f"B9 no juzga {len(b9_sin_tarjeta)} vista(s) sin `lectura_scalp` (el hallazgo, si lo "
        "hay, es de B7): " + " ".join(b9_sin_tarjeta[:4])
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
juzgados = sorted({activo} | {x[3] for x in otros})
print(f"  alcance: los TRES marcos (scalp, swing y largo) a los DOS tamanos (1920x1080 y "
      f"1440x900) · {g.get('barra_de_desplazamiento')}")
print(f"  el PLIEGUE y la PALABRA, en {' '.join(juzgados)} ({len(VISTAS)} vistas): el margen "
      "depende del largo de `scalp.reason` y de la zona, y las dos se mueven con el mercado, "
      "asi que el peor caso no es un activo fijo (A81)")
print(f"  B3, B4, B5, B7 y B8 solo en {activo}: piden la observacion larga, que es del reloj y "
      "no del activo")
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
