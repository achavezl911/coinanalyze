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
fallos=0; pasan=0; declarados=0

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
declara() {  # lo que este control ya no puede ejercitar, con su medida al lado
  declarados=$((declarados+1)); printf '  [decl ] %-58s\n         %s\n' "$1" "$2"
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
# EL PANEL SON N MODULOS (FASE 2). Hasta COLA 124 estas tres lineas grepeaban
# `$ORIG/static/app.js`, que ya no existe: los ficheros salian VACIOS y el control moria en
# `SED-NO-MORDIO` -apagado, sin medir nada-. El censo se toma de donde lo toma el propio check:
# del descubridor, concatenando los modulos que el HTML declara.
PANEL_CAT="$DIR/panel.js"
if ! "${VENV_PY:-$ORIG/.venv/bin/python}" "$ORIG/harness/bin/panel-fuentes" \
       --repo "$ORIG" --cat > "$PANEL_CAT" 2>"$DIR/pf.err"; then
  echo "NO MEDIDO: no se pudieron descubrir las fuentes del panel: $(head -c 200 "$DIR/pf.err")"
  exit 2
fi
printf 'const nada = 1;\n' > "$DIR/sin-rutas.js"
grep -v '/api/ohlcv'   "$PANEL_CAT" > "$DIR/sin-control.js"
grep -v '/api/wyckoff' "$PANEL_CAT" > "$DIR/sin-wyckoff.js"

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
#
# 2026-09-10 · LA ETIQUETA SE PRECISA Y EL BRAZO NO CAMBIA. Lo que planta esto no es «un log
# vacio»: es una INYECCION vacia, y desde hoy son estados distintos -el check dice cual de los
# dos es-. El brazo sigue exigiendo lo mismo, que es que el check SIGA MIDIENDO; lo que se
# corrige es lo que el rotulo afirmaba plantar. Los estados del log se prueban en LOS SEIS
# ESTADOS, mas abajo.
sal=$(corre_env "$CHK" K43_PEDIDAS="")
rcb=$(printf '%s\n' "$sal" | head -1); outb4=$(printf '%s\n' "$sal" | tail -n +2)
# 2026-09-10 · mismo motivo que B1: el denominador se lee ahora de la cola.
comprueba "B4 inyeccion VACIA: sigue midiendo, no NO MEDIDO (rc=$rcb)" \
  "$([ "$rcb" != 2 ] && printf '%s' "$outb4" | grep -qE 'SIN FAMILIA: [0-9]+ de [0-9]+ del censo' && echo si || echo no)"

# B5 · la reproducibilidad, que era el defecto entero. Dos pasadas seguidas, misma primera linea.
b5a=$(printf '%s' "$out0" | head -1)
sal=$(corre "$CHK"); b5b=$(printf '%s\n' "$sal" | tail -n +2 | head -1)
comprueba "B5 dos pasadas seguidas dan la MISMA primera linea" \
  "$([ -n "$b5a" ] && [ "$b5a" = "$b5b" ] && echo si || echo no)"

# B6 · LA OTRA DIRECCION: EL CEMENTERIO -rutas CON familia que el panel ya NO llama-. Hoy vale
# 0, y un cero solo vale si el brazo sabe NO valerlo: se le quita una ruta al panel dejandole la
# familia puesta, y el check tiene que delatarla POR SU NOMBRE.
#
# POR QUE DEJO DE EJERCITARSE, Y ES EL PUNTO DE COLA 125. Este brazo elegia la candidata entre
# las rutas de **FOTO**, y desde la FASE 1 TODAS las de FOTO viajan dentro del sobre: K43 las
# RE-ACREDITA por la tabla `PAREJAS` aunque su literal no este en el panel
# (K43-foto-unica.sh:414-419, `if SOBRE in panel: ... panel.append(_ruta)`). Asi que quitar el
# literal no movia el cementerio, el brazo se declaraba NO EJERCITABLE en CADA corrida, y nadie
# podia decir que el cementerio de K43 sepa condenar. La candidata estaba mal elegida, no el
# brazo: hay 21 rutas con familia que NO viajan en el sobre.
#
# LA CANDIDATA SE DERIVA, NO SE TECLEA, con cinco filtros que salen todos del propio check:
#   1 tiene familia en `ASIGNACION`   si no, no seria cementerio sino «sin familia», otro brazo
#   2 NO esta en `PAREJAS`            el sobre la re-acreditaria y el plantado no mordería
#   3 NO esta en `CONTROL`            quitarla da NO MEDIDO, que es justo lo que mide B3
#   4 ES literal del panel            si no, no hay nada que quitar
#   5 EL PLANTADO SE COMPRUEBA: quitarla tiene que dejar el panel con EXACTAMENTE UNA ruta
#     menos, y esa una tiene que ser ella
# EL FILTRO 5 NO ES UNA HEURISTICA DE PREFIJO, Y LA PRIMERA VERSION SI LO ERA. `grep -v` borra
# LINEAS, asi que quitar `/api/oi` se lleva por delante `/api/oi-context` -y `/api/oi` quita 6
# lineas del panel, medido-. Comparar solo contra las rutas de `ASIGNACION` no basta: en el
# panel hay literales `/api/...` que no tienen familia y tambien se los lleva. Asi que no se
# adivina: se compara el CONJUNTO de rutas del panel antes y despues, y la diferencia tiene que
# ser exactamente la candidata. Eso cubre de paso a las de CONTROL -si se fueran, K43 saldria
# NO MEDIDO y este brazo estaria midiendo el anti-fantasma en vez del cementerio-.
# Lo que no pasa el filtro se DICE, con su nombre y su motivo.
ASIG_DEL_CHECK=$(sed -n '/^ASIGNACION="$/,/^"$/p' "$CHK" | tr ' ' '\n' \
                 | grep '=' | sed 's/=.*//' | grep '^/api/' | sort -u)
[ -n "$ASIG_DEL_CHECK" ] || { echo 'NO MEDIDO: no se pudo leer la ASIGNACION de K43'; exit 2; }
PAREJAS_DEL_CHECK=$(sed -n '/^PAREJAS="$/,/^"$/p' "$CHK" \
                    | awk -F'|' 'NF>1{gsub(/ /,"",$1); if($1!="")print $1}' | sort -u)
CONTROL_DEL_CHECK=$(grep -oE '^CONTROL = \[.*\]' "$CHK" | grep -oE '/api/[a-z0-9/_-]+' | tr '\n' ' ')
_PAR=" $(printf '%s' "$PAREJAS_DEL_CHECK" | tr '\n' ' ') "
rutas_de() { grep -oE '/api/[a-zA-Z0-9/_-]+' "$1" | sort -u; }
rutas_de "$PANEL_CAT" > "$DIR/rutas-antes.txt"
B6RUTA=""; B6DESCARTES=""
for r in $ASIG_DEL_CHECK; do
  case "$_PAR" in *" $r "*) continue ;; esac
  case " $CONTROL_DEL_CHECK " in *" $r "*) continue ;; esac
  grep -qF -- "$r" "$PANEL_CAT" || continue
  grep -v -- "$r" "$PANEL_CAT" > "$DIR/sin-una.js"
  rutas_de "$DIR/sin-una.js" > "$DIR/rutas-despues.txt"
  _perdidas=$(comm -23 "$DIR/rutas-antes.txt" "$DIR/rutas-despues.txt" | tr '\n' ' ')
  if [ "$(printf '%s' "$_perdidas" | wc -w)" != 1 ] || [ "${_perdidas% }" != "$r" ]; then
    B6DESCARTES="$B6DESCARTES $r(se-lleva:${_perdidas:-nada})"
    continue
  fi
  B6RUTA=$r; break
done
if [ -z "$B6RUTA" ]; then
  # SOLO AQUI se declara: cuando NO QUEDA NADA QUE PLANTAR. Mientras quede una candidata, este
  # brazo pasa o falla.
  declara "B6 NO EJERCITABLE: no queda ninguna ruta que plantar" \
          "de las $(printf '%s\n' "$ASIG_DEL_CHECK" | wc -l) con familia, ninguna pasa los cinco filtros. Descartadas:${B6DESCARTES:- ninguna}"
else
  quitadas=$(( $(wc -l < "$PANEL_CAT") - $(wc -l < "$DIR/sin-una.js") ))
  # B6a · LA LINEA BASE. Sin ella, B6b podria ser cierto por casualidad -una ruta que ya
  # estuviera en el cementerio saldria nombrada con plantado y sin el-.
  comprueba "B6a arbol real: el cementerio NO nombra a $B6RUTA" \
    "$(printf '%s' "$out0" | grep -q "CEMENTERIO:.*$B6RUTA" && echo no || echo si)"
  sal=$(corre_env "$CHK" K43_APP_JS="$DIR/sin-una.js")
  outb6=$(printf '%s\n' "$sal" | tail -n +2)
  comprueba "B6b plantado ($B6RUTA, $quitadas linea(s)): la delata como CEMENTERIO" \
    "$(printf '%s' "$outb6" | grep -qE "CEMENTERIO: [0-9]+ de [0-9]+ con familia que el panel ya NO llama:.*$B6RUTA" && echo si || echo no)"
  # B6c · Y NO SE LLEVA A LAS DEMAS POR DELANTE: el cementerio del plantado tiene que valer
  # EXACTAMENTE uno mas que el del arbol real. Sin esto, un `grep -v` que borrara media docena
  # de rutas pasaria B6b igual, nombrando la suya entre otras cinco.
  _c0=$(printf '%s' "$out0"   | grep -oE 'CEMENTERIO: [0-9]+ de' | grep -oE '[0-9]+' | head -1)
  _c1=$(printf '%s' "$outb6"  | grep -oE 'CEMENTERIO: [0-9]+ de' | grep -oE '[0-9]+' | head -1)
  comprueba "B6c el cementerio pasa de ${_c0:-?} a ${_c1:-?}: UNA mas, no seis" \
    "$([ -n "${_c0:-}" ] && [ -n "${_c1:-}" ] && [ "$_c1" = "$(( _c0 + 1 ))" ] && echo si || echo no)"
fi

echo
echo "LOS SEIS ESTADOS DEL LOG · el veredicto NO cambia; lo que tiene que cambiar es la SALIDA"
# ANADIDO EL 2026-09-10. La linea informativa de K43 afirma que ciertas rutas no las pidio
# ningun navegador. Ese dato viene por un canal DISTINTO del que da el criterio, y hasta hoy una
# sustitucion de mandato que fallaba devolvia cadena vacia: lo mismo que un log sin peticiones.
# Medido: con el canal caido la linea decia «44 que el panel puede pedir y ningun navegador
# pidio» -44 de 44, la afirmacion falsa mas grande que ese renglon puede hacer-.
#
# SE COMPARAN SALIDAS Y NO `rc` A PROPOSITO: el veredicto no cambia entre estos estados, porque
# el criterio de K43 se mide por otro canal y ya se midio entero. Un control que los separase por
# el rc estaria midiendo otra cosa (A36).
#
# El arnes de mentira solo necesita dos piezas: K43 usa `$B/env` (linea 56) y `$B/bin/prod`.
montalog() {  # $1 = dir  $2 = rc del prod falso  $3 = lo que escribe
  rm -rf "$1"; mkdir -p "$1/bin"
  printf %s\\n ". /srv/coinanalyze/harness/env" > "$1/env"
  { printf %s\\n "#!/bin/bash"
    printf %s\\n "printf 'LLAMADO\\n' >> $1/senal"
    printf "printf '%%s\\n' '%s'\\n" "$3"
    printf %s\\n "exit $2"
  } > "$1/bin/prod"
  chmod +x "$1/bin/prod"
  # EL DESCUBRIDOR TAMBIEN VIVE EN `$B/bin`. Desde la FASE 2, K43 saca el censo del panel
  # con `$B/bin/panel-fuentes`; sin el en el arnes de mentira, los seis brazos del log
  # salian NO MEDIDO por el canal y no por lo que dicen medir.
  ln -sf "$ORIG/harness/bin/panel-fuentes" "$1/bin/panel-fuentes"
  : > "$1/senal"
}
copialog() {  # $1 = dir del arnes falso
  local f="$1/K43.sh"
  # EL ANCLA SE MIDE, NO SE RECUERDA. Hasta COLA 124 este sed buscaba
  # `B=/srv/coinanalyze/harness; . "$B/env"` en UNA linea, y en K43 son DOS desde que el
  # check aprendio a apuntarse a otro arbol: el sed no mordia, `copialog` devolvia 1 y el
  # control entero moria en SED-NO-MORDIO sin medir nada.
  sed "s#^B=/srv/coinanalyze/harness\$#B=$1#" "$CHK" > "$f"
  if cmp -s "$CHK" "$f"; then echo "SED-NO-MORDIO" >&2; return 1; fi
  printf %s\\n "$f"
}

montalog "$DIR/mudo" 3 ""
fm=$(copialog "$DIR/mudo") || exit 2
salm=$(corre "$fm"); rcm=$(printf %s\\n "$salm" | head -1); outm=$(printf %s\\n "$salm" | tail -n +2)
comprueba "L0 el plantado ocurrio: el prod de mentira se llamo" \
  "$([ -s "$DIR/mudo/senal" ] && echo si || echo no)"
comprueba "L1 canal MUDO: dice que NO pudo mirar, y no afirma nada" \
  "$(printf %s "$outm" | grep -q "EL LOG NO SE PUDO MIRAR (bin/prod rc=3)" && echo si || echo no)"
comprueba "L2 canal MUDO: NO dice que nadie pidio nada" \
  "$(printf %s "$outm" | grep -q "ningun navegador pidio" && echo no || echo si)"

montalog "$DIR/vacio" 0 ""
fv=$(copialog "$DIR/vacio") || exit 2
salv=$(corre "$fv"); rcv=$(printf %s\\n "$salv" | head -1); outv=$(printf %s\\n "$salv" | tail -n +2)
comprueba "L3 canal CONTESTA y cero peticiones: lo publica como HECHO" \
  "$(printf %s "$outv" | grep -q "el log CONTESTO y no registra NINGUNA peticion" && echo si || echo no)"

# EL BRAZO QUE JUSTIFICA LA CAMPANA: antes estos dos daban la MISMA linea.
# Se comparan las SALIDAS ENTERAS y no un trozo extraido: cualquier recorte mio podria
# igualarlas por accidente, y B5 ya prueba que dos pasadas de la misma configuracion dan la
# misma linea, asi que una diferencia aqui sale del estado plantado y no del reloj.
comprueba "L4 MUDO y CERO-PETICIONES dan salidas DISTINTAS" \
  "$([ "$outm" != "$outv" ] && echo si || echo no)"
# ...y el veredicto NO cambia entre ellos, que es la decision del operador.
comprueba "L5 y el VEREDICTO no cambia entre los dos (rc $rcm vs $rcv)" \
  "$([ "$rcm" = "$rcv" ] && echo si || echo no)"

montalog "$DIR/ileg" 0 "zcat: access.log.2.gz: No such file"
fi_=$(copialog "$DIR/ileg") || exit 2
sali=$(corre "$fi_"); outi=$(printf %s\\n "$sali" | tail -n +2)
comprueba "L6 canal contesta ILEGIBLE: lo dice y no afirma nada" \
  "$(printf %s "$outi" | grep -q "NINGUNA se pudo leer" && echo si || echo no)"

sal7=$(corre_env "$CHK" K43_PEDIDAS="")
out7=$(printf %s\\n "$sal7" | tail -n +2)
comprueba "L7 dato INYECTADO: el sobre dice que no vino del canal" \
  "$(printf %s "$out7" | grep -q "dato INYECTADO por K43_PEDIDAS" && echo si || echo no)"
comprueba "L8 canal REAL con datos: la cuenta lleva denominador" \
  "$(printf %s "$out0" | grep -qE "informativo, no criterio: [0-9]+ de [0-9]+" && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan${declarados:+ · $declarados DECLARADO(S) sin ejercitar}"
[ "$fallos" -eq 0 ] || exit 1
exit 0
