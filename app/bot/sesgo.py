"""E1/E2 (BOT-SEGURIDAD) · el SESGO de BTC/ETH/SOL desde las velas `daily` y `4hour` de ohlcv. CONTEXTO, NO una entrada.

E1 · las velas. Las escribe app/daily_agg.py desde ohlcv-history de Coinalyze (perpetuo agregado, BTCUSDT_PERP.A...):
ts es la APERTURA de la vela y cierra en ts + 1 dia (o + 4 h). Cada pasada REESCRIBE los ultimos 3 dias (7 en 4 h), asi
que la vela en curso se guarda a medias y se corrige en la pasada siguiente: una fila con ts + duracion <= ahora puede
seguir siendo la parcial si no hubo pasada desde su cierre. Por eso una vela cuenta como CERRADA solo si ademas el
latido de la ingesta (pipeline_heartbeat 'daily', ok o degraded) es posterior a su cierre en mas de MARGEN_S.

E2 · el sesgo, por activo, sobre la ultima diaria cerrada: el cierre frente a su media de 50 dias en %, los dias seguidos
del mismo lado de la media, si el cierre rompio el maximo o el minimo de los 20 dias anteriores, y la invalidacion (un
cierre diario al otro lado de la media). Sin una diaria cerrada en FRESCA_S: «sin dato desde <cierre>».
"""

from __future__ import annotations

from datetime import UTC, datetime

DUR = {"daily": 86400, "4hour": 14400}
MEDIA, RANGO = 50, 20
MARGEN_S = 900  # el latido tiene que ser al menos 15 min posterior al cierre (una pasada empezada antes no vale)
FRESCA_S = 36 * 3600  # la ultima diaria cerrada, como mucho 36 h despues de su cierre
AVISO = ("contexto, NO es una entrada · ninguna regla medida ha confirmado ventaja (ver la entrega de"
         " claude/fable-be)")
SQL = """
SELECT split_part(symbol, '_', 1), interval, extract(epoch FROM ts)::bigint, high, low, close
  FROM ohlcv
 WHERE symbol = ANY($1::text[])
   AND ((interval = 'daily' AND ts >= to_timestamp($2::bigint))
        OR (interval = '4hour' AND ts >= to_timestamp($3::bigint)))
 ORDER BY 1, 2, 3
"""
LATIDO_SQL = ("SELECT extract(epoch FROM updated_at)::bigint FROM pipeline_heartbeat"
              " WHERE service = 'daily' AND status IN ('ok', 'degraded')")


def hm(t: int, dia: bool = False) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%m-%d" if dia else "%m-%d %H:%MZ")


def cerradas(filas: list, intervalo: str, latido: int | None, ahora: int) -> list[tuple]:
    """filas: (activo, intervalo, ts, alto, bajo, cierre) -> [(ts, alto, bajo, cierre)] de las velas CERRADAS de ese
    intervalo, en orden. Sin latido no hay ninguna (no se sabe si la ultima pasada es posterior al cierre)."""
    if latido is None:
        return []
    tope = min(ahora, latido - MARGEN_S)
    return sorted((int(t), float(h), float(lo), float(c)) for _, i, t, h, lo, c in filas
                  if i == intervalo and int(t) + DUR[intervalo] <= tope)


def sesgo(diarias: list[tuple], ahora: int) -> dict:
    """diarias: [(ts, alto, bajo, cierre)] cerradas y en orden -> el sesgo, o {"dato": False, "desde": cierre | None}."""
    if not diarias or ahora - (diarias[-1][0] + DUR["daily"]) > FRESCA_S:
        return {"dato": False, "desde": diarias[-1][0] + DUR["daily"] if diarias else None}
    # solo el tramo SEGUIDO del final: un hueco de dias corta la media y la racha
    k = len(diarias) - 1
    while k > 0 and diarias[k][0] - diarias[k - 1][0] == DUR["daily"]:
        k -= 1
    d = diarias[k:]
    if len(d) < MEDIA + 1:
        return {"dato": False, "desde": diarias[-1][0] + DUR["daily"], "motivo": f"{len(d)} diarias seguidas de {MEDIA + 1}"}
    c = [x[3] for x in d]
    medias = [sum(c[i - MEDIA + 1:i + 1]) / MEDIA for i in range(MEDIA - 1, len(c))]  # medias[j] es la del dia j+MEDIA-1
    media = medias[-1]
    lado = (c[-1] > media) - (c[-1] < media)
    dias = 0
    for j in range(len(medias) - 1, -1, -1):
        if lado == 0 or ((c[j + MEDIA - 1] > medias[j]) - (c[j + MEDIA - 1] < medias[j])) != lado:
            break
        dias += 1
    previos = d[-RANGO - 1:-1]
    maximo, minimo = max(x[1] for x in previos), min(x[2] for x in previos)
    return {"dato": True, "ts": d[-1][0], "cierre_t": d[-1][0] + DUR["daily"], "cierre": c[-1], "media": media,
            "pct": (c[-1] / media - 1) * 100, "lado": lado, "dias": dias, "max20": maximo, "min20": minimo,
            "rompe": "maximo" if c[-1] > maximo else "minimo" if c[-1] < minimo else None}


def linea(activo: str, s: dict, h4: list[tuple]) -> str:
    nombre = activo.replace("USDT", "")
    if not s["dato"]:
        return f"{nombre}: sin dato desde {hm(s['desde']) if s['desde'] else 'nunca'}" + (
            f" ({s['motivo']})" if s.get("motivo") else "")
    pos = {1: "por encima", -1: "por debajo", 0: "justo en"}[s["lado"]]
    rompe = (f"rompio el {s['rompe']} de {RANGO} d ({s['max20' if s['rompe'] == 'maximo' else 'min20']:.6g})" if s["rompe"]
             else f"dentro de su rango de {RANGO} d ({s['min20']:.6g}-{s['max20']:.6g})")
    otro = "por debajo" if s["lado"] > 0 else "por encima"
    inval = f"invalidacion: un cierre diario {otro} de la media" if s["lado"] else "sin lado: en la media"
    cuatro = f" · 4 h: ultima cerrada {hm(h4[-1][0] + DUR['4hour'])}, {h4[-1][3]:.6g}" if h4 else " · 4 h: sin vela cerrada"
    return (f"{nombre}: diario del {hm(s['ts'], True)} (cerro {hm(s['cierre_t'])}) {s['cierre']:.6g} · {s['pct']:+.2f} % {pos}"
            f" de su media de {MEDIA} d ({s['media']:.6g}) · {s['dias']} d seguidos {pos} · {rompe} · {inval}{cuatro}")


def texto(filas: list, latido: int | None, ahora: int, activos=("BTCUSDT", "ETHUSDT", "SOLUSDT"), corto: bool = False) -> str:
    out = [f"SESGO ({AVISO})"]
    for a in activos:
        mias = [f for f in filas if f[0] == a]
        ln = linea(a, sesgo(cerradas(mias, "daily", latido, ahora), ahora), cerradas(mias, "4hour", latido, ahora))
        out.append(ln.split(" · rompio")[0].split(" · dentro")[0] if corto else ln)
    return "\n".join(out)
