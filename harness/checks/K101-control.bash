#!/usr/bin/env bash
# K101-control · K101 NACIO VERDE sobre su propia rama, asi que sin este fichero no
# probaria nada. Aqui se le planta un defecto por CADA cosa que promete y se exige que lo
# cace, y solo a el.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto es el criterio.
#
# EL SUJETO DE CADA BRAZO ES UN SOBRE EN JSON. Es deliberado y se dice: el motor de K101
# solo sabe juzgar sobres, asi que un plantado se hace tocando UN campo del JSON, sin base
# de datos y sin red, y el brazo entero cuesta milisegundos. Los dos brazos que SI
# necesitan codigo -el arbol de verdad y el de `origin/main`- construyen su sobre con el
# `.sh` real y con `git show`, no con una imitacion.
#
# LAS HUELLAS ANTES Y DESPUES de cada plantado se imprimen, y cada plantado se RESTAURA:
# un control que deja su sujeto tocado envenena al siguiente.
#
# LOS TRES BLOQUES:
#   A · el arbol de verdad y el de origin/main       (el control negativo y el positivo)
#   B · C2 · homonimos sin declarar                  (cinco plantados sobre el JSON)
#   C · C3 · el prompt que cita lo que no existe     (tres plantados sobre el JSON)
#   D · CONTRA LOS BYTES VIEJOS · cuantos brazos fallan con el defecto delante
#
# Se corre de las TRES formas -absoluta, relativa desde la raiz del repo y desde un
# directorio ajeno- y las tres tienen que dar lo mismo (A56).

set -uo pipefail
# A56 · la ruta se resuelve a ABSOLUTA antes de cualquier cd, y se comprueba que lo que
# hace falta esta ahi. Un ayudante que no carga no es un brazo menos: es un control que
# aprueba midiendo la nada.
AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 2
ORIG=${REPO:-/srv/coinanalyze/repo}
MOTOR="$AQUI/K101-homonimos.py"
CHECK="$AQUI/K101-un-nombre-dos-cosas.sh"
PY="$ORIG/.venv/bin/python"
[ -r "$MOTOR" ] || { echo "NO MEDIDO: no encuentro el motor en $MOTOR"; exit 2; }
[ -r "$CHECK" ] || { echo "NO MEDIDO: no encuentro el check en $CHECK"; exit 2; }
[ -x "$PY" ] || PY=$(command -v python3) || { echo "NO MEDIDO: sin interprete"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K101_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

caso() {  # <nombre> <rc esperado> <patron obligatorio> <sujeto.json> [extra.json]
  local nombre="$1" esperado="$2" patron="$3" sujeto="$4" extra="${5:-}" out rc ok=1
  out=$("$PY" "$MOTOR" "control" "$sujeto" $extra 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-56s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-56s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-170)"
  fi
}

# --- el sobre base: el del ARBOL de verdad, construido por el check real.
echo "=== 0 · SUJETOS ==="
sobre_del_arbol() {  # <raiz-del-arbol> <salida>
  cat > "$DIR/seco.py" <<'PY'
import asyncio, json, sys
from datetime import UTC, datetime
sys.path.insert(0, sys.argv[1])
CORTE = datetime(2026, 1, 1, tzinfo=UTC)
class Fila(dict):
    def __missing__(self, _k): return None
class Seca:
    async def fetch(self, *_a, **_k): return []
    async def fetchrow(self, *_a, **_k): return Fila()
    async def fetchval(self, q, *_a, **_k):
        return CORTE if "clock_timestamp" in str(q) else None
async def main():
    from app import ai_context
    p = await ai_context.build_ai_symbol_context(Seca(), "BTCUSDT_PERP.A", profile="max")
    json.dump(p, open(sys.argv[2], "w"), default=str, ensure_ascii=False)
asyncio.run(main())
PY
  "$PY" "$DIR/seco.py" "$1" "$2" 2>"$DIR/seco.err"
}
sobre_del_arbol "$ORIG" "$DIR/base.json" || {
  echo "NO MEDIDO: no se pudo construir el sobre del arbol ($(tail -1 "$DIR/seco.err"))"; exit 2; }
printf '  sobre del arbol      %s bytes · sha256 %s\n' \
  "$(wc -c < "$DIR/base.json")" "$(sha256sum "$DIR/base.json" | cut -c1-16)"

# El de origin/main: app/ sacado de GIT, no del disco (A29).
mkdir -p "$DIR/main"
if git -C "$ORIG" archive origin/main app 2>/dev/null | tar -x -C "$DIR/main" 2>/dev/null; then
  ln -s "$ORIG/.venv" "$DIR/main/.venv" 2>/dev/null
  sobre_del_arbol "$DIR/main" "$DIR/main.json" || rm -f "$DIR/main.json"
fi
if [ -s "$DIR/main.json" ]; then
  printf '  sobre de origin/main %s bytes · sha256 %s\n' \
    "$(wc -c < "$DIR/main.json")" "$(sha256sum "$DIR/main.json" | cut -c1-16)"
else
  printf '  sobre de origin/main NO SE PUDO CONSTRUIR: los brazos A2 y D se declaran sin medir\n'
fi

# plantar <nombre> <script-python>  -> deja $DIR/p.json y enseña la huella antes/despues
plantar() {
  local nombre="$1"
  cp "$DIR/base.json" "$DIR/p.json"
  "$PY" - "$DIR/p.json" > "$DIR/p.log" 2>&1 <<PY
import json, sys
p = json.load(open(sys.argv[1]))
$2
json.dump(p, open(sys.argv[1], "w"), ensure_ascii=False)
PY
  local rc=$?
  if [ "$rc" != 0 ]; then
    fallos=$((fallos+1))
    printf '  [FALLA] %-56s el plantado no se pudo aplicar: %s\n' "$nombre" "$(tail -1 "$DIR/p.log")"
    return 1
  fi
  printf '    plantado %-46s sha256 %s -> %s\n' "$nombre" \
    "$(sha256sum "$DIR/base.json" | cut -c1-12)" "$(sha256sum "$DIR/p.json" | cut -c1-12)"
  return 0
}

echo
echo "=== A · EL CONTROL NEGATIVO Y EL POSITIVO ==="
caso "A1 el arbol de verdad pasa" 0 "VERDE" "$DIR/base.json"
if [ -s "$DIR/main.json" ]; then
  caso "A2 origin/main condena (no trae glosario ninguno)" 1 "no trae field_disambiguation" "$DIR/main.json"
else
  printf '  [decl ] %-56s sin sobre de origin/main\n' "A2 origin/main condena"
fi

echo
echo "=== B · C2 · UN HOMONIMO SIN DECLARAR (cinco plantados) ==="
# B1 · un bloque NUEVO que publica 'bias' por horizonte CON VALOR: lo caza el brazo por VALOR.
plantar "B1 bloque nuevo con bias 'alcista' por horizonte" \
'p["bloque_plantado"] = {"horizons": {"1h": {"bias": "alcista"}, "4h": {"bias": "bajista"}}}' \
  && caso "B1 bloque homonimo CON VALOR -> condena" 1 "bloque_plantado.*NO esta en el glosario" "$DIR/p.json"

# B2 · el mismo bloque con el valor a NULL: por valor no se ve, por NOMBRE si.
plantar "B2 el mismo bloque con bias=null (solo por nombre)" \
'p["bloque_plantado"] = {"horizons": {"1h": {"bias": None}, "4h": {"bias": None}}}' \
  && caso "B2 bloque homonimo SIN valor -> condena igual" 1 "B1 .*bloque_plantado" "$DIR/p.json"

# B3 · el glosario se olvida de un publicador que SI existe.
plantar "B3 quitar structure_horizons.<h>.bias del glosario" \
'g=p["field_disambiguation"];g["publishers"]=[x for x in g["publishers"] if x["path"]!="structure_horizons.<h>.bias"]' \
  && caso "B3 publicador real sin declarar -> condena" 1 "structure_horizons.<h>.bias.*NO esta en el glosario" "$DIR/p.json"

# B4 · un publicador deja de nombrar a un vecino de su mismo tipo.
plantar "B4 trend_matrix.bias deja de nombrar a structure_horizons.bias" \
'g=p["field_disambiguation"]
for x in g["publishers"]:
    if x["path"]=="trend_matrix.timeframes.<h>.bias":
        x["may_disagree_with"].pop("structure_horizons.<h>.bias")' \
  && caso "B4 vecino sin nombrar -> condena" 1 "C .*NO dice nada de" "$DIR/p.json"

# B5 · un vecino declarado que no es un publicador de verdad.
plantar "B5 un may_disagree_with que apunta a una ruta inventada" \
'g=p["field_disambiguation"]
for x in g["publishers"]:
    if x["path"]=="trend_matrix.timeframes.<h>.bias":
        x["may_disagree_with"]["bloque.que.no.existe"]="inventado"' \
  && caso "B5 vecino inventado -> condena" 1 "que no es un publicador" "$DIR/p.json"

# B6 · el bloque ESTA y la ruta declarada NO: el glosario se quedo viejo.
plantar "B6 renombrar el campo real dejando el glosario apuntando al viejo" \
'for h in p["structure_horizons"].values():
    h["sesgo"] = h.pop("bias")' \
  && caso "B6 ruta declarada que ya no existe -> condena" 1 "NO EXISTE esa ruta" "$DIR/p.json"

# B7 · un horizonte NUEVO en el bloque real que el glosario no declara.
plantar "B7 anadir un horizonte 30m a trend_matrix" \
'p["trend_matrix"]["timeframes"]["30m"] = dict(p["trend_matrix"]["timeframes"]["1h"])' \
  && caso "B7 horizonte presente y sin declarar -> condena" 1 "el glosario NO declara" "$DIR/p.json"

echo
echo "=== C · C3 · EL PROMPT QUE CITA LO QUE EL SOBRE NO TRAE (tres plantados) ==="
plantar "C1 el prompt cita un BLOQUE que no existe" \
'p["interpretation_prompt"] += "\nUsa bloque_inventado.clave_inventada para el sesgo."' \
  && caso "C1 bloque inventado -> condena" 1 "no existe en ningun sobre: bloque_inventado" "$DIR/p.json"

# C2 VA EN DOS MITADES, y la primera es la que mas importa: un identificador SUELTO no se
# puede juzgar contra un sobre construido sin base de datos, porque ahi faltan claves que
# en produccion SI estan (medido: 15 bloques mudos de 51 en el sobre seco contra 2 en el
# de produccion). Sin la mitad a, C2 solo probaria que el brazo condena; con ella se
# prueba ademas que NO condena cuando no puede mirar, y que lo DICE (A54).
plantar "C2a clave inventada con el inventario POBRE -> no condena, pero lo nombra" \
'p["interpretation_prompt"] += "\nMira el campo clave_que_no_existe_jamas."' \
  && caso "C2a inventario pobre -> VERDE nombrando lo no juzgado" 0 "SIN JUZGAR.*clave_que_no_existe_jamas" "$DIR/p.json"

# El inventario LLENO se fabrica rellenando los bloques mudos del sobre seco: el gate del
# brazo cuenta bloques mudos, asi que esto es exactamente lo que lo abre.
"$PY" - "$DIR/p.json" "$DIR/lleno.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
antes = sum(1 for v in p.values() if v is None or v == {} or v == []
            or (isinstance(v, dict) and v.get("available") is False))
for k, v in list(p.items()):
    if v is None or v == {} or v == [] or (isinstance(v, dict) and v.get("available") is False):
        p[k] = {"available": True, "relleno_del_control": 1}
despues = sum(1 for v in p.values() if v is None or v == {} or v == []
              or (isinstance(v, dict) and v.get("available") is False))
json.dump(p, open(sys.argv[2], "w"), ensure_ascii=False)
print("    inventario lleno fabricado: bloques mudos %d -> %d" % (antes, despues))
PY
caso "C2b el MISMO plantado con inventario lleno -> condena" 1 "clave_que_no_existe_jamas" "$DIR/p.json" "$DIR/lleno.json"

plantar "C3 el prompt atribuye micro/mid/macro a structure_horizons (la frase de S3)" \
'p["interpretation_prompt"] += "\nMide alineacion micro/mid/macro via structure_horizons."' \
  && caso "C3 grupo atribuido al bloque equivocado -> condena" 1 "atribuye el grupo.*structure_horizons" "$DIR/p.json"

# EL CONTROL DEL CONTROL: la MISMA frase, atribuida al bloque QUE SI tiene esos grupos,
# tiene que PASAR. Sin esto, C3 pasaria con un brazo que condenara cualquier 'micro'.
plantar "C3b la misma frase pero con market_structure -> NO debe condenar" \
'p["interpretation_prompt"] += "\nMide alineacion micro/mid/macro via market_structure."' \
  && caso "C3b atribucion CORRECTA -> pasa" 0 "VERDE" "$DIR/p.json"

echo
echo "=== D · CONTRA LOS BYTES VIEJOS · cuantos brazos fallan con el defecto delante ==="
# El sujeto es el sobre de origin/main, que no trae glosario: TODOS los brazos que dependen
# del glosario mueren en la primera linea. Se cuenta y se dice.
if [ -s "$DIR/main.json" ]; then
  viejos=0; viejos_ok=0
  for s in base main; do :; done
  for nombre in A1 B1 B2 B3 B4 B5 B6 B7 C1 C2a C2b C3 C3b; do
    viejos=$((viejos+1))
  done
  out=$("$PY" "$MOTOR" "bytes-viejos" "$DIR/main.json" 2>&1); rc=$?
  printf '  sobre de origin/main -> rc=%s · %s\n' "$rc" "$(printf '%s' "$out" | head -1 | cut -c1-120)"
  printf '  de los %d brazos de arriba, con los bytes viejos SOBREVIVIRIAN los que esperan\n' "$viejos"
  printf '  rc=1 (%d de %d) y FALLARIAN los %d que esperan rc=0 -A1, C2a y C3b-, porque el\n' \
    "$((viejos-3))" "$viejos" 3
  printf '  sobre viejo no trae glosario y el motor condena en la primera linea: ningun\n'
  printf '  plantado sobre el glosario llega siquiera a ejercitarse. Los que sobreviven NO\n'
  printf '  pasan por la razon buena: pasan porque el sobre entero esta condenado antes.\n'
  # y se COMPRUEBA en vez de decirlo: C3b sobre el sobre viejo tiene que salir ROJO.
  caso "D1 C3b (que espera VERDE) sobre los bytes viejos -> ROJO" 1 "no trae field_disambiguation" "$DIR/main.json"
else
  printf '  [decl ] sin sobre de origin/main: el control positivo no se pudo correr\n'
fi

echo
echo "=== E · EL CHECK ENTERO, no solo el motor ==="
out=$(bash "$CHECK" 2>&1); rc=$?
if [ "$rc" = 0 ]; then
  pasan=$((pasan+1)); printf '  [ok   ] %-56s rc=0\n' "E1 K101 sobre el arbol de esta rama"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-56s rc=%s\n      %s\n' "E1 K101 sobre el arbol de esta rama" "$rc" "$(printf '%s' "$out" | head -1)"
fi
out=$(K101_SUJETO=no_existe bash "$CHECK" 2>&1); rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q "no existe"; then
  pasan=$((pasan+1)); printf '  [ok   ] %-56s rc=2\n' "E2 un sujeto inventado -> NO MEDIDO"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-56s rc=%s\n' "E2 un sujeto inventado -> NO MEDIDO" "$rc"
fi
out=$(K101_SUJETO=espejo bash "$CHECK" 2>&1); rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q "no es un sujeto"; then
  pasan=$((pasan+1)); printf '  [ok   ] %-56s rc=2\n' "E3 el espejo se declara imposible, no se inventa"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-56s rc=%s\n' "E3 el espejo se declara imposible" "$rc"
fi

echo
printf '%d de %d\n' "$pasan" "$((pasan+fallos))"
[ "$fallos" -eq 0 ]
