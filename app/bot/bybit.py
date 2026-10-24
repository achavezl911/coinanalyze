"""Bybit v5, SOLO LECTURA. Este modulo solo hace GET y solo a las rutas de RUTAS; no hay ninguna de ordenes, retiros
ni transferencias (tests/test_bot.py lo comprueba buscando en app/bot/, y K117 en el release de 140). La clave NUNCA
se prueba intentando una orden: sus permisos se leen de /v5/user/query-api.

Firma v5 de un GET: HMAC-SHA256(secreto, timestamp + clave + recv_window + query) en hexadecimal, con la query
EXACTA que se envia. Medido por el OPERADOR en la doc publica (2026-10-24, remate 1 de BOT-2): query-api trae «readOnly»
entero (0 lectura y escritura, 1 solo lectura) e «ips» (lista); 10003 «API key is invalid», 10004 «Error sign», 10010
«Unmatched IP». ponytail: el resto (position/list, closed-pnl y sus parametros) sigue de memoria; un campo que falta se
juzga en contra (la clave se apaga), nunca a favor.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse

import httpx

BASE = "https://api.bybit.com"
RECV = "5000"
# ponytail: sin la ruta de la cartera (wallet-balance): ni C2 ni C3 la usan; se anade (es de lectura) cuando algo la pida
PRIVADAS = ("/v5/user/query-api", "/v5/position/list", "/v5/position/closed-pnl")
PUBLICAS = ("/v5/market/risk-limit", "/v5/market/instruments-info", "/v5/market/tickers")
ERRORES = {
    10003: "Bybit dice que la clave no es valida",
    10004: "Bybit rechaza la firma",
    10005: "la clave no tiene permiso para esta lectura",
    10010: "Bybit rechaza la IP de salida de 140 (¿ha cambiado?)",
    33004: "la clave ha caducado",
}


def firma(secreto: str, ts: str, clave: str, query: str) -> str:
    return hmac.new(secreto.encode(), f"{ts}{clave}{RECV}{query}".encode(), hashlib.sha256).hexdigest()


def error(d: dict) -> str | None:
    if d.get("retCode") == 0:
        return None
    return ERRORES.get(d.get("retCode"), f"Bybit retCode={d.get('retCode')}: {str(d.get('retMsg'))[:80]}")


def juzga_clave(d: dict, ip: str) -> dict:
    """La respuesta de /v5/user/query-api -> lo que el bot publica en su estado. activo solo con solo lectura Y la IP."""
    e = error(d)
    if e:
        return {"activo": False, "solo_lectura": None, "ip_ok": None, "ips": None, "ip_salida": ip, "error": e}
    r = d.get("result") or {}
    solo = r.get("readOnly") == 1
    ips = r.get("ips") if isinstance(r.get("ips"), list) else []
    ip_ok = ip in ips and "*" not in ips
    # las IPs atadas no son secretas: van en el estado al lado de la de salida de 140, para ver que falta sin abrir Bybit
    atadas = ", ".join(map(str, ips)) or "ninguna"
    motivo = None if solo and ip_ok else ("la clave PUEDE OPERAR" if not solo else
                                          f"la clave admite cualquier IP (*): tiene que estar atada solo a {ip}" if "*" in ips else
                                          f"la clave no esta atada a {ip} (Bybit tiene atadas: {atadas})")
    return {"activo": solo and ip_ok, "solo_lectura": solo, "ip_ok": ip_ok, "ips": ips, "ip_salida": ip, "error": motivo}


def posiciones(d: dict) -> list[dict]:
    """Las posiciones abiertas (size > 0) de /v5/position/list, con lo que el bot usa."""
    out = []
    for p in (d.get("result") or {}).get("list") or []:
        if float(p.get("size") or 0) <= 0:
            continue
        num = lambda k, p=p: float(p[k]) if p.get(k) not in (None, "") else None  # noqa: E731
        out.append({
            "id": f"{p['symbol']}:{p['side']}:{p.get('createdTime', '')}",
            "symbol": p["symbol"], "lado": 1 if p["side"] == "Buy" else -1, "cantidad": num("size"),
            "entrada": num("avgPrice"), "marca": num("markPrice"), "apalancamiento": num("leverage"),
            "liquidacion": num("liqPrice"), "stop": num("stopLoss") or None, "objetivo": num("takeProfit") or None,
            "margen": num("positionIM"), "pnl_abierto": num("unrealisedPnl"),
        })
    return out


class Bybit:
    def __init__(self, clave: str, secreto: str, http: httpx.AsyncClient):
        self.clave, self.secreto, self.http = clave, secreto, http

    async def get(self, ruta: str, **params) -> dict:
        if ruta not in PRIVADAS + PUBLICAS:
            raise ValueError(f"ruta fuera de la lista de lectura: {ruta}")
        query = urllib.parse.urlencode(params)
        cab = {}
        if ruta in PRIVADAS:
            ts = str(int(time.time() * 1000))
            cab = {"X-BAPI-API-KEY": self.clave, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": RECV,
                   "X-BAPI-SIGN": firma(self.secreto, ts, self.clave, query), "X-BAPI-SIGN-TYPE": "2"}
        r = await self.http.get(f"{BASE}{ruta}?{query}", headers=cab, timeout=15)
        try:
            return r.json()
        except ValueError:
            return {"retCode": -r.status_code, "retMsg": f"HTTP {r.status_code} sin JSON"}
