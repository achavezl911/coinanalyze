#!/bin/bash
# K71  LA SONDA JUZGA AL FEED QUE DICE JUZGAR.
#
# POR QUE EXISTE. K70 dejo 92 filas nuevas en data_gap y lo dijo al desplegarlas: NACEN SIN
# HERRAMIENTA QUE LAS CIERRE. La unica herramienta que archiva con prueba re-derivable,
# scripts/archive_beyond_horizon.py, tiene su mapa SONDA_POR_FEED indexado SOLO POR FEED, y
# eso no es una limitacion de cobertura: es una via de escribir una prueba FALSA.
#
# EL DANO, MEDIDO EN 140 Y NO RAZONADO. data_gap distingue open_interest_5min@binance de
# open_interest_5min@bybit -- 3 filas cada uno, porque exchange esta dentro de la clave del
# ON CONFLICT --, pero guarda el simbolo CANONICO en los dos: BTCUSDT_PERP.A. El proveedor
# no: pide BTCUSDT_PERP.A para binance y BTCUSDT.6 para bybit, en el MISMO endpoint
# open-interest-history. Una sonda indexada por feed le pedira al proveedor el simbolo
# canonico para los dos, recibira 200 con datos, y archivara el hueco de BYBIT con una
# prueba medida sobre BINANCE. No es un error: es una respuesta PLAUSIBLE sobre el feed
# equivocado, que es peor, porque K04 la acepta -- re-deriva lo que hay escrito en
# recovery_metadata, no por donde se midio.
#
# BRAZO 3, EL CONTROL POSITIVO, es lo que impide que este check sea teatro. Si las dos
# bolsas publicaran lo mismo, confundirlas no tendria consecuencia. Medido en 140 el
# 2026-08-30 sobre el mismo ts, oi_close de open_interest contra oi_bybit:
#     BTC 8533085932 vs 3903320941   54.3 %
#     ETH 5976896577 vs 1920516384   67.9 %
#     SOL  918345782 vs  766448213   16.5 %
# El brazo se vuelve a medir en cada pasada, no se cita de aqui: si algun dia convergieran,
# este check tiene que decirlo en vez de seguir presumiendo de un peligro que ya no existe.
#
# QUE EXIGE, y los cuatro brazos ponen ROJO por separado:
#   1 COBERTURA   cada (feed,exchange) con filas 'unresolved' en 140 tiene sonda declarada.
#                 El inventario se lee de 140, no de una lista escrita a mano aqui: una
#                 lista a mano envejece sin avisar y este check dejaria de morder el dia que
#                 aparezca un feed nuevo.
#   2 IDENTIDAD   la sonda traduce el simbolo canonico al del PROVEEDOR de ESE exchange,
#                 EJECUTANDO su funcion. Sin ejecutarla solo se comprobaria que existe un
#                 diccionario, que es justo lo que ya habia.
#   3 CONSECUENCIA  binance y bybit difieren de verdad en 140 (ver arriba).
#   4 NEGATIVA    un (feed,exchange) NO declarado se RECHAZA, no se le adivina endpoint.
#                 Adivinarlo mal da cero filas por la razon equivocada, y cero filas por la
#                 razon equivocada es exactamente una prueba falsa. Sin este brazo, la forma
#                 mas facil de poner el check en VERDE seria un fallback que acepte todo.
#
# DE QUE ARBOL: el mapa y la traduccion salen del REPO de 143; el inventario de huecos y el
# control positivo salen de 140. Produccion no se escribe.
set -uo pipefail
B=/srv/coinanalyze/harness
REPO=/srv/coinanalyze/repo
. "$B/env"

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

# --- inventario de 140: que (feed,exchange) tienen filas sin resolver -------------------
INV=$("$B/bin/prodsql" "SELECT feed||' '||exchange FROM data_gap WHERE status='unresolved'
       GROUP BY 1 ORDER BY 1" 2>/dev/null | grep -E '^[a-z0-9_]+ [a-z0-9_]+$')
[ -n "$INV" ] || { echo "NO MEDIDO: 140 no devolvio el inventario de (feed,exchange) sin resolver"; exit 2; }

# --- control positivo, medido en 140 en esta misma pasada ------------------------------
DIF=$("$B/bin/prodsql" "SELECT round(min(abs(b.oi_close-y.oi_close)
        /nullif(b.oi_close,0)*100)::numeric,1)
      FROM open_interest b JOIN oi_bybit y USING(ts,symbol,interval)
      WHERE b.interval='5min'
        AND b.ts=(SELECT max(ts) FROM oi_bybit WHERE interval='5min')" 2>/dev/null \
      | tr -d ' ' | grep -E '^[0-9]+\.?[0-9]*$' | head -1)
case "${DIF:-}" in
  ''|*[!0-9.]*) echo "NO MEDIDO: 140 no devolvio la diferencia binance/bybit de open interest"; exit 2 ;;
esac

cd "$REPO" || { echo "NO MEDIDO: no se pudo entrar en $REPO"; exit 2; }

K71_INVENTARIO="$INV" K71_DIF="$DIF" "$PY" - <<'PY'
import os
import sys

sys.path.insert(0, "/srv/coinanalyze/repo")

try:
    from scripts import archive_beyond_horizon as H
except Exception as exc:  # noqa: BLE001
    print(f"NO MEDIDO: no se pudo importar la herramienta ({type(exc).__name__}: {exc})")
    sys.exit(2)

inventario = [tuple(l.split()) for l in os.environ["K71_INVENTARIO"].splitlines() if l.strip()]
dif = float(os.environ["K71_DIF"])
fallos = []

# --- BRAZO 3 · CONSECUENCIA ------------------------------------------------------------
# Va primero a proposito: si las dos bolsas coincidieran, los brazos 1 y 2 estarian
# defendiendo algo que ya no hace dano y habria que reescribir el check, no aprobarlo.
if dif < 1.0:
    fallos.append(
        f"CONTROL POSITIVO CAIDO: binance y bybit difieren solo {dif} % en el ultimo ts "
        f"comun de open interest. Confundirlos ya casi no tiene consecuencia y este check "
        f"defiende un peligro que hay que volver a medir antes de seguir exigiendolo"
    )

# --- BRAZO 1 · COBERTURA ---------------------------------------------------------------
mapa = getattr(H, "SONDA_POR_FEED", {})
por_pareja = all(isinstance(k, tuple) and len(k) == 2 for k in mapa) if mapa else False
if not por_pareja:
    fallos.append(
        f"LA SONDA ESTA INDEXADA SOLO POR FEED: las claves de SONDA_POR_FEED son "
        f"{sorted(map(str, mapa))!r}. Un hueco de bybit y uno de binance del mismo feed "
        f"caen en la misma entrada y se sondean igual"
    )
    sin_sonda = [f"{f}@{e}" for f, e in inventario]
else:
    sin_sonda = [f"{f}@{e}" for f, e in inventario if (f, e) not in mapa]
if sin_sonda:
    fallos.append(
        f"{len(sin_sonda)} de {len(inventario)} parejas (feed,exchange) con filas sin "
        f"resolver en 140 NO tienen sonda declarada, o sea que no tienen camino a "
        f"'resuelto' ni a 'archivado con prueba': {' '.join(sorted(sin_sonda))}"
    )

# --- BRAZO 2 · IDENTIDAD DEL PROVEEDOR -------------------------------------------------
# Se EJECUTA la traduccion. Comprobar que existe un diccionario no distingue el codigo
# arreglado del que ya habia.
traduce = getattr(H, "simbolo_de_proveedor", None)
if traduce is None:
    fallos.append(
        "LA SONDA NO SABE TRADUCIR EL SIMBOLO POR EXCHANGE: no existe "
        "archive_beyond_horizon.simbolo_de_proveedor, asi que le pide al proveedor el "
        "simbolo canonico sea cual sea la bolsa"
    )
else:
    try:
        from app.config import BYBIT_SYMBOL_MAP
    except Exception as exc:  # noqa: BLE001
        print(f"NO MEDIDO: no se pudo leer el catalogo de simbolos ({exc})")
        sys.exit(2)
    canon = "BTCUSDT_PERP.A"
    esperado_bybit = BYBIT_SYMBOL_MAP.get(canon)
    if not esperado_bybit or esperado_bybit == canon:
        print(f"NO MEDIDO: el catalogo no da un simbolo de bybit distinto para {canon}")
        sys.exit(2)
    malas = []
    for feed, exchange in inventario:
        try:
            obtenido = traduce(feed, exchange, canon)
        except Exception as exc:  # noqa: BLE001
            malas.append(f"{feed}@{exchange} revienta ({type(exc).__name__})")
            continue
        quiere = esperado_bybit if exchange == "bybit" else canon
        if obtenido != quiere:
            malas.append(f"{feed}@{exchange} pide '{obtenido}' y el proveedor quiere '{quiere}'")
    if malas:
        fallos.append(
            "LA SONDA PIDE EL SIMBOLO DE OTRA BOLSA: " + "; ".join(sorted(malas))
        )

# --- BRAZO 4 · NEGATIVA ----------------------------------------------------------------
# Un feed inventado tiene que ser rechazado. Si lo aceptara, el brazo 1 se podria aprobar
# con un fallback y la cobertura seria mentira.
decidir = getattr(H, "decidir", None)
if decidir is None:
    fallos.append("no existe archive_beyond_horizon.decidir: no hay decision que auditar")
else:
    class _Falso:
        feed = "feed_que_no_existe_K71"
        exchange = "bolsa_que_no_existe_K71"
        feed_class = "cadence"
    # Se prueba el COMPORTAMIENTO, no la firma: da igual como se llamen los parametros,
    # lo que no puede pasar es que una pareja no declarada acabe en 'archivar'.
    v = None
    for intento in (
        lambda: decidir(_Falso(), sondeo=None, filas_control=999),
        lambda: decidir(_Falso(), 0, 999),
    ):
        try:
            v = intento()
            break
        except Exception:  # noqa: BLE001, S110
            continue
    if v is None or getattr(v, "accion", None) != "rechazar":
        fallos.append(
            "CONTROL NEGATIVO ROTO: un (feed,exchange) NO declarado no se rechaza. "
            "Adivinarle endpoint da cero filas por la razon equivocada, que es una "
            "prueba falsa con buena letra"
        )

if fallos:
    print(" · ".join(fallos))
    sys.exit(1)

print(
    f"las {len(inventario)} parejas (feed,exchange) con huecos sin resolver en 140 tienen "
    f"sonda declarada y la sonda pide el simbolo del proveedor que toca -- bybit traduce a "
    f"'{BYBIT_SYMBOL_MAP[canon]}' y binance se queda en '{canon}' --, un feed no declarado "
    f"se rechaza, y confundirlos importaria: binance y bybit difieren {dif} % en el ultimo "
    f"ts comun de open interest"
)
PY
exit $?
