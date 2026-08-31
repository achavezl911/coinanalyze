#!/bin/bash
# K79  EL COSTE NO PUEDE DAR VEREDICTO CALLANDO LAS PATAS QUE LE FALTAN.
#
# EL ENCARGO DECIA OTRA COSA Y LA MEDICION LA CORRIGIO, asi que lo primero es eso.
# El encargo era: "/api/hypothesis sin parametros da total_cost_bps=0.013 y con
# fee_bps_per_side=4 da 8.013, 616 veces, y app.js:1949 lo pinta sin leer
# cost_components_missing". La cifra es cierta. LA VIA NO: medido contra 140, el caso sin
# parametros sale con status='SIN EVALUAR' y missing_inputs=[entrada,objetivo,stop,comision,
# tamano], y app.js:1943-1948 RETORNA ANTES de pintar el coste -imprime "Falta para evaluar"-.
# O sea que ese 0.013 NUNCA llega a la fila del coste. Un check construido sobre esa via
# habria nacido VERDE sobre el caso equivocado.
#
# LO QUE SI ES ALCANZABLE, y es peor. faltan (scalp_logic.py:4778-4787) y componentes
# (:4789-4794) son DOS VOCABULARIOS DISTINTOS y solo el primero gatea el status:
#     faltan ...... entrada · objetivo · stop · comision · tamano
#     componentes . spread_bps · fees_bps · slippage_bps · funding_bps
# slippage y funding NO estan en faltan. Con un plan completo segun faltan pero sin ellos:
#     status = EVALUADO, verdict con banda, y cost_components_missing = [slippage, funding]
# y app.js:1949 pinta "Coste ida y vuelta" sin decir que faltan dos de cuatro patas.
#
# Y EL DANO NO ES LA ETIQUETA. cost_to_target y cost_to_risk (:4802-4812) salen de ese total
# PARCIAL y son los que producen el veredicto (:4816-4828). MEDIDO contra 140 el 2026-08-31,
# mismo plan y mismo mercado, entry 78913 target 79702 stop 78440 size 25000 fee 4:
#     slippage AUSENTE   total  8.013   ACEPTABLE      missing=[slippage_bps, funding_bps]
#     slippage 5 bps     total 18.013   AJUSTADO       missing=[funding_bps]
#     slippage 10 bps    total 28.013   PROHIBITIVO    missing=[funding_bps]
# La pata que falta cruza DOS bandas. La pantalla dice "aceptable" sobre un coste al que le
# falta la mitad de sus patas.
#
# LO QUE ESTO CORRIGE DEL DIAGNOSTICO HEREDADO: no es solo que "la presentacion vuelva a
# fundir no-hay-dato con vale-cero". EL BACKEND TAMBIEN LO FUNDE, en cost_to_target,
# cost_to_risk y verdict. El backend es fail-closed para faltan y NO lo es para componentes.
#
# Y AUN ASI EL VERDE EXIGE LA VIA DE LA PANTALLA Y NO LA DEL BACKEND, con motivo medido y no
# por comodidad: hacer al backend fail-closed sobre componentes meteria funding_bps en la
# condicion, y funding es LEGITIMAMENTE ausente en cualquier operacion sin carry -es un
# parametro que pone quien llama y la pantalla no lo manda si el operador no lo escribe-.
# El resultado seria SIN EVALUAR permanente, o sea un rojo inarreglable, que es justo lo que
# ensena a ignorar los rojos buenos. La via limpia del backend seria mas estrecha -meter
# SOLO slippage en faltan, al lado de comision, que es su mismo genero: parametro del
# llamante que nunca vale cero de verdad- pero eso convierte EVALUADO en SIN EVALUAR para
# todo el que no declare slippage, que es un cambio de comportamiento de cara al operador y
# NO es lo que se encargo. Queda dicho aqui como la decision siguiente, no tomada.
#
# LAS DOS AUSENCIAS NO SON DEL MISMO GENERO, y no se declara ninguna inocente por simetria:
#   funding_bps ... LEGITIMA por defecto. El docstring de :4771 dice "el funding solo aplica
#                   si se declara": una operacion sin carry no lo paga. Un check que exigiera
#                   funding siempre presente seria un ROJO permanente e inarreglable.
#   slippage_bps .. NO legitima. Se paga en las DOS patas (*2 en :4792) y no existe orden
#                   real a mercado con slippage cero. Su ausencia es un agujero, no un cero.
# Por eso el brazo B mide con SLIPPAGE, que es la que tiene consecuencia, y no con funding.
#
# LOS CUATRO BRAZOS:
#   A · PANTALLA. renderExecutionRows de static/app.js tiene que CONSULTAR
#       cost_components_missing. Es de TEXTO FUENTE por necesidad y no por pereza: este arnes
#       no tiene navegador, y lo que la pantalla pinta NO DEJA HUELLA en ninguna respuesta de
#       la API, asi que ningun brazo de comportamiento puede cazarlo jamas. Misma situacion
#       que el brazo C de K76, y se dice igual de claro. Se mira DENTRO de la funcion, no en
#       el fichero entero: un comentario en cualquier otra parte de app.js no vale.
#   B · CONSECUENCIA, y se re-mide en CADA pasada en vez de citarse de aqui. Si algun dia las
#       bandas o los componentes cambian y omitir el slippage deja de mover el veredicto,
#       este check tiene que DECIRLO en vez de seguir presumiendo de un peligro que ya no
#       existe -leccion de K71-. Sin consecuencia medida, A estaria gateando sobre una
#       etiqueta: eso sale NOMED, no VERDE.
#   C · CONTROL NEGATIVO, y viene del error que el encargo estuvo a punto de meter: el caso
#       SIN EVALUAR -sin parametros- NO cuenta como el defecto, porque app.js YA retorna ahi.
#       Si este brazo se rompe, el check estaria cazando el caso que ya esta guardado.
#   D · CONTROL POSITIVO: con las cuatro patas puestas, missing=[] y hay veredicto. Un check
#       que solo sabe salir ROJO esta tan roto como el que no caza nada.
#
# EL PLAN SE DERIVA DEL DATO Y NO SE FIJA: entry sale del mid vivo de /api/scalp/orderbook y
# el objetivo y el stop son fracciones de el, porque un 78913 fijo caduca en una hora
# -leccion de K76, cuya primera version salio roja por un parametro y no por el defecto-.
# LA COMISION DE 4 bps/lado ES UN PARAMETRO DE LA SONDA, NO UNA AFIRMACION SOBRE LA TARIFA
# REAL: la tarifa con fuente y fecha sigue en la mesa de Alejandro. Aqui solo hace falta un
# valor que lleve el status a EVALUADO; el defecto no depende de cual sea.
#
# DE QUE ARBOL: los brazos B, C y D miden 140 por la API. El brazo A lee static/app.js del
# REPO de 143. El VERDE completo exige los cuatro.
#
# Se comprueba con: bash harness/checks/K79-el-coste-calla-lo-que-le-falta.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"
SIMBOLO=BTCUSDT_PERP.A

# ------------------------------------------------------- el plan, derivado del dato vivo
MID=$("$B/bin/api" "/api/scalp/orderbook?symbol=$SIMBOLO" 2>/dev/null | python3 -c '
import json,sys
try: filas = json.load(sys.stdin).get("rows") or []
except Exception: sys.exit(0)
for f in filas:
    if f.get("mid_px"): print(f["mid_px"]); break
' 2>/dev/null)
case "$MID" in
  ''|*[!0-9.]*) echo "NO MEDIDO: /api/scalp/orderbook no dio un mid vivo para $SIMBOLO; sin precio no hay plan que derivar"; exit 2 ;;
esac

# objetivo a 100 bps y stop a 60 bps del mid. Elegidos para que el coste SIN slippage caiga
# en 'aceptable' -8 bps sobre 100 es 0.08, por debajo del 0.10 de la banda-, que es el estado
# en el que la pantalla miente sin que nada chirrie.
PLAN=$(python3 -c "
m=float('$MID')
print('entry=%.2f&target=%.2f&stop=%.2f&size_usd=25000&fee_bps_per_side=4' % (m, m*1.01, m*0.994))
")

pedir() {  # pedir "<extra query>"  ->  status|verdict|total|missing
  "$B/bin/api" "/api/hypothesis?symbol=$SIMBOLO&$PLAN$1" 2>/dev/null | python3 -c '
import json,sys
try: e = json.load(sys.stdin)["execution"]
except Exception: sys.exit(0)
print("%s|%s|%s|%s" % (e.get("status"), e.get("verdict"), e.get("total_cost_bps"),
                       ",".join(e.get("cost_components_missing") or [])))
' 2>/dev/null
}

SIN=$(pedir "")
CON=$(pedir "&slippage_bps=10")
[ -n "$SIN" ] && [ -n "$CON" ] || { echo "NO MEDIDO: /api/hypothesis no contesto con un bloque execution utilizable"; exit 2; }

IFS='|' read -r S_ST S_VER S_TOT S_MIS <<EOF
$SIN
EOF
IFS='|' read -r C_ST C_VER C_TOT C_MIS <<EOF
$CON
EOF

# --- D · CONTROL POSITIVO: con las cuatro patas, missing vacio y veredicto.
TODO=$(pedir "&slippage_bps=10&funding_bps=1")
IFS='|' read -r T_ST T_VER T_TOT T_MIS <<EOF
$TODO
EOF
[ "$T_ST" = "EVALUADO" ] && [ -z "$T_MIS" ] || {
  echo "NO MEDIDO: el CONTROL POSITIVO no llega al estado limpio -- con las cuatro patas puestas sale status=$T_ST y missing=[$T_MIS]. Sin poder producir el estado sano, un ROJO no distingue el defecto de una sonda rota"
  exit 2
}

# --- C · CONTROL NEGATIVO: el caso sin parametros YA esta guardado por app.js. No es esto.
VACIO=$("$B/bin/api" "/api/hypothesis?symbol=$SIMBOLO" 2>/dev/null | python3 -c '
import json,sys
try: e = json.load(sys.stdin)["execution"]
except Exception: sys.exit(0)
print(e.get("status"))
' 2>/dev/null)
[ "$VACIO" = "SIN EVALUAR" ] || {
  echo "NO MEDIDO: CONTROL NEGATIVO ROTO -- el caso sin plan sale status='$VACIO' y no 'SIN EVALUAR'. app.js:1945 solo retorna con SIN EVALUAR, asi que si eso cambio, este check ya no sabe cual de los dos casos esta cazando"
  exit 2
}

# --- B · CONSECUENCIA: la pata ausente tiene que MOVER el veredicto, medido hoy.
[ "$S_ST" = "EVALUADO" ] || {
  echo "NO MEDIDO: el plan derivado no alcanza status=EVALUADO (sale '$S_ST'), asi que no se puede observar el estado en que la pantalla miente"
  exit 2
}
[ -n "$S_MIS" ] || {
  echo "NO MEDIDO: con el plan sin slippage el backend NO declara ninguna pata ausente (missing vacio). El defecto que este check vigila no se puede reproducir hoy"
  exit 2
}
[ "$S_VER" != "$C_VER" ] || {
  echo "NO MEDIDO: omitir el slippage YA NO MUEVE el veredicto -- sigue en '$S_VER' con y sin la pata ($S_TOT vs $C_TOT bps). Sin consecuencia medida, el brazo de pantalla estaria gateando sobre una etiqueta y no sobre un dano; re-plantea las bandas o retira el check"
  exit 2
}

# --- A · PANTALLA: renderExecutionRows tiene que consultar cost_components_missing.
APP="$REPO/static/app.js"
[ -r "$APP" ] || { echo "NO MEDIDO: no se puede leer $APP"; exit 2; }
CUERPO=$(awk '/^function renderExecutionRows\(/{d=1} d{print} d&&/^\}/{exit}' "$APP")
[ -n "$CUERPO" ] || { echo "NO MEDIDO: no se encontro la funcion renderExecutionRows en $APP; el brazo de pantalla no sabe donde mirar"; exit 2; }
LEE=$(printf '%s' "$CUERPO" | grep -c "cost_components_missing")

if [ "$LEE" -eq 0 ]; then
  printf 'ROJO: la pantalla da VEREDICTO callando las patas que faltan. Con el plan derivado del mid %s, el backend responde %s con total %s bps y cost_components_missing=[%s], y renderExecutionRows de app.js NO consulta ese campo: pinta "Coste ida y vuelta" como si el total fuera completo. Y no es la etiqueta: con la pata puesta el veredicto pasa de %s a %s (%s -> %s bps)\n' \
    "$MID" "$S_VER" "$S_TOT" "$S_MIS" "$S_VER" "$C_VER" "$S_TOT" "$C_TOT"
  exit 1
fi

printf 'renderExecutionRows consulta cost_components_missing (%d veces), asi que un veredicto sobre coste incompleto llega a la pantalla DICIENDO que lo es. Medido hoy sobre el mid %s: sin slippage el backend da %s con %s bps y declara [%s], y con la pata puesta pasa a %s con %s bps -- o sea que la omision SIGUE teniendo consecuencia y este brazo no es cosmetico. Control positivo: con las cuatro patas, missing vacio y veredicto %s. Control negativo: el caso sin plan sigue saliendo SIN EVALUAR, que app.js ya guarda aparte\n' \
  "$LEE" "$MID" "$S_VER" "$S_TOT" "$S_MIS" "$C_VER" "$C_TOT" "$T_VER"
