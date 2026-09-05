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
    # UN TRACEBACK DE PYTHON TAMBIEN SALE CON 1, Y ESE ES EL MODO DE FALLO MAS PROBABLE
    # DEL GENERADOR. La version anterior de este check llamaba ROJO a un generador
    # reventado, y encima con el recuento "(0 ficheros)" delante, que es la forma exacta
    # de un veredicto que no se sostiene. Confundir "esta roto" con "no se pudo medir" es
    # justo lo que los tres estados de este arnes existen para impedir. Se cazo el
    # 2026-09-05 induciendolo con el control I5, y el caso F5 no lo cubria porque su
    # generador falso salia con 9, no con 1.
    if [ "$cuantas" -eq 0 ] || printf '%s' "$salida" | grep -q 'Traceback (most recent call last)'; then
      echo "NO MEDIDO: el generador salio con 1 pero no listo ninguna discrepancia: $(printf '%s' "$salida" | grep -E 'Error|Traceback' | tail -1 | cut -c1-140)"
      exit 2
    fi
    primera=$(printf '%s\n' "$salida" | grep -E '^(FALTA|SOBRA|DIFIERE)' | head -3 | tr '\n' ' ')
    echo "ARQUITECTURA/ no coincide con la regeneracion desde este arbol ($cuantas ficheros): $(printf '%s' "$primera" | cut -c1-150)"
    echo "  se arregla regenerando:  harness/bin/arquitectura"
    exit 1 ;;
  *)
    echo "NO MEDIDO: el generador fallo (rc=$rc): $(printf '%s' "$salida" | tail -2 | tr '\n' ' ' | cut -c1-160)"
    exit 2 ;;
esac

# --- BRAZO 3 · LOS CONTROLES DE RESPUESTA CONOCIDA ------------------------------------
# El brazo 1 compara el documento consigo mismo regenerado, y el 2 comprueba que estan
# todas las rutas. Ninguno de los dos ve que el GRAFO DE IMPACTO se haya torcido: si el
# generador empieza a atribuir mal, regenera coherente y las dos comparaciones pasan.
# Por eso el generador mide en cada corrida tres preguntas de respuesta conocida:
#   compute_snapshot      -> 0 rutas por llamada, 8 por tabla (las de metrics_snapshot)
#   spot_trades_agg       -> 2 INSERT de ws_collector + 1 DELETE de daily_agg
#   liquidations_realtime -> 1 escritor en scalp_collector.py:74 y 14 rutas lectoras
# Las tres tienen respuesta verificada FUERA de este programa -dos contra el codigo por el
# operador, una contra la base de 140, 3241 filas el 2026-09-04-. La tercera es la que
# nacio de un fallo real: en F1 daba CERO escritores porque el generador no resolvia SQL
# guardado en una constante de modulo.
cuadran=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
c=d.get("controles")
if not c: print("SINCAMPO"); raise SystemExit
malos=[k for k,v in c.items() if isinstance(v,dict) and not v.get("cuadra")]
print(",".join(malos) if malos else "OK")' "$DOC/derivada.json" 2>/dev/null)

case "$cuadran" in
  OK) ;;
  SINCAMPO)
    echo "NO MEDIDO: derivada.json no trae el bloque 'controles' (¿version de formato vieja?)"
    exit 2 ;;
  "")
    echo "NO MEDIDO: no se pudo leer el bloque 'controles' de derivada.json"
    exit 2 ;;
  *)
    echo "el grafo de impacto no cuadra con su respuesta conocida: $cuadran"
    echo "  no es una diferencia de formato: el generador esta atribuyendo mal"
    exit 1 ;;
esac

# --- BRAZO 4 · LA CAPA DECLARADA · CUENTA, NO ENROJECE (todavia) -----------------------
# La capa declarada (F3) es la unica que se escribe a mano: pregunta del trader, familia de
# ventana K43, promesa y superficie. No se puede exigir completa de golpe -son 68 rutas y
# cada linea necesita su cita-, asi que este brazo CUENTA cuantas faltan y lo dice en el
# mensaje. Poner ROJO hoy solo enseñaria a ignorar el check.
#
# LO QUE SI ES ROJO: una declarada HUERFANA, de una ruta que ya no existe. Es el mismo
# defecto que el brazo 2 por el otro lado -el documento anunciando algo que no esta- y
# ademas es basura que nadie va a retirar si nadie la nombra.
# El lector va en un heredoc y NO en `python3 -c '...'`. La version anterior llevaba un
# f-string con comillas escapadas dentro de comillas simples de shell y reventaba con
# SyntaxError; el check lo leia como cadena vacia y publicaba "derivada.json no trae el
# recuento" -un diagnostico FALSO, porque el campo estaba ahi-. Es la misma confusion que
# ya se corrigio en el brazo 1: el instrumento fallando disfrazado de dato malo. Por eso
# ahora se distingue el rc del parser de la ausencia del campo.
lectura=$(python3 - "$DOC/derivada.json" 2>&1 <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
r = d.get("resumen", {})
if r.get("sin_declarar") is None:
    print("SINCAMPO")
else:
    print("%s\t%s\t%s" % (r.get("declaradas_completas"),
                          r.get("declaradas_incompletas"),
                          r.get("sin_declarar")))
PY
); rc_lect=$?

if [ "$rc_lect" != "0" ]; then
  echo "NO MEDIDO: el lector del recuento de la capa declarada fallo: $(printf '%s' "$lectura" | tail -1 | cut -c1-120)"
  exit 2
fi
if [ "$lectura" = "SINCAMPO" ]; then
  echo "NO MEDIDO: derivada.json no trae el recuento de la capa declarada (¿formato viejo?)"
  exit 2
fi
completas=$(printf '%s' "$lectura" | cut -f1)
incompletas=$(printf '%s' "$lectura" | cut -f2)
faltan=$(printf '%s' "$lectura" | cut -f3)

if [ -d "$DOC/declarada" ]; then
  huerfanas=''
  for f in "$DOC"/declarada/*.md; do
    [ -e "$f" ] || continue
    s=$(basename "$f" .md)
    grep -q "\"declarada\/$s.md\"" "$DOC/derivada.json" || huerfanas="$huerfanas $s"
  done
  if [ -n "$huerfanas" ]; then
    n=$(printf '%s' "$huerfanas" | wc -w)
    echo "$n declaracion(es) HUERFANA(s): describen una ruta que ya no existe:$huerfanas"
    echo "  el documento anuncia una superficie retirada. Borralas o restaura la ruta."
    exit 1
  fi
fi

echo "ARQUITECTURA/ describe las $n_doc rutas del codigo, coincide con la regeneracion fresca"
echo "  y los cuatro controles de impacto cuadran con su respuesta conocida"
printf '  capa DECLARADA: %s completas · %s incompletas · %s sin declarar (de %s). No es ROJO: se cuenta.\n' \
  "$completas" "$incompletas" "$faltan" "$n_doc"
exit 0
