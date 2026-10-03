"""El GENERADOR en marcha, alojado en coinalyze-ingest (P7: no cabe una unidad nueva).

COMO NO ESTORBA (C2 f). ingest recoge ohlcv 1min y las metricas en su bucle de eventos; los
trades y el libro los recogen OTROS procesos (coinalyze-scalp, coinalyze-ws). El generador:
  - corre en UN hilo aparte, con su propio bucle de eventos y su propia conexion: no toma
    conexiones del pool de ingest ni tiempo de su bucle;
  - nunca dos a la vez: un candado; si la pasada anterior sigue viva, esta se SALTA y lo apunta;
  - con tope de tiempo (comun.tope_tick_s): al tope, ingest deja de esperarla y lo apunta;
  - no lanza nunca hacia ingest: todo fallo queda en entrada_latido, que sirve /api/entradas.

CUANDO CORRE. Cada vela del perfil mas corto (15 min) a +espera_datos_s.primer_intento. La vela
de 1 min llega a ~6-11 s de su cierre (medido en 140 el 2026-10-02: 45 de 45 entre 5.8 y 10.6 s),
asi que lo normal es que este completa al primer intento; si no, se reintenta hasta el ultimo
intento y despues queda NO EVALUABLE con su motivo. Lo que se registre por encima del tope de
retraso lo convierte la base en SOMBRA «tardio».

RECUPERACION. Tras un reinicio o un apagon, las velas perdidas (hasta recuperacion_max_velas) se
evaluan en orden para que la maquina de estados no salte nada; todo lo que salga de ellas es
tardio por construccion: ninguna evaluacion de recuperacion emite DISPARADO de una vela pasada.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Any

import asyncpg

from app.config import MARKET_SYMBOL_CATALOG
from app.entradas import codigo as C
from app.entradas import insumos as I
from app.entradas import motor as M
from app.entradas import registro as G
from app.entradas import reglamento as R

LOGGER = logging.getLogger(__name__)
_EN_CURSO = threading.Lock()
# Solo si el reglamento no carga: la pasada sigue corriendo para apuntar POR QUE no emite.
_CADENCIA_RESERVA_S = 900
_DESFASE_RESERVA_S = 20
_TOPE_RESERVA_S = 600


def _conexion_kw(settings) -> dict[str, Any]:
    return {
        "dsn": settings.pg_dsn,
        "server_settings": {
            "timezone": "UTC",
            "statement_timeout": "20s",
            "lock_timeout": "3s",
            "idle_in_transaction_session_timeout": "30s",
            "application_name": "coinalyze-entradas",
        },
    }


def plan_de_marcha() -> dict[str, int]:
    """Cadencia, desfase y tope del planificador, leidos del reglamento en curso."""
    try:
        doc = R.cargar_valido()
    except Exception:  # noqa: BLE001 - el motivo lo apunta la propia pasada en el latido
        return {"cadencia_s": _CADENCIA_RESERVA_S, "desfase_s": _DESFASE_RESERVA_S,
                "tope_s": _TOPE_RESERVA_S}
    cadencias, desfases, topes = [], [], []
    for v in R.versiones_en_curso(doc):
        pc = R.valores(v["bloques"]["comun"])
        cadencias.extend(p["vela_min"] * 60 for p in pc["perfiles"].values())
        desfases.append(pc["espera_datos_s"]["primer_intento"])
        topes.append(pc["tope_tick_s"])
    return {"cadencia_s": min(cadencias), "desfase_s": min(desfases), "tope_s": min(topes)}


async def _latido_suelto(settings, estado: str, detalle: dict[str, Any]) -> None:
    try:
        conn = await asyncpg.connect(timeout=10, **_conexion_kw(settings))
        try:
            await G.latir(conn, vela_cierre=None, estado=estado, duracion_s=None, detalle=detalle,
                          error=None)
        finally:
            await conn.close()
    except Exception:  # noqa: BLE001 - un latido que no se puede escribir no tumba ingest
        LOGGER.exception("entradas_latido_suelto_fallo estado=%s", estado)


async def pasada(settings, *, objetivo=None, tope_s: float | None = None) -> None:
    """La llama run_aligned_feed. Nunca lanza: lo que falle queda en entrada_latido.

    `objetivo` y `tope_s` solo los cambian los controles (un generador plantado lento o que
    lanza, con un tope corto)."""
    if not _EN_CURSO.acquire(blocking=False):
        await _latido_suelto(settings, "saltado",
                             {"motivo": "la pasada anterior sigue en curso: no corren dos a la vez"})
        return
    tope = tope_s if tope_s is not None else plan_de_marcha()["tope_s"]
    bucle = asyncio.get_running_loop()
    hecho = asyncio.Event()
    trabajo = objetivo or (lambda: asyncio.run(_pasada_async(settings)))

    def en_hilo() -> None:
        try:
            trabajo()
        except BaseException as exc:  # noqa: BLE001 - el hilo no puede tumbar a nadie
            LOGGER.exception("entradas_pasada_fallo_en_hilo")
            detalle = {"motivo": "la pasada lanzo fuera de su propio registro de fallos",
                       "excepcion": f"{type(exc).__name__}: {exc}"[:500],
                       "traza": traceback.format_exc()[-2000:]}
            try:
                asyncio.run(_latido_suelto(settings, "error", detalle))
            except BaseException:  # noqa: BLE001
                LOGGER.exception("entradas_latido_de_error_fallo")
        finally:
            _EN_CURSO.release()
            try:
                bucle.call_soon_threadsafe(hecho.set)
            except RuntimeError:
                pass  # ingest ya se esta parando

    try:
        threading.Thread(target=en_hilo, name="entradas-generador", daemon=True).start()
    except BaseException:
        _EN_CURSO.release()
        raise
    try:
        await asyncio.wait_for(hecho.wait(), timeout=tope)
    except TimeoutError:
        await _latido_suelto(
            settings,
            "tope",
            {"motivo": f"la pasada supero su tope de {tope} s; sigue en su hilo y las siguientes "
             "se saltan mientras tanto"},
        )


def _alineada(T: datetime, vela_min: int) -> bool:
    return int(T.timestamp()) % (vela_min * 60) == 0


async def _pendientes(conn: asyncpg.Connection, T: datetime, cadencia: timedelta,
                      maximo: int) -> tuple[list[datetime], int]:
    ultimo = await G.ultimo_tick(conn)
    if ultimo is None or ultimo >= T:
        return [T], 0
    pendientes = []
    t = ultimo + cadencia
    while t <= T:
        pendientes.append(t)
        t += cadencia
    omitidas = max(0, len(pendientes) - maximo)
    return pendientes[omitidas:], omitidas


async def evaluar_vela(conn: asyncpg.Connection, *, T: datetime, doc: dict[str, Any],
                       huella_codigo: str, esperar: bool, modo: str = M.PROSPECTIVO) -> list[dict]:
    """Una vela de cierre T: todos los perfiles alineados en T, todos los simbolos.

    Las versiones se agrupan por su bloque comun: cada grupo carga SUS insumos (sus ventanas)."""
    revision = R.revision_vigente(doc, T)
    bases = {item.symbol: item.base_asset for item in MARKET_SYMBOL_CATALOG}
    grupos: dict[str, list[dict[str, Any]]] = {}
    for v in R.versiones_en_curso(doc):
        grupos.setdefault(v["huellas"]["comun"], []).append(v)
    salida: list[dict] = []
    for versiones in grupos.values():
        comun = R.valores(versiones[0]["bloques"]["comun"])
        calendario = R.valores(versiones[0]["bloques"]["calendario"])
        for perfil, p in comun["perfiles"].items():
            if not _alineada(T, p["vela_min"]):
                continue
            desde = T - G.ventana_previos(versiones, perfil)
            for symbol in comun["simbolos"]:
                cargar = {"symbol": symbol, "base_asset": bases[symbol], "T": T, "perfil": perfil,
                          "comun": comun, "calendario": calendario, "modo": modo}
                insumos = await I.cargar(conn, **cargar)
                espera = comun["espera_datos_s"]
                while esperar and not I.vela_de_T_completa(insumos):
                    ahora = await conn.fetchval("SELECT clock_timestamp()")
                    if ahora >= T + timedelta(seconds=espera["ultimo_intento"]):
                        break
                    await asyncio.sleep(espera["reintento"])
                    insumos = await I.cargar(conn, **cargar)
                previos = await G.cargar_previos(conn, symbol=symbol, perfil=perfil,
                                                 versiones=[v["version"] for v in versiones],
                                                 desde=desde, T=T)
                resultado = M.paso(T=T, symbol=symbol, perfil=perfil, modo=modo,
                                   versiones=versiones, insumos=insumos, previos=previos,
                                   revision=revision, codigo=huella_codigo)
                registradas = [
                    await G.insertar(conn, t, huella_codigo) for t in resultado["transiciones"]
                ]
                salida.append({"vela_cierre": M.iso(T), "perfil": perfil, "symbol": symbol,
                               "versiones": [v["version"] for v in versiones],
                               "evaluacion": resultado["evaluacion"], "registradas": registradas})
    return salida


async def _pasada_async(settings) -> None:
    t0 = time.monotonic()
    conn = await asyncpg.connect(timeout=10, **_conexion_kw(settings))
    T: datetime | None = None
    estado, error = "ok", None
    detalle: dict[str, Any] = {"velas": []}
    try:
        plan = plan_de_marcha()
        cadencia = timedelta(seconds=plan["cadencia_s"])
        T = await conn.fetchval(
            "SELECT date_bin($1::interval, clock_timestamp(), TIMESTAMPTZ '1970-01-01 00:00:00+00')",
            cadencia,
        )
        try:
            doc = R.cargar_valido()
        except Exception as exc:  # noqa: BLE001
            estado, error = "reglamento_invalido", str(exc)[:2000]
            return
        contenido = C.contenido()
        registro = await G.registrar_reglamento(conn, doc, C.registradas(), M.CODIGO_VERSION,
                                                contenido)
        detalle["reglamento"] = {k: registro[k] for k in ("ok", "motivo", "conflictos",
                                                          "huerfanas")}
        if not registro["ok"]:
            estado, error = "sin_reglamento", registro["motivo"]
            return
        comun = R.valores(R.versiones_en_curso(doc)[0]["bloques"]["comun"])
        # la recuperacion cubre lo que pida el perfil mas exigente: velas x minutos por vela
        minutos = max(comun["recuperacion_max_velas"][p] * comun["perfiles"][p]["vela_min"]
                      for p in comun["perfiles"])
        maximo = minutos * 60 // plan["cadencia_s"]
        pendientes, omitidas = await _pendientes(conn, T, cadencia, maximo)
        detalle["recuperacion"] = {"velas": len(pendientes) - 1, "omitidas": omitidas}
        for Ti in pendientes:
            detalle["velas"].extend(
                await evaluar_vela(conn, T=Ti, doc=doc, huella_codigo=R.huella(contenido),
                                   esperar=Ti == T)
            )
    except Exception:  # noqa: BLE001
        estado, error = "error", traceback.format_exc()[-4000:]
    finally:
        try:
            await G.latir(conn, vela_cierre=T, estado=estado,
                          duracion_s=round(time.monotonic() - t0, 3), detalle=detalle, error=error)
        finally:
            await conn.close()
