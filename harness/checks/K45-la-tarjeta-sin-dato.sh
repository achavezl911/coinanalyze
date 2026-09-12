#!/usr/bin/env bash
# K45 · LA TARJETA QUE SE QUEDA SIN DATO
#
# QUE VIGILA. Que cada ruta de la familia FOTO -la que declara K43- siga LLEGANDO AL
# OPERADOR. No que el panel la pida: que su dato acabe escrito en la pantalla.
#
# POR QUE NACE AHORA Y NO ANTES. Hasta la FASE 1, dejar de pintar una tarjeta exigia quitar
# una PETICION DE RED, y eso se ve en el log de nginx y lo caza K31. Desde la FASE 1,
# diecinueve tarjetas cuelgan de UNA lectura del sobre cada una: perderlas es cambiar una
# cadena dentro de un fichero de 4400 lineas. Medido por las dos partes el 2026-09-11
# -vaciando la clave dentro del sobre, y quitando las dos lecturas del panel- la firma es
# siempre la misma:
#     K31   diseno 7 -> 8   ·   «llegan al operador» 48 -> 47   ·   rc=0
# K31 LO VE Y NO LO CONDENA, porque esa ruta cae en DISENO y K31 solo enrojece por HUECO SIN
# DUENO: es su diseno declarado, no un fallo. K43 tampoco lo ve -pregunta que rutas PUEDE
# pedir el panel, y el sobre las trae todas-. K44 tampoco -mira que se pida el sobre-.
# O sea que la regresion era visible en una CIFRA y en NINGUN VEREDICTO. Eso es lo que
# arregla este check.
#
# COMO MIDE. No lee el codigo: MUTA Y MIRA EL DOM, con la misma sonda de K31 -jsdom, payloads
# reales, reloj congelado-. Una ruta LLEGA si al mutar su payload -o su clave dentro del
# sobre- el texto de la pagina cambia. Es el unico metodo que no se cae cuando el panel
# cambia de forma de pedir, que es justo lo que acaba de pasar.
#
# LA EXCEPCION, Y ES LA PARTE DELICADA. El dia que una tarjeta se rompa, el camino barato
# sera declararla excepcion. Por eso aqui una excepcion NO ES UN NOMBRE EN UNA LISTA: es una
# AFIRMACION FALSABLE que este check vuelve a comprobar en cada corrida.
#   · se declara la ruta Y EL ELEMENTO del panel donde pintaria
#   · la excepcion vale SOLO SI ese elemento NO EXISTE en static/index.html
#   · si el elemento existe, la excepcion queda ANULADA y la ruta condena igual
# Consecuencia buscada: para excusar una tarjeta rota hay que RETIRAR SU HUECO DE LA PAGINA,
# que es un cambio visible del producto y no una linea en un TSV. Declarar la excepcion
# cuesta mas que arreglar la tarjeta.
# Y se comprueban LAS DOS DIRECCIONES: una excepcion cuya ruta SI llega es una HUERFANA y
# tambien condena, para que no queden excusas rancias de algo que ya se arreglo.
#
# CONTROL POSITIVO DENTRO DEL CHECK. Si NO llegara NINGUNA de las 22, la primera hipotesis no
# es «el panel esta muerto»: es «no he medido». Un instrumento que da el mismo valor en todas
# las direcciones no distingue nada. Ese caso sale NO MEDIDO, no veintidos condenas.
set -uo pipefail

REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
B=$(cd "$(dirname "$0")/.." && pwd)
PY="${VENV_PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY=/srv/coinanalyze/repo/.venv/bin/python
PANEL="$REPO/harness/panel"
CANONICO=/srv/coinanalyze/repo/harness/panel
[ -f "$PANEL/probe.js" ] || PANEL="$CANONICO"
MODULOS="$PANEL/node_modules"
[ -d "$MODULOS" ] || MODULOS="$CANONICO/node_modules"
K43="$REPO/harness/checks/K43-foto-unica.sh"
[ -f "$K43" ] || K43=/srv/coinanalyze/repo/harness/checks/K43-foto-unica.sh
EXC="${K45_EXC:-$REPO/harness/checks/K45-excepciones.tsv}"
[ -f "$EXC" ] || EXC=/srv/coinanalyze/repo/harness/checks/K45-excepciones.tsv
HTML="${K45_HTML:-$REPO/static/index.html}"

[ -x "$PY" ]                 || { echo "NO MEDIDO: falta el venv del repo"; exit 2; }
command -v node >/dev/null   || { echo "NO MEDIDO: no hay node en esta maquina"; exit 2; }
[ -d "$MODULOS" ]            || { echo "NO MEDIDO: falta jsdom; correr npm install en $PANEL"; exit 2; }
[ -f "$K43" ]                || { echo "NO MEDIDO: no se puede leer K43, que es quien declara la familia FOTO"; exit 2; }
[ -f "$HTML" ]               || { echo "NO MEDIDO: no se puede leer $HTML"; exit 2; }

# PUERTA PARA EJERCITAR EL CRITERIO SIN PAGAR LA SONDA. `K45_SONDA` sustituye la salida de la
# sonda por un JSON de fichero. Existe porque la sonda tarda ~156 s y sin esta puerta el
# criterio de las EXCEPCIONES -que es la parte por la que se fuerza el verde- no se podria
# probar en un control barato. Es el MISMO codigo que corre de verdad: lo unico que cambia es
# de donde viene el JSON. No afecta a la corrida normal, que no define la variable.
if [ -n "${K45_SONDA:-}" ]; then
  [ -f "$K45_SONDA" ] || { echo "NO MEDIDO: K45_SONDA apunta a un fichero que no existe"; exit 2; }
  salida=$(cat "$K45_SONDA")
else
  # LA CACHE VA A LA RUTA CANONICA Y NO A `$B/estado`. Con `$B` -que es el arnes del arbol
  # desde el que se llame- correr este check DESDE UNA COPIA DEL REPO deja ahi 2.1 MB de
  # payloads de PRODUCCION, y el siguiente `git add -A` se los lleva al repositorio. Me paso
  # haciendo justo eso el 2026-09-12 y lo deshice antes de empujar. Se reusa la cache de K31
  # porque es la MISMA sonda y los mismos payloads: dos copias serian dos verdades.
  CACHE="${K45_FIXTURES:-${K31_FIXTURES:-/srv/coinanalyze/harness/estado/k31-fixtures}}"
  err=$(mktemp)
  salida=$(cd "$PANEL" && REPO="$REPO" NODE_PATH="$MODULOS" K31_FIXTURES="$CACHE" timeout 1500 node probe.js 2>"$err")
  rc=$?
  if [ $rc -ne 0 ] || [ -z "$salida" ]; then
    echo "NO MEDIDO: la sonda no devolvio nada (rc=$rc): $(head -c 200 "$err" | tr '\n' ' ')"
    rm -f "$err"; exit 2
  fi
  rm -f "$err"
fi

# EL JSON VIAJA POR FICHERO Y NO POR TUBERIA: el heredoc de aqui abajo YA OCUPA stdin, asi
# que un `printf | python - <<EOF` le da al interprete el script y se come el JSON. Medido:
# el primer intento moria en json.load con un traceback y rc=1, que se lee como ROJO.
sonda=$(mktemp)
printf '%s' "$salida" > "$sonda"
SONDA="$sonda" K43="$K43" EXC="$EXC" HTML="$HTML" "$PY" - <<'PY'
import json, os, re, sys

s = json.load(open(os.environ["SONDA"], encoding="utf-8"))
if s.get("error"):
    print("NO MEDIDO: la sonda no pudo medir: %s" % s["error"][:160]); raise SystemExit(2)
if s.get("control_determinista") is not True:
    print("NO MEDIDO: el instrumento no es determinista; dos renders sin mutar difieren"); raise SystemExit(2)
if not s.get("payloads_con_datos"):
    print("NO MEDIDO: cero payloads con datos; sin payloads no hay medicion"); raise SystemExit(2)

# LA POBLACION SALE DE K43, que es quien declara la familia. No se teclea aqui.
texto = open(os.environ["K43"], encoding="utf-8", errors="replace").read()
m = re.search(r'^ASIGNACION="\n(.*?)^"$', texto, re.S | re.M)
if not m:
    print("NO MEDIDO: no se pudo leer la ASIGNACION de K43"); raise SystemExit(2)
foto = sorted(r for r, f in re.findall(r"(/api/[\w/\-]+)=([A-Z]+)", m.group(1)) if f == "FOTO")
if not foto:
    print("NO MEDIDO: la ASIGNACION de K43 no declara ninguna ruta FOTO"); raise SystemExit(2)

llegan = set(s.get("llegan_a_la_pantalla") or []) | set(s.get("llegan_por_el_sobre") or [])
sin_dato = [r for r in foto if r not in llegan]

# CONTROL POSITIVO: si no llega NINGUNA, no he medido (A35).
if len(sin_dato) == len(foto):
    print("NO MEDIDO: ninguna de las %d rutas FOTO movio la pantalla. Eso no es un panel "
          "muerto, es una sonda que no midio: un instrumento que da el mismo valor en todas "
          "las direcciones no distingue nada." % len(foto))
    raise SystemExit(2)

# LAS EXCEPCIONES · ruta <TAB> elemento <TAB> cita. Valen SOLO si el elemento NO esta.
exc, mal_formadas = {}, []
try:
    for n, linea in enumerate(open(os.environ["EXC"], encoding="utf-8"), 1):
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        campos = [c.strip() for c in linea.split("\t") if c.strip()]
        if len(campos) < 3 or not campos[0].startswith("/api/"):
            mal_formadas.append(str(n)); continue
        exc[campos[0]] = (campos[1], campos[2])
except FileNotFoundError:
    pass
if mal_formadas:
    print("NO MEDIDO: K45-excepciones.tsv tiene lineas mal formadas (%s): hacen falta "
          "ruta, elemento y cita" % ",".join(mal_formadas))
    raise SystemExit(2)

html = open(os.environ["HTML"], encoding="utf-8", errors="replace").read()
def hueco_en_la_pagina(elem):
    return re.search(r'id\s*=\s*["\']' + re.escape(elem) + r'["\']', html) is not None

perdonadas, anuladas, huerfanas = [], [], []
for r in list(sin_dato):
    if r not in exc:
        continue
    elem, cita = exc[r]
    if hueco_en_la_pagina(elem):
        anuladas.append("%s(su hueco #%s SIGUE en la pagina)" % (r, elem))
    else:
        perdonadas.append("%s(sin hueco #%s · %s)" % (r, elem, cita))
        sin_dato.remove(r)
# LA OTRA DIRECCION: una excepcion de una ruta que SI llega ya no excusa nada.
for r in exc:
    if r in llegan:
        huerfanas.append(r)

cola = ""
if perdonadas:
    cola += " · %d con excepcion VIVA -su hueco no esta en la pagina, y se comprueba cada " \
            "corrida-: %s" % (len(perdonadas), " ".join(perdonadas))
if anuladas:
    cola += " · %d excepcion(es) ANULADA(S): %s" % (len(anuladas), " ".join(anuladas))

if sin_dato or huerfanas or anuladas:
    partes = []
    if sin_dato:
        partes.append("%d tarjeta(s) FOTO se quedaron SIN DATO: %s" % (len(sin_dato), " ".join(sin_dato)))
    if huerfanas:
        partes.append("%d excepcion(es) HUERFANA(S) -su ruta SI llega, la excusa sobra-: %s"
                      % (len(huerfanas), " ".join(huerfanas)))
    print("ROJO: " + " · ".join(partes) +
          " · de %d rutas FOTO, %d llegan (mutando y mirando el DOM, %d secciones recorridas)"
          % (len(foto), len(foto) - len(sin_dato) - len(perdonadas), s.get("secciones", 0)) + cola)
    raise SystemExit(1)

print("las %d rutas FOTO llegan al operador: su dato acaba ESCRITO en la pantalla, medido "
      "mutando el payload -o su clave dentro del sobre- y comparando el DOM, sobre %d "
      "secciones recorridas y %d payloads con datos%s"
      % (len(foto), s.get("secciones", 0), s.get("payloads_con_datos", 0), cola))
PY
rc=$?
rm -f "$sonda"
exit $rc
