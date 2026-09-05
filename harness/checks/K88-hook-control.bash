#!/bin/bash
# K88-hook-control · LOS BRAZOS DEL HOOK, INDUCIDOS EN UN REPO DE VERDAD.
#
# El sujeto es harness/hooks/pre-commit, que decide que entra al repo. Se prueba haciendo
# COMMITS REALES en un repositorio temporal, no leyendo el fichero: un hook que "parece
# correcto" y no se ejecuta es la forma exacta del fallo que este arnes persigue.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y su marcador es del operador.
# Mismo patron que K88-control.bash y K86-control.bash. Corre sin red y sin base de datos.
set -uo pipefail

ORIG=${K88_HOOK_REPO:-/srv/coinanalyze/repo}
HOOK="$ORIG/harness/hooks/pre-commit"
[ -r "$HOOK" ] || { echo "NO MEDIDO: no encuentro el hook en $HOOK"; exit 2; }
command -v git >/dev/null 2>&1 || { echo "NO MEDIDO: no hay git"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "NO MEDIDO: no hay python3"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K88_HOOK_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

# --- un repo de verdad, minimo pero con lo que el hook necesita mirar -------------------
LIMPIO="$DIR/limpio"
mkdir -p "$LIMPIO/harness/bin" "$LIMPIO/harness/hooks" "$LIMPIO/sql"
cp -r "$ORIG/app" "$LIMPIO/app" 2>/dev/null || { echo "NO MEDIDO: no puedo copiar app/"; exit 2; }
cp "$ORIG/sql/schema.sql" "$LIMPIO/sql/" || exit 2
cp "$ORIG/harness/bin/arquitectura" "$LIMPIO/harness/bin/" || exit 2
cp "$HOOK" "$LIMPIO/harness/hooks/" || exit 2
rm -rf "$LIMPIO/app/__pycache__"
python3 "$LIMPIO/harness/bin/arquitectura" --repo "$LIMPIO" >/dev/null 2>&1 || {
  echo "NO MEDIDO: el generador no corre sobre la copia"; exit 2; }

(
  cd "$LIMPIO" || exit 2
  git init -q .
  git config user.email c@c; git config user.name c
  git config commit.gpgsign false
  # el commit base va SIN hook: es el punto de partida, no el sujeto.
  # Y va SIN ARQUITECTURA/, para que el caso "primer commit del mapa" tenga algo que
  # commitear: con la carpeta ya dentro del base, N1 y N2 daban "nothing to commit" y
  # pasaban por no haber ejercitado nada.
  git add -A -- ':!ARQUITECTURA' >/dev/null 2>&1
  git -c core.hooksPath=/dev/null commit -qm base >/dev/null 2>&1
) || { echo "NO MEDIDO: no se pudo preparar el repo"; exit 2; }

# caso <nombre> <rc esperado> <patron en la salida> <entorno> -- cuerpo que prepara $T
caso() {
  local nombre="$1" esperado="$2" patron="$3" entorno="$4"; shift 4
  # UN CASO SIN CUERPO NO ES UN CASO. Se olvido el argumento `normal` en dos llamadas y
  # `entorno` se comio el nombre de la funcion: `$@` quedo vacio, el cuerpo no indujo nada
  # y los dos casos se pasaron media hora "fallando" por una razon que no era la suya.
  # Un argumento de mas o de menos no puede degradar un control en silencio.
  if [ "$#" -eq 0 ]; then
    fallos=$((fallos+1))
    printf '  [FALLA] %-50s SIN CUERPO: ¿falta el argumento de entorno?\n' "$nombre"
    return
  fi
  case "$entorno" in
    normal|escape) ;;
    *) fallos=$((fallos+1))
       printf '  [FALLA] %-50s entorno invalido "%s"\n' "$nombre" "$entorno"; return ;;
  esac
  # UN DIRECTORIO NUEVO POR CASO. Reutilizar siempre `$DIR/t` con `rm -rf` + `cp -r`
  # dejaba, a partir del segundo caso que usaba la segunda base, un arbol que no era el
  # que el caso creia: el cuerpo corria con rc=0, no cambiaba nada, y `git commit` decia
  # "nothing to commit". Un caso que no induce nada puede acertar el rc por casualidad.
  T="$DIR/c$((pasan + fallos + 1))"
  rm -rf "$T"; cp -r "${BASE:-$LIMPIO}" "$T"
  ln -sfn ../../harness/hooks/pre-commit "$T/.git/hooks/pre-commit"
  # EL CUERPO NO PUEDE FALLAR EN SILENCIO. Antes esto era `>/dev/null 2>&1` a secas, y un
  # cuerpo que reventaba dejaba el arbol intacto: `git commit` decia "nothing to commit",
  # el rc coincidia por casualidad con el esperado en algun caso, y el control aprobaba
  # sin haber inducido nada. Se paga un poco de ruido a cambio de que un control mudo no
  # se confunda con un control que pasa.
  local prep prc
  prep=$( cd "$T" && "$@" 2>&1 ); prc=$?
  local out rc
  out=$(cd "$T" && git add -A >/dev/null 2>&1
        if [ "$entorno" = "escape" ]; then HARNESS_DOC=1 git commit -m prueba 2>&1
        else git commit -m prueba 2>&1; fi); rc=$?
  local ok=1
  [ "$rc" = "$esperado" ] || ok=0
  # HUELLA POSITIVA: el rc solo no vale. Un rechazo por OTRA razon contaria como acierto.
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  # GUARDIA ANTI-FANTASMA, Y NO ES TEORICO: la primera corrida de este control dio
  # "2 de 18 pasan" y esos DOS pasaban porque el hook no era ejecutable y git lo ignoraba
  # entero. Los casos que esperan rc=0 no tienen patron que exigir -no hay mensaje cuando
  # todo va bien-, asi que sin esto un hook desinstalado los aprueba TODOS. Es la misma
  # forma del C11 de K05: un control que pasa por no haber ejecutado nada.
  if printf '%s' "$out" | grep -q 'hook was ignored'; then
    ok=0; out="EL HOOK NO SE EJECUTO (git lo ignora: ¿falta el bit +x?). $out"
  fi
  # Y si el cuerpo no dejo NADA que commitear, el caso no indujo la averia que dice
  # inducir: no se juzga su rc, se declara roto el caso.
  if printf '%s' "$out" | grep -q 'nothing to commit'; then
    ok=0
    out="EL CASO NO INDUJO NADA (nada que commitear). cuerpo rc=$prc: $(printf '%s' "$prep" | tail -2 | tr '\n' ' ')"
  fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-50s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-50s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -3 | tr '\n' ' ' | cut -c1-160)"
  fi
}

echo "K88-hook-control · sujeto: $HOOK"
echo

# ======================================================================================
# NEGATIVO · lo que TIENE que pasar. Es el brazo que decide si el hook sirve: si
# ARQUITECTURA/ necesitara el escape en cada commit, el escape se volveria rutina y el
# filtro de libretas estaria apagado siempre, que es de donde venimos.
# ======================================================================================
echo "NEGATIVO · ARQUITECTURA/ regenerado pasa SIN HARNESS_DOC"

n1() { python3 harness/bin/arquitectura --repo . >/dev/null 2>&1
       touch ARQUITECTURA/rutas/api-setup.md; }
caso "N1 ARQUITECTURA/ regenerada, sin escape" 0 "" normal n1

# N2 · un .md nuevo bajo ARQUITECTURA/ que el generador SI produce.
n2() { python3 harness/bin/arquitectura --repo . >/dev/null 2>&1; }
caso "N2 primer commit de ARQUITECTURA/ entera" 0 "" normal n2

# N3 · un fichero que no es .md sigue pasando sin ruido.
n3() { printf 'x = 1\n' > app/_control_hook.py; }
caso "N3 un .py nuevo no le interesa al hook" 0 "" normal n3

echo
# ======================================================================================
# POSITIVO · lo que tiene que seguir rechazando.
# ======================================================================================
echo "POSITIVO · lo que sigue rechazado"

p1() { printf '# notas\n' > NOTAS.md; }
caso "P1 .md nuevo fuera de ARQUITECTURA/" 1 "\.md nuevo rechazado" normal p1

p2() { mkdir -p docs; printf '# plan\n' > docs/PLAN.md; }
caso "P2 .md nuevo en docs/" 1 "\.md nuevo rechazado" normal p2

# P3 · EL CASO QUE MOTIVA EL CAMBIO: ARQUITECTURA/ EDITADA A MANO.
# El hook tiene que rechazarlo aunque el fichero este bajo ARQUITECTURA/. Si esto pasara,
# el hook seria una lista blanca por carpeta y no una comprobacion.
p3() { python3 harness/bin/arquitectura --repo . >/dev/null 2>&1
       sed -i 's/`symbol`/`inventado`/' ARQUITECTURA/rutas/api-setup.md; }
caso "P3 ARQUITECTURA/ editada a mano" 1 "NO coincide con su regeneracion" normal p3

echo
# ======================================================================================
# CAPA DECLARADA (F3) · el hook tiene que dejarla vivir.
# Si commitear una declaracion escrita a mano exigiera regenerar o usar el escape, la capa
# que necesita a una persona seria la mas cara de mantener, y en dos semanas nadie la
# tocaria. La asimetria con la derivada es lo que hace que el mecanismo sirva.
# ======================================================================================
echo "DECLARADA · el hook la deja pasar; a la derivada editada a mano no"

# SEGUNDA BASE, con ARQUITECTURA/ y una declarada YA commiteadas y regeneradas: es el
# estado normal a partir del cual se edita a mano.
#
# Se prepara UNA VEZ aqui y no dentro de cada caso. Encadenar `regenerar + add + commit`
# dentro del cuerpo del caso resulto fragil -el commit intermedio no llegaba a ocurrir y
# los casos pasaban o fallaban por la razon equivocada; HD1 llego a dar rc=0 sin haber
# ejercitado nada-. Un control que depende de que tres ordenes encadenadas salgan bien es
# un control que a veces mide otra cosa.
BASE2="$DIR/base2"
cp -r "$LIMPIO" "$BASE2"
(
  cd "$BASE2" || exit 2
  mkdir -p ARQUITECTURA/declarada
  printf '# X\n\n## PREGUNTA\nq\n\n## VENTANA\nv\n\n## PROMESA\np\n\n## SUPERFICIE\ns\n' \
    > ARQUITECTURA/declarada/api-setup.md
  python3 harness/bin/arquitectura --repo . >/dev/null 2>&1
  git add -A
  git -c core.hooksPath=/dev/null commit -qm base-con-declarada
) >/dev/null 2>&1
# HUELLA: si la segunda base no quedo commiteada, los tres casos de abajo medirian otra
# cosa. Se comprueba en vez de suponerlo.
if [ -n "$(git -C "$BASE2" status --porcelain 2>/dev/null)" ]; then
  echo "NO MEDIDO: la base con declarada no quedo limpia; los casos HD no medirian nada"
  exit 2
fi

BASE="$BASE2"

# H-D1 · (a) del encargo: editar la PROSA de una declarada, SIN regenerar y SIN escape,
# pasa el hook. Es el 99 % de las ediciones de esta capa.
hd1() { printf '\nprosa escrita a mano despues de commitear.\n' \
          >> ARQUITECTURA/declarada/api-setup.md; }
caso "HD1 prosa de una declarada, sin escape ni regenerar" 0 "" normal hd1

# H-D2 · EL LIMITE, medido en vez de supuesto: CREAR una declarada nueva SI exige
# regenerar, porque cambia el estado `existe` de la ficha derivada. No es un fallo: es la
# frontera del mecanismo -la ESTRUCTURA esta guardada, la PROSA no- y conviene que este
# escrita con su rc. Quien anada una declaracion, regenera; quien la edite, no.
hd2() { printf '# Y\n\n## PREGUNTA\nq\n\n## VENTANA\nv\n\n## PROMESA\np\n\n## SUPERFICIE\ns\n' \
          > ARQUITECTURA/declarada/api-snapshot.md; }
caso "HD2 declarada NUEVA sin regenerar: hay que regenerar" 1 "NO coincide con su regeneracion" normal hd2

# H-D3 · la asimetria, en el mismo commit: se edita la prosa de la declarada Y la ficha
# derivada. El hook rechaza por la derivada, no por la declarada.
hd3() { printf '\nprosa a mano.\n' >> ARQUITECTURA/declarada/api-setup.md
        sed -i 's/`symbol`/`inventado`/' ARQUITECTURA/rutas/api-setup.md; }
caso "HD3 prosa OK pero derivada tocada: RECHAZA" 1 "NO coincide con su regeneracion" normal hd3

# el resto de casos vuelve a la base sin ARQUITECTURA/ commiteada
BASE="$LIMPIO"

echo
# ======================================================================================
# EL LIMITE DEL HOOK, DECLARADO Y PROBADO EN VEZ DE CALLADO.
# ======================================================================================
echo "LIMITE · lo que el hook NO vigila, a proposito"

# P4 · ruta nueva en el codigo y mapa sin regenerar, en un commit que NO toca
# ARQUITECTURA/. El hook lo DEJA PASAR, y es deliberado:
#   · vigilarlo obligaria a correr el generador en CADA commit de codigo (~2 s) y a
#     rechazar cualquier commit intermedio de una serie. Un hook insufrible se saltea con
#     --no-verify, y entonces tampoco protege las libretas.
#   · el caso ya esta cubierto: K88 lo caza por el brazo 2 (HUECO) en verify y en CI. La
#     division es a proposito -el hook impide meter un mapa NO GENERADO; K88 impide que el
#     mapa se quede viejo-.
# Se prueba que pasa para que el limite quede MEDIDO y no supuesto: si algun dia el hook
# empezara a rechazarlo, este caso lo diria.
p4() { python3 harness/bin/arquitectura --repo . >/dev/null 2>&1
       git add -A >/dev/null 2>&1
       git -c core.hooksPath=/dev/null commit -qm mapa >/dev/null 2>&1
       cat >> app/api.py <<'PY'


@app.get("/api/control-hook")
async def control_hook() -> dict[str, str]:
    return {"control": "hook"}
PY
}
caso "P4 codigo nuevo sin tocar ARQUITECTURA/ (lo cubre K88)" 0 "" normal p4

echo
# ======================================================================================
# LAS LIBRETAS · y el agujero que este hook viene a cerrar.
# ======================================================================================
echo "LIBRETAS · rechazadas por nombre, CON y SIN escape"

for lib in CAMBIOS.md harness/COLA.md harness/ESTADO.md harness/hechos.tsv; do
  cuerpo() { mkdir -p "$(dirname "$lib")" 2>/dev/null; printf 'contenido\n' > "$lib"; }
  caso "L·$lib sin escape" 1 "NO va en el repo" normal cuerpo
done

# EL AGUJERO: con la version anterior, HARNESS_DOC=1 salia en la linea 4 y saltaba el hook
# ENTERO. O sea que el commit de F1 -que necesito el escape para 71 .md- llevaba el filtro
# de libretas apagado. Estos cuatro casos son los que prueban que ya no.
echo "LIBRETAS · con HARNESS_DOC=1, que ANTES las dejaba pasar"
for lib in CAMBIOS.md harness/COLA.md harness/ESTADO.md harness/hechos.tsv; do
  cuerpo() { mkdir -p "$(dirname "$lib")" 2>/dev/null; printf 'contenido\n' > "$lib"; }
  caso "L·$lib CON escape" 1 "NO hay escape para esto" escape cuerpo
done

echo
# ======================================================================================
# EL ESCAPE SIGUE EXISTIENDO para lo que de verdad lo necesita.
# ======================================================================================
echo "ESCAPE · sigue sirviendo para un .md legitimo fuera de ARQUITECTURA/"
e1() { printf '# algo\n' > OTRO.md; }
caso "E1 .md fuera de ARQUITECTURA/ con HARNESS_DOC=1" 0 "" escape e1

echo
# ======================================================================================
# CONSERVADOR · si no se puede comprobar, NO se aprueba.
# ======================================================================================
echo "CONSERVADOR · sin poder comprobar, no pasa"
# Los dos tocan ARQUITECTURA/ a proposito: si el commit no la tocara, el hook no tendria
# por que decir nada y el caso no probaria lo que dice probar.
c1() { python3 harness/bin/arquitectura --repo . >/dev/null 2>&1
       printf '# suelto\n' > ARQUITECTURA/SUELTO.md
       rm -f harness/bin/arquitectura; }
caso "C1 se toca ARQUITECTURA/ y no hay generador" 1 "no encuentro" normal c1

c2() { python3 harness/bin/arquitectura --repo . >/dev/null 2>&1
       printf '# suelto\n' > ARQUITECTURA/SUELTO.md
       printf 'import sys\nsys.exit(3)\n' > harness/bin/arquitectura; }
caso "C2 se toca ARQUITECTURA/ y el generador esta roto" 1 "NO coincide con su regeneracion" normal c2

# C3 · un .md suelto DENTRO de ARQUITECTURA/ que el generador no produce. La carpeta no es
# una lista blanca: si el generador no lo genera, sobra, y el hook lo tiene que ver.
c3() { python3 harness/bin/arquitectura --repo . >/dev/null 2>&1
       printf '# colado\n' > ARQUITECTURA/COLADO.md; }
caso "C3 .md colado dentro de ARQUITECTURA/" 1 "NO coincide con su regeneracion" normal c3

echo
total=$((pasan + fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
