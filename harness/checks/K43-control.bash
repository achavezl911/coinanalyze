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

echo "NEGATIVO · con la tabla entera, NINGUNA ruta se queda sin familia"
sal=$(corre "$CHK"); rc0=$(printf '%s\n' "$sal" | head -1); out0=$(printf '%s\n' "$sal" | tail -n +2)
# OJO: K43 puede estar ROJO por otra razon -hoy lo esta, por «sin as_of», que es una promesa
# incumplida y no una familia ausente-. Lo que este brazo afirma es solo lo segundo.
comprueba "N1 con la tabla entera: ninguna 'sin familia'" \
  "$(printf '%s' "$out0" | grep -q 'no tienen familia asignada' && echo no || echo si)"

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
sed 's#base + r + "?symbol=%s%s" % (sim, EXTRA.get(r, ""))#base + r + "?symbol=%s\&level=78800\&low=77000\&high=80000" % sim#' "$CHK" > "$MAL"
if cmp -s "$CHK" "$MAL"; then
  echo "NO MEDIDO: el sed no cambio nada, asi que este brazo compararia el check consigo mismo"
  exit 2
fi
sal=$(corre "$MAL"); rcm=$(printf '%s\n' "$sal" | head -1); outm=$(printf '%s\n' "$sal" | tail -n +2)
comprueba "S1 preguntando mal, las rutas salen NO JUZGADAS" \
  "$(printf '%s' "$outm" | grep -q 'NO JUZGADAS' && echo si || echo no)"
comprueba "S2 y NO como incumplidoras de su familia" \
  "$(printf '%s' "$outm" | grep -q 'sin as_of' && echo no || echo si)"
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
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
