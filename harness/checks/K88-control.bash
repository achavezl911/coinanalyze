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
# EL PROPIO FICHERO, EN ABSOLUTO Y ANTES DEL cd. El barrido AC1 se grepea a si mismo, y con
# `$0` relativo mas el `cd "$DIR"` de mas abajo daba "de 0 rutas nombradas, 0 reales" — un
# ok por no haber leido nada. Es el mismo fantasma que este control lleva cuatro rondas
# cazando en otros, cometido aqui.
YO="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
CHK="$(cd "$(dirname "$0")" && pwd)/K88-la-arquitectura-que-miente.sh"
[ -r "$CHK" ] || { echo "no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K88_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

# SE CORRE DESDE UN DIRECTORIO QUE NO ES EL REPO, A PROPOSITO.
# Cinco cuerpos invocaban el generador por ruta RELATIVA -`python3 harness/bin/arquitectura`-
# con el error a /dev/null. Desde el repo el relativo resolvia y todo pasaba; desde
# /home/devops no existia, la regeneracion NO OCURRIA, y D1 y D3 juzgaban un arbol sin
# regenerar: 26 de 28 desde fuera contra 28 de 28 desde dentro. El mismo control daba dos
# veredictos segun quien lo lanzara, que es la enfermedad que K63 describe para el marcador.
# Arrancar aqui es la huella de que ya no depende del cwd: si alguien vuelve a meter una
# ruta relativa, este cd la caza en la primera corrida.
cd "$DIR" || exit 2

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

# LA MARCA DE AGUA SE SIEMBRA EN EL FIXTURE BASE, y no es un detalle: el brazo 6 dice NOMED
# si falta revisado.tsv, asi que sin sembrarlo TODOS los casos que esperan rc=0 caerian por
# ahi y probarian otra cosa. Se siembra AL DIA -copiando revision.json- para que el estado
# por defecto del fixture sea "nadie tiene nada pendiente" y cada caso induzca lo suyo.
_sella() {  # <arbol>
  python3 - "$1" <<'PYS'
import json, sys
from pathlib import Path
t = Path(sys.argv[1])
rev = json.load(open(t / "ARQUITECTURA/revision.json"))
p = t / "ARQUITECTURA/declarada/revisado.tsv"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("# fixture del control: sellos al dia\n"
             + "".join(f"{c}\t{s}\tdeadbeef\t2026-01-01\n" for c, s in sorted(rev["rutas"].items())),
             encoding="utf-8")
PYS
}
_sella "$LIMPIO" || { echo "NO MEDIDO: no se pudo sembrar la marca de agua en la copia"; exit 2; }

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
# LA RUTA QUE SE RENOMBRA SE AÑADE PRIMERO, y no es una real. Antes este cuerpo hacia
# `sed` sobre `@app.get("/api/setup")`, o sea que el mapa acreditaba como CONSUMIDOR de
# /api/setup la linea cuyo proposito es BORRARLA. Es la misma contaminacion que se cazo en
# F3b con /api/volatility, en otro sitio: el instrumento colandose en su propio censo.
p6() {
  cat >> "$T/app/api.py" <<'PY'


@app.get("/api/zzz-fixture-p6")
async def zzz_fixture_p6() -> dict[str, str]:
    return {"control": "p6"}
PY
  python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
  sed -i 's|^@app\.get("/api/zzz-fixture-p6")|@app.get("/api/zzz-fixture-p6-renombrada")|' "$T/app/api.py"
}
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
# CAPA DE IMPACTO (F2) · el brazo 1 la compara porque compara TODOS los ficheros, pero
# "porque si" no es una prueba. Aqui se induce.
# ======================================================================================
echo "IMPACTO · la capa de F2 tambien esta guardada"

# I1 · EL CASO QUE PIDIO EL OPERADOR: alguien edita a mano un radio en una ficha de ruta
# para que diga que su cambio afecta a menos cosas de las que afecta. Es la mentira mas
# rentable que se puede contar en este documento, y por eso tiene que costar ROJO.
i1() { sed -i 's/| \*\*8\*\* |/| **1** |/' "$T/ARQUITECTURA/impacto/app-metrics.md"; }
caso "I1 radio editado a mano en impacto/" 1 "no coincide con la regeneracion" i1

# I2 · el mismo fraude en la ficha de la ruta, que es donde lo leeria quien va a tocarla.
i2() { sed -i '0,/| \*\*[0-9]*\*\* | \[impacto\]/s//| **0** | [impacto]/' \
         "$T/ARQUITECTURA/rutas/api-snapshot.md"; }
caso "I2 radio editado a mano en una ficha de ruta" 1 "no coincide con la regeneracion" i2

# I3 · IMPACTO.md borrado entero.
i3() { rm -f "$T/ARQUITECTURA/IMPACTO.md"; }
caso "I3 IMPACTO.md borrado" 1 "no coincide con la regeneracion" i3

# I4 · BRAZO 3 · SE AVERIA EL GENERADOR, NO SU SALIDA. Y esa distincion es el control.
# Mi primera version de este caso editaba `cuadra` dentro de derivada.json, y no probaba
# nada: el brazo 1 cazaba el JSON tocado ANTES de que el brazo 3 llegara a mirar, o sea
# que el caso pasaba por la razon equivocada. El unico escenario donde el brazo 3 es
# NECESARIO es este: el generador atribuye mal Y regenera coherente, asi que el documento
# cuadra consigo mismo y el brazo 1 no tiene nada que decir.
# La averia inducida no es inventada: es la REGRESION concreta al comportamiento de F1
# -devolver la linea donde abre el literal en vez de la del verbo SQL-, que ponia el
# escritor de liquidations_realtime en :73 cuando esta en :74.
i4() {
  sed -i 's/^    for i, l in enumerate(texto.splitlines()):$/    for i, l in []:/' \
      "$T/harness/bin/arquitectura"
  python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
}
caso "I4 generador con la regresion de F1 en las lineas" 1 "no cuadra con su respuesta conocida" i4

# I5 · un generador de version anterior que no emite el bloque 'controles'. Regenera
# coherente, asi que el brazo 1 pasa; el brazo 3 no puede juzgar y tiene que decir NOMED.
# No es que el impacto este mal: es que este check no sabe si lo esta.
i5() {
  sed -i 's/^def controles_de_respuesta_conocida(impacto: dict, tablas: dict, ey: dict) -> dict:$/&\n    return {}/' \
      "$T/harness/bin/arquitectura"
  python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
}
caso "I5 generador que no emite el bloque de controles" 2 "NO MEDIDO" i5

# I6 · EL GENERADOR REVIENTA CON TRACEBACK. Python sale con 1, igual que "hay
# discrepancias", asi que este es el modo de fallo mas probable y el mas facil de leer
# mal. F5 no lo cubria: su generador falso salia con 9. La version anterior del check
# decia ROJO con "(0 ficheros)" delante. Tiene que ser NOMED.
# El patron ancla en `def construye(` SIN la lista de argumentos: la version anterior
# fijaba la firma entera y dejo de casar en cuanto `construye` gano un parametro. El caso
# no reventaba: pasaba a rc=0 y habria contado como "el check no enrojece", que es lo
# contrario de lo que prueba. Lo cazo la huella positiva; sin ella habria quedado en verde.
i6() { sed -i 's/^def construye(.*$/&\n    raise RuntimeError("averia inducida por I6")/' \
         "$T/harness/bin/arquitectura"; }
caso "I6 el generador revienta con traceback (rc=1)" 2 "NO MEDIDO" i6

echo
# ======================================================================================
# CAPA DECLARADA (F3) · LA ASIMETRIA QUE HACE QUE EL MECANISMO SIRVA.
# La declarada se escribe a mano y tiene que SOBREVIVIR a la regeneracion. La derivada
# editada a mano tiene que seguir fallando. Si las dos se comportaran igual, o bien la
# declarada seria inmantenible o bien la derivada quedaria sin guardia.
# ======================================================================================
echo "DECLARADA · la editada a mano sobrevive; la derivada editada a mano, no"

# D1 · (a) del encargo: editar la PROSA de una declarada no rompe nada.
d1() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       mkdir -p "$T/ARQUITECTURA/declarada"
       printf '# X\n\n## PREGUNTA\nq\n\n## VENTANA\nv\n\n## PROMESA\np\n\n## SUPERFICIE\ns\n' \
         > "$T/ARQUITECTURA/declarada/api-setup.md"
       python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       # ahora se EDITA A MANO, sin regenerar
       printf '\n\nprosa anadida a mano despues de regenerar.\n' \
         >> "$T/ARQUITECTURA/declarada/api-setup.md"; }
caso "D1 declarada editada a mano SIN regenerar" 0 "coincide con la regeneracion" d1

# D2 · (b) del encargo: la derivada editada a mano sigue siendo ROJO. Es el mismo P4 de
# arriba, repetido aqui a proposito para que la asimetria se lea de un vistazo: los dos
# casos, juntos, son el mecanismo entero.
d2() { sed -i 's/`snapshot_ts`/`inventado_ts`/' "$T/ARQUITECTURA/rutas/api-setup.md"; }
caso "D2 derivada editada a mano SIGUE siendo ROJO" 1 "no coincide con la regeneracion" d2

# D3 · (c) del encargo: una ruta nueva CON su ficha regenerada pero SIN declarada sale
# como PENDIENTE y se CUENTA, sin ROJO. Es lo que permite avanzar por fases en vez de
# exigir 68 declaraciones de golpe.
d3() {
  cat >> "$T/app/api.py" <<'PY'


@app.get("/api/control-declarada")
async def control_declarada() -> dict[str, str]:
    return {"control": "declarada"}
PY
  python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
}
caso "D3 ruta nueva sin declarada: PENDIENTE y contada" 0 "sin declarar" d3

# D4 · una declaracion HUERFANA -de una ruta que ya no existe- SI es ROJO: es el brazo 2
# por el otro lado, el documento anunciando una superficie retirada.
d4() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       mkdir -p "$T/ARQUITECTURA/declarada"
       printf '# fantasma\n\n## PREGUNTA\nq\n' > "$T/ARQUITECTURA/declarada/api-ruta-que-no-existe.md"; }
caso "D4 declaracion huerfana" 1 "HUERFANA" d4

# D5 · una declarada a la que le falta una seccion cambia la ficha, asi que hay que
# regenerar. Es el limite del mecanismo y se prueba: la ESTRUCTURA esta guardada, la PROSA
# no. K88 comprueba que la declaracion existe y esta completa, NO que sea cierta -eso lo
# mide F5 con la bateria-.
d5() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       mkdir -p "$T/ARQUITECTURA/declarada"
       printf '# X\n\n## PREGUNTA\nq\n' > "$T/ARQUITECTURA/declarada/api-setup.md"; }
caso "D5 declarada incompleta obliga a regenerar" 1 "no coincide con la regeneracion" d5

echo
# ======================================================================================
# EL DETECTOR DE CONSUMIDORES · su acierto y su falso positivo, los dos.
# El detector viejo exigia comillas alrededor de la ruta y no veia `RUTA=/api/x`, que es
# como la escriben K21..K25: cinco fichas de /api/signals/* afirmaban "NINGUN consumidor"
# y su consumidor era el check que las mide. Se cambio a un limite de token. El motivo del
# diseño viejo era legitimo -que /api/cvd no case con /api/cvd/spot- y por eso va aqui
# como control: un detector que caza de mas es tan inutil como uno que caza de menos.
# ======================================================================================
echo "TEMPORAL · la familia que las siete reglas de consumo no podian ver"
# LAS SIETE REGLAS DEL BRAZO 5 MIRABAN TODAS `consumo`. El 2026-09-05 la decision D2 dio
# `as_of` a una ruta, su ficha siguio diciendo «INCUMPLE ... ni as_of, ni ts», y ninguna
# regla podia cazarlo porque el consumo no habia cambiado. La ceguera era de FAMILIA.
# Los fixtures eligen la ruta LEYENDO derivada.json, no por su nombre: asi no caducan
# cuando cambie que rutas publican marca temporal.
# EL ORDEN IMPORTA, y es el mismo de D1: esqueleto -> REGENERAR -> añadir la frase. Crear
# una ficha cambia `declarada.completa` en derivada.json, asi que escribirla sin regenerar
# enrojece el brazo 1 y el caso mediria otra cosa. Lo enseño el propio brazo 1 al correrlo.
_elige() {  # <con_claves 0|1> -> imprime la ruta relativa de su ficha
  python3 - "$T" "$1" <<'PY'
import json, sys
from pathlib import Path
t, quiere = Path(sys.argv[1]), sys.argv[2] == "1"
d = json.load(open(t / "ARQUITECTURA/derivada.json"))
print(next(x for x in d["rutas"] if bool(x["claves_temporales"]) == quiere)["declarada"]["fichero"])
PY
}
_esqueleto() {  # <fichero relativo>
  mkdir -p "$T/ARQUITECTURA/declarada"
  printf '# x\n\n## PREGUNTA\nq\n\n## VENTANA\nv\n\n## PROMESA\np\n\n## SUPERFICIE\ns\n' \
    > "$T/ARQUITECTURA/$1"
}
_gen() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1; }

t1() { _gen; f=$(_elige 1); _esqueleto "$f"; _gen
       printf '\nNo publica ninguna marca temporal.\n' >> "$T/ARQUITECTURA/$f"; }
caso "T1 ficha niega la marca y la derivada la lista" 1 "claves_temporales=" t1

# T2 · CONTROL NEGATIVO. La misma frase sobre una ruta que de verdad no publica marca no
# puede enrojecer. Sin este caso, T1 solo probaria que el patron casa con el texto.
t2() { _gen; f=$(_elige 0); _esqueleto "$f"; _gen
       printf '\nNo publica ninguna marca temporal.\n' >> "$T/ARQUITECTURA/$f"; }
caso "T2 la misma frase sobre una ruta SIN marca: VERDE" 0 "coincide con la regeneracion" t2

# T3 · LA REGLA QUE NO NECESITA SABER LA VERDAD. Tres fichas citaban «las 7 rutas sin
# ninguna marca temporal»; D2 saco una del conjunto y las tres quedaron viejas a la vez sin
# nombrar a la ruta que cambio. El 7 no se puede comprobar contra la derivada -cuenta otra
# cosa: rutas cuya respuesta el AST resuelve, no rutas de la foto-, pero SI se puede exigir
# que las fichas coincidan ENTRE ELLAS. Si una dice 6 y otra 7, una miente, y eso se sabe
# sin saber cual es el numero bueno.
# Las DOS fichas van sobre rutas SIN claves temporales, para que lo unico que enrojezca sea
# el desacuerdo entre las cifras y no la familia TEMPORAL de T1.
t3() { _gen; a=$(_elige 0); _esqueleto "$a"; _gen
       b="declarada/$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
c=[x for x in d["rutas"] if not x["claves_temporales"]]
print(c[1]["declarada"]["fichero"].split("/")[-1])' "$T/ARQUITECTURA/derivada.json")"
       _esqueleto "$b"; _gen
       printf '\nEs de las 6 rutas sin ninguna marca temporal.\n'          >> "$T/ARQUITECTURA/$a"
       printf '\nEs de las 7 rutas que no publican NINGUNA marca temporal.\n' >> "$T/ARQUITECTURA/$b"; }
caso "T3 dos fichas citan cifras distintas del mismo censo" 1 "no coinciden en cuantas" t3

# T4 · y la regla de cifras NO puede ser un si-siempre: con una sola cifra citada, calla.
t4() { _gen; f=$(_elige 0); _esqueleto "$f"; _gen
       printf '\nEs de las 6 rutas sin ninguna marca temporal.\n' >> "$T/ARQUITECTURA/$f"; }
caso "T4 una sola cifra citada: la regla calla" 0 "coincide con la regeneracion" t4

echo
echo "CONSUMIDORES · caza lo que debe y no caza de mas"

cons() {  # $1 = ruta   -> imprime "llamadas menciones" contra un fichero de prueba
  python3 - "$T" "$1" <<'PY'
import sys, json
from importlib.machinery import SourceFileLoader
from pathlib import Path
T, ruta = sys.argv[1], sys.argv[2]
m = SourceFileLoader("arq", f"{T}/harness/bin/arquitectura").load_module()
c = m.consumidores_de(Path(T), ruta)
r = m.resume_consumo(c)
print(r["n_llamadas"], r["n_menciones"])
PY
}

# C-D1 · el caso que motivo el arreglo: RUTA=/api/x sin comillas ES una llamada.
cd1() {
  mkdir -p "$T/harness/checks"
  printf '#!/bin/sh\nRUTA=/api/zzz-fixture-cd1\ncurl "$RUTA"\n' > "$T/harness/checks/Kzz.sh"
}
T="$DIR/cons"; rm -rf "$T"; cp -r "$LIMPIO" "$T"; cd1
lee=$(cons /api/zzz-fixture-cd1)
if [ "$lee" = "1 0" ]; then
  pasan=$((pasan+1)); printf '  [ok   ] %-46s %s\n' "CD1 RUTA=/api/x sin comillas es LLAMADA" "$lee"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-46s dio "%s", esperaba "1 0"\n' "CD1 RUTA=/api/x sin comillas" "$lee"
fi

# C-D2 · EL FALSO POSITIVO QUE HAY QUE SEGUIR EVITANDO. Un fichero que solo nombra
# /api/cvd/spot NO puede contar como consumidor de /api/cvd. Es el motivo por el que el
# detector viejo exigia comillas, y el limite de token tiene que conservarlo.
cd2() {
  mkdir -p "$T/harness/checks"
  printf '#!/bin/sh\ncurl "/api/zzz-fix/sub"\n' > "$T/harness/checks/Kzz.sh"
}
T="$DIR/cons2"; rm -rf "$T"; cp -r "$LIMPIO" "$T"; cd2
corta=$(cons /api/zzz-fix); larga=$(cons /api/zzz-fix/sub)
if [ "$corta" = "0 0" ] && [ "$larga" = "1 0" ]; then
  pasan=$((pasan+1)); printf '  [ok   ] %-46s corta=%s larga=%s\n' "CD2 el prefijo NO casa con la ruta larga" "$corta" "$larga"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-46s corta=%s (esperaba "0 0") larga=%s (esperaba "1 0")\n' \
    "CD2 limite de token" "$corta" "$larga"
fi

# C-D3 · un comentario es MENCION, no llamada. Sin esta distincion, una ruta de la que
# solo se habla figura como consumida.
#
# LA RUTA DEL FIXTURE NO EXISTE, Y ES DELIBERADO. La primera version usaba
# /api/volatility, que es una ruta REAL, y con eso este control se colaba en el censo: el
# fichero pasaba a mencionarla y su ficha dejaba de decir "sin consumidor". El instrumento
# se estaba midiendo a si mismo y movia la cifra que el propio mapa publica. Con una ruta
# inventada el control ejercita lo mismo y no contamina nada.
cd3() {
  mkdir -p "$T/harness/checks"
  printf '#!/bin/sh\n# esta prueba mira /api/zzz-fixture-cd3 algun dia\necho hola\n' > "$T/harness/checks/Kzz.sh"
}
T="$DIR/cons3"; rm -rf "$T"; cp -r "$LIMPIO" "$T"; cd3
lee=$(cons /api/zzz-fixture-cd3)
if [ "$lee" = "0 1" ]; then
  pasan=$((pasan+1)); printf '  [ok   ] %-46s %s\n' "CD3 un comentario es MENCION, no llamada" "$lee"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-46s dio "%s", esperaba "0 1"\n' "CD3 comentario es mencion" "$lee"
fi

echo
# ======================================================================================
# EL INSTRUMENTO NO PUEDE COLARSE EN SU PROPIO CENSO · barrido, no caso a caso.
#
# Es la TERCERA vez que la misma contaminacion aparece en otro sitio:
#   F3b  /api/volatility en el fixture de CD3 -> su ficha dejaba de decir "sin consumidor"
#   F3d  /api/setup en p6 -> el mapa acreditaba como CONSUMIDOR la linea que la BORRA
#   F3d  /api/signals/ledger en CD1, /api/cvd y /api/cvd/spot en CD2
# Arreglarlas una a una ya fallo dos veces. Esto barre el fichero entero y falla si queda
# CUALQUIER ruta real, sin importar en que caso este. Los fixtures usan rutas inventadas
# -zzz-*, control-*- que no existen en el codigo, asi que nombrarlas no mueve ningun censo.
# ======================================================================================
echo "AUTOCONTAMINACION · ningun fixture puede nombrar una ruta REAL"

reales=$(grep -oE "/api/[a-z0-9/_-]+" "$YO" | sort -u)
# El elegible sale de un instrumento EXTERNO: los decoradores del api.py de verdad.
existen=$(grep -oE '^@app\.(get|post|put|delete|patch)\("[^"]+"\)' "$ORIG/app/api.py" \
          | sed 's/.*("//; s/")$//' | sort -u)
colados=''
for r in $reales; do
  printf '%s\n' "$existen" | grep -qx "$r" || continue
  # Una ruta real puede aparecer en un COMENTARIO -explicando por que se quito-, y eso no
  # contamina: el detector las clasifica como MENCION. Solo cuentan las lineas de codigo.
  if grep -nE "(^|[^#])/api/" "$YO" | grep -v '^[0-9]*:[[:space:]]*#' | grep -q -- "$r"; then
    colados="$colados $r"
  fi
done
if [ -z "$colados" ]; then
  pasan=$((pasan+1))
  printf '  [ok   ] %-46s de %s rutas nombradas, 0 reales en codigo\n' \
    "AC1 ningun fixture nombra una ruta real" "$(printf '%s\n' "$reales" | grep -c .)"
else
  fallos=$((fallos+1))
  printf '  [FALLA] %-46s rutas REALES en codigo de fixture:%s\n' \
    "AC1 autocontaminacion" "$colados"
fi

echo
# ======================================================================================
# HUELLA · que el brazo 1 y el brazo 2 son DE VERDAD independientes.
# P7 aisla el brazo 2 (fichas correctas, JSON vaciado). Este aisla el brazo 1: se induce
# una deriva que el brazo 2 NO puede ver, porque el conjunto de rutas sigue siendo
# exactamente el mismo. Si el check pasara, el brazo 1 no estaria haciendo nada.
# ======================================================================================
echo "HUELLA · los dos brazos cazan cosas distintas"
# EL NUMERO DE LINEA NO SE FIJA: se toma el que haya. La version anterior clavaba
# `"linea": 2008` -la de una ruta concreta en su dia- y dejo de casar en cuanto un cambio
# api.py desplazo el fichero: el caso pasaba a rc=0 y contaba como "el check no enrojece",
# que es lo contrario de lo que prueba. Es la misma fragilidad que I6, y por eso aqui se
# muta la PRIMERA linea que haya, sea cual sea.
h1() {
  python3 - "$T/ARQUITECTURA/derivada.json" <<'PYH1'
import json, re, sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
m = re.search(r'"linea": (\d+)', t)
if not m:
    raise SystemExit("sin ninguna clave 'linea': el fixture no puede inducir nada")
open(p, "w", encoding="utf-8").write(t.replace(m.group(0), '"linea": 99999', 1))
PYH1
}
caso "H1 deriva invisible al brazo 2" 1 "no coincide con la regeneracion" h1

echo
echo "MARCA DE AGUA · LA NORMALIZACION · el unico sitio donde esto se hunde"
# Se prueba la funcion `hechos_de` DIRECTAMENTE, no a traves de K88: la pregunta es si la
# marca distingue un HECHO de un ruido, y eso se contesta sobre la funcion.
# El elegible sale de GIT, no de una lista: los ficheros que el paquete «rojos viejos»
# (9ad124a -> 89ab61a) toco en ARQUITECTURA/rutas/.
norm=$(python3 - "$ORIG" <<'PYN' 2>&1
import copy, json, subprocess, sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
REPO = Path(sys.argv[1])
arq = SourceFileLoader("arq", str(REPO / "harness/bin/arquitectura")).load_module()
def show(c, p):
    o = subprocess.run(["git", "-C", str(REPO), "show", f"{c}:{p}"], capture_output=True, text=True)
    return o.stdout if o.returncode == 0 else None
ANTES, DESPUES = "9ad124a", "89ab61a"
ta, tb = show(ANTES, "ARQUITECTURA/derivada.json"), show(DESPUES, "ARQUITECTURA/derivada.json")
if not ta or not tb:
    print("NOMED no se pueden leer los dos commits"); raise SystemExit
da, db = json.loads(ta)["rutas"], json.loads(tb)["rutas"]
a = {r["camino"]: arq.marca_de(r) for r in da}
b = {r["camino"]: arq.marca_de(r) for r in db}
por_f = {f"ARQUITECTURA/rutas/{r['declarada']['fichero'].split('/')[-1]}": r["camino"] for r in db}
tocadas = subprocess.run(["git", "-C", str(REPO), "diff", "--name-only", f"{ANTES}..{DESPUES}",
                          "--", "ARQUITECTURA/rutas/"], capture_output=True, text=True).stdout.split()
res = [f for f in tocadas if por_f.get(f)]
mov = [f for f in res if a[por_f[f]] != b[por_f[f]]]
print(f"M1 {len(res)} {len(mov)}")
# el contrario: cambios de HECHO tienen que mover; ruido, no.
# LA RUTA DE PRUEBA SE ELIGE POR POSICION, NO POR NOMBRE: escribir un camino real
# aqui hace que el mapa acredite a este control como consumidor suyo, y el barrido
# AC1 de mas arriba lo caza. Es la septima vez en estas campanas.
r0 = next(r for r in db if r["tablas_lee"] and r["campos"] and r["consumo"]["n_llamadas"])
def prueba(mut):
    r = copy.deepcopy(r0); mut(r)
    return arq.marca_de(r) != arq.marca_de(r0)
print("M2", int(prueba(lambda x: x["tablas_lee"].append("zzz_tabla"))))
print("M3", int(prueba(lambda x: x["campos"].update({"zzz_campo": "literal en app/api.py:1"}))))
print("M4", int(prueba(lambda x: x["claves_temporales"].append("as_of"))))
print("M5", int(prueba(lambda x: x["consumo"].update({"n_llamadas": 0}))))
print("M6", int(prueba(lambda x: x["consumo"].update({"n_menciones": x["consumo"]["n_menciones"] + 3}))))
print("M7", int(prueba(lambda x: x["campos"].update({k: "literal en app/api.py:9999" for k in x["campos"]}))))
PYN
)
case "$norm" in
  NOMED*) fallos=$((fallos + 1)); printf '  [FALLA] %-52s %s\n' "la normalizacion no se pudo medir" "$norm" ;;
  *)
    leerm() { printf '%s\n' "$norm" | awk -v k="$1" '$1==k{print $2" "$3}'; }
    set -- $(leerm M1); n_res=${1:-0}; n_mov=${2:-9}
    # M1 · EL CONTROL QUE DECIDE, y es el que el encargo exige por su nombre. «rojos viejos»
    # cambio 10 fichas de rutas/ y no cambio ningun hecho: la marca tiene que quedarse quieta
    # en las diez. Con `consumo` entero dentro se movian SEIS -todas por n_menciones bajando
    # 1 al reescribir una cabecera-, y por eso `consumo` entra como PREDICADOS.
    if [ "$n_res" -ge 10 ] && [ "$n_mov" -eq 0 ]; then
      pasan=$((pasan + 1)); printf '  [ok   ] %-52s %s de %s quietas\n' "M1 rojos viejos no mueve NINGUNA marca" "$n_res" "$n_res"
    else
      fallos=$((fallos + 1)); printf '  [FALLA] %-52s %s movidas de %s\n' "M1 rojos viejos no mueve NINGUNA marca" "$n_mov" "$n_res"
    fi
    # M2..M5 · EL CONTRARIO, sin el cual M1 no vale nada: un control que solo sabe decir «no
    # se movio» no controla nada. Es la leccion del derivada.json que compare consigo mismo.
    for par in "M2:una tabla mas en tablas_lee:1" "M3:un campo nuevo publicado:1" \
               "M4:una clave temporal nueva:1" "M5:pasa a no tener llamadas:1" \
               "M6:SOLO cambia el NUMERO de menciones:0" "M7:SOLO se mueven lineas en campos:0"; do
      k=${par%%:*}; resto=${par#*:}; etq=${resto%:*}; esp=${resto##*:}
      got=$(printf '%s\n' "$norm" | awk -v k="$k" '$1==k{print $2}')
      if [ "${got:-x}" = "$esp" ]; then
        pasan=$((pasan + 1)); printf '  [ok   ] %-52s %s\n' "$k $etq" "$([ "$esp" = 1 ] && echo 'mueve la marca' || echo 'NO la mueve')"
      else
        fallos=$((fallos + 1)); printf '  [FALLA] %-52s esperaba %s, dio %s\n' "$k $etq" "$esp" "${got:-nada}"
      fi
    done ;;
esac

echo
echo "MARCA DE AGUA · EL BRAZO 6"
# W1 · una ficha cuyos hechos cambiaron sale SIN REVISAR y NO enrojece. Se induce moviendo el
# sello de una ruta cualquiera: el elegible sale del propio TSV, no de un nombre tecleado.
w1() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1; _sella "$T"
       python3 - "$T" <<'PYW'
import sys
from pathlib import Path
p = Path(sys.argv[1]) / "ARQUITECTURA/declarada/revisado.tsv"
ls = p.read_text(encoding="utf-8").splitlines()
for i, l in enumerate(ls):
    if l.startswith("/"):
        c = l.split("\t"); c[1] = "0000000000000000"; ls[i] = "\t".join(c); break
p.write_text("\n".join(ls) + "\n", encoding="utf-8")
PYW
}
caso "W1 un sello viejo: SIN REVISAR, y NO enrojece" 0 "1 de [0-9]+ ficha\(s\) SIN REVISAR" w1

# W2 · ANTI-FANTASMA DEL BRAZO: con todos los sellos al dia tiene que decir CERO. Sin este
# caso, W1 pasaria igual si el brazo dijera "sin revisar" siempre.
w2() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1; _sella "$T"; }
caso "W2 todos los sellos al dia: 0 SIN REVISAR" 0 "0 de [0-9]+ ficha\(s\) SIN REVISAR" w2

# W3 · REVISADO.TSV NO PUEDE ENVEJECER EN SILENCIO. Si a una ruta le falta su fila, el brazo
# no la vigila y tiene que DECIRLO. Es la frase de F6 §3 convertida en caso.
w3() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1; _sella "$T"
       python3 - "$T" <<'PYW'
import sys
from pathlib import Path
p = Path(sys.argv[1]) / "ARQUITECTURA/declarada/revisado.tsv"
ls = [l for l in p.read_text(encoding="utf-8").splitlines()]
fuera = next(i for i, l in enumerate(ls) if l.startswith("/"))
del ls[fuera]
p.write_text("\n".join(ls) + "\n", encoding="utf-8")
PYW
}
caso "W3 una ruta sin fila en revisado.tsv: se dice" 0 "sin fila en revisado.tsv" w3

# W4 · y la otra direccion: un sello de una ruta que ya no existe. Sin este brazo el fichero
# se vuelve un cementerio que "revisa" fichas que nadie escribe. Es la HUERFANA de K88/K31.
w4() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1; _sella "$T"
       printf '/api/zzz-que-no-existe\t0000000000000000\tdeadbeef\t2026-01-01\n' \
         >> "$T/ARQUITECTURA/declarada/revisado.tsv"; }
caso "W4 sello HUERFANO -su ruta ya no existe-" 0 "HUERFANO" w4

# W5 · CERO SELLOS NO ES CERO SIN REVISAR. Si el fichero se vacia o cambia de formato,
# "0 sin revisar" seria indistinguible de "no he leido nada". NOMED, jamas VERDE.
w5() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       printf '# solo comentarios\n' > "$T/ARQUITECTURA/declarada/revisado.tsv"; }
caso "W5 revisado.tsv sin filas: NOMED" 2 "ninguna fila de ruta" w5

w6() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       rm -f "$T/ARQUITECTURA/declarada/revisado.tsv"; }
caso "W6 sin revisado.tsv: NOMED" 2 "falta .*revisado.tsv" w6

w7() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       rm -f "$T/ARQUITECTURA/revision.json"; }
# W7 · si falta revision.json lo caza el BRAZO 1, no el 6: es un fichero que el
# generador emite, asi que su ausencia es una deriva contra la regeneracion fresca.
# La guarda del brazo 6 sigue estando por si alguien lo borra despues de comparar.
caso "W7 sin revision.json: lo caza el brazo 1 antes" 1 "FALTA en lo commiteado: revision.json" w7

echo
echo "BRAZO 5 · una frase ENTRECOMILLADA no es una afirmacion"
# EL FIXTURE ES EL MISMO PARA LOS DOS Y SOLO CAMBIAN LAS COMILLAS. Eso es lo que hace que el
# par signifique algo: si Q1 pasara por otra razon -por ejemplo porque la frase resulta ser
# CIERTA-, Q2 fallaria y se veria. Y paso: la primera version elegia una ruta cualquiera del
# fixture, y como el arbol de mentira no copia static/ ni tests/, TODAS tienen sin_ninguno
# verdadero y «sin ningun rastro» era cierto siempre. Q1 pasaba sin ejercitar nada.
# Aqui se le FABRICA un consumidor a la ruta elegida, para que la frase sea FALSA.
_con_consumidor() {  # deja la ruta elegida con un consumidor real y devuelve su ficha
  python3 - "$T" <<'PYC'
import json, sys
from pathlib import Path
t = Path(sys.argv[1])
d = json.load(open(t / "ARQUITECTURA/derivada.json"))
r = sorted(d["rutas"], key=lambda x: x["camino"])[10]
(t / "static").mkdir(parents=True, exist_ok=True)
(t / "static/app.js").write_text("async function x(){ await fetch('%s'); }\n" % r["camino"],
                                 encoding="utf-8")
print(r["declarada"]["fichero"])
PYC
}
q1() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       f=$(_con_consumidor); _esqueleto "$f"
       python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       printf '\nEl andamio escribio "sin ningun rastro" cuando el detector fallaba.\n' \
         >> "$T/ARQUITECTURA/$f"; _sella "$T"; }
caso "Q1 la formula entre comillas: no afirma, no enrojece" 0 "coincide con la regeneracion" q1

q2() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       f=$(_con_consumidor); _esqueleto "$f"
       python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
       printf '\nEsta ruta esta SIN NINGUN RASTRO en el repo.\n' >> "$T/ARQUITECTURA/$f"; _sella "$T"; }
caso "Q2 la misma frase SIN comillas y en versales: ROJO" 1 "sin ningun rastro" q2

echo "EL DETECTOR · un decorador citado no es una llamada"
# D1 · un test que PARSEA api.py buscando `@app.get("/api/x")` no es consumidor de esa ruta:
# es su SUJETO. Medido en el arbol real: afectaba a TRES rutas, no a una.
d1det() { python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
          r=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
print(next(x["camino"] for x in d["rutas"] if not x["consumo"]["n_llamadas"]))' "$T/ARQUITECTURA/derivada.json")
          mkdir -p "$T/tests"
          printf 'def test_x():\n    body = src.index(\x27@app.get("%s")\x27)\n' "$r" > "$T/tests/test_zzz_parser.py"
          python3 "$T/harness/bin/arquitectura" --repo "$T" >/dev/null 2>&1
          python3 - "$T" "$r" <<'PYD'
import json, sys
d = json.load(open(sys.argv[1] + "/ARQUITECTURA/derivada.json"))
r = next(x for x in d["rutas"] if x["camino"] == sys.argv[2])
print("LLAMADAS", r["consumo"]["n_llamadas"], "MENCIONES", r["consumo"]["n_menciones"], file=sys.stderr)
raise SystemExit(0 if r["consumo"]["n_llamadas"] == 0 else 1)
PYD
}
if d1det 2>/dev/null; then
  pasan=$((pasan + 1)); printf '  [ok   ] %-52s\n' "D1 @app.get citado en un test: MENCION, no llamada"
else
  fallos=$((fallos + 1)); printf '  [FALLA] %-52s el decorador citado sigue contando como llamada\n' "D1 @app.get citado en un test"
fi

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
