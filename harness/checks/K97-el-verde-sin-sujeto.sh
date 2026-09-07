#!/usr/bin/env bash
# K97 · EL VERDE SIN SUJETO
#
# SUJETO   los demas checks del arnes. Para cada uno se le da una POBLACION VACIA por el mismo
#          canal por el que lee, y se exige que NO salga VERDE.
# ROJO     si algun check sale VERDE (exit 0) con la poblacion vacia y no tiene disposicion.
# VERDE    si ninguno lo hace -o los que lo hacen estan dispuestos con su cita-.
# NOMED    si el instrumento no se puede montar, o si sus DOS controles no responden como se
#          sabe que tienen que responder. Un censo que no se ha probado a si mismo no es un censo.
#
# POR QUE EXISTE. La campania CADUCIDAD cerro K86 y K92 y dejo abierto H3: ¿hay mas checks que
# puedan ponerse verdes por falta de ocasion? Se intento contestar con tres tamices de `grep` y
# **se contradijeron entre si -18, 13 y 2-**, asi que no se nombro a ninguno. La conclusion de
# aquella entrega fue que no se cierra con otro grep sino con un check que EJECUTE cada sujeto
# contra una poblacion vacia. Esto es ese check.
#
# UN CHECK QUE ANTE CERO SUJETOS DICE «TODO BIEN» NO ESTA MIDIENDO, ESTA VOTANDO.
#
# ---------------------------------------------------------------------------------
# COMO SE LE DA UNA POBLACION VACIA A CADA FAMILIA. Se clasifica por su CANAL, medido con
# `grep -n` sobre el propio fichero y no supuesto:
#
#   A  FIXTURE      el check ya acepta un fichero por entorno (K86_FIXTURE). Se le da uno VACIO.
#   B  BINARIO      acepta el binario del canal por entorno (K90_PRODSQL, K92_PRODSQL/PROD).
#                   Se le da un doble.
#   C  ARNES POR $B hace `B=/srv/coinanalyze/harness` y luego `"$B/bin/prodsql"`. Se corre una
#                   COPIA con esa linea reescrita a un arnes de mentira. Es el patron que
#                   K95-control y K86-control ya usan: un arbol de mentira, no un mock.
#   D  SIN CANAL    su poblacion no llega por un canal a 140. **NO SE JUZGA ASI Y SE NOMBRA.**
#                   Un repo vacio no es una poblacion vacia: es un sujeto roto.
#
# LOS DOS DOBLES, y por que hacen falta los dos. `bin/prodsql` invoca `psql -X -A -F'|' -t`,
# o sea sin cabeceras. Sobre una tabla vacia:
#   · `SELECT ... FROM t WHERE ...`  devuelve CERO LINEAS   -> lo modela el doble MUDO
#   · `SELECT count(*) FROM t`       devuelve la linea `0`  -> lo modela el doble CERO
# Un check se declara ENFERMO si sale VERDE con CUALQUIERA de los dos. Exigir los dos seria
# mas laxo, no mas estricto.
#
# EL DOBLE TIENE QUE SALIR BIEN (rc=0). Un doble que fallara probaria otra cosa -que el check
# aguanta un canal caido, que ya esta probado en varios- y el veredicto seria sobre el guardia
# equivocado. Aqui la pregunta se HACE, se CONTESTA, y no habia nada.
#
# LO QUE ESTE CHECK NO SABE, dicho para que no se lea como si lo supiera:
#   1. NO distingue un NOMED por poblacion de un NOMED por transporte. Si un check dice «el
#      canal no responde» ante el doble mudo, aqui cuenta como SANO -no salio verde- aunque su
#      razon sea otra. Es un limite real y por eso la salida publica el motivo cuando lo hay.
#   2. EL DOBLE DE `api` ES DEBIL: emite `{}`, y un check que espere claves concretas dira
#      NOMED por formato. Sale SANO sin haber probado gran cosa. Se nombra en la salida.
#   3. No juzga a los checks SIN ventana movil. Un check cuyo sujeto es el arbol no puede
#      caducar, que es de lo que iba la campania de la que este sale.
#
# CONTROLES: harness/checks/K97-control.bash. No lleva .sh a proposito: bin/verify globea *.sh.
set -uo pipefail
B=/srv/coinanalyze/harness
REPO=${K97_REPO:-/srv/coinanalyze/repo}
CHECKS=${K97_CHECKS:-$REPO/harness/checks}
DISPOSICIONES=${K97_DISPOSICIONES:-$CHECKS/K97-disposiciones.tsv}
TOPE=${K97_TOPE:-60}

[ -d "$CHECKS" ] || { echo "NO MEDIDO: no encuentro los checks en $CHECKS"; exit 2; }
command -v timeout >/dev/null 2>&1 || { echo "NO MEDIDO: no hay timeout(1); un sujeto colgado se llevaria el censo"; exit 2; }

DIR=$(mktemp -d) || { echo "NO MEDIDO: no pude crear el arbol de mentira"; exit 2; }
[ "${K97_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT

# --- EL ARNES DE MENTIRA ------------------------------------------------------------------
# Se enlaza TODO el arnes real y se sustituyen solo los tres binarios del canal. Asi `env`,
# `_corta`, `leer` y compania siguen siendo los de verdad: lo unico que cambia es que al otro
# lado no hay filas. Un arnes recortado haria fallar a los sujetos por otra razon.
monta_falso() {  # $1 = destino   $2 = MUDO|CERO
  local d="$1" modo="$2" f
  mkdir -p "$d/bin"
  for f in "$B"/*; do
    case "$(basename "$f")" in bin) continue ;; esac
    ln -s "$f" "$d/$(basename "$f")" 2>/dev/null || true
  done
  for f in "$B"/bin/*; do
    case "$(basename "$f")" in prodsql|prod|api) continue ;; esac
    ln -s "$f" "$d/bin/$(basename "$f")" 2>/dev/null || true
  done
  # prodsql · psql -t sobre una tabla vacia no imprime nada; un count(*) imprime 0.
  #
  # UNA POBLACION VACIA NO ES UN CANAL CAIDO, y la primera version de este doble los confundia.
  # Varios checks abren con una sonda de vida -`SELECT 'canal_ok'`, `SELECT 1`-, que NO LLEVA
  # `FROM` y por tanto el motor la contesta sin mirar ninguna tabla: vaciar la base no la cambia.
  # Con el doble mudo a secas esa sonda volvia vacia, el check decia «prodsql no responde» y se
  # apuntaba como SANO **por la razon equivocada**. Medido: asi K06-visibilidad salia sano, y el
  # operador lo tenia confirmado como enfermo. Ahora el doble contesta lo que el motor
  # contestaria: las consultas SIN `FROM` se responden, las que tocan tablas vuelven vacias.
  { printf '#!/bin/sh\nq=$*\ncase "$q" in\n  *[Ff][Rr][Oo][Mm]*) ;;\n'
    printf '  *) printf %%s\\\\n "$q" | sed -e "s/^[[:space:]]*//" -e "s/;[[:space:]]*$//" \\\n'
    printf '       -e "s/^[Ss][Ee][Ll][Ee][Cc][Tt][[:space:]]*//" -e "s/^.\\(.*\\).$/\\1/"\n'
    printf '     exit 0 ;;\nesac\n'
    # EL DOBLE CERO SOLO CONTESTA `0` A LOS RECUENTOS, y esto tambien lo cazo su control.
    # La primera version devolvia `0` a CUALQUIER consulta con FROM, y eso no es una tabla
    # vacia: `SELECT ts FROM t` sobre una tabla vacia devuelve CERO LINEAS, no la linea `0`.
    # Con el doble infiel, un check sano -que cuenta sus filas y declara el vacio- recibia una
    # fila de mentira, se creia que tenia poblacion y salia ENFERMO. Un falso positivo del
    # instrumento es peor que un falso negativo: enseña a ignorar el censo.
    [ "$modo" = CERO ] && printf 'case "$q" in *[Cc][Oo][Uu][Nn][Tt]\\(*) printf %%s\\\\n 0 ;; esac\n'
    printf 'exit 0\n'
  } > "$d/bin/prodsql"
  # prod · la unidad no dijo nada en la ventana. Es el vacio del journal.
  printf '#!/bin/sh\nexit 0\n' > "$d/bin/prod"
  # api · la ruta contesta, y no trae nada. El doble es DEBIL y se declara en la salida.
  printf '#!/bin/sh\nprintf %%s\\\\n "{}"\nexit 0\n' > "$d/bin/api"
  # LA HUELLA. Cada doble deja constancia de que lo llamaron, y sin esa constancia NO SE JUZGA.
  # Es la correccion del fallo que tuvo la primera version: se reescribia `B=/srv/coinanalyze/harness`
  # con un sed anclado, y K18-borrado pone `B=${K18_HARNESS:-/srv/coinanalyze/harness}`. El sed no
  # casaba, la copia era identica al original, **el check corria contra PRODUCCION DE VERDAD**,
  # salia VERDE porque hoy lo esta... y este censo lo apuntaba como ENFERMO. Un falso positivo
  # del instrumento es peor que un falso negativo: enseña a ignorar el censo.
  for x in prodsql prod api; do
    sed -i "1a printf '%s\\\\n' \"\$0\" >> \"\$K97_HUELLA\" 2>/dev/null || true" "$d/bin/$x"
  done
  chmod 755 "$d/bin/prodsql" "$d/bin/prod" "$d/bin/api"
}
monta_falso "$DIR/mudo" MUDO
monta_falso "$DIR/cero" CERO
VACIO="$DIR/vacio.txt"; : > "$VACIO"
HUELLA="$DIR/huella.txt"; : > "$HUELLA"
export K97_HUELLA="$HUELLA"

# El doble tiene que salir BIEN y MUDO. Si no, todo lo de abajo mide otra cosa.
for m in mudo cero; do
  # (a) la sonda de vida se contesta: una poblacion vacia no tumba el canal.
  s=$("$DIR/$m/bin/prodsql" "SELECT 'canal_ok'" 2>&1); rc=$?
  [ "$rc" = 0 ] || { echo "NO MEDIDO: el doble $m sale rc=$rc; probaria un canal caido, no una poblacion vacia"; exit 2; }
  [ "$s" = canal_ok ] || { echo "NO MEDIDO: el doble $m no contesta la sonda de vida (dio '$s'); estaria fingiendo un canal caido"; exit 2; }
  # (b) una consulta de FILAS sobre tablas vuelve VACIA en los dos dobles: una tabla vacia no
  #     devuelve la linea '0', devuelve cero lineas.
  s=$("$DIR/$m/bin/prodsql" "SELECT ts FROM alguna_tabla WHERE ts > now()" 2>&1); rc=$?
  [ "$rc" = 0 ] || { echo "NO MEDIDO: el doble $m sale rc=$rc con una consulta con FROM"; exit 2; }
  [ -z "$s" ] || { echo "NO MEDIDO: el doble $m devolvio '$s' a una consulta de filas; una tabla vacia no devuelve nada"; exit 2; }
  # (c) y un RECUENTO: el mudo sigue mudo, el cero contesta 0. Es la unica diferencia entre ellos.
  s=$("$DIR/$m/bin/prodsql" "SELECT count(*) FROM alguna_tabla" 2>&1)
  case "$m" in
    mudo) [ -z "$s" ] || { echo "NO MEDIDO: el doble mudo contesto '$s' a un recuento"; exit 2; } ;;
    cero) [ "$s" = 0 ] || { echo "NO MEDIDO: el doble cero contesto '$s' y no 0 a un recuento"; exit 2; } ;;
  esac
done

# --- CLASIFICAR POR CANAL, con grep anclado sobre el propio fichero ------------------------
canal_de() {  # $1 = ruta del check
  grep -qE '\$\{K[0-9A-Za-z]+_FIXTURE' "$1" && { echo A; return; }
  grep -qE '\$\{K[0-9A-Za-z]+_(PRODSQL|PROD|API|CANAL)[:-]' "$1" && { echo B; return; }
  # SE BUSCA `bin/prodsql` DONDE SEA, no solo `"$B/bin/prodsql"`. K62-una-version-dos-reglas lo
  # arma desde python -`B + "/bin/prodsql"`, linea 117- y con el patron anclado salia como «sin
  # canal» cuando en realidad lee de 140 por el mismo sitio que los demas. El sed reescribe la
  # ruta este donde este, asi que lo unico que fallaba era el detector.
  grep -qE 'bin/(prodsql|prod|api)' "$1" && { echo C; return; }
  echo D
}
ventana_movil() {  # el sujeto son los checks que PUEDEN caducar
  # `now()` A SECAS YA CUENTA. El criterio anterior pedia `now() - interval`, y cuando K06
  # paso a comparar su umbral en shell dejo de casar: **se cayo del censo por culpa de su
  # propio arreglo**, que es la peor manera de perder un sujeto. Cualquier consulta que llame
  # a now() se mide contra el instante de correr, y eso es lo que puede caducar.
  grep -qE '^(DIAS|K[0-9a-z]+_DIAS|HORAS|VENTANA|K[0-9a-z]+_UMBRAL)=|--since|[Nn][Oo][Ww]\(\)|current_date *-|CURRENT_DATE *-|date -u -d "\$hoy -' "$1"
}

# --- CORRER UN SUJETO CONTRA UN DOBLE ------------------------------------------------------
# Devuelve el rc del check en la PRIMERA linea y su salida detras. El rc se toma directamente,
# no detras de una tuberia: `$?` tras un pipe es el del ultimo mandato y no el del sujeto.
corre_sujeto() {  # $1 = fichero del check   $2 = canal   $3 = mudo|cero
  local f="$1" can="$2" modo="$3" falso="$DIR/$3" copia="$DIR/$(basename "$f").$3" out rc
  # SE REESCRIBE LA RUTA DEL ARNES EN TODAS SUS FORMAS. La primera version solo cubria la
  # constante desnuda y se le escapaba `B=${K18_HARNESS:-/srv/coinanalyze/harness}`.
  sed -e "s#/srv/coinanalyze/harness#$falso#g" "$f" > "$copia"
  : > "$HUELLA"
  case "$can" in
    A) out=$(K97_HUELLA="$HUELLA" K86_FIXTURE="$VACIO" timeout -k 5 "$TOPE" bash "$copia" 2>&1); rc=$? ;;
    B) out=$(K97_HUELLA="$HUELLA" K90_PRODSQL="$falso/bin/prodsql" K92_PRODSQL="$falso/bin/prodsql" \
             K92_PROD="$falso/bin/prod" timeout -k 5 "$TOPE" bash "$copia" 2>&1); rc=$? ;;
    *) out=$(K97_HUELLA="$HUELLA" timeout -k 5 "$TOPE" bash "$copia" 2>&1); rc=$? ;;
  esac
  # Si el sujeto no llamo NI UNA VEZ a un doble, no se le dio ninguna poblacion vacia y su
  # veredicto no dice nada. Se marca con rc=99, que no es ninguno de los tres del arnes.
  # EL CANAL A NO PASA POR LOS DOBLES -su vacio es un fichero-, asi que su prueba de entrega es
  # que el check declare el fixture en su salida. Sin esta excepcion, el guardia escrito para
  # cazar el sed que no casaba dejaba fuera del censo justo al unico check de canal A.
  if [ "$can" = A ]; then
    printf '%s' "$out" | grep -qF "$VACIO" || rc=99
  else
    [ -s "$HUELLA" ] || rc=99
  fi
  printf '%s\n' "$rc"
  printf '%s\n' "$out"
}

# --- EL CENSO ------------------------------------------------------------------------------
enfermos=""; sanos=0; nojuzg=""; n=0; detalle=""; api_debil=""
for f in "$CHECKS"/*.sh; do
  c=$(basename "$f" .sh)
  case "$c" in K97-*) continue ;; esac       # no se juzga a si mismo: seria un espejo, no un control
  ventana_movil "$f" || continue
  n=$((n+1))
  can=$(canal_de "$f")
  if [ "$can" = D ]; then
    nojuzg="$nojuzg $c(sin-canal)"
    continue
  fi
  grep -qE '"?\$B/bin/api|/harness/bin/api' "$f" && api_debil="$api_debil $c"
  veredicto=SANO; porque=""
  for modo in mudo cero; do
    sal=$(corre_sujeto "$f" "$can" "$modo")
    rc=$(printf '%s\n' "$sal" | head -1)
    if [ "$rc" = 99 ]; then
      # NO TOCO EL DOBLE: no se le dio ninguna poblacion vacia, asi que no se le juzga.
      veredicto=NOJUZG; porque="no-llego-al-canal"; break
    fi
    if [ "$rc" = 0 ]; then
      veredicto=ENFERMO; porque="$modo"
      break
    fi
    [ "$rc" = 124 ] || [ "$rc" = 137 ] && { veredicto=NOJUZG; porque="agoto los ${TOPE}s"; break; }
  done
  case "$veredicto" in
    ENFERMO) enfermos="$enfermos $c";  detalle="$detalle  $c ENFERMO (sale VERDE con el doble $porque)
" ;;
    NOJUZG)  nojuzg="$nojuzg $c($porque)" ;;
    *)       sanos=$((sanos+1)) ;;
  esac
done

if [ "$n" -eq 0 ]; then
  echo "NO MEDIDO: cero checks con ventana movil en $CHECKS. O el arbol esta vacio o el criterio dejo de casar."
  exit 2
fi

# --- LOS DOS CONTROLES, y sin ellos no hay veredicto ---------------------------------------
# POSITIVO · un check que SI sabe declarar su vacio tiene que salir SANO. Si el instrumento
# marcara a todos, estaria tan roto como si no marcara a ninguno.
pos_ok=0; pos_n=0; pos_falla=""
for c in K92-el-minuto-que-miente K52-el-minuto-corto; do
  [ -r "$CHECKS/$c.sh" ] || continue
  pos_n=$((pos_n+1))
  case " $enfermos " in *" $c "*) pos_falla="$pos_falla $c" ;; *) pos_ok=$((pos_ok+1)) ;; esac
done
# NEGATIVO · un check de mentira que diga VERDE sobre cero. Si no lo caza, lo de arriba es
# decoracion. Se escribe aqui, se corre por el mismo camino, y se tira.
MENT="$DIR/Z99-miente.sh"
cat > "$MENT" <<'MENTIRA'
#!/bin/bash
# Ignora su entrada y vota. DIAS=7 para que case el criterio de ventana movil.
DIAS=7
B=/srv/coinanalyze/harness
filas=$("$B/bin/prodsql" "SELECT 1 FROM inventada WHERE ts > now() - interval '7 days'" 2>/dev/null)
echo "VERDE: todo en orden"
exit 0
MENTIRA
sal=$(corre_sujeto "$MENT" C mudo); neg_rc=$(printf '%s\n' "$sal" | head -1)
[ "$neg_rc" = 0 ] && neg_ok=si || neg_ok=NO

echo "K97 · el verde sin sujeto · $n check(s) con ventana movil, cada uno corrido contra una poblacion vacia"
echo "  canales: A fixture · B binario por entorno · C arnes de mentira por \$B · D sin canal (no se juzga)"
echo "  dobles: MUDO (cero filas, como psql -t sobre tabla vacia) y CERO (la linea '0', como un count)"
echo "  control POSITIVO: $pos_ok de $pos_n checks que YA declaran su vacio salen SANOS${pos_falla:+ · FALLAN:$pos_falla}"
echo "  control NEGATIVO: un check de mentira que vota VERDE sobre cero -> cazado=$neg_ok"
[ -n "$api_debil" ] && echo "  aviso: el doble de api es DEBIL (emite {}), asi que el SANO de estos vale menos:$api_debil"

if [ "$pos_n" -eq 0 ] || [ "$pos_ok" -ne "$pos_n" ] || [ "$neg_ok" != si ]; then
  echo "NO MEDIDO: los controles del propio instrumento no cuadran. Un censo que no se ha probado a si mismo no es un censo."
  echo "  positivo $pos_ok/$pos_n · negativo cazado=$neg_ok"
  exit 2
fi

n_enf=$(printf '%s' "$enfermos" | wc -w)
n_noj=$(printf '%s' "$nojuzg" | wc -w)
echo "  juzgados ejecutandolos: $((n - n_noj)) de $n · sanos: $sanos · enfermos: $n_enf · no juzgables: $n_noj"
[ -n "$nojuzg" ] && echo "  NO JUZGABLES, nombrados con su motivo:$nojuzg"
[ -n "$detalle" ] && printf '%s' "$detalle"

# --- DISPOSICIONES · el que no se arregla, se dispone CON SU CITA --------------------------
sin_dueno=""
for c in $enfermos; do
  if [ -r "$DISPOSICIONES" ] && grep -qE "^$c	" "$DISPOSICIONES"; then continue; fi
  sin_dueno="$sin_dueno $c"
done
n_sd=$(printf '%s' "$sin_dueno" | wc -w)
if [ "$n_sd" -gt 0 ]; then
  echo "ROJO: $n_sd check(s) salen VERDE con la poblacion vacia y no tienen disposicion:$sin_dueno"
  echo "  un check que ante cero sujetos dice «todo bien» no esta midiendo, esta votando."
  echo "  o se arregla, o se dispone en $(basename "$DISPOSICIONES") con su cita."
  exit 1
fi
echo "VERDE: ninguno de los $((n - n_noj)) juzgados sale VERDE sin sujeto sin estar dispuesto ($n_enf dispuesto(s))."
exit 0
