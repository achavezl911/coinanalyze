# _panel-de-mentira · fabrica un panel FALSO CON LA FORMA QUE EL DESCUBRIDOR EXIGE.
#
# Se carga con `. "$(dirname "$0")/_panel-de-mentira.bash"`.
#
# POR QUE EXISTE. Cuatro controles -K43, K88, K90 y K96- fabricaban su arbol con UN
# `static/app.js`, que NO EXISTE desde la FASE 2. Medido el 2026-09-16, antes de tocar nada:
#
#     K43-control   rc=2  SED-NO-MORDIO            -> apagado: grepeaba un fichero ausente
#     K96-control   rc=1  0 de 7 pasan             -> apagado entero
#     K90-control   rc=1  17 de 18 pasan
#     K88-control   rc=0  53 de 53 pasan           -> PASABA midiendo el camino de ayer
#
# El ultimo es el peligroso: un control que pasa fabricando la forma vieja NO ejercita lo que el
# check hace hoy, y su verde es sobre otro sujeto.
#
# LA FORMA ES LA DEL CONTRATO de `bin/panel-fuentes`: `static/index.html` declara N
# `<script defer src="/static/js/NN-....js">` CLASICOS en orden de documento, y no hay imports.
# Aqui no se copia esa lista: se ESCRIBE el HTML a partir de los modulos que se pidan, que es la
# misma direccion -del HTML a los ficheros- que usa el descubridor.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y esto no es un check.

# panel_de_mentira <destino> [fichero-con-el-js]
#   Monta <destino>/static/index.html + <destino>/static/js/01-panel.js. Si se le pasa un
#   fichero, su contenido ES el modulo; si no, lee el JS de la entrada estandar.
panel_de_mentira() {
  local dst="$1" src="${2:-}"
  mkdir -p "$dst/static/js"
  if [ -n "$src" ]; then cp "$src" "$dst/static/js/01-panel.js"
  else cat > "$dst/static/js/01-panel.js"; fi
  _panel_html "$dst" 01-panel.js
}

# panel_de_mentira_multi <destino> <fichero1.js> [fichero2.js ...]
#   Igual, pero con N modulos: los numera en el orden en que se dan y los declara en ese orden.
panel_de_mentira_multi() {
  local dst="$1"; shift
  mkdir -p "$dst/static/js"
  local i=1 nombres=()
  for f in "$@"; do
    local n; n=$(printf '%02d-%s' "$i" "$(basename "$f")")
    cp "$f" "$dst/static/js/$n"; nombres+=("$n"); i=$((i+1))
  done
  _panel_html "$dst" "${nombres[@]}"
}

# panel_de_mentira_real <destino>
#   Copia el panel DE VERDAD -index.html y todos sus modulos-, para los controles que necesitan
#   un arbol sano al que despues le plantan un defecto.
panel_de_mentira_real() {
  local dst="$1" orig="${2:-${ORIG:-/srv/coinanalyze/repo}}"
  mkdir -p "$dst/static"
  cp "$orig/static/index.html" "$dst/static/index.html"
  cp -a "$orig/static/js" "$dst/static/"
  _venv_de_mentira "$dst" "$orig"
}

# El descubridor se ejecuta con `${VENV_PY:-$REPO/.venv/bin/python}`, y `$REPO` es el arbol de
# mentira: sin un `.venv` ahi, el check sale NO MEDIDO por el interprete y el control mide el
# canal en vez del criterio. Se enlaza al del arbol real.
_venv_de_mentira() {
  local dst="$1" orig="${2:-${ORIG:-/srv/coinanalyze/repo}}"
  [ -e "$dst/.venv" ] || { [ -d "$orig/.venv" ] && ln -s "$orig/.venv" "$dst/.venv"; }
}

_panel_html() {
  local dst="$1"; shift
  _venv_de_mentira "$dst"
  {
    printf '%s\n' '<!doctype html><html><head><meta charset="utf-8"><title>panel de mentira</title></head>'
    printf '%s\n' '<body>'
    for n in "$@"; do printf '  <script defer src="/static/js/%s"></script>\n' "$n"; done
    printf '%s\n' '</body></html>'
  } > "$dst/static/index.html"
}
