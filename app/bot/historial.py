"""BOT-4a «TU HISTORIAL»: baja y guarda el historial real de la cuenta de Bybit (linear), SIN analizarlo.

Medido por el OPERADOR en la doc de Bybit (2026-11-02): /v5/position/closed-pnl y /v5/execution/list llegan a «2 years»,
piden category, endTime - startTime <= 7 dias, limit hasta 100 y paginan con nextPageCursor. closed-pnl no dice cuando se
abrio la posicion: por eso van las ejecuciones. Que la clave de solo lectura sirva para execution/list NO esta medido:
un error de permiso ahi no tira los cierres, se dice en el fichero (permiso_ejecuciones).

Aislamiento: no escribe en la base (ni bot_operacion, ni el libro, ni bot_crudo), no evalua, no avisa por operacion y no
llama a Anthropic. Son datos financieros privados: sus filas van SOLO al fichero (600, directorio 700), nunca a un log.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime

import httpx

from app.bot import bybit as bb

RUTA = "/var/lib/coinalyze-bot/historial/historial.json"
DIAS = 730
VENTANA_MS = 7 * 86400 * 1000  # el tope de Bybit: endTime - startTime <= 7 dias
CADUCA_S = 7 * 86400
PAUSA = 0.25
ESPERAS = (1.0, 2.0, 4.0)  # los reintentos de un fallo pasajero: cortos y limitados
MAX_PAGINAS = 500  # por ventana y ruta: un cursor que no acaba no deja la tarea viva para siempre
PERMISO = {10005}
CLAVE = {10003, 10004, 10010, 33004}  # la clave no sirve: no es una ventana fallida, se para y se dice
RUTAS = {"cierres": "/v5/position/closed-pnl", "ejecuciones": "/v5/execution/list"}


class ClaveRechazada(RuntimeError):
    pass


def ventanas(hasta_ms: int, dias: int = DIAS) -> list[tuple[int, int]]:
    """De `hasta_ms` hacia atras: [inicio, fin] en ms, fin - inicio <= 7 dias, contiguas sin hueco ni solape (la
    siguiente acaba 1 ms antes de donde empezo la anterior) y la ultima empieza justo en hasta - dias."""
    desde, fin, out = hasta_ms - dias * 86400 * 1000, hasta_ms, []
    while fin >= desde:
        ini = max(desde, fin - VENTANA_MS)
        out.append((ini, fin))
        fin = ini - 1
    return out


async def pide(bybit, ruta: str, dormir, **params) -> dict:
    d: dict = {}
    for espera in (*ESPERAS, None):
        try:
            d = await bybit.get(ruta, **params)
        except httpx.HTTPError as e:
            d = {"retCode": -1, "retMsg": f"no contesta: {type(e).__name__}"}
        if not bb.transitorio(d) or espera is None:
            return d
        await dormir(espera)
    return d


async def ventana(bybit, ruta: str, ini: int, fin: int, dormir, pausa: float) -> tuple[list, dict | None]:
    """Todas las paginas de una ventana. Devuelve (filas, None) o (lo leido, la respuesta con error)."""
    filas, cursor, vistos = [], None, set()
    for _ in range(MAX_PAGINAS):
        p = {"category": "linear", "startTime": ini, "endTime": fin, "limit": 100}
        if cursor:
            p["cursor"] = cursor
        d = await pide(bybit, ruta, dormir, **p)
        await dormir(pausa)
        if bb.error(d):
            return filas, d
        res = d.get("result") or {}
        filas.extend(res.get("list") or [])
        cursor = res.get("nextPageCursor") or None
        if not cursor or cursor in vistos:
            return filas, None
        vistos.add(cursor)
    return filas, {"retCode": -2, "retMsg": f"mas de {MAX_PAGINAS} paginas"}


async def descarga(bybit, ahora_ms: int | None = None, dias: int = DIAS, pausa: float = PAUSA, dormir=asyncio.sleep) -> dict:
    hasta = int(time.time() * 1000) if ahora_ms is None else ahora_ms
    vs = ventanas(hasta, dias)
    out = {"generado": datetime.now(UTC).isoformat(timespec="seconds"), "desde": vs[-1][0], "hasta": hasta,
           "n_cierres": 0, "n_ejecuciones": 0, "ventanas_fallidas": [], "permiso_ejecuciones": "ok",
           "cierres": [], "ejecuciones": []}
    for ini, fin in vs:
        for tipo, ruta in RUTAS.items():
            if tipo == "ejecuciones" and out["permiso_ejecuciones"] != "ok":
                continue
            filas, d = await ventana(bybit, ruta, ini, fin, dormir, pausa)
            out[tipo].extend(filas)
            if d is None:
                continue
            if d.get("retCode") in CLAVE:
                raise ClaveRechazada(f"{ruta}: {bb.error(d)}")
            if tipo == "ejecuciones" and d.get("retCode") in PERMISO:
                out["permiso_ejecuciones"] = f"sin permiso: {bb.error(d)}"
                continue
            out["ventanas_fallidas"].append({"ruta": ruta, "desde": ini, "hasta": fin, "error": bb.error(d)})
    out["n_cierres"], out["n_ejecuciones"] = len(out["cierres"]), len(out["ejecuciones"])
    return out


def _t(f: dict, *claves: str) -> int | None:
    for k in claves:
        try:
            return int(f[k])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _en(filas: list, desde: int, *claves: str) -> int:
    return sum(1 for f in filas if (_t(f, *claves) or 0) >= desde)


def completo(d: dict) -> bool:
    return not d.get("ventanas_fallidas") and d.get("permiso_ejecuciones") == "ok"


def _escribe(ruta: str, datos: dict):
    tmp = f"{ruta}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(datos, f)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def guarda(ruta: str, datos: dict) -> str:
    """Escribe atomico (600, directorio 700) y devuelve donde. Un fichero COMPLETO no se pisa con uno que traiga menos
    filas en el mismo tramo (desde el `desde` nuevo: lo que la ventana movil deja fuera por viejo no cuenta): entonces
    va a historial.parcial.json, al lado."""
    carpeta = os.path.dirname(ruta) or "."
    os.makedirs(carpeta, mode=0o700, exist_ok=True)
    os.chmod(carpeta, 0o700)
    try:
        with open(ruta) as f:
            viejo = json.load(f)
    except (OSError, ValueError):
        viejo = None
    if isinstance(viejo, dict) and completo(viejo):
        desde = datos["desde"]
        if (len(datos["cierres"]) < _en(viejo.get("cierres") or [], desde, "updatedTime", "createdTime")
                or len(datos["ejecuciones"]) < _en(viejo.get("ejecuciones") or [], desde, "execTime")):
            ruta = os.path.join(carpeta, "historial.parcial.json")
    _escribe(ruta, datos)
    return ruta


def vigente(ruta: str, ahora: float | None = None) -> bool:
    try:
        return ((time.time() if ahora is None else ahora) - os.stat(ruta).st_mtime) < CADUCA_S
    except OSError:
        return False


def _dia(ms: int | None) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d") if ms else "-"


def resumen(d: dict, parcial: bool) -> str:
    """El Telegram de fin: cuantas filas, primera y ultima fecha, ventanas fallidas. Sin una cifra de dinero."""
    ts = [t for t in [_t(f, "createdTime", "updatedTime") for f in d["cierres"]]
          + [_t(f, "updatedTime", "createdTime") for f in d["cierres"]]
          + [_t(f, "execTime") for f in d["ejecuciones"]] if t]
    lineas = [f"historial de Bybit: {d['n_cierres']} cierres, {d['n_ejecuciones']} ejecuciones",
              f"primera {_dia(min(ts) if ts else None)} · ultima {_dia(max(ts) if ts else None)}",
              f"ventanas fallidas: {len(d['ventanas_fallidas'])}"]
    if d["permiso_ejecuciones"] != "ok":
        lineas.append(f"ejecuciones: {d['permiso_ejecuciones']}")
    if parcial:
        lineas.append("trae menos filas que el completo que habia: NO lo piso, va a historial.parcial.json")
    return "\n".join(lineas)
