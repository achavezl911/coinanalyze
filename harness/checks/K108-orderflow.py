"""K108 · ayudante: junta, recalcula por su cuenta y juzga el dato del order-flow (OF-1, campana 140).

No importa NADA de app/orderflow_lectura.py: el footprint y el perfil se recalculan aqui desde las celdas con su
propia aritmetica, y el algoritmo de la value area se reescribe desde su declaracion. Si se reusara el codigo que se
audita, (d) compararia el codigo consigo mismo.

Uso: K108-orderflow.py juzga   (el entorno lo pone K108-el-dato-del-order-flow.sh)
     K108-orderflow.py sirve <dir> [--planta X]   (escribe lo que serviria el arbol, para los controles)
Desde OF-3 (campana 143), (d) juzga tambien lo que sirven /sesiones (con su compuesto), /vwap y /tpo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

H = os.environ.get("K108_HARNESS", "/srv/coinanalyze/harness")
REPO = os.environ.get("K108_REPO", "/srv/coinanalyze/repo")
SUJETO = os.environ.get("K108_SUJETO", "produccion")
BASE = os.environ.get("K108_BASE", "")
AGREGADOS = os.environ.get("K108_AGREGADOS", "")
SERVIDO = os.environ.get("K108_SERVIDO", "")
RELOJ = os.environ.get("K108_RELOJ", "")

VENUES = ("binance_spot", "binance_usdm", "bybit_spot", "bybit_linear", "okx_spot", "okx_swap", "coinbase_spot",
          "bitget_usdt", "deribit_perp")
ACTIVOS = ("BTC", "ETH", "SOL")
# (a) los cuatro mercados que tienen un colector INDEPENDIENTE del mismo flujo en 140.
TRIANGULO = {"binance_spot": ("spot", "binance"), "bybit_spot": ("spot", "bybit"),
             "binance_usdm": ("fut", "binance"), "bybit_linear": ("fut", "bybit")}
# Umbrales DECLARADOS en la prediccion ante-hoc (entregas/20261017-0358-...-prediccion.md, apuesta 5) y no movidos.
TRI_MEDIANA = Decimal("0.005")
TRI_COLA, TRI_COLA_MAX = Decimal("0.02"), Decimal("0.05")
TRI_MINUTOS = 30
VENTANA = timedelta(hours=int(os.environ.get("K108_HORAS", "6")))
VENTANA_CINTA = timedelta(hours=1)
COBERTURA_MIN = Decimal("0.90")
TICK_MIN, TICK_MUESTRA = Decimal("0.5"), 50
SIN_ESCRIBIR = timedelta(minutes=10)
GRACIA = timedelta(hours=2)
PASO_D = Decimal(10)  # (d) se pide a 10 veces el paso base: ejercita la agregacion de niveles
MARCO_D, VENTANA_D = 5, timedelta(minutes=30)  # (d) velas de 5 min de la ultima media hora
MINIMO = timedelta(minutes=int(os.environ.get("K108_MINIMO", "30")))  # vida minima del servicio para juzgar


class Canal(Exception):
    pass


class NoLaSirve(Canal):
    """La ruta no existe en el sujeto (404): un sujeto anterior a la campana que la anadio. No es el canal caido."""


def _ts(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00")


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sql(destino: str, q: str) -> list[list[str]]:
    """Filas de texto. `produccion` va por bin/prodsql (solo lectura, UTC); otra cosa es un DSN de 143."""
    if destino == "produccion":
        cmd = ["sh", f"{H}/bin/prodsql", q]
        env = {**os.environ, "TODO": "1"}
    else:
        cmd = ["psql", destino, "-X", "-A", "-F|", "-t", "-q", "-v", "ON_ERROR_STOP=1",
               "-c", "SET TIME ZONE 'UTC'", "-c", q]
        env = dict(os.environ)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
    if r.returncode != 0:
        raise Canal(f"{'prodsql' if destino == 'produccion' else 'psql'} rc={r.returncode}: "
                    f"{(r.stderr or r.stdout).strip()[:160]}")
    return [linea.split("|") for linea in r.stdout.splitlines() if linea.strip()]


def una(destino: str, q: str) -> list[str]:
    filas = sql(destino, q)
    if not filas:
        raise Canal(f"la consulta no devolvio ninguna fila: {q[:80]}")
    return filas[0]


def api(ruta: str) -> dict:
    if SUJETO == "produccion":
        r = subprocess.run(["sh", f"{H}/bin/api", ruta], capture_output=True, text=True, timeout=120,
                           env={**os.environ, "TODO": "1"})
        if r.returncode != 0 and "HTTP 404" in r.stderr:
            raise NoLaSirve(ruta.split("?")[0])
        if r.returncode != 0:
            raise Canal(f"api {ruta.split('?')[0]} rc={r.returncode}")
        try:
            return json.loads(r.stdout)
        except ValueError as exc:
            raise Canal(f"api {ruta.split('?')[0]} no devolvio JSON") from exc
    nombre = Path(SERVIDO) / (urllib.parse.quote(ruta, safe="") + ".json")
    if not nombre.is_file() and (Path(SERVIDO) / "sin-of3").is_file():  # el control: un sujeto anterior a OF-3
        raise NoLaSirve(ruta.split("?")[0])
    if not nombre.is_file():
        raise Canal(f"no hay respuesta servida para {ruta} en {SERVIDO}")
    return json.loads(nombre.read_text())


def texto(d: Decimal) -> str:
    return "0" if d == 0 else format(d.normalize(), "f")


def ventana_d(fin: datetime, primero: datetime) -> tuple[datetime, datetime]:
    """(d): las velas de MARCO_D min enteras de la ultima VENTANA_D, sin salirse de la vida del servicio."""
    hasta = fin.replace(minute=fin.minute - fin.minute % MARCO_D)
    desde = max(hasta - VENTANA_D, primero)
    desde = desde.replace(second=0, microsecond=0) + timedelta(minutes=(-desde.minute) % MARCO_D)
    return hasta, desde


# --------------------------------------------------------------------------------------------- recalculo propio
def poc_de(totales: dict[Decimal, Decimal]) -> Decimal | None:
    if not totales:
        return None
    mayor = max(totales.values())
    return min(n for n, t in totales.items() if t == mayor)


def value_area(totales: dict[Decimal, Decimal]) -> tuple[Decimal, Decimal, Decimal] | None:
    """Reescrita desde la declaracion: desde el POC, se anade el nivel con volumen inmediatamente encima o debajo
    del area que tenga mas volumen (empate: el de arriba; un lado agotado: el otro) hasta el 70 % del total."""
    poc = poc_de(totales)
    if poc is None:
        return None
    orden = sorted(totales)
    meta = sum(totales.values()) * Decimal("0.70")
    lo = hi = orden.index(poc)
    vol = totales[poc]
    while vol < meta and (lo > 0 or hi < len(orden) - 1):
        sube = totales[orden[hi + 1]] if hi < len(orden) - 1 else None
        baja = totales[orden[lo - 1]] if lo > 0 else None
        if baja is None or (sube is not None and sube >= baja):
            hi += 1
            vol += totales[orden[hi]]
        else:
            lo -= 1
            vol += totales[orden[lo]]
    return orden[lo], orden[hi], vol


def recalcula(destino: str, activo: str, desde: datetime, hasta: datetime, paso: Decimal, marco_min: int,
              unidad: str) -> dict:
    filas = sql(destino, f"""SELECT extract(epoch FROM ts)::bigint, nivel, compra_base, venta_base, compra_usd,
                                    venta_usd, compras, ventas
                               FROM orderflow_celda WHERE symbol='{activo}' AND ts >= '{_ts(desde)}'
                                AND ts < '{_ts(hasta)}'""")
    cob = sql(destino, f"""SELECT extract(epoch FROM ts)::bigint, segundos, definitivo FROM orderflow_cobertura
                            WHERE symbol='{activo}' AND ts >= '{_ts(desde)}' AND ts < '{_ts(hasta)}'""")
    velas: dict[int, dict[Decimal, list]] = {}
    for ts, nivel, cb, vb, cu, vu, nc, nv in filas:
        vela = int(ts) - (int(ts) - int(desde.timestamp())) % (marco_min * 60)
        n = (Decimal(nivel) / paso).to_integral_value(rounding="ROUND_FLOOR") * paso
        c, v = (Decimal(cb), Decimal(vb)) if unidad == "base" else (Decimal(cu), Decimal(vu))
        x = velas.setdefault(vela, {}).setdefault(n, [Decimal(0), Decimal(0), 0])
        x[0] += c
        x[1] += v
        x[2] += int(nc) + int(nv)
    por_vela_cob: dict[int, list] = {}
    for ts, seg, defin in cob:
        vela = int(ts) - (int(ts) - int(desde.timestamp())) % (marco_min * 60)
        por_vela_cob.setdefault(vela, []).append((int(seg), defin == "t"))
    return {"velas": velas, "cobertura": por_vela_cob}


def compara_footprint(servido: dict, rec: dict, desde: datetime, marco_min: int) -> list[str]:
    malos = []
    n_ven = len(VENUES)
    for k, vela in enumerate(servido.get("velas") or []):
        inicio = int(desde.timestamp()) + k * marco_min * 60
        try:
            ts_ok = datetime.fromisoformat(str(vela.get("ts")).replace("Z", "+00:00")).timestamp() == inicio
        except ValueError:
            ts_ok = False
        if not ts_ok:
            malos.append(f"vela {k}: ts servido {vela.get('ts')} no es el inicio {_iso(datetime.fromtimestamp(inicio, UTC))}")
            continue
        niveles = rec["velas"].get(inicio, {})
        serv = {Decimal(n["nivel"]): (Decimal(n["compra"]), Decimal(n["venta"]), int(n["operaciones"]),
                                      Decimal(n["delta"]), Decimal(n["total"])) for n in vela.get("niveles", [])}
        mio = {n: (c, v, o, c - v, c + v) for n, (c, v, o) in niveles.items()}
        if serv != mio:
            dif = sorted(set(serv.items()) ^ set(mio.items()))[:1]
            malos.append(f"vela {vela['ts']}: niveles servidos != recalculados ({len(serv)} vs {len(mio)}; "
                         f"primero distinto {dif})")
            continue
        compra = sum((c for c, _, _ in niveles.values()), Decimal(0))
        venta = sum((v for _, v, _ in niveles.values()), Decimal(0))
        poc = poc_de({n: c + v for n, (c, v, _) in niveles.items()})
        totales_ok = (Decimal(vela["compra"]), Decimal(vela["venta"]), Decimal(vela["delta"]),
                      Decimal(vela["total"])) == (compra, venta, compra - venta, compra + venta)
        if not totales_ok or (Decimal(vela["poc"]) if vela.get("poc") else None) != poc:
            malos.append(f"vela {vela['ts']}: totales o POC servidos != recalculados (poc {vela.get('poc')} vs "
                         f"{texto(poc) if poc is not None else None})")
            continue
        # OF-2 (campana 142): la value area de CADA vela, con la misma regla que el perfil, reescrita aqui. Un sujeto
        # anterior a OF-2 no la sirve: entonces no se juzga (lo dice la linea de (d)).
        if "value_area" in vela:
            va = value_area({n: c + v for n, (c, v, _) in niveles.items()})
            sva = vela["value_area"]
            mia_va = {"val": texto(va[0]), "vah": texto(va[1]), "volumen": texto(va[2])} if va else None
            if (sva and {k: texto(Decimal(sva[k])) for k in ("val", "vah", "volumen")}) != mia_va:
                malos.append(f"vela {vela['ts']}: value area servida {sva} != recalculada {mia_va}")
                continue
        cob = rec["cobertura"].get(inicio, [])
        esperados = marco_min * n_ven
        mia = {"minutos_esperados": esperados, "minutos_con_fila": len(cob),
               "minutos_completos": sum(1 for s, _ in cob if s == 60), "segundos": sum(s for s, _ in cob)}
        if any(vela.get("cobertura", {}).get(k2) != v2 for k2, v2 in mia.items()):
            malos.append(f"vela {vela['ts']}: cobertura servida {vela.get('cobertura')} != recalculada {mia}")
    return malos


def compara_perfil(servido: dict, rec: dict) -> list[str]:
    total: dict[Decimal, list] = {}
    for niveles in rec["velas"].values():
        for n, (c, v, o) in niveles.items():
            x = total.setdefault(n, [Decimal(0), Decimal(0), 0])
            x[0] += c
            x[1] += v
            x[2] += o
    serv = {Decimal(n["nivel"]): (Decimal(n["compra"]), Decimal(n["venta"]), int(n["operaciones"]))
            for n in servido.get("niveles", [])}
    mio = {n: tuple(x) for n, x in total.items()}
    malos = []
    if serv != mio:
        malos.append(f"perfil: {len(serv)} niveles servidos != {len(mio)} recalculados")
        return malos
    totales = {n: c + v for n, (c, v, _) in mio.items()}
    va = value_area(totales)
    sva = servido.get("value_area") or {}
    poc = poc_de(totales)
    if (Decimal(servido["poc"]) if servido.get("poc") else None) != poc:
        malos.append(f"perfil: POC servido {servido.get('poc')} != recalculado {texto(poc) if poc else None}")
    if va and (Decimal(sva.get("val") or -1), Decimal(sva.get("vah") or -1), Decimal(sva.get("volumen") or -1)) != va:
        malos.append(f"perfil: value area servida {sva.get('val')}-{sva.get('vah')} != recalculada "
                     f"{texto(va[0])}-{texto(va[1])}")
    return malos


# --------------------------------------------------------------------------------------------- OF-3 (campana 143)
# LOS PERFILES servidos -sesiones con su compuesto, VWAP con bandas y TPO- == recalculados aqui con su propia
# aritmetica: las sesiones se cuentan aqui, los niveles se suman aqui al paso, el VWAP sale EXACTO con Fraction y la
# sigma con Decimal a 60 cifras por OTRA formula (dos pasadas: sum q_n (p_n - vwap)^2 / Q, con p_n = u_n / q_n), y el
# TPO con su propio «toca», su propio paso y sus propias letras.
LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuv"
PLANTILLAS = {"dia": ("00:00", "24:00"), "asia": ("00:00", "08:00"), "europa": ("07:00", "16:00"),
              "eeuu": ("13:30", "20:00")}


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))


def plantilla_cruzada(fin: datetime) -> str:
    """Una sesion propia de 24 h que empieza 12 h antes de `fin`: contiene la ventana de (d) y CRUZA siempre una
    medianoche. Si el sujeto la partiera en dos, sus sesiones no serian las de aqui."""
    s = fin - timedelta(hours=12)
    if (s.hour, s.minute) == (0, 0):
        s += timedelta(minutes=1)  # a las 00:00 seria el dia, que no cruza
    return f"{s:%H:%M}-{s:%H:%M}"


def sesiones_aqui(plantilla: str, a: datetime, b: datetime) -> list[tuple[datetime, datetime]]:
    i, f = PLANTILLAS.get(plantilla, tuple(plantilla.split("-")))
    ini = int(i[:2]) * 60 + int(i[3:])
    largo = (int(f[:2]) * 60 + int(f[3:]) - ini) % 1440 or 1440
    out, dia = [], datetime(a.year, a.month, a.day, tzinfo=UTC) - timedelta(days=2)
    while dia <= b:
        s = dia + timedelta(minutes=ini)
        if s < b and s + timedelta(minutes=largo) > a:
            out.append((s, s + timedelta(minutes=largo)))
        dia += timedelta(days=1)
    return out


def peticiones_of3(desde: datetime, hasta: datetime, pasos: dict, fin: datetime) -> list[tuple[str, str, dict]]:
    """Lo que (d) pide de OF-3 por activo, sobre su ventana: las sesiones del dia y las de la plantilla que cruza la
    medianoche (con su compuesto), el VWAP de 5 min de la que cruza y el TPO del dia (paso automatico)."""
    cruzada = plantilla_cruzada(fin)
    out = []
    for activo in ACTIVOS:
        w = {"symbol": activo, "desde": _iso(desde), "hasta": _iso(hasta)}
        paso = texto(pasos[activo] * PASO_D)
        out += [(activo, "sesiones", {**w, "sesion": "dia", "paso": paso, "unidad": "base"}),
                (activo, "sesiones", {**w, "sesion": cruzada, "paso": paso, "unidad": "base"}),
                (activo, "vwap", {**w, "marco": f"{MARCO_D}m", "sesion": cruzada}),
                (activo, "tpo", {**w, "sesion": "dia", "paso": "auto"})]
    return out


def _cobertura(db: str, activo: str, s: datetime, corte: datetime) -> tuple[int, int, int]:
    if corte <= s:
        return 0, 0, 0
    f, c, g = una(db, f"""SELECT count(*), count(*) FILTER (WHERE segundos = 60), coalesce(sum(segundos), 0)
                            FROM orderflow_cobertura WHERE symbol='{activo}' AND ts >= '{_ts(s)}' AND ts < '{_ts(corte)}'""")
    return int(f), int(c), int(g)


def _cuadra_cobertura(quien: str, c: dict, cob: tuple, esperados: int) -> list[str]:
    mia = {"minutos_esperados": esperados, "minutos_con_fila": cob[0], "minutos_completos": cob[1], "segundos": cob[2]}
    return [f"{quien}: cobertura servida {c} != recalculada {mia}"] if any((c or {}).get(k) != v
                                                                           for k, v in mia.items()) else []


def _cuadra_perfil(quien: str, sv: dict, mio: dict[Decimal, list]) -> list[str]:
    serv = {Decimal(n["nivel"]): [Decimal(n["compra"]), Decimal(n["venta"]), int(n["operaciones"])]
            for n in sv.get("niveles") or []}
    if serv != mio:
        return [f"{quien}: {len(serv)} niveles servidos != {len(mio)} recalculados"]
    tot = {n: c + v for n, (c, v, _) in mio.items()}
    poc, va = poc_de(tot), value_area(tot)
    sva = sv.get("value_area")
    malos = []
    if (Decimal(sv["poc"]) if sv.get("poc") is not None else None) != poc:
        malos.append(f"{quien}: POC servido {sv.get('poc')} != recalculado {poc}")
    if (sva and (Decimal(sva["val"]), Decimal(sva["vah"]), Decimal(sva["volumen"]))) != va:
        malos.append(f"{quien}: value area servida {sva and (sva['val'], sva['vah'])} != recalculada "
                     f"{va and (texto(va[0]), texto(va[1]))}")
    return malos


def juzga_sesiones(db: str, activo: str, q: dict, sv: dict, hasta: datetime) -> list[str]:
    mias = sesiones_aqui(q["sesion"], _dt(q["desde"]), hasta)
    quien = f"sesiones {q['sesion']}"
    servidas = [(_dt(s["inicio"]), _dt(s["fin"])) for s in sv.get("sesiones") or []]
    if servidas != mias:
        return [f"{quien}: sesiones servidas {[(_iso(a), _iso(b)) for a, b in servidas]} != recalculadas "
                f"{[(_iso(a), _iso(b)) for a, b in mias]}"]
    paso, n_ven = Decimal(q["paso"]), len(sv.get("venues") or VENUES)
    malos, todos, cob_total, esperados = [], {}, [0, 0, 0], 0
    for (s, e), x in zip(mias, sv["sesiones"], strict=True):
        corte = min(e, hasta)
        if _dt(x["corte"]) != corte or bool(x.get("en_curso")) != (corte < e):
            malos.append(f"{quien} {_iso(s)}: corte {x.get('corte')} en curso {x.get('en_curso')}; aqui {_iso(corte)} "
                         f"{corte < e}")
        mio: dict[Decimal, list] = {}
        for n, c, v, o in sql(db, f"""SELECT nivel, sum(compra_base), sum(venta_base), sum(compras + ventas)
                                        FROM orderflow_celda WHERE symbol='{activo}' AND ts >= '{_ts(s)}'
                                         AND ts < '{_ts(corte)}' GROUP BY nivel"""):
            z = mio.setdefault((Decimal(n) / paso).to_integral_value(rounding="ROUND_FLOOR") * paso,
                               [Decimal(0), Decimal(0), 0])
            z[0], z[1], z[2] = z[0] + Decimal(c), z[1] + Decimal(v), z[2] + int(o)
            t = todos.setdefault((Decimal(n) / paso).to_integral_value(rounding="ROUND_FLOOR") * paso,
                                 [Decimal(0), Decimal(0), 0])
            t[0], t[1], t[2] = t[0] + Decimal(c), t[1] + Decimal(v), t[2] + int(o)
        malos += _cuadra_perfil(f"{quien} {_iso(s)}", x, mio)
        cob = _cobertura(db, activo, s, corte)
        n_esp = int((corte - s) // timedelta(minutes=1)) * n_ven
        malos += _cuadra_cobertura(f"{quien} {_iso(s)}", x.get("cobertura"), cob, n_esp)
        cob_total, esperados = [cob_total[i] + cob[i] for i in range(3)], esperados + n_esp
    if mias:
        comp = sv.get("compuesto") or {}
        malos += _cuadra_perfil(f"{quien} compuesto", comp, todos)
        malos += _cuadra_cobertura(f"{quien} compuesto", comp.get("cobertura"), tuple(cob_total), esperados)
    return malos


def _dec(f: Fraction) -> Decimal:
    return Decimal(f.numerator) / Decimal(f.denominator)


def juzga_vwap(db: str, activo: str, q: dict, sv: dict, hasta: datetime, base: Decimal) -> list[str]:
    a, m = _dt(q["desde"]), int(q["marco"].rstrip("m")) * 60
    mias = sesiones_aqui(q["sesion"], a, hasta)
    quien = f"vwap {q['sesion']}"
    if [_dt(s["inicio"]) for s in sv.get("sesiones") or []] != [s for s, _ in mias]:
        return [f"{quien}: sesiones servidas {[s['inicio'] for s in sv.get('sesiones') or []]} != recalculadas "
                f"{[_iso(s) for s, _ in mias]}"]
    tol = base / 100 / 2  # el servidor redondea a paso_base / 100: medio quantum, y nada mas
    malos = []
    for (s, e), x in zip(mias, sv["sesiones"], strict=True):
        por_vela: dict[int, list] = {}
        for v, n, u, qq in sql(db, f"""SELECT floor(extract(epoch FROM ts) / {m})::bigint * {m}, nivel,
                                               sum(compra_usd + venta_usd), sum(compra_base + venta_base)
                                          FROM orderflow_celda WHERE symbol='{activo}' AND ts >= '{_ts(s)}'
                                           AND ts < '{_ts(min(e, hasta))}' GROUP BY 1, 2"""):
            por_vela.setdefault(int(v), []).append((Decimal(n), Fraction(u), Fraction(qq)))
        u_n: dict[Decimal, Fraction] = {}
        q_n: dict[Decimal, Fraction] = {}
        esperados = []
        for v in sorted(set(por_vela) | set(range(int(a.timestamp()), int(hasta.timestamp()), m))):
            for n, u, qq in por_vela.get(v, []):
                u_n[n], q_n[n] = u_n.get(n, Fraction(0)) + u, q_n.get(n, Fraction(0)) + qq
            if v < a.timestamp() or v + m <= s.timestamp() or v >= min(e, hasta).timestamp() or not sum(q_n.values()):
                continue
            vw = sum(u_n.values()) / sum(q_n.values())
            with localcontext() as ctx:
                ctx.prec = 60
                vwd = _dec(vw)
                sig = abs(sum(_dec(q_n[n]) * (_dec(u_n[n]) / _dec(q_n[n]) - vwd) ** 2 for n in u_n if q_n[n])
                          / _dec(sum(q_n.values()))).sqrt()
            esperados.append((v, vw, vwd, sig))
        puntos = x.get("puntos") or []
        if [int(_dt(p["ts"]).timestamp()) for p in puntos] != [v for v, *_ in esperados]:
            malos.append(f"{quien} {_iso(s)}: {len(puntos)} puntos servidos != {len(esperados)} velas con operaciones")
            continue
        for p, (_, vw, vwd, sig) in zip(puntos, esperados, strict=True):
            if abs(Fraction(p["vwap"]) - vw) > Fraction(tol):  # el VWAP, exacto contra exacto
                malos.append(f"{quien} vela {p['ts']}: vwap servido {p['vwap']} != recalculado {vwd:.6f}")
                break
            pares = [("sigma", p["sigma"], sig)] + [
                (f"banda {s_}{k}", p["bandas"][k][i], vwd + int(s_ + "1") * int(k) * sig)
                for k in ("1", "2", "3") for i, s_ in enumerate(("-", "+"))]
            fuera = [f"{nombre} servido {servido} != recalculado {mio:.6f}" for nombre, servido, mio in pares
                     if abs(Decimal(servido) - mio) > tol * Decimal("1.000001")]
            if fuera:
                malos.append(f"{quien} vela {p['ts']}: {fuera[0]}")
                break
        cob = _cobertura(db, activo, s, min(e, hasta))
        malos += _cuadra_cobertura(f"{quien} {_iso(s)}", x.get("cobertura"), cob,
                                   int((min(e, hasta) - s) // timedelta(minutes=1)) * len(sv.get("venues") or VENUES))
    return malos


def paso_tpo(rangos: list, base: Decimal) -> Decimal:
    """La regla de paso=auto de OF-2 sobre periodos de 30 min, reescrita: el menor 1-2-5 x base con el que el periodo
    mediano toca <= 20 niveles."""
    if not rangos:
        return base
    for e in range(12):
        for mult in (1, 2, 5):
            p = base * mult * 10**e
            toques = sorted(int((hi / p).to_integral_value(rounding="ROUND_FLOOR")
                                - (lo / p).to_integral_value(rounding="ROUND_FLOOR")) + 1 for lo, hi in rangos)
            if toques[len(toques) // 2] <= 20:
                return p
    return p


def juzga_tpo(db: str, activo: str, q: dict, sv: dict, hasta: datetime, base: Decimal) -> list[str]:
    mias = sesiones_aqui(q["sesion"], _dt(q["desde"]), hasta)
    quien = f"tpo {q['sesion']}"
    if [_dt(s["inicio"]) for s in sv.get("sesiones") or []] != [s for s, _ in mias]:
        return [f"{quien}: sesiones servidas {[s['inicio'] for s in sv.get('sesiones') or []]} != recalculadas "
                f"{[_iso(s) for s, _ in mias]}"]
    periodos = {}
    for s, e in mias:
        for k, lo, hi in sql(db, f"""SELECT floor(extract(epoch FROM ts - '{_ts(s)}'::timestamptz) / 1800)::int,
                                            min(nivel), max(nivel) FROM orderflow_celda WHERE symbol='{activo}'
                                       AND ts >= '{_ts(s)}' AND ts < '{_ts(min(e, hasta))}' GROUP BY 1"""):
            periodos[(s, int(k))] = (Decimal(lo), Decimal(hi))
    paso = paso_tpo(list(periodos.values()), base) if q.get("paso") == "auto" else Decimal(q["paso"])
    if Decimal(sv["paso"]) != paso:
        return [f"{quien}: paso servido {sv['paso']} != el de la regla {texto(paso)}"]
    malos, n_ven = [], len(sv.get("venues") or VENUES)
    for (s, e), x in zip(mias, sv["sesiones"], strict=True):
        letras: dict[Decimal, str] = {}
        ib = []
        for k in range(48):
            if (s, k) not in periodos:
                continue
            lo, hi = ((y / paso).to_integral_value(rounding="ROUND_FLOOR") * paso for y in periodos[(s, k)])
            n = lo
            while n <= hi:
                letras[n] = letras.get(n, "") + LETRAS[k]
                n += paso
            if k < 2:
                ib.append((lo, hi))
        serv = {Decimal(n["nivel"]): n["letras"] for n in x.get("niveles") or []}
        if serv != letras:
            malos.append(f"{quien} {_iso(s)}: letras servidas != recalculadas (primera distinta "
                         f"{sorted(set(serv.items()) ^ set(letras.items()))[:1]})")
            continue
        tot = {n: len(t) for n, t in letras.items()}
        poc, va = poc_de(tot), value_area(tot)
        if (Decimal(x["poc"]) if x.get("poc") is not None else None) != poc or \
                (x.get("value_area") and (Decimal(x["value_area"]["val"]), Decimal(x["value_area"]["vah"]))) != \
                (va and (va[0], va[1])):
            malos.append(f"{quien} {_iso(s)}: POC/value area de los TPO servidos {x.get('poc')} {x.get('value_area')} "
                         f"!= recalculados {poc} {va and (texto(va[0]), texto(va[1]))}")
        mib = {"lo": texto(min(i for i, _ in ib)), "hi": texto(max(j for _, j in ib))} if ib else None
        if x.get("balance_inicial") != mib:
            malos.append(f"{quien} {_iso(s)}: balance inicial servido {x.get('balance_inicial')} != recalculado {mib}")
        orden, tramos = sorted(tot), []
        for n in orden:
            if tot[n] == 1:
                if tramos and n - tramos[-1][-1] == paso:
                    tramos[-1].append(n)
                else:
                    tramos.append([n])
        if [(t["desde"], t["hasta"]) for t in x.get("single_prints") or []] != [(texto(t[0]), texto(t[-1]))
                                                                                for t in tramos]:
            malos.append(f"{quien} {_iso(s)}: single prints servidos != recalculados")
        corte = min(e, hasta)
        malos += _cuadra_cobertura(f"{quien} {_iso(s)}", x.get("cobertura"), _cobertura(db, activo, s, corte),
                                   int((corte - s) // timedelta(minutes=1)) * n_ven)
    return malos


# --------------------------------------------------------------------------------------------- juicio
def juzga() -> int:
    """Seis brazos. Cada uno captura SU canal: un brazo que no se pudo medir es NO MEDIDO, y un ROJO medido en otro
    brazo manda sobre el. Solo el preludio (las tablas, el reloj, la vida del servicio) decide por todos."""
    if SUJETO == "local" and not BASE:
        print("NO MEDIDO: K108_SUJETO=local pide K108_BASE")
        return 2
    db = "produccion" if SUJETO == "produccion" else BASE
    agg = AGREGADOS or db
    rojos: list[str] = []
    nomed: list[str] = []
    info: list[str] = []
    try:
        hay = una(db, "SELECT (to_regclass('orderflow_celda') IS NOT NULL AND to_regclass('orderflow_cinta') IS "
                      "NOT NULL AND to_regclass('orderflow_cobertura') IS NOT NULL AND to_regclass('orderflow_grande') "
                      "IS NOT NULL AND to_regclass('orderflow_paso') IS NOT NULL)::int")
        if hay != ["1"]:
            print("NO MEDIDO: FALTA DESPLEGAR · el sujeto no tiene las tablas orderflow_* (OF-1); sin ellas no hay "
                  "dato que juzgar")
            return 2
        ahora = datetime.fromisoformat(RELOJ) if RELOJ else datetime.fromisoformat(
            una(db, "SELECT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS+00:00')")[0])
        primero_txt, ultimo_txt, n_cob = una(db, "SELECT min(ts), max(ts), count(*) FROM orderflow_cobertura")
        if int(n_cob) == 0:
            print("NO MEDIDO: las tablas orderflow_* estan pero orderflow_cobertura no tiene ni una fila: el servicio "
                  "no ha escrito nunca. Cero defectos sobre cero filas no es cero defectos")
            return 2
    except Canal as exc:
        print(f"NO MEDIDO (CANAL): {exc}")
        return 2
    primero = datetime.fromisoformat(primero_txt.replace(" ", "T").replace("+00", "+00:00"))
    ultimo = datetime.fromisoformat(ultimo_txt.replace(" ", "T").replace("+00", "+00:00"))
    fin = ahora.replace(second=0, microsecond=0) - timedelta(minutes=3)
    ini = max(fin - VENTANA, primero)
    ini_c = max(fin - VENTANA_CINTA, primero)
    if ahora - ultimo > SIN_ESCRIBIR:
        rojos.append(f"(c) el servicio no escribe: el ultimo minuto con cobertura es {_iso(ultimo)}, "
                     f"{int((ahora - ultimo).total_seconds() // 60)} min antes de {_iso(ahora)}")
    if fin - ini < MINIMO:
        print(f"NO MEDIDO: el servicio lleva menos de {MINIMO} de minutos definitivos ({_iso(ini)}-{_iso(fin)}); "
              "no hay ventana que juzgar todavia")
        for r in rojos:
            print(f"   - {r}")
        return 1 if rojos else 2
    info.append(f"ventana {_iso(ini)} - {_iso(fin)} (cinta {_iso(ini_c)} - {_iso(fin)}) sobre "
                f"{'produccion' if SUJETO == 'produccion' else 'base local'}")
    w, wc, f_ = _ts(ini), _ts(ini_c), _ts(fin)

    def triangula() -> None:
        cel = sql(db, f"""SELECT c.venue, c.symbol, extract(epoch FROM c.ts)::bigint, coalesce(sum(x.compra_usd),0),
                                 coalesce(sum(x.venta_usd),0)
                            FROM orderflow_cobertura c LEFT JOIN orderflow_celda x
                                 ON x.symbol=c.symbol AND x.ts=c.ts AND x.venue=c.venue
                           WHERE c.venue IN ('binance_spot','bybit_spot','binance_usdm','bybit_linear')
                             AND c.segundos=60 AND c.definitivo AND c.ts >= '{w}' AND c.ts < '{f_}'
                           GROUP BY 1,2,3""")
        ag = sql(agg, f"""SELECT 'spot', exchange, symbol, extract(epoch FROM ts)::bigint, buy_vol_usd, sell_vol_usd
                            FROM spot_trades_agg WHERE interval='1min' AND exchange IN ('binance','bybit')
                             AND symbol IN ('BTC','ETH','SOL') AND covered_seconds=60 AND ts >= '{w}' AND ts < '{f_}'
                          UNION ALL
                          SELECT 'fut', exchange, left(symbol, 3), extract(epoch FROM ts)::bigint, buy_vol_usd,
                                 sell_vol_usd
                            FROM futures_trades_agg WHERE interval='1min' AND exchange IN ('binance','bybit')
                             AND symbol IN ('BTCUSDT_PERP.A','ETHUSDT_PERP.A','SOLUSDT_PERP.A') AND covered_seconds=60
                             AND ts >= '{w}' AND ts < '{f_}'""")
        inv = {v: k for k, v in TRIANGULO.items()}
        otro = {(inv[(t, ex)], sym, int(ts)): (Decimal(b), Decimal(s)) for t, ex, sym, ts, b, s in ag}
        difs: dict[str, list[Decimal]] = {v: [] for v in TRIANGULO}
        for v, sym, ts, b, s in cel:
            par = otro.get((v, sym, int(ts)))
            if par is None:
                continue
            for x, y in ((Decimal(b), par[0]), (Decimal(s), par[1])):
                if max(x, y) > 0:
                    difs[v].append(abs(x - y) / max(x, y))
        for v, ds in difs.items():
            if len(ds) < TRI_MINUTOS * 2:
                nomed.append(f"(a) {v}: solo {len(ds)} minutos-lado comunes con el colector viejo (hacen falta "
                             f"{TRI_MINUTOS * 2})")
                continue
            ds.sort()
            med = ds[len(ds) // 2]
            cola = Decimal(sum(1 for d in ds if d > TRI_COLA)) / len(ds)
            linea = (f"(a) {v} contra {'spot' if TRIANGULO[v][0] == 'spot' else 'futures'}_trades_agg/"
                     f"{TRIANGULO[v][1]}: {len(ds)} minutos-lado, |dif| p50={med * 100:.4f}% "
                     f"p90={ds[int(len(ds) * .9)] * 100:.3f}% p99={ds[min(len(ds) - 1, int(len(ds) * .99))] * 100:.3f}% "
                     f"max={ds[-1] * 100:.3f}%, >{TRI_COLA * 100:.0f}% en {cola * 100:.2f}%")
            if med > TRI_MEDIANA or cola > TRI_COLA_MAX:
                rojos.append(linea + f" (umbral: p50 <= {TRI_MEDIANA * 100}% y cola <= {TRI_COLA_MAX * 100}%)")
            else:
                info.append(linea)

    def consistencia() -> None:
        # EXACTA en todo minuto con cobertura, salvo los de un ARRANQUE (declarados collector_outage): ahi la cinta
        # puede guardar operaciones del proceso que se fue, cuyas celdas se perdieron con el, y la regla es que las
        # celdas esten CONTENIDAS en su cinta (nunca mas volumen ni mas operaciones que ella). Lo que esa regla no
        # ve, dicho: una celda de un minuto de arranque a la que le FALTA volumen.
        comp, dist, mins, sobra, mins_arr = una(db, f"""
            WITH p AS (SELECT symbol, paso FROM orderflow_paso),
            c AS (SELECT venue, symbol, ts, EXISTS (
                         SELECT 1 FROM data_gap g WHERE g.feed = 'orderflow' AND g.exchange = c.venue
                            AND g.symbol = c.symbol AND g.evidence_type = 'collector_outage'
                            AND g.start_ts <= c.ts AND g.end_ts >= c.ts + interval '1 minute') AS arranque
                    FROM orderflow_cobertura c WHERE definitivo AND ts >= '{wc}' AND ts < '{f_}'),
            cin AS (SELECT t.venue, t.symbol, date_trunc('minute', t.ts) AS ts, floor(t.precio / p.paso) * p.paso AS nivel,
                           sum(t.base) FILTER (WHERE t.compra) cb, sum(t.base) FILTER (WHERE NOT t.compra) vb,
                           sum(t.usd) FILTER (WHERE t.compra) cu, sum(t.usd) FILTER (WHERE NOT t.compra) vu,
                           count(*) FILTER (WHERE t.compra) nc, count(*) FILTER (WHERE NOT t.compra) nv
                      FROM orderflow_cinta t JOIN p USING (symbol)
                     WHERE t.ts >= '{wc}' AND t.ts < '{f_}' GROUP BY 1, 2, 3, 4),
            cel AS (SELECT x.venue, x.symbol, x.ts, x.nivel, x.compra_base cb, x.venta_base vb, x.compra_usd cu,
                           x.venta_usd vu, x.compras nc, x.ventas nv
                      FROM orderflow_celda x WHERE x.ts >= '{wc}' AND x.ts < '{f_}'),
            j AS (SELECT c.arranque, cin.nc AS t_nc, cin.nv AS t_nv, coalesce(cin.cb, 0) t_cb, coalesce(cin.vb, 0) t_vb,
                         coalesce(cin.cu, 0) t_cu, coalesce(cin.vu, 0) t_vu,
                         cel.nc AS c_nc, cel.nv AS c_nv, cel.cb c_cb, cel.vb c_vb, cel.cu c_cu, cel.vu c_vu
                    FROM cin FULL JOIN cel USING (venue, symbol, ts, nivel)
                    JOIN c USING (venue, symbol, ts))
            SELECT count(*) FILTER (WHERE NOT arranque),
                   count(*) FILTER (WHERE NOT arranque AND (t_nc IS NULL OR c_nc IS NULL OR t_cb <> c_cb OR t_vb <> c_vb
                                        OR t_cu <> c_cu OR t_vu <> c_vu OR t_nc <> c_nc OR t_nv <> c_nv)),
                   (SELECT count(*) FROM c WHERE NOT arranque),
                   count(*) FILTER (WHERE arranque AND c_nc IS NOT NULL AND (t_nc IS NULL OR c_cb > t_cb OR c_vb > t_vb
                                        OR c_cu > t_cu OR c_vu > t_vu OR c_nc > t_nc OR c_nv > t_nv)),
                   (SELECT count(*) FROM c WHERE arranque)
              FROM j""")
        if int(mins) == 0:
            nomed.append("(b) ningun minuto (salvo arranques) en la ventana de la cinta: no hay celdas que recalcular")
        elif int(dist):
            rojos.append(f"(b) {dist} de {comp} celdas no son la agregacion exacta de su cinta ({mins} "
                         "minutos-venue-activo, sin contar los de arranque)")
        else:
            info.append(f"(b) {comp} celdas de {mins} minutos = la agregacion exacta de su cinta")
        if int(sobra):
            rojos.append(f"(b) {sobra} celdas de minutos de ARRANQUE con mas de lo que hay en su cinta ({mins_arr} "
                         "minutos de arranque)")
        else:
            info.append(f"(b) {mins_arr} minutos de arranque: sus celdas caben en su cinta")
        fuera_paso, fuera_rango, ops_mal, sin_cob, negativos = una(db, f"""
            SELECT (SELECT count(*) FROM orderflow_celda x JOIN orderflow_paso p USING (symbol)
                     WHERE x.ts >= '{w}' AND x.ts < '{f_}' AND x.nivel % p.paso <> 0),
                   (SELECT count(*) FROM orderflow_celda x JOIN orderflow_paso p USING (symbol)
                      JOIN (SELECT venue, symbol, date_trunc('minute', ts) ts, min(precio) lo, max(precio) hi
                              FROM orderflow_cinta WHERE ts >= '{wc}' AND ts < '{f_}'
                             GROUP BY 1, 2, 3) r USING (venue, symbol, ts)
                     WHERE x.nivel < floor(r.lo / p.paso) * p.paso OR x.nivel > floor(r.hi / p.paso) * p.paso),
                   (SELECT count(*) FROM orderflow_cobertura c
                      LEFT JOIN (SELECT venue, symbol, ts, sum(compras + ventas) n FROM orderflow_celda
                                  WHERE ts >= '{w}' AND ts < '{f_}' GROUP BY 1, 2, 3) x
                             USING (venue, symbol, ts)
                     WHERE c.ts >= '{w}' AND c.ts < '{f_}' AND coalesce(x.n, 0) <> c.operaciones),
                   (SELECT count(*) FROM (SELECT DISTINCT venue, symbol, ts FROM orderflow_celda
                                           WHERE ts >= '{w}' AND ts < '{f_}') x
                      LEFT JOIN orderflow_cobertura c USING (venue, symbol, ts) WHERE c.ts IS NULL),
                   (SELECT count(*) FROM orderflow_celda WHERE ts >= '{w}' AND ts < '{f_}'
                       AND (compra_base < 0 OR venta_base < 0 OR compra_usd < 0 OR venta_usd < 0 OR compras < 0
                            OR ventas < 0 OR nivel < 0))
                 + (SELECT count(*) FROM orderflow_cinta WHERE ts >= '{wc}' AND ts < '{f_}'
                       AND (precio <= 0 OR base <= 0 OR usd <= 0))
                 + (SELECT count(*) FROM orderflow_cobertura WHERE ts >= '{w}' AND ts < '{f_}'
                       AND (segundos < 0 OR segundos > 60 OR operaciones < 0 OR tardias < 0 OR fuera < 0
                            OR reconexiones < 0))""")
        for n, frase in ((fuera_paso, "celdas con un nivel que no es multiplo del paso base"),
                         (fuera_rango, "celdas con un nivel fuera del rango de precios de su minuto en la cinta"),
                         (ops_mal, "minutos cuyas celdas no suman las operaciones de su cobertura"),
                         (sin_cob, "minutos con celdas y sin fila de cobertura"),
                         (negativos, "valores negativos o nulos donde no caben")):
            if int(n):
                rojos.append(f"(b) {n} {frase}")
        info.append(f"(b) niveles multiplo del paso, dentro del rango, conteos = operaciones, sin negativos: "
                    f"{fuera_paso}/{fuera_rango}/{ops_mal}/{sin_cob}/{negativos} defectos")

    def cubre() -> None:
        filas = sql(db, f"""
            WITH m AS (SELECT generate_series('{w}'::timestamptz, '{f_}'::timestamptz - interval '1 minute',
                                              interval '1 minute') AS ts),
            k AS (SELECT v, s FROM unnest(ARRAY{list(VENUES)}) v CROSS JOIN unnest(ARRAY{list(ACTIVOS)}) s),
            e AS (SELECT k.v AS venue, k.s AS symbol, m.ts, c.segundos FROM m CROSS JOIN k
                    LEFT JOIN orderflow_cobertura c ON c.venue = k.v AND c.symbol = k.s AND c.ts = m.ts)
            SELECT venue, count(*), count(*) FILTER (WHERE segundos = 60),
                   count(*) FILTER (WHERE segundos IS NULL),
                   count(*) FILTER (WHERE coalesce(segundos, 0) < 60 AND NOT EXISTS (
                       SELECT 1 FROM data_gap g WHERE g.feed = 'orderflow' AND g.exchange = e.venue
                          AND g.symbol = e.symbol AND g.start_ts <= e.ts AND g.end_ts >= e.ts + interval '1 minute'))
              FROM e GROUP BY venue ORDER BY venue""")
        partes = []
        for venue, esp, comp_, aus, sin_decl in filas:
            frac = Decimal(comp_) / Decimal(esp)
            partes.append(f"{venue} {frac * 100:.1f}%")
            if int(sin_decl):
                rojos.append(f"(c) {venue}: {sin_decl} minutos-activo incompletos o ausentes SIN declarar en data_gap "
                             f"({aus} sin fila) de {esp}")
            if frac < COBERTURA_MIN:
                rojos.append(f"(c) {venue}: solo {comp_} de {esp} minutos-activo completos ({frac * 100:.1f}% < "
                             f"{COBERTURA_MIN * 100:.0f}%)")
        info.append("(c) minutos completos por venue: " + ", ".join(partes))

    def servido() -> None:
        hasta_d, desde_d = ventana_d(fin, primero)
        if hasta_d - desde_d < timedelta(minutes=MARCO_D):
            nomed.append(f"(d) ni una vela de {MARCO_D} min completa dentro de la vida del servicio")
            return
        pasos = {s: Decimal(p) for s, p in sql(db, "SELECT symbol, paso::text FROM orderflow_paso")}
        velas_ok = con_va = 0
        for activo in ACTIVOS:
            paso = pasos[activo] * PASO_D
            q = urllib.parse.urlencode({"symbol": activo, "desde": _iso(desde_d), "hasta": _iso(hasta_d),
                                        "marco": f"{MARCO_D}m", "paso": texto(paso), "unidad": "base"})
            fp = api(f"/api/orderflow/footprint?{q}")
            if not isinstance(fp.get("velas"), list) or fp.get("paso") is None:
                raise Canal(f"/api/orderflow/footprint {activo} no tiene la forma de un footprint")
            malos = compara_footprint(fp, recalcula(db, activo, desde_d, hasta_d, paso, MARCO_D, "base"), desde_d,
                                      MARCO_D)
            q = urllib.parse.urlencode({"symbol": activo, "desde": _iso(desde_d), "hasta": _iso(hasta_d),
                                        "paso": texto(paso), "unidad": "usd"})
            pf = api(f"/api/orderflow/perfil?{q}")
            if not isinstance(pf.get("niveles"), list):
                raise Canal(f"/api/orderflow/perfil {activo} no tiene la forma de un perfil")
            malos += compara_perfil(pf, recalcula(db, activo, desde_d, hasta_d, paso, 60 * 24, "usd"))
            if malos:
                rojos.append(f"(d) {activo} {_iso(desde_d)}-{_iso(hasta_d)} paso {texto(paso)}: {malos[0]}"
                             + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
            velas_ok += len(fp["velas"])
            con_va += sum(1 for x in fp["velas"] if "value_area" in x)
        info.append(f"(d) footprint {MARCO_D}m ({velas_ok} velas) y perfil de {_iso(desde_d)}-{_iso(hasta_d)} a 10x "
                    "el paso base, servidos == recalculados desde las celdas · value area por vela: "
                    + (f"{con_va} de {velas_ok} servidas y recalculadas" if con_va
                       else "SIN JUZGAR, el sujeto no la sirve (anterior a OF-2)"))

    def perfiles() -> None:
        """(d) de OF-3: sesiones (del dia y de una que cruza la medianoche) con su compuesto, el VWAP con sus bandas
        y el TPO, servidos sobre la ventana de (d) == recalculados aqui. Un sujeto anterior a OF-3 no los sirve."""
        hasta_d, desde_d = ventana_d(fin, primero)
        if hasta_d - desde_d < timedelta(minutes=MARCO_D):
            nomed.append(f"(d) OF-3: ni una vela de {MARCO_D} min completa dentro de la vida del servicio")
            return
        pasos = {s: Decimal(p) for s, p in sql(db, "SELECT symbol, paso::text FROM orderflow_paso")}
        cuenta: dict[str, int] = {}
        for activo, nombre, q in peticiones_of3(desde_d, hasta_d, pasos, fin):
            try:
                sv = api(f"/api/orderflow/{nombre}?{urllib.parse.urlencode(q)}")
            except NoLaSirve as exc:
                info.append(f"(d) OF-3: SIN JUZGAR, el sujeto no sirve {exc} (anterior a OF-3)")
                return
            if not isinstance(sv.get("sesiones"), list):
                raise Canal(f"/api/orderflow/{nombre} {activo} no tiene la forma de OF-3")
            if nombre == "sesiones":
                malos = juzga_sesiones(db, activo, q, sv, hasta_d)
            elif nombre == "vwap":
                malos = juzga_vwap(db, activo, q, sv, hasta_d, pasos[activo])
            else:
                malos = juzga_tpo(db, activo, q, sv, hasta_d, pasos[activo])
            if malos:
                rojos.append(f"(d) {activo} {_iso(desde_d)}-{_iso(hasta_d)}: {malos[0]}"
                             + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
            cuenta[nombre] = cuenta.get(nombre, 0) + len(sv["sesiones"])
        info.append(f"(d) OF-3 de {_iso(desde_d)}-{_iso(hasta_d)}: {cuenta.get('sesiones', 0)} sesiones (dia y "
                    f"{plantilla_cruzada(fin)}, que cruza la medianoche) con su compuesto, {cuenta.get('vwap', 0)} VWAP "
                    f"con sus bandas y {cuenta.get('tpo', 0)} TPO, servidos == recalculados")

    def retiene() -> None:
        ret = retencion()
        hoy = ahora.date()
        e = una(db, f"""
            SELECT (SELECT count(*) FROM orderflow_cinta WHERE ts < '{_ts(ahora - timedelta(hours=ret['cinta_h']) - GRACIA)}'),
                   (SELECT count(*) FROM orderflow_celda WHERE ts < '{_ts(ahora - timedelta(days=ret['celda_d']) - GRACIA)}'),
                   (SELECT count(*) FROM orderflow_grande WHERE ts < '{_ts(ahora - timedelta(days=ret['grande_d']) - GRACIA)}'),
                   (SELECT count(*) FROM orderflow_cobertura WHERE segundos = 60
                       AND ts < '{_ts(ahora - timedelta(days=ret['celda_d']) - GRACIA)}'),
                   (to_regclass('orderflow_celda_p{hoy:%Y%m%d}') IS NOT NULL
                    AND to_regclass('orderflow_celda_p{hoy + timedelta(days=1):%Y%m%d}') IS NOT NULL
                    AND to_regclass('orderflow_cinta_p{hoy:%Y%m%d}') IS NOT NULL
                    AND to_regclass('orderflow_cinta_p{hoy + timedelta(days=1):%Y%m%d}') IS NOT NULL)::int,
                   (SELECT count(*) FROM pg_proc WHERE proname IN ('ensure_temporal_partitions',
                                                                   'drop_expired_temporal_partitions')
                       AND position('''orderflow_celda''' in pg_get_functiondef(oid)) > 0
                       AND position('''orderflow_cinta''' in pg_get_functiondef(oid)) > 0)""")
        nombres = ("filas de cinta", "celdas", "grandes", "minutos completos de cobertura")
        for n, nombre, lim in zip(e[:4], nombres, (f"{ret['cinta_h']} h", f"{ret['celda_d']} d",
                                                    f"{ret['grande_d']} d", f"{ret['celda_d']} d"), strict=True):
            if int(n):
                rojos.append(f"(e) {n} {nombre} mas viejas que su retencion ({lim} + {GRACIA})")
        if e[4] != "1":
            rojos.append(f"(e) faltan particiones de hoy o de manana ({hoy} UTC) para orderflow_celda/orderflow_cinta")
        if e[5] != "2":
            rojos.append(f"(e) las funciones vivas de particion no gestionan orderflow_celda y orderflow_cinta "
                         f"({e[5]} de 2)")
        info.append(f"(e) retencion {ret['origen']}: cinta {ret['cinta_h']} h, celdas {ret['celda_d']} d, grandes "
                    f"{ret['grande_d']} d; particiones de hoy y manana; funciones vivas: {e[5]} de 2")

    def agresor() -> None:
        filas = sql(db, f"""
            WITH t AS (SELECT venue, symbol, ts, compra, precio, lag(precio) OVER w AS prev, lag(ts) OVER w AS prev_ts
                         FROM orderflow_cinta WHERE ts >= '{wc}' AND ts < '{f_}'
                       WINDOW w AS (PARTITION BY venue, symbol ORDER BY ts, id))
            SELECT venue, symbol, count(*) FILTER (WHERE precio <> prev),
                   count(*) FILTER (WHERE (precio > prev AND compra) OR (precio < prev AND NOT compra))
              FROM t WHERE prev IS NOT NULL AND ts > prev_ts GROUP BY 1, 2 ORDER BY 1, 2""")
        juzgados: dict[str, list[str]] = {}
        for venue, sym, cambios, acuerdo in filas:
            if int(cambios) < TICK_MUESTRA:
                continue
            c = Decimal(acuerdo) / Decimal(cambios)
            juzgados.setdefault(venue, []).append(f"{sym} {c:.3f}")
            if c < TICK_MIN:
                rojos.append(f"(f) {venue} {sym}: el agresor contradice al precio en {(1 - c) * 100:.1f}% de {cambios} "
                             f"cambios (concordancia {c:.3f} < {TICK_MIN}): el lado esta al reves")
        sin = [v for v in VENUES if v not in juzgados]
        if sin:
            nomed.append(f"(f) sin {TICK_MUESTRA} cambios de precio en ningun activo: {', '.join(sin)}")
        info.append("(f) concordancia del tick con el agresor: " + "; ".join(
            f"{v} {', '.join(x)}" for v, x in sorted(juzgados.items())))

    for letra, brazo in (("a", triangula), ("b", consistencia), ("c", cubre), ("d", servido), ("d", perfiles),
                         ("e", retiene), ("f", agresor)):
        try:
            brazo()
        except Canal as exc:
            nomed.append(f"({letra}) NO MEDIDO (CANAL): {exc}")
        except (ArithmeticError, KeyError, ValueError, TypeError) as exc:  # OF-3: un recalculo que no sabe con un
            # dato roto no tumba a los demas brazos (el que lo ve, lo condena): se dice, y no se juzga ese brazo
            nomed.append(f"({letra}) NO MEDIDO: el recalculo de {brazo.__name__} no pudo con lo que hay "
                         f"({type(exc).__name__}: {str(exc)[:120]})")

    if rojos:
        print(f"ROJO  K108 {rojos[0][:240]}")
        for r in rojos[1:]:
            print(f"   - {r}")
    elif nomed:
        print(f"NO MEDIDO: K108 {nomed[0][:240]}")
    else:
        print(f"VERDE  K108 · el dato del order-flow: {len(VENUES)} venues, triangulado, consistente, cubierto, "
              "servido = recalculado, retenido y con el agresor en su sitio")
    for n in nomed[1 if not rojos else 0:]:
        print(f"   ? {n}")
    for i in info:
        print(f"   · {i}")
    return 1 if rojos else (2 if nomed else 0)


def retencion() -> dict:
    """Las retenciones que el sujeto APLICA: su config.py (Field(default=...)), pisadas por su entorno."""
    import re

    if SUJETO == "produccion":
        r = subprocess.run(["sh", f"{H}/bin/prod", "grep -hoE 'ORDERFLOW_[A-Z_]+(: int = Field\\(default=|=)[0-9]+' "
                            "/opt/coinalyze/current/app/config.py /etc/coinalyze/coinalyze.env"],
                           capture_output=True, text=True, timeout=60, env={**os.environ, "TODO": "1"})
        texto_cfg, origen = r.stdout, "leida de 140 (config.py del release y coinalyze.env)"
    else:
        texto_cfg, origen = (Path(REPO) / "app/config.py").read_text(), "leida del config.py del arbol"
    val = {}
    for nombre, n in re.findall(r"(ORDERFLOW_[A-Z_]+)(?:: int = Field\(default=|=)([0-9]+)", texto_cfg):
        val[nombre] = int(n)  # el entorno va despues en el grep: pisa al defecto
    try:
        return {"cinta_h": val["ORDERFLOW_TAPE_RETENTION_HOURS"], "celda_d": val["ORDERFLOW_CELL_RETENTION_DAYS"],
                "grande_d": val["ORDERFLOW_LARGE_RETENTION_DAYS"], "origen": origen}
    except KeyError as exc:
        raise Canal(f"no se pudo leer la retencion {exc} ({origen})") from exc


def sirve(directorio: str, planta: str = "") -> int:
    """Lo que serviria el ARBOL para las peticiones de (d), con las rutas de verdad de app/api.py sobre K108_BASE.
    Es lo que el control usa como «lo servido» y lo que planta torcido. Con `planta` (OF-3, campana 143) se sirve con
    UN defecto inyectado en el proceso, el arbol sin tocar: `partir_medianoche` (la sesion que cruza la medianoche,
    partida en dos) o `vwap_al_nivel` (el VWAP con el precio del NIVEL en vez de usd/base: otra cuenta)."""
    import asyncio

    import asyncpg

    sys.path.insert(0, REPO)
    import app.api as api_mod
    from app import orderflow_lectura as lec

    if planta == "partir_medianoche":
        original = lec.instancias

        def partidas(ses, a, b):
            out = []
            for s, e in original(ses, a, b):
                m = s.replace(hour=0, minute=0) + timedelta(days=1)
                out += [(s, m), (m, e)] if s < m < e else [(s, e)]
            return [(s, e) for s, e in out if e > a and s < b]

        lec.instancias = partidas
    elif planta == "vwap_al_nivel":
        lec.VWAP_SQL = lec.VWAP_SQL.replace("sum(compra_usd) + sum(venta_usd)", "sum(nivel * (compra_base + venta_base))")
    elif planta:
        raise SystemExit(f"planta desconocida: {planta}")

    class _Peticion:
        def __init__(self, **q):
            self.query_params = q

    async def corre():
        pool = await asyncpg.create_pool(BASE, min_size=1, max_size=2, server_settings={"timezone": "UTC"})
        api_mod.app.state.pool = pool
        try:
            ahora = datetime.fromisoformat(RELOJ)
            async with pool.acquire() as c:
                primero = await c.fetchval("SELECT min(ts) FROM orderflow_cobertura")
                pasos = {r["symbol"]: Decimal(r["paso"]) for r in await c.fetch(
                    "SELECT symbol, paso::text AS paso FROM orderflow_paso")}
            fin = ahora.replace(second=0, microsecond=0) - timedelta(minutes=3)
            hasta_d, desde_d = ventana_d(fin, primero)
            for activo in ACTIVOS:
                paso = texto(pasos[activo] * PASO_D)
                for nombre, q, f in (
                    ("footprint", {"symbol": activo, "desde": _iso(desde_d), "hasta": _iso(hasta_d), "marco": f"{MARCO_D}m",
                                   "paso": paso, "unidad": "base"}, api_mod.orderflow_footprint),
                    ("perfil", {"symbol": activo, "desde": _iso(desde_d), "hasta": _iso(hasta_d), "paso": paso,
                                "unidad": "usd"}, api_mod.orderflow_perfil),
                ):
                    resp = await f(_Peticion(**q), **q)
                    ruta = f"/api/orderflow/{nombre}?{urllib.parse.urlencode(q)}"
                    (Path(directorio) / (urllib.parse.quote(ruta, safe="") + ".json")).write_text(
                        json.dumps(resp, default=str))
            rutas = {"sesiones": api_mod.orderflow_sesiones, "vwap": api_mod.orderflow_vwap, "tpo": api_mod.orderflow_tpo}
            for _activo, nombre, q in peticiones_of3(desde_d, hasta_d, pasos, fin):
                resp = await rutas[nombre](_Peticion(**q), **q)
                ruta = f"/api/orderflow/{nombre}?{urllib.parse.urlencode(q)}"
                (Path(directorio) / (urllib.parse.quote(ruta, safe="") + ".json")).write_text(
                    json.dumps(resp, default=str))
        finally:
            await pool.close()

    asyncio.run(corre())
    print("servido:", directorio, "app de", api_mod.__file__)
    return 0


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "juzga":
        sys.exit(juzga())
    if orden == "sirve" and len(sys.argv) == 3:
        sys.exit(sirve(sys.argv[2]))
    if orden == "sirve" and len(sys.argv) == 5 and sys.argv[3] == "--planta":
        sys.exit(sirve(sys.argv[2], sys.argv[4]))
    print("NO MEDIDO: uso K108-orderflow.py juzga | sirve <dir> [--planta X]")
    sys.exit(2)
