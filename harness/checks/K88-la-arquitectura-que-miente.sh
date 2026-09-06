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

# EL ARBOL LO PUEDE FIJAR EL LLAMANTE, Y NO SOLO POR K88_REPO. El gate de K15 en
# .github/workflows/ci.yml exporta `REPO=<worktree>` para medir el arbol del PR contra el de
# main; K88 solo miraba `K88_REPO`, asi que habria medido siempre /srv/coinanalyze/repo -que
# en el runner no existe- y devuelto NOMED. La funcion contar() del gate convierte un NOMED
# en 99, o sea que anadir K88 al gate sin esta linea lo habria dejado CIEGO en vez de darle
# dientes. Lo cazo su control (K15-gate-control.bash, caso G2) antes de entregarlo.
# K88_REPO manda sobre REPO porque es el que usa su propio control, que necesita fijar el
# arbol aunque el entorno traiga otro.
REPO=${K88_REPO:-${REPO:-/srv/coinanalyze/repo}}
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

# --- BRAZO 5 · LA FICHA NO PUEDE CONTRADECIR A LA DERIVADA DEL MISMO COMMIT ------------
# EL CASO QUE LO MOTIVA, y es de manual. `declarada/api-volatility.md` afirmaba «cero
# llamadas y cero menciones, una de las seis rutas sin ningun rastro» mientras
# `derivada.json` del MISMO COMMIT listaba una mencion. Y la mencion era el comentario que
# explicaba que se habia quitado esa ruta del fixture para no contaminar el censo: el
# arreglo quito el fixture y la prosa que lo explicaba volvio a meter la mencion.
# Quien lee ARQUITECTURA/ lee la ficha, no el JSON. Un mapa que se contradice consigo mismo
# en el mismo commit es exactamente lo que este check existe para impedir, y hasta hoy no
# lo cazaba: el brazo 1 compara la derivada contra su regeneracion, y la prosa a mano de la
# capa declarada esta -a proposito- fuera de esa comparacion.
#
# NO se hace en el generador y es deliberado: si el generador leyera estas afirmaciones,
# entrarian en derivada.json y editar una frase de la capa declarada moveria el mapa
# entero, que es justo lo que el mecanismo de F3 evita. Lo comprueba el check, que puede
# mirar las dos capas sin mezclarlas.
desacuerdos=$(python3 - "$DOC" 2>&1 <<'PY'
import json, re, sys
from pathlib import Path
doc = Path(sys.argv[1])
d = json.load(open(doc / "derivada.json"))
por_slug = {}
for r in d["rutas"]:
    s = r["declarada"]["fichero"].split("/")[-1][:-3]
    por_slug[s] = r

# Afirmaciones ACOTADAS y verificables. No se intenta entender la prosa: se buscan frases
# concretas que afirman algo que la derivada ya mide, y solo esas.
REGLAS = [
    (r"cero llamadas",              lambda c: c["n_llamadas"] == 0,            "dice 'cero llamadas'"),
    (r"cero menciones",             lambda c: c["n_menciones"] == 0,           "dice 'cero menciones'"),
    (r"sin ningun rastro",          lambda c: c["sin_ninguno"],                "dice 'sin ningun rastro'"),
    (r"Sin consumidor conocido",    lambda c: c["sin_ninguno"],                "dice 'sin consumidor conocido'"),
    (r"NADIE LA LLAMA",             lambda c: c["n_llamadas"] == 0,            "dice 'nadie la llama'"),
    (r"\*\*La llama el panel",      lambda c: c["llamada_desde_el_panel"],     "dice 'la llama el panel'"),
    (r"[Nn]o la llama el panel",    lambda c: not c["llamada_desde_el_panel"], "dice 'no la llama el panel'"),
]

# LAS SIETE DE ARRIBA MIRAN TODAS `consumo` -QUIEN LLAMA A LA RUTA-. Por eso el brazo era
# ciego a lo que la ruta PUBLICA, y el 2026-09-05 lo demostro: la decision D2 dio
# `as_of`/`window_start`/`window_end` a una ruta de scalp -la de los niveles de
# liquidacion-, su ficha siguio diciendo «INCUMPLE ... ni `as_of`, ni `ts`», y ninguna de
# las siete reglas podia verlo porque el consumo de esa ruta no cambio. La ceguera no era
# de grado sino de FAMILIA.
# (Su camino completo no se escribe aqui: el detector de consumidores lo acreditaria como
#  MENCION, y este comentario pasaria a figurar en el mapa como consumidor suyo.)
# SIN MAYUSCULAS EN EL PATRON. La primera version pedia `no publica` en minuscula y las
# fichas reales escriben «**No publica ninguna marca temporal**» al empezar la frase: el
# control T1 salio VERDE con una ficha que mentia. Van todas con IGNORECASE.
TEMPORAL = [
    (r"no +publican? +ninguna +marca +temporal", "dice 'no publica ninguna marca temporal'"),
    (r"sin +ninguna +marca\s+temporal",          "dice 'sin ninguna marca temporal'"),
    (r"INCUMPLE la promesa de frescura",         "dice 'INCUMPLE la promesa de frescura'"),
]
# UNA FRASE ENTRECOMILLADA NO ES UNA AFIRMACION. Es la misma distincion que «una cadena
# literal no es prosa» de F3d, aplicada aqui. Las siete reglas de arriba eran SENSIBLES A
# MAYUSCULAS y por eso no cazaban «SIN NINGUN RASTRO» en versales; medido el 2026-09-06, con
# `IGNORECASE` a secas cazaban ONCE fichas y NUEVE de ellas **solo citan la formula** narrando
# un fallo pasado -«el andamio escribio "sin consumidor conocido" cuando el detector no
# veia...»-, que no afirma nada de su ruta. Encenderlo asi metia nueve falsos.
# Con el descarte del entrecomillado el IGNORECASE ya se puede encender, que es lo que hace
# esta linea. Se quitan comillas dobles, angulares y acentos graves; el resto se compara.
RE_CITAS = re.compile(r'"[^"\n]{0,200}"|«[^»\n]{0,200}»|`[^`\n]{0,200}`')

malos = []
for f in sorted((doc / "declarada").glob("*.md")):
    r = por_slug.get(f.stem)
    if r is None:
        continue
    texto = f.read_text(encoding="utf-8", errors="replace")
    afirmado = RE_CITAS.sub(" ", texto)
    for pat, ok, etiqueta in REGLAS:
        if re.search(pat, afirmado, re.IGNORECASE) and not ok(r["consumo"]):
            malos.append(f"{f.name} {etiqueta} y la derivada dice "
                         f"llamadas={r['consumo']['n_llamadas']} "
                         f"menciones={r['consumo']['n_menciones']}")
    # familia TEMPORAL: la afirmacion es sobre lo que la ruta PUBLICA, no sobre quien la llama.
    for pat, etiqueta in TEMPORAL:
        if re.search(pat, texto, re.IGNORECASE) and r["claves_temporales"]:
            malos.append(f"{f.name} {etiqueta} y la derivada del mismo commit lista "
                         f"claves_temporales={r['claves_temporales']}")

# LA REGLA QUE NO NECESITA SABER LA VERDAD. Tres fichas citaban «es de las 7 rutas sin
# ninguna marca temporal»; D2 saco una del conjunto y las TRES quedaron viejas a la vez, aun
# sin nombrar a la ruta que cambio. No se puede comprobar el 7 contra la derivada -la
# derivada cuenta rutas cuya respuesta el AST resuelve, la ficha cuenta rutas de la FOTO, y
# fusionar las dos cifras seria medir otra definicion y llamarlo correccion-. Pero SI se
# puede exigir que las fichas coincidan ENTRE ELLAS: si una dice 6 y otra 7, una miente,
# y eso se sabe sin saber cual es el numero bueno.
cifras = {}
for f in sorted((doc / "declarada").glob("*.md")):
    # DOS redacciones para la misma afirmacion -«N rutas sin ninguna» y «N rutas que no
    # publican NINGUNA»-, y el primer patron solo cubria la primera: el control con la ficha
    # de ayer lo enseño en cuanto se corrio.
    for m in re.finditer(r"(?:de las|las) \*{0,2}(\d+) rutas?\b[^.]{0,60}?"
                         r"(?:sin +ninguna|no +publican? +ninguna)",
                         f.read_text(encoding="utf-8", errors="replace"), re.IGNORECASE):
        cifras.setdefault(m.group(1), []).append(f.name)
if len(cifras) > 1:
    detalle = " · ".join(f"{n} en {','.join(sorted(set(fs)))}" for n, fs in sorted(cifras.items()))
    malos.append(f"las fichas no coinciden en cuantas rutas no publican marca temporal: {detalle}")
print("\n".join(malos))
PY
); rc_des=$?

if [ "$rc_des" != "0" ]; then
  echo "NO MEDIDO: el comparador ficha/derivada fallo: $(printf '%s' "$desacuerdos" | tail -1 | cut -c1-120)"
  exit 2
fi
if [ -n "$desacuerdos" ]; then
  n=$(printf '%s\n' "$desacuerdos" | grep -c .)
  echo "$n ficha(s) de la capa declarada contradicen a derivada.json DEL MISMO COMMIT:"
  printf '%s\n' "$desacuerdos" | head -6 | sed 's/^/  /'
  echo "  quien lee ARQUITECTURA/ lee la ficha. Corrige la prosa o regenera."
  exit 1
fi

# --- BRAZO 6 · LA MARCA DE AGUA · ¿alguien ha MIRADO la ficha desde que sus hechos cambiaron?
#
# LOS CINCO BRAZOS DE ARRIBA PERSIGUEN AL ULTIMO FALLO. Cada uno nacio de una ceguera
# concreta: el 1 de una derivada vieja, el 5 de una ficha que contradecia al JSON de su propio
# commit, la familia TEMPORAL de que las siete reglas del 5 solo miraban el consumo. Una tabla
# de reglas **enumera lo conocido**, y la proxima ceguera sera de una familia que nadie ha
# pensado. Este brazo no enumera nada.
#
# NO COMPRUEBA SI LA FICHA ES VERDAD -indecidible sobre prosa-. Comprueba si sus HECHOS han
# cambiado desde que alguien la miro. Cualquier cambio en lo que una ficha puede afirmar
# levanta la marca, incluida una familia que no exista todavia.
#
# LAS DOS PIEZAS:
#   ARQUITECTURA/revision.json          lo emite el generador: sha de los hechos de cada ruta.
#   ARQUITECTURA/declarada/revisado.tsv a mano: el sha que tenia cuando alguien la miro.
# La normalizacion vive en `hechos_de` de harness/bin/arquitectura y cada exclusion se gano
# midiendo: consumo como PREDICADOS y no cuentas, NOMBRES de campo y no sus numeros de linea.
#
# SE CUENTA, NO ENROJECE, igual que la capa declarada incompleta. Una ficha SIN REVISAR no
# esta mintiendo: esta sin mirar. Lo que SI es ROJO es que el fichero de revisiones no se
# pueda leer o se quede sin filas: entonces «0 sin revisar» seria indistinguible de «no he
# mirado nada», que es la trampa de K60 aplicada aqui.
REVJSON="$DOC/revision.json"
REVTSV="$DOC/declarada/revisado.tsv"
if [ ! -r "$REVJSON" ]; then
  echo "NO MEDIDO: falta $REVJSON; lo emite harness/bin/arquitectura y sin el no hay marca fresca"
  exit 2
fi
if [ ! -r "$REVTSV" ]; then
  echo "NO MEDIDO: falta $REVTSV, que es quien dice con que hechos se escribio cada ficha"
  exit 2
fi
marca=$(python3 - "$REVJSON" "$REVTSV" "$DOC" <<'PY' 2>&1
import json, sys
from pathlib import Path
rev = json.load(open(sys.argv[1]))
sellos = {}
for l in Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace").splitlines():
    if not l.startswith("/"):
        continue
    p = l.split("\t")
    if len(p) >= 2:
        sellos[p[0]] = p[1].strip()
fresca = rev.get("rutas", {})
if not sellos:
    print("SINSELLOS"); raise SystemExit
sin_revisar = sorted(c for c, s in fresca.items() if sellos.get(c) != s)
# HUERFANOS: un sello de una ruta que ya no existe. Es la otra direccion, y sin ella el
# fichero se vuelve un cementerio que "revisa" fichas que nadie escribe ya.
huerfanos = sorted(c for c in sellos if c not in fresca)
sin_sello = sorted(c for c in fresca if c not in sellos)
print(f"TOTAL {len(fresca)}")
print(f"SINSELLO {len(sin_sello)} {' '.join(sin_sello[:6])}")
print(f"HUERFANOS {len(huerfanos)} {' '.join(huerfanos[:6])}")
print(f"SINREVISAR {len(sin_revisar)}")
for c in sin_revisar:
    print(f"  S {c}")
PY
); rc_m=$?
case "$marca" in
  SINSELLOS*) echo "NO MEDIDO: $REVTSV no tiene ninguna fila de ruta: o esta vacio o cambio de formato"; exit 2 ;;
esac
[ "$rc_m" = "0" ] || { echo "NO MEDIDO: no se pudo leer la marca de agua: $(printf '%s' "$marca" | tail -1 | cut -c1-110)"; exit 2; }
m_total=$(printf '%s\n' "$marca" | awk '/^TOTAL/{print $2}')
m_sinsello=$(printf '%s\n' "$marca" | awk '/^SINSELLO/{print $2}')
m_huerf=$(printf '%s\n' "$marca" | awk '/^HUERFANOS/{print $2}')
m_sin=$(printf '%s\n' "$marca" | awk '/^SINREVISAR/{print $2}')

echo "ARQUITECTURA/ describe las $n_doc rutas del codigo, coincide con la regeneracion fresca"
echo "  y los cuatro controles de impacto cuadran con su respuesta conocida"
printf '  capa DECLARADA: %s completas · %s incompletas · %s sin declarar (de %s). No es ROJO: se cuenta.\n' \
  "$completas" "$incompletas" "$faltan" "$n_doc"
printf '  MARCA DE AGUA: %s de %s ficha(s) SIN REVISAR -sus hechos cambiaron desde que se escribio su prosa-.\n' \
  "$m_sin" "$m_total"
printf '%s\n' "$marca" | sed -n 's/^  S /    /p'
[ "${m_sinsello:-0}" -eq 0 ] || printf '  %s ruta(s) sin fila en revisado.tsv: siembralas o el brazo no las vigila\n' "$m_sinsello"
[ "${m_huerf:-0}" -eq 0 ] || printf '  %s sello(s) HUERFANO(S) -su ruta ya no existe-: %s\n' "$m_huerf" "$(printf '%s\n' "$marca" | awk '/^HUERFANOS/{$1="";$2="";print}')"
printf '  No es ROJO: se cuenta. Una ficha sin revisar no miente, esta sin mirar.\n'
exit 0
