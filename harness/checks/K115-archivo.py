"""K115 · EL ARCHIVO · campana 147. Juzga el MANIFIESTO del archivo del nodo contra la base.

El archivador del nodo (tools/archivo/archiva.sh) guarda cada hora cerrada de ocho tablas finas en /mnt/archivo y
deja una linea por hora en su MANIFIESTO (tabla, hora, filas, bytes, sha256, escrito), que copia a 140 al acabar cada
pase. Desde 143 no se ve el nodo: se lee esa copia por bin/prod y la base por bin/prodsql.

  (a) ninguna hora que la base aun tiene, cerrada hace mas de 75 min, falta en el manifiesto;
  (b) las filas de cada linea == count(*) de su hora en la base, mientras la base tenga la hora entera;
  (c) el archivador vive: la ultima linea de la copia de 140 se escribio hace menos de 75 min;
  (d) la continuidad: ninguna hora desde la primera archivada (NACE, declarada) que la base ya no tiene falta.

QUE HORAS TIENE LA BASE. La ventana de retencion de 140 (config.py del release, pisada por coinalyze.env) dice desde
donde la base tiene las horas ENTERAS; dentro de ella se cuenta hora a hora y la primera hora con filas es el borde
que la poda recorta, asi que (b) empieza en la siguiente. Ese suelo sale del dato A PROPOSITO: con la retencion de
DECIDE alargada en el entorno, la base tarda 30 dias en llenarse, y una hora que la base ya no tiene no es un fallo
del archivo sino de la base (K18/K104). Una hora sin linea antes de ese suelo es (d), despues es (a).

Una consulta por hora y tabla, en autocommit y con lock_timeout de 1 s: ninguna se acerca a los 3 s de lock_timeout
del mantenimiento de particiones (app/db.py). La cinta no tiene indice que empiece por ts y contar una hora barria la
particion del dia (1287 ms, 2026-10-18): va por (symbol, ts DESC) con symbol = ANY(...) (363-752 ms). En produccion
no cuenta en los minutos :00-:02 (el ciclo de coinalyze-daily es a los :01).

  K115-archivo.py                       sujeto por entorno: K115_SUJETO=produccion (K115_HARNESS) o local
                                        (K115_MANIFIESTO fichero, K115_BASE dsn de psql, K115_AHORA, K115_REPO)
rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

MANIFIESTO_140 = "/var/lib/coinalyze/archivo/MANIFIESTO.tsv"
# tabla: (variable de retencion, horas por unidad, contar por (symbol, ts) en vez de por ts)
TABLAS = {
    "orderflow_cinta": ("ORDERFLOW_TAPE_RETENTION_HOURS", 1, True),
    "libro_foto": ("LIBRO_RETENTION_DAYS", 24, False),
    "orderflow_celda": ("ORDERFLOW_CELL_RETENTION_DAYS", 24, False),
    "scalp_signal_snapshot": ("SCALP_SIGNAL_RETENTION_HOURS", 1, False),
    "futures_trades_realtime": ("SCALP_TRADE_RETENTION_HOURS", 1, False),
    "orderbook_snapshot": ("SCALP_ORDERBOOK_RETENTION_HOURS", 1, False),
    "libro_cobertura": ("LIBRO_RETENTION_DAYS", 24, False),
    "orderflow_cobertura": ("ORDERFLOW_CELL_RETENTION_DAYS", 24, False),
}
# La primera hora archivada de cada tabla, DECLARADA: la copia de 140 a las 2026-10-18T21:36Z (x1-tmp/c147/p2.out).
# Un manifiesto que pierde su cabeza no mueve este suelo: es (d).
NACE = {
    "orderflow_cinta": "2026-10-17T07:00:00Z",
    "libro_foto": "2026-10-18T03:00:00Z",
    "orderflow_celda": "2026-10-17T07:00:00Z",
    "scalp_signal_snapshot": "2026-10-15T19:00:00Z",
    "futures_trades_realtime": "2026-10-18T07:00:00Z",
    "orderbook_snapshot": "2026-10-18T13:00:00Z",
    "libro_cobertura": "2026-10-18T03:00:00Z",
    "orderflow_cobertura": "2026-10-17T07:00:00Z",
}
H1 = dt.timedelta(hours=1)
EXIGIBLE = dt.timedelta(minutes=75)  # (a) desde el cierre de la hora, (c) desde la ultima linea
CERRADA = dt.timedelta(minutes=10)  # archiva.sh solo toma horas cerradas hace >= 10 min
LOTE = 40_000  # bytes de SQL por llamada: bin/prodsql la pasa por la linea de ssh, en base64 dos veces


class Canal(Exception):
    pass


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def lee(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)


def techo(t: dt.datetime) -> dt.datetime:
    h = t.replace(minute=0, second=0, microsecond=0)
    return h if h == t else h + H1


class Sujeto:
    def __init__(self) -> None:
        self.prod = os.environ.get("K115_SUJETO", "produccion") == "produccion"
        self.b = os.environ.get("K115_HARNESS", "/srv/coinanalyze/harness")
        self.repo = Path(os.environ.get("K115_REPO", "/srv/coinanalyze/repo"))

    def _corre(self, args: list[str], entrada: str | None = None) -> str:
        try:
            r = subprocess.run(args, input=entrada, capture_output=True, text=True, timeout=300,
                               env={**os.environ, "TODO": "1"})
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Canal(f"{args[0]}: {exc}") from exc
        if r.returncode != 0:
            raise Canal(f"{' '.join(args[:2])[:60]} rc={r.returncode}: {r.stderr.strip()[:160]}")
        return r.stdout

    def manifiesto(self) -> tuple[str | None, str]:
        """(texto o None si no existe, origen). En produccion entre cabecera y cierre: bin/prod mezcla stderr y su rc es 0."""
        if not self.prod:
            f = os.environ.get("K115_MANIFIESTO", "")
            return (Path(f).read_text() if f and Path(f).is_file() else None), f"local {f}"
        out = self._corre(["sh", f"{self.b}/bin/prod",
                           f"if [ -r {MANIFIESTO_140} ]; then echo MANIFIESTO $(stat -c %Y {MANIFIESTO_140}); "
                           f"cat {MANIFIESTO_140}; echo FIN-MANIFIESTO; else echo SIN-MANIFIESTO; fi"])
        lineas = out.split("\n")
        if lineas and lineas[0] == "SIN-MANIFIESTO":
            return None, f"140:{MANIFIESTO_140}"
        if not re.fullmatch(r"MANIFIESTO \d+", lineas[0] if lineas else "") or "FIN-MANIFIESTO" not in lineas:
            raise Canal(f"bin/prod no devolvio el manifiesto entero: {out[:160]!r}")
        mtime = dt.datetime.fromtimestamp(int(lineas[0].split()[1]), dt.UTC)
        cuerpo = "\n".join(lineas[1:lineas.index("FIN-MANIFIESTO")]) + "\n"
        return cuerpo, f"140:{MANIFIESTO_140} (mtime {iso(mtime)})"

    def retencion(self) -> dict[str, int]:
        """Horas de retencion por tabla: el config.py del sujeto, pisado por su entorno (en produccion)."""
        nombres = "|".join(sorted({v for v, _, _ in TABLAS.values()}))
        if self.prod:
            texto = self._corre(["sh", f"{self.b}/bin/prod", f"grep -hoE '({nombres})(: int = Field\\(default=|=)[0-9]+' "
                                 "/opt/coinalyze/current/app/config.py /etc/coinalyze/coinalyze.env"])
        else:
            texto = (self.repo / "app/config.py").read_text()
        val = {n: int(x) for n, x in re.findall(rf"\b({nombres})(?:: int = Field\(default=|=)(\d+)", texto)}
        falta = [v for v, _, _ in TABLAS.values() if v not in val]
        if falta:
            raise Canal(f"no se pudo leer la retencion {falta[0]}")
        return {t: val[v] * k for t, (v, k, _) in TABLAS.items()}

    def sql(self, q: str) -> list[list[str]]:
        q = "SET lock_timeout = '1s';\n" + q
        if self.prod:
            out = self._corre(["sh", f"{self.b}/bin/prodsql", q])
        else:
            out = self._corre(["psql", os.environ.get("K115_BASE", ""), "-X", "-A", "-F|", "-t", "-q",
                               "-v", "ON_ERROR_STOP=1", "-f", "-"], entrada=q)
        return [x.split("|") for x in out.splitlines() if x.strip()]


def parsea(texto: str) -> tuple[dict[tuple[str, str], tuple[int, dt.datetime]], list[str]]:
    lineas = texto.rstrip("\n").split("\n")
    malas, vistas = [], Counter()
    m: dict[tuple[str, str], tuple[int, dt.datetime]] = {}
    if lineas[0].split("\t") != ["tabla", "hora", "filas", "bytes", "sha256", "escrito"]:
        malas.append(f"cabecera: {lineas[0][:80]!r}")
    for i, li in enumerate(lineas[1:], 2):
        c = li.split("\t")
        try:
            assert len(c) == 6 and re.fullmatch(r"[0-9a-f]{64}", c[4])
            lee(c[1])
            m[(c[0], c[1])] = (int(c[2]), lee(c[5]))
            vistas[(c[0], c[1])] += 1
        except (AssertionError, ValueError):
            malas.append(f"linea {i}: {li[:80]!r}")
    malas += [f"{t} {h} esta {n} veces" for (t, h), n in sorted(vistas.items()) if n > 1]
    return m, malas


def juzga() -> int:
    s = Sujeto()
    try:
        texto, origen = s.manifiesto()
    except (Canal, OSError) as exc:
        print(f"NO MEDIDO (CANAL): K115 no pudo leer el manifiesto: {exc}")
        return 2
    if not texto or not texto.strip():
        print(f"NO MEDIDO: K115 no hay manifiesto del archivo en {origen}")
        return 2
    m, malas = parsea(texto)
    try:
        ret = s.retencion()
        if s.prod:
            while dt.datetime.now(dt.UTC).minute in (0, 1, 2):  # lejos del ciclo de coinalyze-daily (:01)
                time.sleep(20)
        cab = s.sql("SELECT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"');\n"
                    "WITH RECURSIVE x AS (SELECT min(symbol) AS s FROM orderflow_cinta UNION ALL "
                    "SELECT (SELECT min(symbol) FROM orderflow_cinta WHERE symbol > x.s) FROM x WHERE x.s IS NOT NULL) "
                    "SELECT coalesce(string_agg(s, ','), '') FROM x WHERE s IS NOT NULL;")
        ahora = lee(os.environ["K115_AHORA"]) if os.environ.get("K115_AHORA") else lee(cab[0][0])
        simbolos = cab[1][0] if len(cab) > 1 and cab[1] else ""
        # las horas que la base puede tener enteras: desde su ventana de retencion (o la primera archivada) hasta la
        # ultima cerrada hace >= 10 min
        ultima = (ahora - CERRADA).replace(minute=0, second=0, microsecond=0) - H1
        cuenta, sentencias = {}, []
        for t, (_, _, por_simbolo) in TABLAS.items():
            h = max(lee(NACE[t]), techo(ahora - dt.timedelta(hours=ret[t])))
            while h <= ultima:
                filtro = f"symbol = ANY('{{{simbolos}}}'::text[]) AND " if por_simbolo else ""
                sentencias.append(f"SELECT '{t}', '{iso(h)}', count(*) FROM {t} WHERE {filtro}"
                                  f"ts >= '{iso(h)}' AND ts < timestamptz '{iso(h)}' + interval '1 hour';")
                h += H1
        lote: list[str] = []
        for q in [*sentencias, None]:
            if q is None or sum(map(len, lote)) + len(q) > LOTE:
                for t, h, n in s.sql("\n".join(lote)) if lote else []:
                    cuenta[(t, h)] = int(n)
                lote = []
            if q is not None:
                lote.append(q)
        if len(cuenta) != len(sentencias):
            raise Canal(f"la base devolvio {len(cuenta)} cuentas de {len(sentencias)} horas")
    except (Canal, ValueError, IndexError) as exc:
        print(f"NO MEDIDO (CANAL): K115 {exc}")
        return 2

    rojos, info, sin_juzgar = [f"manifiesto ilegible: {x}" for x in malas], [], []
    if not m and not malas:
        print(f"NO MEDIDO: K115 el manifiesto de {origen} no trae ninguna linea")
        return 2
    for t in TABLAS:
        con_filas = sorted(h for (tt, h), n in cuenta.items() if tt == t and n > 0)
        # la primera hora con filas es el borde que la poda recorta: (b) empieza en la siguiente
        borde = lee(con_filas[0]) if con_filas else None
        comparadas = 0
        h = lee(NACE[t])
        while h <= ultima:
            k = (t, iso(h))
            n_base = cuenta.get(k)
            if k in m:
                if n_base is not None and borde is not None and h > borde:
                    comparadas += 1
                    if m[k][0] != n_base:
                        rojos.append(f"(b) {t} {iso(h)}: el manifiesto dice {m[k][0]} filas y la base tiene {n_base}")
            elif h + H1 + EXIGIBLE <= ahora:
                if n_base is not None and borde is not None and h >= borde:
                    rojos.append(f"(a) {t} {iso(h)}: cerro hace {int((ahora - h - H1).total_seconds() // 60)} min y "
                                 f"no esta en el manifiesto; la base aun la tiene ({n_base} filas)")
                else:
                    rojos.append(f"(d) {t} {iso(h)}: la base ya no la tiene y no esta en el manifiesto: perdida")
            h += H1
        if comparadas == 0:
            sin_juzgar.append(t)
        info.append(f"{t}: {sum(1 for (tt, _) in m if tt == t)} lineas desde {NACE[t]}, {comparadas} horas contadas "
                    f"contra la base (retencion {ret[t]} h, borde {iso(borde) if borde else '-'})")
    if not m:
        print(f"ROJO  K115 {rojos[0][:200]}")
        return 1
    ultima_escrita = max(e for _, e in m.values())
    hace = int((ahora - ultima_escrita).total_seconds() // 60)
    if ahora - ultima_escrita > EXIGIBLE:
        rojos.append(f"(c) la ultima linea del manifiesto se escribio a las {iso(ultima_escrita)}, hace {hace} min: "
                     "el archivador esta parado o no copia el manifiesto a 140")
    otras = sorted({t for (t, _) in m} - set(TABLAS))
    if otras:
        info.append(f"tablas del manifiesto que K115 no juzga: {', '.join(otras)}")
    info.append(f"manifiesto {origen}: {len(m)} lineas, la ultima escrita hace {hace} min; ahora {iso(ahora)}; "
                f"{len(cuenta)} horas contadas en la base")
    if rojos:
        print(f"ROJO  K115 {rojos[0][:200]}")
        for r in rojos[1:30]:
            print(f"   - {r}")
        if len(rojos) > 30:
            print(f"   - y {len(rojos) - 30} mas")
    elif sin_juzgar:
        # una base que no devuelve ninguna hora entera no absuelve (b): seria un VERDE sin sujeto
        print(f"NO MEDIDO: K115 (b) sin juzgar: la base no tiene ninguna hora entera archivada de {', '.join(sin_juzgar)}")
    else:
        print(f"VERDE  K115 · el archivo: {len(TABLAS)} tablas, ninguna hora sin archivar, las filas cuadran con la "
              f"base y el archivador escribio hace {hace} min")
    for i in info:
        print(f"   · {i}")
    return 1 if rojos else (2 if sin_juzgar else 0)


if __name__ == "__main__":
    sys.exit(juzga())
