"""K110 · ayudante: junta, recalcula por su cuenta y juzga el dato del libro (OF-4a, campana 144).

No importa NADA de app/libro_lectura.py: lo servido se recalcula aqui desde las filas con su propia aritmetica (la
agregacion a un paso mayor y el corte del nivel del borde se reescriben desde su declaracion). Si se reusara el codigo
que se audita, (d) compararia el codigo consigo mismo.

Uso: K110-libro.py juzga   (el entorno lo pone K110-el-libro.sh)
     K110-libro.py sirve <dir>   (escribe lo que serviria el arbol, para los controles)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path

H = os.environ.get("K110_HARNESS", "/srv/coinanalyze/harness")
REPO = os.environ.get("K110_REPO", "/srv/coinanalyze/repo")
SUJETO = os.environ.get("K110_SUJETO", "produccion")
BASE = os.environ.get("K110_BASE", "")
VIEJO = os.environ.get("K110_VIEJO", "")  # donde esta orderbook_snapshot (el colector viejo): por omision, el sujeto
SERVIDO = os.environ.get("K110_SERVIDO", "")
RELOJ = os.environ.get("K110_RELOJ", "")

VENUES = ("binance_usdm", "binance_spot", "bybit_linear", "bybit_spot", "okx_swap", "okx_spot", "bitget_usdt",
          "deribit_perp", "coinbase_spot")
# El control juzga un sujeto grabado de DOS venues (los nueve no caben en el repo): K110_VENUES lo dice. Por omision, los
# nueve, y un venue que falta en la cobertura es un venue sin declarar.
VENUES = tuple(v for v in os.environ.get("K110_VENUES", ",".join(VENUES)).split(",") if v in VENUES)
ACTIVOS = tuple(a for a in os.environ.get("K110_ACTIVOS", "BTC,ETH,SOL").split(",") if a in ("BTC", "ETH", "SOL"))
# (b) los dos venues que tienen un colector INDEPENDIENTE del mismo libro en 140 (scalp_collector -> orderbook_snapshot)
TRIANGULO = {v: ex for v, ex in {"binance_usdm": "binance", "bybit_linear": "bybit"}.items() if v in VENUES}
SIMBOLO_VIEJO = {"BTC": "BTCUSDT_PERP.A", "ETH": "ETHUSDT_PERP.A", "SOL": "SOLUSDT_PERP.A"}
# Umbrales DECLARADOS en la prediccion ante-hoc (entregas/20261017-2250-libro-dato-prediccion.md) y no movidos.
TRI_MEDIANA_BPS, TRI_COLA_BPS, TRI_COLA_MAX = Decimal("0.5"), Decimal("5"), Decimal("0.05")
TRI_PARES = int(os.environ.get("K110_PARES", "100"))
VENTANA = timedelta(hours=int(os.environ.get("K110_HORAS", "6")))
VENTANA_B = timedelta(hours=1)
COBERTURA_MIN = Decimal("0.90")
SIN_ESCRIBIR = timedelta(minutes=10)
GRACIA = timedelta(hours=2)
VENTANA_D, CADA_D, MULT_D = timedelta(minutes=30), 60, 5  # (d): la ultima media hora, una foto por minuto, y a 5x
MINIMO = timedelta(minutes=int(os.environ.get("K110_MINIMO", "30")))  # vida minima del servicio para juzgar


class Canal(Exception):
    pass


class NoLaSirve(Canal):
    """La ruta no existe en el sujeto (404): un sujeto anterior a OF-4a."""


def _ts(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00")


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dt(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace(" ", "T").replace("+00", "+00:00").replace("Z", "+00:00"))


def sql(destino: str, q: str) -> list[list[str]]:
    """Filas de texto. `produccion` va por bin/prodsql (solo lectura, UTC); otra cosa es un DSN de 143."""
    if destino == "produccion":
        cmd = ["sh", f"{H}/bin/prodsql", q]
        env = {**os.environ, "TODO": "1"}
    else:
        cmd = ["psql", destino, "-X", "-A", "-F|", "-t", "-q", "-v", "ON_ERROR_STOP=1",
               "-c", "SET TIME ZONE 'UTC'", "-c", q]
        env = dict(os.environ)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
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
        r = subprocess.run(["sh", f"{H}/bin/api", ruta], capture_output=True, text=True, timeout=180,
                           env={**os.environ, "TODO": "1"})
        if r.returncode != 0 and "HTTP 404" in r.stderr:
            raise NoLaSirve(ruta.split("?")[0])
        if r.returncode != 0:
            raise Canal(f"api {ruta.split('?')[0]} rc={r.returncode}")
        try:
            return json.loads(r.stdout)
        except ValueError as exc:
            raise Canal(f"api {ruta.split('?')[0]} no devolvio JSON") from exc
    nombre = fichero_servido(SERVIDO, ruta)
    if not nombre.is_file():
        raise Canal(f"no hay respuesta servida para {ruta} en {SERVIDO}")
    d = json.loads(nombre.read_text())
    if d.get("__http__") == 404:  # el sujeto local no sirve esa ruta (uno anterior a ella)
        raise NoLaSirve(ruta.split("?")[0])
    return d


def fichero_servido(directorio: str, ruta: str) -> Path:
    """Donde `sirve` guarda la respuesta a una ruta (la ruta entera no cabe en un nombre de fichero)."""
    import hashlib

    return Path(directorio) / (hashlib.sha256(ruta.encode()).hexdigest()[:32] + ".json")


def texto(d: Decimal) -> str:
    return "0" if d == 0 else format(d.normalize(), "f")


def nivel(precio: Decimal, paso: Decimal) -> Decimal:
    return (precio / paso).to_integral_value(rounding=ROUND_FLOOR) * paso


def declarado(arbol: bool = False) -> dict:
    """Lo que el sujeto DECLARA: paso, banda y cadencia de app/libro.py, y la retencion de su config.py pisada por su
    entorno. En produccion se lee del release de 140; en local (o para `sirve`), del arbol."""
    if SUJETO == "produccion" and not arbol:
        r = subprocess.run(["sh", f"{H}/bin/prod", "grep -hE '^(FOTO_S|PASOS|BANDA) = |LIBRO_RETENTION_DAYS' "
                            "/opt/coinalyze/current/app/libro.py /opt/coinalyze/current/app/config.py "
                            "/etc/coinalyze/coinalyze.env"], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "TODO": "1"})
        fuente, origen = r.stdout, "leido de 140 (app/libro.py y config.py del release, coinalyze.env)"
    else:
        fuente = "\n".join((Path(REPO) / f).read_text() for f in ("app/libro.py", "app/config.py"))
        origen = "leido del arbol"
    try:
        foto_s = int(re.search(r"^FOTO_S = (\d+)", fuente, re.M).group(1))
        pasos = {a: Decimal(p) for a, p in re.findall(r'"(BTC|ETH|SOL)": Decimal\("([0-9.]+)"\)',
                                                       re.search(r"^PASOS = (.*)$", fuente, re.M).group(1))}
        banda = {a: int(n) for a, n in re.findall(r'"(BTC|ETH|SOL)": (\d+)', re.search(r"^BANDA = (.*)$", fuente,
                                                                                        re.M).group(1))}
        dias = [int(x) for x in re.findall(r"LIBRO_RETENTION_DAYS(?:: int = Field\(default=|=)(\d+)", fuente)]
        return {"foto_s": foto_s, "pasos": pasos, "banda": banda, "dias": dias[-1], "origen": origen}
    except (AttributeError, IndexError, ValueError) as exc:
        raise Canal(f"no se pudo leer lo declarado ({origen}): {exc}") from exc


def reagrega(desde: Decimal, cantidades: list[Decimal], fino: Decimal, paso: Decimal, abajo: bool):
    """Reescrita desde la declaracion de la API: los niveles finos sumados a niveles de `paso`; un nivel grueso solo
    sale si TODOS sus finos estan dentro de lo guardado, salvo la parte del otro lado del mejor precio, que se sabe
    vacia. Devuelve (nivel del primero, cantidades) o None."""
    if paso == fino:
        return desde, cantidades
    n = len(cantidades)
    finos = {(desde - i * fino if abajo else desde + i * fino): q for i, q in enumerate(cantidades)}
    bajo, alto = (desde - (n - 1) * fino, desde) if abajo else (desde, desde + (n - 1) * fino)
    out = []
    g = nivel(desde, paso)
    while True:
        dentro = [f for f in finos if g <= f < g + paso]
        completo = (g >= bajo) if abajo else (g + paso - fino <= alto)
        if not dentro or not completo:
            break
        out.append(sum((finos[f] for f in dentro), Decimal(0)))
        g = g - paso if abajo else g + paso
    return (nivel(desde, paso), out) if out else None


def ventana_d(fin: datetime, primero: datetime) -> tuple[datetime, datetime]:
    hasta = fin.replace(second=0, microsecond=0)
    return hasta, max(hasta - VENTANA_D, primero.replace(second=0, microsecond=0) + timedelta(minutes=1))


def peticiones_d(desde: datetime, hasta: datetime, pasos: dict) -> list[tuple[str, str, dict]]:
    """Lo que (d) pide: por activo, las fotos de cada venue al paso guardado y a MULT_D veces, una por minuto, y la
    cobertura de los nueve."""
    out = []
    for activo in ACTIVOS:
        w = {"symbol": activo, "desde": _iso(desde), "hasta": _iso(hasta), "venues": ",".join(VENUES)}
        for p in (pasos[activo], pasos[activo] * MULT_D):
            out.append((activo, "fotos", {**w, "paso": texto(p), "cada": str(CADA_D)}))
        out.append((activo, "cobertura", w))
    return out


RUTA_ULTIMO = "/api" + "/libro/ultimo"


def peticiones_ultimo(base: Decimal, grueso: Decimal) -> list[str]:
    """(d) OF-4b: el libro VIVO por GET de un activo y sus venues, al paso BASE de OF-1 (lo que trae el aviso) y al paso
    guardado de la foto (el grueso), con todos los niveles que caben."""
    q = {"symbol": ACTIVOS[0], "venues": ",".join(VENUES), "niveles": "100"}
    return [f"{RUTA_ULTIMO}?{urllib.parse.urlencode({**q, 'paso': texto(p)})}" for p in (base, grueso)]


def juzga_ultimo(fino: dict, grueso: dict, base: Decimal, paso: Decimal) -> tuple[int, int, list[str]]:
    """Cada libro de las dos respuestas tiene que estar bien formado (compra < venta, el primer nivel de cada lado el de
    su mejor precio, niveles seguidos al paso, cantidades >= 0); y en los venues cuyo aviso es el MISMO en las dos (mismo
    emitido_ms), la escalera gruesa == la fina reagregada con la aritmetica de este check. -> (venues, casados, malos)"""
    malos: list[str] = []
    por = [{x["venue"]: x for x in r.get("libros") or []} for r in (fino, grueso)]
    for r, p in ((por[0], base), (por[1], paso)):
        for v, x in r.items():
            if x.get("tipo") != "libro":
                continue
            c, w = Decimal(x["compra"]), Decimal(x["venta"])
            if not c < w:
                malos.append(f"{v} al paso {texto(p)}: compra {x['compra']} >= venta {x['venta']}")
            for lado, mejor, signo in (("compras", c, -1), ("ventas", w, 1)):
                niv = [Decimal(a) for a, _ in x[lado]]
                if niv and (niv[0] != nivel(mejor, p) or any(b - a != signo * p for a, b in zip(niv, niv[1:], strict=False))):
                    malos.append(f"{v} al paso {texto(p)}: los niveles de {lado} no van seguidos desde su mejor precio")
                if any(Decimal(q) < 0 for _, q in x[lado]):
                    malos.append(f"{v} al paso {texto(p)}: una cantidad negativa en {lado}")
    casados = 0
    for v, f in por[0].items():
        g = por[1].get(v)
        if not g or f.get("tipo") != "libro" or g.get("tipo") != "libro" or f.get("emitido_ms") != g.get("emitido_ms"):
            continue
        casados += 1
        for lado, abajo in (("compras", True), ("ventas", False)):
            fin = f[lado]
            r = reagrega(Decimal(fin[0][0]), [Decimal(q) for _, q in fin], base, paso, abajo) if fin else None
            mio = [[texto(r[0] - i * paso if abajo else r[0] + i * paso), texto(q)] for i, q in enumerate(r[1])] if r else []
            if mio[:100] != [[texto(Decimal(a)), texto(Decimal(q))] for a, q in g[lado]]:
                malos.append(f"{v}: la escalera de {lado} servida al paso {texto(paso)} != la del paso {texto(base)} "
                             "reagregada")
    return len(por[0]), casados, malos


# --------------------------------------------------------------------------------------------- juicio
def juzga() -> int:
    """Cinco brazos. Cada uno captura SU canal: un brazo que no se pudo medir es NO MEDIDO, y un ROJO medido en otro
    brazo manda sobre el. Solo el preludio (las tablas, el reloj, la vida del servicio) decide por todos."""
    if SUJETO == "local" and not BASE:
        print("NO MEDIDO: K110_SUJETO=local pide K110_BASE")
        return 2
    db = "produccion" if SUJETO == "produccion" else BASE
    viejo = VIEJO or db
    rojos: list[str] = []
    nomed: list[str] = []
    info: list[str] = []
    try:
        hay = una(db, "SELECT (to_regclass('libro_foto') IS NOT NULL AND to_regclass('libro_cobertura') IS NOT NULL "
                      "AND to_regclass('orderflow_paso') IS NOT NULL)::int")
        if hay != ["1"]:
            print("NO MEDIDO: FALTA DESPLEGAR · el sujeto no tiene las tablas libro_foto / libro_cobertura (OF-4a); sin "
                  "ellas no hay libro que juzgar")
            return 2
        ahora = _dt(RELOJ) if RELOJ else _dt(una(db, "SELECT to_char(now() AT TIME ZONE 'UTC', "
                                                     "'YYYY-MM-DD\"T\"HH24:MI:SS+00:00')")[0])
        primero_txt, ultimo_txt, n_cob = una(db, "SELECT min(ts), max(ts), count(*) FROM libro_cobertura")
        if int(n_cob) == 0:
            print("NO MEDIDO: las tablas libro_* estan pero libro_cobertura no tiene ni una fila: el servicio no ha "
                  "escrito nunca. Cero defectos sobre cero filas no es cero defectos")
            return 2
        dec = declarado()
    except Canal as exc:
        print(f"NO MEDIDO (CANAL): {exc}")
        return 2
    primero, ultimo = _dt(primero_txt), _dt(ultimo_txt)
    fin = ahora.replace(second=0, microsecond=0) - timedelta(minutes=2)
    ini = max(fin - VENTANA, primero)
    if ahora - ultimo > SIN_ESCRIBIR:
        rojos.append(f"(c) el servicio no escribe: el ultimo minuto con cobertura es {_iso(ultimo)}, "
                     f"{int((ahora - ultimo).total_seconds() // 60)} min antes de {_iso(ahora)}")
    if fin - ini < MINIMO:
        print(f"NO MEDIDO: el servicio lleva menos de {MINIMO} de minutos escritos ({_iso(ini)}-{_iso(fin)}); no hay "
              "ventana que juzgar todavia")
        for r in rojos:
            print(f"   - {r}")
        return 1 if rojos else 2
    n_s = dec["foto_s"]
    info.append(f"ventana {_iso(ini)} - {_iso(fin)} sobre {'produccion' if SUJETO == 'produccion' else 'base local'}; "
                f"declarado ({dec['origen']}): una foto cada {n_s} s, pasos {', '.join(f'{a} {texto(p)}' for a, p in dec['pasos'].items())}, "
                f"banda {dec['banda']}, retencion {dec['dias']} d")
    w, f_ = _ts(ini), _ts(fin)

    def valido() -> None:
        casos = "\n".join(
            f"WHEN '{a}' THEN {dec['banda'][a]}" for a in ACTIVOS)
        pasos = "\n".join(f"WHEN '{a}' THEN {texto(dec['pasos'][a])}" for a in ACTIVOS)
        (total, cruzadas, nivel_c, nivel_v, vacias, negativas, banda, paso_base, alcance, rejilla, paso_decl) = una(db, f"""
            WITH f AS (SELECT f.*, p.paso AS base, cardinality(compras) AS nc, cardinality(ventas) AS nv
                         FROM libro_foto f JOIN orderflow_paso p USING (symbol)
                        WHERE f.ts >= '{w}' AND f.ts < '{f_}')
            SELECT count(*),
                   count(*) FILTER (WHERE NOT compra < venta),
                   count(*) FILTER (WHERE compra_nivel <> floor(compra / paso) * paso),
                   count(*) FILTER (WHERE venta_nivel <> floor(venta / paso) * paso),
                   count(*) FILTER (WHERE NOT (compras[1] > 0 AND ventas[1] > 0)),
                   count(*) FILTER (WHERE NOT (0 <= ALL (compras) AND 0 <= ALL (ventas))),
                   count(*) FILTER (WHERE nc > CASE symbol {casos} END OR nv > CASE symbol {casos} END
                                       OR nc < 1 OR nv < 1),
                   count(*) FILTER (WHERE paso % base <> 0),
                   count(*) FILTER (WHERE compra_nivel - (nc - 1) * paso < alcance_compra
                                       OR venta_nivel + nv * paso > alcance_venta
                                       OR compra < alcance_compra OR venta > alcance_venta),
                   count(*) FILTER (WHERE extract(epoch FROM ts)::bigint % {n_s} <> 0),
                   count(*) FILTER (WHERE paso <> CASE symbol {pasos} END)
              FROM f""")
        if int(total) == 0:
            nomed.append("(a) ni una foto en la ventana")
            return
        for n, frase in ((cruzadas, "fotos con la mejor compra >= la mejor venta (un libro cruzado)"),
                         (nivel_c, "fotos con el nivel de la mejor compra que no es floor(compra / paso) * paso"),
                         (nivel_v, "fotos con el nivel de la mejor venta que no es floor(venta / paso) * paso"),
                         (vacias, "fotos cuyo mejor nivel no tiene cantidad"),
                         (negativas, "fotos con alguna cantidad negativa"),
                         (banda, "fotos con mas niveles que la banda declarada (o ninguno)"),
                         (paso_base, "fotos con un paso que no es multiplo del paso base de OF-1"),
                         (alcance, "fotos con niveles fuera del alcance declarado"),
                         (rejilla, f"fotos fuera de la rejilla de {n_s} s"),
                         (paso_decl, "fotos con un paso que no es el declarado")):
            if int(n):
                rojos.append(f"(a) {n} de {total} {frase}")
        info.append(f"(a) {total} fotos: cruzadas/nivel compra/nivel venta/mejor vacio/negativas/banda/paso base/"
                    f"alcance/rejilla/paso: {cruzadas}/{nivel_c}/{nivel_v}/{vacias}/{negativas}/{banda}/{paso_base}/"
                    f"{alcance}/{rejilla}/{paso_decl} defectos")

    def triangula() -> None:
        ini_b = max(fin - VENTANA_B, primero)
        mias = sql(db, f"""SELECT venue, symbol, extract(epoch FROM ts_libro)::numeric, compra, venta FROM libro_foto
                            WHERE venue IN ('binance_usdm', 'bybit_linear') AND ts >= '{_ts(ini_b)}' AND ts < '{f_}'""")
        suyas = sql(viejo, f"""SELECT exchange, symbol, extract(epoch FROM ts)::numeric, bid_px, ask_px
                                 FROM orderbook_snapshot WHERE exchange IN ('binance', 'bybit')
                                  AND symbol IN ('BTCUSDT_PERP.A', 'ETHUSDT_PERP.A', 'SOLUSDT_PERP.A')
                                  AND bid_px IS NOT NULL AND ask_px IS NOT NULL
                                  AND ts >= '{_ts(ini_b - timedelta(seconds=5))}' AND ts < '{f_}'""")
        por_segundo: dict[tuple, list] = {}
        for ex, sym, t, b, a in suyas:
            por_segundo.setdefault((ex, sym, int(Decimal(t))), []).append((Decimal(t), Decimal(b), Decimal(a)))
        difs: dict[str, list[Decimal]] = {v: [] for v in TRIANGULO}
        dts: list[Decimal] = []
        for v, sym, t, b, a in mias:
            if v not in TRIANGULO:
                continue
            t = Decimal(t)
            cands = por_segundo.get((TRIANGULO[v], SIMBOLO_VIEJO[sym], int(t)))
            if not cands:
                continue
            tt, bb, aa = min(cands, key=lambda c: abs(c[0] - t))
            dts.append(abs(tt - t))
            medio = (Decimal(b) + Decimal(a)) / 2
            for mio, suyo in ((Decimal(b), bb), (Decimal(a), aa)):
                difs[v].append(abs(mio - suyo) / medio * 10000)
        for v, ds in difs.items():
            if len(ds) < TRI_PARES * 2:
                nomed.append(f"(b) {v}: solo {len(ds) // 2} pares en el mismo segundo con orderbook_snapshot (hacen "
                             f"falta {TRI_PARES})")
                continue
            ds.sort()
            med = ds[len(ds) // 2]
            cola = Decimal(sum(1 for d in ds if d > TRI_COLA_BPS)) / len(ds)
            exactos = Decimal(sum(1 for d in ds if d == 0)) / len(ds)
            linea = (f"(b) {v} contra orderbook_snapshot/{TRIANGULO[v]}: {len(ds) // 2} pares, |dif| bps p50={med:.3f} "
                     f"p90={ds[int(len(ds) * .9)]:.3f} p99={ds[min(len(ds) - 1, int(len(ds) * .99))]:.3f} "
                     f"max={ds[-1]:.3f}, >{TRI_COLA_BPS} bps en {cola * 100:.2f}%, exactos {exactos * 100:.1f}%")
            if med > TRI_MEDIANA_BPS or cola > TRI_COLA_MAX:
                rojos.append(linea + f" (umbral: p50 <= {TRI_MEDIANA_BPS} bps y cola <= {TRI_COLA_MAX * 100}%)")
            else:
                info.append(linea)
        if dts:
            dts.sort()
            info.append(f"(b) distancia entre las dos horas del venue en cada par: p50 {dts[len(dts) // 2] * 1000:.0f} "
                        f"ms, max {dts[-1] * 1000:.0f} ms")

    def cubre() -> None:
        filas = sql(db, f"""
            WITH m AS (SELECT generate_series('{w}'::timestamptz, '{f_}'::timestamptz - interval '1 minute',
                                              interval '1 minute') AS ts),
            k AS (SELECT v, s FROM unnest(ARRAY{list(VENUES)}) v CROSS JOIN unnest(ARRAY{list(ACTIVOS)}) s),
            e AS (SELECT k.v AS venue, k.s AS symbol, m.ts, c.segundos FROM m CROSS JOIN k
                    LEFT JOIN libro_cobertura c ON c.venue = k.v AND c.symbol = k.s AND c.ts = m.ts)
            SELECT venue, count(*), count(*) FILTER (WHERE segundos = 60), count(*) FILTER (WHERE segundos IS NULL),
                   count(*) FILTER (WHERE coalesce(segundos, 0) < 60 AND NOT EXISTS (
                       SELECT 1 FROM data_gap g WHERE g.feed = 'libro' AND g.exchange = e.venue
                          AND g.symbol = e.symbol AND g.start_ts <= e.ts AND g.end_ts >= e.ts + interval '1 minute'))
              FROM e GROUP BY venue ORDER BY venue""")
        partes = []
        for venue, esp, comp, aus, sin_decl in filas:
            frac = Decimal(comp) / Decimal(esp)
            partes.append(f"{venue} {frac * 100:.1f}%")
            if int(sin_decl):
                rojos.append(f"(c) {venue}: {sin_decl} minutos-activo incompletos o ausentes SIN declarar en data_gap "
                             f"({aus} sin fila) de {esp}")
            if frac < COBERTURA_MIN:
                rojos.append(f"(c) {venue}: solo {comp} de {esp} minutos-activo completos ({frac * 100:.1f}% < "
                             f"{COBERTURA_MIN * 100:.0f}%)")
        info.append("(c) minutos completos por venue: " + ", ".join(partes))
        # NUNCA RELLENADO: lo que la cobertura dice tiene que cuadrar con las fotos que hay y con los huecos declarados
        cuenta, mas_fotos, completo_corto, sin_fila, declarado_completo = una(db, f"""
            WITH x AS (SELECT venue, symbol, date_trunc('minute', ts) AS ts, count(*) AS n FROM libro_foto
                        WHERE ts >= '{w}' AND ts < '{f_}' GROUP BY 1, 2, 3),
            c AS (SELECT * FROM libro_cobertura WHERE ts >= '{w}' AND ts < '{f_}')
            SELECT (SELECT count(*) FROM c LEFT JOIN x USING (venue, symbol, ts) WHERE coalesce(x.n, 0) <> c.fotos),
                   (SELECT count(*) FROM c WHERE fotos > c.segundos / {n_s} + 1),
                   (SELECT count(*) FROM c WHERE segundos = 60 AND fotos <> 60 / {n_s}),
                   (SELECT count(*) FROM x LEFT JOIN c USING (venue, symbol, ts) WHERE c.ts IS NULL),
                   (SELECT count(*) FROM c WHERE segundos = 60 AND EXISTS (
                        SELECT 1 FROM data_gap g WHERE g.feed = 'libro' AND g.exchange = c.venue AND g.symbol = c.symbol
                           AND g.start_ts <= c.ts AND g.end_ts >= c.ts + interval '1 minute'))""")
        for n, frase in ((cuenta, "minutos cuya cobertura no cuenta las fotos que hay"),
                         (mas_fotos, f"minutos con mas fotos de las que caben en sus segundos (una cada {n_s} s)"),
                         (completo_corto, f"minutos completos sin sus {60 // n_s} fotos"),
                         (sin_fila, "minutos con fotos y sin fila de cobertura"),
                         (declarado_completo, "minutos completos que tienen un hueco declarado encima")):
            if int(n):
                rojos.append(f"(c) cobertura RELLENADA: {n} {frase}")
        info.append(f"(c) cobertura sin rellenar: fotos contadas/de mas/completos cortos/sin fila/declarados completos: "
                    f"{cuenta}/{mas_fotos}/{completo_corto}/{sin_fila}/{declarado_completo} defectos")

    def servido() -> None:
        hasta_d, desde_d = ventana_d(fin, primero)
        if hasta_d - desde_d < timedelta(minutes=2):
            nomed.append("(d) ni dos minutos escritos dentro de la vida del servicio")
            return
        cuenta = {"fotos": 0, "cobertura": 0}
        for activo, nombre, q in peticiones_d(desde_d, hasta_d, dec["pasos"]):
            try:
                sv = api(f"/api/libro/{nombre}?{urllib.parse.urlencode(q)}")
            except NoLaSirve as exc:
                nomed.append(f"(d) el sujeto no sirve {exc}: FALTA DESPLEGAR la lectura")
                return
            malos = juzga_fotos(db, activo, q, sv) if nombre == "fotos" else juzga_cobertura(db, activo, q, sv)
            if malos:
                rojos.append(f"(d) {activo} {nombre} paso {q.get('paso', '-')}: {malos[0]}"
                             + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
            cuenta[nombre] += len(sv.get("fotos") or sv.get("venues") or [])
        info.append(f"(d) de {_iso(desde_d)}-{_iso(hasta_d)}: {cuenta['fotos']} fotos servidas (al paso guardado y a "
                    f"{MULT_D}x, una por minuto) y {cuenta['cobertura']} coberturas por venue == las guardadas")
        # OF-4b (campana 145): el libro VIVO por GET. La primera peticion despierta la escucha del relevo en la API; luego
        # el paso base y el guardado, seguidos, hasta tres veces si ningun venue trae el mismo aviso en las dos.
        base = Decimal(una(db, f"SELECT paso FROM orderflow_paso WHERE symbol = '{ACTIVOS[0]}'")[0])
        grueso = dec["pasos"][ACTIVOS[0]]
        fino_url, grueso_url = peticiones_ultimo(base, grueso)
        try:
            api(grueso_url)
        except NoLaSirve:
            info.append(f"(d) el libro vivo por GET: SIN JUZGAR, el sujeto no sirve {RUTA_ULTIMO} (anterior a OF-4b)")
            return
        n, casados, malos = 0, 0, []
        for _ in range(3 if SUJETO == "produccion" else 1):
            if SUJETO == "produccion":
                time.sleep(2)
            n, casados, malos = juzga_ultimo(api(fino_url), api(grueso_url), base, grueso)
            if casados or malos:
                break
        if malos:
            rojos.append(f"(d) {ACTIVOS[0]} {RUTA_ULTIMO}: {malos[0]}" + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else ""))
        elif not casados:
            nomed.append(f"(d) {RUTA_ULTIMO}: ningun venue trajo el mismo aviso al paso base y al guardado")
        else:
            info.append(f"(d) {ACTIVOS[0]} {RUTA_ULTIMO}: {n} venues; en {casados} con el mismo aviso, la escalera al paso "
                        f"{texto(grueso)} == la del paso {texto(base)} reagregada")

    def retiene() -> None:
        hoy = ahora.date()
        e = una(db, f"""
            SELECT (SELECT count(*) FROM libro_foto WHERE ts < '{_ts(ahora - timedelta(days=dec['dias']) - GRACIA)}'),
                   (SELECT count(*) FROM libro_cobertura WHERE segundos = 60
                       AND ts < '{_ts(ahora - timedelta(days=dec['dias']) - GRACIA)}'),
                   (to_regclass('libro_foto_p{hoy:%Y%m%d}') IS NOT NULL
                    AND to_regclass('libro_foto_p{hoy + timedelta(days=1):%Y%m%d}') IS NOT NULL)::int,
                   (SELECT count(*) FROM pg_proc WHERE proname IN ('ensure_temporal_partitions',
                                                                   'drop_expired_temporal_partitions')
                       AND position('''libro_foto''' in pg_get_functiondef(oid)) > 0)""")
        for n, nombre in zip(e[:2], ("fotos", "minutos completos de cobertura"), strict=True):
            if int(n):
                rojos.append(f"(e) {n} {nombre} mas viejos que su retencion ({dec['dias']} d + {GRACIA})")
        if e[2] != "1":
            rojos.append(f"(e) faltan particiones de hoy o de manana ({hoy} UTC) para libro_foto")
        if e[3] != "2":
            rojos.append(f"(e) las funciones vivas de particion no gestionan libro_foto ({e[3]} de 2)")
        info.append(f"(e) retencion {dec['dias']} d; particiones de hoy y manana; funciones vivas: {e[3]} de 2")

    for letra, brazo in (("a", valido), ("b", triangula), ("c", cubre), ("d", servido), ("e", retiene)):
        try:
            brazo()
        except Canal as exc:
            nomed.append(f"({letra}) NO MEDIDO (CANAL): {exc}")
        except (ArithmeticError, KeyError, ValueError, TypeError, IndexError) as exc:
            nomed.append(f"({letra}) NO MEDIDO: el recalculo de {brazo.__name__} no pudo con lo que hay "
                         f"({type(exc).__name__}: {str(exc)[:120]})")

    if rojos:
        print(f"ROJO  K110 {rojos[0][:240]}")
        for r in rojos[1:]:
            print(f"   - {r}")
    elif nomed:
        print(f"NO MEDIDO: K110 {nomed[0][:240]}")
    else:
        print(f"VERDE  K110 · el libro: {len(VENUES)} venues, fotos validas, triangulado, cubierto sin rellenar, "
              "servido = guardado y retenido")
    for n in nomed[1 if not rojos else 0:]:
        print(f"   ? {n}")
    for i in info:
        print(f"   · {i}")
    return 1 if rojos else (2 if nomed else 0)


def juzga_fotos(db: str, activo: str, q: dict, sv: dict) -> list[str]:
    paso = Decimal(q["paso"])
    if Decimal(sv.get("paso", "-1")) != paso:
        return [f"paso servido {sv.get('paso')} != pedido {q['paso']}"]
    hora = """'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'"""
    filas = sql(db, f"""SELECT to_char(ts AT TIME ZONE 'UTC', {hora}), venue, to_char(ts_libro AT TIME ZONE 'UTC', {hora}),
                               compra, venta, paso, compra_nivel, array_to_string(compras, ','), venta_nivel,
                               array_to_string(ventas, ','), alcance_compra, alcance_venta
                          FROM libro_foto WHERE symbol = '{activo}' AND ts >= '{_ts(_dt(q['desde']))}'
                           AND ts < '{_ts(_dt(q['hasta']))}' AND extract(epoch FROM ts)::bigint % {q['cada']} = 0
                         ORDER BY ts, venue""")
    mias = []
    for ts, venue, ts_libro, compra, venta, fino, cn, cs, vn, vs, ac, av in filas:
        fino = Decimal(fino)
        c = reagrega(Decimal(cn), [Decimal(x) for x in cs.split(",")], fino, paso, True)
        v = reagrega(Decimal(vn), [Decimal(x) for x in vs.split(",")], fino, paso, False)
        mias.append({"ts": ts, "venue": venue, "ts_libro": ts_libro, "compra": texto(Decimal(compra)),
                     "venta": texto(Decimal(venta)),
                     "compras": {"desde": texto(c[0]), "cantidades": [texto(x) for x in c[1]]} if c else None,
                     "ventas": {"desde": texto(v[0]), "cantidades": [texto(x) for x in v[1]]} if v else None,
                     "alcance": {"compra": texto(Decimal(ac)), "venta": texto(Decimal(av))}})
    servidas = [{k: f.get(k) for k in ("ts", "venue", "ts_libro", "compra", "venta", "compras", "ventas", "alcance")}
                for f in sv.get("fotos") or []]
    if len(servidas) != len(mias):
        return [f"{len(servidas)} fotos servidas != {len(mias)} guardadas"]
    for s, m in zip(servidas, mias, strict=True):
        if s != m:
            campo = next(k for k in m if s.get(k) != m[k])
            return [f"foto {m['ts']} {m['venue']}: {campo} servido {str(s.get(campo))[:80]} != guardado "
                    f"{str(m[campo])[:80]}"]
    return []


def juzga_cobertura(db: str, activo: str, q: dict, sv: dict) -> list[str]:
    filas = {f[0]: f[1:] for f in sql(db, f"""
        SELECT venue, count(*), count(*) FILTER (WHERE segundos = 60), sum(segundos), sum(fotos), sum(saltos)
          FROM libro_cobertura WHERE symbol = '{activo}' AND ts >= '{_ts(_dt(q['desde']))}'
           AND ts < '{_ts(_dt(q['hasta']))}' GROUP BY venue""")}
    malos = []
    for x in sv.get("venues") or []:
        mia = [int(n) for n in filas.get(x["venue"], ("0",) * 5)]
        suya = [x.get(k) for k in ("filas", "completos", "segundos", "fotos", "saltos")]
        if mia != suya:
            malos.append(f"cobertura {x['venue']}: servida {suya} != guardada {mia}")
    if len(sv.get("venues") or []) != len(VENUES):
        malos.append(f"{len(sv.get('venues') or [])} venues servidos de {len(VENUES)}")
    return malos


async def sirve_ultimo(directorio: str, pool, api_mod) -> None:
    """OF-4b: los ultimos avisos que el colector del ARBOL publico al reproducir la grabacion (K110-reproduce.py), dados
    al relevo de la API del arbol como si llegaran por NOTIFY, y lo que su ruta /api/libro/ultimo sirve con ellos."""
    import asyncio
    import importlib.util

    from app import libro_lectura as lec

    spec = importlib.util.spec_from_file_location("k110_reproduce", Path(__file__).resolve().parent / "K110-reproduce.py")
    rep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rep)
    ultimos = await rep.reproduce("-", os.environ["K110_FLUJO"], "")
    lec.RELEVO.tarea = asyncio.get_running_loop().create_future()  # sin escucha de verdad: los avisos se dan a mano
    for carga in ultimos.values():
        lec.RELEVO._aviso(None, 0, "libro", carga)
    async with pool.acquire() as c:
        base = Decimal(await c.fetchval("SELECT paso::text FROM orderflow_paso WHERE symbol = $1", ACTIVOS[0]))
    for url in peticiones_ultimo(base, declarado(arbol=True)["pasos"][ACTIVOS[0]]):
        q = dict(urllib.parse.parse_qsl(url.split("?", 1)[1]))
        resp = await api_mod.libro_ultimo(_Peticion(**q), **q)
        fichero_servido(directorio, url).write_text(json.dumps(resp, default=str))


class _Peticion:
    def __init__(self, **q):
        self.query_params = q


def sirve(directorio: str) -> int:
    """Lo que serviria el ARBOL para las peticiones de (d), con las rutas de verdad de app/api.py sobre K110_BASE. Es
    lo que el control usa como «lo servido» y lo que planta torcido."""
    import asyncio

    import asyncpg

    sys.path.insert(0, REPO)
    import app.api as api_mod

    async def corre():
        pool = await asyncpg.create_pool(BASE, min_size=1, max_size=2, server_settings={"timezone": "UTC"})
        api_mod.app.state.pool = pool
        try:
            ahora = datetime.fromisoformat(RELOJ)
            async with pool.acquire() as c:
                primero = await c.fetchval("SELECT min(ts) FROM libro_cobertura")
            fin = ahora.replace(second=0, microsecond=0) - timedelta(minutes=2)
            hasta_d, desde_d = ventana_d(fin, primero)
            for _activo, nombre, q in peticiones_d(desde_d, hasta_d, declarado(arbol=True)["pasos"]):
                f = api_mod.libro_fotos if nombre == "fotos" else api_mod.libro_cobertura
                kw = {k: (int(v) if k == "cada" else v) for k, v in q.items()}
                resp = await f(_Peticion(**q), **kw)
                ruta = f"/api/libro/{nombre}?{urllib.parse.urlencode(q)}"
                fichero_servido(directorio, ruta).write_text(json.dumps(resp, default=str))
            if os.environ.get("K110_FLUJO"):
                await sirve_ultimo(directorio, pool, api_mod)
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
    print("NO MEDIDO: uso K110-libro.py juzga | sirve <dir>")
    sys.exit(2)
