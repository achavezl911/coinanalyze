#!/bin/bash
# K88-control · LOS DOS BRAZOS DEL GUARDIA, INDUCIDOS FUERA DE LINEA.
#
# Un guardia que caza todo esta tan roto como el que no caza nada, y el brazo negativo
# casi nadie lo prueba. Aqui se prueban los dos con su rc, y ademas los CONTROLES
# ANTI-FANTASMA: que el check no pase en VERDE por no haber llegado a mirar.
#
# EL FANTASMA NO ES TEORICO, ME PASO EL 2026-09-04 CON EL C11 DE K05: escribi un control
# que pasaba tambien cuando el check ni llegaba a leer la serie, y estuvo en verde
# mientras todo lo demas fallaba. Un control que pasa por no ejecutar nada es peor que no
# tenerlo, porque da tranquilidad. Por eso aqui todo lo que no se puede medir se exige
# como rc=2 (NOMED) y NUNCA como rc=0.
#
# NO LLEVA .sh A PROPOSITO. bin/verify globea checks/*.sh y su marcador es del operador;
# este fichero prueba al check, no a produccion. Mismo patron que K86-control.bash.
#
# TODO OCURRE SOBRE UNA COPIA del arbol en un temporal: no se toca /srv/coinanalyze/repo.
# Corre sin red, sin ssh y sin base de datos.
set -uo pipefail

ORIG=${K88_CONTROL_REPO:-/srv/coinanalyze/repo}
CHK="$(cd "$(dirname "$0")" && pwd)/K88-la-arquitectura-que-miente.sh"
[ -r "$CHK" ] || { echo "no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K88_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

# --- la copia limpia sobre la que se induce cada averia --------------------------------
LIMPIO="$DIR/limpio"
mkdir -p "$LIMPIO/harness/bin" "$LIMPIO/harness/checks" "$LIMPIO/sql"
cp -r "$ORIG/app" "$LIMPIO/app" 2>/dev/null || { echo "NO MEDIDO: no puedo copiar app/"; exit 2; }
cp "$ORIG/sql/schema.sql" "$LIMPIO/sql/" 2>/dev/null || { echo "NO MEDIDO: falta sql/schema.sql"; exit 2; }
cp "$ORIG/harness/bin/arquitectura" "$LIMPIO/harness/bin/" || exit 2
cp "$CHK" "$LIMPIO/harness/checks/" || exit 2
rm -rf "$LIMPIO/app/__pycache__" 2>/dev/null
python3 "$LIMPIO/harness/bin/arquitectura" --repo "$LIMPIO" >/dev/null 2>&1 || {
  echo "NO MEDIDO: el generador no corre sobre la copia"; exit 2; }

# caso <nombre> <rc esperado> <patron que DEBE salir en el mensaje> -- el cuerpo muta $T
caso() {
  local nombre="$1" esperado="$2" patron="$3"; shift 3
  T="$DIR/t"; rm -rf "$T"; cp -r "$LIMPIO" "$T"
  "$@" >/dev/null 2>&1
  local out rc
  out=$(K88_REPO="$T" bash "$T/harness/checks/K88-la-arquitectura-que-miente.sh" 2>&1); rc=$?
  local ok=1
  [ "$rc" = "$esperado" ] || ok=0
  # HUELLA POSITIVA: no basta el rc, el mensaje tiene que demostrar que miro LO QUE CREES.
  # Sin esto, un rc=1 por una razon equivocada cuenta como acierto. Es la leccion de C11.
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasans=pasan+1))
    printf '  [ok   ] %-46s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-46s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-150)"
  fi
}

nada() { :; }

echo "K88-control · sujeto: $CHK"
echo "             copia:  $DIR/limpio  (el arbol real no se toca)"
echo

# ======================================================================================
# BRAZO NEGATIVO · el check NO PUEDE enrojecer cuando no hay nada roto.
# Es el brazo que casi nadie prueba y el que decide si el check sobrevive un mes: un
# guardia que enrojece por ruido se apaga solo, porque la gente deja de mirarlo.
# ======================================================================================
echo "BRAZO NEGATIVO · sin averia, tiene que dar VERDE"
caso "N1 arbol recien generado" 0 "coincide con la regeneracion" nada

# N2 · UN CAMBIO EN EL CODIGO QUE NO CAMBIA LO DERIVADO NO PUEDE ENROJECER.
# Se anade un comentario AL FINAL de api.py: no desplaza ninguna linea de ninguna funcion
# y no toca el AST derivado. Si esto enrojeciera, el check seria "cualquier commit = ROJO"
# y estaria muerto en una semana. Al final y no al principio a proposito: arriba SI
# desplazaria los numeros de linea, y entonces ROJO seria la respuesta correcta.
n2() { printf '\n# comentario que no cambia el AST derivado\n' >> "$T/app/api.py"; }
caso "N2 comentario al final de api.py" 0 "coincide con la regeneracion" n2

# N3 · un fichero .py nuevo SIN rutas tampoco puede enrojecer.
n3() { printf 'def suma(a, b):\n    return a + b\n' > "$T/app/_control_k88.py"; }
caso "N3 modulo nuevo sin rutas" 0 "coincide con la regeneracion" n3

echo
# ======================================================================================
# BRAZO POSITIVO · cada forma conocida de que el documento mienta.
# ======================================================================================
echo "BRAZO POSITIVO · con averia inducida, tiene que dar ROJO"

p1() { rm -rf "$T/ARQUITECTURA"; }
caso "P1 no existe ARQUITECTURA/" 1 "no existe" p1

p2() { rm -f "$T/ARQUITECTURA/derivada.json"; }
caso "P2 falta derivada.json" 1 "falta.*derivada.json" p2

p3() { rm -f "$T/ARQUITECTURA/rutas/api-setup.md"; }
caso "P3 borrada la ficha de una ruta" 1 "no coincide con la regeneracion" p3

# P4 · EL CASO QUE MOTIVA TODO EL CHECK: alguien edita el documento a mano para que diga
# lo que le conviene. Un caracter cambiado tiene que bastar.
p4() { sed -i 's/`symbol`/`simbolo_inventado`/' "$T/ARQUITECTURA/rutas/api-setup.md"; }
caso "P4 ficha editada a mano (un campo)" 1 "no coincide con la regeneracion" p4

# P5 · ruta nueva en el codigo sin regenerar. Es el caso ordinario: se anade un endpoint
# y se olvida el mapa. El documento no miente por lo que dice, sino por lo que calla.
p5() {
  cat >> "$T/app/api.py" <<'PY'


@app.get("/api/control-k88")
async def control_k88() -> dict[str, str]:
    return {"control": "k88"}
PY
}
caso "P5 ruta nueva sin regenerar (HUECO)" 1 "no las describe" p5

# P6 · ruta retirada del codigo y el documento sigue anunciandola. Es peor que el hueco:
# promete una superficie que ya no existe.
p6() { sed -i 's|^@app\.get("/api/setup")|@app.get("/api/setup-renombrada")|' "$T/app/api.py"; }
caso "P6 ruta renombrada sin regenerar" 1 "(no las describe|YA NO existen)" p6

# P7 · TAUTOLOGIA. Se vacia la lista de rutas de derivada.json dejando las 68 fichas .md
# en su sitio. Si el brazo 2 preguntara al propio generador en vez de a un instrumento
# externo, esto pasaria en VERDE.
p7() {
  python3 - "$T/ARQUITECTURA/derivada.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["rutas"] = []
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False, sort_keys=True)
PY
}
caso "P7 derivada.json sin rutas, fichas intactas" 1 "no las describe" p7

# P8 · el codigo cambia de forma que SI mueve las lineas. Aqui ROJO es lo correcto: los
# numeros de linea que publica el mapa dejarian de apuntar donde dicen.
p8() { sed -i '1i # linea insertada arriba que desplaza todo el fichero' "$T/app/api.py"; }
caso "P8 desplazadas las lineas de api.py" 1 "no coincide con la regeneracion" p8

echo
# ======================================================================================
# ANTI-FANTASMA · lo que no se puede medir tiene que salir NOMED (rc=2), nunca VERDE.
# Un check que da VERDE porque no llego a mirar es la averia mas cara de este arnes.
# ======================================================================================
echo "ANTI-FANTASMA · sin poder medir, NOMED (rc=2) y jamas VERDE"

f1() { rm -f "$T/harness/bin/arquitectura"; }
caso "F1 sin generador" 2 "NO MEDIDO" f1

f2() { rm -f "$T/app/api.py"; }
caso "F2 sin api.py" 2 "NO MEDIDO" f2

# F3 · api.py existe y es legible pero no tiene ni un decorador de ruta. CERO rutas por
# grep NO es un cero medido: es que cambio la forma de declararlas y el brazo externo se
# quedo ciego. Tiene que ser NOMED. Si esto diera VERDE, bastaria con migrar a un router
# para que K88 dejara de vigilar nada, en silencio y para siempre.
f3() { printf 'x = 1\n' > "$T/app/api.py"; }
caso "F3 api.py sin decoradores (cero sin medicion)" 2 "NO MEDIDO" f3

f4() { printf 'no soy json' > "$T/ARQUITECTURA/derivada.json"; }
caso "F4 derivada.json corrupto" 2 "NO MEDIDO" f4

# F5 · el generador existe pero revienta. NOMED, no VERDE y no ROJO: no se ha medido.
f5() { printf 'import sys\nsys.exit(9)\n' > "$T/harness/bin/arquitectura"; }
caso "F5 el generador falla al correr" 2 "NO MEDIDO" f5

echo
# ======================================================================================
# HUELLA · que el brazo 1 y el brazo 2 son DE VERDAD independientes.
# P7 aisla el brazo 2 (fichas correctas, JSON vaciado). Este aisla el brazo 1: se induce
# una deriva que el brazo 2 NO puede ver, porque el conjunto de rutas sigue siendo
# exactamente el mismo. Si el check pasara, el brazo 1 no estaria haciendo nada.
# ======================================================================================
echo "HUELLA · los dos brazos cazan cosas distintas"
h1() { sed -i 's/"linea": 2008/"linea": 99999/' "$T/ARQUITECTURA/derivada.json"; }
caso "H1 deriva invisible al brazo 2" 1 "no coincide con la regeneracion" h1

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
