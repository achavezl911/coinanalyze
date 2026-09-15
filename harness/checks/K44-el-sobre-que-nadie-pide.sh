#!/usr/bin/env bash
# K44 · EL PANEL TIENE QUE PEDIR EL SOBRE, Y ESO NO LO EXIGE NADIE
#
# SUJETO   lo que un navegador de verdad PIDE a 140, leido del log de nginx.
# VERDE    en la ventana reciente hay al menos una peticion a /api/ai/context y CERO a rutas
#          de la familia FOTO de K43.
# ROJO     hubo visitas y el panel no pide el sobre; o lo pide y ADEMAS sigue pidiendo las
#          partes, que es la reforma a medias.
# NOMED    el canal no contesto; o no consta que nadie mirara; o no se pudo leer la lista FOTO.
#
# POR QUE EXISTE. `/api/ai/context` es EL SOBRE: una sola respuesta atomica con su
# `generated_at`, de la que todo lo que es FOTO deberia salir con UNA edad en vez de con
# veintidos. Es el requisito central del diseno y es lo que K43 vigila con sus cuatro familias.
# La propia prosa de K43 dice que «que llegue a pedirlo es lo que mide K44, no esta unidad»
# — y K44 no existia: nadie lo habia escrito (COLA.md 105). Sin el, las cuatro familias pueden
# quedar las cuatro VERDES con la pantalla haciendo exactamente las mismas peticiones sueltas.
#
# EL INSTRUMENTO ES EXTERNO AL SUJETO, y tiene que serlo. Leer `static/app.js` mide su FORMA y
# cambia con su parche; ademas ahi caen los comentarios -medido al cerrar K45: el criterio «no
# menciona ninguna ruta de FOTO» se cumplia BORRANDO UN COMENTARIO-. Lo que no comparte forma
# con el panel es lo que un navegador pide de verdad.
#
# EL FILTRO ES «AGENTE DE NAVEGADOR Y NO LA IP DEL ARNES», el mismo que usa K43, y no una IP:
# medido al cerrar K46, hay CUATRO navegadores en el historico -.101, .73, .99 desde un iPhone
# y .100 desde un Mac- y un solo cliente curl, el arnes desde .2. Filtrar por una IP dejaria al
# panel pidiendo rutas de FOTO desde el movil con el criterio en VERDE.
#
# ---------------------------------------------------------------------------------
# LA VENTANA ES RECIENTE, Y AQUI ES AL REVES QUE EN K43. Para el DENOMINADOR de K43 el
# historico entero es lo correcto: una pestana cerrada no es una ruta muerta. Para K44 el
# historico seria MORTAL, porque las peticiones viejas no se borran y bastaria con que el panel
# hubiera pedido una ruta de FOTO una vez en agosto para que el criterio no llegue a cero nunca.
# Mismo log, misma pregunta aparente, ventanas opuestas.
#
# POR QUE SEIS HORAS, y sale de una medida y no de un gusto. Medido el 2026-09-11 sobre las
# ~25 h de log retenido (33 255 peticiones de navegador): **el silencio mas largo que el panel
# se toma de verdad son 6 505 s = 108.4 min**. Una ventana menor que eso apaga el check en
# cualquier pausa normal; seis horas son 3.3 veces ese silencio. Y con una ventana de 1 h,
# medido ese mismo dia a las 07:05Z, el trafico era CERO y el check no habria podido hablar:
# la ultima visita habia sido a las 00:05 locales y eran las 01:05.
#
#     ventana   1 h -> 0 peticiones · 2 h -> 44 · 3 h -> 44 · 6 h -> 3 272 · 24 h -> 31 340
#
# LO QUE SE MIRA ESTA PODADO y por eso la ventana se declara en la salida: `logrotate` guarda
# `rotate 14` diarios, asi que el log no puede probar una ausencia mas alla de eso. Con seis
# horas eso no aprieta -entran en los dos ficheros vivos-, pero la frase no puede decir mas de
# lo que la ventana alcanza.
#
# ---------------------------------------------------------------------------------
# LOS SEIS ESTADOS, y cada uno tiene su linea. El encargo nombraba cuatro; son seis, y los dos
# que faltaban son un ROJO y un NOMED:
#
#   1 EL CANAL NO CONTESTO ................. NOMED. No es un hecho sobre nada.
#   2 NO CONSTA QUE NADIE MIRARA ........... NOMED. No es un hecho sobre el panel: en una
#     ventana sin visitas, «cero peticiones al sobre» sale igual que si el panel lo pidiera
#     en cada carga. Sin esta rama K44 se pondria rojo un domingo por la tarde y alguien lo
#     «arreglaria» sin que hubiera nada que arreglar.
#   3 NO SE PUDO LEER LA LISTA FOTO ........ NOMED. El conjunto no es de este check: sale de la
#     ASIGNACION de K43. Sin el no hay criterio, y un criterio sobre cero rutas se cumple solo.
#   3b UNA EXCUSA QUE NO SE PUDO VERIFICAR . NOMED, y NO VERDE. Si falta lo que la sostiene -el
#     `profile` del sobre, `PROFILE_LIMITS`, el `limit` del log-, esa ruta no se excusa y
#     TAMPOCO se condena: queda en un tercer cubo. Decirlo en la linea y ademas dar VERDE seria
#     contar como medida lo que no se midio. Si en la misma corrida hay una ruta suelta SIN
#     excusa, manda esa condena y las no verificables van nombradas.
#   4 PIDE EL SOBRE Y CERO PARTES .......... VERDE. «Cero partes» = cero SIN EXCUSA VIVA; las
#     excusadas se nombran con la razon contra la que se comprobaron en esta misma corrida.
#   5 NO PIDE EL SOBRE ..................... ROJO. Es el estado de hoy.
#   6 PIDE EL SOBRE Y SIGUE PIDIENDO PARTES  ROJO, y es OTRO rojo: en el 5 no ha empezado
#     nadie; en el 6 alguien empezo y dejo las dos cosas puestas —que cuesta MAS que hoy—.
#     Las dos condiciones van juntas a proposito: pedir la foto sin dejar de pedir las partes
#     cumpliria un criterio de una sola mitad siendo falso.
#
# ---------------------------------------------------------------------------------
# LA EXCEPCION NO ES UN NOMBRE EN UNA LISTA: ES UNA AFIRMACION QUE ESTE CHECK VUELVE A
# COMPROBAR EN CADA CORRIDA. Es el patron que el operador impuso a K45 (COLA 118) traido aqui.
#
# EL PROBLEMA QUE RESUELVE. La FASE 1 dejo TRES rutas de FOTO que el panel sigue pidiendo
# sueltas -y bien-: el sobre NO trae lo que el panel lee de ellas. Medido en COLA 117/118 y otra
# vez en COLA 123 decision 1. Meterlas en el sobre no es gratis: el sobre NO esta cacheado y se
# reconstruye entero en 5-6 s por refresco, asi que doce ventanas y cincuenta niveles lo
# encarecen PARA TODAS las tarjetas. Los restos son un diseno medido; lo que fallaba es que K44
# no lo sabia y condenaba el comportamiento correcto.
#
# CADA EXCEPCION DICE CONTRA QUE SE COMPROBO, y muere sola por dos caminos distintos:
#
#   la afirmacion deja de ser cierta  ->  excepcion ANULADA, la ruta CONDENA igual
#   el panel ya no pide esa ruta      ->  excepcion HUERFANA, sobra, y se DICE (no condena)
#
# Nadie tiene que acordarse de nada: el dia que el sobre traiga lo suyo, la excusa se cae y el
# rojo vuelve. Eso es lo que la hace mejor que cambiar el criterio.
#
# LA TABLA · ruta | tipo | argumento | clave del sobre
#   FALTAN  la RUTA sirve esas claves y el SOBRE no las tiene en ningun nivel.
#   MENOS   el valor del SOBRE tiene estrictamente MENOS elementos que el de la ruta.
# Las claves del sobre salen de las PAREJAS de K43, que es la traduccion declarada.
#   TOPE    el SOBRE sirve esa clave con un TOPE DE PERFIL menor que el `limit` con que el
#           panel pide la ruta. El tope NO se copia: se lee en cada corrida del codigo que lo
#           aplica, y el perfil lo dice el propio sobre.
EXCEPCIONES="
/api/dashboard/state          | FALTAN | scalp_persistence,signal_base_rate          |
/api/scalp/delta-matrix       | MENOS  |                                             | delta_matrix
/api/scalp/liquidation-levels | TOPE   | liq_levels                                  | liquidation_levels
"
# LO QUE CADA UNA AFIRMA, medido el 2026-09-14 23:0xZ con bin/api contra 140:
#   dashboard/state      scalp_persistence y signal_base_rate: en la ruta SI, en el sobre NO.
#                        CONTROL del buscador, en la misma corrida: symbol, snapshot, scalp y
#                        setup SI aparecen en el sobre. Sin ese control, un buscador roto
#                        excusaria cualquier ruta diciendo que no encuentra nada.
#   delta-matrix         la ruta sirve 12 ventanas y el sobre 5 (PROFILE_LIMITS, ai_context.py).
#   liquidation-levels   el sobre topa `liquidation_levels` en el `liq_levels` de su perfil, y
#                        ese tope es MENOR que el `limit` con que el panel pide la ruta. Lo que
#                        el panel LEE son las filas: `renderLiquidationLevels` las mapea TODAS y
#                        publica su cuenta; de los metadatos solo usa `minutes`, con reserva 60.
#
#                        POR QUE EL TOPE Y NO «EL SOBRE TRAE MENOS FILAS». Contar filas hace que
#                        EL VEREDICTO DEPENDA DE LA HORA: en una hora agitada la ruta trae mas
#                        que el tope y la excusa vive; en una tranquila los dos traen lo mismo
#                        -medido 2026-09-15 03:33Z: ruta 4, sobre 4- y la excusa moria, con K44
#                        condenando el comportamiento correcto. El panel NO SABE de antemano si
#                        la hora sera tranquila: la peticion suelta esta justificada por diseno
#                        aunque una hora concreta no lo ensene. Un ROJO que ademas avisa de que
#                        «hay que mirar un dia con mas niveles» es un rojo sobre el que nadie
#                        puede actuar, y ensena a leer el rojo de K44 como ruido.
#
#                        EL TOPE NO SE COPIA: se lee en CADA CORRIDA de `PROFILE_LIMITS`, en el
#                        codigo que lo aplica, y el perfil lo dice el propio sobre (`profile`).
#                        Se lee del RELEASE DESPLEGADO en 140 -que es quien lo aplica- y si el
#                        canal no contesta, del arbol local, DICIENDO de cual salio. Una ventana
#                        copiada a mano es lo que hizo que K18 acusara en falso durante semanas.
#
#                        LA EXCUSA CAE, sin que nadie toque nada, por dos caminos: si alguien
#                        sube `liq_levels` hasta el `limit` del panel -el sobre ya podria darle
#                        todo- o si el sobre empieza a servir MAS filas que su propio tope -ese
#                        tope ya no lo describe-.
#
#                        UNA CIFRA QUE PUBLIQUE Y ERA FALSA: dije que «con el `limit` por
#                        defecto la ruta da 5 filas y con el del panel 9». Los defectos de la
#                        ruta SON los del panel (app/api.py:3026-3031: minutes=60, bucket_bps=10,
#                        limit=50). Pedidas espalda con espalda, alternadas, dos rondas
#                        -2026-09-15 03:33:30Z-: 4 y 4 filas con el MISMO as_of. Aquel 5 y aquel
#                        9 los separaba el RELOJ, no el `limit`.
#
# CONTROL: harness/checks/K44-control.bash. No lleva .sh a proposito: bin/verify globea *.sh.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}

K43=${K44_K43:-$REPO/harness/checks/K43-foto-unica.sh}
VENTANA_H=${K44_VENTANA_H:-6}
ARNES_IP=${K44_ARNES_IP:-10.10.100.2}
SOBRE=/api/ai/context

# --- 1 · EL CONJUNTO FOTO, que no es de este check -----------------------------------------
FOTO=""
if [ -r "$K43" ]; then
  FOTO=$(sed -n '/^ASIGNACION="$/,/^"$/p' "$K43" | tr ' ' '\n' | grep '=FOTO$' | sed 's/=FOTO$//' | sort -u)
fi
N_FOTO=$(printf '%s\n' "$FOTO" | grep -c . || true)
if [ "$N_FOTO" -lt 1 ]; then
  echo "NO MEDIDO: no se pudo leer ninguna ruta de la familia FOTO en $K43." \
       "El conjunto que este check juzga sale de la ASIGNACION de K43, y sin el no hay" \
       "criterio: «cero rutas de FOTO pedidas» se cumpliria solo sobre cero rutas."
  exit 2
fi

# --- 2 · EL LOG, CRUDO Y CON SU rc (receta A8) ---------------------------------------------
# Las tuberias van DENTRO del mandato que ejecuta 140, asi que este rc es el de bin/prod y no
# el de un filtro que lo suplanta. `grep -a` es obligatorio -A4: sobre un flujo con bytes no
# texto, grep declara «binary file matches» y CALLA las lineas, y CERO es justo el valor que
# este check busca-. El patron va SIN espacio final: toda ruta viaja con ?symbol=.
#
# LA HORA LA PONE 140. El log de nginx va en hora LOCAL (-0600), no en UTC, asi que no se hace
# aritmetica de husos desde aqui: se le piden a 140 las etiquetas de hora que quiere aceptar.
# SOLO SE PIDEN LAS QUERIES DE LAS RUTAS CON EXCEPCION, no las de las 22: acota la salida del
# canal y deja claro para que se leen. El awk NO puede llevar `>` ni `<`: `bin/prod` los ve como
# una redireccion a fichero y DENIEGA el mandato entero (rc=3). Por eso se emiten todas las
# variantes con su cuenta y la mas frecuente se elige aqui, con `sort -rn`.
RUTAS_EX=$(printf '%s\n' "$EXCEPCIONES" | awk -F'|' 'NF>1 {gsub(/ /,"",$1); if ($1!="") printf "|%s", $1} END {printf "|"}')
LOG_CMD="
  horas=\$(for i in \$(seq 0 $((VENTANA_H-1))); do date -d \"-\$i hours\" +%d/%b/%Y:%H; done | tr '\n' '|' | sed 's/|\$//')
  cat /var/log/nginx/access.log.1 /var/log/nginx/access.log 2>/dev/null \
    | grep -a Mozilla | grep -av '^$ARNES_IP ' \
    | awk -v H=\"\$horas\" 'BEGIN{n=split(H,a,\"|\")} { for(i=1;i<=n;i++) if (index(\$4,a[i])==2) { print; break } }' \
    | awk -v EX='$RUTAS_EX' '{ visitas++; full=\$7; p=full; sub(/\?.*/, \"\", p);
             if (p ~ /^\/api\//) { c[p]++; if (index(EX, \"|\" p \"|\")) q[full]++ } }
           END { printf \"VISITAS %d\n\", visitas+0;
                 for (i in c) printf \"%d %s\n\", c[i], i;
                 for (i in q) printf \"QUERY %d %s\n\", q[i], i }'"

if [ "${K44_LOG+puesta}" = puesta ]; then
  LOG=$K44_LOG
  ORIGEN="inyectado"
else
  LOG=$("$B/bin/prod" "$LOG_CMD" 2>/dev/null)
  _rc=$?
  if [ "$_rc" -ne 0 ]; then
    echo "NO MEDIDO: el log de nginx no se pudo leer (bin/prod rc=$_rc)." \
         "Esta linea NO dice nada sobre lo que el panel pide, ni que pida el sobre ni que no."
    exit 2
  fi
  ORIGEN="canal"
fi
MARCA=""
[ "$ORIGEN" = inyectado ] && MARCA=" [log INYECTADO por K44_LOG, no leido del canal]"

# --- 3 · EL VEREDICTO -----------------------------------------------------------------------
VISITAS=$(printf '%s\n' "$LOG" | awk '$1=="VISITAS" {print $2; exit}')
[ -n "${VISITAS:-}" ] || VISITAS=0

if [ "$VISITAS" -lt 1 ]; then
  echo "NO MEDIDO: no consta que nadie mirara el panel en las ultimas ${VENTANA_H} h" \
       "-0 peticiones de navegador, filtrando por agente y descartando la IP del arnes-." \
       "En una ventana sin visitas, «cero peticiones al sobre» sale IGUAL que si el panel lo" \
       "pidiera en cada carga, y solo uno de los dos es un defecto.$MARCA"
  exit 2
fi

pedidas=$(printf '%s\n' "$LOG" | awk '$1!="VISITAS" && $1 ~ /^[0-9]+$/ {print}')
# LA QUERY CON LA QUE EL PANEL PIDE CADA RUTA, sacada del log y no copiada a mano. Sin ella la
# comparacion de filas se haria contra la peticion equivocada: `liquidation-levels` da 5 filas
# con el limit por defecto y 9 con el del panel.
QUERIES=$(printf '%s\n' "$LOG" | awk '$1=="QUERY" {print $2, $3}' | sort -rn)
n_sobre=$(printf '%s\n' "$pedidas" | awk -v S="$SOBRE" '$2==S {s+=$1} END {print s+0}')

pedidas_foto=""
while read -r r; do
  [ -n "$r" ] || continue
  n=$(printf '%s\n' "$pedidas" | awk -v R="$r" '$2==R {s+=$1} END {print s+0}')
  [ "$n" -gt 0 ] && pedidas_foto="$pedidas_foto$r $n
"
done <<EOF
$FOTO
EOF

COLA0="ventana ${VENTANA_H} h · $VISITAS peticiones de navegador · $N_FOTO rutas en la familia FOTO"

# --- 2a · EL ESTADO 5 NO PASA POR LAS EXCEPCIONES ------------------------------------------
# Si el panel NO pide el sobre, excusar una ruta por «el sobre no trae lo suyo» no significa
# nada: no hay sobre que consultar. Se cuentan TODAS las partes y se condena, que es el estado
# 5 de siempre. Ademas asi este brazo no depende del canal de payloads.
if [ "$n_sobre" -lt 1 ]; then
  n_partes=0; rutas_partes=0; partes=""
  while read -r r n; do
    [ -n "$r" ] || continue
    partes="$partes $r($n)"; n_partes=$((n_partes + n)); rutas_partes=$((rutas_partes + 1))
  done <<EOF
$pedidas_foto
EOF
  echo "el panel NO pide el sobre: 0 peticiones a $SOBRE, y $n_partes a $rutas_partes de las" \
       "$N_FOTO rutas de FOTO, que es reconstruir la foto en vez de consumirla ·$partes" \
       "· $COLA0$MARCA"
  exit 1
fi

# --- 2b · SIN PARTES NO HAY NADA QUE EXCUSAR -----------------------------------------------
# Cero rutas sueltas: el VERDE no necesita consultar ningun payload. Mantiene barato el caso
# bueno, que es el que va a correr casi siempre.
if [ -z "${pedidas_foto//[$' \t\n']/}" ]; then
  # LA OTRA DIRECCION, Y SALE GRATIS: si el panel no pide NINGUNA parte, entonces TODAS las
  # excepciones declaradas sobran. Se dicen por su nombre sin bajar un solo payload. Callarlas
  # dejaria que una excusa muerta viviera para siempre en la tabla sin que nadie la mire.
  todas=$(printf '%s\n' "$EXCEPCIONES" | awk -F'|' 'NF>1 {gsub(/ /,"",$1); if ($1!="") printf "%s ", $1}')
  SOBRAN=""
  [ -n "${todas// /}" ] && SOBRAN=" · EXCEPCIONES HUERFANAS (el panel ya no pide ninguna parte, las $(printf '%s' "$todas" | wc -w) sobran): $todas"
  echo "el panel pide el sobre $n_sobre veces y CERO de las $N_FOTO rutas de FOTO: lo que se" \
       "pinta como foto sale de una sola respuesta con un solo generated_at · $COLA0$MARCA$SOBRAN"
  exit 0
fi

# --- 2c · LAS EXCEPCIONES, REVERIFICADAS CONTRA LOS PAYLOADS DE ESTA MISMA CORRIDA ----------
# Se bajan el sobre y SOLO las rutas que tienen excepcion declarada: cuatro peticiones, no 22.
# Si el canal de payloads no contesta NO se excusa a nadie por defecto -eso seria la excepcion
# silenciosa que este mecanismo existe para impedir-: sale NO MEDIDO y se dice cual fallo.
API=${K44_API:-$B/bin/api}
SIMBOLO=${K44_SIMBOLO:-$(TODO=1 timeout 60 "$API" /api/symbols 2>/dev/null \
  | sed -n 's/.*"symbol":"\([^"]*\)".*/\1/p' | head -1)}
if [ -z "$SIMBOLO" ]; then
  echo "NO MEDIDO: no se pudo leer ningun simbolo de /api/symbols, asi que las excepciones de" \
       "este check no se pueden reverificar. Sin reverificarlas NO se excusa a nadie: una" \
       "excusa que no se comprueba es exactamente lo que este mecanismo existe para impedir."
  exit 2
fi

COMO_SE_PIDIO=""
TMPX=$(mktemp -d /tmp/k44.XXXXXX); trap 'rm -rf "$TMPX"' EXIT
if [ -n "${K44_PAYLOADS:-}" ]; then
  cp "$K44_PAYLOADS"/*.json "$TMPX"/ 2>/dev/null
  MARCA="$MARCA [payloads INYECTADOS por K44_PAYLOADS]"
else
  TODO=1 timeout 90 "$API" "/api/ai/context?symbol=$SIMBOLO" > "$TMPX/_sobre.json" 2>/dev/null
  while IFS='|' read -r r _t _a _c; do
    r=$(printf '%s' "$r" | tr -d ' '); [ -n "$r" ] || continue
    # SE PIDE COMO LA PIDE EL PANEL. Si el log trae su query, esa; si no, la minima, y se dice.
    # `QUERIES` viene ordenado por cuenta descendente: la primera que empiece por la ruta es la
    # variante que el panel mas usa en la ventana.
    q=$(printf '%s\n' "$QUERIES" | awk -v R="$r" 'index($2, R"?")==1 {print $2; exit}')
    if [ -n "$q" ]; then
      COMO_SE_PIDIO="$COMO_SE_PIDIO $r<-log"
    else
      q="$r?symbol=$SIMBOLO"; COMO_SE_PIDIO="$COMO_SE_PIDIO $r<-minima"
    fi
    TODO=1 timeout 90 "$API" "$q" > "$TMPX/$(printf '%s' "$r" | tr '/' '_').json" 2>/dev/null
  done <<EOF
$EXCEPCIONES
EOF
fi

# EL TOPE DEL SOBRE, LEIDO DE QUIEN LO APLICA. Primero del release desplegado en 140 -ahi es
# donde el sobre se construye-, y si el canal no contesta, del arbol local. La fuente se declara
# en la linea: un tope leido del arbol equivocado es una copia con otro nombre.
TOPES_DE=""
if [ -n "${K44_LIMITS:-}" ]; then
  cp "$K44_LIMITS" "$TMPX/_limits.py" 2>/dev/null && TOPES_DE="INYECTADO por K44_LIMITS"
else
  _src=$("$B/bin/prod" "sed -n '/^PROFILE_LIMITS/,/^}/p' /opt/coinalyze/current/app/ai_context.py" 2>/dev/null)
  if printf '%s' "$_src" | grep -q '^PROFILE_LIMITS'; then
    printf '%s\n' "$_src" > "$TMPX/_limits.py"; TOPES_DE="el release desplegado en 140"
  elif [ -r "$REPO/app/ai_context.py" ]; then
    cp "$REPO/app/ai_context.py" "$TMPX/_limits.py"; TOPES_DE="el arbol local $REPO (140 no contesto)"
  fi
fi
[ -s "$TMPX/_limits.py" ] || TOPES_DE=""

VEREDICTOS=$(EXCEPCIONES="$EXCEPCIONES" PEDIDAS_FOTO="$pedidas_foto" TMPX="$TMPX" \
             QUERIES="$QUERIES" TOPES_DE="$TOPES_DE" python3 - <<'PY'
import json, os, sys

def hojas_claves(o, prof=0, out=None):
    """todas las claves del arbol, a cualquier nivel"""
    if out is None: out = set()
    if prof > 8 or not isinstance(o, (dict, list)): return out
    if isinstance(o, list):
        for x in o[:6]: hojas_claves(x, prof + 1, out)
        return out
    for k, v in o.items():
        out.add(k); hojas_claves(v, prof + 1, out)
    return out

def carga(p):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return None

def lee_topes():
    """PROFILE_LIMITS del codigo que lo aplica, por AST. NO se importa `app/`: importarlo
    abriria el pool, y `app.db.create_pool` ESCRIBE en market_assets y crea particiones."""
    import ast
    p = os.path.join(os.environ["TMPX"], "_limits.py")
    try:
        arbol = ast.parse(open(p).read())
    except Exception:
        return None
    for n in arbol.body:
        tgt = None
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name): tgt = n.target.id
        elif isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name): tgt = n.targets[0].id
        if tgt == "PROFILE_LIMITS":
            try: return ast.literal_eval(n.value)
            except Exception: return None
    return None

def limite_panel(ruta):
    """el `limit` con que el panel pide la ruta, sacado del log de nginx y no copiado."""
    import re
    for ln in (os.environ.get("QUERIES") or "").splitlines():
        p = ln.split(None, 1)
        if len(p) != 2 or not p[1].startswith(ruta + "?"): continue
        m = re.search(r"[?&]limit=(\d+)", p[1])
        if m: return int(m.group(1))
    return None

tmp = os.environ["TMPX"]
sobre = carga(os.path.join(tmp, "_sobre.json"))
pedidas = {}
for ln in os.environ["PEDIDAS_FOTO"].strip().splitlines():
    if not ln.strip(): continue
    r, n = ln.rsplit(" ", 1); pedidas[r.strip()] = int(n)

# EL CONTROL DEL BUSCADOR, en la misma corrida. Si `hojas_claves` estuviera rota devolveria
# vacio y excusaria TODAS las rutas por «el sobre no lo trae». Cuatro claves que el sobre tiene
# seguro -son las PAREJAS de /api/dashboard/state que SI viajan- tienen que aparecer.
TESTIGOS = ["symbol", "snapshot", "scalp", "setup"]
if sobre is None:
    print("NOMED\tno se pudo leer el sobre, asi que ninguna excepcion se puede reverificar")
    sys.exit(0)
cs = hojas_claves(sobre)
faltan_testigos = [t for t in TESTIGOS if t not in cs]
if faltan_testigos:
    print("NOMED\tel buscador de claves no encuentra en el sobre "
          + " ".join(faltan_testigos) + ", que SI estan: esta roto y excusaria a cualquiera")
    sys.exit(0)

for ln in os.environ["EXCEPCIONES"].strip().splitlines():
    if not ln.strip(): continue
    p = [x.strip() for x in ln.split("|")]
    while len(p) < 4: p.append("")
    ruta, tipo, arg, clave = p[0], p[1], p[2], p[3]
    if not ruta: continue
    if ruta not in pedidas:
        print(f"HUERFANA\t{ruta}\tel panel ya no la pide en la ventana: la excepcion sobra")
        continue
    rp = carga(os.path.join(tmp, ruta.replace("/", "_") + ".json"))
    if rp is None:
        print(f"NOMED\tno se pudo leer {ruta}, asi que su excepcion no se puede reverificar")
        continue
    if tipo == "FALTAN":
        pedidas_k = [k for k in arg.split(",") if k]
        en_ruta = hojas_claves(rp)
        no_en_ruta = [k for k in pedidas_k if k not in en_ruta]
        # EL AMBITO IMPORTA, Y ME MORDIO AL ESCRIBIRLO. Buscar el nombre en TODO el sobre da
        # falsos positivos por homonimia: `window_start` y `window_end` existen en el sobre
        # -nueve sitios, todos bajo `oi_context.coverage.*`- y no tienen nada que ver con los
        # niveles de liquidacion. Con la busqueda global esta excepcion salia ANULADA por un
        # nombre que coincide. Si la fila declara clave del sobre, se busca DENTRO de ella.
        if clave:
            ambito = sobre.get(clave, "<<AUSENTE>>")
            if ambito == "<<AUSENTE>>" or ambito is None:
                print(f"ANULADA\t{ruta}\tel sobre ya no trae `{clave}`: la excusa mira dentro de nada")
                continue
            if isinstance(ambito, (list, dict)) and len(ambito) == 0:
                print(f"ANULADA\t{ruta}\t`{clave}` viene VACIA en el sobre: sobre un vacio "
                      f"cualquier clave falta sola y la excusa se cumpliria por construccion")
                continue
            donde = f"dentro de `{clave}` ({len(hojas_claves(ambito))} claves)"
            en_sobre = [k for k in pedidas_k if k in hojas_claves(ambito)]
        else:
            donde = f"en TODO el sobre ({len(cs)} claves, control {' '.join(TESTIGOS)} OK)"
            en_sobre = [k for k in pedidas_k if k in cs]
        if no_en_ruta:
            print(f"ANULADA\t{ruta}\tla RUTA ya no sirve {' '.join(no_en_ruta)}: "
                  f"la excusa hablaba de algo que ya no existe")
        elif en_sobre:
            print(f"ANULADA\t{ruta}\tel sobre YA trae {' '.join(en_sobre)} {donde}: la excusa es falsa")
        else:
            print(f"VIVA\t{ruta}\tla ruta sirve {' '.join(pedidas_k)} y NO estan {donde}")
    elif tipo == "TOPE":
        # EL TOPE ES LO QUE SEPARA «el sobre lo trae todo» de «el tope no ha mordido», y no
        # depende de cuantas liquidaciones hubo en la ultima hora.
        def filas(x):
            if isinstance(x, dict) and isinstance(x.get("rows"), list): return x["rows"]
            return x if isinstance(x, list) else None
        fs = filas(sobre.get(clave))
        perfil = sobre.get("profile")
        topes = lee_topes()
        lim = limite_panel(ruta)
        de = os.environ.get("TOPES_DE") or "fuente no declarada"
        tope = None
        if topes is not None and perfil and perfil in topes:
            t = topes[perfil].get(arg)
            if isinstance(t, int): tope = t

        # LO QUE SE PUEDE DECIDIR CON LO QUE TRAE ESTA CORRIDA, SE DECIDE, Y VA PRIMERO.
        # Que el sobre sirva MAS filas que su propio tope no necesita el `limit` del panel para
        # nada: ese tope ya no lo describe y la excusa se apoyaba en el. La version anterior
        # evaluaba lo que FALTA antes que esto, asi que con un log sin `limit` -y el sobre
        # sirviendo 50 filas con un tope de 8- salia «no verificable» y K44 quedaba VERDE
        # teniendo delante lo que hacia falta para condenar.
        if fs is not None and tope is not None and len(fs) > tope:
            print(f"ANULADA\t{ruta}\tel sobre sirve {len(fs)} filas y el perfil `{perfil}` topa en "
                  f"{tope} ({arg}, leido de {de}): ese tope YA NO describe al sobre y la excusa "
                  f"se apoyaba en el -y esto se decide SIN el `limit` del panel-")
            continue

        falta = []
        if fs is None: falta.append(f"el sobre no trae `{clave}` como lista de filas")
        if not perfil: falta.append("el sobre no declara su `profile`")
        if topes is None: falta.append(f"no se pudo leer PROFILE_LIMITS ({de})")
        elif perfil and perfil not in topes: falta.append(f"PROFILE_LIMITS no tiene el perfil `{perfil}`")
        elif tope is None: falta.append(f"el perfil `{perfil}` no declara `{arg}`")
        if lim is None: falta.append("el log no trae el `limit` con que el panel pide la ruta")
        if falta:
            # LO QUE NO SE PUEDE VERIFICAR NO CUENTA COMO EXCUSA VIVA. Antes esto salia como
            # VIVA y K44 daba VERDE: decirlo en la linea no lo convierte en medida, porque el
            # marcador cuenta VERDE. Es exactamente el defecto que esta campana vino a quitar,
            # y el propio K44 lo escribe dos ramas mas arriba: «dar por buena la excusa seria
            # excusar en silencio». Ahora NO da verde y NO condena al panel: la ruta queda en un
            # tercer cubo y el veredicto lo decide quien tenga algo que decir.
            print(f"NOVER\t{ruta}\tNO VERIFICABLE EN ESTA CORRIDA: {'; '.join(falta)} (tope leido "
                  f"de {de}). La excusa se sostiene contra el TOPE del perfil y NO se cambia por "
                  f"otra que hoy si se vea; pero sin poder mirarla NO cuenta como excusa viva")
            continue
        if tope >= lim:
            print(f"ANULADA\t{ruta}\tel perfil `{perfil}` topa en {tope} ({arg}, leido de {de}) y el "
                  f"panel pide limit={lim}: el sobre ya puede darle TODO lo que lee, y la "
                  f"peticion suelta sobra")
        else:
            print(f"VIVA\t{ruta}\tel sobre topa `{clave}` en {tope} ({arg} del perfil `{perfil}`, "
                  f"leido de {de}) y el panel pide limit={lim}: el sobre NO puede darle todo lo "
                  f"que lee. Hoy trae {len(fs)} filas, por debajo del tope, asi que las cuentas "
                  f"de esta hora no lo ensenan -y por eso NO son lo que sostiene la excusa-")
    elif tipo == "FILAS":
        # LO QUE EL PANEL LEE DE ESTA RUTA SON LAS FILAS: las mapea todas y publica su cuenta.
        # `rp` puede ser {rows:[...]} o una lista pelada; el valor del sobre, lo mismo.
        def filas(x):
            if isinstance(x, dict) and isinstance(x.get("rows"), list): return x["rows"]
            return x if isinstance(x, list) else None
        fr, fs = filas(rp), filas(sobre.get(clave))
        if fs is None:
            print(f"ANULADA\t{ruta}\tel sobre ya no trae `{clave}` como lista de filas: "
                  f"la excusa comparaba contra nada")
        elif fr is None:
            print(f"NOMED\t{ruta} no devolvio filas legibles, asi que su excusa no se puede reverificar")
        elif len(fs) < len(fr):
            print(f"VIVA\t{ruta}\tla ruta sirve {len(fr)} filas -pedida como la pide el panel- y "
                  f"el sobre `{clave}` solo {len(fs)}: el panel las pinta TODAS y publica su cuenta")
        elif len(fs) > len(fr):
            print(f"ANULADA\t{ruta}\tel sobre trae {len(fs)} filas y la ruta {len(fr)}: el sobre ya "
                  f"le da al panel todo lo que lee de esta ruta, y la peticion suelta sobra")
        else:
            # IGUALES: LA EXCUSA NO SE SOSTIENE HOY, Y SE DICE DE QUE DEPENDE ESO. Con la misma
            # cuenta en los dos lados el sobre le da al panel todo lo que lee, asi que la
            # peticion suelta no esta justificada en ESTA corrida y condena. Pero la igualdad
            # tiene DOS causas que estos payloads no separan -que el sobre lo traiga todo, o que
            # el tope del sobre no haya mordido porque hoy hay pocos niveles-, y la linea lo dice
            # entero: quien lea este rojo NO debe retirar la peticion suelta sin mirar un dia con
            # mas niveles que el tope. Condenar es la direccion segura porque la excusa se gana
            # en cada corrida; callar la ambiguedad seria el defecto.
            print(f"ANULADA\t{ruta}\tla ruta da {len(fr)} filas y el sobre {len(fs)}: HOY el sobre "
                  f"le da al panel todo lo que lee, asi que la excusa no se sostiene en esta "
                  f"corrida. OJO: la igualdad tambien sale cuando el tope del sobre NO ha mordido "
                  f"porque hoy hay pocos niveles, y estos payloads no separan las dos causas; "
                  f"antes de retirar la peticion suelta hay que mirar un dia con mas niveles")
    elif tipo == "MENOS":
        val = sobre.get(clave) if clave else None
        nr = len(rp) if isinstance(rp, (list, dict)) else 0
        ns = len(val) if isinstance(val, (list, dict)) else 0
        if val is None:
            print(f"ANULADA\t{ruta}\tel sobre ya no trae `{clave}`: la excusa comparaba contra nada")
        elif ns >= nr:
            print(f"ANULADA\t{ruta}\tel sobre trae {ns} y la ruta {nr}: ya no trae menos, la excusa es falsa")
        else:
            print(f"VIVA\t{ruta}\tla ruta sirve {nr} elementos y el sobre `{clave}` solo {ns}")
    else:
        print(f"ANULADA\t{ruta}\ttipo de excepcion desconocido: {tipo}")
PY
)

if printf '%s\n' "$VEREDICTOS" | grep -q '^NOMED'; then
  echo "NO MEDIDO: $(printf '%s\n' "$VEREDICTOS" | grep '^NOMED' | cut -f2- | tr '\n' ' ')" \
       "· sin reverificar las excepciones este check no puede decir si una peticion suelta" \
       "esta excusada o es un defecto, y dar por buena la excusa seria excusar en silencio.$MARCA"
  exit 2
fi

excusadas=""; anuladas=""; huerfanas=""; noverificables=""
partes=""; n_partes=0; rutas_partes=0
while read -r r n; do
  [ -n "$r" ] || continue
  if printf '%s\n' "$VEREDICTOS" | grep -q "^VIVA	$r	"; then
    razon=$(printf '%s\n' "$VEREDICTOS" | grep "^VIVA	$r	" | cut -f3)
    excusadas="$excusadas · $r($n): $razon"
    continue
  fi
  # EL TERCER CUBO. Una excusa que no se puede verificar NI excusa NI condena: la ruta no entra
  # en `partes` -no se condena al panel por algo que este check no pudo mirar- pero tampoco
  # cuenta como excusada, asi que no puede sostener un VERDE.
  if printf '%s\n' "$VEREDICTOS" | grep -q "^NOVER	$r	"; then
    razon=$(printf '%s\n' "$VEREDICTOS" | grep "^NOVER	$r	" | cut -f3)
    noverificables="$noverificables · $r($n): $razon"
    continue
  fi
  motivo=""
  if printf '%s\n' "$VEREDICTOS" | grep -q "^ANULADA	$r	"; then
    motivo=" [EXCEPCION ANULADA: $(printf '%s\n' "$VEREDICTOS" | grep "^ANULADA	$r	" | cut -f3)]"
    anuladas="$anuladas $r"
  fi
  partes="$partes $r($n)$motivo"
  n_partes=$((n_partes + n))
  rutas_partes=$((rutas_partes + 1))
done <<EOF
$pedidas_foto
EOF
huerfanas=$(printf '%s\n' "$VEREDICTOS" | grep '^HUERFANA' | cut -f2 | tr '\n' ' ')

COLA="$COLA0$MARCA"
[ -n "${excusadas// /}" ] && COLA="$COLA · EXCUSADAS Y REVERIFICADAS EN ESTA CORRIDA:$excusadas"
[ -n "${noverificables// /}" ] && COLA="$COLA · EXCUSAS QUE NO SE HAN PODIDO VERIFICAR (no excusan, y no condenan al panel):$noverificables"
[ -n "${huerfanas// /}" ] && COLA="$COLA · EXCEPCIONES HUERFANAS (el panel ya no las pide, sobran): $huerfanas"

# EL ORDEN IMPORTA. Si en esta corrida hay una ruta suelta SIN excusa, eso es un hecho sobre el
# panel y manda: el veredicto es esa condena, y las no verificables van nombradas en la linea.
# Solo cuando no hay nada que condenar, una excusa sin verificar deja el check SIN MEDIDA.
if [ "$rutas_partes" -gt 0 ]; then
  echo "REFORMA A MEDIAS: el panel pide el sobre $n_sobre veces Y ADEMAS sigue pidiendo" \
       "$n_partes veces $rutas_partes de las $N_FOTO rutas de FOTO SIN EXCUSA VIVA. Las dos" \
       "cosas a la vez cuestan mas que hoy y el sobre no gobierna la edad de lo que se pinta" \
       "·$partes · $COLA"
  exit 1
fi
if [ -n "${noverificables// /}" ]; then
  _n=$(printf '%s\n' "$noverificables" | grep -o ' · ' | grep -c .)
  echo "NO MEDIDO: ninguna ruta de FOTO queda sin excusa, pero $_n excusa(s) NO SE HAN PODIDO" \
       "VERIFICAR en esta corrida, asi que este check no ha medido si esas peticiones sueltas" \
       "estan justificadas. Decirlo en la linea y ademas dar VERDE seria contar como medida lo" \
       "que no se midio, que es justo lo que esta red existe para no hacer · $COLA"
  exit 2
fi
echo "el panel pide el sobre $n_sobre veces y CERO de las $N_FOTO rutas de FOTO sin excusa" \
     "viva: lo que se pinta como foto sale de una sola respuesta con un solo generated_at." \
     "Cada excusa se ha vuelto a comprobar contra los payloads de ESTA corrida y dice contra" \
     "que · $COLA"
exit 0
