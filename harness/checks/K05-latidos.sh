#!/bin/bash
# K05  /api/healthz tiene que vigilar TODAS las filas de pipeline_heartbeat, y lo que
#      publica sobre ellas tiene que ser cierto SOSTENIDAMENTE, no en una muestra suelta.
#
# El fallo real NO era el parseo del check anterior. Es este: "services" en la
# respuesta es records(heartbeats) (app/api.py:2029), o sea un ECO de la tabla.
# Comparar la tabla contra "services" es una tautologia y nace VERDE siempre.
# Quien decide si un latido esta rancio es el dict thresholds (app/api.py:1992-2002):
# 7 claves = ingest, ws, scalp, daily, api, mas las 2 de INGEST_COMPONENT_MAX_AGES
# (app/db.py:14). required_heartbeat_failures (app/db.py:21-47) itera SOLO sobre
# esas 7, asi que una fila que no este ahi no puede poner degraded jamas.
#
# Prueba viva medida el 2026-08-25 contra 140: ws-binance y ws-bybit llevan
# 1303034 s (15.08 dias) sin latir, con status 'ok', y healthz nunca dijo nada.
# Se quedaron congeladas el 2026-08-09 19:00:59, que es cuando 5ed802f
# ("make collectors horizontally safe") renombro el servicio a ws-<ex>:<shard>/<n>.
#
# CRITERIO 1 (COBERTURA, el de siempre, POR MUESTRA Y ASI SE QUEDA): la tabla tiene que
# estar contenida en el conjunto que healthz DECLARA vigilar. Mientras healthz no declare
# nada, no hay forma honrada de saber desde fuera que se vigila, y eso ya es el fallo.
# Se juzga sobre la respuesta de AHORA porque es una propiedad del CONTRATO, no del estado:
# no parpadea, y una sola muestra basta para leerlo.
#
# CRITERIO 2 (ESTADO), anadido el 2026-09-02: algun servicio GOBERNADO publica status
# distinto de ok, con su detail LITERAL en el mensaje.
# CRITERIO 3 (STATUS GLOBAL), anadido el 2026-09-03: healthz.status no dice ok.
#
# POR QUE HICIERON FALTA, y es la clase de fallo que este arnes existe para no repetir: el
# 2026-09-02, de 14:40Z a 15:11Z, produccion perdio Binance -el venue principal- durante 31
# minutos en un bucle de reconexion (35 disconnected contra 2 connected, backoff de 1 a
# 60 s), con la tabla de trades a CERO mientras bybit seguia a 36/min. EL ARNES DIO CERO
# ROJO. K05 era el UNICO check que toca la palabra degraded y solo comprobaba que la CLAVE
# status EXISTIERA: nunca leia su VALOR. El colector SI lo ve -ws_collector.py:552, age >
# 90 s sobre eventos de mercado- y nadie consumia ese juicio.
#
# ==================================================================================
# 2026-09-04 · LOS CRITERIOS 2 Y 3 PASAN DE MUESTRA A SERIE. QUE CAMBIA Y QUE SE PIERDE
# ==================================================================================
# LECCION DE METODO QUE VA AQUI PORQUE AQUI SE PAGO: el 2026-09-02 alguien miro healthz a
# las 14:56Z, vio "ws-binance ok, last_event=28s" y escribio que se habia recuperado. Era
# UNA CONEXION QUE DURO 45 SEGUNDOS dentro del bucle. **Una MUESTRA no es un ESTADO.** Esa
# frase llevaba dos dias escrita en este fichero mientras los criterios 2 y 3 seguian
# juzgando una muestra. La contradiccion estaba dentro del mismo fichero.
#
# LO QUE COSTABA, medido sobre la serie ya guardada (x1-tmp/k05-rejuego.py, 3032 muestras,
# arco 2026-09-02T16:06:34Z..2026-09-04T18:37Z): la regla por muestra rojea en
# **244 de 3003 ventanas = 8.13 %, o sea 1 de cada 12.3 corridas**, sin que nadie toque
# nada. Un ROJO que sale 1 de cada 12 veces solo enseña a ignorar rojos, y el coste no cae
# sobre K05: cae sobre TODOS los rojos, porque el marcador deja de ser legible.
#
# LA REGLA NUEVA: criterios 2 y 3 son ROJO si el suceso se repite en >= N de las ultimas M
# muestras de harness/estado/healthz-serie.jsonl (la serie que ya escribia bin/capta-healthz
# para el control positivo). N=24, M=30, ambos por entorno. **Si la serie falta, no cubre M,
# esta rancia o tiene un hueco: NO MEDIDO. Nunca VERDE.** Falla cerrado.
#
# POR QUE 24 DE 30 y no otra cosa, medido sobre esas 3032 muestras:
#   scalp no-ok 231 (7.6 %) · __GLOBAL__ 248 (8.2 %) · ingest 18 · ingest:ohlcv_1m 4
#   174 episodios: 136 duran 1 muestra, el mas largo 14. **El peor recuento que el ruido de
#   fondo alcanza en una ventana de 30 es 17**, luego N=24 deja 7 de margen y scalp no puede
#   rojear por ruido. Una caida sostenida de 24 min llena la ventana y dispara.
# POR QUE LOS DOS CRITERIOS A LA VEZ: sobre las 3003 ventanas, el 2 y el 3 rojean EN LAS
#   MISMAS 244 (solo c2 = 0, solo c3 = 0). Tocar uno solo habria movido el parpadeo al gate
#   de al lado sin bajarlo ni un punto.
#
# LO QUE DEJA DE VIGILARSE, DICHO SIN ADORNO (la mitad que en K43 se cayo sin que nadie lo
# notara): **todo episodio que no llene 24 de una ventana de 30 deja de gatear.** En el arco
# medido eso son los 174 episodios enteros, el mas largo de 14 muestras, y el que mas se
# acerco al umbral nuevo llego a 17 de 24. Caso real y fechado: el reinicio del despliegue
# de hoy (parada 17:16:55Z, arranque 17:17:14Z) dejo el minuto 17:17 en 502 y los minutos
# 17:18 y 17:19 con ingest/ingest:metrics_5m no-ok. La regla vieja daba ROJO en esos dos
# minutos; la nueva no. **Quien lo caza entonces:** el minuto del 502 lo sigue cazando ESTE
# check por el criterio 1 (healthz ilegible -> NO MEDIDO, sin cambio); la parada y el arranque
# los cazan K52 (covered_seconds del minuto de borde) y K37 (huecos de datos); y el estado
# instantaneo se sigue VIENDO en la linea de VERDE -que es exactamente cuando antes habria
# rojeado-: AHORA trae el status y los no-ok del minuto, y RECUENTO trae cuantas veces cada
# servicio fallo en la ventana. Se ve y no gatea, que es lo que se pedia.
# LO QUE SI SE PIERDE, y lo digo aqui porque es lo unico: el detail LITERAL de un episodio
# que no llegue a N ya no aparece en el mensaje. Sigue guardado entero en la serie, y se
# saca con grep sobre healthz-serie.jsonl por el minuto que interese.
# LO QUE TAMBIEN SE PAGA: la latencia. Una caida sostenida tardaba 1 muestra en rojear y
# ahora tarda 24. Es el precio explicito de no rojear 1 de cada 12 corridas por ruido.
# LO QUE NO CAMBIA: el criterio 1 entero, el detail LITERAL del servicio culpable cuando SI
# gatea, el PORQUE del status global (missing_services, rancios, simbolos), y que los
# criterios se SUMAN.
# LO QUE APARECE COMO DEPENDENCIA NUEVA: el cron de bin/capta-healthz en 143. Si deja de
# escribir, los criterios 2 y 3 dan NO MEDIDO -por eso estan los guardias de frescura y de
# hueco-, nunca VERDE por silencio.
#
# K05_CAPTURA=<fichero> re-juega el criterio 1 contra un MINUTO guardado.
# K05_SERIE=<fichero>   re-juega los criterios 2 y 3 contra una VENTANA guardada. Es el
#                       equivalente de K05_CAPTURA para una regla de serie, y sin el no
#                       habria forma de inducir los dos brazos fuera de linea.
# K05_TABLA=<fichero>   inyecta la lista de servicios de pipeline_heartbeat (una por linea)
#                       en vez de preguntarsela a prodsql. SOLO para el control fuera de
#                       linea: en produccion no se pone y la tabla sale de 140.
# K05_N / K05_M / K05_HUECO  el umbral, la ventana y los segundos de tolerancia.
# K05_AHORA=<epoca>     ancla el reloj para re-jugar una ventana HISTORICA sin que el guardia
#                       de frescura la rechace por vieja. Solo para re-juego.
#
# Salida 2 = NO MEDIDO. Que FALTE el campo governed_services no es NOMED: el canal contesta
# perfectamente, lo que falta es la respuesta. Eso es ROJO.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"

N=${K05_N:-24}
M=${K05_M:-30}
HUECO=${K05_HUECO:-300}
SERIE=${K05_SERIE:-$B/estado/healthz-serie.jsonl}

# LA TABLA · criterio 1. Si no se puede leer, el criterio 1 queda SIN MEDIR, pero los 2 y 3
# se miden igual: la serie vive en 143 y no necesita el canal de 140. Antes esto era un
# exit 2 inmediato y se llevaba por delante los otros dos criterios.
if [ -n "${K05_TABLA:-}" ]; then
  tabla=$(cat "$K05_TABLA" 2>/dev/null | tr -d ' ' | grep -E '^[a-z][a-z0-9_:/.-]*$' | sort -u)
else
  tabla=$("$B/bin/prodsql" "SELECT service FROM pipeline_heartbeat ORDER BY 1" 2>/dev/null \
          | tr -d ' ' | grep -E '^[a-z][a-z0-9_:/.-]*$' | sort -u)
fi

if [ -n "${K05_CAPTURA:-}" ]; then
  [ -r "$K05_CAPTURA" ] || { echo "NO MEDIDO: no se puede leer la captura $K05_CAPTURA"; exit 2; }
  crudo=$(cat "$K05_CAPTURA")
  cuerpo=$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1]))
print(json.dumps(d.get("h", d)))' "$K05_CAPTURA" 2>/dev/null)
else
  crudo=$("$B/bin/api" /api/healthz 2>/dev/null)
  cuerpo="$crudo"
fi

# EL GUARDIA DEL CORTE, que es la trampa 1 de K86 esperando aqui: bin/api pasa por
# bin/_corta y trunca a MAX_BYTES=8000. El cuerpo de healthz mide hoy entre 4299 y 5261 B
# (medido sobre 3041 muestras de la serie, 2026-09-04), o sea que quedan 2739 B de margen
# -la mitad del propio cuerpo-. El dia que healthz crezca -mas shards, mas simbolos- el
# JSON llegara partido. Sin este guardia el check diria "no respondio", que es FALSO y manda
# a mirar a produccion cuando el problema esta en el transporte del arnes.
case "$crudo" in
  *"[CORTADO:"*)
    echo "NO MEDIDO: el transporte corto la respuesta de healthz. $(printf '%s' "$crudo" | grep -o '\[CORTADO:[^]]*\]'). Es la trampa 1 de K86: sube MAX_BYTES en harness/env, no pongas TODO=1 por inercia"
    exit 2 ;;
esac

# UN SOLO PROGRAMA para las dos cosas -el vivo y la ventana- porque los dos necesitan la
# misma tabla de umbrales y las mismas reglas de "quien esta gobernado". Duplicarlo era la
# forma segura de que uno de los dos envejeciera. Va entre comillas SIMPLES: ni una comilla
# simple dentro, o la orden se parte.
veredicto=$(printf '%s' "$cuerpo" | python3 -c '
import calendar, json, os, sys, time

SERIE, N, M, HUECO = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
MARCA = chr(123) + chr(34) + "t" + chr(34) + ":"   # el prefijo {"t": con que empieza cada muestra


def marca_t(s):
    """La hora de una muestra, leida del prefijo aunque el resto de la linea sea basura."""
    if not s.startswith(MARCA):
        return None
    a = s.find(chr(34), len(MARCA))
    b = s.find(chr(34), a + 1) if a >= 0 else -1
    return s[a + 1:b] if b > 0 else None

# DICHO EXPLICITAMENTE porque es una DUPLICACION y las duplicaciones envejecen: esta tabla
# repite api.py:2740-2752 y db.py:95. Se acepta a sabiendas y acotada: no gatea nada -el
# gate es el status, que lo calcula la app-, y el dia que la app mueva un umbral lo unico
# que puede mentir es la frase "N s > M s", nunca el veredicto.
UMBRALES = {"ingest": 420.0, "ingest:ohlcv_1m": 180.0, "ingest:metrics_5m": 420.0,
            "ws": 90.0, "scalp": 90.0, "daily": 3900.0, "api": 180.0}
POR_DEFECTO = 900.0


def umbral(nombre):
    if nombre in UMBRALES:
        return UMBRALES[nombre]
    return UMBRALES.get(nombre.split(":")[0], POR_DEFECTO)


def gobernados(d):
    g = d.get("governed_services")
    if g is None:
        return None
    try:
        return {x["service"] if isinstance(x, dict) else str(x) for x in g}
    except Exception:
        return None


def malos_de(d, nombres):
    # SOLO LOS GOBERNADOS: un latido que healthz no declara vigilar ya lo caza el criterio 1,
    # y contarlo aqui seria juzgar dos veces la misma falta.
    out = []
    for s in d.get("services") or []:
        if not isinstance(s, dict):
            continue
        nombre, estado = str(s.get("service") or ""), str(s.get("status") or "")
        if nombre in nombres and estado != "ok":
            det = str(s.get("detail") or "sin detail").replace("\n", " ")
            # EL DETAIL SE ACOTA A 110 Y LOS NOMBRES VAN PRIMERO, y no es cosmetica: el detail
            # de scalp pasa de 300 caracteres y en la primera version se comia el corte de la
            # linea dejando fuera a ws-binance, que era EL servicio que habia que ver.
            out.append((nombre, estado, det[:110]))
    return sorted(out)


def porque_de(d, nombres):
    # Los criterios 1 y 2 miran la LISTA y la FILA, y los dos se quedaron ciegos ante las tres
    # formas que el operador indujo el 2026-09-03: un scalp MUERTO 2 h con su fila diciendo ok
    # (lag 7200), un scalp AUSENTE de services (missing_services), y el snapshot de BTC a
    # 1200 s. En las tres, las filas no-ok estaban VACIAS y el status global decia degraded.
    faltan = [str(x) for x in (d.get("missing_services") or [])]
    rancios = []
    for s in d.get("services") or []:
        if not isinstance(s, dict):
            continue
        nm, lag = str(s.get("service") or ""), s.get("lag_seconds")
        if nm in nombres and isinstance(lag, (int, float)) and lag > umbral(nm):
            rancios.append(nm + "=" + str(int(lag)) + "s>" + str(int(umbral(nm))) + "s")
    simbolos = []
    for s in d.get("symbols") or []:
        if isinstance(s, dict) and isinstance(s.get("lag_seconds"), (int, float)) and s["lag_seconds"] > 180:
            simbolos.append(str(s.get("symbol")) + "=" + str(int(s["lag_seconds"])) + "s")
    return " · ".join(
        (["missing_services: " + ", ".join(faltan)] if faltan else [])
        + (["rancios: " + ", ".join(sorted(rancios))] if rancios else [])
        + (["simbolos>180s: " + ", ".join(sorted(simbolos))] if simbolos else [])
    ) or "(healthz no dice por que)"


# --- EL VIVO · CRITERIO 1 Y LA LINEA INFORMATIVA -----------------------------------
try:
    vivo = json.load(sys.stdin)
except Exception:
    vivo = None
if not isinstance(vivo, dict) or "status" not in vivo:
    print("VIVO ilegible")
else:
    nombres_vivo = gobernados(vivo)
    if nombres_vivo is None:
        print("VIVO sincampo")
    else:
        print("VIVO ok")
        print("VIGILA " + " ".join(sorted(n for n in nombres_vivo if n)))
        ahora = malos_de(vivo, nombres_vivo)
        print("AHORA status=" + str(vivo.get("status")) + "  no-ok: "
              + (", ".join(n + "=" + e for n, e, _ in ahora) if ahora else "ninguno"))

# --- LA SERIE · CRITERIOS 2 Y 3 ----------------------------------------------------
# UNA MUESTRA NO ES UNA LINEA, y esto no es teorico: capta-healthz hace
# printf ...{"t":"%s","h":%s} con el cuerpo CRUDO, y el 2026-09-04T17:17:01Z nginx devolvio
# una pagina HTML de 502 durante el despliegue. Ese minuto ocupa OCHO lineas del fichero.
# Contando por lineas, un solo minuto de 502 se come 8 de los 30 huecos de la ventana y
# empuja fuera muestras reales. Se agrupa por el prefijo {"t":", que es lo unico que
# capta-healthz garantiza al principio de cada minuto.
def lee_muestras(ruta, minimo):
    try:
        sz = os.path.getsize(ruta)
    except OSError:
        return None
    for salto in (4000000, sz + 1):
        desde = max(0, sz - salto)
        with open(ruta, "rb") as f:
            f.seek(desde)
            crudo = f.read().decode("utf-8", "replace")
        trozos = []
        for ln in crudo.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            if ln.startswith(MARCA):
                trozos.append(ln)
            elif trozos:
                trozos[-1] += ln
        # Leyendo por la cola, la PRIMERA muestra puede venir partida por la mitad: se tira.
        if desde > 0 and trozos:
            trozos = trozos[1:]
        if len(trozos) >= minimo or desde == 0:
            return trozos
    return trozos


trozos = lee_muestras(SERIE, M)
if trozos is None:
    print("SERIE ausente " + SERIE)
    raise SystemExit(0)
if len(trozos) < M:
    print("SERIE corta " + str(len(trozos)) + " muestras, hacen falta " + str(M))
    raise SystemExit(0)

ventana = []
for s in trozos[-M:]:
    t = marca_t(s)
    try:
        o = json.loads(s)
        h = o.get("h", o)
        if not isinstance(h, dict) or "status" not in h:
            h = None
    except Exception:
        h = None
    ventana.append((t, h))

# EL RELOJ · sin el, la regla es fail-open por la puerta grande: si el cron muere, la
# ventana se queda congelada en 30 minutos buenos y el check dice VERDE para siempre.
seg = []
for t, _ in ventana:
    try:
        # timegm y NO mktime: la serie va en UTC y 143 corre en America/Mexico_City. mktime
        # habria metido 6 h de sesgo, que es la trampa 2 de K86 otra vez, aqui en python.
        seg.append(calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%SZ")))
    except Exception:
        print("SERIE sinreloj una muestra sin marca de tiempo legible")
        raise SystemExit(0)
# K05_AHORA ancla el reloj para RE-JUGAR una ventana historica. Sin el, cualquier ventana
# guardada da NO MEDIDO por rancia a los cinco minutos, o sea que K05_SERIE solo serviria
# para fixtures recien fabricados y NUNCA para un trozo de la serie de verdad. Es el mismo
# recurso que la ventana en epoca de K86: el guardia sigue puesto, lo que se declara es
# desde cuando se mira. En produccion no se pone y manda el reloj.
edad = int(os.environ.get("K05_AHORA") or time.time()) - seg[-1]
if edad > HUECO:
    print("SERIE rancia la ultima muestra tiene " + str(edad) + " s (tope " + str(HUECO) + ")")
    raise SystemExit(0)
peor_hueco = max(b - a for a, b in zip(seg, seg[1:]))
if peor_hueco > HUECO:
    print("SERIE hueco de " + str(peor_hueco) + " s dentro de la ventana (tope " + str(HUECO) + ")")
    raise SystemExit(0)

cnt, ultimo = {}, {}
c3, ultimo_c3, ileg = 0, None, 0
for t, h in ventana:
    if h is None:
        ileg += 1
        continue
    nombres = gobernados(h) or set()
    for n, e, det in malos_de(h, nombres):
        cnt[n] = cnt.get(n, 0) + 1
        ultimo[n] = (t, e, det)
    if str(h.get("status") or "") != "ok":
        c3 += 1
        ultimo_c3 = (t, str(h.get("status")), porque_de(h, nombres))

print("SERIE ok")
print("ARCO " + str(ventana[0][0]) + " .. " + str(ventana[-1][0]) + "  " + str(M)
      + " muestras, " + str(ileg) + " ilegibles, hueco max " + str(peor_hueco) + " s, edad "
      + str(edad) + " s")
c2max = max(cnt.values()) if cnt else 0
print("C2MAX " + str(c2max))
print("C3 " + str(c3))
print("ILEG " + str(ileg))
# EL PEOR DE LOS DOS CRITERIOS, y no solo el del 2: el status global puede estar no-ok en 20
# de 30 sin que ninguna FILA lo publique -las tres formas del 2026-09-03-, y una cabecera que
# dijera "peor 0" con el global a 20 seria falsa en la unica linea que verify llega a enseñar.
# En empate gana el NOMBRE del servicio, no __GLOBAL__: es lo accionable. __GLOBAL__ solo
# encabeza cuando el status esta peor que cualquier fila, que es justo el caso que ninguna
# fila explica y por el que hubo que anadir el criterio 3.
print("PEOR " + str(max(c2max, c3)) + (" __GLOBAL__" if c3 > c2max or not cnt else " "
      + sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]))
print("RECUENTO " + (", ".join(k + "=" + str(v) for k, v in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:6]) or "ningun gobernado no-ok") + "  ·  __GLOBAL__=" + str(c3))
for k, v in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0])):
    if v >= N:
        t, e, det = ultimo[k]
        print("C2ROJO " + k + "=" + str(v) + "/" + str(M) + " (" + e + ") ultima " + str(t) + ": " + det)
if c3 >= N:
    t, e, p = ultimo_c3
    print("C3ROJO status no-ok en " + str(c3) + "/" + str(M) + " · ultima " + str(t) + " = " + e + " · " + p)
' "$SERIE" "$N" "$M" "$HUECO" 2>/dev/null)

lee() { printf '%s\n' "$veredicto" | sed -n "s/^$1 //p"; }
vivo=$(lee VIVO)
serie=$(lee SERIE)

# EL VEREDICTO SE COMPONE, y el orden importa: un ROJO MEDIDO manda sobre un NO MEDIDO,
# porque "hay un fallo" es un hecho y "no pude mirar" es la ausencia de uno. Lo que NO puede
# pasar nunca es que un NO MEDIDO se convierta en VERDE, que es lo que hacia el silencio.
rojo=""; nomed=""
anade() { local -n v=$1; v="${v:+$v · }$2"; }

# --- CRITERIO 1 · COBERTURA. NO SE TOCA ---
case "$vivo" in
  ok)
    if [ -z "$tabla" ]; then
      anade nomed "criterio 1: la tabla de latidos no se pudo leer (prodsql)"
    else
      vigilados=$(lee VIGILA | tr ' ' '\n' | grep -v '^$' | sort -u)
      falta=$(comm -23 <(printf '%s\n' "$tabla") <(printf '%s\n' "$vigilados") | tr '\n' ' ')
      [ -z "${falta// /}" ] || anade rojo "sin vigilar: $falta"
    fi ;;
  sincampo)
    anade rojo "healthz no declara que vigila: sin campo governed_services. $(printf '%s\n' "$tabla" | grep -c . ) latidos en la tabla, 7 con umbral en api.py:1992-2002" ;;
  *)
    anade nomed "criterio 1: /api/healthz no respondio o no es JSON" ;;
esac

# --- CRITERIOS 2 Y 3 · LA SERIE ---
case "$serie" in
  ok)
    c2rojo=$(lee C2ROJO | tr '\n' '|' | sed 's/|$//; s/|/ · /g')
    c3rojo=$(lee C3ROJO)
    c2max=$(lee C2MAX); c3=$(lee C3); ileg=$(lee ILEG)
    [ -z "$c2rojo" ] || anade rojo "criterio 2, $N de $M: $c2rojo"
    [ -z "$c3rojo" ] || anade rojo "criterio 3, $N de $M: $c3rojo"
    # LAS ILEGIBLES SON INCOGNITAS, no ceros. Si contandolas TODAS como fallo el veredicto
    # cambiaria, entonces no hay veredicto: NO MEDIDO. Y si no puede cambiar, se ignoran y no
    # introducen parpadeo. Medido sobre 3003 ventanas reales: 0 ventanas volteables.
    if [ -z "$c2rojo" ] && [ -z "$c3rojo" ] && [ "${ileg:-0}" -gt 0 ] \
       && { [ $(( ${c2max:-0} + ileg )) -ge "$N" ] || [ $(( ${c3:-0} + ileg )) -ge "$N" ]; }; then
      anade nomed "criterios 2 y 3: $ileg muestras ilegibles en la ventana y con ellas el veredicto cambiaria (peor $c2max, global $c3, umbral $N)"
    fi ;;
  ausente*|corta*|rancia*|hueco*|sinreloj*)
    anade nomed "criterios 2 y 3: serie $serie" ;;
  *)
    anade nomed "criterios 2 y 3: el evaluador de la serie no dijo nada" ;;
esac

[ -z "$rojo" ] || { printf 'ROJO: %s%s\n' "$rojo" "${nomed:+  ·  SIN MEDIR: $nomed}" | cut -c1-700; exit 1; }
[ -z "$nomed" ] || { printf 'NO MEDIDO: %s\n' "$nomed" | cut -c1-700; exit 2; }

ileg=$(lee ILEG)
printf '%s latidos vigilados · ventana %s%s: peor %s/%s (%s) · %s · %s\n' \
  "$(printf '%s\n' "$tabla" | grep -c .)" "$M" \
  "$([ "${ileg:-0}" -gt 0 ] && printf ' (ilegibles: %s)' "$ileg")" \
  "$(lee PEOR | awk '{print $1}')" "$N" "$(lee PEOR | awk '{print $2}')" \
  "$(lee RECUENTO)" "$(lee AHORA)" | cut -c1-700
