"""Opus 5.5 por HTTP directo con httpx (ya es dependencia, requirements.lock:11: el SDK no aporta nada a dos POST).
Precio de platform.claude.com/docs/en/about-claude/pricing (leido el 2026-10-24): 4 USD/MTok de entrada, 20 de salida,
5 la escritura de cache de 5 min y 0.20 su lectura; en Opus 5.5 el thinking adaptativo no se apaga y cuenta como salida.

EL ESFUERZO, por llamada (el servicio lo elige por ruta y lo lee de su configuracion); MAX_TOKENS crece con el.
LA CACHE: la parte ESTABLE (instrucciones, reglamento, la forma de operar de Alejandro) va en `system` con cache_control;
el minimo cacheable de Opus 5.5 es 512 tokens (prompt-caching, leido el 2026-10-24): por debajo no cachea y no avisa.
EL TOPE: antes de llamar se cuentan los tokens de entrada exactos (count_tokens, gratis) y se reserva el peor caso (toda
la entrada al precio de escritura de cache x 1.02 + MAX_TOKENS enteros de salida). Si lo gastado hoy + la reserva pasa
del tope, NO se llama. Si la llamada cae sin decir lo que gasto, se apunta la reserva entera (estimado). Las llamadas van
en fila (un candado en el servicio), asi que dos no pueden pasarse juntas.
"""

from __future__ import annotations

import time

import httpx

URL = "https://api.anthropic.com/v1/messages"
MODELO = "claude-opus-5-5"
ESFUERZOS = ("low", "medium", "high", "xhigh", "max")
MAX_TOKENS = {"low": 4000, "medium": 8000, "high": 16000, "xhigh": 32000, "max": 64000}
# el tope de espera de cada esfuerzo (la medida del operador en 140: p90 11.7 s en low, 26.2 s en medium, 44.1 s en high,
# 71.3 s en xhigh): unas 10 veces su p90, no los 900 s de antes para todos
TIMEOUT = {"low": 120, "medium": 240, "high": 480, "xhigh": 900, "max": 900}
PRECIO = {"input_tokens": 4e-6, "output_tokens": 20e-6,
          "cache_creation_input_tokens": 5e-6, "cache_read_input_tokens": 0.2e-6}


def coste(usage: dict) -> float:
    return sum(p * (usage.get(k) or 0) for k, p in PRECIO.items())


def reserva(tokens_entrada: int, effort: str) -> float:
    return tokens_entrada * PRECIO["cache_creation_input_tokens"] * 1.02 + MAX_TOKENS[effort] * PRECIO["output_tokens"]


async def llama(http: httpx.AsyncClient, clave: str, estable: str, texto: str, gastado: float, tope: float,
                effort: str = "high") -> dict:
    """-> texto (None si no hubo respuesta), error, y lo que hay que apuntar: llamada (bool), entrada (toda, cacheada
    incluida), salida, coste, estimado, cache {leida, escrita}, ms. llamada=False: no se llamo a messages."""
    cab = {"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    mensajes = [{"role": "user", "content": texto}]
    nada = {"texto": None, "llamada": False, "entrada": 0, "salida": 0, "coste": 0.0, "estimado": False,
            "cache": {"leida": 0, "escrita": 0}, "ms": 0}
    if effort not in MAX_TOKENS:
        return {**nada, "error": f"esfuerzo desconocido {effort!r}"}
    try:
        r = await http.post(f"{URL}/count_tokens", json={"model": MODELO, "system": estable, "messages": mensajes},
                            headers=cab, timeout=30)
        n = int(r.json()["input_tokens"]) if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError, KeyError):
        n = None
    if n is None:
        return {**nada, "error": "no puedo contar los tokens de entrada: no llamo"}
    if gastado + reserva(n, effort) > tope:
        return {**nada, "error": f"tope diario: gastado {gastado:.2f} + hasta {reserva(n, effort):.2f} pasaria de {tope:.2f} USD"}
    cuerpo = {"model": MODELO, "max_tokens": MAX_TOKENS[effort], "output_config": {"effort": effort}, "messages": mensajes,
              "system": [{"type": "text", "text": estable, "cache_control": {"type": "ephemeral"}}]}
    peor = {**nada, "llamada": True, "entrada": n, "salida": MAX_TOKENS[effort], "coste": reserva(n, effort), "estimado": True}
    t0 = time.monotonic()
    try:
        r = await http.post(URL, json=cuerpo, headers=cab, timeout=TIMEOUT[effort])
    except httpx.HTTPError as e:  # no se sabe si llego a procesarse: se apunta el peor caso
        return {**peor, "ms": int((time.monotonic() - t0) * 1000), "error": f"Anthropic no contesto ({type(e).__name__}): apunto el peor caso"}
    ms = int((time.monotonic() - t0) * 1000)
    try:
        d = r.json()
    except ValueError:
        d = None
    u = d.get("usage") if isinstance(d, dict) else None
    if not u and r.status_code >= 400:  # un error que contesta (400, 429, 500, 529 overloaded...) no se cobra: 0, dicho
        tipo = ((d or {}).get("error") or {}).get("type", "") if isinstance(d, dict) else ""
        return {**nada, "llamada": True, "entrada": n, "ms": ms, "error": f"Anthropic HTTP {r.status_code} {tipo} (no se cobra)".replace("  ", " ")}
    if not u:
        return {**peor, "ms": ms, "error": f"Anthropic HTTP {r.status_code} sin usage: apunto el peor caso"}
    cache = {"leida": int(u.get("cache_read_input_tokens") or 0), "escrita": int(u.get("cache_creation_input_tokens") or 0)}
    hecho = {**nada, "llamada": True, "entrada": int(u.get("input_tokens") or 0) + cache["leida"] + cache["escrita"],
             "salida": int(u.get("output_tokens") or 0), "coste": coste(u), "cache": cache, "ms": ms}
    if r.status_code != 200:
        return {**hecho, "error": f"Anthropic HTTP {r.status_code}"}
    texto = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()
    if d.get("stop_reason") == "max_tokens":
        texto += "\n(cortado: llego a max_tokens)"
    return {**hecho, "texto": texto, "error": None}
