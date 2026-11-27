#!/bin/bash
# K20-control · que rellenar `desde` desde la declaracion de la ruta no convierta a K20 en ciego.
#
# Mitad A, el ayudante (K20-rellena.py) con rutas plantadas en una app FastAPI de mentira:
#   real_estructura   /api/rango/estructura del arbol: `desde` sale del validador -> un valor
#                     que ventana_pedida acepta
#   iso_plantada      validador fromisoformat plantado                -> se rellena
#   sin_validador     el parametro no pasa por ninguna funcion        -> None
#   rechaza_todo      validador que lanza siempre                     -> None
#   asincrono         validador async (no se llama)                   -> None
#   recibe_conn       validador que ademas recibe algo no resoluble   -> None
# Mitad B, el check ENTERO con REPO= un arbol plantado cuya /api/ohlcv exige un parametro
# obligatorio sin validador: K20 tiene que salir rc=1 con «no sabe rellenar». Lee produccion
# (rutas del release y un GET de /api/ohlcv), nada mas.
# rc: 0 todos pasan · 1 alguno no.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 1
REPO_REAL=$(cd -- "$AQUI/../.." && pwd -P)
PY="${VENV_PY:-$REPO_REAL/.venv/bin/python}"
D=$(mktemp -d) || exit 1
trap 'rm -rf "$D"' EXIT
fallos=0
pasa() { echo "  PASA  $1"; }
falla() { echo "  FALLA $1"; fallos=$((fallos + 1)); }

mkdir -p "$D/plantado"
cat > "$D/plantado/k20_plantas.py" <<'EOF'
from datetime import datetime
from fastapi import FastAPI
app = FastAPI()
def valida_iso(x):
    a = datetime.fromisoformat(x)
    if a.tzinfo is None:
        raise ValueError("sin zona")
    return a
def rechaza(x):
    raise ValueError("nunca")
async def asinc(x):
    return x
def con_conn(conn, x):
    return x
@app.get("/iso")
def iso(desde: str):
    return {"a": valida_iso(desde)}
@app.get("/sin")
def sin(misterio: str):
    return {"m": misterio}
@app.get("/rechaza")
def rch(misterio: str):
    return {"m": rechaza(misterio)}
@app.get("/asinc")
async def asn(misterio: str):
    return {"m": await asinc(misterio)}
@app.get("/conn")
def cn(misterio: str):
    conn = object()
    return {"m": con_conn(conn, misterio)}
EOF

out=$(cd "$REPO_REAL" && K20_RELLENA="$AQUI/K20-rellena.py" PLANT="$D/plantado" "$PY" - <<'EOF' 2>&1
import importlib.util, os, sys
from datetime import datetime
s = importlib.util.spec_from_file_location("r", os.environ["K20_RELLENA"])
r = importlib.util.module_from_spec(s); s.loader.exec_module(r)
from app.api import app as real, ventana_pedida
sys.path.insert(0, os.environ["PLANT"])
from k20_plantas import app as pl
V = {"symbol": "BTCUSDT_PERP.A"}
v = r.rellenar(real, "/api/rango/estructura", "desde", V)
try:
    ventana_pedida(v, None, obligatoria=True); ok = True
except Exception:
    ok = False
print("real_estructura", "PASA" if v and ok else "FALLA", v)
v = r.rellenar(pl, "/iso", "desde", V)
print("iso_plantada", "PASA" if v and datetime.fromisoformat(v).tzinfo else "FALLA", v)
for caso, ruta in (("sin_validador", "/sin"), ("rechaza_todo", "/rechaza"),
                   ("asincrono", "/asinc"), ("recibe_conn", "/conn")):
    v = r.rellenar(pl, ruta, "misterio", V)
    print(caso, "PASA" if v is None else "FALLA", v)
EOF
)
while read -r caso veredicto resto; do
  case "$veredicto" in
    PASA) pasa "$caso -> $resto" ;;
    *) falla "$caso $veredicto $resto" ;;
  esac
done <<< "$out"
[ "$(grep -c -E 'PASA|FALLA' <<< "$out")" = 6 ] || falla "ayudante: salida inesperada: $(head -c 300 <<< "$out")"

# Mitad B · el check entero con un arbol plantado
mkdir -p "$D/arbol/app"
: > "$D/arbol/app/__init__.py"
cat > "$D/arbol/app/api.py" <<'EOF'
from fastapi import FastAPI
app = FastAPI()
@app.get("/api/ohlcv")
def ohlcv(symbol: str, misterio: str):
    return {"m": misterio}
EOF
salida=$(REPO="$D/arbol" VENV_PY="$PY" bash "$AQUI/K20-cincoxx.sh" 2>&1); rc=$?
case "$rc:$salida" in
  "1:el barrido no sabe rellenar un parametro obligatorio nuevo: /api/ohlcv(misterio)"*) pasa "check_plantado rc=1: $salida" ;;
  *) falla "check_plantado rc=$rc: $(head -c 300 <<< "$salida")" ;;
esac

echo "K20-control: $((7 - fallos)) de 7 pasan"
[ "$fallos" = 0 ]
