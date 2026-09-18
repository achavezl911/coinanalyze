#!/bin/bash
# K49-control · ¿el veredicto sobre la unit de respaldo sale de una corrida TERMINADA?
#
#     bash harness/checks/K49-control.bash
#
# EL PUNTO (COLA 125, A58). El 2026-09-17 el operador leyo el respaldo de las libretas como
# SANO mientras llevaba 21 h fallando en cada tick de 5 minutos. No se equivoco de comando: lo
# leyo DENTRO de una corrida de la unit. Medido: `systemctl show` durante la corrida devuelve
# los valores NEUTROS -Result=success, ExecMainStatus=0- con `ExecMainExitTimestamp` VACIO, que
# es la firma. K49 leia Result y ExecMainStatus sin mirar nada mas, asi que durante esos
# segundos de cada 300 daba VERDE pase lo que pase despues.
#
# EL ACTOR ES REAL, NO UN DOBLE DE `systemctl` (A57). Un `systemctl` de mentira en el PATH
# habria pasado este control con el defecto delante: lo que hay que reproducir es lo que hace
# SYSTEMD, y sus valores neutros durante la corrida son precisamente lo que un doble no tiene
# por que imitar bien. Aqui se instala una unit VOLATIL en `/run/systemd/system` -que es tmpfs:
# no sobrevive a un reinicio y no toca `/etc`-, se la hace correr, fallar y salir bien de
# verdad, y se lee K49 en cada uno de esos estados.
#
# LA UNIT DEL RESPALDO NO SE TOCA. Ni se para, ni se relanza, ni se le escribe: K49 recibe la
# suya por `K49_UNIT`. Lo unico que se lee de la de verdad es su TIMER, y solo porque K49 exige
# que haya un timer armado; `systemctl is-active` es una lectura.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K49-libretas-fuera-de-143.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
command -v systemctl >/dev/null 2>&1 || { echo "NO MEDIDO: no hay systemctl en esta maquina"; exit 2; }
[ "$(id -u)" = 0 ] || { echo "NO MEDIDO: instalar una unit volatil en /run/systemd/system pide root; soy $(id -un)"; exit 2; }
[ -d /run/systemd/system ] || { echo "NO MEDIDO: no hay /run/systemd/system: esto no es un systemd vivo"; exit 2; }

TIMER_REAL=${K49_CONTROL_TIMER:-coinalyze-libretas.timer}
U="k49-control-$$.service"
U2="k49-control-b-$$.service"
SH="/run/k49-control-$$.sh"
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-62s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-62s\n' "$1"; fi; }

limpia() {
  systemctl stop "$U" "$U2" >/dev/null 2>&1
  systemctl reset-failed "$U" "$U2" >/dev/null 2>&1
  rm -f "/run/systemd/system/$U" "/run/systemd/system/$U2" "$SH"
  systemctl daemon-reload >/dev/null 2>&1
}
trap limpia EXIT

instala() {  # $1 = nombre de la unit
  cat > "/run/systemd/system/$1" <<EOF
[Unit]
Description=control de K49 · unit VOLATIL de $SH, se borra al acabar
[Service]
Type=oneshot
ExecStart=/bin/bash $SH
EOF
  systemctl daemon-reload
}
guion() { printf '#!/bin/bash\n%s\n' "$1" > "$SH"; chmod +x "$SH"; }
foto() {  # el estado de la unit, en una linea
  systemctl show "$1" -p ActiveState -p Result -p ExecMainStatus -p ExecMainExitTimestamp \
    2>/dev/null | tr '\n' ' '
}
corre_k49() {  # $1 = unit que K49 tiene que mirar  -> deja RC y OUT
  OUT=$(env K49_UNIT="$1" K49_TIMER="$TIMER_REAL" timeout -k 10 180 bash "$CHK" 2>&1); RC=$?
}
espera_corriendo() {  # $1 = unit · hasta 50 intentos de 0.2 s
  local i=0
  while [ $i -lt 50 ]; do
    case "$(systemctl show "$1" -p ActiveState --value 2>/dev/null)" in
      activating|active) return 0 ;;
    esac
    sleep 0.2; i=$((i+1))
  done
  return 1
}
lee() {  # $1 = etiqueta  $2 = unit · imprime la foto ANTES y DESPUES de leer K49
  local etq="$1" u="$2" a d
  a=$(foto "$u"); corre_k49 "$u"; d=$(foto "$u")
  printf '      %s antes:   %s\n' "$etq" "$a"
  printf '      %s K49:     rc=%s · %s\n' "$etq" "$RC" "$(printf '%s' "$OUT" | head -1 | cut -c1-150)"
  printf '      %s despues: %s\n' "$etq" "$d"
  ANTES="$a"; DESPUES="$d"
}

echo "K49-control · sujeto: $CHK"
echo "   unit volatil: $U (y $U2 para «nunca ha corrido») · timer que K49 mira: $TIMER_REAL"
systemctl is-active --quiet "$TIMER_REAL" 2>/dev/null \
  || { echo "NO MEDIDO: $TIMER_REAL no esta activo, asi que K49 condenaria por el timer y no por la unit"; exit 2; }
echo

instala "$U"

# ── A1 · UNA CORRIDA TERMINADA EN FALLO ─────────────────────────────────────────────────────
echo "A1 · corrida TERMINADA EN FALLO -> ROJO"
guion 'echo "el respaldo de mentira se niega"; exit 1'
systemctl start "$U" >/dev/null 2>&1 || true
lee A1 "$U"
comprueba "A1a ROJO, rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
comprueba "A1b y dice que la unit FALLO" \
  "$(printf '%s' "$OUT" | grep -q 'la unit de respaldo FALLO' && echo si || echo no)"
comprueba "A1c y dice DE QUE CORRIDA habla (terminada, con su fecha)" \
  "$(printf '%s' "$OUT" | grep -q 'corrida terminada' && echo si || echo no)"
comprueba "A1d leer K49 NO movio la unit" "$([ "$ANTES" = "$DESPUES" ] && echo si || echo no)"

# ── A1b · LA MISMA CORRIDA FALLIDA, CON `show` YA EN BLANCO ────────────────────────────────
echo
echo "A1bis · el fallo sigue siendo fallo aunque `systemctl show` vuelva a los valores NEUTROS"
# `reset-failed` deja la unit EXACTAMENTE como una que salio bien -o como una que no ha corrido
# nunca-: Result=success, ExecMainStatus=0, ExecMainExitTimestamp vacio. Si K49 solo mirara
# `show`, aqui volveria a dar VERDE sobre una corrida que fallo. Es el mismo agujero que el de
# leer durante la corrida, por la otra puerta.
systemctl reset-failed "$U" >/dev/null 2>&1 || true
lee A1bis "$U"
comprueba "A1bis-a con show en blanco, SIGUE siendo ROJO (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
comprueba "A1bis-b y el veredicto sale de la ULTIMA corrida TERMINADA del journal" \
  "$(printf '%s' "$OUT" | grep -q 'ULTIMA corrida TERMINADA' && echo si || echo no)"
comprueba "A1bis-c y dice que la leyo ENTRE corridas, no durante una" \
  "$(printf '%s' "$OUT" | grep -q 'leida entre corridas' && echo si || echo no)"

# ── A2 · UNA CORRIDA TERMINADA BIEN ─────────────────────────────────────────────────────────
echo
echo "A2 · corrida TERMINADA BIEN -> VERDE"
guion 'echo "el respaldo de mentira hace su trabajo"; exit 0'
systemctl start "$U" >/dev/null 2>&1 || true
lee A2 "$U"
comprueba "A2a VERDE, rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
comprueba "A2b y NO condena a la unit" \
  "$(printf '%s' "$OUT" | grep -q 'la unit de respaldo FALLO' && echo no || echo si)"
comprueba "A2c y dice QUE corrida juzgo" \
  "$(printf '%s' "$OUT" | grep -q 'ultima corrida TERMINADA' && echo si || echo no)"
comprueba "A2d leer K49 NO movio la unit" "$([ "$ANTES" = "$DESPUES" ] && echo si || echo no)"

# ── A3 · EL PUNTO · LEIDA DURANTE UNA CORRIDA QUE SIGUE A UN FALLO ──────────────────────────
echo
echo "A3 · EL PUNTO · CORRIENDO, y la ultima TERMINADA fallo -> NO puede dar VERDE"
guion 'echo "falla otra vez"; exit 1'
systemctl start "$U" >/dev/null 2>&1 || true
guion 'sleep 60'
systemctl start --no-block "$U" >/dev/null 2>&1 || true
if espera_corriendo "$U"; then
  vivo=$(foto "$U")
  printf '      A3 la unit CORRIENDO dice: %s\n' "$vivo"
  # LA FIRMA DE A58, MEDIDA AQUI Y NO CITADA: durante la corrida los valores son NEUTROS.
  comprueba "A3a reproducido: durante la corrida Result=success y ExecMainStatus=0" \
    "$(printf '%s' "$vivo" | grep -q 'Result=success' && printf '%s' "$vivo" | grep -q 'ExecMainStatus=0' && echo si || echo no)"
  comprueba "A3b y ExecMainExitTimestamp VACIO, que es lo que los delata" \
    "$(printf '%s' "$vivo" | grep -q 'ExecMainExitTimestamp= ' && echo si || echo no)"
  lee A3 "$U"
  comprueba "A3c NO da VERDE (rc=$RC)" "$([ "$RC" != 0 ] && echo si || echo no)"
  comprueba "A3d da ROJO, que es lo que la corrida anterior merece (rc=$RC)" \
    "$([ "$RC" = 1 ] && echo si || echo no)"
  comprueba "A3e y dice que la leyo DURANTE una corrida y de cual saca el veredicto" \
    "$(printf '%s' "$OUT" | grep -q 'leida DURANTE una corrida' && printf '%s' "$OUT" | grep -q 'ULTIMA corrida TERMINADA' && echo si || echo no)"
  comprueba "A3f leer K49 NO movio la unit" "$([ "$ANTES" = "$DESPUES" ] && echo si || echo no)"
else
  comprueba "A3 la unit volatil no llego a ponerse en marcha" no
fi
systemctl stop "$U" >/dev/null 2>&1 || true
systemctl reset-failed "$U" >/dev/null 2>&1 || true

# ── A4 · EL CONTROL DE A3 · CORRIENDO, PERO LA ULTIMA TERMINADA FUE BIEN ────────────────────
echo
echo "A4 · CONTROL DE A3 · CORRIENDO, y la ultima TERMINADA fue BIEN -> VERDE"
# Sin este brazo, A3 pasaria igual con un K49 que condenara SIEMPRE que la unit este corriendo.
# Lo unico que cambia entre los dos es el resultado de la corrida ANTERIOR.
guion 'echo "esta vez bien"; exit 0'
systemctl start "$U" >/dev/null 2>&1 || true
guion 'sleep 60'
systemctl start --no-block "$U" >/dev/null 2>&1 || true
if espera_corriendo "$U"; then
  lee A4 "$U"
  comprueba "A4a VERDE, rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
  comprueba "A4b y dice que la leyo DURANTE una corrida" \
    "$(printf '%s' "$OUT" | grep -q 'leida DURANTE una corrida' && echo si || echo no)"
  comprueba "A4c leer K49 NO movio la unit" "$([ "$ANTES" = "$DESPUES" ] && echo si || echo no)"
else
  comprueba "A4 la unit volatil no llego a ponerse en marcha" no
fi
systemctl stop "$U" >/dev/null 2>&1 || true
systemctl reset-failed "$U" >/dev/null 2>&1 || true

# ── A5 · NINGUNA CORRIDA TERMINADA QUE LEER ────────────────────────────────────────────────
echo
echo "A5 · una unit que NO HA CORRIDO NUNCA -> NO MEDIDO, y no VERDE"
instala "$U2"
lee A5 "$U2"
comprueba "A5a NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "A5b y lo dice: no hay ninguna corrida TERMINADA que leer" \
  "$(printf '%s' "$OUT" | grep -q 'no hay NINGUNA corrida TERMINADA' && echo si || echo no)"
comprueba "A5c y NO dice que el respaldo este bien" \
  "$(printf '%s' "$OUT" | grep -q 'RESTAURADAS' && echo no || echo si)"

# ── A6 · CORRIENDO POR PRIMERA VEZ: TAMPOCO HAY NADA TERMINADO ─────────────────────────────
echo
echo "A6 · CORRIENDO por primera vez, sin ninguna terminada detras -> NO MEDIDO"
guion 'sleep 60'
systemctl start --no-block "$U2" >/dev/null 2>&1 || true
if espera_corriendo "$U2"; then
  lee A6 "$U2"
  comprueba "A6a NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
  comprueba "A6b y NO da VERDE por estar la unit en marcha" "$([ "$RC" != 0 ] && echo si || echo no)"
else
  comprueba "A6 la unit volatil no llego a ponerse en marcha" no
fi
systemctl stop "$U2" >/dev/null 2>&1 || true
systemctl reset-failed "$U2" >/dev/null 2>&1 || true

# ── EL CONTROL DEL CONTROL · la unit de VERDAD sigue donde estaba ──────────────────────────
echo
echo "   la unit del respaldo de VERDAD, que este control NO toca:"
systemctl show coinalyze-libretas.service -p ActiveState -p Result -p ExecMainStatus \
  -p ExecMainExitTimestamp 2>/dev/null | sed 's/^/      /'
echo "      timer: $(systemctl show "$TIMER_REAL" -p ActiveState --value 2>/dev/null)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
