#!/bin/bash
# K117-control · LOS PLANTADOS QUE TIENEN QUE FALLAR EN K117 (campana BOT-2).
#
# EL ESCENARIO BUENO, sin produccion: un arnes de mentira cuyos bin/prodsql y bin/prod contestan desde un directorio
# de fixtures. Las velas son ohlcv 1min REAL de 140 (K117-velas.tsv.xz, 2026-10-19 21:00Z .. 10-21 00:10Z); el
# registro de alertas lo escribe el CODIGO DEL BOT (app/bot/centinela.py) sobre esas velas; ahora = 10-21 00:50Z (la
# ventana de K117 cubre la cascada del 10-20 14:01-14:02Z y ETH 15:13Z); latido de hace 30 s, Bybit de solo lectura y
# atada a la IP, la unidad active/running, gasto 1.25 de 3 USD, release sin rutas; y (remate 1) el interruptor con su
# temporizador activo que paso hace 100 s sin problemas, el parte del 10-20 a las 13:00Z, y 1234 lineas de journal sin
# ninguna forma de clave. -> VERDE, con las alertas juzgadas.
# Cada plantado, en su copia:
#
#   ruta_arbol        «/v5/order/create» en app/bot/bybit.py de una copia del arbol            ROJO ruta en el arbol
#   ruta_release      el grep del release de 140 encuentra /v5/order                           ROJO ruta en el release
#   alerta_de_mas     una rafaga de ETH registrada donde el detector no da ninguna              ROJO el detector NO da
#   alerta_que_falta  falta en el registro la primera rafaga de la ventana                      ROJO faltan
#   clase_cambiada    una CASCADA registrada como BARRIDO                                       ROJO el detector NO da
#   gasto_sobre_tope  el 10-20 gasto 3.40 con tope 3                                            ROJO gasto
#   bybit_opera       el estado del bot: solo_lectura false                                     ROJO PUEDE OPERAR
#   ip_no_atada       el estado del bot: ip_ok false                                            ROJO no atada a la IP
#   latido_viejo      el ultimo latido de hace 600 s                                            ROJO latido
#   servicio_caido    ActiveState=failed                                                        ROJO failed/failed
#   sin_servicio      sin tablas bot_*, la unidad not-found, el release sin app/bot             NO MEDIDO no instalada
#   canal_prod        bin/prod no devuelve nada (sin marco)                                     NO MEDIDO sin su marco
#   bybit_sin_juzgar  el estado del bot no pudo juzgar la clave                                 NO MEDIDO
#   arbol_roto        K117_REPO a un directorio vacio                                           NO MEDIDO
#   (remate 1)
#   vigia_no_avisa    el bot sin latir 600 s cuando paso el interruptor, que no lo da por problema  ROJO no avisa
#   vigia_parado      el interruptor paso hace 3600 s                                           ROJO no pasa
#   vigia_apagado     su temporizador inactive                                                  ROJO el temporizador
#   vigia_sin_canal   un problema sin avisar y el envio fallido                                 ROJO no pudo avisar
#   parte_no_sale     el ultimo parte, del 10-19                                                ROJO el parte no salio
#   clave_en_log      3 lineas del journal con forma de clave                                   ROJO forma de clave
#
# Y el check: sus tres invocaciones (A56) y los dos modos de SIGPIPE (A89) sobre el escenario bueno. Al salir: el
# arbol intacto y nada en el temporal. No toca produccion, ni el espejo, ni una base.
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K117-el-bot.sh"
VE="$AQUI/K117-velas.tsv.xz"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY=$(command -v python3)
for f in "$CHK" "$AQUI/K117-bot.py" "$VE" "$REPO/app/rafagas.py" "$REPO/app/bot/centinela.py"; do
  [ -r "$f" ] || { echo "control: falta $f"; exit 2; }
done
T=$(mktemp -d) || exit 2
trap 'rm -rf "$T"' EXIT
trap 'rm -rf "$T"; trap - EXIT; exit 143' INT TERM
ARBOL_ANTES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)

# --- el arnes de mentira: contesta por el nombre de la tabla de la consulta, desde $K117_FX
mkdir -p "$T/h/bin"
cat > "$T/h/bin/prodsql" <<'SH'
#!/bin/sh
q="$*"
case "$q" in
  *bot_estado*) f=estado ;; *bot_evento*\'parte\'*) f=parte ;; *bot_evento*arranque*) f=arranque ;; *bot_evento*) f=eventos ;;
  *ohlcv*) f=velas ;; *bot_llamada*) f=gasto ;; *) f=ahora ;;
esac
[ -r "$K117_FX/$f" ] || { echo "psql:<stdin>:1: ERROR:  relation \"$f\" does not exist" >&2; exit 3; }
cat "$K117_FX/$f"
SH
cat > "$T/h/bin/prod" <<'SH'
#!/bin/sh
case "$*" in
  *journalctl*) f=journal ;; *coinalyze-bot-vigia.timer*) f=vigia ;; *systemctl*) f=systemctl ;; *grep*) f=codigo ;; *) f=nada ;;
esac
[ -r "$K117_FX/$f" ] && cat "$K117_FX/$f"
exit 0
SH

# --- el escenario bueno
B0="$T/fx/base"; mkdir -p "$B0"
xz -dc "$VE" > "$B0/velas" || { echo "control: no descomprimo $VE"; exit 2; }
"$PY" -S - "$REPO" "$B0" <<'PY' || { echo "control: no genero el registro"; exit 2; }
import json, sys
from datetime import UTC, datetime
repo, fx = sys.argv[1:]
sys.path.insert(0, repo)
import app
import app.bot.centinela as cen
assert app.__file__.startswith(repo + "/"), app.__file__
filas = {a: {} for a in cen.ACTIVOS}
for ln in open(f"{fx}/velas"):
    a, m, *x = ln.rstrip("\n").split("|")
    filas[a][int(m)] = tuple(map(float, x))
ahora = int(datetime(2026, 10, 21, 0, 50, tzinfo=UTC).timestamp())
hasta = min(max(f) for f in filas.values()) + 1
ev = []
for d in (datetime(2026, 10, 20, tzinfo=UTC), datetime(2026, 10, 21, tzinfo=UTC)):
    for r in cen.rafagas_del_dia(filas, int(d.timestamp()) // 60, hasta):
        ev.append(f"rafaga|{r['activo']}|{r['minuto']}|{r['lado']}|")
        if r["clase"]:
            ev.append(f"clase|{r['activo']}|{r['minuto']}|{r['lado']}|{r['clase']}")
estado = {"bybit": {"activo": True, "solo_lectura": True, "ip_ok": True, "ips": ["138.186.31.141"], "error": None}}
w = lambda f, t: open(f"{fx}/{f}", "w").write(t + "\n")
w("ahora", str(ahora))
vigia = {"problemas": {}, "notificados": {}, "envio": {"ok": None, "ts": None}, "canal": "puente"}
arranque = int(datetime(2026, 10, 19, 20, tzinfo=UTC).timestamp())
w("estado", f"bot|{ahora - 30}|{json.dumps(estado)}\nvigia|{ahora - 100}|{json.dumps(vigia)}")
w("arranque", str(arranque))
w("parte", f"{int(datetime(2026, 10, 20, 13, tzinfo=UTC).timestamp())}|{arranque}")
w("vigia", "LoadState=loaded\nActiveState=active\nSERVICIO-K117\nResult=success\nFIN-K117")
w("journal", "LINEAS-K117 1234\nFORMAS-K117 0\nFIN-K117")
w("eventos", "\n".join(ev))
w("gasto", "2026-10-20|1.25|3|5")
w("systemctl", "LoadState=loaded\nActiveState=active\nSubState=running\nFIN-K117")
w("codigo", "CODIGO-K117\nFIN-K117")
PY

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-18s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-18s %s\n' "$1" "$3"; fi
}
copia() {  # nombre -> una copia de los fixtures buenos
  cp -r "$B0" "$T/fx/$1"; echo "$T/fx/$1"
}
arbol() {  # nombre -> una copia del arbol que K117 juzga (detector, bot y ayudante)
  local a="$T/$1"
  mkdir -p "$a/app/bot" "$a/harness/checks"
  cp "$REPO/app/__init__.py" "$REPO/app/rafagas.py" "$a/app/"
  cp "$REPO"/app/bot/*.py "$a/app/bot/"
  cp "$AQUI/K117-bot.py" "$a/harness/checks/"
  echo "$a"
}
huella() {  # fixtures arbol -> huella del sujeto
  cat "$1"/* "$2"/app/*.py "$2"/app/bot/*.py 2>/dev/null | sha256sum | cut -c1-12
}
k117() {  # fixtures arbol -> rc; salida en $T/sal
  K117_FX="$1" K117_HARNESS="$T/h" K117_REPO="$2" K117_PY="$PY" bash "$CHK" > "$T/sal" 2>&1
  echo $?
}
sustituye() {  # fichero viejo nuevo [n]: falla si el texto viejo no esta
  "$PY" -S - "$@" <<'PY'
import sys
f, viejo, nuevo = sys.argv[1:4]
t = open(f, encoding="utf-8").read()
if viejo not in t:
    sys.exit(f"control: no encuentro {viejo!r} en {f}")
open(f, "w", encoding="utf-8").write(t.replace(viejo, nuevo, 1))
PY
}

echo "== el escenario bueno"
rc=$(k117 "$B0" "$REPO")
comprueba base_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K117 .*alertas == detector: [1-9][0-9]* rafagas' && echo 0 || echo 1)" \
  "rc=$rc · $(head -1 "$T/sal" | cut -c1-300)"
BUENA=$(arbol buena)
H_BUENA=$(huella "$B0" "$BUENA")
rc=$(k117 "$B0" "$BUENA")
comprueba copia_verde "$([ "$rc" = 0 ] && head -1 "$T/sal" | grep -q '^VERDE  K117 ' && echo 0 || echo 1)" "rc=$rc · huella $H_BUENA"

planta() {  # nombre esperado_rc patron detalle fixtures arbol
  local nombre=$1 rc_e=$2 patron=$3 que=$4 rc despues visto
  despues=$(huella "$5" "$6")
  rc=$(k117 "$5" "$6")
  visto=$(grep -E "$patron" "$T/sal" | head -1 | cut -c1-260)
  comprueba "$nombre" "$([ "$rc" = "$rc_e" ] && [ -n "$visto" ] && [ "$H_BUENA" != "$despues" ] && echo 0 || echo 1)" \
    "rc=$rc · $H_BUENA -> $despues · ${visto:-NO SALE: $(head -1 "$T/sal" | cut -c1-200)} · $que"
}

estado() {  # fixtures clave segundos_atras [campo=json ...]: reescribe la fila de bot_estado de esa clave
  "$PY" -S - "$@" <<'PY'
import json, sys
fx, clave, atras, *cambios = sys.argv[1:]
ahora = int(open(f"{fx}/ahora").read())
filas = [ln.split("|", 2) for ln in open(f"{fx}/estado").read().splitlines()]
for f in filas:
    if f[0] == clave:
        f[1] = str(ahora - int(atras))
        e = json.loads(f[2])
        for c in cambios:
            k, v = c.split("=", 1)
            e[k] = json.loads(v)
        f[2] = json.dumps(e)
open(f"{fx}/estado", "w").write("\n".join("|".join(f) for f in filas) + "\n")
PY
}

echo "== los plantados"
A=$(arbol ruta_arbol); printf 'RUTA_PLANTADA = "/v5/order/create"\n' >> "$A/app/bot/bybit.py"
planta ruta_arbol 1 "^ROJO  K117 ruta de ordenes/retiros/transferencias en el arbol: app/bot/bybit.py" "una ruta de ordenes en el codigo" "$B0" "$A"
F=$(copia ruta_release); printf 'CODIGO-K117\n/opt/coinalyze/current/app/bot/bybit.py:12:/v5/order\nFIN-K117\n' > "$F/codigo"
planta ruta_release 1 "^ROJO  K117 ruta de ordenes/retiros/transferencias en el release de 140" "el release la trae" "$F" "$BUENA"
F=$(copia alerta_de_mas); M=$(( $(cat "$F/ahora") / 60 - 300 )); printf 'rafaga|ETHUSDT|%s|1|\n' "$M" >> "$F/eventos"
planta alerta_de_mas 1 "^ROJO  K117 1 alerta\(s\) registradas que el detector NO da: ETH 10-20 19:50Z rafaga" "una alerta que el detector no da" "$F" "$BUENA"
F=$(copia alerta_que_falta)
QUITADA=$("$PY" -S - "$F" <<'PY'
import sys
fx = sys.argv[1]
a = int(open(f"{fx}/ahora").read()) // 60
ev = open(f"{fx}/eventos").read().splitlines()
k = next(i for i, ln in enumerate(ev) if ln.startswith("rafaga|BTCUSDT|") and a - 1440 <= int(ln.split("|")[2]) < a - 45)
print(ev.pop(k))
open(f"{fx}/eventos", "w").write("\n".join(ev) + "\n")
PY
)
planta alerta_que_falta 1 "^ROJO  K117 faltan 1 alerta\(s\) que el detector da: BTC 10-20" "fuera del registro: ${QUITADA:-NADA}" "$F" "$BUENA"
F=$(copia clase_cambiada)  # la primera CASCADA del registro (BTC 00:20Z) cae FUERA de la ventana: se cambia una de dentro
CAMBIADA=$("$PY" -S - "$F" <<'PY'
import sys
fx = sys.argv[1]
a = int(open(f"{fx}/ahora").read()) // 60
ev = open(f"{fx}/eventos").read().splitlines()
k = next(i for i, ln in enumerate(ev) if ln.startswith("clase|") and ln.endswith("|CASCADA") and a - 1440 <= int(ln.split("|")[2]) < a - 45)
ev[k] = ev[k].replace("|CASCADA", "|BARRIDO")
print(ev[k])
open(f"{fx}/eventos", "w").write("\n".join(ev) + "\n")
PY
)
planta clase_cambiada 1 "^ROJO  K117 1 alerta\(s\) registradas que el detector NO da: .*clase=BARRIDO" "registrada: ${CAMBIADA:-NADA}" "$F" "$BUENA"
F=$(copia gasto_sobre_tope); printf '2026-10-20|3.40|3|12\n' > "$F/gasto"
planta gasto_sobre_tope 1 "^ROJO  K117 gasto de la API por encima del tope: 2026-10-20 3.40 > 3.00 USD" "un gasto por encima del tope" "$F" "$BUENA"
F=$(copia bybit_opera); sustituye "$F/estado" '"solo_lectura": true' '"solo_lectura": false'
planta bybit_opera 1 "^ROJO  K117 el bot publica que la clave de Bybit PUEDE OPERAR" "un estado de Bybit con permiso de operar" "$F" "$BUENA"
F=$(copia ip_no_atada); sustituye "$F/estado" '"ip_ok": true' '"ip_ok": false'
planta ip_no_atada 1 "^ROJO  K117 el bot publica que la clave de Bybit no esta atada a la IP" "ip_ok false" "$F" "$BUENA"
F=$(copia latido_viejo); estado "$F" bot 600
planta latido_viejo 1 "^ROJO  K117 el ultimo latido del bot es de hace 600 s" "latido de hace 600 s" "$F" "$BUENA"
F=$(copia servicio_caido); sustituye "$F/systemctl" "ActiveState=active" "ActiveState=failed"; sustituye "$F/systemctl" "SubState=running" "SubState=failed"
planta servicio_caido 1 "^ROJO  K117 coinalyze-bot failed/failed en 140" "la unidad cayo" "$F" "$BUENA"
F=$(copia sin_servicio); rm -f "$F/estado" "$F/eventos" "$F/arranque" "$F/gasto" "$F/parte"
printf 'LoadState=not-found\nActiveState=inactive\nSubState=dead\nFIN-K117\n' > "$F/systemctl"; printf 'SIN-BOT-K117\n' > "$F/codigo"
printf 'LoadState=not-found\nActiveState=inactive\nSERVICIO-K117\nResult=success\nFIN-K117\n' > "$F/vigia"
printf 'LINEAS-K117 0\nFORMAS-K117 0\nFIN-K117\n' > "$F/journal"
planta sin_servicio 2 "^NO MEDIDO: K117 servicio: coinalyze-bot no esta instalada en 140" "lo de hoy en 140" "$F" "$BUENA"
F=$(copia canal_prod); rm -f "$F/systemctl" "$F/codigo" "$F/vigia" "$F/journal"
planta canal_prod 2 "^NO MEDIDO: K117 servicio: bin/prod sin su marco" "bin/prod mudo" "$F" "$BUENA"
F=$(copia bybit_sin_juzgar); sustituye "$F/estado" '"solo_lectura": true, "ip_ok": true' '"solo_lectura": null, "ip_ok": null'
planta bybit_sin_juzgar 2 "^NO MEDIDO: K117 bybit: el bot no pudo juzgar la clave" "clave sin juzgar" "$F" "$BUENA"
mkdir -p "$T/vacio"
planta arbol_roto 2 "^NO MEDIDO: K117 no encuentro" "K117_REPO vacio" "$B0" "$T/vacio"
F=$(copia vigia_no_avisa); estado "$F" bot 600
planta vigia_no_avisa 1 "ROJO el interruptor no avisa: el bot no late desde hace 500 s" "un interruptor que no avisa" "$F" "$BUENA"
F=$(copia vigia_parado); estado "$F" vigia 3600
planta vigia_parado 1 "^ROJO  K117 el interruptor no pasa desde hace 3600 s" "el interruptor parado" "$F" "$BUENA"
F=$(copia vigia_apagado); sustituye "$F/vigia" "ActiveState=active" "ActiveState=inactive"
planta vigia_apagado 1 "^ROJO  K117 el temporizador del interruptor esta inactive" "su temporizador apagado" "$F" "$BUENA"
F=$(copia vigia_sin_canal); estado "$F" vigia 100 'problemas={"parte:2026-10-20": "el parte no salio"}' 'envio={"ok": false, "ts": null}' 'canal="sin canal"'
planta vigia_sin_canal 1 "^ROJO  K117 el interruptor no pudo avisar de \['parte:2026-10-20'\]" "un problema sin avisar" "$F" "$BUENA"
F=$(copia parte_no_sale); printf '%s|%s\n' "$(date -u -d 2026-10-19T13:00:00Z +%s)" "$(cat "$F/arranque")" > "$F/parte"
planta parte_no_sale 1 "^ROJO  K117 el parte de 10-20 no salio \(el ultimo: 10-19 13:00Z\)" "un parte que no sale" "$F" "$BUENA"
F=$(copia clave_en_log); printf 'LINEAS-K117 1234\nFORMAS-K117 3\nFIN-K117\n' > "$F/journal"
planta clave_en_log 1 "^ROJO  K117 3 linea\(s\) del journal del bot con FORMA de clave" "una clave con su forma en el log" "$F" "$BUENA"

echo "== el check: A89 los dos modos de SIGPIPE y A56 las tres invocaciones, sobre el escenario bueno"
export K117_FX="$B0" K117_HARNESS="$T/h" K117_PY="$PY"
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env "$modo" bash "$CHK" > "$T/chk" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K117 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
done
(bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_absoluta "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K117 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd "$REPO" && bash harness/checks/K117-el-bot.sh > "$T/chk" 2>&1); rc=$?
comprueba invocacion_relativa "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K117 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
(cd /tmp && bash "$CHK" > "$T/chk" 2>&1); rc=$?
comprueba invocacion_ajena "$([ "$rc" = 0 ] && head -1 "$T/chk" | grep -q '^VERDE  K117 ' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/chk" | cut -c1-90)"
unset K117_FX K117_HARNESS K117_PY

echo "== restaurado"
ARBOL_DESPUES=$(git -C "$REPO" status --porcelain 2>/dev/null | sha256sum | cut -c1-12)
comprueba arbol_intacto "$([ "$ARBOL_ANTES" = "$ARBOL_DESPUES" ] && echo 0 || echo 1)" "git status del arbol $ARBOL_ANTES -> $ARBOL_DESPUES"

echo
echo "K117-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
