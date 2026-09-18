#!/bin/bash
# K49  las cuatro libretas -hechos.tsv, COLA.md, CAMBIOS.md, ESTADO.md- son 368.8 KB de
# CRITERIO acumulado en seis semanas y vivian en un solo sitio: el rootfs de 143.
#
# LO QUE ESTE CHECK NO ACEPTA COMO RESPALDO
# Los 24 .bak de harness/ estan en el MISMO rootfs: protegen de una edicion mala, no de
# perder el contenedor. Y el respaldo que corre en 140 escribe en /var/backups/coinalyze,
# o sea el rootfs de 140, que esta en el MISMO nodo Proxmox que 143: no sirve para el
# fallo que importa. Copia y respaldo no son lo mismo, que es la leccion entera de K01b.
#
# POR QUE NO BASTA CON QUE EL FICHERO EXISTA
# Un fichero de 0 bytes en el destino tambien "existe", y un push truncado tambien deja
# un commit. Se exige PRUEBA DE RESTAURACION: se clona el destino de verdad, se recupera
# hechos.tsv y su sha256 tiene que cuadrar con el vivo. Sin eso es un fichero, no un
# respaldo.
#
# LO QUE NO SE GUARDA, y es deliberado: harness/secretos/. Son 1605 bytes REGENERABLES
# -el nodo Proxmox entra a 140 sin la clave- y lo irrecuperable no son las llaves, es el
# criterio. harness/env si va: su primera linea dice que ahi no vive ningun secreto.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
DESTINO=${LIBRETAS_REMOTO:-https://github.com/achavezl911/coinanalyze-libretas.git}
MAX_HORAS=24

declare -A VIVAS=(
  [hechos.tsv]=/srv/coinanalyze/harness/hechos.tsv
  [COLA.md]=/srv/coinanalyze/harness/COLA.md
  [ESTADO.md]=/srv/coinanalyze/harness/ESTADO.md
  [CAMBIOS.md]=/srv/coinanalyze/CAMBIOS.md
)

for f in "${!VIVAS[@]}"; do
  [ -r "${VIVAS[$f]}" ] || { echo "NO MEDIDO: no se puede leer la libreta viva ${VIVAS[$f]}"; exit 2; }
done

# EL RESPALDO PODIA ESTAR FALLANDO CADA 5 MIN Y ESTE CHECK NO SE ENTERABA.
# MEDIDO el 2026-08-28: coinalyze-libretas.service llevaba fallando desde las 22:10:03Z
# -un servicio sin User= corre como root pero con HOME VACIO, y sin HOME git no llega a
# /root/.gitconfig, donde vive el ayudante de credenciales- con 9 commits sin empujar que
# contenian una sesion entera de auditoria. Y este check seguia en VERDE, porque lo unico
# que miraba era la EDAD de la copia contra un techo de 24 h: habrian hecho falta 24
# FALLOS CONSECUTIVOS para que enrojeciera. UN FALLO RUIDOSO QUE NINGUN CHECK LEE ES UN
# FALLO SILENCIOSO CON PASOS EXTRA.
# El arreglo del PR 94 hizo que la unit fallara a gritos en cada tick; esto es lo que la
# escucha. Sin las dos mitades no sirve ninguna.
UNIT=${K49_UNIT:-coinalyze-libretas.service}
TIMER=${K49_TIMER:-coinalyze-libretas.timer}
CORRIDA="sin systemctl en esta maquina: la unit no se ha podido mirar"
if command -v systemctl >/dev/null 2>&1; then
  carga=$(systemctl show "$UNIT" -p LoadState --value 2>/dev/null)
  case "$carga" in
    loaded) ;;
    not-found|"") echo "no hay unit de respaldo instalada ($UNIT): no hay nada empujando las libretas fuera de 143"; exit 1 ;;
    *) echo "NO MEDIDO: LoadState=$carga para $UNIT"; exit 2 ;;
  esac
  # EL VEREDICTO SALE DE UNA CORRIDA TERMINADA, NO DE LA QUE ESTA CORRIENDO (COLA 125, A58).
  # MEDIDO: `systemctl show` DENTRO de la corrida de una unit devuelve los valores NEUTROS
  # -Result=success y ExecMainStatus=0- con `ExecMainExitTimestamp` VACIO, que es la firma.
  # Estas cuatro lineas leian Result y ExecMainStatus SIN MIRAR NADA MAS, asi que durante los
  # segundos que dura cada tick DABAN VERDE PASE LO QUE PASE DESPUES. El 2026-09-17 el operador
  # leyo el respaldo como sano mientras llevaba 21 h fallando en cada tick: lo leyo dentro de
  # una corrida. Un instrumento cuya respuesta depende de CUANDO se le pregunta no esta
  # midiendo el sujeto, esta midiendo el reloj -y este mide justo lo que no se puede perder-.
  #
  # EL DISCRIMINADOR ES `ActiveState`, Y NO `ExecMainExitTimestamp`. La primera version de este
  # arreglo usaba el sello de salida -«si tiene valor, hay corrida terminada»- y su propio
  # control la tumbo: MEDIDO el 2026-09-18 sobre una unit volatil, tras una corrida que sale
  # BIEN systemd deja `ExecMainExitTimestamp` VACIO igual que durante la corrida, y solo lo
  # conserva cuando la unit queda en `failed`:
  #     terminada mal   Result=exit-code ExecMainExitTimestamp=<fecha> ExecMainStatus=1 ActiveState=failed
  #     terminada bien  Result=success   ExecMainExitTimestamp=        ExecMainStatus=0 ActiveState=inactive
  #     CORRIENDO       Result=success   ExecMainExitTimestamp=        ExecMainStatus=0 ActiveState=activating
  # Las dos ultimas son IDENTICAS en `show` salvo por `ActiveState`, y «nunca ha corrido» es
  # identica a la segunda. Por eso la corrida terminada se lee del JOURNAL, que es el unico
  # sitio donde una terminacion deja rastro que systemd no borre al arrancar la siguiente.
  #
  # LOS CUATRO ESTADOS, Y NINGUNO DE ELLOS ES «VERDE POR DEFECTO»:
  #   la unit quedo en `failed`            -> ROJO, con su motivo y su fecha
  #   ultima terminacion del journal: mal  -> ROJO, se este corriendo ahora o no
  #   ultima terminacion del journal: bien -> se sigue midiendo, y la linea dice CUAL juzgo
  #   el journal no trae ninguna           -> NO MEDIDO, nunca VERDE
  estado=$(systemctl show "$UNIT" -p ActiveState --value 2>/dev/null)
  resultado=$(systemctl show "$UNIT" -p Result --value 2>/dev/null)
  salida=$(systemctl show "$UNIT" -p ExecMainStatus --value 2>/dev/null)
  fin=$(systemctl show "$UNIT" -p ExecMainExitTimestamp --value 2>/dev/null)
  motivo_journal() {
    journalctl -u "$UNIT" -n 20 --no-pager 2>/dev/null \
      | grep -iE 'fatal|error|respalda-libretas:' | tail -1 | cut -c1-160
  }
  if [ "$estado" = failed ]; then
    echo "la unit de respaldo FALLO (Result=$resultado ExecMainStatus=$salida, corrida terminada" \
         "${fin:-sin fecha}): $(motivo_journal || true)"; exit 1
  fi
  case "$estado" in
    activating|active|reloading|deactivating)
      COMO="leida DURANTE una corrida (ActiveState=$estado)" ;;
    *)
      COMO="leida entre corridas (ActiveState=$estado)" ;;
  esac
  ult=$(journalctl -u "$UNIT" -n 500 --no-pager -o short-iso 2>/dev/null \
        | grep -E 'Deactivated successfully|Succeeded\.|Failed with result' | tail -1)
  case "$ult" in
    *"Failed with result"*)
      echo "la unit de respaldo FALLO en su ULTIMA corrida TERMINADA" \
           "-$(printf '%s' "$ult" | cut -c1-70)-; $COMO. Durante la corrida systemd devuelve" \
           "Result=success con ExecMainExitTimestamp vacio, y eso no es un veredicto:" \
           "$(motivo_journal || true)"; exit 1 ;;
    *"Deactivated successfully"*|*"Succeeded."*)
      CORRIDA="ultima corrida TERMINADA $(printf '%s' "$ult" | awk '{print $1}'), bien · $COMO" ;;
    *)
      echo "NO MEDIDO: no hay NINGUNA corrida TERMINADA de $UNIT que leer ($COMO," \
           "ExecMainExitTimestamp='${fin}', y el journal no trae ninguna terminacion en las" \
           "ultimas 500 lineas). Dar VERDE aqui seria dar por bueno un respaldo del que no" \
           "consta que haya corrido nunca."; exit 2 ;;
  esac
  # Y EL TIMER TIENE QUE ESTAR ARMADO. Una unit que "no ha fallado" porque no la lanza
  # nadie es el cero-sin-medicion de K60 aplicado a un respaldo: el veredicto mas
  # tranquilizador posible sobre algo que no esta ocurriendo.
  systemctl is-active --quiet "$TIMER" 2>/dev/null || {
    echo "la unit de respaldo no ha fallado, pero su timer ($TIMER) NO esta activo: no la lanza nadie"; exit 1; }
fi

# TRES ESTADOS, NO UNO. La version anterior metia "no existe", "existe pero vacio" y "no
# se pudo alcanzar" en el mismo saco y afirmaba ROJO para los tres: dio VERDE, ROJO y
# VERDE otra vez en minutos, y ese ROJO decia "siguen SOLO en el rootfs de 143" cuando el
# remoto ya tenia las cuatro libretas dentro. Era falso. Es la misma forma que K19 y K07
# -leer sin filtrar por estado- y aqui pesa mas, porque K49 vigila lo unico que si se
# pierde no se recupera, y un check que enrojece segun el momento acaba tratandose como
# ruido. GIT_TERMINAL_PROMPT=0 y timeout para que un remoto colgado falle rapido en vez
# de quedarse esperando una credencial que nadie va a teclear.
ls_salida=$(GIT_TERMINAL_PROMPT=0 timeout 30 git ls-remote --exit-code "$DESTINO" HEAD 2>&1)
ls_rc=$?
case $ls_rc in
  0) : ;;                                   # alcanzable y con refs: se sigue midiendo
  2) echo "el destino existe pero esta VACIO: $DESTINO no tiene ni una ref, las libretas siguen solo en 143"; exit 1 ;;
  *)
    # Alcanzar el remoto y que conteste "no" es una respuesta y se afirma. No alcanzarlo
    # no es una respuesta: eso es NO MEDIDO, y el mensaje lleva lo que dijo git para que
    # se distinga de un vistazo si se perdio el repo o solo el acceso.
    if printf '%s' "$ls_salida" | grep -qiE 'not found|does not exist|access denied|permission denied|403'; then
      echo "el remoto contesta y NIEGA el destino ($DESTINO): $(printf '%s' "$ls_salida" | tr '\n' ' ' | cut -c1-120)"; exit 1
    fi
    echo "NO MEDIDO: no se pudo alcanzar $DESTINO (rc=$ls_rc): $(printf '%s' "$ls_salida" | tr '\n' ' ' | cut -c1-120)"; exit 2 ;;
esac

# Restauracion de verdad: se clona a un directorio nuevo. Si el destino esta vacio,
# truncado o sin alguna libreta, se ve aqui y no cuando haga falta.
TMP=$(mktemp -d /tmp/k49-restaura.XXXXXX) || { echo "NO MEDIDO: no se pudo crear el directorio de restauracion"; exit 2; }
trap 'rm -rf "$TMP"' EXIT
git clone --quiet --depth 1 "$DESTINO" "$TMP/copia" 2>/dev/null || {
  echo "NO MEDIDO: $DESTINO responde pero no se pudo clonar"; exit 2; }

faltan=""
for f in "${!VIVAS[@]}"; do
  [ -s "$TMP/copia/$f" ] || faltan="$faltan $f"
done
[ -z "$faltan" ] || { echo "la copia existe pero no trae (o trae vacias):$faltan"; exit 1; }

# `entregas/` TAMBIEN TIENE QUE VOLVER (COLA 124). Las cuatro libretas son el CRITERIO;
# `entregas/` es el METODO, y hasta hoy vivia solo en el disco de 143. Si el remoto trae las
# libretas y no el metodo, este check decia VERDE sobre media copia.
n_entregas=$(find "$TMP/copia/entregas" -type f 2>/dev/null | wc -l)
if [ "$n_entregas" -eq 0 ]; then
  echo "la copia trae las libretas pero NO trae entregas/: el metodo -recetas, traspasos," \
       "auditorias, encargos y predicciones- sigue solo en 143, y esto decia VERDE igual"
  exit 1
fi

# Fecha del respaldo: la del ULTIMO COMMIT del destino, no la mtime del clon, que es de
# hace un segundo y diria que siempre esta fresco.
commit_epoch=$(git -C "$TMP/copia" log -1 --format=%ct 2>/dev/null)
[ -n "$commit_epoch" ] || { echo "NO MEDIDO: la copia no trae fecha de commit"; exit 2; }
horas=$(( ( $(date +%s) - commit_epoch ) / 3600 ))
[ "$horas" -le "$MAX_HORAS" ] || {
  echo "la copia de las libretas tiene $horas h, por encima del techo de $MAX_HORAS h: el respaldo dejo de correr"; exit 1; }

# LA PRUEBA DE RESTAURACION. Lo recuperado del remoto contra el manifiesto que viajo en
# el MISMO commit: eso demuestra el viaje de ida y vuelta -que nada se trunco ni se
# corrompio- y no depende del instante en que se mire.
#
# NO se compara contra el fichero vivo, y es deliberado: se probo, y sale ROJO cada vez
# que alguien anade un hecho a hechos.tsv entre dos ticks del timer, con el mensaje "no
# cuadra con el vivo", que se lee como corrupcion cuando lo unico que pasa es que la
# copia va minutos por detras. Lo que acota ese retraso es el techo de $MAX_HORAS de
# arriba, no una comparacion que enrojece por el reloj. El desfase se MIDE y se dice en
# la linea de VERDE, para que se vea en vez de esconderse.
[ -s "$TMP/copia/SHA256SUMS" ] || { echo "la copia no trae manifiesto: sin el, restaurar no se puede demostrar"; exit 1; }
if ! ( cd "$TMP/copia" && sha256sum --quiet -c SHA256SUMS >/dev/null 2>&1 ); then
  malas=$( cd "$TMP/copia" && sha256sum -c SHA256SUMS 2>/dev/null | grep -v ': OK$' | cut -d: -f1 | tr '\n' ' ')
  echo "lo restaurado del remoto NO cuadra con su propio manifiesto: $malas (copia de hace $horas h)"; exit 1
fi

# EL MANIFIESTO TIENE UN HUECO Y ESTE ES EL PARCHE. sha256sum -c prueba que lo que llego
# llego INTACTO, no que sea FIEL: si respalda-libretas escribiera un hechos.tsv truncado
# y calculara el manifiesto sobre ESE fichero, cuadraria y el check pasaria.
#
# hechos.tsv es append-only POR REGLA, asi que la copia tiene que ser un PREFIJO EXACTO
# del vivo. Eso caza un origen truncado o reordenado Y TOLERA el desfase, que es lo que
# rompia la comparacion por igualdad.
#
# NO SE GENERALIZA A LAS OTRAS TRES, medido: ESTADO.md se reescribe entero cada sesion y
# COLA.md se edita en medio, asi que ninguna es prefijo de nada. Vale para hechos.tsv y
# solo para hechos.tsv.
#
# EFECTO SECUNDARIO, que es lo mejor de la idea: convierte el append-only de hechos.tsv
# en un INVARIANTE COMPROBADO. Si alguien borra una linea, la copia deja de ser prefijo y
# esto lo caza. Hasta hoy esa regla la sostenia la disciplina de quien escribe, y una
# regla que solo sostiene la disciplina de alguien no es una regla: es una costumbre.
sha_copia=$(sha256sum "$TMP/copia/hechos.tsv" | cut -d' ' -f1)
bytes_copia=$(wc -c < "$TMP/copia/hechos.tsv")
bytes_vivo=$(wc -c < "${VIVAS[hechos.tsv]}")

if [ "$bytes_copia" -gt "$bytes_vivo" ]; then
  echo "el hechos.tsv VIVO es mas corto que la copia ($bytes_vivo B < $bytes_copia B): o se trunco el vivo, o dejo de ser append-only"; exit 1
fi

sha_prefijo=$(head -c "$bytes_copia" "${VIVAS[hechos.tsv]}" | sha256sum | cut -d' ' -f1)
if [ "$sha_prefijo" != "$sha_copia" ]; then
  echo "la copia de hechos.tsv NO es prefijo del vivo: los primeros $bytes_copia B del vivo dan ${sha_prefijo:0:12} y la copia ${sha_copia:0:12}. hechos.tsv se reescribio en medio, o el respaldo salio de un origen distinto"; exit 1
fi

if [ "$bytes_copia" -eq "$bytes_vivo" ]; then
  desfase="hechos.tsv identico al vivo"
else
  desfase="hechos.tsv es PREFIJO EXACTO del vivo, $(( bytes_vivo - bytes_copia )) B por detras (append-only intacto)"
fi

# LA CIFRA TIENE QUE SER LA DE LA COPIA. Antes se sumaban los ficheros VIVOS y la frase
# decia que esos bytes estaban fuera de 143: el numero pertenecia a un objeto DISTINTO del
# que se afirmaba a salvo. Con el desfase normal la diferencia es de bytes y pasa
# desapercibida; el dia que el respaldo se congele, la cifra seguiria creciendo con el
# vivo y publicando tranquilidad sobre una copia que ya no crece. Se suma lo restaurado.
total=$(( $(wc -c < "$TMP/copia/hechos.tsv") + $(wc -c < "$TMP/copia/COLA.md") \
        + $(wc -c < "$TMP/copia/ESTADO.md") + $(wc -c < "$TMP/copia/CAMBIOS.md") ))
b_entregas=$(find "$TMP/copia/entregas" -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1} END{print s+0}')
n_manifiesto=$(wc -l < "$TMP/copia/SHA256SUMS")
echo "las 4 libretas RESTAURADAS suman $total B fuera de 143, y entregas/ otros $b_entregas B" \
     "en $n_entregas ficheros -el metodo, no solo el criterio-; copia de hace ${horas} h," \
     "cuadrada contra su manifiesto ($n_manifiesto ficheros); $desfase · unit: $CORRIDA"
