#!/bin/bash
# K86 · LA EXCEPCION QUE SABE QUE HORA ES
#
# SUJETO   el par (minuto del dia UTC, clase de excepcion) en el journal de una unidad.
#          NO el conteo de excepciones.
#
# DOS PREGUNTAS, NO UNA. Hasta el 2026-09-06 este check solo contestaba la primera, y por eso
# podia publicar un ROJO CADUCO: el par dejo de aparecer el 09-05 y el check habria seguido
# rojo hasta el ~10-03 -cuando el ultimo dia con el par saliera de la ventana de 30- para
# despues ponerse VERDE SOLO, por el paso del tiempo y sin que nadie arreglara nada.
#
#   1 ¿RECURRE?     sobre los 30 dias enteros. Es lo que separa un bug estructural de una
#                   averia de una tarde. NO SE TOCA: es el poder de discriminacion del check.
#   2 ¿SIGUE VIVO?  sobre las ocasiones RECIENTES. Eje NUEVO, no un estrechamiento del viejo.
#
# ROJO   VIVO · el par recurre Y aparece en la ultima ocasion elegible.
# VERDE  o no recurre, o REMITIDO Y PROBADO: no aparece desde hace >= K ocasiones elegibles.
# NOMED  CALLADO SIN PROBAR · no aparece, pero las ocasiones limpias son menos de K, asi que
#        el silencio no esta probado. Tambien si el canal no responde, si no hay dias
#        elegibles, o si el TRANSPORTE trunco la salida: un veredicto sobre una base
#        recortada no es un veredicto.
#
# LA RECAIDA ENROJECE EL PRIMER DIA, que es lo que antes no pasaba. La recurrencia ya esta
# demostrada por los 30 dias de historia, asi que UNA SOLA aparicion reciente basta para
# volver a VIVO: no hay que reacumular el umbral. Antes, con el check ya en rojo, que el bug
# volviera manana no cambiaba ni una letra de la salida.
#
# DE DONDE SALE K, y no sale del color que produce:
#   p_lo  cota inferior al 95 % de la tasa historica por ocasion. Si el par aparecio en TODAS
#         las ocasiones activas (v de v), p_lo = 0.05^(1/v) -la regla de tres-; si no,
#         p_lo = v/activas, que es la estimacion puntual y se dice que lo es.
#   K     ocasiones limpias necesarias para descartar al 95 % que la tasa siga siendo esa:
#         K = ceil(ln 0.05 / ln(1 - p_lo)),  con un SUELO de 7.
#   EL SUELO NO ES UN AJUSTE DE VENTANA y solo puede convertir un VERDE en NOMED, nunca al
#   reves: con menos de 7 ocasiones independientes no se distingue un arreglo de una racha.
#   Con una tasa del 100 % siete ocasiones limpias dejan la coincidencia por debajo de 1 en
#   10^6; con una del 33 %, por debajo del 5 %. Es una constante del fichero A PROPOSITO:
#   si fuera K86_SUELO seria exactamente el ajuste barato que este check existe para no tener.
#
# ELEGIBLE un dia D es elegible PARA UN MINUTO HH:MM si la unidad emitio al menos una
#          linea de journal -de lo que fuera- en [HH:MM-R, HH:MM+R] de ese dia.
#          Instrumento EXTERNO al sujeto: cuenta lineas cualesquiera, no excepciones.
#
# Por que el sujeto es el par y no el conteo, con las cifras del operador (140,
# 2026-09-04): el 2026-08-14 entre 17:38Z y 18:51Z hubo ~47 eventos de red y DNS en tres
# boots. Setenta y tres minutos de una averia ya atendida producen TANTOS eventos como
# tres semanas de bug estructural (46, dos por dia). Un check que cuente eventos pone la
# tarde de DNS por delante del bug. Lo que separa a las dos poblaciones es la RECURRENCIA
# del par (minuto del reloj, clase): 1 dia contra 24.
#
# ---------------------------------------------------------------------------------
# LAS DOS COSAS QUE ESTA VERSION ARREGLA, medidas por el operador sobre la version
# anterior de este script (sha256 c5c273a4f49f95a3) corrida contra 140 el 2026-09-04.
#
# TRAMPA 1 · EL CORTE DE 8 KB DECIDIA EL VEREDICTO.
#   La version anterior traia el journal CRUDO y agregaba en 143. bin/_corta corta a
#   MAX_BYTES=8000, asi que de la base solo cruzaba el 39 %:
#       sin TODO=1:   84 lineas /  8081 bytes      <-- lo que veia el check
#       con TODO=1:  216 lineas / 20951 bytes      <-- lo que hay
#   Y el recorte no es aleatorio: se queda con las lineas MAS VIEJAS que caben. El check
#   decia "5 de 28 dias" (08-10..08-14, justo las primeras) en vez de "24 de 28".
#   Salio ROJO POR SUERTE: dentro de ese 39 % el par (13:30, ValueError) seguia siendo el
#   mas frecuente y llegaba a 5 >= 3. Si la rafaga de DNS del 08-14 -47 eventos en 73
#   minutos- hubiera llenado los 8 KB primero, el par ganador habria sido otro y el check
#   habria dicho VERDE sobre un sistema roto. Es justo el modo de fallo que existe para
#   evitar.
#   ARREGLO, y no es poner TODO=1: poner TODO=1 deja la correccion colgando de que la
#   salida no crezca, o sea deja el veredicto atado al transporte. LA AGREGACION SE HACE
#   EN 140. Lo que cruza es UNA LINEA POR PAR (minuto,clase), no una por evento, mas
#   cuatro cabeceras: 14 lineas y ~2.4 KB en el peor caso, contra un techo de 8000. La
#   base -las 216 lineas- se CUENTA en 140 y cruza como un numero.
#   Y por si algun dia creciera igual, :guardia() declara NOMED en cuanto ve la marca
#   [CORTADO:. Cinturon y tirantes: el cinturon es que no quepa, los tirantes que se note.
#
# TRAMPA 2 · --since=<fecha> SE PARSEABA EN LA HORA LOCAL DE 140.
#   Una fecha desnuda la interpreta journalctl en la zona de la maquina, y 140 esta en
#   America/Mexico_City (-0600). Medido por el operador:
#       --since=2026-08-05     -> primera linea 2026-08-05T06:00:26+00:00   (6 h tarde)
#       --since=@1785888000    -> primera linea 2026-08-05T00:00:19+00:00   (correcta)
#   El arco no eran 30 dias sino 29.75, con el dia mas viejo PARTIDO, y eso ensuciaba el
#   denominador de elegibles en silencio. Hoy es inocuo porque 13:30Z cae despues de las
#   06:00Z; con un minuto recurrente a las 03:00Z el dia mas viejo desaparecia sin que
#   nada lo dijera.
#   ARREGLO: la ventana va en EPOCA y anclada a medianoche UTC, y el check IMPRIME sus
#   propios bordes en UTC en la primera linea. Se audita sin releer el codigo.
#
# ---------------------------------------------------------------------------------
# COMO LEER SU SALIDA · el check fecha el nacimiento del fallo sin que nadie se lo diga.
#   Dice "24 de 28 dias elegibles" y no "28 de 28". Los 4 elegibles que NO fallan son los
#   ANTERIORES al bug: app/data_gaps.py nacio en 91111f6 (2026-08-09, PR #9) y es el unico
#   commit que introduce "must satisfy start < end". El primer minuto perdido es el primer
#   cierre de sesion despues de ese despliegue -2026-08-10, confirmado por el operador
#   contra metrics_snapshot: 08-05/06/08/09 traen min_apertura=3, desde el 08-10 sale 0-.
#   O sea: la distancia entre los dias elegibles y los dias con el par ES la edad del
#   fallo. Un salto de esa distancia hacia arriba dice "empezo hoy".
#
# LO QUE NO CIERRA, dicho para que no se lea como si cerrara:
#   1. LA FOTO PERDIDA SIN EXCEPCION. Si la fila falta por un return temprano o un error
#      tragado, no hay nada que agrupar y esto sale VERDE. Eso lo ve una consulta a
#      metrics_snapshot, que hoy no es un check.
#   2. LA UNIDAD MUDA. Sin lineas no hay elegibles y el check se calla, justo cuando el
#      servicio esta mas roto. Por eso NOMBRA los dias no elegibles en vez de descontarlos.
#   3. LA RETENCION del journal. "Desde que existe el despliegue" no se contesta por aqui.
#
# CONTROLES: harness/checks/K86-control.bash (positivo, negativo, y la regresion de la
# trampa 1). No lleva .sh a proposito: bin/verify globea *.sh y su sujeto es el ARBOL,
# no produccion. Mismo patron que K31-cubos.py.

set -uo pipefail
B=/srv/coinanalyze/harness
. "$B/env"

UNIDAD=${K86_UNIDAD:-coinalyze-ingest}
DIAS=${K86_DIAS:-30}
MINIMO=${K86_DIAS_MINIMOS:-3}
RADIO=${K86_RADIO_MIN:-5}
TOP=${K86_TOP:-10}

# --- LA VENTANA, EN EPOCA Y ANCLADA A MEDIANOCHE UTC -------------------------------
# T0 = medianoche UTC de hace DIAS dias. T1 = ahora. El arco es DIAS dias completos mas
# lo que va de hoy, o sea DIAS+1 dias naturales tocados, y el ultimo entra PARTIDO por
# fuerza. Se dice, no se disimula.
hoy=$(date -u +%Y-%m-%d)
T0=$(date -u -d "$hoy -$DIAS days" +%s) || { echo "NO MEDIDO: date -u -d no resolvio el arco"; exit 2; }
T1=$(date -u +%s)
D0=$(date -u -d "@$T0" +%F)
D1=$(date -u -d "@$T1" +%F)
horas_hoy=$(( (T1 - $(date -u -d "$hoy" +%s)) / 360 ))

# --- FUENTE Y CANAL ----------------------------------------------------------------
# La AGREGACION es la misma cadena de texto en los dos casos; lo unico que cambia es de
# donde salen las lineas y por que tuberia vuelven. Y el fixture pasa por bin/_corta
# IGUAL que produccion: un control que esquivara el corte no controlaria nada, que es
# justo lo que la trampa 1 castiga.
if [ -n "${K86_FIXTURE:-}" ]; then
  FUENTE="cat $K86_FIXTURE"
  TRANSPORTE="fixture $K86_FIXTURE -> bin/_corta"
  canal() { sh -c "$1" 2>&1 | "$B/bin/_corta"; }
else
  FUENTE="journalctl -u $UNIDAD --utc -o short-iso --no-hostname --no-pager --since=@$T0 --until=@$T1"
  TRANSPORTE="bin/prod -> ssh 140 -> bin/_corta"
  canal() { "$B/bin/prod" "$1"; }
fi

guardia() {  # $1 = etiqueta   $2 = salida
  case "$2" in
    *"[CORTADO:"*)
      echo "NO MEDIDO: el transporte trunco la salida de $1. No se emite veredicto sobre"
      echo "  una base recortada: eso es exactamente la trampa 1. Sube K86_TOP o baja K86_DIAS."
      exit 2 ;;
    *"DENEGADO por el arnes"*)
      echo "NO MEDIDO: bin/prod denego la orden de $1 -revisa que no lleve '>' ni verbos vetados-"
      exit 2 ;;
  esac
  [ -n "$2" ] || { echo "NO MEDIDO: $1 no devolvio nada (canal a 140 caido, o unidad $UNIDAD inexistente)"; exit 2; }
}

# --- FASE 1 · LOS PARES, AGREGADOS EN 140 ------------------------------------------
# NI UNA SOLA '>' EN ESTE PROGRAMA: bin/prod deniega cualquier orden que la lleve, y una
# comparacion de awk escrita al derecho la mete sin que se vea. Todas van con '<'.
# Tampoco lleva comillas simples: va embebido entre comillas simples.
# Sale, ya ordenable:   0 <letra> <numero>          cabeceras
#                       1 <dias> <HH:MM> <Clase> <lista de dias>
AWK_PARES='
{
  t = $1
  if (length(t) < 19) next
  if (substr(t,11,1) != "T") next
  d = substr(t,1,10)
  if (d < D0) next
  if (D1 < d) next
  L++
  if ($0 ~ /(Error|Exception): /) B++
  c = $3
  if (c !~ /^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception):$/) next
  sub(/:$/, "", c)
  c = substr(c, 1, 40)
  M++
  k = substr(t,12,5) " " c
  kd = k " " d
  if (kd in visto) next
  visto[kd] = 1
  n[k]++
  dl[k] = dl[k] substr(d,6) ","
}
END {
  for (k in n) P++
  printf "0 L %d\n", L+0
  printf "0 B %d\n", B+0
  printf "0 M %d\n", M+0
  printf "0 P %d\n", P+0
  for (k in n) printf "1 %d %s %s\n", n[k], k, dl[k]
}'

# El segundo programa: EL ELEGIBLE, con un instrumento EXTERNO al sujeto. Cuenta lineas
# CUALESQUIERA en +-RADIO minutos del minuto ganador. Cuando la unidad esta muda no hay
# minuto que juzgar, y eso NO es un acierto ni un fallo: es un dia que no entra en el
# denominador y que se NOMBRA mas abajo.
# La distancia es CIRCULAR (1440-f) para que una ventana que cruce medianoche no pierda la
# mitad. La version anterior lo hacia con un grep -E 'T${hh}:(0?${mm})' que ni cubria los
# +-5 min que su propio criterio declaraba, ni sobrevivia a un minuto con cero delante.
AWK_ELEG='
{
  t = $1
  if (length(t) < 19) next
  if (substr(t,11,1) != "T") next
  d = substr(t,1,10)
  if (d < D0) next
  if (D1 < d) next
  f = substr(t,12,2) * 60 + substr(t,15,2) - M0
  if (f < 0) f = -f
  if (1440 - f < f) f = 1440 - f
  if (R < f) next
  e[d] = 1
}
END {
  for (d in e) N++
  printf "0 N %d\n", N+0
  for (d in e) printf "1 %s\n", d
}'

# LAS DOS ORDENES QUE VIAJAN A 140, en una variable y no incrustadas en la llamada, por la
# regla 2 de la seccion 8 del CLAUDE.md: se deja el comando que produjo cada numero.
#   K86_ORDEN=1 bash este-fichero    las imprime y no mide nada.
# Sirve para dos cosas: repetirlas a mano en tres meses, y que K86-control.bash se las pase
# al filtro REAL de bin/prod. Ese filtro deniega toda orden con '>' -la lee como
# redireccion a fichero- y esa trampa solo se dispara en produccion, nunca con un fixture.
# El orden secundario por minuto y clase existe para que el mismo journal de siempre el
# MISMO ganador: "for (k in n)" de mawk no tiene orden, y un check que desempata al azar
# no es reproducible.
ORD_PARES="$FUENTE | awk -v D0=$D0 -v D1=$D1 '$AWK_PARES' | sort -k1,1n -k2,2nr -k3,3 -k4,4 | head -$((4 + TOP))"
ord_eleg() { printf '%s' "$FUENTE | awk -v D0=$D0 -v D1=$D1 -v M0=$1 -v R=$RADIO '$AWK_ELEG' | sort -k1,1n -k2,2 | head -$((DIAS + 6))"; }
# Las ordenes llevan saltos de linea DENTRO -el programa de awk-, asi que van separadas
# por una linea marca y no por el salto: leerlas linea a linea las parte en 49 trozos.
if [ "${K86_ORDEN:-0}" = "1" ]; then
  printf '%s\n' "$ORD_PARES"
  printf '%s\n' '# --- ORDEN 2 ---'
  ord_eleg 810; printf '\n'   # 810 = 13:30, de muestra: lo unico que cambia es ese numero
  exit 0
fi

agg=$(canal "$ORD_PARES")
guardia "la agregacion de pares" "$agg"
bytes_agg=$(printf '%s' "$agg" | wc -c)

cab() { printf '%s\n' "$agg" | awk -v k="$1" '$1=="0" && $2==k {print $3+0; exit}'; }
lineas=$(cab L); base=$(cab B); conpar=$(cab M); pares=$(cab P)
[ -n "${pares:-}" ] || { echo "NO MEDIDO: la agregacion volvio sin cabeceras -formato de journal inesperado-"; exit 2; }

echo "arco: ${D0}T00:00:00Z .. $(date -u -d "@$T1" +%FT%TZ)  ·  $DIAS dias completos + $((horas_hoy/10)).$((horas_hoy%10)) h de hoy  ·  $((DIAS+1)) dias naturales tocados"
echo "transporte: $TRANSPORTE  ·  cruzaron $bytes_agg B de un techo de ${MAX_BYTES:-8000} (TODO=${TODO:-0}). El veredicto se calcula sobre lineas YA AGREGADAS en el origen."
echo "base: $base lineas con '(Error|Exception): ' sobre $lineas lineas de journal de la unidad $UNIDAD; $conpar dieron par (minuto,clase)"

if [ "$pares" -eq 0 ]; then
  echo "NO MEDIDO: $base lineas de excepcion y ningun par reconocible. El formato de la unidad cambio, o la clase no va en el tercer campo."
  exit 2
fi
echo "pares (minuto,clase) distintos: $pares  ·  se muestran los $(printf '%s\n' "$agg" | awk '$1=="1"' | wc -l) mayores (K86_TOP=$TOP)"
printf '%s\n' "$agg" | awk '$1=="1" {printf "  %3d dias  %s  %-28s  %s\n", $2, $3, $4, $5}'

peor=$(printf '%s\n' "$agg" | awk '$1=="1" {print; exit}')
vistos=$(printf '%s' "$peor" | awk '{print $2}')
minuto=$(printf '%s' "$peor" | awk '{print $3}')
clase=$(printf '%s' "$peor" | awk '{print $4}')
M0=$(( 10#${minuto%%:*} * 60 + 10#${minuto##*:} ))

# --- FASE 2 · EL ELEGIBLE, MEDIDO PARA EL MINUTO GANADOR ---------------------------
ele=$(canal "$(ord_eleg "$M0")")
guardia "el instrumento de elegibilidad" "$ele"
declarados=$(printf '%s\n' "$ele" | awk '$1=="0" && $2=="N" {print $3+0; exit}')
lista_ele=$(printf '%s\n' "$ele" | awk '$1=="1" {print $2}')
elegibles=$(printf '%s\n' "$lista_ele" | grep -c . || true)

# GUARDIA DE TRANSPORTE, no de logica: si llegan menos dias de los que el origen dijo
# haber contado, algo se comio lineas por el camino y el denominador seria mentira.
if [ "${declarados:-0}" -ne "${elegibles:-0}" ]; then
  echo "NO MEDIDO: el origen declaro $declarados dias elegibles y llegaron $elegibles. El transporte perdio lineas."
  exit 2
fi
if [ "$elegibles" -eq 0 ]; then
  echo "NO MEDIDO: 0 dias elegibles para ${minuto}Z -la unidad no hablo en +-$RADIO min de esa franja en todo el arco-"
  exit 2
fi
# Un dia con la excepcion es por fuerza un dia con una linea a ese minuto. Si sale al
# reves, el instrumento externo esta roto y no se puede dividir por el.
if [ "$elegibles" -lt "$vistos" ]; then
  echo "NO MEDIDO: $vistos dias con el par sobre $elegibles elegibles. El instrumento de elegibilidad contradice al sujeto; no se emite veredicto."
  exit 2
fi

# Los NO elegibles, nombrados. Se enumera el arco entero y se resta: asi salen tanto los
# dias que la unidad paso muda como los que caen fuera de la retencion del journal.
noele=""; t=$T0
while [ "$t" -le "$T1" ]; do
  d=$(date -u -d "@$t" +%F)
  printf '%s\n' "$lista_ele" | grep -qx "$d" || noele="$noele $d"
  t=$((t + 86400))
done

echo "elegibles para ${minuto}Z (+-$RADIO min, instrumento externo al sujeto): $elegibles de $((DIAS+1)) dias del arco"
echo "no elegibles, nombrados:${noele:- ninguno}"

# --- FASE 3 · LAS DOS PUNTAS, Y LAS OCASIONES LIMPIAS -------------------------------
# H2 · LA FRASE VIEJA ERA FALSA. Decia que "la distancia entre los dias elegibles y los dias
# con el par ES la edad del fallo", y eso solo vale si los dias sin el par estan al PRINCIPIO
# del arco. Cuando el par se calla, aparecen dias sin el par tambien al FINAL, y la resta
# `elegibles - vistos` los metia en el mismo saco: presentaba como "edad del fallo" un numero
# que incluia el silencio. Ahora se parten por su POSICION y se nombran las dos puntas: la de
# delante fecha el NACIMIENTO, la de detras es justo la señal de que se callo.
# SE RECORRE LA LISTA DE ELEGIBLES EN ORDEN, no se comparan cadenas MM-DD. Dos razones, y la
# primera me mordio al escribirlo: `dl[k]` sale de un `for (k in n)` de awk y su orden es el de
# INSERCION, que en produccion es cronologico pero en un fixture no tiene por que serlo; con
# head/tail sobre esa lista el primer y el ultimo dia salian cambiados. La segunda es que
# MM-DD no ordena a traves del cambio de anio: el 12-31 seria "mayor" que el 01-02.
# `lista_ele` viene de `sort` y lleva el anio, asi que aqui el orden es el del calendario.
dias_par=$(printf '%s' "$peor" | awk '{print $5}' | tr ',' '\n' | grep . || true)
antes=0; despues=0; enmedio=0; limpias_lista=""; visto_par=0
primer_par=""; ultimo_par=""
for d in $lista_ele; do
  md=${d#????-}
  if printf '%s\n' "$dias_par" | grep -qx "$md"; then
    [ -n "$primer_par" ] || primer_par=$md
    ultimo_par=$md
    visto_par=1
    # Un elegible sin el par que estaba entre dos CON el par deja de ser "de detras".
    enmedio=$((enmedio + despues)); despues=0; limpias_lista=""
  elif [ "$visto_par" = 0 ]; then
    antes=$((antes+1))
  else
    despues=$((despues+1)); limpias_lista="$limpias_lista $d"
  fi
done
echo "puntas: $antes elegible(s) ANTES del primer dia con el par ($primer_par) · $enmedio en medio sin el par · $despues DESPUES del ultimo ($ultimo_par)"
echo "  los $antes de delante fechan el nacimiento; los $despues de detras son ocasiones LIMPIAS y no fechan nada del nacimiento"

# K, calculado aqui y no elegido: cota de la tasa historica + suelo. Ver la cabecera.
SUELO=7
activas=$((vistos + enmedio))
K=$(python3 -c "
import math
v, a, suelo = $vistos, $activas, $SUELO
if a <= 0:
    print(suelo); raise SystemExit
p = 0.05 ** (1.0 / v) if v >= a else v / a
print(max(suelo, math.ceil(math.log(0.05) / math.log(1 - p))) if 0 < p < 1 else suelo)
" 2>/dev/null) || K=$SUELO

if [ "$vistos" -lt "$MINIMO" ]; then
  # No recurre. Aun asi, cero ocasiones no es verde: eso lo cubre el NOMED de mas arriba.
  echo "VERDE (NO RECURRE): ningun par (minuto,clase) llega a $MINIMO dias elegibles. El peor es $clase a las ${minuto}Z, $vistos de $elegibles."
  exit 0
fi

echo "recurrencia: $clase a las ${minuto}Z en $vistos de $elegibles dias elegibles (umbral $MINIMO) · ocasiones limpias tras el ultimo caso: $despues · K=$K (suelo $SUELO)"
if [ "$despues" -eq 0 ]; then
  echo "ROJO (VIVO): el par recurre Y aparece en la ULTIMA ocasion elegible ($ultimo_par). Una excepcion que sabe que hora es no es una averia, es un defecto de diseno."
  echo "  la recurrencia ya esta demostrada, asi que una sola aparicion reciente basta: una recaida enrojece el primer dia."
  exit 1
fi
if [ "$despues" -ge "$K" ]; then
  echo "VERDE (REMITIDO Y PROBADO): el par recurrio $vistos veces y lleva $despues ocasiones elegibles limpias, que son >= K=$K."
  echo "  limpias:$limpias_lista"
  echo "  ESTO NO DICE QUE NADIE LO ARREGLARA. Dice que la tasa historica ya no explica el silencio. Quien quiera afirmar un arreglo tiene que enseniar el commit."
  exit 0
fi
echo "NO MEDIDO (CALLADO SIN PROBAR): el par recurre ($vistos de $elegibles) pero no aparece desde $ultimo_par."
echo "  solo hay $despues ocasion(es) elegible(s) limpia(s) y hacen falta $K:$limpias_lista"
echo "  NO es verde: un verde por falta de prueba es un verde no ganado. NO es rojo: el defecto no se ha vuelto a ver."
exit 2
