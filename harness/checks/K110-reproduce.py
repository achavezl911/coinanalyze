"""K110-control · reproduce una grabacion REAL de los flujos de libro (K110-flujo.jsonl.xz) por el codigo REAL del
colector del arbol (app/libro.py: procesa, Libro, fotografia, vuelca, carga_relevo) con el reloj de la grabacion, y lo
escribe en una base. Es el sujeto del control: lo que el servicio habria guardado con esos mensajes. Las fotos REST de
Binance son las grabadas: la que se pide en t es la primera grabada despues de t. Solo se montan los libros de los
venues que trae la grabacion.

Con --planta se reproduce con UN defecto inyectado en el proceso (el arbol no se toca):
  salto_no_detectado   un hueco de 4 s de mensajes de binance_usdm y bybit_linear que el colector NO detecta: aplica lo
                       que llega como si fuera seguido, y no se fia de un libro cruzado (lo sigue fotografiando)
  foto_fuera_de_banda  la foto guarda el doble de niveles de la banda
  cobertura_rellena    un hueco de 4 s en bybit_linear que el colector SI detecta, pero cuenta como cubierto el tiempo
                       sin libro valido

Uso: K110-reproduce.py <dsn|-> <flujo.jsonl.xz|.gz> [--planta X]   (con `-` no escribe: solo cuenta)
"""

from __future__ import annotations

import asyncio
import gzip
import json
import lzma
import sys
import time
from collections import defaultdict
from decimal import Decimal

import asyncpg

import app.libro as lb


class _Una:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_):
        return False


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Una(self.conn)


HUECO = {}  # planta salto_no_detectado: venue -> (desde_rx_ms, hasta_rx_ms) de mensajes que se tiran
ALIAS = {"coinbase_advanced": "coinbase_spot"}  # el nombre que el grabador de P1 le daba a la conexion de Coinbase
BASES = {"BTC": Decimal("1"), "ETH": Decimal("0.1"), "SOL": Decimal("0.01")}  # orderflow_paso (OF-1)


def planta(nombre: str, lineas: list[dict]) -> None:
    if nombre == "salto_no_detectado":
        # Un hueco de 4 s a mitad de la grabacion en los dos venues que K110 (b) triangula; el colector plantado aplica
        # lo que llega como si fuera seguido y no invalida un libro cruzado.
        mitad = lineas[len(lineas) // 2]["rx"]
        for v in ("binance_usdm", "bybit_linear"):
            HUECO[v] = (mitad, mitad + 4000)

        def sin_numeracion(v, libros, msg, ahora, original=lb.binance):
            x = msg.get("data") or {}
            activo = next((a for a, i in v.instrumentos.items() if i == x.get("s")), None)
            if activo is not None and libros[activo].valido:
                lb._binance_aplica(libros[activo], x, int(ahora * 1000))
                return [libros[activo]]
            return original(v, libros, msg, ahora)

        def bybit_seguido(v, libros, msg, ahora, original=lb.bybit):
            x = msg.get("data") or {}
            if msg.get("type") == "delta":
                activo = next((a for a, i in v.instrumentos.items() if i == str(msg.get("topic", "")).rsplit(".", 1)[-1]),
                              None)
                if activo is not None and libros[activo].valido:
                    libros[activo].seq = int(x["u"]) - 1  # el salto no se ve
            return original(v, libros, msg, ahora)

        lb.binance, lb.bybit = sin_numeracion, bybit_seguido
        lb.Libro.comprueba = lambda self, ahora: None
    elif nombre == "foto_fuera_de_banda":
        lb.BANDA = {a: 2 * n for a, n in lb.BANDA.items()}
    elif nombre == "cobertura_rellena":
        # Un hueco real en bybit_linear, que el colector SI detecta (el libro deja de ser valido y, sin foto nueva en la
        # grabacion, ya no vuelve); el defecto es contar como cubierto el tiempo sin libro valido.
        mitad = lineas[len(lineas) // 2]["rx"]
        HUECO["bybit_linear"] = (mitad, mitad + 4000)
        original = lb.Libro.invalida

        def rellena(self, ahora, motivo, evidencia):
            original(self, ahora, motivo, evidencia)
            self.cob.abre(ahora)

        lb.Libro.invalida = rellena
    elif nombre:
        raise SystemExit(f"planta desconocida: {nombre}")


async def reproduce(dsn: str, fichero: str, nombre: str) -> dict:
    """Devuelve el ULTIMO aviso del relevo que el colector publico por libro (venue, activo): lo que la API oiria."""
    with (lzma.open if fichero.endswith(".xz") else gzip.open)(fichero, "rt") as g:
        lineas = [json.loads(x) for x in g]
    lineas.sort(key=lambda d: d["rx"])
    planta(nombre, lineas)
    rest: dict[tuple[str, str], list[tuple[int, dict]]] = defaultdict(list)
    for d in lineas:
        if "rest" in d and d.get("status") == 200 and d["v"] in lb.VENUES and lb.VENUES[d["v"]].rest:
            v = lb.VENUES[d["v"]]
            inst = d["rest"].split("symbol=")[1].split("&")[0]
            activo = next((a for a, i in v.instrumentos.items() if i == inst), None)
            if activo:
                rest[(d["v"], activo)].append((d["rx"], json.loads(d["body"])))
    inicio = lineas[0]["rx"] / 1000
    presentes = {ALIAS.get(d["v"], d["v"]) for d in lineas} & set(lb.VENUES)  # solo los venues de la grabacion
    libros = {v: {a: lb.Libro(v, a) for a in lb.ACTIVOS} for v in lb.VENUES if v in presentes}
    todos = [x for por in libros.values() for x in por.values()]
    alm = lb.Almacen(inicio)
    salud = {"caidas": defaultdict(int), "mal_formados": defaultdict(int), "reconexiones": defaultdict(int),
             "avisos": 0, "avisos_fallidos": 0}
    conexiones = {v: {"seq": None} for v in lb.VENUES}
    pedidas: dict[tuple[str, str], int] = {}
    cargas: list[int] = []
    ultimos: dict[tuple[str, str], str] = {}
    conn = None
    if dsn != "-":
        conn = await asyncpg.connect(dsn, server_settings={"timezone": "UTC"})
        await conn.execute("SELECT ensure_temporal_partitions(to_timestamp($1), 1, 2)", inicio)
    pool = _Pool(conn)
    segundo = int(inicio)
    relevo_t = inicio
    cpu0 = time.process_time()
    mensajes = 0
    try:
        for d in lineas:
            ahora = d["rx"] / 1000
            while segundo < int(ahora):
                segundo += 1
                if segundo % lb.FOTO_S == 0:
                    lb.fotografia(todos, alm, segundo)
                if conn is not None:
                    await lb.vuelca(pool, None, alm, todos, float(segundo), inicio, salud)
            while relevo_t + lb.RELEVO_S <= ahora:
                relevo_t += lb.RELEVO_S
                for x in todos:
                    if x.cambiado:
                        x.cambiado = False
                        aviso = lb.carga_relevo(x, BASES[x.activo], relevo_t)
                        ultimos[(x.venue, x.activo)] = aviso
                        cargas.append(len(aviso.encode()))
            v = lb.VENUES.get(ALIAS.get(d["v"], d["v"]))
            if v is None:
                continue
            if "ev" in d:
                if d["ev"] == "open":
                    salud["reconexiones"][(v.venue, int(ahora) // 60 * 60)] += 1
                elif d["ev"].startswith("close") or d["ev"] == "fin":
                    for x in libros[v.venue].values():
                        if x.valido or x.buffer:
                            x.invalida(ahora, "la conexion se cerro", "disconnect")
                continue
            if "raw" not in d:
                continue
            if v.venue in HUECO and HUECO[v.venue][0] <= d["rx"] < HUECO[v.venue][1]:
                continue
            mensajes += 1
            try:
                lb.procesa(v, libros[v.venue], d["raw"], ahora, conexiones[v.venue])
            except lb.SaltoDeConexion:
                for x in libros[v.venue].values():
                    x.invalida(ahora, "salto de la conexion", "sequence_discontinuity")
            except Exception:  # noqa: BLE001
                salud["mal_formados"][v.venue] += 1
                for x in libros[v.venue].values():
                    if x.valido or x.buffer:
                        x.invalida(ahora, "mensaje que no se entiende", "source_failure")
            if v.rest:  # la foto REST: la primera grabada despues de pedirla
                for x in libros[v.venue].values():
                    clave = (v.venue, x.activo)
                    if not x.valido and x.foto_rest is None and x.buffer:
                        pedidas.setdefault(clave, d["rx"])
                    if clave in pedidas:
                        lista = rest[clave]
                        while lista and lista[0][0] < pedidas[clave]:
                            lista.pop(0)
                        if lista and lista[0][0] <= d["rx"]:
                            del pedidas[clave]
                            x.foto_rest = lista.pop(0)[1]
                            lb.binance_sincroniza(v, x, ahora)
                            x.comprueba(ahora)
        fin = lineas[-1]["rx"] / 1000
        for x in todos:
            if x.valido:
                x.cob.cierra(fin)
        if conn is not None:
            await lb.vuelca(pool, None, alm, todos, fin, inicio, salud, apagando=True)
        cpu = time.process_time() - cpu0
        cargas.sort()
        print(f"reproducido: {mensajes} mensajes en {fin - inicio:.0f} s de grabacion, CPU {cpu:.1f} s "
              f"({cpu / (fin - inicio) * 100:.1f} % de un nucleo); app de {lb.__file__}")
        if cargas:
            print(f"relevo: {len(cargas)} avisos, bytes p50 {cargas[len(cargas) // 2]} p99 "
                  f"{cargas[int(len(cargas) * .99)]} max {cargas[-1]}")
        if conn is not None:
            n = await conn.fetchval("SELECT count(*) FROM libro_foto")
            c = await conn.fetchval("SELECT count(*) FROM libro_cobertura")
            g = await conn.fetchval("SELECT count(*) FROM data_gap WHERE feed = 'libro'")
            print(f"base: {n} fotos, {c} filas de cobertura, {g} huecos declarados")
        else:
            por = defaultdict(int)
            for fs in alm.fotos.values():
                for f in fs:
                    por[(f[1], f[2])] += 1
            print("fotos en memoria por venue/activo:", dict(sorted(por.items())))
            print("invalidaciones por libro:", {f"{x.venue}:{x.activo}": sum(x.resyncs.values())
                                                for x in todos if x.resyncs})
            print("mal formados:", dict(salud["mal_formados"]))
    finally:
        if conn is not None:
            await conn.close()
    return ultimos


if __name__ == "__main__":
    args = sys.argv[1:]
    nombre = ""
    if "--planta" in args:
        i = args.index("--planta")
        nombre = args[i + 1]
        del args[i:i + 2]
    asyncio.run(reproduce(args[0], args[1], nombre))
