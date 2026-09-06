import time

import pytest

from app.ws_collector import (
    WHALE_TRADE_THRESHOLD,
    Bucket,
    BucketStore,
    binance_url,
    spot_pairs,
    valid_trade,
)


def test_valid_trade_rejects_bad_values(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    now_ms = 1_000_000_000
    assert valid_trade("100", "2", now_ms) == (100.0, 2.0, now_ms)
    assert valid_trade("nan", "2", now_ms) is None
    assert valid_trade("100", "0", now_ms) is None
    assert valid_trade("100", "2", now_ms - 121_000) is None
    assert valid_trade("100", "2", now_ms + 31_000) is None
    assert valid_trade("10000000", "100000000", now_ms) is None


@pytest.mark.asyncio
async def test_ack_does_not_drop_bucket_changed_during_flush(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    store = BucketStore()
    event_ms = 999_800_000
    await store.add("BTC", "binance", event_ms, 100.0, 1.0, True)
    snapshots = await store.minute_snapshot()
    assert len(snapshots) == 1
    await store.add("BTC", "binance", event_ms + 1, 100.0, 1.0, True)
    await store.ack_minute(snapshots)
    assert len(store.minute) == 1


@pytest.mark.asyncio
async def test_bucketstore_caps_realtime_buckets_during_database_outage(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    store = BucketStore(max_bucket_minutes=120, max_buckets_per_key=2)
    for offset_ms in (0, 5_000, 10_000):
        await store.add("BTC", "binance", 1_000_000_000 - offset_ms, 100.0, 1.0, True)

    assert len(store.realtime) == 2
    assert store.dropped_buckets == 1
    assert store.dropped_trades == 1


def test_whale_trade_threshold_is_asset_specific():
    bucket = Bucket()
    bucket.add(1_000_000, True, WHALE_TRADE_THRESHOLD["BTC"])
    assert bucket.inst_buy_usd == 0
    assert bucket.mid_buy_usd == 1_000_000
    bucket.add(5_000_000, True, WHALE_TRADE_THRESHOLD["BTC"])
    assert bucket.inst_buy_usd == 5_000_000


def test_heartbeat_publishes_each_spot_venue() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ws_collector.py").read_text()
    assert 'f"ws-{exchange}:{shard_index}/{shard_count}"' in source


def test_websocket_topics_are_generated_only_for_assigned_symbols():
    symbols = ("ETHUSDT_PERP.A",)

    assert spot_pairs(symbols) == ("ETHUSDT",)
    assert binance_url(symbols).endswith("ethusdt@aggTrade")
    assert "btcusdt" not in binance_url(symbols)
    assert "solusdt" not in binance_url(symbols)


@pytest.mark.asyncio
async def test_el_vaciado_de_apagado_se_lleva_los_minutos_cerrados(monkeypatch):
    """Los que esperan la gracia se perdian en cada reinicio: son dato real."""
    from app.ws_collector import LATE_TRADE_GRACE_SECONDS

    ahora = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: ahora)
    store = BucketStore()
    # un minuto cerrado hace 70 s: NO es elegible para el flush normal (gracia 125 s)
    cerrado_ms = int((ahora - 130) * 1000)
    await store.add("BTC", "binance", cerrado_ms, 100.0, 1.0, True)
    assert await store.minute_snapshot() == []
    assert LATE_TRADE_GRACE_SECONDS > 60
    # con gracia 0 si sale, que es lo que hace el vaciado del apagado
    assert len(await store.minute_snapshot(grace=0.0)) == 1


@pytest.mark.asyncio
async def test_el_vaciado_de_apagado_NO_publica_el_minuto_en_curso(monkeypatch):
    """Un minuto a medias escrito como completo seria inventarse un volumen."""
    ahora = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: ahora)
    store = BucketStore()
    await store.add("BTC", "binance", int((ahora - 5) * 1000), 100.0, 1.0, True)
    assert await store.minute_snapshot(grace=0.0) == []


@pytest.mark.asyncio
async def test_drain_devuelve_cuantos_minutos_salvo(monkeypatch):
    from app import ws_collector

    ahora = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: ahora)
    monkeypatch.setattr(ws_collector, "STORE", BucketStore())
    await ws_collector.STORE.add("BTC", "binance", int((ahora - 130) * 1000), 100.0, 1.0, True)
    escritos = []

    # El doble acepta `fin` y lo GUARDA: desde el arreglo de K92 el drenaje tiene que
    # trasladar el instante de parada, y un doble que lo ignorara dejaria pasar que no llegue.
    async def _falso(_pool, _ownership, snapshots, fin=None):
        escritos.append((snapshots, fin))

    monkeypatch.setattr(ws_collector, "_write_minute", _falso)
    assert await ws_collector.drain_closed_minutes(None, None, fin=ahora) == 1
    assert len(escritos) == 1
    assert escritos[0][1] == ahora
    # y sin nada que salvar no toca la base
    monkeypatch.setattr(ws_collector, "STORE", BucketStore())
    assert await ws_collector.drain_closed_minutes(None, None) == 0
    assert len(escritos) == 1


def test_el_minuto_del_arranque_se_marca_corto():
    """K52: la fila existe y hoy pasa por completa; el que arranca a mitad no cubre 60 s."""
    from app.ws_collector import segundos_cubiertos

    arranque = 1_000_030.0  # el proceso empieza 30 s dentro del minuto que abre en 1000000
    assert segundos_cubiertos(1_000_000, arranque) == 30
    assert segundos_cubiertos(1_000_045, arranque) == 60  # minuto posterior: completo
    assert segundos_cubiertos(999_940, arranque) == 0     # minuto anterior entero: nada


def test_el_minuto_completo_NO_se_marca():
    """El control positivo: un guardia que marca todo esta tan roto como el que no marca."""
    from app.ws_collector import segundos_cubiertos

    arranque = 1_000_000.0
    assert segundos_cubiertos(1_000_000, arranque) == 60
    assert segundos_cubiertos(1_000_600, arranque) == 60


def test_los_dos_colectores_marcan_igual():
    """Lo pagan los dos y la marca tiene que significar lo mismo en las dos tablas."""
    from app.scalp_collector import segundos_cubiertos as futuros
    from app.ws_collector import segundos_cubiertos as spot

    for ts in (999_900, 1_000_000, 1_000_030, 1_000_120):
        assert spot(ts, 1_000_030.0) == futuros(ts, 1_000_030.0)


def test_el_minuto_de_la_PARADA_se_marca_corto():
    """K92, medido en 140 el 2026-09-04T17:16: cubrio 55 s y la fila decia 60.

    EL MECANISMO, leido en el codigo y no supuesto: al apagar, `drain_closed_minutes` escribe
    los minutos YA CERRADOS. Si el SIGTERM llega en el segundo 55, ese minuto aun esta abierto;
    para cuando el drenaje corre ya cerro, asi que se escribe. Y `segundos_cubiertos` solo
    conocia el ARRANQUE: como el minuto empieza despues del arranque, devolvia 60.

    UN HUECO SE VE; UN MINUTO QUE MIENTE QUE ESTA COMPLETO NO LO VE NADIE.
    """
    from app.scalp_collector import segundos_cubiertos as futuros
    from app.ws_collector import segundos_cubiertos

    arranque, parada = 1_000_000.0, 1_000_115.0   # se va 55 s dentro del minuto que abre en 60
    assert segundos_cubiertos(1_000_060, arranque, parada) == 55
    assert futuros(1_000_060, arranque, parada) == 55
    # El minuto SIGUIENTE al de la parada no se cubrio en absoluto.
    assert segundos_cubiertos(1_000_120, arranque, parada) == 0
    # Y el ANTERIOR, entero antes de la parada, sigue completo: la correccion no contagia.
    assert segundos_cubiertos(1_000_000, arranque, parada) == 60


def test_el_arranque_y_la_parada_se_recortan_a_la_vez():
    """El caso que ninguna de las dos mitades cubre sola: arranca y muere dentro del mismo minuto."""
    from app.ws_collector import segundos_cubiertos

    # Minuto [1000000, 1000060). Arranca en el segundo 10, se va en el 40: cubre 30.
    assert segundos_cubiertos(1_000_000, 1_000_010.0, 1_000_040.0) == 30


def test_sin_instante_de_parada_el_resultado_es_EL_DE_ANTES():
    """CONTROL DE NO REGRESION: `fin` es una extension, no un cambio de comportamiento.

    Sin este caso, el arreglo podria haber movido en silencio la cobertura de todos los minutos
    que no tienen nada que ver con una parada, que son la inmensa mayoria.
    """
    from app.scalp_collector import segundos_cubiertos as futuros
    from app.ws_collector import segundos_cubiertos

    def anterior(ts: int, arranque: float) -> int:
        """La implementacion literal de antes del 2026-09-06."""
        if ts >= arranque:
            return 60
        return max(0, min(60, int(round(ts + 60 - arranque))))

    for arranque in (999_900.0, 1_000_000.0, 1_000_030.0, 1_000_059.9):
        for ts in range(999_840, 1_000_200, 20):
            esperado = anterior(ts, arranque)
            assert segundos_cubiertos(ts, arranque) == esperado, (ts, arranque)
            assert futuros(ts, arranque) == esperado, (ts, arranque)


def test_el_drenaje_de_apagado_pasa_el_instante_de_parada():
    """Que la funcion sepa recortar no sirve de nada si el que apaga no se lo dice.

    Es el eslabon que hace que el arreglo llegue a la fila: `drain_closed_minutes(fin=...)`
    tiene que trasladarlo hasta `segundos_cubiertos`. Se comprueba en la firma y en el paso,
    porque el camino entero -SIGTERM, sockets, pool- no se puede montar en un test.
    """
    import inspect

    from app import scalp_collector, ws_collector

    assert "fin" in inspect.signature(ws_collector.drain_closed_minutes).parameters
    assert "fin" in inspect.signature(ws_collector._write_minute).parameters
    assert "fin" in inspect.signature(scalp_collector.drenar_minutos).parameters
    fuente = inspect.getsource(ws_collector.drain_closed_minutes)
    assert "fin=fin" in fuente
    # Y EL INSTANTE SE TOMA ANTES DE CANCELAR LAS TAREAS: despues regalaria al minuto los
    # segundos del desmontaje, que es cobertura que no hubo.
    # La primera version de este brazo pedia `ws_collector.main`, que NO EXISTE -el lazo se
    # llama `run`-, asi que el `if` nunca entraba y el caso pasaba en vacio. Ahora se nombran
    # las dos funciones y se exige que existan: un brazo que no puede fallar no es un brazo.
    for modulo, lazo in ((ws_collector, "run"), (scalp_collector, "main")):
        fuente_lazo = inspect.getsource(getattr(modulo, lazo))
        assert "parando = time.time()" in fuente_lazo, lazo
        assert fuente_lazo.index("parando = time.time()") < fuente_lazo.index("task.cancel()"), lazo
        assert "fin=parando" in fuente_lazo, lazo
