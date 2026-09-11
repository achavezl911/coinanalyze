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
#   4 PIDE EL SOBRE Y CERO PARTES .......... VERDE.
#   5 NO PIDE EL SOBRE ..................... ROJO. Es el estado de hoy.
#   6 PIDE EL SOBRE Y SIGUE PIDIENDO PARTES  ROJO, y es OTRO rojo: en el 5 no ha empezado
#     nadie; en el 6 alguien empezo y dejo las dos cosas puestas —que cuesta MAS que hoy—.
#     Las dos condiciones van juntas a proposito: pedir la foto sin dejar de pedir las partes
#     cumpliria un criterio de una sola mitad siendo falso.
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
LOG_CMD="
  horas=\$(for i in \$(seq 0 $((VENTANA_H-1))); do date -d \"-\$i hours\" +%d/%b/%Y:%H; done | tr '\n' '|' | sed 's/|\$//')
  cat /var/log/nginx/access.log.1 /var/log/nginx/access.log 2>/dev/null \
    | grep -a Mozilla | grep -av '^$ARNES_IP ' \
    | awk -v H=\"\$horas\" 'BEGIN{n=split(H,a,\"|\")} { for(i=1;i<=n;i++) if (index(\$4,a[i])==2) { print; break } }' \
    | awk '{ visitas++; p=\$7; sub(/\?.*/, \"\", p); if (p ~ /^\/api\//) c[p]++ } END { printf \"VISITAS %d\n\", visitas+0; for (i in c) printf \"%d %s\n\", c[i], i }'"

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
n_sobre=$(printf '%s\n' "$pedidas" | awk -v S="$SOBRE" '$2==S {s+=$1} END {print s+0}')

partes=""; n_partes=0; rutas_partes=0
while read -r r; do
  [ -n "$r" ] || continue
  n=$(printf '%s\n' "$pedidas" | awk -v R="$r" '$2==R {s+=$1} END {print s+0}')
  if [ "$n" -gt 0 ]; then
    partes="$partes $r($n)"
    n_partes=$((n_partes + n))
    rutas_partes=$((rutas_partes + 1))
  fi
done <<EOF
$FOTO
EOF

COLA="ventana ${VENTANA_H} h · $VISITAS peticiones de navegador · $N_FOTO rutas en la familia FOTO$MARCA"

if [ "$n_sobre" -lt 1 ]; then
  echo "el panel NO pide el sobre: 0 peticiones a $SOBRE, y $n_partes a $rutas_partes de las" \
       "$N_FOTO rutas de FOTO, que es reconstruir la foto en vez de consumirla ·$partes · $COLA"
  exit 1
fi
if [ "$rutas_partes" -gt 0 ]; then
  echo "REFORMA A MEDIAS: el panel pide el sobre $n_sobre veces Y ADEMAS sigue pidiendo" \
       "$n_partes veces $rutas_partes de las $N_FOTO rutas de FOTO. Las dos cosas a la vez" \
       "cuestan mas que hoy y el sobre no gobierna la edad de lo que se pinta ·$partes · $COLA"
  exit 1
fi
echo "el panel pide el sobre $n_sobre veces y CERO de las $N_FOTO rutas de FOTO: lo que se" \
     "pinta como foto sale de una sola respuesta con un solo generated_at · $COLA"
exit 0
