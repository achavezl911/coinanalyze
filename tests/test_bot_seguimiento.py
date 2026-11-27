"""SEGUIMIENTO R2: el seguimiento de una posicion abierta con la especificacion MEDIDA de Fable I18 (en sombra).

I18 (entregas/fable/fable-i18, 08-18..11-26, dos mitades y nulo emparejado): ninguna senal da DIRECCION, casi todas anuncian
MAS MOVIMIENTO en 15 min y el precio no respeta ningun nivel mas que una linea al azar. Todo con dobles: minutos sinteticos
de SOL y una posicion CORTO inventada; ni red ni filas del dueno.
"""

from __future__ import annotations

import math

from app.bot import centinela as cen
from app.bot import seguimiento as seg
from app.bot import servicio as sv

M0 = 29_000_000 // 1440 * 1440 + 720  # un mediodia UTC, multiplo de 5: el bloque [M0-5, M0) acaba de cerrar
CORTO = {"clave": "SOLUSDT:Sell", "symbol": "SOLUSDT", "lado": -1, "entrada": 100.5, "marca": 100.0, "stop": 102.5,
         "objetivo": 96.5, "cantidad": 10.0}
LIQ_HIST = [(M0 - 2000 - 5 * k, 1e6, 1e6) for k in range(100)]  # 100 bloques de 1 M$ en 30 d: el p99.5 es 1 M$
GRA_HIST = [(M0 - 3000 - k, "binance_usdm", c, 1e6) for k in range(20) for c in (True, False)]  # p99.9 de 10 d: 1 M$


def velas(ahora: int, cambia: dict | None = None) -> dict:
    """1500 minutos planos en 100 (+-0.1), delta pequeno que alterna; `cambia` pisa minutos: {minuto: (h, l, c, buy, vol)}."""
    out = {}
    for m in range(ahora - 1500, ahora):
        c = 100 + 0.1 * math.sin(m / 7)
        out[m] = (c + 0.05, c - 0.05, c, 480.0 if m % 2 else 520.0, 1000.0)
    out.update(cambia or {})
    return out


def plano(m: int, c: float, buy: float = 500.0) -> tuple:
    return (c + 0.02, c - 0.02, c, buy, 1000.0)


class Base:
    """La base de 140 en dobles: cada SELECT contesta lo que el escenario dice; se cuentan las lecturas. Contesta tambien
    las consultas de R1 (main) para que las pruebas caigan por lo que el codigo viejo HACE, no por un nombre que falta."""

    def __init__(self, ahora: int, **esc):
        self.ahora, self.lecturas, self.eventos = ahora, [], []
        self.esc = {"velas": velas(ahora), "liq5": [], "grandes": [], "rango7": (130.0, 70.0), "perp": [], "cont": [],
                    "oi": [(m, 1e6) for m in range(ahora - 43200, ahora, 5)]} | esc

    def _es(self, sql, nombre):
        return sql is getattr(seg, nombre, object())

    async def fetch(self, sql, *a):
        self.lecturas.append(sql)
        e, v = self.esc, self.esc["velas"]
        if self._es(sql, "SQL_VELAS"):
            return [(m, *x) for m, x in sorted(v.items()) if a[1] <= m < a[2]]
        if self._es(sql, "SQL_RANGO"):
            d = [x for m, x in v.items() if a[1] <= m < a[2]]
            return [(max(x[0] for x in d), min(x[1] for x in d))] if d else [e["rango7"]]
        if self._es(sql, "SQL_OI"):
            return [x for x in e["oi"] if a[1] <= x[0] < a[2]]
        if self._es(sql, "SQL_GRANDES"):
            return [x for x in e["grandes"] if a[1] <= x[0] < a[2]]
        # ---- R2 ----
        if self._es(sql, "SQL_LIQ5"):
            return [x for x in e["liq5"] if a[1] <= x[0] < a[2]]
        if self._es(sql, "SQL_CIERRES5"):
            return [(m, x[2]) for m, x in sorted(v.items()) if m % 5 == 4 and a[1] <= m < a[2]]
        if self._es(sql, "SQL_GRANDES_COLA") or self._es(sql, "SQL_GRANDES_COLA_CONT"):  # perpetuo / contado (R3)
            n: dict = {}
            spot = self._es(sql, "SQL_GRANDES_COLA_CONT")
            for m, venue, compra, usd in e["grandes"]:
                if a[1] <= m < a[2] and venue.endswith("_spot") is spot:
                    n[(m, compra)] = n.get((m, compra), 0.0) + usd
            return [(m, c, s) for (m, c), s in n.items()]
        if self._es(sql, "SQL_FLUJO_PERP") or self._es(sql, "SQL_FLUJO_CONT"):
            filas = e["perp"] if self._es(sql, "SQL_FLUJO_PERP") else e["cont"]
            return [x for x in filas if a[1] <= x[0] < a[2]]
        if self._es(sql, "SQL_DELTA_OHLCV"):
            n = {}
            for m, x in v.items():
                if a[1] <= m < a[2]:
                    n[m // 5 * 5] = n.get(m // 5 * 5, 0.0) + (2 * x[3] - x[4]) * x[2]
            return sorted(n.items())
        # ---- R1 (main): liquidations_realtime por minuto y lado, y su cola ----
        if self._es(sql, "SQL_LIQ"):
            return [(b, lado, x) for b, lg, sh in e["liq5"] if a[1] <= b < a[2] for lado, x in (("long", lg), ("short", sh)) if x]
        if self._es(sql, "SQL_LIQ_COLA"):
            return [("long", 1e6), ("short", 1e6)]
        raise AssertionError(f"consulta sin doble: {sql[:80]}")

    async def execute(self, sql, *a):
        self.eventos.append((sql, a))


async def tic(base: Base, estado: dict, cache: dict, minuto: int, posiciones=(CORTO,)) -> list[dict]:
    base.ahora = minuto
    return await seg.tic(base, list(posiciones), estado, cache, minuto * 60 + 20)


def mensajes(evs: list[dict]) -> list[dict]:
    """Lo que llegaria al dueno: todo lo que no es solo registro."""
    return [x for x in evs if x["tipo"] != "registro"]


def registro(evs: list[dict]) -> set:
    return {x.get("senal") for x in evs if x["tipo"] == "registro"}


def textos(evs: list[dict]) -> str:
    return "\n".join(x["texto"] for x in mensajes(evs))


# ---------- (a) OI: el cambio se mide NETO del precio ----------
async def test_a_un_oi_que_solo_sube_por_el_precio_no_es_entran_largos():
    cambia = {M0 - 6: plano(M0 - 6, 100.0)} | {m: plano(m, 100.5) for m in range(M0 - 5, M0)}  # el precio +0.5 % en el bloque
    oi = [(m, 1e6) for m in range(M0 - 43200, M0 - 5, 5)] + [(M0 - 5, 1.005e6)]  # oi_close en USD: +0.5 % por el precio
    ev = await tic(Base(M0, velas=velas(M0, cambia), oi=oi), seg.nuevo(), {}, M0)
    t = textos(ev)
    assert "entran largos" not in t and "interes abierto" not in t, t


async def test_a_bis_oi_neto_del_precio_da_el_estado_por_los_dos_signos():
    cambia = {M0 - 6: plano(M0 - 6, 100.0)} | {m: plano(m, 99.95) for m in range(M0 - 5, M0)}
    oi = [(m, 1e6) for m in range(M0 - 43200, M0 - 5, 5)] + [(M0 - 5, 1.01e6)]
    t = textos(await tic(Base(M0, velas=velas(M0, cambia), oi=oi), seg.nuevo(), {}, M0))
    assert "el interes abierto sube" in t and "precio bajando: entran cortos" in t and "sin lado medido" in t, t
    # AVISOS R1 (H2): el lado de la senal respecto de la posicion no se dice; I18 lo midio NULO
    assert "A FAVOR" not in t and "EN CONTRA" not in t, t


# ---------- (b) liq5m y oi5m: el bloque cuenta cuando ha CERRADO ----------
async def test_b_un_bloque_de_5_min_abierto_no_cuenta_y_al_cerrar_si():
    liq = LIQ_HIST + [(M0, 1.5e6, 0.0)]  # ts de APERTURA M0: el bloque se conoce a M0+5
    b, estado, cache = Base(M0 + 3, liq5=liq), seg.nuevo(), {}
    assert "liquid" not in textos(await tic(b, estado, cache, M0 + 3))
    t = textos(await tic(b, estado, cache, M0 + 5))
    assert "1.50 M$ de largos liquidados en 5 min" in t, t


async def test_b_bis_el_oi_del_bloque_abierto_no_cuenta():
    oi = [(m, 1e6) for m in range(M0 - 43200, M0, 5)] + [(M0, 1.05e6)]
    # el bloque cerrado, sin cambio de OI ni de precio; el abierto [M0, M0+5), con el precio y el OI subiendo (main lo avisa)
    quieto = velas(M0 + 3, {m: plano(m, 100.0) for m in range(M0 - 15, M0)} | {m: plano(m, 100.3) for m in range(M0, M0 + 3)})
    t = textos(await tic(Base(M0 + 3, oi=oi, velas=quieto), seg.nuevo(), {}, M0 + 3))
    assert "interes abierto" not in t, t


# ---------- (c) el exchange `combined` no se suma con los demas ----------
async def test_c_div_no_suma_combined_con_binance_y_bybit():
    hist_c = [(M0 - 1000 - 5 * k, "binance", 1e5 if k % 2 else -1e5) for k in range(60)]
    hist_p = [(M0 - 1000 - 5 * k, "binance", 1e5 if k % 2 else -1e5) for k in range(60)]
    cont = hist_c + [(M0 - 5, "binance", 3e5), (M0 - 5, "bybit", 2e5), (M0 - 5, "combined", 5e5)]
    perp = hist_p + [(M0 - 5, "binance", -4e5), (M0 - 5, "combined", -4e5)]
    t = textos(await tic(Base(M0, cont=cont, perp=perp), seg.nuevo(), {}, M0))
    assert "el contado compra 0.50 M$ en 5 min y el perpetuo hace lo contrario (0.40 M$)" in t, t


# ---------- (d) absorcion, grandes de contado y rango de 4 h: solo registro ----------
async def test_d_absorcion_no_avisa_solo_registro():  # la grande de contado (CONT), en test_bot_seguimiento_r3.py
    cambia = {m: (100.05, 99.95, 100.0, 900.0 if m >= M0 - 5 else 500.0, 1000.0) for m in range(M0 - 6, M0)}  # precio quieto
    b = Base(M0, velas=velas(M0, cambia), grandes=[(M0 - 1, "coinbase_spot", False, 1.2e6)])
    ev = await tic(b, seg.nuevo(), {}, M0)
    t = textos(ev)
    assert "absorcion" not in t and "contado" not in t, t
    assert "ABS" in registro(ev), ev


async def test_d_bis_ruptura_del_rango_de_4_h_solo_registro():
    # el rango de [i-240, i-30) se estrecha a 100 +-0.02; las 24 h siguen con su maximo en ~100.15 y el cierre queda debajo
    cambia = {m: plano(m, 100.0) for m in range(M0 - 240, M0 - 5)} | {m: plano(m, 100.11) for m in range(M0 - 5, M0)}
    oi = [(m, 1e6) for m in range(M0 - 43200, M0 - 5, 5)] + [(M0 - 5, 1.0011e6)]  # oi en USD sigue al precio: dOI ~ 0
    ev = await tic(Base(M0, velas=velas(M0, cambia), oi=oi), seg.nuevo(), {}, M0)
    assert "RNG4" in registro(ev), ev
    assert not mensajes(ev), ev


# ---------- (e) ningun texto dice soporte ni resistencia ----------
async def test_e_ningun_texto_dice_soporte_ni_resistencia_y_el_nivel_cerca_va_de_contexto():
    liq = LIQ_HIST + [(M0 - 5, 1.5e6, 0.0)]
    rompe = {m: plano(m, 101.0) for m in range(M0 - 5, M0)}
    todo = ""
    for b in (Base(M0), Base(M0, liq5=liq), Base(M0, velas=velas(M0, rompe))):
        todo += textos(await tic(b, seg.nuevo(), {}, M0)) + "\n"
    assert "soporte" not in todo.lower() and "resistencia" not in todo.lower(), todo
    arriba = velas(M0, {m: plano(m, 100.1) for m in range(M0 - 5, M0)})
    t = textos(await tic(Base(M0, liq5=liq, velas=arriba), seg.nuevo(), {}, M0))
    # el maximo (~100.15, el mismo en 7 d, 24 h y ayer: se nombra el mas ancho) a <= 0.5 ATR: linea de contexto, no aviso
    assert "Contexto: Maximo de 7 dias en 100.15, a " in t and t.count("seguimiento de tu") == 1, t
    assert len(mensajes(await tic(Base(M0), seg.nuevo(), {}, M0))) == 0  # el nivel cerca solo, sin aviso


# ---------- (f) AVISOS R1 (H4): un aviso sale en el tic en que nace; tras un mensaje del activo, espera a sus 10 min ----------
async def test_f_un_aviso_a_los_2_min_de_un_mensaje_sale_a_los_10():
    liq = LIQ_HIST + [(M0 - 5, 1.5e6, 0.0)]
    b = Base(M0, liq5=liq, grandes=GRA_HIST + [(M0 - 1, "binance_usdm", True, 2e6)])
    estado, cache = seg.nuevo(), {}
    ev = mensajes(await tic(b, estado, cache, M0))
    assert len(ev) == 1 and ev[0]["activo"] == "SOL", ev
    assert "liquidados" in ev[0]["texto"] and "operaciones grandes de perpetuo" in ev[0]["texto"], ev
    b.esc["grandes"] = GRA_HIST + [(M0 + 1, "bybit_linear", False, 3e6)]
    for m in range(M0 + 2, M0 + 10):  # nace a los 2 min del mensaje: espera a que se cumplan 10 (antes, 30)
        assert not mensajes(await tic(b, estado, cache, m)), m
    ev = mensajes(await tic(b, estado, cache, M0 + 10))
    assert len(ev) == 1 and "venta agresiva" in ev[0]["texto"] and "liquidados" not in ev[0]["texto"], ev
    assert ev[0]["texto"].split("\n")[1].startswith("12:02Z "), ev  # con la hora en que nacio


async def test_ruptura_es_un_cierre_de_5_min_con_margen_y_la_mecha_no():
    mecha = {M0 - 1: (101.0, 99.95, 100.0, 500.0, 1000.0)}
    assert "por encima del maximo" not in textos(await tic(Base(M0, velas=velas(M0, mecha)), seg.nuevo(), {}, M0))
    rompe = {m: plano(m, 101.0) for m in range(M0 - 5, M0)}
    t = textos(await tic(Base(M0, velas=velas(M0, rompe)), seg.nuevo(), {}, M0))
    assert "cierre de 5 min por encima del maximo de" in t and "vuelve a cerrar dentro" in t, t
    assert "A FAVOR" not in t and "EN CONTRA" not in t, t  # AVISOS R1 (H2)


async def test_sin_posicion_abierta_no_se_calcula_nada():
    b = Base(M0, liq5=LIQ_HIST + [(M0 - 5, 1.5e6, 0.0)])
    assert await tic(b, seg.nuevo(), {}, M0, posiciones=()) == []
    assert b.lecturas == []


# ---------- (g) el centinela con el stop movido a beneficio ----------
def test_g_stop_en_beneficio_cerca_si_avisa():
    largo = {"symbol": "BTCUSDT", "lado": 1, "entrada": 100.0, "stop": 101.0, "marca": 101.2}
    corto = {"symbol": "BTCUSDT", "lado": -1, "entrada": 100.0, "stop": 99.0, "marca": 98.9}
    control = {"symbol": "BTCUSDT", "lado": 1, "entrada": 100.0, "stop": 99.0, "marca": 99.2}
    for p in (largo, corto, control):
        assert [t for t, _ in cen.alertas_posicion(p)] == ["stop"], p
    lejos = {"symbol": "BTCUSDT", "lado": 1, "entrada": 100.0, "stop": 101.0, "marca": 103.0}
    assert cen.alertas_posicion(lejos) == []


def montado(modo: str | None, base: Base):
    e = {} if modo is None else {"BOT_SEGUIMIENTO": modo}
    bot, mandados = sv.Bot(e, base, None), []

    async def manda(texto):
        mandados.append(texto)
        return True
    bot.manda = manda
    bot.bybit_ultima = [CORTO]
    return bot, mandados


async def test_en_sombra_no_se_envia_nada_y_estado_cuenta_por_senal(monkeypatch, caplog):
    b = Base(M0, liq5=LIQ_HIST + [(M0 - 5, 1.5e6, 0.0)])
    bot, mandados = montado(None, b)
    assert bot.seguimiento_c.modo == "sombra"
    monkeypatch.setattr(sv.time, "time", lambda: M0 * 60 + 20)
    with caplog.at_level("INFO"):
        await bot.tic_seguimiento()
    assert mandados == []
    assert any(r.getMessage().startswith("SEGUIMIENTO ") for r in caplog.records)
    av = sv.json.loads(sv.js(bot.estado))["seguimiento"]["avisos"]
    assert av and not any(x[1] for x in av), av
    assert not [x for x in b.eventos if "bot_evento" in x[0]]  # sin tipo nuevo en bot_evento
    txt = bot.texto_seguimiento()
    assert "sombra" in txt and "1 mensajes en 24 h" in txt and "LIQ 1" in txt, txt


async def test_enviar_manda_y_apagado_no_lee(monkeypatch):
    monkeypatch.setattr(sv.time, "time", lambda: M0 * 60 + 20)
    b = Base(M0, liq5=LIQ_HIST + [(M0 - 5, 1.5e6, 0.0)])
    bot, mandados = montado("enviar", b)
    await bot.tic_seguimiento()
    assert len(mandados) == 1 and "liquidados" in mandados[0], mandados
    b2 = Base(M0)
    bot2, mandados2 = montado("apagado", b2)
    await bot2.tic_seguimiento()
    assert mandados2 == [] and b2.lecturas == []
    bot3, _ = montado("raro", Base(M0))
    assert bot3.seguimiento_c.modo == "sombra"
