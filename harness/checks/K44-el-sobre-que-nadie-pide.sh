#!/usr/bin/env bash
# K44 · CADA PANTALLA PIDE LO QUE TIENE QUE PEDIR (nacio como «el panel tiene que pedir el sobre»)
#
# SUJETO   lo que un navegador de verdad PIDE a 140, leido del log de nginx, y ATRIBUIDO A LA
#          PANTALLA QUE LO PIDIO. Desde la campana 133 son dos, y cada una se juzga contra lo SUYO:
#            el panel viejo (static/index.html)  pide /api/ai/context -EL SOBRE- y CERO rutas de la
#                                                familia FOTO de K43 sin excusa viva (los seis estados)
#            la mesa (static/mesa.html)           pide su NUCLEO, /api/mesa/decide, y NADA fuera de su
#                                                contrato declarado (K44-contrato-mesa.tsv)
# VERDE    cada pantalla que alguien miro en la ventana cumple lo suyo, y al menos una se miro.
# ROJO     una pantalla que se miro no cumple lo suyo. Manda esa condena, y la linea dice CUAL.
# NOMED    el canal no contesto; o no consta que nadie mirara; o nada de lo pedido se pudo atribuir;
#          o una pantalla que se miro no se pudo juzgar entera.
# LO QUE NO SE PUEDE ATRIBUIR sale NOMBRADO -motivo, rutas y cuentas- y NO SE CARGA A NINGUNA.
#
# POR QUE EXISTE. `/api/ai/context` es EL SOBRE: una sola respuesta atomica con su
# `generated_at`, de la que todo lo que es FOTO deberia salir con UNA edad en vez de con
# veintidos. Es el requisito central del diseno y es lo que K43 vigila con sus cuatro familias.
# La propia prosa de K43 dice que «que llegue a pedirlo es lo que mide K44, no esta unidad»
# — y K44 no existia: nadie lo habia escrito (COLA.md 105). Sin el, las cuatro familias pueden
# quedar las cuatro VERDES con la pantalla haciendo exactamente las mismas peticiones sueltas.
#
# EL INSTRUMENTO ES EXTERNO AL SUJETO, y tiene que serlo. Leer `static/app.js` mide su FORMA y
# cambia con su parche; ademas ahi caen los comentarios -medido al cerrar K99, que hasta COLA
# 124 se llamo K45: el criterio «no menciona ninguna ruta de FOTO» se cumplia BORRANDO UN
# COMENTARIO-. Lo que no comparte forma
# con el panel es lo que un navegador pide de verdad.
#
# EL FILTRO ES «AGENTE DE NAVEGADOR Y NO LA IP DEL ARNES», el mismo que usa K43, y no una IP:
# medido al cerrar K46, hay CUATRO navegadores en el historico -.101, .73, .99 desde un iPhone
# y .100 desde un Mac- y un solo cliente curl, el arnes desde .2. Filtrar por una IP dejaria al
# panel pidiendo rutas de FOTO desde el movil con el criterio en VERDE.
#
# ---------------------------------------------------------------------------------
# LAS DOS PANTALLAS, Y COMO SE SABE CUAL PIDIO QUE (campana 133)
#
# HASTA LA 133 ESTE CHECK LLAMABA «VISITA AL PANEL» A CUALQUIER LINEA DE NAVEGADOR, y desde la 130
# la mesa tambien es un navegador: una sola carga de la mesa -que pide rutas de la familia FOTO
# POR DISENO y nunca el sobre- lo ponia ROJO «REFORMA A MEDIAS», acusando al panel viejo de lo que
# pedia otra pantalla. Con `/` sirviendo la mesa, eso iba a ser lo normal.
#
# EL REFERER NO SIRVE PARA ATRIBUIR: LA APP LO APAGA. `app/api.py` pone `Referrer-Policy:
# no-referrer` en TODA respuesta, asi que el navegador no dice desde que pagina pide. Medido el
# 2026-10-02 sobre access.log.3.gz y .4.gz de 140: 35 710 de 35 710 lineas de navegador real con
# Referer «-». Encenderlo (`same-origin`) seria un cambio de la app que esta campana no hace.
#
# ASI QUE SE ATRIBUYE POR LA CARGA DEL DOCUMENTO, cliente por cliente (IP + agente):
#   · una CARGA es un GET con 200 o 304 de `/`, `/mesa` o `/panel`. Un 401 no es una carga.
#   · `/mesa` es la mesa; `/panel`, el panel viejo; y `/` es LO QUE SERVIA EL RELEASE ACTIVO EN ESE
#     SEGUNDO. El instante del cambio NO SALE DEL LOG QUE SE MIDE (A68): sale del registro del
#     desplegador, /var/log/coinalyze/deploy.log («current -> .../releases/<sha>» y las vueltas
#     atras), y QUE servia cada release se lee de su propio `app/api.py` -la funcion de
#     `@app.get("/")`- en 140, o de git si el release ya se podo. Una carga de `/` a menos de
#     MARGEN_S de un cambio que movio la pantalla de `/` es AMBIGUA -en una vuelta atras el proceso
#     viejo sigue sirviendo hasta que reinicia- y se nombra.
#   · una peticion es de la pantalla que su cliente tenia cargada. Si el cliente cargo LAS DOS en
#     las CARGAS_H horas que se miran, la peticion puede ser de cualquier pestana: se nombra y no se
#     carga a ninguna. Si no se ve ninguna carga suya antes de ella, tambien.
#
# POR QUE CARGAS_H = 48 Y NO LOS 14 DIAS DEL LOG, Y POR QUE NO SE MIRA EL SILENCIO. El unico
# cliente de navegador real de los 14 dias retenidos (medido el 2026-10-02) hizo 47 420 peticiones
# /api con DOS cargas de documento en cinco dias: una pestana vive dias. Con 14 dias, el dia que
# esa persona abra la mesa tras haber usado el panel, sus peticiones serian ambiguas DOS SEMANAS;
# con 48 h, como mucho dos dias. Lo que cuesta, dicho: una pestana cargada hace mas de 48 h no
# tiene carga visible y sus peticiones salen nombradas. Y el silencio no prueba que una pestana
# murio: el temporizador de 15 s del panel viejo no mira si la pestana esta oculta (static/js/08-arranque.js:166)
# -cuanto pide oculto lo decide el navegador, y no se midio-, y un portatil dormido calla a todas y al despertar siguen.
#
# EL DIA DEL DESPLIEGUE, que es el caso que obliga a todo esto: una pestana del panel cargada en `/`
# ANTES del cambio sigue pidiendo DESPUES, y por la ruta sola se cargaria a la mesa. Aqui va al
# panel, porque su carga es anterior al cambio; y si ese cliente recarga `/` despues -ya la mesa-,
# lo que pida desde entonces sale nombrado hasta que la carga del panel salga de las 48 h.
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
# lo que la ventana alcanza. Las CARGAS se buscan tambien en access.log.2.gz, que con los dos
# vivos cubre de sobra las 48 h.
#
# ---------------------------------------------------------------------------------
# LOS SEIS ESTADOS DEL PANEL VIEJO, y cada uno tiene su linea. El encargo nombraba cuatro; son
# seis, y los dos que faltaban son un ROJO y un NOMED:
#
#   1 EL CANAL NO CONTESTO ................. NOMED. No es un hecho sobre nada.
#   2 NO CONSTA QUE NADIE MIRARA ........... NOMED. No es un hecho sobre el panel: en una
#     ventana sin visitas, «cero peticiones al sobre» sale igual que si el panel lo pidiera
#     en cada carga. Sin esta rama K44 se pondria rojo un domingo por la tarde y alguien lo
#     «arreglaria» sin que hubiera nada que arreglar. Desde la 133 es POR PANTALLA: la que no se
#     miro no se juzga y lo dice; si no se miro ninguna, el check entero es NO MEDIDO.
#   3 NO SE PUDO LEER LA LISTA FOTO ........ NOMED. El conjunto no es de este check: sale de la
#     ASIGNACION de K43. Sin el no hay criterio, y un criterio sobre cero rutas se cumple solo.
#   3b UNA EXCUSA QUE NO SE PUDO VERIFICAR . NOMED, y NO VERDE. Si falta lo que la sostiene -el
#     `profile` del sobre, `PROFILE_LIMITS`, el `limit` del log-, esa ruta no se excusa y
#     TAMPOCO se condena: queda en un tercer cubo. Decirlo en la linea y ademas dar VERDE seria
#     contar como medida lo que no se midio. Si en la misma corrida hay una ruta suelta SIN
#     excusa, manda esa condena y las no verificables van nombradas.
#   4 PIDE EL SOBRE Y CERO PARTES .......... VERDE. «Cero partes» = cero SIN EXCUSA VIVA; las
#     excusadas se nombran con la razon contra la que se comprobaron en esta misma corrida.
#   5 NO PIDE EL SOBRE ..................... ROJO.
#   6 PIDE EL SOBRE Y SIGUE PIDIENDO PARTES  ROJO, y es OTRO rojo: en el 5 no ha empezado
#     nadie; en el 6 alguien empezo y dejo las dos cosas puestas —que cuesta MAS que hoy—.
#     Las dos condiciones van juntas a proposito: pedir la foto sin dejar de pedir las partes
#     cumpliria un criterio de una sola mitad siendo falso.
#
# LA MESA, contra su contrato (K44-contrato-mesa.tsv, que DECLARA lo que pide hoy y por que):
#   ROJO   pide una ruta que su contrato no declara; o carga su vista principal -pide una ruta que
#          solo pide esa vista- y NO pide su NUCLEO, que esa vista pide siempre antes que nada.
#   NOMED  se miro y el contrato no se pudo leer: sin el no hay contra que juzgarla.
#   VERDE  todo lo que pidio esta en su contrato. Lo declarado y no pedido se NOMBRA y no condena:
#          es un marco o una vista que nadie abrio en la ventana.
#
# ---------------------------------------------------------------------------------
# LA EXCEPCION NO ES UN NOMBRE EN UNA LISTA: ES UNA AFIRMACION QUE ESTE CHECK VUELVE A
# COMPROBAR EN CADA CORRIDA. Es el patron que el operador impuso a K99 -entonces K45- (COLA
# 118) traido aqui.
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
#
# Y UNA REGLA QUE VALE PARA TODOS LOS TIPOS (COLA 128): si el SOBRE NO TRAE la clave de la que
# habla la excusa, la excusa SE SOSTIENE. No sirve ese dato, luego el panel no tiene de donde
# sacarlo y la peticion suelta es necesaria. Antes eso daba tres veredictos distintos segun el
# tipo -ROJO en MENOS, NO MEDIDO en TOPE, excusa viva en FALTAN-, o sea que el veredicto lo
# decidia la fila de esta tabla y no el sobre. La clave PRESENTE y VACIA es otra cosa y no se
# toca: esa depende del mercado, y en FALTAN ademas cumpliria la excusa por construccion.
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
CONTRATO=${K44_CONTRATO:-$REPO/harness/checks/K44-contrato-mesa.tsv}
VENTANA_H=${K44_VENTANA_H:-6}
CARGAS_H=${K44_CARGAS_H:-48}
MARGEN_S=${K44_MARGEN_S:-120}
ARNES_IP=${K44_ARNES_IP:-10.10.100.2}
SOBRE=/api/ai/context

TMPX=$(mktemp -d /tmp/k44.XXXXXX) || { echo "NO MEDIDO: no se pudo crear un directorio temporal"; exit 2; }
trap 'rm -rf "$TMPX"' EXIT

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

# --- 2 · EL LOG, CRUDO, A UN FICHERO Y CON SU rc (recetas A8 y A89) ---------------------------
# Las tuberias van DENTRO del mandato que ejecuta 140, asi que este rc es el de bin/prod y no el
# de un filtro que lo suplanta. `grep -a` es obligatorio -A4: sobre un flujo con bytes no texto,
# grep declara «binary file matches» y CALLA las lineas, y CERO es justo lo que este check busca-.
#
# LO QUE EL MANDATO DEVUELVE, linea a linea y con su etiqueta:
#   AHORA <epoch>   la hora la pone 140, que es la del log
#   C <linea>       una carga de documento (/, /mesa, /panel) de access.log.2.gz, .1 o el vivo
#   A <linea>       una peticion /api de las ultimas VENTANA_H+1 horas del log vivo y del .1. El
#                   log va en hora LOCAL, asi que 140 da sus etiquetas de hora y aqui se corta por
#                   epoch exacto: la aritmetica de husos no se hace en 143.
#   D <linea>       un cambio de release del desplegador (/var/log/coinalyze/deploy.log)
#   R <sha> <html>  QUE fichero sirve `/` cada release que 140 conserva
#   K44-FIN         la ultima: sin ella la respuesta esta incompleta y no se juzga nada.
#
# A FICHERO, NO A UNA VARIABLE (A89): en una tarde de uso son miles de lineas, y `printf "$VAR" |
# grep -q` sobre mas de 64 KB es justo el defecto de K104. Aqui nada de eso se pasa por tuberia.
# TODO=1 porque el corte de 8 KB de bin/prod cortaria el log a media linea: se dice el porque.
# El mandato NO puede llevar `>`: bin/prod lo lee como redireccion a fichero y DENIEGA (rc=3).
read -r -d '' LOG_CMD <<'REMOTO'
echo "AHORA $(date +%s)"
horas=$(for i in $(seq 0 __VH__); do LC_ALL=C date -d "-$i hours" +%d/%b/%Y:%H; done | tr '\n' '|' | sed 's/|$//')
{ zcat /var/log/nginx/access.log.2.gz 2>/dev/null; echo "@@VIVOS@@"; cat /var/log/nginx/access.log.1 /var/log/nginx/access.log 2>/dev/null; } | grep -a -e Mozilla -e '^@@VIVOS@@$' | grep -av '^__ARNES__ ' | awk -v H="$horas" '
  BEGIN { n = split(H, a, "|") }
  $0 == "@@VIVOS@@" { vivos = 1; next }
  { split($0, q, "\""); split(q[2], r, " "); p = r[2]; sub(/\?.*/, "", p)
    if (r[1] == "GET" && (p == "/" || p == "/mesa" || p == "/panel")) { print "C " $0; next }
    if (vivos && p ~ /^\/api\//) for (i = 1; i <= n; i++) if (index($4, a[i]) == 2) { print "A " $0; break } }'
grep -a -E 'current -|rolling back to|restoring previous release' /var/log/coinalyze/deploy.log 2>/dev/null | sed 's/^/D /'
for d in /opt/coinalyze/releases/*/; do
  f=$(awk '/^@app.get\("\/"\)/ { e = 1 } e && /FileResponse\(/ { print; exit }' "$d/app/api.py" 2>/dev/null | grep -o '[a-z_]*\.html' | head -1)
  echo "R $(basename "$d") ${f:-?}"
done
echo K44-FIN
REMOTO
LOG_CMD=${LOG_CMD//__VH__/$VENTANA_H}
LOG_CMD=${LOG_CMD//__ARNES__/$ARNES_IP}

# DOS GANCHOS PARA INYECTAR, y el segundo no es un capricho: una ventana REAL no cabe en una variable
# de entorno. Medido en la 133: el 29/Sep, 12-18 h, un solo cliente hizo 8 664 peticiones /api en 6 h
# -1.86 MB de log- y `K44_LOG="$(cat ...)"` murio con «Argument list too long» antes de arrancar.
if [ -n "${K44_LOG_FICHERO:-}" ]; then
  if ! cp "$K44_LOG_FICHERO" "$TMPX/crudo" 2>/dev/null; then
    echo "NO MEDIDO: no se pudo leer el log inyectado por K44_LOG_FICHERO ($K44_LOG_FICHERO)." \
         "Esta linea NO dice nada sobre lo que pide ninguna pantalla."
    exit 2
  fi
  _rc=0; ORIGEN="inyectado"
elif [ "${K44_LOG+puesta}" = puesta ]; then
  printf '%s\n' "$K44_LOG" > "$TMPX/crudo"
  _rc=0; ORIGEN="inyectado"
else
  TODO=1 "$B/bin/prod" "$LOG_CMD" > "$TMPX/crudo" 2>/dev/null
  _rc=$?; ORIGEN="canal"
fi
if [ "$_rc" -ne 0 ]; then
  echo "NO MEDIDO: el log de nginx no se pudo leer (bin/prod rc=$_rc)." \
       "Esta linea NO dice nada sobre lo que el panel pide, ni que pida el sobre ni que no," \
       "ni sobre lo que pide la mesa."
  exit 2
fi
# bin/prod sale 0 aunque el ssh falle (su rc es el de su filtro de corte): la marca final es lo
# unico que prueba que el mandato remoto llego hasta el final.
if ! grep -q '^K44-FIN$' "$TMPX/crudo"; then
  echo "NO MEDIDO: el log de nginx llego INCOMPLETO, sin la marca final del mandato remoto" \
       "($(wc -c < "$TMPX/crudo") B; primera linea: «$(head -c 140 "$TMPX/crudo" | tr '\n' ' ')»)" \
       "-o, si es inyectado, viene en la forma AGREGADA de antes de la 133, que no dice que cliente" \
       "pidio que y no se puede atribuir-. Esta linea NO dice nada sobre lo que el panel pide, ni sobre" \
       "lo que pide la mesa."
  exit 2
fi
MARCA=""
GANCHO=K44_LOG; [ -n "${K44_LOG_FICHERO:-}" ] && GANCHO=K44_LOG_FICHERO
[ "$ORIGEN" = inyectado ] && MARCA=" [log INYECTADO por $GANCHO, no leido del canal]"

# --- 2b · LA ATRIBUCION, Y EL JUICIO DE LA MESA --------------------------------------------
RUTAS_EX=$(printf '%s\n' "$EXCEPCIONES" | awk -F'|' 'NF>1 {gsub(/ /,"",$1); if ($1!="") printf "|%s", $1} END {printf "|"}')
CRUDO="$TMPX/crudo" VENTANA_H="$VENTANA_H" CARGAS_H="$CARGAS_H" MARGEN_S="$MARGEN_S" \
ARNES_IP="$ARNES_IP" REPO="$REPO" FOTO="$(printf '%s ' $FOTO)" RUTAS_EX="$RUTAS_EX" \
CONTRATO="$CONTRATO" python3 - > "$TMPX/atrib" 2> "$TMPX/atrib.err" <<'PY'
import os, re, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

VH = float(os.environ["VENTANA_H"]); CH = float(os.environ["CARGAS_H"])
MARGEN = float(os.environ["MARGEN_S"]); ARNES = os.environ["ARNES_IP"]; REPO = os.environ["REPO"]
FOTO = set(os.environ.get("FOTO", "").split())
EXC = set(os.environ.get("RUTAS_EX", "").split("|")) - {""}
PANTALLA_DE = {"index.html": "panel", "mesa.html": "mesa"}
NOMBRE = {"panel": "el panel viejo", "mesa": "la mesa"}
LINEA = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "([^"]*)" (\d{3}) \S+ "[^"]*" "([^"]*)"')

def sale(*c):
    print("\t".join(str(x) for x in c))

def epoch_nginx(s):
    try:
        return datetime.strptime(s, "%d/%b/%Y:%H:%M:%S %z").timestamp()
    except ValueError:
        return None

def corto(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%m-%d %H:%M:%SZ")

ahora = None
cargas, pets, desp, rel = [], [], [], {}
with open(os.environ["CRUDO"], encoding="utf-8", errors="replace") as fh:
    for ln in fh:
        ln = ln.rstrip("\n")
        tag, _, resto = ln.partition(" ")
        if tag == "AHORA":
            try:
                ahora = int(resto.strip())
            except ValueError:
                pass
        elif tag in ("C", "A"):
            m = LINEA.match(resto)
            if not m:
                continue
            ip, t, pet, st, ua = m.group(1), epoch_nginx(m.group(2)), m.group(3), int(m.group(4)), m.group(5)
            # EL FILTRO OTRA VEZ AQUI: lo inyectado no ha pasado por el grep de 140.
            if t is None or ip == ARNES or "Mozilla" not in ua:
                continue
            p = pet.split(" ")
            if len(p) < 2:
                continue
            completa = p[1]
            ruta = completa.split("?", 1)[0].split("#", 1)[0]
            if tag == "C":
                if p[0] == "GET" and ruta in ("/", "/mesa", "/panel") and st in (200, 304):
                    cargas.append((t, (ip, ua), ruta))
            elif ruta.startswith("/api/"):
                pets.append((t, (ip, ua), ruta, completa))
        elif tag == "D":
            desp.append(resto)
        elif tag == "R":
            q = resto.split()
            if q:
                rel[q[0]] = q[1] if len(q) > 1 else "?"

if ahora is None:
    sale("ERROR", "el mandato remoto no dijo la hora (falta la linea AHORA)")
    sys.exit(0)

# LA LINEA DE TIEMPO DE `/`, del registro del DESPLEGADOR (A68: el borde no sale del dato medido).
EV = []
PATRONES = (re.compile(r"current -> \S*/releases/([^/\s]+)"), re.compile(r"rolling back to (\S+)"),
            re.compile(r"restoring previous release (\S+)"))
for d in desp:
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z\s+(.*)$", d)
    if not m:
        continue
    t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    for pat in PATRONES:
        m2 = pat.search(m.group(2))
        if m2:
            if m2.group(1) != "none":
                EV.append((t, m2.group(1)))
            break
EV.sort()

_git = {}
def fichero_de(sha):
    """QUE fichero sirve `/` en ese release: lo que dice 140 de su propio arbol, o git si se podo."""
    f = rel.get(sha)
    if f and f != "?":
        return f, "140"
    if sha in _git:
        return _git[sha]
    r = (None, "ni 140 lo conserva ni git lo encuentra")
    try:
        out = subprocess.run(["git", "-C", REPO, "show", sha + ":app/api.py"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            i = out.stdout.find('@app.get("/")')
            if i >= 0:
                tramo = out.stdout[i:]
                j = tramo.find("@app.", 5)
                tramo = tramo[:j] if j > 0 else tramo
                m = re.search(r'FileResponse\([^)]*?"([a-z_]+\.html)"', tramo)
                if m:
                    r = (m.group(1), "git")
    except Exception:
        pass
    _git[sha] = r
    return r

def pantalla_raiz(t):
    idx = None
    for i, (te, _sha) in enumerate(EV):
        if te <= t:
            idx = i
        else:
            break
    if idx is None:
        return None, "carga de `/` sin ningun cambio de release registrado antes"
    te, sha = EV[idx]
    f, de = fichero_de(sha)
    p = PANTALLA_DE.get(f or "")
    if p is None:
        return None, f"carga de `/` con el release {sha[:7]}, del que no se sabe que servia ({de})"
    if idx > 0 and t - te <= MARGEN:
        fp, _ = fichero_de(EV[idx - 1][1])
        pp = PANTALLA_DE.get(fp or "")
        if pp != p:
            return None, (f"carga de `/` a {int(t - te)} s del cambio ({NOMBRE.get(pp, '?')} -> "
                          f"{NOMBRE[p]}, {corto(te)}), dentro del margen de {int(MARGEN)} s")
    return p, None

ini, ini_c = ahora - VH * 3600, ahora - CH * 3600
por_cliente = defaultdict(list)
for (t, k, ruta) in cargas:
    if ini_c <= t <= ahora:
        if ruta == "/mesa":
            p, mot = "mesa", None
        elif ruta == "/panel":
            p, mot = "panel", None
        else:
            p, mot = pantalla_raiz(t)
        por_cliente[k].append((t, ruta, p, mot))
for k in por_cliente:
    por_cliente[k].sort(key=lambda c: c[0])

pide = {"panel": Counter(), "mesa": Counter()}
query = Counter()
rutas_doc = {"panel": set(), "mesa": set()}
sin = defaultdict(Counter)
n_api, clientes = 0, set()
for (t, k, ruta, completa) in pets:
    if not (ini <= t <= ahora):
        continue
    n_api += 1
    clientes.add(k)
    previas = [c for c in por_cliente.get(k, ()) if c[0] <= t]
    if not previas:
        sin[f"sin carga visible de ninguna pantalla en las {CH:g} h de cargas que se miran"][ruta] += 1
        continue
    ambiguas = [c for c in previas if c[2] is None]
    if ambiguas:
        sin[ambiguas[-1][3]][ruta] += 1
        continue
    ps = {c[2] for c in previas}
    if len(ps) > 1:
        sin[f"el cliente tenia cargadas LAS DOS pantallas en esas {CH:g} h: pudo pedirla cualquiera"][ruta] += 1
        continue
    p = ps.pop()
    pide[p][ruta] += 1
    rutas_doc[p].update(c[1] for c in previas)
    if p == "panel" and ruta in EXC:
        query[completa] += 1

n_cargas = sum(1 for (t, _k, _r) in cargas if ini <= t <= ahora)
sale("META", "n_api", n_api)
sale("META", "n_clientes", len(clientes))
sale("META", "n_cargas", n_cargas)
for p in ("panel", "mesa"):
    docs = " y ".join(f"`{r}`" for r in sorted(rutas_doc[p]))
    sale("PANT", p, sum(pide[p].values()), docs)
for p in ("panel", "mesa"):
    for r, n in sorted(pide[p].items()):
        sale("PIDE", p, n, r)
for c, n in sorted(query.items()):
    sale("QUERY", "panel", n, c)
for motivo, cuenta in sin.items():
    sale("SIN", sum(cuenta.values()), motivo, " ".join(f"{r}({n})" for r, n in sorted(cuenta.items())))

# LA PUERTA EN LA VENTANA DE CARGAS: que servia `/` al empezar y cada cambio dentro.
p0, mot0 = pantalla_raiz(ini_c)
cambios = []
for te, sha in EV:
    if ini_c < te <= ahora:
        f, _ = fichero_de(sha)
        cambios.append(f"{corto(te)} release {sha[:7]} -> {NOMBRE.get(PANTALLA_DE.get(f or ''), '?')}")
sale("META", "puerta",
     (f"`/` servia {NOMBRE[p0]} al empezar las {CH:g} h de cargas" if p0 else f"`/` al empezar las {CH:g} h: {mot0}")
     + (" · cambios del desplegador dentro: " + "; ".join(cambios) if cambios else " · sin cambios de release dentro")
     + f" · margen {int(MARGEN)} s")

# LA MESA, CONTRA SU CONTRATO DECLARADO.
contrato, err = {}, None
try:
    with open(os.environ["CONTRATO"], encoding="utf-8") as fh:
        for ln in fh:
            if not ln.strip() or ln.startswith("#"):
                continue
            c = ln.rstrip("\n").split("\t")
            if len(c) >= 2 and c[0].startswith("/api/"):
                contrato[c[0]] = {x.strip() for x in c[1].split(",") if x.strip()}
except OSError as e:
    err = str(e)
if not contrato and err is None:
    err = "no tiene ninguna fila /api/"
mp = pide["mesa"]
nombre_m = "la mesa (static/mesa.html" + (f", cargada por {' y '.join(f'`{r}`' for r in sorted(rutas_doc['mesa']))}" if rutas_doc["mesa"] else "") + ")"
if not mp:
    sale("MESA", 3, f"la mesa (static/mesa.html): sin visitas en las {VH:g} h", "")
elif err:
    sale("MESA", 2, f"NO MEDIDO: {nombre_m} se miro ({sum(mp.values())} peticiones) y su contrato no se pudo leer "
                    f"({os.environ['CONTRATO']}: {err}): sin el no hay contra que juzgarla", "")
else:
    nucleo = sorted(r for r, pap in contrato.items() if "NUCLEO" in pap)
    principal = sorted(r for r in mp if contrato.get(r) == {"PARTE"})
    n_nucleo = sum(mp.get(r, 0) for r in nucleo)
    fuera = sorted((r, n) for r, n in mp.items() if r not in contrato)
    pedidas = [r for r in contrato if mp.get(r)]
    no_pedidas = [r for r in contrato if not mp.get(r)]
    det = "pidio " + " ".join(f"{r}({n})" for r, n in sorted(mp.items()))
    if no_pedidas:
        det += (" · declaradas y NO pedidas en esta ventana -un marco o una vista que nadie abrio; no "
                "condenan-: " + " ".join(no_pedidas))
    if not principal and not n_nucleo and not fuera:
        det += " · solo se miro su vista de ESTADO, que no pide el nucleo: no se le exige"
    malas = []
    if fuera:
        malas.append("pide FUERA de su contrato (K44-contrato-mesa.tsv): "
                     + " ".join(f"{r}({n})" for r, n in fuera))
    if principal and not n_nucleo:
        malas.append(f"carga su vista principal ({' '.join(principal)}) y NO pide su nucleo "
                     + " ".join(nucleo) + ", que esa vista pide siempre antes que nada")
    if malas:
        sale("MESA", 1, f"{nombre_m} " + " Y ADEMAS ".join(malas), det)
    elif not n_nucleo:
        sale("MESA", 0, f"{nombre_m} solo se miro en su vista de ESTADO, que no pide el nucleo, y no pidio "
                        f"NADA fuera de su contrato: {len(pedidas)} de sus {len(contrato)} rutas declaradas", det)
    else:
        foto = [r for r in pedidas if r in FOTO]
        sale("MESA", 0, f"{nombre_m} pide su nucleo {' '.join(nucleo)} {n_nucleo} veces y NADA fuera de su "
                        f"contrato: {len(pedidas)} de sus {len(contrato)} rutas declaradas, {len(foto)} de "
                        f"ellas de la familia FOTO de K43 -por diseno, con su porque en el contrato-", det)
PY
_rc=$?
if [ "$_rc" -ne 0 ] || grep -q '^ERROR' "$TMPX/atrib"; then
  echo "NO MEDIDO: la atribucion de peticiones a pantallas no se pudo hacer (rc=$_rc):" \
       "$(grep -m1 '^ERROR' "$TMPX/atrib" | cut -f2) $(tail -1 "$TMPX/atrib.err" | cut -c1-160)." \
       "Esta linea NO dice nada sobre lo que pide ninguna pantalla.$MARCA"
  exit 2
fi
meta() { awk -F'\t' -v K="$1" '$1=="META" && $2==K {print $3; exit}' "$TMPX/atrib"; }
N_API=$(meta n_api); N_CLIENTES=$(meta n_clientes); N_CARGAS=$(meta n_cargas); PUERTA=$(meta puerta)
P_VISITAS=$(awk -F'\t' '$1=="PANT" && $2=="panel" {print $3}' "$TMPX/atrib")
P_RUTAS=$(awk -F'\t' '$1=="PANT" && $2=="panel" {print $4}' "$TMPX/atrib")
P_NOMBRE="el panel viejo (static/index.html${P_RUTAS:+, cargado por $P_RUTAS})"
N_SIN=$(awk -F'\t' '$1=="SIN" {s+=$2} END {print s+0}' "$TMPX/atrib")
SIN_DET=$(awk -F'\t' '$1=="SIN" {printf " · %s: %s", $3, $4}' "$TMPX/atrib")
M_RC=$(awk -F'\t' '$1=="MESA" {print $2; exit}' "$TMPX/atrib")
M_LINEA=$(awk -F'\t' '$1=="MESA" {print $3; exit}' "$TMPX/atrib")
M_DET=$(awk -F'\t' '$1=="MESA" {print $4; exit}' "$TMPX/atrib")

# Lo que el PANEL VIEJO pidio, en el formato de siempre: «cuenta ruta» y «cuenta query».
pedidas=$(awk -F'\t' '$1=="PIDE" && $2=="panel" {print $3, $4}' "$TMPX/atrib")
# LA QUERY CON LA QUE EL PANEL PIDE CADA RUTA, sacada del log y no copiada a mano. Sin ella la
# comparacion de filas se haria contra la peticion equivocada: `liquidation-levels` da 5 filas
# con el limit por defecto y 9 con el del panel.
QUERIES=$(awk -F'\t' '$1=="QUERY" {print $3, $4}' "$TMPX/atrib" | sort -rn)
COLA0="ventana ${VENTANA_H} h · ${N_API:-0} peticiones /api de navegador de ${N_CLIENTES:-0} cliente(s) y ${N_CARGAS:-0} carga(s) de pantalla · $N_FOTO rutas en la familia FOTO"

# --- 3 · EL PANEL VIEJO, CONTRA LO SUYO ----------------------------------------------------
# Deja P_RC (0 VERDE · 1 ROJO · 2 NO MEDIDO · 3 SIN VISITAS), P_LINEA y P_DET. No sale: el
# veredicto del check lo decide el paso 5 con las dos pantallas delante.
juzga_panel() {
  P_DET=""
  if [ "${P_VISITAS:-0}" -lt 1 ]; then
    P_RC=3; P_LINEA="$P_NOMBRE: sin visitas en las ${VENTANA_H} h"; return 0
  fi
  n_sobre=$(printf '%s\n' "$pedidas" | awk -v S="$SOBRE" '$2==S {s+=$1} END {print s+0}')
  pedidas_foto=""
  local r n
  while read -r r; do
    [ -n "$r" ] || continue
    n=$(printf '%s\n' "$pedidas" | awk -v R="$r" '$2==R {s+=$1} END {print s+0}')
    [ "$n" -gt 0 ] && pedidas_foto="$pedidas_foto$r $n
"
  done <<EOF
$FOTO
EOF

  # --- 3a · EL ESTADO 5 NO PASA POR LAS EXCEPCIONES ----------------------------------------
  # Si el panel NO pide el sobre, excusar una ruta por «el sobre no trae lo suyo» no significa
  # nada: no hay sobre que consultar. Se cuentan TODAS las partes y se condena, que es el estado
  # 5 de siempre. Ademas asi este brazo no depende del canal de payloads.
  if [ "$n_sobre" -lt 1 ]; then
    local n_partes=0 rutas_partes=0 partes=""
    while read -r r n; do
      [ -n "$r" ] || continue
      partes="$partes $r($n)"; n_partes=$((n_partes + n)); rutas_partes=$((rutas_partes + 1))
    done <<EOF
$pedidas_foto
EOF
    P_RC=1
    P_LINEA="$P_NOMBRE NO pide el sobre: 0 peticiones a $SOBRE, y $n_partes a $rutas_partes de las $N_FOTO rutas de FOTO, que es reconstruir la foto en vez de consumirla ·$partes"
    return 0
  fi

  # --- 3b · SIN PARTES NO HAY NADA QUE EXCUSAR -----------------------------------------------
  # Cero rutas sueltas: el VERDE no necesita consultar ningun payload. Mantiene barato el caso
  # bueno, que es el que va a correr casi siempre.
  if [ -z "${pedidas_foto//[$' \t\n']/}" ]; then
    # LA OTRA DIRECCION, Y SALE GRATIS: si el panel no pide NINGUNA parte, entonces TODAS las
    # excepciones declaradas sobran. Se dicen por su nombre sin bajar un solo payload. Callarlas
    # dejaria que una excusa muerta viviera para siempre en la tabla sin que nadie la mire.
    local todas
    todas=$(printf '%s\n' "$EXCEPCIONES" | awk -F'|' 'NF>1 {gsub(/ /,"",$1); if ($1!="") printf "%s ", $1}')
    [ -n "${todas// /}" ] && P_DET="EXCEPCIONES HUERFANAS (el panel ya no pide ninguna parte, las $(printf '%s' "$todas" | wc -w) sobran): $todas"
    P_RC=0
    P_LINEA="$P_NOMBRE pide el sobre $n_sobre veces y CERO de las $N_FOTO rutas de FOTO: lo que se pinta como foto sale de una sola respuesta con un solo generated_at"
    return 0
  fi

  # --- 3c · LAS EXCEPCIONES, REVERIFICADAS CONTRA LOS PAYLOADS DE ESTA MISMA CORRIDA -------
  # Se bajan el sobre y SOLO las rutas que tienen excepcion declarada: cuatro peticiones, no 22.
  # Si el canal de payloads no contesta NO se excusa a nadie por defecto -eso seria la excepcion
  # silenciosa que este mecanismo existe para impedir-: sale NO MEDIDO y se dice cual fallo.
  API=${K44_API:-$B/bin/api}
  SIMBOLO=${K44_SIMBOLO:-$(TODO=1 timeout 60 "$API" /api/symbols 2>/dev/null \
    | sed -n 's/.*"symbol":"\([^"]*\)".*/\1/p' | head -1)}
  if [ -z "$SIMBOLO" ]; then
    P_RC=2
    P_LINEA="NO MEDIDO: no se pudo leer ningun simbolo de /api/symbols, asi que las excepciones de $P_NOMBRE no se pueden reverificar. Sin reverificarlas NO se excusa a nadie: una excusa que no se comprueba es exactamente lo que este mecanismo existe para impedir."
    return 0
  fi

  COMO_SE_PIDIO=""
  if [ -n "${K44_PAYLOADS:-}" ]; then
    cp "$K44_PAYLOADS"/*.json "$TMPX"/ 2>/dev/null
    MARCA="$MARCA [payloads INYECTADOS por K44_PAYLOADS]"
  else
    TODO=1 timeout 90 "$API" "/api/ai/context?symbol=$SIMBOLO" > "$TMPX/_sobre.json" 2>/dev/null
    local _t _a _c q
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
  # donde el sobre se construye-, y si el canal no contesta, del arbol local. La fuente se
  # declara en la linea: un tope leido del arbol equivocado es una copia con otro nombre.
  TOPES_DE=""
  if [ -n "${K44_LIMITS:-}" ]; then
    cp "$K44_LIMITS" "$TMPX/_limits.py" 2>/dev/null && TOPES_DE="INYECTADO por K44_LIMITS"
  else
    "$B/bin/prod" "sed -n '/^PROFILE_LIMITS/,/^}/p' /opt/coinalyze/current/app/ai_context.py" > "$TMPX/_limits.src" 2>/dev/null
    if grep -q '^PROFILE_LIMITS' "$TMPX/_limits.src"; then
      cp "$TMPX/_limits.src" "$TMPX/_limits.py"; TOPES_DE="el release desplegado en 140"
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

def sin_verificar_todas(motivo):
    """UN FALLO GLOBAL YA NO APAGA EL CHECK ENTERO (A54, COLA 125). Sin el sobre no se puede
    reverificar NINGUNA excusa, y eso se dice ruta por ruta en el TERCER CUBO; pero que el
    panel pida SUELTA una ruta de FOTO que no tiene excusa ninguna es un hecho que NO necesita
    el sobre, y esa condena no puede comersela lo que falta. Se emite ademas una linea `NOMED`
    global para que, cuando no haya nada que condenar, el veredicto sea NO MEDIDO y no VERDE."""
    for _ln in os.environ["EXCEPCIONES"].strip().splitlines():
        if not _ln.strip(): continue
        _r = _ln.split("|")[0].strip()
        if not _r: continue
        if _r not in pedidas:
            print(f"HUERFANA\t{_r}\tel panel ya no la pide en la ventana: la excepcion sobra")
        else:
            print(f"NOVER\t{_r}\t{motivo}")
    print(f"NOMED\t{motivo}")
    sys.exit(0)

if sobre is None:
    sin_verificar_todas("no se pudo leer el sobre, asi que ninguna excepcion se puede reverificar")
cs = hojas_claves(sobre)
faltan_testigos = [t for t in TESTIGOS if t not in cs]
if faltan_testigos:
    sin_verificar_todas("el buscador de claves no encuentra en el sobre "
                        + " ".join(faltan_testigos) + ", que SI estan: esta roto y excusaria a cualquiera")

# ── UN SOLO TRATAMIENTO PARA «EL SOBRE NO TRAE LA CLAVE DE LA QUE HABLA LA EXCUSA» ───────────
# HASTA LA COLA 128 HABIA TRES, Y EL VEREDICTO DEPENDIA DE QUE EXCUSA FUERA Y NO DEL SOBRE.
# Medido con plantados sobre los payloads reales y el mismo log:
#     sin `delta_matrix`       (MENOS)  -> ANULADA  -> ROJO,      rc=1
#     sin `liquidation_levels` (TOPE)   -> NOVER    -> NO MEDIDO, rc=2
#     sin `scalp_persistence`  (FALTAN) -> es su premisa          rc=0
# Tres respuestas a la MISMA pregunta sobre el MISMO sobre. Decidido por el operador: LA EXCUSA
# SE SOSTIENE. Si el sobre no sirve ese dato en ninguna forma, el panel no tiene de donde sacarlo
# y la peticion suelta es justo lo que la excusa dice que es: necesaria. Que la excusa la mate
# precisamente el caso en que su premisa es MAS cierta era la version mas cara del defecto.
#
# NO ES LO MISMO QUE LA CLAVE VACIA, y por eso la vacia se queda COMO HOY. Ausente = el sobre no
# publica ese dato, que es una propiedad del CODIGO y no se mueve con la hora. Vacia = el sobre
# SI lo publica y hoy no trae nada dentro, que es el MERCADO (A53) -y en FALTAN ademas hace que
# la excusa se cumpla por construccion, que es la guarda de vacuidad que hay unas lineas mas
# abajo-. Unificar las dos habria borrado esa guarda.
#
# LO QUE NO CAMBIA HOY: ninguna de las tres entradas del sobre puede faltar sin tocar codigo
# -son entradas literales, medido en la COLA 126-, asi que con los payloads reales K44 sigue
# dando lo que daba. Esto se escribe para el dia en que una se vuelva condicional, que es
# exactamente cuando ya no se podria decidir con la cabeza fria.
def sin_esa_clave(ruta, clave, tipo):
    print(f"VIVA\t{ruta}\tel sobre NO TRAE `{clave}` en absoluto ({tipo}): no sirve ese dato en "
          f"ninguna forma, asi que el panel no tiene de donde sacarlo y la peticion suelta es "
          f"NECESARIA. Un solo tratamiento para las tres excusas (COLA 128); la clave PRESENTE "
          f"y vacia es otra cosa y se trata aparte")

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
        # EL TERCER CUBO, NO EL INTERRUPTOR. Esta linea decia `NOMED` y apagaba el check
        # entero: una ruta ilegible se comia la condena de OTRA que el panel pide suelta y sin
        # excusa. Lo que no se pudo leer no excusa y no condena -y se dice con su nombre-.
        print(f"NOVER\t{ruta}\tno se pudo leer su payload en esta corrida, asi que su excusa "
              f"no se ha podido reverificar: ni excusa ni condena")
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
                sin_esa_clave(ruta, clave, "FALTAN"); continue
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
        # AUSENTE Y «NO ES UNA LISTA DE FILAS» SON DOS COSAS Y ANTES CAIAN EN LA MISMA. Que el
        # sobre no traiga la clave es decidible (la excusa se sostiene); que la traiga con una
        # forma que no se sabe leer NO lo es, y ese sigue yendo al tercer cubo.
        bruto = sobre.get(clave, "<<AUSENTE>>")
        ausente = (bruto == "<<AUSENTE>>" or bruto is None)
        fs = None if ausente else filas(bruto)
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

        if ausente:
            sin_esa_clave(ruta, clave, "TOPE"); continue

        falta = []
        if fs is None: falta.append(f"el sobre trae `{clave}` pero NO como lista de filas")
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
        bruto = sobre.get(clave, "<<AUSENTE>>")
        if bruto == "<<AUSENTE>>" or bruto is None:
            # EL MISMO TRATAMIENTO QUE LAS OTRAS TRES, aunque hoy no haya ninguna fila FILAS
            # declarada: dejarlo distinto aqui seria volver a poner el defecto donde nadie mira.
            sin_esa_clave(ruta, clave, "FILAS"); continue
        fr, fs = filas(rp), filas(bruto)
        if fs is None:
            print(f"NOVER\t{ruta}\tel sobre trae `{clave}` pero NO como lista de filas, asi que "
                  f"su excusa no se puede reverificar: ni excusa ni condena")
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
        if not clave:
            print(f"ANULADA\t{ruta}\tla fila MENOS no declara clave del sobre: la tabla esta mal "
                  f"escrita y no hay nada contra que comparar")
            continue
        val = sobre.get(clave, "<<AUSENTE>>")
        if val == "<<AUSENTE>>" or val is None:
            sin_esa_clave(ruta, clave, "MENOS"); continue
        nr = len(rp) if isinstance(rp, (list, dict)) else 0
        ns = len(val) if isinstance(val, (list, dict)) else 0
        if ns >= nr:
            print(f"ANULADA\t{ruta}\tel sobre trae {ns} y la ruta {nr}: ya no trae menos, la excusa es falsa")
        else:
            print(f"VIVA\t{ruta}\tla ruta sirve {nr} elementos y el sobre `{clave}` solo {ns}")
    else:
        print(f"ANULADA\t{ruta}\ttipo de excepcion desconocido: {tipo}")
PY
)

  # A54 · LO DECIDIBLE VA ANTES QUE LO QUE FALTA, TAMBIEN CUANDO LO QUE FALTA ES UN PAYLOAD.
  # Hasta COLA 125 estas cuatro lineas APAGABAN EL CHECK ENTERO aqui mismo, antes de mirar
  # `partes`: bastaba con que UNA de las tres rutas con excepcion no se pudiera leer en esa
  # corrida. Y en la misma corrida el panel podia estar pidiendo SUELTA otra ruta de FOTO SIN
  # NINGUNA EXCUSA -un hecho sobre el panel que no necesita ese payload para nada-: lo que
  # faltaba de una se comia la condena de otra.
  # Ahora lo que no se pudo leer NO excusa y NO condena: cae en el TERCER CUBO con su nombre
  # -eso lo hace el propio bloque de python, que emite `NOVER` por ruta- y aqui solo queda el
  # aviso GLOBAL, que se dice en la linea y, si no hay nada que condenar, deja NO MEDIDO.
  local sin_medir excusadas="" anuladas="" huerfanas="" noverificables="" partes="" n_partes=0 rutas_partes=0 razon motivo
  sin_medir=$(printf '%s\n' "$VEREDICTOS" | grep '^NOMED' | cut -f2- | tr '\n' ' ')
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

  P_DET=""
  [ -n "${excusadas// /}" ] && P_DET="$P_DET · EXCUSADAS Y REVERIFICADAS EN ESTA CORRIDA:$excusadas"
  [ -n "${noverificables// /}" ] && P_DET="$P_DET · EXCUSAS QUE NO SE HAN PODIDO VERIFICAR (no excusan, y no condenan al panel):$noverificables"
  [ -n "${sin_medir// /}" ] && P_DET="$P_DET · LO QUE NO SE PUDO LEER EN ESTA CORRIDA: $sin_medir"
  [ -n "${huerfanas// /}" ] && P_DET="$P_DET · EXCEPCIONES HUERFANAS (el panel ya no las pide, sobran): $huerfanas"
  P_DET=${P_DET# · }

  # EL ORDEN IMPORTA. Si en esta corrida hay una ruta suelta SIN excusa, eso es un hecho sobre el
  # panel y manda: el veredicto es esa condena, y las no verificables van nombradas en la linea.
  # Solo cuando no hay nada que condenar, una excusa sin verificar deja el check SIN MEDIDA.
  if [ "$rutas_partes" -gt 0 ]; then
    P_RC=1
    P_LINEA="REFORMA A MEDIAS: $P_NOMBRE pide el sobre $n_sobre veces Y ADEMAS sigue pidiendo $n_partes veces $rutas_partes de las $N_FOTO rutas de FOTO SIN EXCUSA VIVA. Las dos cosas a la vez cuestan mas que hoy y el sobre no gobierna la edad de lo que se pinta ·$partes"
    return 0
  fi
  if [ -n "${noverificables// /}" ] || [ -n "${sin_medir// /}" ]; then
    local _n
    _n=$(printf '%s\n' "$noverificables" | grep -o ' · ' | grep -c .)
    P_RC=2
    P_LINEA="NO MEDIDO: ninguna ruta de FOTO de $P_NOMBRE queda sin excusa, pero $_n excusa(s) NO SE HAN PODIDO VERIFICAR en esta corrida, asi que este check no ha medido si esas peticiones sueltas estan justificadas. Decirlo en la linea y ademas dar VERDE seria contar como medida lo que no se midio, que es justo lo que esta red existe para no hacer"
    return 0
  fi
  P_RC=0
  P_LINEA="$P_NOMBRE pide el sobre $n_sobre veces y CERO de las $N_FOTO rutas de FOTO sin excusa viva: lo que se pinta como foto sale de una sola respuesta con un solo generated_at. Cada excusa se ha vuelto a comprobar contra los payloads de ESTA corrida y dice contra que"
  return 0
}
juzga_panel

# --- 4 · EL VEREDICTO, CON LAS DOS PANTALLAS DELANTE ---------------------------------------
# Manda lo que condena; despues lo que no se pudo juzgar entero; despues lo que cumple; y lo que
# nadie miro se dice al final. LO NO ATRIBUIDO SE NOMBRA Y NO SE CARGA A NINGUNA: no condena a
# nadie y tampoco cuenta como visto. La primera linea lleva el veredicto, las pantallas y la
# cuenta de lo no atribuido, porque es la unica que el marcador cita.
rojos=""; nomeds=""; verdes=""; vacias=""
cubo() {  # cubo <rc de la pantalla> <su linea>
  case "$1" in
    1) rojos="$rojos · $2" ;;
    2) nomeds="$nomeds · $2" ;;
    0) verdes="$verdes · $2" ;;
    *) vacias="$vacias · $2" ;;
  esac
}
cubo "${P_RC:-3}" "$P_LINEA"
cubo "${M_RC:-3}" "$M_LINEA"
SIN_DICHO=""
[ "${N_SIN:-0}" -gt 0 ] && SIN_DICHO=" · $N_SIN peticion(es) SIN ATRIBUIR a ninguna pantalla, que no se cargan a ninguna (abajo, con su motivo)"

if [ -n "$rojos$nomeds$verdes" ]; then
  primera="$rojos$nomeds$verdes$vacias"
  primera="${primera# · }$SIN_DICHO · $COLA0$MARCA"
elif [ "${N_API:-0}" -lt 1 ] && [ "${N_CARGAS:-0}" -lt 1 ]; then
  primera="NO MEDIDO: no consta que nadie mirara ninguna pantalla en las ultimas ${VENTANA_H} h -0 peticiones de navegador, filtrando por agente y descartando la IP del arnes-. En una ventana sin visitas, «cero peticiones al sobre» sale IGUAL que si el panel lo pidiera en cada carga, y solo uno de los dos es un defecto.$MARCA"
elif [ "${N_API:-0}" -lt 1 ]; then
  primera="NO MEDIDO: ${N_CARGAS} carga(s) de pantalla en las ultimas ${VENTANA_H} h y CERO peticiones /api de navegador: una pantalla que no pide nada no se puede juzgar contra lo que tiene que pedir · $COLA0$MARCA"
else
  primera="NO MEDIDO: hubo ${N_API:-0} peticiones de navegador en las ultimas ${VENTANA_H} h y NINGUNA se pudo atribuir a una pantalla, asi que no se juzga a ninguna$SIN_DICHO · $COLA0$MARCA"
fi
echo "$primera"
[ -n "${P_DET:-}" ] && echo "  panel viejo · $P_DET"
[ -n "${M_DET:-}" ] && echo "  mesa · $M_DET"
[ "${N_SIN:-0}" -gt 0 ] && echo "  SIN ATRIBUIR$SIN_DET"
echo "  puerta · ${PUERTA:-sin linea de tiempo}"

if [ -n "$rojos" ]; then exit 1; fi
if [ -n "$nomeds" ] || [ -z "$verdes" ]; then exit 2; fi
exit 0
