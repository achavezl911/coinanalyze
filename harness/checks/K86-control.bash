#!/bin/bash
# K86-control · LOS DOS BRAZOS DEL GUARDIA, INDUCIDOS FUERA DE LINEA.
#
# Un guardia que caza todo esta tan roto como el que no caza nada, y el brazo negativo
# casi nadie lo prueba. Aqui se prueban los dos, con su rc, y ademas la REGRESION de la
# trampa que casi hunde a la version anterior: la base truncada por el transporte contra
# la base completa tienen que dar el MISMO veredicto y el MISMO recuento.
#
# NO LLEVA .sh A PROPOSITO. bin/verify globea checks/*.sh y su marcador es del operador;
# el sujeto de este fichero es EL ARBOL, no produccion, asi que no debe entrar en esa
# cuenta. Mismo patron que K31-cubos.py. Corre sin red, sin ssh y sin base de datos.
#
# LOS FIXTURES SE GENERAN, NO SE GUARDAN, y me aparto aqui del precedente de K52
# (/home/devops/k52ind, ficheros estaticos) con una razon medida: el sujeto de K86 es una
# ventana movil de 30 dias. Un fixture con fechas absolutas sale del arco a los 30 dias y
# a partir de ahi el control PASA sin ejercitar nada -0 lineas dentro del arco, y el brazo
# que creias probando esta apagado-. Ademas viven en el repo, o sea que el PR los revisa.
# El precio es que el generador es codigo que tambien puede estar mal; lo pago porque un
# control que caduca en silencio es la misma enfermedad que este check persigue.

set -uo pipefail
B=/srv/coinanalyze/harness
CHK="$(cd "$(dirname "$0")" && pwd)/K86-la-excepcion-que-sabe-que-hora-es.sh"
[ -r "$CHK" ] || { echo "no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
# K86_CONTROL_GUARDA=1 deja los fixtures en pie para mirarlos a mano. Por defecto se
# borran: 360 KB por corrida en /tmp es basura que nadie recoge.
[ "${K86_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
hoy=$(date -u +%Y-%m-%d)
fallos=0

fecha() { date -u -d "$hoy -$1 days" +%F; }

# --- GENERADORES ------------------------------------------------------------------
# Formato exacto de journalctl --utc -o short-iso --no-hostname:
#   2026-09-03T13:30:04+00:00 coinalyze-ingest[3312]: <mensaje>
# El relleno va cada 10 minutos: con RADIO=5 eso garantiza que CUALQUIER minuto del dia
# tenga una linea a <=5 min, o sea que el dia es elegible para el minuto que sea. Asi el
# brazo de elegibilidad no contamina el veredicto que se esta probando.
relleno() {  # $1 = fecha
  awk -v D="$1" 'BEGIN{
    for (m = 0; m < 1440; m += 10)
      printf "%sT%02d:%02d:00+00:00 coinalyze-ingest[3312]: ingest tick ok symbols=210 lag=0.8s\n", D, int(m/60), m%60
  }'
}

# Bloque de traceback REAL, de cuatro lineas, del que solo la ultima debe parsear. Las
# otras tres son ruido que el parser tiene que descartar: la linea del raise lleva la
# palabra ValueError y NO puede contar.
traza() {  # $1 = fecha   $2 = HH:MM   $3 = segundos
  local d="$1" t="$2" s="$3"
  printf '%sT%s:%s+00:00 coinalyze-ingest[3312]: Traceback (most recent call last):\n' "$d" "$t" "$s"
  printf '%sT%s:%s+00:00 coinalyze-ingest[3312]:   File "/opt/coinalyze/current/app/data_gaps.py", line 77, in _window\n' "$d" "$t" "$s"
  printf '%sT%s:%s+00:00 coinalyze-ingest[3312]:     raise ValueError("gap window must satisfy start end")\n' "$d" "$t" "$s"
  printf '%sT%s:%s+00:00 coinalyze-ingest[3312]: ValueError: gap window must satisfy start end\n' "$d" "$t" "$s"
}

# La rafaga de DNS del 2026-08-14 medida en 140 por el operador: 47 eventos entre las
# 17:38Z y las 18:51Z -73 minutos- en tres boots, un solo dia. Es EL confundidor, y por eso
# va en los DOS fixtures: 47 sucesos en 1 dia contra 48 sucesos en 24 dias. Un check que
# contara sucesos daria ganadora a esta tarde, que ademas ya esta atendida, y dejaria el
# bug estructural en segundo lugar. Los 47 caen en 47 minutos DISTINTOS -m = int(i*73/47),
# estrictamente creciente-, asi que ningun par de la rafaga pasa de 1 dia.
rafaga() {  # $1 = fecha
  awk -v D="$1" 'BEGIN{
    for (i = 0; i < 47; i++) {
      m = int(i * 73 / 47)
      h = 17 + int((38 + m) / 60); mi = (38 + m) % 60
      if (i % 3 == 2)
        printf "%sT%02d:%02d:%02d+00:00 coinalyze-ingest[3312]: httpx.ConnectError: [Errno -3] Temporary failure in name resolution\n", D, h, mi, i % 60
      else
        printf "%sT%02d:%02d:%02d+00:00 coinalyze-ingest[3312]: CoinalyzeError: feed binance_futures failed: connection reset by peer\n", D, h, mi, i % 60
    }
  }'
}

# POSITIVO · el par SI recurre. Copia la forma real medida en 140: dos escrituras por dia
# a las 13:30:04 y 13:30:18, 24 dias.
#   offsets  1..24  relleno + el par        -> 24 dias con el par
#   offsets 25..27  relleno SOLO            -> elegibles SIN el par: los pre-bug
#   offsets  0,28..30  mudos                -> no elegibles, tienen que salir NOMBRADOS
# Esperado: ROJO, ValueError a las 13:30Z, 24 de 27 elegibles, 4 no elegibles.
# La distancia 27-24 = 3 es la que en produccion vale 28-24 = 4 y fecha el bug al 08-10.
fx_positivo() {
  local f="$1" k
  : > "$f"
  for k in $(seq 1 27); do relleno "$(fecha "$k")" >> "$f"; done
  for k in $(seq 1 24); do
    traza "$(fecha "$k")" 13:30 04 >> "$f"
    traza "$(fecha "$k")" 13:30 18 >> "$f"
  done
  rafaga "$(fecha 21)" >> "$f"
}

# NEGATIVO · MISMO VOLUMEN de excepciones -48 ValueError + 47 de rafaga = 95 lineas en
# los dos-, repartidas por horas distintas: el minuto cambia cada dia con paso 61, que es
# coprimo con 1440, asi que los 24 minutos son distintos y ningun par pasa de 1 dia.
# Esperado: VERDE. Este es el brazo que casi nadie prueba.
fx_negativo() {
  local f="$1" k m hh mm
  : > "$f"
  for k in $(seq 1 27); do relleno "$(fecha "$k")" >> "$f"; done
  for k in $(seq 1 24); do
    m=$(( (k * 61) % 1440 )); hh=$(printf '%02d' $((m / 60))); mm=$(printf '%02d' $((m % 60)))
    traza "$(fecha "$k")" "$hh:$mm" 04 >> "$f"
    traza "$(fecha "$k")" "$hh:$mm" 18 >> "$f"
  done
  rafaga "$(fecha 21)" >> "$f"
}

# --- LOS TRES FIXTURES DE LA CADUCIDAD, anadidos el 2026-09-06 -----------------------
# El check tenia UN eje -¿recurre?- y por eso podia publicar un rojo caduco y despues un
# verde no ganado, los dos por el paso del tiempo. Estos tres ejercitan el eje nuevo.

# RECAIDA · EL CASO QUE NO EXISTIA Y QUE ES EL QUE IMPORTA. El par recurrio 11 dias
# (offsets 20..30), se callo 18 dias (2..19) y VUELVE ayer (offset 1). Tiene que salir ROJO
# EL PRIMER DIA: la recurrencia ya esta en la ventana, asi que no hay que reacumular nada.
# Antes, con el check ya en rojo, la vuelta del bug no cambiaba ni una letra de la salida.
fx_recaida() {
  local f="$1" k
  : > "$f"
  for k in $(seq 1 30); do relleno "$(fecha "$k")" >> "$f"; done
  for k in $(seq 20 30) 1; do
    traza "$(fecha "$k")" 13:30 04 >> "$f"
    traza "$(fecha "$k")" 13:30 18 >> "$f"
  done
  rafaga "$(fecha 21)" >> "$f"
}

# EL CONTRASTE DE LA RECAIDA · el MISMO dia reciente con el par, pero SIN la historia. Aqui
# el par no recurre (1 dia < 3) y tiene que salir VERDE. Sin este brazo, C7 no probaria que
# el rojo viene del cruce historia+recencia: podria venir de la aparicion sola.
fx_recaida_sin_historia() {
  local f="$1" k
  : > "$f"
  for k in $(seq 1 30); do relleno "$(fecha "$k")" >> "$f"; done
  traza "$(fecha 1)" 13:30 04 >> "$f"
  traza "$(fecha 1)" 13:30 18 >> "$f"
  rafaga "$(fecha 21)" >> "$f"
}

# REMITIDO · el par recurrio 21 dias (offsets 10..30) y lleva 9 ocasiones elegibles limpias
# (1..9). 9 >= K=7, luego VERDE Y GANADO. Es el unico verde que este check puede firmar.
# CALLADO · el mismo, con solo 3 limpias (el corte en 4..30). 3 < 7, luego NOMED.
# El segundo argumento es cuantos dias limpios se dejan detras.
fx_remitido() {
  local f="$1" limpias="$2" k
  : > "$f"
  for k in $(seq 1 30); do relleno "$(fecha "$k")" >> "$f"; done
  for k in $(seq $((limpias + 1)) 30); do
    traza "$(fecha "$k")" 13:30 04 >> "$f"
    traza "$(fecha "$k")" 13:30 18 >> "$f"
  done
  rafaga "$(fecha 21)" >> "$f"
}

# RUIDOSO · 500 pares distintos en un solo dia. Ninguno recurre, o sea VERDE, pero sirve
# para lo otro: con K86_TOP=2000 la salida agregada pasa de 13 KB y el corte de 8 KB la
# parte. El check tiene que decir NO MEDIDO, no inventarse un veredicto.
fx_ruidoso() {
  local f="$1"
  relleno "$(fecha 1)" > "$f"
  awk -v D="$(fecha 1)" 'BEGIN{
    for (i = 0; i < 500; i++) {
      m = i * 2
      printf "%sT%02d:%02d:11+00:00 coinalyze-ingest[3312]: NoiseError: transitorio %d\n", D, int(m/60), m%60, i
    }
  }' >> "$f"
}

# --- ARNES DE ASERCION -------------------------------------------------------------
corre() {  # imprime rc en la primera linea y la salida detras
  local fx="$1"; shift
  local out rc
  out=$(env K86_FIXTURE="$fx" "$@" bash "$CHK" 2>&1); rc=$?
  printf '%s\n' "$rc"
  printf '%s\n' "$out"
}

juzga() {  # $1 = etiqueta   $2 = rc esperado   $3 = rc real   $4 = patron   $5 = salida
  local est
  if [ "$3" = "$2" ] && printf '%s\n' "$5" | grep -qF -- "$4"; then est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
  printf '%-46s rc=%s (esperado %s)  %-5s  %s\n' "$1" "$3" "$2" "$est" "$(printf '%s\n' "$5" | grep -E '^(ROJO|VERDE|NO MEDIDO)' | head -1 | cut -c1-72)"
  [ "$est" = FALLA ] && printf '   esperaba encontrar: %s\n' "$4"
  return 0
}

echo "K86 · controles fuera de linea   ·   $(date -u +%FT%TZ)   ·   fixtures en $DIR"
echo "check: $CHK"
echo

# --- C0 · EL CONSTRUCTOR, ESTATICO -------------------------------------------------
# Los dos programas de awk viajan DENTRO de la orden que se le pasa a bin/prod, y bin/prod
# DENIEGA cualquier orden que lleve '>' -lo lee como redireccion a fichero-. Una
# comparacion de awk escrita al derecho ("if (f > R)") mete una '>' que no se ve, y la
# orden entera se cae con DENEGADO en produccion mientras los fixtures siguen pasando,
# porque el camino del fixture no usa bin/prod. Es una trampa que SOLO se dispara en 140.
# Se comprueba aqui, en estatico, que es donde se puede.
c0=PASA
cuerpo=$(sed -n "/^AWK_PARES='\$/,/^}'\$/p;/^AWK_ELEG='\$/,/^}'\$/p" "$CHK" | grep -vE "^(AWK_[A-Z]+='|\}')\$")
tuberia=$(grep -h 'canal "' "$CHK")
[ -n "$cuerpo" ] && [ -n "$tuberia" ] || { c0=FALLA; echo "   C0: no pude extraer los programas de awk ni las tuberias del check"; }
# La orden ENTERA que viaja a 140 son los cuerpos de awk mas las dos tuberias. Ni una '>'.
printf '%s\n%s\n' "$cuerpo" "$tuberia" | grep -q '[>]' && c0=FALLA
# Y el cuerpo de awk va embebido entre comillas simples: una comilla simple dentro lo
# parte en dos y la orden llega mutilada.
printf '%s\n' "$cuerpo" | grep -q "'" && c0=FALLA
[ "$c0" = FALLA ] && fallos=$((fallos + 1))
printf '%-46s %-18s %-5s  %s\n' "C0 constructor: awk sin '>' ni comilla simple" \
  "$(printf '%s\n' "$cuerpo" | grep -c '') lin awk" "$c0" \
  "bin/prod deniega toda orden con '>'; una comparacion al derecho la mete sin que se vea"

# --- C1 · CONTROL POSITIVO ---------------------------------------------------------
fx_positivo "$DIR/j-positivo.txt"
sal=$(corre "$DIR/j-positivo.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C1 positivo: el par recurre 24 dias" 1 "$rc" \
  "ROJO (VIVO): el par recurre Y aparece en la ULTIMA ocasion elegible" "$out"
# C1a · y la recurrencia sigue publicandose con su denominador: el eje nuevo no se come al viejo.
juzga "C1a positivo: la recurrencia sigue medida" 1 "$rc" \
  "recurrencia: ValueError a las 13:30Z en 24 de 27 dias elegibles (umbral 3)" "$out"
pos_out="$out"

# C1b · y NO se deja ganar por la rafaga. 47 sucesos en 1 dia contra 48 en 24 dias: si el
# check contara sucesos, el ganador seria la rafaga. Esta es la razon de ser del par, asi
# que no basta con ver ROJO: hay que ver que la rafaga ESTA en la tabla, con 1 dia, y
# DEBAJO. Un ROJO con el ganador equivocado es el fallo de la version anterior.
cima=$(printf '%s\n' "$out" | awk '/ dias  [0-9][0-9]:[0-9][0-9]  /{print; exit}')
raf=$(printf '%s\n' "$out" | grep -cE '^ +1 dias  1[78]:[0-9]{2}  (CoinalyzeError|httpx\.ConnectError)' || true)
if [ "$rc" = 1 ] && printf '%s\n' "$cima" | grep -q '24 dias  13:30  ValueError' \
   && [ "${raf:-0}" -ge 1 ] && printf '%s\n' "$out" | grep -q 'pares (minuto,clase) distintos: 48'; then
  est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
printf '%-46s %-18s %-5s  %s\n' "C1b positivo: la rafaga de DNS no gana" "48 pares, $raf de rafaga" "$est" \
  "$(printf '%s' "$cima" | sed 's/  */ /g' | cut -c1-72)"

# C1c · los dias mudos salen NOMBRADOS, no descontados en silencio.
juzga "C1c positivo: nombra los 4 no elegibles" 1 "$rc" \
  "no elegibles, nombrados: $(fecha 30) $(fecha 29) $(fecha 28) $(fecha 0)" "$out"

# --- C2 · CONTROL NEGATIVO ---------------------------------------------------------
fx_negativo "$DIR/j-negativo.txt"
sal=$(corre "$DIR/j-negativo.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C2 negativo: mismo volumen, horas distintas" 0 "$rc" "VERDE (NO RECURRE): ningun par" "$out"

# C2b · y con el MISMO numero de lineas de excepcion que el positivo. Si los dos brazos no
# tienen el mismo volumen, lo que separa VERDE de ROJO podria ser el volumen y no la
# recurrencia, y entonces el control negativo no prueba lo que dice probar.
b_pos=$(printf '%s\n' "$pos_out" | sed -n 's/^base: \([0-9]*\) .*/\1/p')
b_neg=$(printf '%s\n' "$out"     | sed -n 's/^base: \([0-9]*\) .*/\1/p')
if [ "$b_pos" = "$b_neg" ] && [ -n "$b_pos" ]; then est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
printf '%-46s %-18s %-5s  %s\n' "C2b volumen pareado" "pos=$b_pos neg=$b_neg" "$est" \
  "lo que separa los dos brazos es la recurrencia, no el volumen"

# --- C3 · LA REGRESION DE LA TRAMPA 1 ----------------------------------------------
# El fixture positivo son ~380 KB de journal crudo. La version anterior traia eso por
# bin/prod y el corte de 8 KB le dejaba el 2 %. Aqui el veredicto y el recuento tienen que
# ser IDENTICOS con el corte puesto y con TODO=1, porque lo que cruza ya viene agregado.
# Se comparan todas las lineas menos 'arco:' y 'transporte:', que cambian a proposito:
# la primera lleva el segundo actual, la segunda declara el valor de TODO.
crudo_b=$(wc -c < "$DIR/j-positivo.txt")
sal=$(corre "$DIR/j-positivo.txt" TODO=1); rc_todo=$(printf '%s\n' "$sal" | head -1); out_todo=$(printf '%s\n' "$sal" | tail -n +2)
sust() { printf '%s\n' "$1" | grep -vE '^(arco|transporte):'; }
if [ "$rc_todo" = "1" ] && [ "$(sust "$pos_out")" = "$(sust "$out_todo")" ]; then est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
printf '%-46s %-18s %-5s  %s\n' "C3 trampa 1: con corte == con TODO=1" "rc=1 y rc=$rc_todo" "$est" \
  "$crudo_b B de journal crudo; cruzan $(printf '%s\n' "$pos_out" | sed -n 's/^transporte:.*cruzaron \([0-9]*\) B.*/\1/p') B agregados"

# --- C4 · EL GUARDIA DEL CORTE, DISPARADO DE VERDAD --------------------------------
# Con K86_TOP=10 la salida agregada del fixture ruidoso cabe y hay veredicto. Con
# K86_TOP=2000 son 500 pares, la salida pasa de 13 KB, bin/_corta la parte y el check
# tiene que declarar NO MEDIDO. Un check que ante una base recortada emite veredicto es
# la version anterior otra vez.
fx_ruidoso "$DIR/j-ruidoso.txt"
sal=$(corre "$DIR/j-ruidoso.txt" K86_TOP=10); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C4a ruidoso, TOP=10: cabe y juzga" 0 "$rc" "VERDE (NO RECURRE): ningun par" "$out"
juzga "C4b ruidoso, TOP=10: declara lo que oculta" 0 "$rc" "pares (minuto,clase) distintos: 500" "$out"
sal=$(corre "$DIR/j-ruidoso.txt" K86_TOP=2000); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C4c ruidoso, TOP=2000: el corte -> NO MEDIDO" 2 "$rc" \
  "NO MEDIDO: el transporte trunco la salida" "$out"

# --- C5 · LOS BORDES, EN UTC Y EN LA PRIMERA LINEA ---------------------------------
# Criterio (2): el arco que evaluo de verdad, auditable sin releer el codigo.
primera=$(printf '%s\n' "$pos_out" | head -1)
esperado="arco: $(fecha 30)T00:00:00Z"
if printf '%s\n' "$primera" | grep -qF "$esperado" && printf '%s\n' "$primera" | grep -q '31 dias naturales tocados'; then
  est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
printf '%-46s %-18s %-5s  %s\n' "C5 la primera linea imprime el arco en UTC" "" "$est" "$(printf '%s' "$primera" | cut -c1-72)"

# --- C6 · LAS ORDENES REALES CONTRA EL FILTRO REAL DE bin/prod ---------------------
# C0 mira el codigo; esto ejecuta el guardia de verdad. El filtro se EXTRAE de bin/prod en
# vez de copiarse, para que no pueda derivar: si manana bin/prod prohibe un verbo mas, este
# control se entera solo. Se le pasan las DOS ordenes que el check enviaria de verdad,
# sacadas del propio check con K86_ORDEN=1.
# Por que hace falta: el camino del fixture NO pasa por bin/prod, asi que una orden
# denegada saldria de aqui con los diez controles en verde y se caeria solo en 140.
filtro=$(awk '/^case " \$cmd " in$/{f=1} f{print} f && /^esac$/{n++; if (n==2) exit}' "$B/bin/prod")
ordenes=$(env K86_ORDEN=1 bash "$CHK")
n_ord=$(printf '%s\n' "$ordenes" | grep -c 'journalctl -u ')
# Cada orden lleva saltos de linea dentro (el programa de awk), asi que se parten por la
# linea marca, NO por el salto. Se le pasan enteras al filtro, que es como las recibe.
o1=$(printf '%s\n' "$ordenes" | awk '/^# --- ORDEN 2 ---$/{exit} {print}')
o2=$(printf '%s\n' "$ordenes" | awk 'f{print} /^# --- ORDEN 2 ---$/{f=1}')
pasa=0; total=0
for orden in "$o1" "$o2"; do
  [ -n "$orden" ] || continue
  total=$((total + 1))
  ( cmd="$orden"; eval "$filtro" ) >/dev/null 2>&1 && pasa=$((pasa + 1))
done
if [ -n "$filtro" ] && [ "$n_ord" -eq 2 ] && [ "$total" -eq 2 ] && [ "$pasa" -eq 2 ]; then
  est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
printf '%-46s %-18s %-5s  %s\n' "C6 bin/prod no deniega las dos ordenes" "$pasa de $total pasan" "$est" \
  "filtro extraido de bin/prod: $(printf '%s\n' "$filtro" | grep -c '') lineas, no una copia"

# --- C7 · LA RECAIDA ENROJECE EL PRIMER DIA ---------------------------------------
fx_recaida "$DIR/j-recaida.txt"
sal=$(corre "$DIR/j-recaida.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C7 recaida: 11 dias viejos + 1 de ayer -> ROJO" 1 "$rc" \
  "ROJO (VIVO): el par recurre Y aparece en la ULTIMA ocasion elegible" "$out"
# C7b · Y NO tuvo que reacumular el umbral: los 18 dias de silencio de en medio se cuentan y
# se dicen, pero no impiden el rojo. Si el check exigiera recencia CONSECUTIVA, aqui saldria
# verde y la vuelta del bug pasaria desapercibida.
juzga "C7b recaida: el silencio de en medio se declara" 1 "$rc" \
  "en medio sin el par" "$out"

# C7c · EL CONTRASTE. Mismo dia reciente con el par, sin historia: VERDE. Sin este caso, C7
# no distinguiria "vuelve un bug estructural" de "hoy fallo algo una vez".
fx_recaida_sin_historia "$DIR/j-recaida-sola.txt"
sal=$(corre "$DIR/j-recaida-sola.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C7c una aparicion SIN historia no es rojo" 0 "$rc" "VERDE (NO RECURRE)" "$out"

# --- C8 · REMITIDO Y PROBADO · el unico verde que este check puede firmar ----------
fx_remitido "$DIR/j-remitido.txt" 9
sal=$(corre "$DIR/j-remitido.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C8 remitido: 21 dias y 9 limpias -> VERDE" 0 "$rc" "VERDE (REMITIDO Y PROBADO)" "$out"
# C8b · y NO afirma un arreglo que no puede ver. Un check que dijera "arreglado" estaria
# afirmando algo que no esta en su alcance: solo ve el journal.
juzga "C8b remitido: no afirma que nadie lo arreglara" 0 "$rc" \
  "ESTO NO DICE QUE NADIE LO ARREGLARA" "$out"

# --- C9 · CALLADO SIN PROBAR · el estado que antes se pintaba de verde -------------
# ES EL CASO DE PRODUCCION DE HOY: el par lleva 2 dias sin aparecer y el check anterior
# habria seguido rojo hasta que la ventana lo olvidara, para despues ponerse verde solo.
fx_remitido "$DIR/j-callado.txt" 3
sal=$(corre "$DIR/j-callado.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C9 callado: 3 limpias de 7 -> NOMED" 2 "$rc" "NO MEDIDO (CALLADO SIN PROBAR)" "$out"
juzga "C9b callado: dice cuantas faltan" 2 "$rc" "hacen falta 7" "$out"
# C9c · LA FRONTERA, que es donde un umbral se equivoca. Con 7 limpias exactas: VERDE.
fx_remitido "$DIR/j-frontera.txt" 7
sal=$(corre "$DIR/j-frontera.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C9c frontera: 7 limpias exactas -> VERDE" 0 "$rc" "VERDE (REMITIDO Y PROBADO)" "$out"
fx_remitido "$DIR/j-frontera6.txt" 6
sal=$(corre "$DIR/j-frontera6.txt"); rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C9d frontera: 6 limpias -> NOMED" 2 "$rc" "NO MEDIDO (CALLADO SIN PROBAR)" "$out"

# --- C10 · H2 · LAS DOS PUNTAS, SEPARADAS -----------------------------------------
# La prosa vieja decia que "la distancia entre los dias elegibles y los dias con el par ES la
# edad del fallo". Solo vale si los dias sin el par estan al PRINCIPIO. En el fixture de C9
# hay 6 delante y 3 detras: si se sumaran, el check fecharia el nacimiento 3 dias mas atras
# de lo que toca. Se exige que los nombre por separado.
sal=$(corre "$DIR/j-callado.txt"); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C10 H2: las dos puntas se nombran aparte" 2 "$(printf '%s\n' "$sal" | head -1)" \
  "3 DESPUES del ultimo" "$out"
juzga "C10b H2: y no fechan el nacimiento" 2 "$(printf '%s\n' "$sal" | head -1)" \
  "no fechan nada del nacimiento" "$out"

echo
if [ "$fallos" -eq 0 ]; then
  echo "23 de 23 controles PASAN. Los dos brazos juzgan, el corte no decide el veredicto,"
  echo "y las ordenes que viajan a 140 sobreviven al filtro de bin/prod."
  exit 0
fi
echo "$fallos controles FALLAN."
exit 1
