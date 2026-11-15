"""EL PROPONENTE del simulador ciego (S2): `claude -p` con la foto y unas instrucciones FIJAS por la entrada estandar,
SIN NINGUNA HERRAMIENTA, en el plan Max de quien lo lanza (sin ANTHROPIC_API_KEY en el entorno).

Aislamiento, por la orden (ver `orden`): --tools "" (ninguna herramienta: no lee ficheros ni ejecuta nada), --safe-mode
(sin CLAUDE.md, skills, plugins, hooks ni MCP), --strict-mcp-config sin --mcp-config (ningun servidor MCP),
--disable-slash-commands, --system-prompt propio (sustituye al de serie, que lleva la fecha de hoy, el directorio y el
estado de git), --no-session-persistence, y el directorio de trabajo es una carpeta temporal VACIA.
Y se COMPRUEBA en cada llamada: con --output-format stream-json el primer mensaje (system/init) lista las herramientas
y los servidores MCP de la sesion; si alguna de las dos listas no esta vacia, la respuesta es INVALIDA y no se usa.
La respuesta valida es un JSON diario-entradas/1 (fuentes.py, buzon) en precios ESCALADOS y tiempos desde AHORA, o
«ninguna»; `lee` lo rechaza con motivo si no lo es.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile

from app.diario.fuentes import FORMATO

MODELO = "claude-fable-5-2"
EFFORT = "medium"
MAX_PROPUESTAS = 3
SISTEMA = "Eres un operador de futuros perpetuos. Respondes SOLO con el JSON que se te pide, sin texto alrededor."
INSTRUCCIONES = """Abajo hay una FOTO de un mercado perpetuo de cripto: solo el pasado hasta AHORA, con los precios
escalados por un factor desconocido y sin fechas. No sabes que activo es ni en que fecha estas: decide con lo que ves.

Propon de 0 a 3 entradas que abririas AHORA, o ninguna. La forma de cada entrada:
- riesgo 5 USD (riesgo_usd: 5);
- stop en la estructura (un minimo o un maximo que invalide la idea), a ~1.5-5 % de la entrada;
- objetivo a ~2 R (dos veces la distancia de la entrada al stop);
- orden "limite" (largo: entrada por debajo del ultimo cierre; corto: por encima) o "mercado" (se llena en la
  apertura de la siguiente vela de 5 min; su entrada es el ultimo cierre, solo como referencia);
- caduca: SEGUNDOS desde AHORA durante los que vale el llenado del limite, como mucho 432000 (5 dias);
- plazo_h: HORAS que puede estar abierta tras llenarse, como mucho 240 (10 dias);
- porque: una frase.
Todos los precios en las MISMAS unidades escaladas de la foto; "activo" es la letra de la foto.

Responde SOLO con este JSON, sin texto alrededor:
{"formato": "diario-entradas/1", "propuestas": [{"id": "1", "activo": "<letra>", "lado": "largo|corto",
 "orden": "limite|mercado", "entrada": <precio>, "stop": <precio>, "objetivo": <precio>, "caduca": <segundos>,
 "plazo_h": <horas>, "riesgo_usd": 5, "porque": "<una frase>"}]}
Si no abririas ninguna: {"formato": "diario-entradas/1", "propuestas": []}
"""
HUELLA = hashlib.sha256((SISTEMA + "\n" + INSTRUCCIONES).encode()).hexdigest()


def orden(modelo: str = MODELO, effort: str = EFFORT, binario: str = "claude", tope_usd: float = 2.0) -> list[str]:
    return [binario, "-p", "--model", modelo, "--effort", effort, "--tools", "", "--safe-mode", "--strict-mcp-config",
            "--disable-slash-commands", "--no-session-persistence", "--system-prompt", SISTEMA,
            "--output-format", "stream-json", "--verbose", "--max-budget-usd", f"{tope_usd:g}"]


def pide(foto: str, modelo: str = MODELO, effort: str = EFFORT, binario: str | None = None, timeout: int = 1200,
         tope_usd: float = 2.0) -> dict:
    """Una llamada. Devuelve el registro a guardar: texto, coste, uso, herramientas vistas y `error` (None si valida)."""
    binario = binario or os.environ.get("DIARIO_CIEGO_CLAUDE", "claude")
    cmd = orden(modelo, effort, binario, tope_usd)
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    reg = {"modelo_pedido": modelo, "effort": effort, "instrucciones_sha256": HUELLA, "orden": cmd[1:], "error": None}
    with tempfile.TemporaryDirectory(prefix="ciego-vacio-") as vacio:
        try:
            r = subprocess.run(cmd, input=INSTRUCCIONES + "\n" + foto, cwd=vacio, env=env, capture_output=True,
                               text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {**reg, "error": f"no corrio: {type(e).__name__} {str(e)[:200]}"}
    init, res, limite = None, None, None
    for ln in r.stdout.splitlines():
        try:
            m = json.loads(ln)
        except ValueError:
            continue
        if m.get("type") == "system" and m.get("subtype") == "init" and init is None:
            init = m
        elif m.get("type") == "result":
            res = m
        elif m.get("type") == "rate_limit_event":
            limite = m
    reg.update({"rc": r.returncode, "stderr": r.stderr[-400:], "herramientas": (init or {}).get("tools"),
                "mcp": (init or {}).get("mcp_servers"), "modelo": (init or {}).get("model"),
                "texto": (res or {}).get("result"), "coste_usd": (res or {}).get("total_cost_usd"),
                "uso": (res or {}).get("usage"), "duracion_ms": (res or {}).get("duration_ms"),
                "limite": (limite or {}).get("rate_limit_info", limite)})
    if init is None:
        reg["error"] = f"sin mensaje init (rc={r.returncode}): {(r.stderr or r.stdout)[-200:]}"
    elif init.get("tools") != [] or init.get("mcp_servers") not in ([], None):
        reg["error"] = f"el proponente TENIA herramientas {init.get('tools')} / MCP {init.get('mcp_servers')}: invalida"
    elif res is None or res.get("is_error") or r.returncode != 0:
        reg["error"] = f"sin resultado valido (rc={r.returncode}): {str((res or {}).get('result') or r.stderr)[-200:]}"
    return reg


def lee(texto: str | None) -> tuple[list, str | None]:
    """(propuestas crudas, None) o ([], motivo). «ninguna» o una lista vacia son una respuesta valida sin propuestas."""
    s = (texto or "").strip()
    if not s:
        return [], "respuesta vacia"
    if s.strip(" .«»\"'`").lower() == "ninguna":
        return [], None
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, re.S)
    if m:
        s = m.group(1)
    if not s.startswith("{") and "{" in s:
        s = s[s.find("{"):s.rfind("}") + 1]
    try:
        d = json.loads(s)
    except ValueError as e:
        return [], f"la respuesta no es JSON ({str(e)[:80]})"
    if not isinstance(d, dict) or d.get("formato") != FORMATO or not isinstance(d.get("propuestas"), list):
        return [], f"no es {FORMATO} con una lista `propuestas`"
    if len(d["propuestas"]) > MAX_PROPUESTAS:
        return [], f"{len(d['propuestas'])} propuestas: como mucho {MAX_PROPUESTAS}"
    return d["propuestas"], None
