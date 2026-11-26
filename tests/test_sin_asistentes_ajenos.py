"""PURGA R2: el arbol no nombra asistentes ajenos y lo publicado no filtra la red ni los chats.

1. scripts/sonda_purga_ia.py sobre el arbol versionado da TOTAL 0.
2. docs/, README.md y static/ no publican IPs privadas (10/8, 172.16/12, 192.168/16) ni ids
   de chat de Telegram: un numero de 9 o mas cifras en una linea que habla de chat, telegram o
   ids de usuario, o cualquier -100 seguido de 9 o mas cifras.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SONDA = ROOT / "scripts" / "sonda_purga_ia.py"
PUBLICADO = ["docs", "README.md", "static"]

_OCT = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IP_PRIVADA = re.compile(
    r"(?<![\d.])(?:"
    rf"10\.{_OCT}\.{_OCT}\.{_OCT}"
    rf"|172\.(?:1[6-9]|2\d|3[01])\.{_OCT}\.{_OCT}"
    rf"|192\.168\.{_OCT}\.{_OCT}"
    r")(?![\d.]*\d)"
)
CONTEXTO_CHAT = re.compile(r"chat|telegram|user_?ids?", re.IGNORECASE)
NUMERO_LARGO = re.compile(r"(?<![\d.])-?\d{9,}(?![\d.]*\d)")
SUPERGRUPO = re.compile(r"(?<!\d)-100\d{9,}(?!\d)")


def _versionados(rutas: list[str]) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", *rutas],
        check=True, capture_output=True,
    ).stdout
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def _texto(rel: str) -> str | None:
    datos = (ROOT / rel).read_bytes()
    if b"\0" in datos[:8192]:
        return None
    return datos.decode("utf-8", "replace")


def fugas_publicadas() -> list[str]:
    fugas = []
    for rel in _versionados(PUBLICADO):
        if not (ROOT / rel).is_file():
            continue
        texto = _texto(rel)
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            if IP_PRIVADA.search(linea):
                fugas.append(f"{rel}:{n}: IP privada")
            if SUPERGRUPO.search(linea) or (
                CONTEXTO_CHAT.search(linea) and NUMERO_LARGO.search(linea)
            ):
                fugas.append(f"{rel}:{n}: id de chat")
    return fugas


def test_sonda_purga_ia_total_cero():
    r = subprocess.run(
        [sys.executable, str(SONDA), "--repo", str(ROOT)],
        capture_output=True, text=True,
    )
    ultima = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    assert ultima == "TOTAL 0" and r.returncode == 0, r.stdout[-2000:] + r.stderr[-500:]


def test_publicado_sin_ip_privada_ni_id_de_chat():
    fugas = fugas_publicadas()
    # Solo fichero:linea y el tipo: el valor no se repite en la salida.
    assert not fugas, f"{len(fugas)} fugas:\n" + "\n".join(fugas[:60])


def test_detector_muerde():
    """Los patrones casan lo que deben y no lo que no (sin valores reales)."""
    assert IP_PRIVADA.search("host 192.168.0.9 dentro")
    assert IP_PRIVADA.search("`172.20.1.2:22`")
    assert IP_PRIVADA.search("red 10.0.0.0/28")
    assert not IP_PRIVADA.search("172.32.0.1 y 110.1.2.3 y 8.8.8.8")
    assert not IP_PRIVADA.search("version 1.10.2.3.4")
    assert SUPERGRUPO.search('X="-100123456789"')
    assert CONTEXTO_CHAT.search("TELEGRAM_CHAT_ID=1") and NUMERO_LARGO.search('["123456789"]')
    assert not (CONTEXTO_CHAT.search("CVD 418000000.51") and NUMERO_LARGO.search("418000000.51"))
    assert not NUMERO_LARGO.search("418000000.51")
