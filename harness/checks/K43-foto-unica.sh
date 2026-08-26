#!/bin/bash
# K43  el panel pinta de UNA foto, y la foto dice cuando se tomo.
#
# Hoy la pantalla es un collage: app.js menciona 37 rutas en 49 sitios y hace 8
# Promise.all; cada endpoint resuelve su propio now() y solo uno de esos instantes
# llega a pintarse. Medido el 2026-08-26: las 37 rutas del panel son 403749 B y 14.10 s
# sumadas; /api/ai/context trae lo mismo -y 12 de las 20 rutas huerfanas de K31- en
# 71586 B y 3.15 s, en UNA peticion.
#
# EL CRITERIO QUE PARECE OBVIO SE CUMPLE SIENDO FALSO. "un solo generated_at" es
# facil de servir y no prueba nada: medido, dentro del snapshot hay 27 instantes y 16
# son de construccion, con el generated_at de la raiz tomado A MITAD del armado -13
# secciones calculadas antes de su propia etiqueta y dos despues, liquidation_map a
# +2.650 s-. Una etiqueta unica sobre datos de vendimias distintas miente MAS que 43
# etiquetas porque parece autoritativa. Por eso aqui se exige una VENTANA de
# construccion declarada y que todas las secciones caigan dentro.
#
# TRES FAMILIAS DE INSTANTE Y NO SE PUEDEN MEZCLAR:
#   construccion  as_of, generated_at, snapshot_ts, captured_at: cuando NOSOTROS
#                 calculamos esa seccion. Tiene que caer dentro de la ventana.
#   referencia    *_reference_ts y *_latest_ts de K38, y window_start/window_end de
#                 K42: apuntan al pasado A PROPOSITO. La barra de 24 h TIENE que ser
#                 vieja. EXENTOS: aplicarles el criterio seria deshacer K38.
#   fuente        fetched_at: cuando el DATO se trajo de su origen, que no es cuando
#                 nosotros armamos la foto. Medido: external_macro_context viene con
#                 fetched_at 52 min atras porque esa es la cadencia real de esa
#                 fuente, no un fallo. EXENTO, y ademas es la forma correcta de
#                 declarar la edad: existiendo. Meterlo en construccion haria el
#                 criterio imposible por el motivo equivocado.
#
# Las dos mitades tienen que pasar. Ninguna vale sin la otra: una foto perfecta que
# el panel no usa no arregla la pantalla, y un panel que solo pide la foto no sirve
# si la foto miente sobre cuando se tomo.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PANEL="$REPO/static/app.js"
SIM=${K43_SIMBOLO:-BTCUSDT_PERP.A}
# Excepciones declaradas CON motivo. No es una lista de conveniencia.
#   /api/stream   SSE: empuje continuo, no es una foto y no puede serlo
#   /api/healthz  salud del sistema, no una cifra de mercado
EXCEPCIONES="/api/stream /api/healthz"

[ -r "$PANEL" ] || { echo "NO MEDIDO: no se puede leer static/app.js"; exit 2; }

fallos=""

# ---- mitad (a): la foto declara su ventana de construccion ----
cuerpo=$(curl -sS -k --netrc-file "$NETRC" --max-time 40 \
         "$API_PROD/api/ai/context?symbol=$SIM" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: /api/ai/context no respondio"; exit 2; }

foto=$(printf '%s' "$cuerpo" | python3 -c '
import sys, json, re
from datetime import datetime

CONSTRUCCION = re.compile(r"^(as_of|generated_at|snapshot_ts|captured_at)$")
REFERENCIA = re.compile(r"reference_ts$|_latest_ts$|^window_start$|^window_end$|session_end_at$")

try:
    d = json.load(sys.stdin)
except Exception:
    print("NOMED json ilegible"); raise SystemExit(0)

ini, fin = d.get("build_started_at"), d.get("build_finished_at")
if not ini or not fin:
    print("ROJO el sobre no declara su ventana de construccion: falta %s"
          % " ".join(k for k, v in (("build_started_at", ini), ("build_finished_at", fin)) if not v))
    raise SystemExit(0)
try:
    t0, t1 = datetime.fromisoformat(ini), datetime.fromisoformat(fin)
except ValueError:
    print("ROJO build_started_at/build_finished_at no son fechas ISO"); raise SystemExit(0)
if t1 < t0:
    print("ROJO la ventana declarada termina antes de empezar"); raise SystemExit(0)

fuera = []
def rec(o, ruta=""):
    if isinstance(o, dict):
        for k, v in o.items():
            r = (ruta + "." + k).lstrip(".")
            if isinstance(v, str) and len(v) > 15 and CONSTRUCCION.match(k) and not REFERENCIA.search(k):
                try:
                    t = datetime.fromisoformat(v)
                except ValueError:
                    continue
                if not (t0 <= t <= t1):
                    fuera.append((r, (t - t1).total_seconds()))
            rec(v, r)
    elif isinstance(o, list):
        for v in o[:5]:
            rec(v, ruta + "[]")
rec(d)

if fuera:
    fuera.sort(key=lambda x: -abs(x[1]))
    print("ROJO %d secciones se calcularon fuera de la ventana declarada y no declaran su edad: %s"
          % (len(fuera), " ".join("%s(%+.1fs)" % (r, s) for r, s in fuera[:4])))
    raise SystemExit(0)
print("OK ventana [%s, %s) de %.2f s" % (ini[11:19], fin[11:19], (t1 - t0).total_seconds()))
')
case "$foto" in
  NOMED*) echo "NO MEDIDO: ${foto#NOMED }"; exit 2 ;;
  ROJO*)  fallos="LA FOTO: ${foto#ROJO }" ;;
esac

# ---- mitad (b): el panel no pide nada mas que la foto ----
otras=""
for r in $(cd "$REPO" && grep -o "/api/[a-z0-9/-]*" static/app.js | sort -u); do
  case " $EXCEPCIONES " in *" $r "*) continue ;; esac
  [ "$r" = "/api/ai/context" ] && continue
  otras="$otras $r"
done
n=$(printf '%s' "$otras" | wc -w)
[ "$n" -eq 0 ] || {
  extra="EL PANEL: pide $n rutas ademas de la foto:$otras"
  fallos="${fallos:+$fallos | }$extra"
}

[ -z "$fallos" ] || { echo "$fallos" | cut -c1-300; exit 1; }
echo "el panel pide solo /api/ai/context (mas $EXCEPCIONES, declaradas) y la foto declara su ventana de construccion con todas sus secciones dentro"
