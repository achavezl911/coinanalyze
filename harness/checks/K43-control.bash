#!/usr/bin/env bash
# K43-control · ¿la tabla de asignaciones SIRVE, o es un adorno?
#
# K43 declara la familia de cada ruta en una cadena, `ASIGNACION="..."`, y de ahi salen dos
# afirmaciones distintas: «esta ruta tiene familia» y «esta familia cumple su promesa». Una tabla
# que no se leyera de verdad daria VERDE en la primera sin que nadie lo notara — y este check ya
# tuvo esa enfermedad una vez: hasta el 2026-08-26, para las rutas de FOTO solo comprobaba que
# existiera una clave con un nombre parecido, deducida por un heuristico, y cuatro pasaban con su
# contenido fuera (su propia cabecera lo cuenta).
#
# EL BRAZO QUE IMPORTA es el que pide el encargo: **quitar UNA asignacion tiene que volver a
# enrojecer a K43, y nombrando justo esa.** Se hace sobre una COPIA con un `sed`, que es el patron
# que K97 y K86-control ya usan: un arbol de mentira, no un mock.
#
# NECESITA 140: K43 pide las rutas por la API real, y no hay forma de inyectarle un cuerpo sin
# levantar un servidor. Si el canal no contesta, esto es NOMED y no un aprobado.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto de este fichero es el
# criterio, no produccion.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K43-foto-unica.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K43_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

QUITADA_ESPERADA=/api/scalp/signals   # la que usa el positivo; N1 la necesita por delante

echo "K43-control · sujeto: $CHK"
echo

# --- EL CANAL, ANTES DE NADA. Sin el, lo de abajo mide otra cosa -------------------------
base=$("$ORIG/harness/bin/api" "/api/healthz" 2>&1) || true
case "$base" in
  *status*|*ok*|*healthy*) ;;
  *) echo "NO MEDIDO: la API de 140 no contesta a /api/healthz, asi que no se puede pedir ninguna ruta"
     echo "  primera linea: $(printf '%s' "$base" | head -1 | cut -c1-110)"
     exit 2 ;;
esac

corre() {  # $1 = fichero del check   -> rc en la primera linea, salida detras
  local f="$1" out rc
  out=$(timeout -k 10 400 bash "$f" 2>&1); rc=$?
  printf '%s\n' "$rc"
  printf '%s\n' "$out"
}
comprueba() {  # $1 = etiqueta   $2 = si|no
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-58s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-58s\n' "$1"; fi
}

echo "NEGATIVO · con la tabla entera, la ruta del positivo NO sale sin familia"
sal=$(corre "$CHK"); rc0=$(printf '%s\n' "$sal" | head -1); out0=$(printf '%s\n' "$sal" | tail -n +2)
# OJO: K43 puede estar ROJO por otra razon -hoy lo esta, por «sin as_of», que es una promesa
# incumplida y no una familia ausente-. Lo que este brazo afirma es solo lo segundo.
#
# N1 SE REESCRIBIO EL 2026-09-09 Y NO SE AFLOJO. Decia «ninguna ruta sale sin familia», y era
# cierto cuando se escribio; hoy hay TRES que no tienen familia -carry/matriz, liquidation-map y
# rango/estructura- y son un ROJO legitimo, asi que la frase vieja convertia un hallazgo real en
# un fallo del control. Lo que N1 tiene que sostener es la LINEA BASE DEL POSITIVO: que la ruta
# que P1-P3 van a quitar NO aparece sin familia mientras su asignacion siga puesta. Sin eso, P3
# -«nombra justo la que se quito»- podria ser cierto por casualidad. El criterio no baja: sigue
# habiendo un negativo, y ahora apunta a lo que el positivo necesita.
comprueba "N1 con la tabla entera: $QUITADA_ESPERADA no sale sin familia" \
  "$(printf '%s' "$out0" | grep -q "no tienen familia asignada.*$QUITADA_ESPERADA" && echo no || echo si)"

echo
echo "POSITIVO · se quita UNA asignacion y tiene que enrojecer NOMBRANDOLA"
QUITADA=/api/scalp/signals
FALSO="$DIR/K43-sin-una.sh"
sed "s#$QUITADA=DEMANDA##" "$CHK" > "$FALSO"
# El sed tiene que haber MORDIDO. Si no, lo de abajo compararia el check consigo mismo y
# «no enrojece» seria un aprobado falso: es el mismo fallo que tuvo K97 con K18 anoche.
if cmp -s "$CHK" "$FALSO"; then
  echo "NO MEDIDO: el sed no cambio nada, asi que el positivo compararia el check consigo mismo"
  exit 2
fi
sal=$(corre "$FALSO"); rc1=$(printf '%s\n' "$sal" | head -1); out1=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "P1 sin la asignacion de $QUITADA: ROJO (rc=$rc1)" \
  "$([ "$rc1" = 1 ] && echo si || echo no)"
comprueba "P2 y dice que es una ruta SIN FAMILIA" \
  "$(printf '%s' "$out1" | grep -q 'no tienen familia asignada' && echo si || echo no)"
comprueba "P3 y NOMBRA justo la que se quito" \
  "$(printf '%s' "$out1" | grep -q "no tienen familia asignada.*$QUITADA" && echo si || echo no)"
# P4 · Y NO ARRASTRA A LAS OTRAS CUATRO. Un check que ante una tabla incompleta acusara a media
# pantalla seria inutil: hay que poder ir a la ruta que falta, no a una lista.
otras=0
for r in /api/signals/ledger /api/signals/replay /api/signals/execution /api/signals/visibility; do
  printf '%s' "$out1" | grep -q "no tienen familia asignada.*$r" && otras=$((otras+1))
done
comprueba "P4 y NO acusa a las otras cuatro (arrastradas: $otras)" \
  "$([ "$otras" -eq 0 ] && echo si || echo no)"

echo
echo "LA SONDA · preguntar mal no puede leerse como que la ruta incumple"
# EL DEFECTO QUE SE ARREGLO EL 2026-09-07: `cuerpo()` pedia TODA ruta con `&level&low&high`. Las
# cuatro de signals rechazan lo que no reconocen y contestan HTTP 422; `curl` sin `-f` entrega el
# cuerpo y sale 0, asi que el JSON del error pasaba por respuesta y K43 dictaminaba
# «DEMANDA: sin as_of». El veredicto hablaba de las rutas y en realidad hablaba de su peticion.
#
# EL CONTROL SE MUEVE: se hace una copia que vuelve a pegar los extras a TODAS -la forma vieja- y
# se exige que esas rutas salgan como NO JUZGADAS, **no como incumplidoras**. Una ruta que
# contesta bien y a la que preguntamos mal no esta incumpliendo nada.
MAL="$DIR/K43-preguntando-mal.sh"
# 2026-09-10 · este `sed` apuntaba a la expresion ENTERA de la url. Al aparecer CONSULTA -las
# rutas que no aceptan `symbol`- esa expresion pasa a dos lineas y el sed dejo de morder; el
# control lo canto solo y salio NO MEDIDO en vez de dar un aprobado falso. Se reapunta a la rama
# `else`, que es la que este brazo quiere estropear, y lo que exige no cambia.
sed 's#else "symbol=%s%s" % (sim, EXTRA.get(r, ""))#else "symbol=%s\&level=78800\&low=77000\&high=80000" % sim#' "$CHK" > "$MAL"
if cmp -s "$CHK" "$MAL"; then
  echo "NO MEDIDO: el sed no cambio nada, asi que este brazo compararia el check consigo mismo"
  exit 2
fi
sal=$(corre "$MAL"); rcm=$(printf '%s\n' "$sal" | head -1); outm=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "S1 preguntando mal, las rutas salen NO JUZGADAS" \
  "$(printf '%s' "$outm" | grep -q 'NO JUZGADAS' && echo si || echo no)"
# 2026-09-10 · S2 preguntaba si aparecia «sin as_of» EN NINGUN SITIO, y eso valia cuando ninguna
# ruta fallaba por ese motivo de verdad. Hoy fallan tres -level/breakout, range/validate y
# zone/analysis, destapadas al asignar las huerfanas-, asi que el brazo condenaba por culpa de
# rutas que no son las suyas. Se le acota el sujeto a las que ESTE brazo maltrata a proposito.
# No baja lo que exige: sigue siendo «a la que preguntamos mal no se la llama incumplidora».
comprueba "S2 y NO como incumplidoras de su familia" \
  "$(printf '%s' "$outm" | grep -qE '/api/(signals/[a-z]+|scalp/signals)\(DEMANDA' && echo no || echo si)"
comprueba "S3 y nombra el codigo que le contestaron" \
  "$(printf '%s' "$outm" | grep -q 'HTTP 422' && echo si || echo no)"
# S4 · EL NEGATIVO, sin el cual S1 seria una maquina de «no juzgadas»: preguntando BIEN no puede
# quedar ninguna sin juzgar.
sal=$(corre "$CHK"); outb=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "S4 preguntando bien no queda ninguna sin juzgar" \
  "$(printf '%s' "$outb" | grep -q 'NO JUZGADAS' && echo no || echo si)"
# S5 · y las tres rutas de NIVEL siguen recibiendo sus extras: son las unicas que los necesitan.
comprueba "S5 las tres de nivel conservan sus extras" \
  "$(grep -q '"/api/zone/analysis":   "&level=78800&low=77000&high=80000"' "$CHK" && echo si || echo no)"

echo
echo "LA CONSULTA · una ruta que no acepta symbol no se puede leer como incumplidora"
# ANADIDO EL 2026-09-10 con CONSULTA. /api/carry/matriz cubre los TRES perpetuos y rechaza
# `symbol` con un 422. Si el check le pega la peticion generica, ese 422 se leeria como «no
# cumple su familia» cuando lo que fallo fue la PREGUNTA. Se quita su linea de CONSULTA y tiene
# que salir NO JUZGADA -no incumplidora-, que es la misma exigencia que S1-S3 para las de signals.
SINQ="$DIR/K43-sin-consulta.sh"
sed 's#"/api/carry/matriz": "dias=15",##' "$CHK" > "$SINQ"
if cmp -s "$CHK" "$SINQ"; then
  echo "NO MEDIDO: el sed no cambio nada, asi que este brazo compararia el check consigo mismo"
  exit 2
fi
sal=$(corre "$SINQ"); outq=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "Q1 sin su CONSULTA, carry/matriz sale NO JUZGADA" \
  "$(printf '%s' "$outq" | grep -q 'NO JUZGADAS.*carry/matriz' && echo si || echo no)"
comprueba "Q2 y NO como incumplidora de SERIE" \
  "$(printf '%s' "$outq" | grep -q 'carry/matriz(SERIE' && echo no || echo si)"
# EL NEGATIVO: con su CONSULTA puesta, no puede quedarse sin juzgar.
comprueba "Q3 con su CONSULTA, SI se la juzga" \
  "$(printf '%s' "$out0" | grep -q 'NO JUZGADAS.*carry/matriz' && echo no || echo si)"

echo
echo "LA POBLACION · de donde sale el denominador, y que pasa si esa fuente se rompe"
# ANADIDO EL 2026-09-09, cuando la poblacion dejo de salir del log de nginx -un registro de
# visitas- y paso a salir de static/app.js. Un cambio de denominador puede aflojar un check sin
# que se note: basta con que el censo nuevo encuentre menos, o nada. B2 y B3 son el corazon,
# porque un censo roto que dijera «0 sin familia» seria un VERDE sobre cero rutas, que es
# exactamente la enfermedad que este check condena en otros.
corre_env() {  # $1 = fichero del check, resto = VAR=valor   -> rc en la primera linea
  local f="$1"; shift
  local out rc
  out=$(env "$@" timeout -k 10 400 bash "$f" 2>&1); rc=$?
  printf '%s\n' "$rc"
  printf '%s\n' "$out"
}
printf 'const nada = 1;\n' > "$DIR/sin-rutas.js"
grep -v '/api/ohlcv'   "$ORIG/static/app.js" > "$DIR/sin-control.js"
grep -v '/api/wyckoff' "$ORIG/static/app.js" > "$DIR/sin-wyckoff.js"

# 2026-09-10 · B1 buscaba el denominador en el mensaje de «sin familia», y ese mensaje ya no se
# imprime porque ya no hay ninguna. El denominador no se ha perdido: se ha mudado a la cola, que
# lo dice por los DOS caminos y aunque valga cero. El brazo se reapunta ahi, y de paso exige mas
# que antes -antes solo salia por el camino del rojo por familia ausente-.
comprueba "B1 la salida DICE el denominador, no solo el numerador" \
  "$(printf '%s' "$out0" | grep -qE 'SIN FAMILIA: [0-9]+ de [0-9]+ del censo' && echo si || echo no)"

sal=$(corre_env "$CHK" K43_APP_JS="$DIR/sin-rutas.js")
rcb=$(printf '%s\n' "$sal" | head -1); outb2=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "B2 censo vacio: NO MEDIDO y no VERDE (rc=$rcb)" \
  "$([ "$rcb" = 2 ] && printf '%s' "$outb2" | grep -q 'da 0 rutas' && echo si || echo no)"

sal=$(corre_env "$CHK" K43_APP_JS="$DIR/sin-control.js")
rcb=$(printf '%s\n' "$sal" | head -1); outb3=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "B3 falta una ruta de CONTROL: NO MEDIDO (rc=$rcb)" \
  "$([ "$rcb" = 2 ] && printf '%s' "$outb3" | grep -q 'faltan los controles /api/ohlcv' && echo si || echo no)"

# B4 · EL CAMBIO QUE MAS IMPORTA. Con el log de denominador, un log vacio era NO MEDIDO: el
# check dejaba de medir porque no habia visitas. Ahora el log no decide, asi que sigue midiendo.
sal=$(corre_env "$CHK" K43_PEDIDAS="")
rcb=$(printf '%s\n' "$sal" | head -1); outb4=$(printf '%s\n' "$sal" | tail -n +2)
# 2026-09-10 · mismo motivo que B1: el denominador se lee ahora de la cola.
comprueba "B4 log VACIO: sigue midiendo, no NO MEDIDO (rc=$rcb)" \
  "$([ "$rcb" != 2 ] && printf '%s' "$outb4" | grep -qE 'SIN FAMILIA: [0-9]+ de [0-9]+ del censo' && echo si || echo no)"

# B5 · la reproducibilidad, que era el defecto entero. Dos pasadas seguidas, misma primera linea.
b5a=$(printf '%s' "$out0" | head -1)
sal=$(corre "$CHK"); b5b=$(printf '%s\n' "$sal" | tail -n +2 | head -1)
comprueba "B5 dos pasadas seguidas dan la MISMA primera linea" \
  "$([ -n "$b5a" ] && [ "$b5a" = "$b5b" ] && echo si || echo no)"

# B6 · LA OTRA DIRECCION. Hoy el cementerio vale 0, y un cero solo vale si el brazo sabe no
# valerlo: se le quita una ruta al panel dejandole la familia puesta y tiene que delatarla.
sal=$(corre_env "$CHK" K43_APP_JS="$DIR/sin-wyckoff.js")
outb6=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "B6 con familia y sin llamada: la delata como CEMENTERIO" \
  "$(printf '%s' "$outb6" | grep -qE 'CEMENTERIO: 1 de [0-9]+ con familia que el panel ya NO llama: /api/wyckoff' && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
