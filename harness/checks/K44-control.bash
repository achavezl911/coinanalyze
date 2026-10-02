#!/usr/bin/env bash
# K44-control · ¿sabe K44 decir en cual de los SEIS estados esta el mundo?
#
#     bash harness/checks/K44-control.bash
#
# POR QUE ESTE CONTROL Y NO OTRO. K44 mira lo que pidio un NAVEGADOR, y un instrumento asi
# **solo ve algo si alguien abrio el panel**. En una ventana sin visitas da cero exactamente
# igual que si el panel no pidiera el sobre, **y solo uno de los dos es un defecto**. Si K44 no
# separa esos dos, nace roto de una forma que no se ve: se pone rojo un domingo por la tarde y
# alguien lo «arregla» sin que hubiera nada que arreglar. Aqui se plantan los seis y se comparan
# las SALIDAS, no los `rc` -tres de los seis comparten rc=2 a proposito-.
#
# EL CONTROL POSITIVO ES E4 Y HAY QUE VERLO DISPARAR: un instrumento que nunca marca verde esta
# tan roto como el que marca siempre. E4 planta un panel que SI pide el sobre y no pide ninguna
# parte, y exige rc=0. Sin ese brazo, «K44 esta rojo» no distingue un defecto de un check que no
# sabe decir que si.
#
# CADA PLANTADO DEJA SU PRUEBA: el `bin/prod` de mentira escribe en un fichero senal cuando lo
# llaman, y el brazo la comprueba. Sin llamada NO SE JUZGA.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
#
# DESDE LA CAMPANA 133 EL MUNDO SE PLANTA COMO LOG CRUDO, CLIENTE A CLIENTE. K44 ya no lee cuentas
# agregadas: atribuye cada peticion a la pantalla que la pidio por la CARGA del documento de su
# cliente y por la linea de tiempo del desplegador. Asi que el `bin/prod` de mentira devuelve las
# DOS formas del MISMO mundo: la agregada de antes -que lee el K44 de main- y la cruda -que lee el
# de la 133-; cada uno ignora las lineas del otro. Eso es lo que deja correr este control contra
# los BYTES de main (REPO=<arbol de main>): los brazos de las pantallas (P*) tienen que CAER ahi.
# Los brazos E1-E40 plantan el mundo de siempre -un solo cliente que cargo `/` cuando `/` era el
# panel- y tienen que seguir diciendo lo mismo con los dos.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K44-el-sobre-que-nadie-pide.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
DIR=$(mktemp -d) || exit 2
[ "${K44_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0
declare -A SALIDA

comprueba() {  # $1 = etiqueta   $2 = si|no
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-58s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-58s\n' "$1"; fi
}

# EL RELOJ DE LOS PLANTADOS ES FIJO: el mundo que se planta no depende de la hora a la que se corra.
AHORA=1790960000   # 2026-10-02T16:53:20Z
GEN="$DIR/genera.py"
cat > "$GEN" <<'PY'
"""genera.py <agregado|ventana> <ahora>   (la especificacion entra por stdin)

agregado  la entrada es la forma AGREGADA de antes de la 133 (VISITAS n · «n ruta» · «QUERY n
          ruta?query») y sale el MISMO mundo en crudo: UN cliente que cargo `/` -el panel- hace 3 h
          y pidio exactamente eso, con sus queries. La forma agregada la pone quien llama.
ventana   la entrada son EVENTOS y salen las DOS formas: la agregada que el awk de 140 del K44 de
          main habria contado en la ventana de 6 h, y la cruda.
EVENTOS, uno por linea; los tiempos en segundos respecto de AHORA (negativo = antes):
  C <cliente> <seg> <ruta> [status]      una carga de documento (GET), 200 por omision
  A <cliente> <seg> <n> <ruta[?query]>   n peticiones, una por segundo desde <seg>
  D <seg> <panel|mesa|rara>               el desplegador cambia de release: `/` pasa a esa pantalla
  B <seg> <panel|mesa>                    una vuelta atras («rolling back to <sha>»)
  SIN_R                                   140 no dice que sirve ningun release (obliga a ir a git)
  SIN_BASE                                sin el cambio de release de base de hace 30 dias
Clientes: alex (.101, Firefox) · ipad (.99, Safari) · arnes (.2, Chromium: lo tiene que descartar).
"""
import datetime, sys
modo, ahora = sys.argv[1], int(sys.argv[2])
SHA = {"panel": "1" * 40, "mesa": "2" * 40, "rara": "3" * 40}
IP = {"alex": "10.10.100.101", "ipad": "10.10.100.99", "arnes": "10.10.100.2"}
UA = {"alex": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:156.0) Gecko/20100101 Firefox/156.0",
      "ipad": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
      "arnes": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/152.0.0.0 Safari/537.36"}
TZ = datetime.timezone(datetime.timedelta(hours=-6))   # el log de nginx de 140 va en -0600
def hora(t): return datetime.datetime.fromtimestamp(t, TZ).strftime("%d/%b/%Y:%H:%M:%S -0600")
def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def linea(cli, t, ruta, st=200):
    usr = "-" if st == 401 else "operator"
    return f'{IP[cli]} - {usr} [{hora(t)}] "GET {ruta} HTTP/1.1" {st} 100 "-" "{UA[cli]}"'
C, A, D = [], [], []
sin_r, base = False, True
if modo == "agregado":
    rutas, queries = [], []
    for ln in sys.stdin:
        p = ln.split()
        if not p: continue
        if p[0] == "QUERY" and len(p) >= 3: queries.append((int(p[1]), p[2]))
        elif p[0].isdigit() and len(p) >= 2: rutas.append((int(p[0]), p[1]))
    if rutas:
        C.append(("alex", ahora - 3 * 3600, "/", 200))
        t = ahora - 3 * 3600 + 5
        for n, r in rutas:
            usadas = 0
            for nq, full in queries:
                if full.split("?", 1)[0] == r:
                    for _ in range(nq): A.append(("alex", t, full)); t += 1
                    usadas += nq
            for _ in range(max(0, n - usadas)): A.append(("alex", t, r + "?symbol=TEST")); t += 1
else:
    for ln in sys.stdin:
        p = ln.split()
        if not p or p[0].startswith("#"): continue
        if p[0] == "C": C.append((p[1], ahora + int(p[2]), p[3], int(p[4]) if len(p) > 4 else 200))
        elif p[0] == "A":
            t0 = ahora + int(p[2])
            for i in range(int(p[3])): A.append((p[1], t0 + i, p[4]))
        elif p[0] == "D": D.append((ahora + int(p[1]), "current -> /opt/coinalyze/releases/" + SHA[p[2]]))
        elif p[0] == "B": D.append((ahora + int(p[1]), "rolling back to " + SHA[p[2]]))
        elif p[0] == "SIN_R": sin_r = True
        elif p[0] == "SIN_BASE": base = False
if base: D.append((ahora - 30 * 86400, "current -> /opt/coinalyze/releases/" + SHA["panel"]))
D.sort()
if modo == "ventana":
    ini, vis, cuenta, q = ahora - 6 * 3600, 0, {}, {}
    EXC = {"/api/dashboard/state", "/api/scalp/delta-matrix", "/api/scalp/liquidation-levels"}
    for (cli, t, ruta, st) in C:
        if cli != "arnes" and ini <= t <= ahora: vis += 1
    for (cli, t, full) in A:
        if cli == "arnes" or not (ini <= t <= ahora): continue
        vis += 1; r = full.split("?", 1)[0]; cuenta[r] = cuenta.get(r, 0) + 1
        if r in EXC: q[full] = q.get(full, 0) + 1
    print(f"VISITAS {vis}")
    for r, n in cuenta.items(): print(f"{n} {r}")
    for f, n in q.items(): print(f"QUERY {n} {f}")
print(f"AHORA {ahora}")
for (cli, t, ruta, st) in C: print("C " + linea(cli, t, ruta, st))
for (cli, t, full) in A: print("A " + linea(cli, t, full))
for (t, txt) in D: print(f"D {iso(t)} {txt}")
if not sin_r:
    print(f"R {SHA['panel']} index.html")
    print(f"R {SHA['mesa']} mesa.html")
print("K44-FIN")
PY

# K44 solo usa dos cosas del arnes: `$B/env` (para el entorno) y `$B/bin/prod` (el log).
# Se monta un arnes de mentira con esas dos y se apunta una COPIA del check con un `sed`,
# comprobando que el sed MORDIO: si no muerde, se compararia el check consigo mismo.
# LO QUE EL PROD DE MENTIRA DEVUELVE VA EN UN FICHERO, NO EN UN HEREDOC: el K44 de la 133 cierra
# su respuesta con una marca propia, y un heredoc con delimitador se cortaria en una linea igual.
monta() {  # $1 = dir   $2 = rc del prod falso   $3 = lo que escribe, en la forma AGREGADA
  rm -rf "$1"; mkdir -p "$1/bin"
  printf '%s\n' ". /srv/coinanalyze/harness/env" > "$1/env"
  if [ -n "$3" ]; then
    { printf '%s\n' "$3"; printf '%s\n' "$3" | python3 "$GEN" agregado "$AHORA"; } > "$1/salida"
  else
    : > "$1/salida"
  fi
  {
    printf '%s\n' "#!/bin/bash"
    printf '%s\n' "printf 'LLAMADO\\n' >> $1/senal"
    printf '%s\n' "cat $1/salida"
    printf '%s\n' "exit $2"
  } > "$1/bin/prod"
  chmod +x "$1/bin/prod"
  : > "$1/senal"
  # LOS PAYLOADS DE LAS EXCEPCIONES. El check baja el sobre y las rutas excusadas para volver a
  # comprobar cada excusa; aqui se le inyectan con K44_PAYLOADS para no tocar la red. El sobre
  # de serie trae SOLO los cuatro testigos del buscador -si faltaran, el check saldria NO MEDIDO
  # diciendo que su buscador esta roto, y ese es justo el brazo que lo protege-.
  mkdir -p "$1/payloads"
  printf '%s\n' '{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{}}' > "$1/payloads/_sobre.json"
}
# `plantada` sobreescribe un payload concreto del arnes de mentira.
plantada() {  # $1 = dir   $2 = nombre de fichero   $3 = json
  printf '%s\n' "$3" > "$1/payloads/$2"
}
copia() {  # $1 = dir del arnes falso -> imprime la ruta de la copia
  local f="$1/K44.sh"
  sed "s#^B=/srv/coinanalyze/harness; . \"\$B/env\"#B=$1; . \"\$B/env\"#" "$CHK" > "$f"
  if cmp -s "$CHK" "$f"; then echo "SED-NO-MORDIO" >&2; return 1; fi
  printf '%s\n' "$f"
}
# `corre` deja el resultado en DOS GLOBALES y no lo imprime. La primera version lo llamaba
# dentro de una sustitucion de mandato, o sea en un SUBSHELL, y ahi la asignacion al array se
# pierde: los rc salian bien y las salidas llegaban VACIAS, asi que los diez brazos de texto
# fallaban todos por el instrumento y no por el sujeto. Lo canto el propio control.
corre() {  # $1 = etiqueta  $2 = fichero  resto = VAR=valor   -> deja RC y OUT
  local etq="$1" f="$2"; shift 2
  OUT=$(env "$@" timeout -k 5 200 bash "$f" 2>&1); RC=$?
  SALIDA["$etq"]="$OUT"
}

echo "K44-control · sujeto: $CHK"
echo

# ── E1 · EL CANAL NO CONTESTO ────────────────────────────────────────────────────────────────
echo "E1 · el canal no pudo contestar (bin/prod rc=3)"
monta "$DIR/e1" 3 ""
f=$(copia "$DIR/e1") || exit 2
corre E1 "$f"; rc=$RC
comprueba "E1a el plantado OCURRIO: el prod de mentira se llamo" \
  "$([ -s "$DIR/e1/senal" ] && echo si || echo no)"
comprueba "E1b NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E1c y dice que fue el CANAL, con su rc" \
  "$(printf '%s' "${SALIDA[E1]}" | grep -q 'no se pudo leer (bin/prod rc=3)' && echo si || echo no)"
comprueba "E1d y NO afirma nada sobre lo que el panel pide" \
  "$(printf '%s' "${SALIDA[E1]}" | grep -q 'NO dice nada sobre lo que el panel pide' && echo si || echo no)"

# ── E2 · NO CONSTA QUE NADIE MIRARA ──────────────────────────────────────────────────────────
echo
echo "E2 · el canal contesta y NO CONSTA que nadie mirara"
monta "$DIR/e2" 0 "VISITAS 0"
f=$(copia "$DIR/e2") || exit 2
corre E2 "$f"; rc=$RC
comprueba "E2a el plantado OCURRIO" "$([ -s "$DIR/e2/senal" ] && echo si || echo no)"
comprueba "E2b NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E2c y lo dice: 'no consta que nadie mirara'" \
  "$(printf '%s' "${SALIDA[E2]}" | grep -q 'no consta que nadie mirara' && echo si || echo no)"
comprueba "E2d y explica por que eso NO es el defecto" \
  "$(printf '%s' "${SALIDA[E2]}" | grep -q 'solo uno de los dos es un defecto' && echo si || echo no)"

# ── E3 · NO SE PUDO LEER LA LISTA FOTO ───────────────────────────────────────────────────────
echo
echo "E3 · el conjunto FOTO no se puede leer (la lista no es de este check)"
monta "$DIR/e3" 0 "VISITAS 100"
f=$(copia "$DIR/e3") || exit 2
corre E3 "$f" K44_K43=/dev/null; rc=$RC
comprueba "E3a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E3b y nombra el fichero del que no pudo leerla" \
  "$(printf '%s' "${SALIDA[E3]}" | grep -q 'familia FOTO en /dev/null' && echo si || echo no)"
comprueba "E3c y NO juzga: un criterio sobre cero rutas se cumple solo" \
  "$(printf '%s' "${SALIDA[E3]}" | grep -q 'se cumpliria solo sobre cero rutas' && echo si || echo no)"

# ── E4 · EL CONTROL POSITIVO · el VERDE, visto disparar ──────────────────────────────────────
echo
echo "E4 · CONTROL POSITIVO · el panel pide el sobre y CERO partes"
monta "$DIR/e4" 0 "VISITAS 900
450 /api/ai/context
450 /api/ohlcv"
f=$(copia "$DIR/e4") || exit 2
corre E4 "$f"; rc=$RC
comprueba "E4a el plantado OCURRIO" "$([ -s "$DIR/e4/senal" ] && echo si || echo no)"
comprueba "E4b VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E4c y dice cuantas veces lo pidio y cuantas partes (0)" \
  "$(printf '%s' "${SALIDA[E4]}" | grep -qE 'pide el sobre 450 veces y CERO de las [0-9]+ rutas' && echo si || echo no)"
printf '        %s\n' "$(printf '%s' "${SALIDA[E4]}" | head -1 | cut -c1-125)"

# ── E5 · NO PIDE EL SOBRE ────────────────────────────────────────────────────────────────────
echo
echo "E5 · hubo visitas y el panel NO pide el sobre"
monta "$DIR/e5" 0 "VISITAS 900
600 /api/dashboard/state
300 /api/ohlcv"
f=$(copia "$DIR/e5") || exit 2
corre E5 "$f"; rc=$RC
comprueba "E5a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E5b y NOMBRA las partes que si pide, con su cuenta" \
  "$(printf '%s' "${SALIDA[E5]}" | grep -q '/api/dashboard/state(600)' && echo si || echo no)"
comprueba "E5c y dice 0 peticiones al sobre" \
  "$(printf '%s' "${SALIDA[E5]}" | grep -q '0 peticiones a /api/ai/context' && echo si || echo no)"

# ── E6 · LA REFORMA A MEDIAS ─────────────────────────────────────────────────────────────────
echo
echo "E6 · pide el sobre Y ADEMAS sigue pidiendo las partes"
# LA RUTA DE E6 NO PUEDE TENER EXCEPCION, o dejaria de medir lo que dice medir. Antes plantaba
# /api/dashboard/state, que desde COLA 124 esta excusada: el brazo habria pasado a VERDE y
# «E6 falla» habria parecido una regresion del estado 6 cuando era su sujeto mal elegido.
# /api/wyckoff es FOTO y no tiene excusa, que es exactamente lo que este brazo necesita.
monta "$DIR/e6" 0 "VISITAS 900
450 /api/ai/context
200 /api/wyckoff"
f=$(copia "$DIR/e6") || exit 2
corre E6 "$f" K44_PAYLOADS="$DIR/e6/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E6a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E6b y lo llama REFORMA A MEDIAS, no lo mismo que E5" \
  "$(printf '%s' "${SALIDA[E6]}" | grep -q 'REFORMA A MEDIAS' && echo si || echo no)"
comprueba "E6c y dice las DOS cifras: las del sobre y las de las partes" \
  "$(printf '%s' "${SALIDA[E6]}" | grep -q 'pide el sobre 450 veces Y ADEMAS sigue pidiendo 200' && echo si || echo no)"

# ── LA EXCEPCION FALSABLE (COLA 124) · cuatro brazos ─────────────────────────────────────────
# Lo que se prueba aqui no es que la excusa exista: es que SE CAE SOLA. Una excusa que solo
# alguien puede retirar a mano es una lista de nombres con otro nombre.
SOBRE_SIN='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"delta_matrix":[1,2]}'
SOBRE_CON='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"delta_matrix":[1,2,3,4,5,6,7,8,9,10,11,12]}'
RUTA_DM='[1,2,3,4,5,6,7,8,9,10,11,12]'

echo
echo "E7 · una ruta EXCUSADA con su razon CIERTA no condena"
monta "$DIR/e7" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e7" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e7" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e7") || exit 2
corre E7 "$f" K44_PAYLOADS="$DIR/e7/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E7a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E7b NOMBRA la excusa y CONTRA QUE se comprobo" \
  "$(printf '%s' "${SALIDA[E7]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 2' && echo si || echo no)"

echo
echo "E8 · LA MISMA ruta con la razon hecha FALSA vuelve a condenar, sin que nadie toque la tabla"
monta "$DIR/e8" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e8" _sobre.json "$SOBRE_CON"
plantada "$DIR/e8" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e8") || exit 2
corre E8 "$f" K44_PAYLOADS="$DIR/e8/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E8a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E8b y dice EXCEPCION ANULADA con la cifra que la mato" \
  "$(printf '%s' "${SALIDA[E8]}" | grep -q 'EXCEPCION ANULADA: el sobre trae 12 y la ruta 12' && echo si || echo no)"
comprueba "E8c mismo plantado que E7 salvo el sobre, y veredicto CONTRARIO" \
  "$([ "${SALIDA[E7]}" != "${SALIDA[E8]}" ] && echo si || echo no)"

echo
echo "E9 · una ruta SIN excusa junto a una excusada: condena, y solo por la que no tiene"
monta "$DIR/e9" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix
77 /api/wyckoff"
plantada "$DIR/e9" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e9" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e9") || exit 2
corre E9 "$f" K44_PAYLOADS="$DIR/e9/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E9a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E9b condena SOLO 1 ruta, la que no tiene excusa" \
  "$(printf '%s' "${SALIDA[E9]}" | grep -q 'sigue pidiendo 77 veces 1 de las' && echo si || echo no)"
comprueba "E9c y nombra a wyckoff, no a delta-matrix, como la condenada" \
  "$(printf '%s' "${SALIDA[E9]}" | grep -q '· /api/wyckoff(77) ·' && echo si || echo no)"

echo
echo "E10 · la excusa de una ruta que el panel YA NO PIDE sobra, y se dice"
monta "$DIR/e10" 0 "VISITAS 900
450 /api/ai/context"
f=$(copia "$DIR/e10") || exit 2
corre E10 "$f" K44_PAYLOADS="$DIR/e10/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E10a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E10b y declara las excepciones HUERFANAS por su nombre" \
  "$(printf '%s' "${SALIDA[E10]}" | grep -q 'HUERFANAS.*dashboard/state.*delta-matrix.*liquidation-levels' && echo si || echo no)"

echo
echo "E11 · el sobre no se pudo leer: NO se excusa a nadie por defecto"
monta "$DIR/e11" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
rm -f "$DIR/e11/payloads/_sobre.json"
f=$(copia "$DIR/e11") || exit 2
corre E11 "$f" K44_PAYLOADS="$DIR/e11/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E11a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
# 2026-09-18 · ESTE BRAZO SE RE-APUNTA, Y NO SE AFLOJA. Casaba la frase «excusar en silencio»,
# que vivia en el `exit 2` que apagaba el check entero en la primera linea del bloque; ese
# camino se fue con COLA 125 (A54: lo decidible va antes que lo que falta). Lo que E11 tiene que
# sostener no es una frase: es que NADIE salga excusado cuando no se pudo reverificar, y que lo
# que no se pudo leer se DIGA. Las dos cosas se comprueban ahora, que es mas que antes.
comprueba "E11b y NADIE sale excusado" \
  "$(printf '%s' "${SALIDA[E11]}" | grep -q 'EXCUSADAS Y REVERIFICADAS' && echo no || echo si)"
comprueba "E11c y NOMBRA lo que no pudo leer" \
  "$(printf '%s' "${SALIDA[E11]}" | grep -q 'no se pudo leer el sobre' && echo si || echo no)"

echo
echo "E12 · el BUSCADOR roto no puede excusar a nadie: sobre sin los testigos"
monta "$DIR/e12" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e12" _sobre.json '{"delta_matrix":[1,2]}'
plantada "$DIR/e12" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e12") || exit 2
corre E12 "$f" K44_PAYLOADS="$DIR/e12/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E12a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E12b y nombra los testigos que no encuentra" \
  "$(printf '%s' "${SALIDA[E12]}" | grep -q 'buscador de claves no encuentra' && echo si || echo no)"

# ── LA AFIRMACION ES LO QUE EL PANEL LEE (COLA 124, remate) ──────────────────────────────────
# De /api/scalp/liquidation-levels el panel pinta TODAS las filas y publica su cuenta; de los
# metadatos solo usa `minutes`, con reserva de 60. La primera version de esta excepcion
# afirmaba que la ruta declara minutes/bucket_bps/window_start/window_end y el sobre no, y eso
# se refuta por algo que el panel NO LEE: los dos brazos de abajo salian AL REVES.
LIQ_RUTA='{"minutes":60,"bucket_bps":10,"window_start":"a","window_end":"b","rows":[1,2,3,4,5,6,7,8,9]}'
TESTIGOS='"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"profile":"default"'
# A · los cuatro metadatos DENTRO del sobre, y el tope del sobre INTACTO (8 de 9 filas).
# Los metadatos entran DONDE ENTRARIAN de verdad: dentro del propio bloque del sobre, junto a
# sus filas -que siguen topadas en 8 de 9-. Ponerlos al nivel alto del sobre no reproduce nada:
# la version de 333b359b ya buscaba ACOTADA dentro de `liquidation_levels` y no los veria.
SOBRE_META="{$TESTIGOS,\"liquidation_levels\":{\"minutes\":60,\"bucket_bps\":10,\"window_start\":\"a\",\"window_end\":\"b\",\"rows\":[1,2,3,4,5,6,7,8]}}"
# B · TODAS las filas de la ruta dentro del sobre: NUEVE, por encima del tope de 8.
SOBRE_FILAS="{$TESTIGOS,\"liquidation_levels\":[1,2,3,4,5,6,7,8,9]}"
# C · HORA TRANQUILA: las dos cuentas iguales y por DEBAJO del tope.
LIQ_CORTA='{"minutes":60,"rows":[1,2,3]}'
SOBRE_CORTA="{$TESTIGOS,\"liquidation_levels\":[1,2,3]}"
# D · HORA AGITADA: la ruta trae 16 y el sobre sus 8. Mismo panel, otra hora.
LIQ_LARGA='{"minutes":60,"rows":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}'
SOBRE_OCHO="{$TESTIGOS,\"liquidation_levels\":[1,2,3,4,5,6,7,8]}"

# EL TOPE SE INYECTA, en vez de leerlo de 140: asi el control no depende del canal ni del
# release, y puede plantar un tope SUBIDO para ver caer la excusa.
LIMITS_OK="$DIR/limits-ok.py"
LIMITS_SUBIDO="$DIR/limits-subido.py"
printf '%s\n' 'PROFILE_LIMITS = {"lite": {"liq_levels": 5}, "default": {"liq_levels": 8}, "max": {"liq_levels": 25}}' > "$LIMITS_OK"
printf '%s\n' 'PROFILE_LIMITS = {"lite": {"liq_levels": 5}, "default": {"liq_levels": 50}, "max": {"liq_levels": 80}}' > "$LIMITS_SUBIDO"

liqmonta() {  # $1 = dir   $2 = json del sobre   $3 = json de la ruta
  # El log lleva la QUERY con el `limit` del panel: el check lo saca de ahi, no de una copia.
  monta "$1" 0 "VISITAS 900
450 /api/ai/context
101 /api/scalp/liquidation-levels
QUERY 101 /api/scalp/liquidation-levels?symbol=TEST&minutes=60&bucket_bps=10&limit=50"
  plantada "$1" _sobre.json "$2"
  plantada "$1" "_api_scalp_liquidation-levels.json" "$3"
}
liqcorre() {  # $1 = etiqueta  $2 = dir  $3 = fichero de topes (o vacio)
  local f; f=$(copia "$2") || exit 2
  if [ -n "$3" ]; then
    corre "$1" "$f" K44_PAYLOADS="$2/payloads" K44_SIMBOLO=TEST K44_LIMITS="$3"
  else
    corre "$1" "$f" K44_PAYLOADS="$2/payloads" K44_SIMBOLO=TEST K44_LIMITS=/no/existe
  fi
}

echo
echo "E13 · los CUATRO METADATOS en el sobre y el tope intacto: sigue EXCUSADA"
liqmonta "$DIR/e13" "$SOBRE_META" "$LIQ_RUTA"
liqcorre E13 "$DIR/e13" "$LIMITS_OK"; rc=$RC
comprueba "E13a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E13b y la razon es el TOPE del perfil contra el limit del panel" \
  "$(printf '%s' "${SALIDA[E13]}" | grep -q 'topa `liquidation_levels` en 8 .* y el panel pide limit=50' && echo si || echo no)"

echo
echo "E14 · el sobre sirve MAS filas que su propio tope: ese tope ya no lo describe, CONDENA"
liqmonta "$DIR/e14" "$SOBRE_FILAS" "$LIQ_RUTA"
liqcorre E14 "$DIR/e14" "$LIMITS_OK"; rc=$RC
comprueba "E14a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E14b y dice ANULADA con las dos cifras que la matan" \
  "$(printf '%s' "${SALIDA[E14]}" | grep -q 'el sobre sirve 9 filas y el perfil `default` topa en 8' && echo si || echo no)"
comprueba "E14c E13 y E14 dan veredictos CONTRARIOS con la misma ruta" \
  "$([ "${SALIDA[E13]}" != "${SALIDA[E14]}" ] && echo si || echo no)"

# ── EL VEREDICTO NO DEPENDE DE LA HORA ───────────────────────────────────────────────────────
# Este par es el punto entero del segundo remate. Mismo panel, mismo tope, mismo `limit`: lo
# UNICO que cambia entre E15 y E16 es cuantas liquidaciones hubo en la ultima hora. Con el
# criterio anterior -contar filas- la hora tranquila CONDENABA y la agitada excusaba.
echo
echo "E15 · HORA TRANQUILA: cuentas iguales por debajo del tope (3 y 3) NO condena"
liqmonta "$DIR/e15" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E15 "$DIR/e15" "$LIMITS_OK"; rc=$RC
comprueba "E15a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E15b y DICE que las cuentas de esta hora no son lo que sostiene la excusa" \
  "$(printf '%s' "${SALIDA[E15]}" | grep -q 'por debajo del tope, asi que las cuentas de esta hora no lo ensenan' && echo si || echo no)"

echo
echo "E16 · HORA AGITADA: la ruta trae 16 y el sobre 8. MISMO veredicto que la tranquila"
liqmonta "$DIR/e16" "$SOBRE_OCHO" "$LIQ_LARGA"
liqcorre E16 "$DIR/e16" "$LIMITS_OK"; rc=$RC
comprueba "E16a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E16b MISMO veredicto que E15 con 5 veces mas filas: la hora NO manda" \
  "$([ "$RC" = 0 ] && printf '%s' "${SALIDA[E16]}" | grep -q 'topa `liquidation_levels` en 8' && echo si || echo no)"

echo
echo "E17 · LA EXCUSA CAE SOLA: alguien sube liq_levels hasta el limit del panel"
liqmonta "$DIR/e17" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E17 "$DIR/e17" "$LIMITS_SUBIDO"; rc=$RC
comprueba "E17a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E17b y dice que el sobre YA puede darle todo lo que lee" \
  "$(printf '%s' "${SALIDA[E17]}" | grep -q 'topa en 50 .* y el panel pide limit=50: el sobre ya puede darle TODO' && echo si || echo no)"
comprueba "E17c mismos payloads que E15 y veredicto CONTRARIO: lo que cambia es el tope" \
  "$([ "${SALIDA[E15]}" != "${SALIDA[E17]}" ] && echo si || echo no)"

# ── LO QUE NO SE PUEDE VERIFICAR NO ES UN VERDE (COLA 124, tercer remate) ────────────────────
# Antes estos casos salian VIVA y K44 daba VERDE. Decirlo en la linea no lo convierte en medida:
# el marcador cuenta VERDE, y esta campana vino justo a quitar las redes que dicen lo que no
# midieron. Ahora la ruta queda en un tercer cubo: ni excusa ni condena.
SOBRE_SINPERFIL='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"liquidation_levels":[1,2,3]}'
SOBRE_50="{$TESTIGOS,\"liquidation_levels\":[$(seq -s, 1 50)]}"
LIQ_50="{\"minutes\":60,\"rows\":[$(seq -s, 1 50)]}"
LIQ_16='{"minutes":60,"rows":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}'
SOBRE_16="{$TESTIGOS,\"liquidation_levels\":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}"
# Un log SIN la query del panel: el `limit` no se puede leer.
liqmonta_sinlimit() {  # $1 = dir   $2 = sobre   $3 = ruta
  monta "$1" 0 "VISITAS 900
450 /api/ai/context
101 /api/scalp/liquidation-levels"
  plantada "$1" _sobre.json "$2"
  plantada "$1" "_api_scalp_liquidation-levels.json" "$3"
}

echo
echo "E18 · sin fuente para el tope: NO MEDIDO. No condena, pero TAMPOCO da verde"
liqmonta "$DIR/e18" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E18 "$DIR/e18" ""; rc=$RC
comprueba "E18a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E18b y lo declara NO VERIFICABLE EN ESTA CORRIDA" \
  "$(printf '%s' "${SALIDA[E18]}" | grep -q 'NO VERIFICABLE EN ESTA CORRIDA' && echo si || echo no)"
comprueba "E18c y dice por que no basta con decirlo" \
  "$(printf '%s' "${SALIDA[E18]}" | grep -q 'contar como medida lo que no se midio' && echo si || echo no)"

echo
echo "E19 · MAS filas que su tope y un log SIN limit: se decide igual, y CONDENA"
liqmonta_sinlimit "$DIR/e19" "$SOBRE_50" "$LIQ_50"
liqcorre E19 "$DIR/e19" "$LIMITS_OK"; rc=$RC
comprueba "E19a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E19b y dice que se decide SIN el limit del panel" \
  "$(printf '%s' "${SALIDA[E19]}" | grep -q 'se decide SIN el `limit` del panel' && echo si || echo no)"
comprueba "E19c con 16 y 16 y sin limit, tambien condena" \
  "$(liqmonta_sinlimit "$DIR/e19b" "$SOBRE_16" "$LIQ_16"; liqcorre E19b "$DIR/e19b" "$LIMITS_OK"; [ "$RC" = 1 ] && echo si || echo no)"

echo
echo "E20 · un sobre SIN \`profile\`: no hay tope que leer, NO MEDIDO"
liqmonta "$DIR/e20" "$SOBRE_SINPERFIL" "$LIQ_CORTA"
liqcorre E20 "$DIR/e20" "$LIMITS_OK"; rc=$RC
comprueba "E20a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E20b y nombra lo que falta" \
  "$(printf '%s' "${SALIDA[E20]}" | grep -q 'el sobre no declara su `profile`' && echo si || echo no)"

echo
echo "E21 · log SIN limit y filas POR DEBAJO del tope: no se puede decidir, NO MEDIDO"
liqmonta_sinlimit "$DIR/e21" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E21 "$DIR/e21" "$LIMITS_OK"; rc=$RC
comprueba "E21a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E21b y nombra que falta el limit del log" \
  "$(printf '%s' "${SALIDA[E21]}" | grep -q 'el log no trae el `limit`' && echo si || echo no)"

echo
echo "E22 · una no verificable JUNTO a una ruta sin excusa: manda la condena"
monta "$DIR/e22" 0 "VISITAS 900
450 /api/ai/context
101 /api/scalp/liquidation-levels
77 /api/wyckoff"
plantada "$DIR/e22" _sobre.json "$SOBRE_CORTA"
plantada "$DIR/e22" "_api_scalp_liquidation-levels.json" "$LIQ_CORTA"
liqcorre E22 "$DIR/e22" ""; rc=$RC
comprueba "E22a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E22b condena por wyckoff, que es la que no tiene excusa" \
  "$(printf '%s' "${SALIDA[E22]}" | grep -q '· /api/wyckoff(77)' && echo si || echo no)"
comprueba "E22c y la no verificable sale NOMBRADA, no callada" \
  "$(printf '%s' "${SALIDA[E22]}" | grep -q 'NO SE HAN PODIDO VERIFICAR' && echo si || echo no)"

# ── E23-E26 · UN PAYLOAD QUE NO SE PUDO LEER NO SE COME LA CONDENA DE OTRA RUTA (COLA 125) ──
# EL PUNTO. Hasta hoy, si UNA de las tres rutas con excepcion no se podia leer en la corrida,
# K44 salia NO MEDIDO ENTERO -y lo hacia ANTES de mirar `partes`-. En esa misma corrida el panel
# podia estar pidiendo suelta otra ruta de FOTO SIN NINGUNA EXCUSA, que es un hecho sobre el
# panel que no necesita ese payload para nada. Lo que faltaba de una se comia la condena de otra,
# que es A54 otra vez y por otra puerta.
# COMO SE PLANTA «ILEGIBLE»: el fichero EXISTE y no es JSON, que es lo que deja `bin/api` cuando
# la ruta no contesta -no se borra el fichero, se queda vacio-. Asi el plantado se ve.
echo
echo "E23 · la ruta con excusa ILEGIBLE y NADA MAS: no hay nada que condenar -> NO MEDIDO"
monta "$DIR/e23" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e23" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e23" "_api_scalp_delta-matrix.json" ""
f=$(copia "$DIR/e23") || exit 2
corre E23 "$f" K44_PAYLOADS="$DIR/e23/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E23a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E23b y NOMBRA la ruta que no se pudo leer" \
  "$(printf '%s' "${SALIDA[E23]}" | grep -q '/api/scalp/delta-matrix(200): no se pudo leer su payload' && echo si || echo no)"
comprueba "E23c y NO la da por excusada" \
  "$(printf '%s' "${SALIDA[E23]}" | grep -q 'EXCUSADAS Y REVERIFICADAS' && echo no || echo si)"

echo
echo "E24 · EL PUNTO · la MISMA ruta ilegible MAS una suelta sin excusa -> ROJO, y nombra las dos"
monta "$DIR/e24" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix
77 /api/wyckoff"
plantada "$DIR/e24" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e24" "_api_scalp_delta-matrix.json" ""
f=$(copia "$DIR/e24") || exit 2
corre E24 "$f" K44_PAYLOADS="$DIR/e24/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E24a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E24b condena por /api/wyckoff, que no necesita ese payload" \
  "$(printf '%s' "${SALIDA[E24]}" | grep -q '· /api/wyckoff(77)' && echo si || echo no)"
comprueba "E24c y NOMBRA ademas la que no se pudo leer" \
  "$(printf '%s' "${SALIDA[E24]}" | grep -q '/api/scalp/delta-matrix(200): no se pudo leer su payload' && echo si || echo no)"
comprueba "E24d y NO condena a la ilegible: no entra en las partes" \
  "$(printf '%s' "${SALIDA[E24]}" | grep -q '· /api/scalp/delta-matrix(200) ' && echo no || echo si)"

echo
echo "E25 · CONTROL DE E24 · el MISMO log con el payload LEGIBLE: sigue ROJO, y sin nada sin leer"
# Sin este brazo, E24 pasaria igual si el check condenara SIEMPRE a wyckoff: lo unico que
# cambia entre los dos es si ese payload se puede leer.
monta "$DIR/e25" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix
77 /api/wyckoff"
plantada "$DIR/e25" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e25" "_api_scalp_delta-matrix.json" "$RUTA_DM"
f=$(copia "$DIR/e25") || exit 2
corre E25 "$f" K44_PAYLOADS="$DIR/e25/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E25a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E25b y NADA queda sin leer" \
  "$(printf '%s' "${SALIDA[E25]}" | grep -q 'no se pudo leer su payload' && echo no || echo si)"
comprueba "E25c y delta-matrix SI sale excusada y reverificada" \
  "$(printf '%s' "${SALIDA[E25]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 2' && echo si || echo no)"

echo
echo "E26 · el SOBRE ilegible tampoco apaga la condena de una suelta sin excusa"
# La otra mitad del mismo punto: sin sobre NINGUNA excusa se puede reverificar -y las tres salen
# nombradas en el tercer cubo- pero `/api/wyckoff` sigue sin tener excusa, y eso se decide con el
# log. Antes esto era un `exit 2` en la primera linea del bloque.
monta "$DIR/e26" 0 "VISITAS 900
450 /api/ai/context
77 /api/wyckoff"
plantada "$DIR/e26" _sobre.json ""
f=$(copia "$DIR/e26") || exit 2
corre E26 "$f" K44_PAYLOADS="$DIR/e26/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E26a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E26b y dice que el sobre no se pudo leer" \
  "$(printf '%s' "${SALIDA[E26]}" | grep -q 'no se pudo leer el sobre' && echo si || echo no)"
comprueba "E26c y las tres excepciones salen como HUERFANAS o sin verificar, no excusadas" \
  "$(printf '%s' "${SALIDA[E26]}" | grep -q 'EXCUSADAS Y REVERIFICADAS' && echo no || echo si)"

echo
echo "E27 · y sin sobre y sin nada que condenar, NO MEDIDO (no VERDE)"
monta "$DIR/e27" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e27" _sobre.json ""
f=$(copia "$DIR/e27") || exit 2
corre E27 "$f" K44_PAYLOADS="$DIR/e27/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E27a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E27b y dice lo que no pudo leer" \
  "$(printf '%s' "${SALIDA[E27]}" | grep -q 'LO QUE NO SE PUDO LEER EN ESTA CORRIDA' && echo si || echo no)"

# ── E28-E33 · LAS OTRAS DOS EXCUSAS CONTRA LA HORA (A53) ────────────────────────────────────
# COLA 124 rehizo la excusa de liquidation-levels porque su veredicto dependia de la hora: en
# una hora tranquila las cuentas coincidian, la excusa moria y K44 condenaba un diseno correcto.
# E15/E16 lo fijan para TOPE. Aqui se hace lo mismo con las OTRAS DOS, que nadie habia atacado.
#
# LOS PLANTADOS SON FIJOS Y SE DIFERENCIAN SOLO EN EL DATO DE MERCADO: misma forma, mismas
# claves, mismo numero de ventanas. Si el veredicto cambiara entre los dos, el check estaria
# juzgando el mercado y no el panel.
#
# DE DONDE SALE LA FORMA, medido el 2026-09-18 sobre el RELEASE DESPLEGADO en 140
# (/opt/coinalyze/releases/582459337bc7167317b4abca3b9841a3cf65b2cb):
#   · la ruta delta-matrix devuelve SIEMPRE 12 ventanas: la lista es un literal (api.py:1311-1323)
#     y el bucle que las recorre hace `rows.append` INCONDICIONAL, sin un solo `continue`
#     (scalp_logic.py:4319-4458). El numero es una constante del codigo, no de la hora.
#   · el sobre trae 5: `delta_windows` del perfil (ai_context.py:76), otra constante.
#   · `scalp_persistence` y `signal_base_rate` son claves LITERALES del dict que devuelve
#     /api/dashboard/state (api.py:3500-3502): no pueden faltar por falta de dato.
#   · `delta_matrix` y `liquidation_levels` son entradas literales del sobre (ai_context.py:861
#     y :925): tampoco pueden faltar por falta de dato.
# Conclusion MEDIDA: la UNICA ausencia que produccion puede dar hoy sin cambiar codigo es que el
# payload NO LLEGUE, y eso ya es el tercer cubo (E23-E27). Las ausencias de E30 y E33 SOLO las
# puede producir un cambio de codigo, y por eso ahi la excusa DEBE morir: es su diseno.
dm_ruta() {  # $1 = valor del delta en cada ventana. Las 12 del release, siempre las 12.
  local v="$1" w out=""
  for w in 15s 30s 1m 3m 5m 15m 18m 30m 1h 4h 8h 1d; do
    out="$out,{\"window\":\"$w\",\"delta\":$v}"
  done
  printf '[%s]' "${out#,}"
}
dm_sobre() {  # $1 = valor  $2..= ventanas. El sobre trae las 5 del perfil.
  local v="$1"; shift
  local w out=""
  for w in "$@"; do out="$out,{\"window\":\"$w\",\"delta\":$v}"; done
  printf '{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"delta_matrix":[%s]}' "${out#,}"
}
LOG_DM="VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"

echo
echo "E28 · MENOS · HORA TRANQUILA (12 ventanas, todas sin dato): EXCUSADA"
monta "$DIR/e28" 0 "$LOG_DM"
plantada "$DIR/e28" _sobre.json "$(dm_sobre null 15s 1m 3m 5m 15m)"
plantada "$DIR/e28" "_api_scalp_delta-matrix.json" "$(dm_ruta null)"
f=$(copia "$DIR/e28") || exit 2
corre E28 "$f" K44_PAYLOADS="$DIR/e28/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E28a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E28b la excusa VIVE, con sus dos cifras (12 y 5)" \
  "$(printf '%s' "${SALIDA[E28]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 5' && echo si || echo no)"

echo
echo "E29 · MENOS · HORA AGITADA (las MISMAS 12 ventanas, con dato): MISMO VEREDICTO"
monta "$DIR/e29" 0 "$LOG_DM"
plantada "$DIR/e29" _sobre.json "$(dm_sobre 91400.5 15s 1m 3m 5m 15m)"
plantada "$DIR/e29" "_api_scalp_delta-matrix.json" "$(dm_ruta 91400.5)"
f=$(copia "$DIR/e29") || exit 2
corre E29 "$f" K44_PAYLOADS="$DIR/e29/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E29a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E29b EL PUNTO: la hora no cambia el veredicto de MENOS (E28=$rc)" \
  "$([ "$rc" = 0 ] && printf '%s' "${SALIDA[E29]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 5' && echo si || echo no)"

echo
echo "E30 · MENOS · y SI CAMBIA EL CODIGO -la ruta baja a 5 ventanas- la excusa MUERE"
# Esta ausencia produccion NO la puede dar: las 12 son un literal. Si un dia la ruta sirve 5,
# el sobre ya le da todo y la peticion suelta sobra. Sin este brazo, E28/E29 pasarian igual con
# una excusa que no supiera morir.
monta "$DIR/e30" 0 "$LOG_DM"
plantada "$DIR/e30" _sobre.json "$(dm_sobre 91400.5 15s 1m 3m 5m 15m)"
plantada "$DIR/e30" "_api_scalp_delta-matrix.json" '[{"window":"15s","delta":1},{"window":"1m","delta":1},{"window":"3m","delta":1},{"window":"5m","delta":1},{"window":"15m","delta":1}]'
f=$(copia "$DIR/e30") || exit 2
corre E30 "$f" K44_PAYLOADS="$DIR/e30/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E30a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E30b y dice EXCEPCION ANULADA con la cifra que la mato" \
  "$(printf '%s' "${SALIDA[E30]}" | grep -q 'EXCEPCION ANULADA: el sobre trae 5 y la ruta 5' && echo si || echo no)"

# --- FALTAN · lo mismo con la otra excusa -------------------------------------------------
DS_TRANQUILA='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"scalp_persistence":{"available":false,"episodios":0},"signal_base_rate":{"available":false,"n":0}}'
DS_AGITADA='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"scalp_persistence":{"available":true,"episodios":6146,"p90_min":4},"signal_base_rate":{"available":true,"n":812,"tasa":0.37}}'
DS_SIN='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"scalp_persistence":{"available":true,"episodios":6146}}'
SOBRE_TESTIGOS='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{}}'
LOG_DS="VISITAS 900
450 /api/ai/context
200 /api/dashboard/state"

echo
echo "E31 · FALTAN · HORA TRANQUILA (las dos claves presentes y VACIAS): EXCUSADA"
monta "$DIR/e31" 0 "$LOG_DS"
plantada "$DIR/e31" _sobre.json "$SOBRE_TESTIGOS"
plantada "$DIR/e31" "_api_dashboard_state.json" "$DS_TRANQUILA"
f=$(copia "$DIR/e31") || exit 2
corre E31 "$f" K44_PAYLOADS="$DIR/e31/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E31a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E31b la excusa VIVE y dice DONDE busco" \
  "$(printf '%s' "${SALIDA[E31]}" | grep -q 'la ruta sirve scalp_persistence signal_base_rate y NO estan en TODO el sobre' && echo si || echo no)"

echo
echo "E32 · FALTAN · HORA AGITADA (las MISMAS claves con dato): MISMO VEREDICTO"
monta "$DIR/e32" 0 "$LOG_DS"
plantada "$DIR/e32" _sobre.json "$SOBRE_TESTIGOS"
plantada "$DIR/e32" "_api_dashboard_state.json" "$DS_AGITADA"
f=$(copia "$DIR/e32") || exit 2
corre E32 "$f" K44_PAYLOADS="$DIR/e32/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E32a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E32b EL PUNTO: la hora no cambia el veredicto de FALTAN" \
  "$([ "$rc" = 0 ] && [ "${SALIDA[E31]}" = "${SALIDA[E32]}" ] && echo si || echo no)"

echo
echo "E33 · FALTAN · y SI CAMBIA EL CODIGO -la ruta deja de servir una clave- la excusa MUERE"
# `signal_base_rate` es una clave LITERAL del dict de /api/dashboard/state (api.py:3502): esta
# ausencia solo la produce un cambio de codigo, y entonces la excusa TIENE que morir.
monta "$DIR/e33" 0 "$LOG_DS"
plantada "$DIR/e33" _sobre.json "$SOBRE_TESTIGOS"
plantada "$DIR/e33" "_api_dashboard_state.json" "$DS_SIN"
f=$(copia "$DIR/e33") || exit 2
corre E33 "$f" K44_PAYLOADS="$DIR/e33/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E33a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E33b y NOMBRA la clave que la ruta dejo de servir" \
  "$(printf '%s' "${SALIDA[E33]}" | grep -q 'la RUTA ya no sirve signal_base_rate' && echo si || echo no)"

# ── E34-E40 · «EL SOBRE NO TRAE LA CLAVE DE LA QUE HABLA LA EXCUSA» (COLA 128) ──────────────
# EL DEFECTO QUE ATACAN. La MISMA pregunta sobre el MISMO sobre daba tres respuestas segun que
# excusa fuera: MENOS condenaba (rc=1), TOPE salia al tercer cubo (rc=2) y FALTAN la daba por
# viva (rc=0). O sea que el veredicto lo decidia la fila de la tabla de excepciones y no el
# sobre. El criterio unico -decidido por el operador- es que LA EXCUSA SE SOSTIENE.
#
# LOS PLANTADOS SON LOS DE E28-E33, con UN SOLO CAMBIO: se quita la clave del sobre. Mismo log,
# misma ruta, misma forma. Si el veredicto de los tres no coincide, el defecto sigue.
SOBRE_SIN_DM='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{}}'

echo
echo "E34 · MENOS · el sobre NO TRAE \`delta_matrix\`: la excusa SE SOSTIENE"
monta "$DIR/e34" 0 "$LOG_DM"
plantada "$DIR/e34" _sobre.json "$SOBRE_SIN_DM"
plantada "$DIR/e34" "_api_scalp_delta-matrix.json" "$(dm_ruta 91400.5)"
f=$(copia "$DIR/e34") || exit 2
corre E34 "$f" K44_PAYLOADS="$DIR/e34/payloads" K44_SIMBOLO=TEST; rc=$RC; RC34=$RC
comprueba "E34a VERDE, rc=0 (rc=$rc) -antes ANULADA y ROJO-" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E34b y dice su PORQUE: el sobre no sirve ese dato, la suelta es NECESARIA" \
  "$(printf '%s' "${SALIDA[E34]}" | grep -q 'el sobre NO TRAE `delta_matrix` en absoluto' \
     && printf '%s' "${SALIDA[E34]}" | grep -q 'NECESARIA' && echo si || echo no)"

echo
echo "E35 · TOPE · el sobre NO TRAE \`liquidation_levels\`: EL MISMO tratamiento"
liqmonta "$DIR/e35" "{$TESTIGOS}" "$LIQ_LARGA"
liqcorre E35 "$DIR/e35" "$LIMITS_OK"; rc=$RC; RC35=$RC
comprueba "E35a VERDE, rc=0 (rc=$rc) -antes NO VERIFICABLE y rc=2-" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E35b y dice su PORQUE, con LA MISMA frase que MENOS" \
  "$(printf '%s' "${SALIDA[E35]}" | grep -q 'el sobre NO TRAE `liquidation_levels` en absoluto' && echo si || echo no)"

echo
echo "E36 · FALTAN · con \`clave\` declarada y AUSENTE: EL MISMO tratamiento"
# Hoy la fila FALTAN no declara clave del sobre, asi que esta rama NO SE ALCANZA con la tabla
# real: se inyecta una clave en la copia -y se comprueba que el sed MORDIO-. Sin este brazo, el
# criterio quedaria unificado solo para las filas de hoy y se rompeia la primera vez que alguien
# escribiera una clave ahi, que es justo cuando nadie estaria mirando.
monta "$DIR/e36" 0 "$LOG_DS"
plantada "$DIR/e36" _sobre.json "$SOBRE_TESTIGOS"
plantada "$DIR/e36" "_api_dashboard_state.json" "$DS_AGITADA"
f=$(copia "$DIR/e36") || exit 2
sed -i 's#| scalp_persistence,signal_base_rate *|$#| scalp_persistence,signal_base_rate | panel_extra#' "$f"
comprueba "E36-pre el plantado OCURRIO: la fila FALTAN ya declara clave del sobre" \
  "$(grep -q 'FALTAN | scalp_persistence,signal_base_rate | panel_extra' "$f" && echo si || echo no)"
corre E36 "$f" K44_PAYLOADS="$DIR/e36/payloads" K44_SIMBOLO=TEST; rc=$RC; RC36=$RC
comprueba "E36a VERDE, rc=0 (rc=$rc) -antes ANULADA y ROJO-" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E36b y dice su PORQUE, con LA MISMA frase que las otras dos" \
  "$(printf '%s' "${SALIDA[E36]}" | grep -q 'el sobre NO TRAE `panel_extra` en absoluto' && echo si || echo no)"

echo
echo "E37 · EL PUNTO · los TRES tipos dan el MISMO veredicto ante la MISMA ausencia"
# SE CUENTAN BRAZOS, NO APARICIONES. La primera version conto las veces que sale la frase en la
# concatenacion de los tres y pidio 3: K44 la escribe DOS veces por corrida -en el veredicto por
# ruta y otra vez en la linea de excusadas-, asi que salian 6 y el brazo fallaba por su propia
# aritmetica. Es A4 en el control: leer el formato del sujeto como si fuera su contenido.
n_unif=0
for _e in E34 E35 E36; do
  printf '%s' "${SALIDA[$_e]}" | grep -q 'en absoluto' && n_unif=$((n_unif+1))
done
comprueba "E37 los 3 tipos dicen la MISMA frase ($n_unif de 3) y los 3 dan rc=0" \
  "$([ "$n_unif" = 3 ] && [ "$RC34" = 0 ] && [ "$RC35" = 0 ] && [ "$RC36" = 0 ] && echo si || echo no)"

echo
echo "E38 · LA LISTA VACIA NO SE TOCA · MENOS con \`delta_matrix\` presente y VACIA"
# Ausente y vacia NO son lo mismo y el criterio nuevo no las mezcla: ausente es una propiedad del
# codigo, vacia es el mercado (A53). Sin este brazo, unificar de mas pasaria desapercibido.
monta "$DIR/e38" 0 "$LOG_DM"
plantada "$DIR/e38" _sobre.json '{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"delta_matrix":[]}'
plantada "$DIR/e38" "_api_scalp_delta-matrix.json" "$(dm_ruta 91400.5)"
f=$(copia "$DIR/e38") || exit 2
corre E38 "$f" K44_PAYLOADS="$DIR/e38/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E38a VERDE, rc=0 (rc=$rc), COMO ANTES" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E38b y por la via de siempre -12 contra 0-, NO por la de la clave ausente" \
  "$(printf '%s' "${SALIDA[E38]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 0' \
     && printf '%s' "${SALIDA[E38]}" | grep -q 'en absoluto' && echo no || echo si)"

echo
echo "E39 · LA LISTA VACIA NO SE TOCA · FALTAN con el AMBITO presente y VACIO sigue ANULADA"
# La guarda de vacuidad: sobre un ambito vacio cualquier clave falta sola. Si la unificacion se
# hubiera llevado por delante este caso, la excusa se cumpliria por construccion.
monta "$DIR/e39" 0 "$LOG_DS"
plantada "$DIR/e39" _sobre.json '{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"panel_extra":{}}'
plantada "$DIR/e39" "_api_dashboard_state.json" "$DS_AGITADA"
f=$(copia "$DIR/e39") || exit 2
sed -i 's#| scalp_persistence,signal_base_rate *|$#| scalp_persistence,signal_base_rate | panel_extra#' "$f"
corre E39 "$f" K44_PAYLOADS="$DIR/e39/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E39a ROJO, rc=1 (rc=$rc), COMO ANTES" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E39b y por la guarda de vacuidad, no por la clave ausente" \
  "$(printf '%s' "${SALIDA[E39]}" | grep -q 'viene VACIA en el sobre' && echo si || echo no)"

echo
echo "E40 · TOPE · la clave PRESENTE pero con una forma que no es una lista de filas: TERCER CUBO"
# Ausente y «no se sabe leer» caian antes en el mismo saco. Lo primero es decidible; lo segundo
# no, y sigue sin excusar y sin condenar.
liqmonta "$DIR/e40" "{$TESTIGOS,\"liquidation_levels\":\"no-soy-una-lista\"}" "$LIQ_LARGA"
liqcorre E40 "$DIR/e40" "$LIMITS_OK"; rc=$RC
comprueba "E40a NO MEDIDO, rc=2 (rc=$rc): ni excusa ni condena" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E40b y lo dice: la trae, pero NO como lista de filas" \
  "$(printf '%s' "${SALIDA[E40]}" | grep -q 'pero NO como lista de filas' && echo si || echo no)"

# ══ LAS PANTALLAS (campana 133) ══════════════════════════════════════════════════════════════
# Cada brazo planta una VENTANA de eventos -cargas de documento, peticiones y cambios del
# desplegador, cliente a cliente- y mira lo que K44 dice de CADA pantalla. Los P* miden lo que
# trajo la 133 y TIENEN QUE CAER contra los bytes de main (REPO=<arbol de main>): ahi K44 llama
# «panel» a cualquier navegador. Los G* son GUARDAS de lo que ya valia antes, y pasan en los dos:
# se dicen aparte para que nadie cuente su verde como prueba de lo nuevo.
montav() {  # $1 = dir   $2 = eventos (ver genera.py)
  rm -rf "$1"; mkdir -p "$1/bin" "$1/payloads"
  printf '%s\n' ". /srv/coinanalyze/harness/env" > "$1/env"
  printf '%s\n' "$2" | python3 "$GEN" ventana "$AHORA" > "$1/salida"
  printf '%s\n' "#!/bin/bash" "printf 'LLAMADO\\n' >> $1/senal" "cat $1/salida" "exit 0" > "$1/bin/prod"
  chmod +x "$1/bin/prod"; : > "$1/senal"
  printf '%s\n' '{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{}}' > "$1/payloads/_sobre.json"
}
corrv() {  # $1 = etiqueta  $2 = dir  resto = VAR=valor
  local etq="$1" d="$2"; shift 2
  local f; f=$(copia "$d") || exit 2
  corre "$etq" "$f" K44_PAYLOADS="$d/payloads" K44_SIMBOLO=TEST K44_LIMITS=/no/existe "$@"
}
# LAS SALIDAS SE MIRAN EN FICHERO, NO POR TUBERIA (A89): `printf "$VAR" | grep -q` con mas de
# 64 KB no llega nunca al `&&`.
tiene() {  # tiene <etiqueta> <ERE>  -> si|no, sobre TODA la salida
  printf '%s\n' "${SALIDA[$1]}" > "$DIR/_sal"; grep -qE -- "$2" "$DIR/_sal" && echo si || echo no
}
no_tiene() {  # no_tiene <etiqueta> <ERE>  -> si|no
  printf '%s\n' "${SALIDA[$1]}" > "$DIR/_sal"; grep -qE -- "$2" "$DIR/_sal" && echo no || echo si
}
en_primera() {  # en_primera <etiqueta> <ERE>  -> si|no, SOLO la primera linea: la que cita el marcador
  printf '%s\n' "${SALIDA[$1]}" | awk 'NR==1' > "$DIR/_pri"; grep -qE -- "$2" "$DIR/_pri" && echo si || echo no
}
S1="symbol=BTCUSDT_PERP.A"
# LAS RUTAS DE ESTOS BRAZOS SE ESCRIBEN "$A/..." Y NO EN LITERAL, y no es estilo. bin/arquitectura
# acredita como CONSUMIDOR de una ruta a toda linea de codigo que la nombre: escritas en literal, este
# control pasaba a «llamar» a /api/setup y K88 se puso ROJO contra la ficha declarada que dice que
# nadie la llama (medido en la 133). Es la autocontaminacion que K31-control ya cuenta: no escribirlas.
A=/api
ev_mesa() {  # ev_mesa <cliente> <seg> [marco] · una carga de la vista principal y 40 refrescos de DECIDE
  local c=$1 s=$2 m=${3:-scalp} r
  echo "A $c $s 1 $A/mesa/decide?$S1&frame=$m"
  for r in $A/quality/feeds $A/scalp/signals $A/scalp/delta-matrix $A/setup $A/signals/replay; do
    echo "A $c $((s + 1)) 1 $r?$S1"
  done
  case $m in
    scalp) for r in $A/scalp/orderbook $A/liquidation-map $A/volume-profile; do echo "A $c $((s + 2)) 1 $r?$S1"; done ;;
    swing) for r in $A/wyckoff $A/oi-context $A/liquidation-map $A/volume-profile; do echo "A $c $((s + 2)) 1 $r?$S1"; done ;;
    largo) for r in $A/structure-detail $A/scalp/basis $A/external-macro; do echo "A $c $((s + 2)) 1 $r?$S1"; done ;;
  esac
  echo "A $c $((s + 15)) 40 $A/mesa/decide?$S1&frame=$m"
}
ev_panel() {  # ev_panel <cliente> <seg> <n> · el panel viejo: el sobre n veces, y una serie y una exenta (ninguna FOTO)
  local c=$1 s=$2 n=$3
  echo "A $c $s $n $A/ai/context?$S1&profile=default"
  echo "A $c $((s + n)) 5 $A/ohlcv?$S1&interval=5min&limit=576"
  echo "A $c $((s + n + 5)) 3 $A/symbols"
}

echo
echo "P1 · SOLO LA MESA, en \`/\` despues del cambio: se juzga contra SU contrato, no contra el sobre"
montav "$DIR/p1" "$(echo 'D -86400 mesa'; echo 'C alex -10800 /'; ev_mesa alex -10790)"
corrv P1 "$DIR/p1"; rc=$RC
comprueba "G2 (guarda) el plantado OCURRIO: el prod de mentira se llamo" "$([ -s "$DIR/p1/senal" ] && echo si || echo no)"
comprueba "P1b VERDE, rc=0 (rc=$rc): la mesa no pide el sobre por diseno" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "P1c la PRIMERA linea nombra la mesa y la ruta por la que se cargo" \
  "$(en_primera P1 'la mesa \(static/mesa\.html, cargada por `/`\) pide su nucleo '"$A"'/mesa/decide 41 veces y NADA fuera de su contrato')"
comprueba "P1d y dice cuantas de sus rutas son FOTO: 4 de las 9 pedidas" \
  "$(tiene P1 '9 de sus 15 rutas declaradas, 4 de ellas de la familia FOTO')"
comprueba "P1e y el panel viejo, que nadie miro, sale SIN VISITAS y no condenado" \
  "$(en_primera P1 'el panel viejo \(static/index\.html\): sin visitas')"
comprueba "P1f y no acusa a NADIE de no pedir el sobre" "$(no_tiene P1 'NO pide el sobre|REFORMA A MEDIAS')"

echo
echo "P2 · SOLO LA MESA, en \`/mesa\` ANTES del cambio (\`/\` era el panel)"
montav "$DIR/p2" "$(echo 'C alex -10800 /mesa'; ev_mesa alex -10790)"
corrv P2 "$DIR/p2"; rc=$RC
comprueba "P2a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "P2b cargada por \`/mesa\`, y la puerta dice que \`/\` era el panel" \
  "$([ "$(en_primera P2 'cargada por `/mesa`')" = si ] && [ "$(tiene P2 'puerta · `/` servia el panel viejo al empezar')" = si ] && echo si || echo no)"

echo
echo "P3 · SOLO EL PANEL, en \`/\` ANTES del cambio: el criterio de siempre, y dice QUE pantalla"
montav "$DIR/p3" "$(echo 'C alex -10800 /'; ev_panel alex -10790 300)"
corrv P3 "$DIR/p3"; rc=$RC
comprueba "G3 (guarda) el panel solo sigue VERDE, rc=0 (rc=$rc): el criterio de siempre intacto" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "P3b la PRIMERA linea nombra el panel viejo y su ruta" \
  "$(en_primera P3 'el panel viejo \(static/index\.html, cargado por `/`\) pide el sobre 300 veces y CERO de las [0-9]+ rutas')"
comprueba "P3c y la mesa, que nadie miro, SIN VISITAS" "$(en_primera P3 'la mesa \(static/mesa\.html\): sin visitas')"

echo
echo "P4 · SOLO EL PANEL, en \`/panel\` DESPUES del cambio"
montav "$DIR/p4" "$(echo 'D -86400 mesa'; echo 'C alex -10800 /panel'; ev_panel alex -10790 300)"
corrv P4 "$DIR/p4"; rc=$RC
comprueba "G4 (guarda) VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "P4b cargado por \`/panel\`" "$(en_primera P4 'el panel viejo \(static/index\.html, cargado por `/panel`\)')"

echo
echo "P5 · LAS DOS, dos clientes: la mesa en \`/\` y el panel en \`/panel\`; cada una contra lo suyo"
montav "$DIR/p5" "$(echo 'D -86400 mesa'; echo 'C alex -10800 /'; ev_mesa alex -10790; echo 'C ipad -9000 /panel'; ev_panel ipad -8990 300)"
corrv P5 "$DIR/p5"; rc=$RC
comprueba "P5a VERDE, rc=0 (rc=$rc): ninguna de las dos se carga lo de la otra" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "P5b la PRIMERA linea juzga LAS DOS, cada una con su nombre" \
  "$([ "$(en_primera P5 'el panel viejo \(static/index\.html, cargado por `/panel`\) pide el sobre 300 veces y CERO')" = si ] \
     && [ "$(en_primera P5 'la mesa \(static/mesa\.html, cargada por `/`\) pide su nucleo')" = si ] && echo si || echo no)"
comprueba "G5 (guarda) y no inventa peticiones sin atribuir donde no las hay" "$(no_tiene P5 'SIN ATRIBUIR')"

echo
echo "P6 · LAS DOS piden $A/wyckoff (la mesa por contrato, el panel sin excusa): a cada uno lo SUYO"
montav "$DIR/p6" "$(echo 'D -86400 mesa'; echo 'C alex -10800 /'; ev_mesa alex -10790 swing
                     echo "A alex -9000 20 $A/wyckoff?$S1"
                     echo 'C ipad -9000 /panel'; ev_panel ipad -8990 300; echo "A ipad -7000 7 $A/wyckoff?$S1")"
corrv P6 "$DIR/p6"; rc=$RC
comprueba "P6a ROJO, rc=1 (rc=$rc), y le cuenta al panel SOLO sus 7, no las 28 de las dos pantallas" \
  "$([ "$rc" = 1 ] && [ "$(en_primera P6 'REFORMA A MEDIAS: el panel viejo \(static/index\.html, cargado por `/panel`\) pide el sobre 300 veces Y ADEMAS sigue pidiendo 7 veces 1 de las')" = si ] \
     && [ "$(tiene P6 '· '"$A"'/wyckoff\(7\)')" = si ] && echo si || echo no)"
comprueba "P6c y la mesa, con las suyas dentro del contrato, VERDE en la misma linea" \
  "$(en_primera P6 'la mesa \(static/mesa\.html, cargada por `/`\) pide su nucleo '"$A"'/mesa/decide 41 veces y NADA fuera')"

echo
echo "P7 · CRUZA EL CAMBIO: una pestana del panel cargada en \`/\` ANTES sigue pidiendo DESPUES"
# El caso que obliga a todo. alex carga `/` a -4 h (el panel), el desplegador cambia `/` a la
# mesa a -2 h, la pestana vieja sigue pidiendo el sobre 3000 veces DESPUES del cambio, y a -1000 s
# alex recarga `/` -ya la mesa-. Por la ruta sola, esas 3000 serian de la mesa y la condenarian.
montav "$DIR/p7" "$(echo 'D -7200 mesa'; echo 'C alex -14400 /'
                     echo "A alex -14390 7000 $A/ai/context?$S1&profile=default"
                     echo "A alex -7000 3000 $A/ai/context?$S1&profile=default"
                     echo 'C alex -1000 /'; ev_mesa alex -990)"
corrv P7 "$DIR/p7"; rc=$RC
comprueba "P7a las 3000 de DESPUES del cambio son del panel: pide el sobre 10000 veces" \
  "$(en_primera P7 'el panel viejo \(static/index\.html, cargado por `/`\) pide el sobre 10000 veces')"
# Esta ausencia main la cumple EN VACIO -main no juzga la mesa-, asi que es una guarda; lo que
# prueba que la mide es V1, mas abajo: la variante que atribuye por la ruta sola SI la incumple.
comprueba "G7 (guarda) la mesa NO se carga el sobre de la pestana vieja (nada FUERA de contrato)" "$(no_tiene P7 'FUERA de su contrato')"
comprueba "P7c lo de despues de la recarga sale NOMBRADO y sin cargar: 49, las DOS pantallas" \
  "$([ "$(en_primera P7 '49 peticion\(es\) SIN ATRIBUIR')" = si ] && [ "$(tiene P7 'LAS DOS pantallas')" = si ] && echo si || echo no)"
comprueba "P7d y la puerta dice el cambio que leyo del desplegador" \
  "$(tiene P7 'cambios del desplegador dentro: [0-9-]+ [0-9:]+Z release 2222222 -> la mesa')"
comprueba "P7e VERDE, rc=0 (rc=$rc): lo atribuido cumple y lo no atribuido no condena" "$([ "$rc" = 0 ] && echo si || echo no)"

echo
echo "P8 · UNA CARGA DE \`/\` A 30 s DEL CAMBIO: dentro del margen, ambigua, se nombra"
montav "$DIR/p8" "$(echo 'D -7200 mesa'; echo 'C ipad -7170 /'; ev_mesa ipad -7160)"
corrv P8 "$DIR/p8"; rc=$RC
comprueba "P8a NO MEDIDO, rc=2 (rc=$rc): no se juzga a ninguna" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "P8b y dice por que: 30 s del cambio, dentro del margen de 120 s" \
  "$(tiene P8 'carga de `/` a 30 s del cambio \(el panel viejo -> la mesa, [^)]*\), dentro del margen de 120 s')"

echo
echo "P9 · UNA VUELTA ATRAS del desplegador devuelve \`/\` al panel"
montav "$DIR/p9" "$(echo 'D -20000 mesa'; echo 'B -7200 panel'; echo 'C alex -5000 /'; ev_panel alex -4990 300)"
corrv P9 "$DIR/p9"; rc=$RC
comprueba "P9a VERDE, rc=0 (rc=$rc), y la carga de \`/\` tras la vuelta atras es del panel" \
  "$([ "$rc" = 0 ] && [ "$(en_primera P9 'el panel viejo \(static/index\.html, cargado por `/`\) pide el sobre 300 veces')" = si ] && echo si || echo no)"

echo
echo "P10 · PETICIONES SIN NINGUNA CARGA VISIBLE (una pestana de antes del log)"
montav "$DIR/p10" "$(echo 'D -86400 mesa'; ev_mesa alex -10790)"
corrv P10 "$DIR/p10"; rc=$RC
comprueba "P10a NO MEDIDO, rc=2 (rc=$rc): 49 peticiones y NINGUNA atribuible" \
  "$([ "$rc" = 2 ] && [ "$(en_primera P10 'hubo 49 peticiones de navegador .* NINGUNA se pudo atribuir')" = si ] && echo si || echo no)"
comprueba "P10b y nombra el motivo con sus rutas" \
  "$(tiene P10 'sin carga visible de ninguna pantalla en las 48 h de cargas que se miran: .*'"$A"'/mesa/decide\(41\)')"

echo
echo "P11 · LA CARGA ES DE HACE 50 h: fuera de las 48 h que se miran, tampoco se atribuye"
montav "$DIR/p11" "$(echo 'C alex -180000 /mesa'; ev_mesa alex -10790)"
corrv P11 "$DIR/p11"; rc=$RC
comprueba "P11a NO MEDIDO, rc=2 (rc=$rc), por «sin carga visible»" \
  "$([ "$rc" = 2 ] && [ "$(tiene P11 'sin carga visible de ninguna pantalla')" = si ] && echo si || echo no)"

echo
echo "P12 · UN RELEASE DEL QUE NI 140 NI git DICEN QUE SIRVE \`/\`"
montav "$DIR/p12" "$(echo 'SIN_R'; echo 'D -86400 rara'; echo 'C alex -10800 /'; ev_mesa alex -10790)"
corrv P12 "$DIR/p12"; rc=$RC
comprueba "P12a NO MEDIDO, rc=2 (rc=$rc): la carga de \`/\` no se puede atribuir" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "P12b y lo dice con el release" "$(tiene P12 'con el release 3333333, del que no se sabe que servia')"

echo
echo "P13 · LA MESA PIDE UNA RUTA QUE SU CONTRATO NO DECLARA"
montav "$DIR/p13" "$(echo 'D -86400 mesa'; echo 'C alex -10800 /'; ev_mesa alex -10790; echo "A alex -9000 3 $A/ai/context?$S1")"
corrv P13 "$DIR/p13"; rc=$RC
comprueba "P13a ROJO, rc=1 (rc=$rc), y es LA MESA la condenada, nombrando la ruta y su cuenta" \
  "$([ "$rc" = 1 ] && [ "$(en_primera P13 'la mesa \(static/mesa\.html, cargada por `/`\) pide FUERA de su contrato \(K44-contrato-mesa\.tsv\): '"$A"'/ai/context\(3\)')" = si ] && echo si || echo no)"

echo
echo "P14 · LA MESA CARGA SU VISTA PRINCIPAL Y NO PIDE SU NUCLEO"
montav "$DIR/p14" "$(echo 'C alex -10800 /mesa'; for r in $A/scalp/signals $A/setup $A/scalp/orderbook; do echo "A alex -10790 2 $r?$S1"; done)"
corrv P14 "$DIR/p14"; rc=$RC
comprueba "P14a ROJO, rc=1 (rc=$rc), y dice que NO pide su nucleo" \
  "$([ "$rc" = 1 ] && [ "$(en_primera P14 'carga su vista principal .* y NO pide su nucleo '"$A"'/mesa/decide')" = si ] && echo si || echo no)"

echo
echo "P15 · LA MESA SOLO EN SU VISTA DE ESTADO: no pide el nucleo y NO es un defecto"
montav "$DIR/p15" "$(echo 'C alex -10800 /mesa'; echo "A alex -10790 3 $A/healthz"; echo "A alex -10780 3 $A/quality/feeds?$S1")"
corrv P15 "$DIR/p15"; rc=$RC
comprueba "P15a VERDE, rc=0 (rc=$rc), y lo dice" \
  "$([ "$rc" = 0 ] && [ "$(en_primera P15 'solo se miro en su vista de ESTADO, que no pide el nucleo')" = si ] && echo si || echo no)"

echo
echo "P16 · LA MESA SE MIRO Y SU CONTRATO NO SE PUEDE LEER"
montav "$DIR/p16" "$(echo 'C alex -10800 /mesa'; ev_mesa alex -10790)"
corrv P16 "$DIR/p16" K44_CONTRATO=/no/existe; rc=$RC
comprueba "P16a NO MEDIDO, rc=2 (rc=$rc): sin contrato no hay contra que juzgarla" \
  "$([ "$rc" = 2 ] && [ "$(en_primera P16 'su contrato no se pudo leer')" = si ] && echo si || echo no)"

echo
echo "P17 · EL CANAL CONTESTA rc=0 PERO SIN LA MARCA FINAL: respuesta incompleta"
mkdir -p "$DIR/p17"; montav "$DIR/p17" "$(echo 'C alex -10800 /mesa'; ev_mesa alex -10790)"
grep -v '^K44-FIN$' "$DIR/p17/salida" > "$DIR/p17/s2"; mv "$DIR/p17/s2" "$DIR/p17/salida"
corrv P17 "$DIR/p17"; rc=$RC
comprueba "P17a NO MEDIDO, rc=2 (rc=$rc), y dice INCOMPLETO, no «nadie miro»" \
  "$([ "$rc" = 2 ] && [ "$(tiene P17 'llego INCOMPLETO')" = si ] && echo si || echo no)"

echo
echo "P18 · MAS DE 64 KB DE LOG, EN LOS DOS MODOS DE SIGPIPE (A89): misma salida, y la 1a linea es el veredicto"
montav "$DIR/p18" "$(echo 'D -86400 mesa'; echo 'C alex -14000 /'; ev_mesa alex -13990; echo "A alex -13000 3000 $A/mesa/decide?$S1&frame=scalp")"
tam=$(wc -c < "$DIR/p18/salida")
f18=$(copia "$DIR/p18") || exit 2
env --ignore-signal=PIPE K44_PAYLOADS="$DIR/p18/payloads" K44_SIMBOLO=TEST K44_LIMITS=/no/existe \
  timeout -k 5 200 bash "$f18" > "$DIR/p18/ign" 2>&1; rc_i=$?
env --default-signal=PIPE K44_PAYLOADS="$DIR/p18/payloads" K44_SIMBOLO=TEST K44_LIMITS=/no/existe \
  timeout -k 5 200 bash "$f18" > "$DIR/p18/def" 2>&1; rc_d=$?
printf '        sujeto: %s B de log plantado (el brazo exige mas de 65536) · rc ignorado=%s omision=%s\n' "$tam" "$rc_i" "$rc_d"
comprueba "G18 (guarda del sujeto) el log plantado PASA de 64 KB, medido ($tam B)" "$([ "$tam" -gt 65536 ] && echo si || echo no)"
comprueba "P18b las dos salidas IGUALES byte a byte, y rc=0 las dos" \
  "$(cmp -s "$DIR/p18/ign" "$DIR/p18/def" && [ "$rc_i" = 0 ] && [ "$rc_d" = 0 ] && echo si || echo no)"
comprueba "P18c la 1a linea con SIGPIPE IGNORADO es el veredicto, no un «Broken pipe»" \
  "$(awk 'NR==1' "$DIR/p18/ign" | grep -q '^la mesa (static/mesa.html, cargada por `/`) pide su nucleo '"$A"'/mesa/decide 3041 veces' && echo si || echo no)"

echo
echo "G1 · GUARDA (ya valia antes): el ARNES no cuenta aunque venga con agente de navegador"
montav "$DIR/g1" "$(echo 'C arnes -10800 /mesa'; ev_mesa arnes -10790)"
corrv G1 "$DIR/g1"; rc=$RC
comprueba "G1a NO MEDIDO, rc=2 (rc=$rc): «no consta que nadie mirara»" \
  "$([ "$rc" = 2 ] && [ "$(tiene G1 'no consta que nadie mirara')" = si ] && echo si || echo no)"

echo
echo "V1 · LA VARIANTE QUE ATRIBUYE \`/\` POR LA HORA DE LA PETICION -la ruta sola, A68-: P7 la tiene que cazar"
# Una copia del check con UNA linea cambiada: la pantalla de una carga de `/` se mira a la hora de
# cada PETICION, no a la de la carga. Es justo «atribuir por la ruta sola»: tras el cambio, todo lo
# que llega con `/` seria de la mesa. Si la ventana de P7 no la condena, P7 no mide el cruce.
rm -rf "$DIR/v1"; cp -a "$DIR/p7" "$DIR/v1"
sed -e "s#^B=/srv/coinanalyze/harness; . \"\$B/env\"#B=$DIR/v1; . \"\$B/env\"#" \
    -e 's/^    ps = {c\[2\] for c in previas}$/    ps = {((pantalla_raiz(t)[0] or c[2]) if c[1] == "\/" else c[2]) for c in previas}/' \
    "$CHK" > "$DIR/v1/K44.sh"
mordio=$(grep -c 'pantalla_raiz(t)\[0\] or c\[2\]) if c\[1\]' "$DIR/v1/K44.sh")
comprueba "V1a la variante SE PLANTO (una linea cambiada, contada: $mordio)" "$([ "$mordio" = 1 ] && echo si || echo no)"
corre V1 "$DIR/v1/K44.sh" K44_PAYLOADS="$DIR/v1/payloads" K44_SIMBOLO=TEST K44_LIMITS=/no/existe
comprueba "V1b y la ventana del cruce la CONDENA: carga a la mesa el sobre de la pestana vieja" \
  "$([ "$RC" = 1 ] && [ "$(en_primera V1 'la mesa \(static/mesa\.html, cargada por `/`\) pide FUERA de su contrato \(K44-contrato-mesa\.tsv\): '"$A"'/ai/context\(3000\)')" = si ] \
     && [ "$(en_primera V1 'pide el sobre 10000 veces')" = no ] && echo si || echo no)"

# ── LOS SEIS, DOS A DOS ──────────────────────────────────────────────────────────────────────
echo
echo "LOS SEIS ESTADOS · si dos dan la MISMA salida, no distingue lo que dice distinguir"
iguales=""
for a in E1 E2 E3 E4 E5 E6; do
  for b in E1 E2 E3 E4 E5 E6; do
    [ "$a" \< "$b" ] || continue
    [ "${SALIDA[$a]}" = "${SALIDA[$b]}" ] && iguales="$iguales $a=$b"
  done
done
comprueba "S1 los 6 dan 6 salidas DISTINTAS (repetidas:${iguales:- ninguna})" \
  "$([ -z "$iguales" ] && echo si || echo no)"
# y el reparto de rc, que NO es el criterio: tres comparten rc a proposito
printf '        rc: E1=2 E2=2 E3=2 (NOMED) · E4=0 (VERDE) · E5=1 E6=1 (ROJO)\n'
printf '        por eso se comparan SALIDAS y no rc: dos estados con el mismo rc\n'
printf '        son indistinguibles para quien solo mire el marcador.\n'

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
