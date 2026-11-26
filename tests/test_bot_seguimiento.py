"""SEGUIMIENTO R1: con una posicion abierta, el bot sigue SU activo en vivo y avisa solo cuando cambia algo (en sombra).

Pedido del dueno (11-26): liquidaciones, absorciones, participantes grandes, rupturas y niveles cercanos mientras tiene una
operacion abierta. Todo con dobles: minutos sinteticos de SOL y una posicion CORTO inventada; ni red ni filas del dueno.
"""

from __future__ import annotations

import math

from app.bot import seguimiento as seg
from app.bot import servicio as sv

M0 = 29_000_000 // 1440 * 1440 + 720  # un mediodia UTC: el maximo del dia existe
CORTO = {"clave": "SOLUSDT:Sell", "symbol": "SOLUSDT", "lado": -1, "entrada": 100.5, "marca": 100.0, "stop": 102.5,
         "objetivo": 96.5, "cantidad": 10.0}


def velas(ahora: int, cambia: dict | None = None) -> dict:
    """1500 minutos planos en 100 (+-0.1), delta pequeno que alterna; `cambia` pisa minutos: {minuto: (h, l, c, buy, vol)}."""
    out = {}
    for m in range(ahora - 1500, ahora):
        c = 100 + 0.1 * math.sin(m / 7)
        out[m] = (c + 0.05, c - 0.05, c, 480.0 if m % 2 else 520.0, 1000.0)
    out.update(cambia or {})
    return out


class Base:
    """La base de 140 en dobles: cada SELECT del modulo contesta lo que el escenario dice; se cuentan las lecturas."""

    def __init__(self, ahora: int, **esc):
        self.ahora, self.lecturas, self.eventos = ahora, [], []
        self.esc = {"velas": velas(ahora), "liq": [], "grandes": [], "liq_cola": [("long", 200_000.0), ("short", 200_000.0)],
                    "rango7": [(130.0, 70.0)], "oi": [(m, 1e6) for m in range(ahora - 10080, ahora, 5)]} | esc

    async def fetch(self, sql, *a):
        self.lecturas.append(sql)
        e = self.esc
        if sql is seg.SQL_VELAS:
            return [(m, *x) for m, x in sorted(e["velas"].items()) if a[1] <= m < a[2]]
        if sql is seg.SQL_LIQ:
            return [x for x in e["liq"] if a[1] <= x[0] < a[2]]
        if sql is seg.SQL_GRANDES:
            return [x for x in e["grandes"] if a[1] <= x[0] < a[2]]
        if sql is seg.SQL_OI:
            return [x for x in e["oi"] if a[1] <= x[0] < a[2]]
        return {seg.SQL_LIQ_COLA: e["liq_cola"], seg.SQL_RANGO: e["rango7"]}[sql]

    async def execute(self, sql, *a):
        self.eventos.append((sql, a))


async def tic(base: Base, estado: dict, cache: dict, minuto: int, posiciones=(CORTO,)) -> list[dict]:
    base.ahora = minuto
    return await seg.tic(base, list(posiciones), estado, cache, minuto * 60 + 20)


def de(evs: list[dict], tipo: str) -> list[dict]:
    return [x for x in evs if x["tipo"] == tipo]


async def test_a_una_rafaga_de_liquidaciones_de_largos_da_UN_evento_y_no_se_repite_en_el_enfriamiento():
    b, estado, cache = Base(M0, liq=[(M0 - 2, "long", 600_000.0)]), seg.nuevo(), {}
    ev = de(await tic(b, estado, cache, M0), "liquidaciones")
    assert len(ev) == 1, ev
    assert ev[0]["lado"] == -1 and "largos" in ev[0]["texto"] and "A FAVOR" in ev[0]["texto"], ev
    assert len(ev[0]["texto"].split("\n")) <= 2
    for m in (M0 + 1, M0 + 2, M0 + 3):  # sigue dentro de la ventana de 5 min: el estado no cambia
        assert not de(await tic(b, estado, cache, m), "liquidaciones")
    b.esc["liq"] = []
    assert not de(await tic(b, estado, cache, M0 + 8), "liquidaciones")
    b.esc["liq"] = [(M0 + 9, "long", 900_000.0)]  # otra rafaga dentro del enfriamiento: callada
    assert not de(await tic(b, estado, cache, M0 + 10), "liquidaciones")
    b.esc["liq"] = [(M0 + 30, "long", 900_000.0)]  # pasado el enfriamiento, vuelve a avisar
    assert len(de(await tic(b, estado, cache, M0 + 31), "liquidaciones")) == 1


async def test_a_bis_por_debajo_de_su_cola_no_avisa():
    b = Base(M0, liq=[(M0 - 2, "long", 150_000.0)])
    assert not de(await tic(b, seg.nuevo(), {}, M0), "liquidaciones")


async def test_b_delta_agresivo_grande_con_el_precio_quieto_es_absorcion_con_su_lado():
    cambia = {m: (100.05, 99.95, 100.0, 900.0 if m >= M0 - 5 else 500.0, 1000.0) for m in range(M0 - 6, M0)}  # precio quieto
    ev = de(await tic(Base(M0, velas=velas(M0, cambia)), seg.nuevo(), {}, M0), "absorcion")
    assert len(ev) == 1, ev
    assert ev[0]["lado"] == -1 and "compras" in ev[0]["texto"] and "A FAVOR" in ev[0]["texto"], ev
    # el mismo delta con el precio subiendo detras NO es absorcion
    sube = {m: (100.0 + (m - M0 + 6) * 0.6 + 0.05, 99.9 + (m - M0 + 6) * 0.6, 100.0 + (m - M0 + 6) * 0.6, 900.0, 1000.0)
            for m in range(M0 - 5, M0)}
    assert not de(await tic(Base(M0, velas=velas(M0, sube)), seg.nuevo(), {}, M0), "absorcion")


async def test_c_una_operacion_grande_da_grande_con_lado_y_mercado():
    b = Base(M0, grandes=[(M0 - 1, "binance_usdm", True, 1_500_000.0), (M0 - 1, "coinbase_spot", False, 1_200_000.0),
                          (M0 - 1, "okx_swap", False, 50_000.0)])
    ev = de(await tic(b, seg.nuevo(), {}, M0), "grande")
    assert len(ev) == 2, ev
    perp = next(x for x in ev if "perpetuo" in x["texto"])
    contado = next(x for x in ev if "contado" in x["texto"])
    assert perp["lado"] == 1 and "compra" in perp["texto"] and "EN CONTRA" in perp["texto"], perp
    assert contado["lado"] == -1 and "venta" in contado["texto"] and "A FAVOR" in contado["texto"], contado


async def test_d_cerrar_1_min_mas_alla_del_maximo_con_margen_es_ruptura_y_la_mecha_no():
    mecha = {M0 - 1: (101.0, 99.95, 100.0, 500.0, 1000.0)}
    assert not de(await tic(Base(M0, velas=velas(M0, mecha)), seg.nuevo(), {}, M0), "ruptura")
    rompe = {M0 - 1: (101.0, 100.0, 100.9, 500.0, 1000.0)}
    ev = de(await tic(Base(M0, velas=velas(M0, rompe)), seg.nuevo(), {}, M0), "ruptura")
    assert len(ev) == 1, ev
    assert ev[0]["lado"] == 1 and "maximo" in ev[0]["texto"] and "EN CONTRA" in ev[0]["texto"], ev


async def test_d_bis_un_nivel_cercano_avisa_una_vez():
    b, estado, cache = Base(M0), seg.nuevo(), {}
    ev = de(await tic(b, estado, cache, M0), "cerca")
    assert {x["lado"] for x in ev} == {1, -1}, ev  # el maximo (resistencia) y el minimo (soporte) de 24 h, una vez
    assert not de(await tic(b, estado, cache, M0 + 1), "cerca")


async def test_e_sin_posicion_abierta_no_se_calcula_nada():
    b = Base(M0, liq=[(M0 - 2, "long", 600_000.0)])
    assert await tic(b, seg.nuevo(), {}, M0, posiciones=()) == []
    assert b.lecturas == []


async def test_avance_en_r_avisa_al_cruzar_un_hito():
    b, estado, cache = Base(M0), seg.nuevo(), {}
    assert not de(await tic(b, estado, cache, M0), "avance")  # la primera lectura solo fija el tramo
    ev = de(await tic(b, estado, cache, M0 + 1, posiciones=(CORTO | {"marca": 98.4},)), "avance")
    assert len(ev) == 1 and "+1.0 R" in ev[0]["texto"] and "A FAVOR" in ev[0]["texto"], ev


async def test_tope_por_hora_y_resumen():
    b, estado, cache = Base(M0), seg.nuevo(), {}
    estado["emitidos"] = [M0 * 60 - 60] * seg.TOPE_HORA
    ev = await tic(b, estado, cache, M0, posiciones=(CORTO,))
    assert ev and all(x["contenido"] for x in ev), ev
    res = de(await tic(b, estado, cache, M0 + 31), "resumen")
    assert len(res) == 1 and "SOL" in res[0]["texto"], res


def montado(modo: str | None, base: Base):
    e = {} if modo is None else {"BOT_SEGUIMIENTO": modo}
    bot, mandados = sv.Bot(e, base, None), []

    async def manda(texto):
        mandados.append(texto)
        return True
    bot.manda = manda
    bot.bybit_ultima = [CORTO]
    return bot, mandados


async def test_f_en_sombra_no_se_envia_nada_y_se_cuenta_en_el_estado(monkeypatch, caplog):
    b = Base(M0, liq=[(M0 - 2, "long", 600_000.0)])
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
    assert "seguimiento" in bot.texto_seguimiento() and "sombra" in bot.texto_seguimiento()


async def test_f_bis_enviar_manda_y_apagado_no_lee(monkeypatch):
    monkeypatch.setattr(sv.time, "time", lambda: M0 * 60 + 20)
    b = Base(M0, liq=[(M0 - 2, "long", 600_000.0)])
    bot, mandados = montado("enviar", b)
    await bot.tic_seguimiento()
    assert any("liquidaciones" in t for t in mandados), mandados
    b2 = Base(M0)
    bot2, mandados2 = montado("apagado", b2)
    await bot2.tic_seguimiento()
    assert mandados2 == [] and b2.lecturas == []
    bot3, _ = montado("raro", Base(M0))
    assert bot3.seguimiento_c.modo == "sombra"
