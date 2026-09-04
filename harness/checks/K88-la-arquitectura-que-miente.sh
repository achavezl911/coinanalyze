#!/bin/bash
# K88  ARQUITECTURA/ DICE ALGO DISTINTO DE LO QUE EL CODIGO HACE.
#
# EL SUJETO. Un documento de arquitectura escrito a mano envejece, y uno que miente es
# PEOR QUE NINGUNO, porque la gente se fia y actua. En esta casa el patron se ha repetido
# nueve veces: algo existe, parece completo, y esta muerto o sin conectar. La unica forma
# de que un mapa siga siendo cierto dentro de un mes es que nadie lo escriba -que salga
# del codigo- y que ALGO COMPARE lo commiteado contra el codigo vivo. Eso es este check.
# Es el patron de K49/respalda-libretas -copia commiteada contra fichero vivo- aplicado a
# la arquitectura en vez de a las libretas.
#
# LOS DOS BRAZOS, Y POR QUE HACEN FALTA LOS DOS
#   1 · DERIVA   lo commiteado no coincide con una regeneracion fresca desde este arbol.
#                Alguien toco el codigo y no regenero, o edito ARQUITECTURA/ a mano.
#   2 · HUECO    existe en el codigo una ruta que el documento no describe.
# El 1 solo no basta: si el generador dejara de descubrir rutas, la regeneracion fresca y
# lo commiteado coincidirian los dos en estar vacios, y el check pasaria en VERDE sobre un
# documento que no describe nada. El 2 es el que impide ese verde. Y el 2 solo tampoco
# basta: cubre la existencia de la ruta, no que su contenido siga siendo cierto.
#
# POR QUE EL CRITERIO 2 CUENTA CON UN INSTRUMENTO DISTINTO DEL GENERADOR.
# Preguntarle al generador cuantas rutas hay y comparar con lo que el generador escribio
# es una tautologia: coincide siempre, incluso si el generador esta ciego. El elegible se
# deriva de un instrumento EXTERNO -grep sobre los decoradores- exactamente por eso.
#
# NO TOCA PRODUCCION NI LA BASE. El sujeto es EL ARBOL. Corre sin red, sin ssh y sin
# PostgreSQL: es analisis estatico contra ficheros.
set -uo pipefail

REPO=${K88_REPO:-/srv/coinanalyze/repo}
GEN="$REPO/harness/bin/arquitectura"
DOC="$REPO/ARQUITECTURA"
API=${K88_API:-$REPO/app/api.py}

# --- canal: si no se puede medir, NOMED. NOMED no es ROJO. -----------------------------
command -v python3 >/dev/null 2>&1 || { echo "NO MEDIDO: no hay python3"; exit 2; }
[ -r "$GEN" ] || { echo "NO MEDIDO: no encuentro el generador en $GEN"; exit 2; }
[ -r "$API" ] || { echo "NO MEDIDO: no encuentro $API, de donde sale el recuento externo"; exit 2; }
python3 -c 'import ast,json,re,filecmp,tempfile' 2>/dev/null || {
  echo "NO MEDIDO: a python3 le falta alguno de ast/json/re/filecmp/tempfile"; exit 2; }

if [ ! -d "$DOC" ]; then
  echo "ARQUITECTURA/ no existe en $REPO: el mapa no esta versionado, asi que no viaja con el codigo"
  exit 1
fi

# --- BRAZO 2 · HUECO ·  el recuento viene de un instrumento EXTERNO al generador --------
# grep sobre los decoradores de FastAPI. Si el generador se quedara ciego, esta cuenta
# seguiria viendo las rutas y el check enrojeceria, que es justo lo que se quiere.
rutas_codigo=$(grep -oE '^@app\.(get|post|put|delete|patch)\("[^"]+"\)' "$API" \
               | sed 's/.*("//; s/")$//' | sort -u)
n_codigo=$(printf '%s\n' "$rutas_codigo" | grep -c . || true)

if [ "$n_codigo" -eq 0 ]; then
  # Cero rutas por grep sobre un api.py legible es un cero SIN MEDICION, no un cero medido:
  # significa que cambio la forma de declarar rutas y este brazo dejo de ver. Un check que
  # se apaga solo y pasa en verde es la averia que K60 describe.
  echo "NO MEDIDO: el grep de decoradores no encuentra NINGUNA ruta en $API (¿cambio la forma de declararlas?)"
  exit 2
fi

if [ ! -r "$DOC/derivada.json" ]; then
  echo "falta $DOC/derivada.json: hay directorio pero no la capa derivada"
  exit 1
fi

rutas_doc=$(python3 -c '
import json,sys
try:
    d=json.load(open(sys.argv[1]))
except Exception as e:
    sys.stderr.write(str(e)); sys.exit(3)
print("\n".join(sorted({r["camino"] for r in d.get("rutas",[])})))' "$DOC/derivada.json") || {
  echo "NO MEDIDO: $DOC/derivada.json no es JSON legible"; exit 2; }

faltan=$(comm -23 <(printf '%s\n' "$rutas_codigo") <(printf '%s\n' "$rutas_doc" | sort -u))
sobran=$(comm -13 <(printf '%s\n' "$rutas_codigo") <(printf '%s\n' "$rutas_doc" | sort -u))
n_doc=$(printf '%s\n' "$rutas_doc" | grep -c . || true)

if [ -n "$faltan" ]; then
  cuantas=$(printf '%s\n' "$faltan" | grep -c .)
  echo "$cuantas rutas existen en el codigo y ARQUITECTURA/ no las describe (de $n_codigo): $(printf '%s' "$faltan" | tr '\n' ' ' | cut -c1-140)"
  exit 1
fi
if [ -n "$sobran" ]; then
  cuantas=$(printf '%s\n' "$sobran" | grep -c .)
  echo "$cuantas rutas descritas en ARQUITECTURA/ YA NO existen en el codigo: $(printf '%s' "$sobran" | tr '\n' ' ' | cut -c1-140)"
  exit 1
fi

# --- BRAZO 1 · DERIVA · lo commiteado contra una regeneracion fresca --------------------
# --comprueba regenera a un temporal y compara fichero a fichero. No escribe en el arbol.
salida=$(python3 "$GEN" --repo "$REPO" --salida "$DOC" --comprueba 2>&1); rc=$?
case "$rc" in
  0) ;;
  1)
    cuantas=$(printf '%s\n' "$salida" | grep -cE '^(FALTA|SOBRA|DIFIERE)' || true)
    primera=$(printf '%s\n' "$salida" | grep -E '^(FALTA|SOBRA|DIFIERE)' | head -3 | tr '\n' ' ')
    echo "ARQUITECTURA/ no coincide con la regeneracion desde este arbol ($cuantas ficheros): $(printf '%s' "$primera" | cut -c1-150)"
    echo "  se arregla regenerando:  harness/bin/arquitectura"
    exit 1 ;;
  *)
    echo "NO MEDIDO: el generador fallo (rc=$rc): $(printf '%s' "$salida" | tail -2 | tr '\n' ' ' | cut -c1-160)"
    exit 2 ;;
esac

echo "ARQUITECTURA/ describe las $n_doc rutas del codigo y coincide con la regeneracion fresca"
exit 0
