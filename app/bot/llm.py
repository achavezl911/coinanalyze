"""Opus 5.5 con effort xhigh, por HTTP directo con httpx (ya es dependencia, requirements.lock:11: el SDK no aporta
nada a dos POST). Precio de platform.claude.com/docs/en/about-claude/pricing (leido el 2026-10-24): 4 USD/MTok de
entrada, 20 USD/MTok de salida; en Opus 5.5 el thinking adaptativo no se apaga y cuenta como salida.

EL TOPE: antes de llamar se cuentan los tokens de entrada exactos (count_tokens, gratis) y se reserva el peor caso
(entrada x 1.02 + MAX_TOKENS enteros de salida). Si lo gastado hoy + la reserva pasa del tope, NO se llama. Si la
llamada cae sin decir lo que gasto, se apunta la reserva entera (estimado). Las llamadas van en fila (un candado en
el servicio), asi que dos no pueden pasarse juntas.
"""

from __future__ import annotations

import httpx

URL = "https://api.anthropic.com/v1/messages"
MODELO, EFFORT, MAX_TOKENS = "claude-opus-5-5", "xhigh", 16000
PRECIO = {"input_tokens": 4e-6, "output_tokens": 20e-6,
          "cache_creation_input_tokens": 5e-6, "cache_read_input_tokens": 0.2e-6}


def coste(usage: dict) -> float:
    return sum(p * (usage.get(k) or 0) for k, p in PRECIO.items())


def reserva(tokens_entrada: int) -> float:
    return tokens_entrada * PRECIO["input_tokens"] * 1.02 + MAX_TOKENS * PRECIO["output_tokens"]


async def llama(http: httpx.AsyncClient, clave: str, system: str, texto: str, gastado: float, tope: float) -> dict:
    """-> texto (None si no hubo respuesta), error, y lo que hay que apuntar: llamada (bool), entrada, salida, coste,
    estimado. llamada=False: no se llamo a messages y no hay nada que apuntar."""
    cab = {"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    cuerpo = {"model": MODELO, "system": system, "messages": [{"role": "user", "content": texto}]}
    nada = {"texto": None, "llamada": False, "entrada": 0, "salida": 0, "coste": 0.0, "estimado": False}
    try:
        r = await http.post(f"{URL}/count_tokens", json=cuerpo, headers=cab, timeout=30)
        n = int(r.json()["input_tokens"]) if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError, KeyError):
        n = None
    if n is None:
        return {**nada, "error": "no puedo contar los tokens de entrada: no llamo"}
    if gastado + reserva(n) > tope:
        return {**nada, "error": f"tope diario: gastado {gastado:.2f} + hasta {reserva(n):.2f} pasaria de {tope:.2f} USD"}
    peor = {**nada, "llamada": True, "entrada": n, "salida": MAX_TOKENS, "coste": reserva(n), "estimado": True}
    try:
        r = await http.post(URL, json={**cuerpo, "max_tokens": MAX_TOKENS, "output_config": {"effort": EFFORT}},
                            headers=cab, timeout=900)
        d = r.json()
    except (httpx.HTTPError, ValueError) as e:
        return {**peor, "error": f"Anthropic no contesto ({type(e).__name__}): apunto el peor caso"}
    u = d.get("usage") if isinstance(d, dict) else None
    if not u:
        return {**peor, "error": f"Anthropic HTTP {r.status_code} sin usage: apunto el peor caso"}
    hecho = {**nada, "llamada": True, "entrada": int(u.get("input_tokens") or 0),
             "salida": int(u.get("output_tokens") or 0), "coste": coste(u)}
    if r.status_code != 200:
        return {**hecho, "error": f"Anthropic HTTP {r.status_code}"}
    texto = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()
    if d.get("stop_reason") == "max_tokens":
        texto += "\n(cortado: llego a max_tokens)"
    return {**hecho, "texto": texto, "error": None}
