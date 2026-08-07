#!/usr/bin/env python3
"""Aplica el cambio de /preview -> perfil `max` en el bridge de Telegram.

No usa `patch`: el LXC no lo trae instalado. Cada reemplazo lleva su conteo esperado, asi
que si el fuente no es el que se espera aborta sin escribir nada. Es idempotente: si ya
esta aplicado, lo dice y sale con 0.

    /opt/coinalyze-ai-bridge/.venv/bin/python apply.py [--src RUTA]

Despues hay que reinstalar (el bridge se instala como COPIA, no editable) y reiniciar:

    cd /opt/coinalyze-ai-bridge && ./.venv/bin/pip install --no-deps .
    systemctl restart coinalyze-ai-bridge
"""
from __future__ import annotations

import argparse
import pathlib
import sys

EDITS: dict[str, list[tuple[str, str]]] = {
    "config.py": [
        (
            "    telegram_preview_single_delivery: bool\n"
            "    telegram_preview_document_if_large: bool\n",
            "    telegram_preview_single_delivery: bool\n"
            "    telegram_preview_document_if_large: bool\n"
            "    telegram_preview_profile: str\n",
        ),
        (
            '            telegram_preview_document_if_large=_bool_env(\n'
            '                "TELEGRAM_PREVIEW_DOCUMENT_IF_LARGE", True\n'
            '            ),\n',
            '            telegram_preview_document_if_large=_bool_env(\n'
            '                "TELEGRAM_PREVIEW_DOCUMENT_IF_LARGE", True\n'
            '            ),\n'
            '            # /preview no gasta tokens de OpenAI: su salida se pega a mano en una IA web,\n'
            '            # asi que pide el perfil completo del dashboard (historico diario incluido).\n'
            '            telegram_preview_profile=_env("TELEGRAM_PREVIEW_PROFILE", "max").strip() or "max",\n',
        ),
    ],
    "scheduler.py": [
        (
            '            payload = await self._collect_market_payload(symbols, profile_name="default")\n'
            '            text = build_preview_text(payload)',
            '            profile = self.settings.telegram_preview_profile\n'
            '            payload = await self._collect_market_payload(symbols, profile_name=profile)\n'
            '            text = build_preview_text(payload)',
        ),
        (
            '                    caption=(\n'
            '                        "PREVIEW completo para ChatGPT. No se consumieron tokens de OpenAI. "\n'
            '                        "Se envía como un solo JSON porque excede el límite de texto de Telegram."\n'
            '                    ),',
            '                    caption=(\n'
            '                        f"PREVIEW completo (perfil {profile}) para pegar en una IA web. "\n'
            '                        "No se consumieron tokens de OpenAI. Se envía como un solo JSON "\n'
            '                        "porque excede el límite de texto de Telegram."\n'
            '                    ),',
        ),
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--src",
        default="/opt/coinalyze-ai-bridge/src/coinalyze_ai_bridge",
        help="carpeta del paquete coinalyze_ai_bridge",
    )
    args = parser.parse_args()
    root = pathlib.Path(args.src)
    if not root.is_dir():
        print(f"ERROR: no existe {root}", file=sys.stderr)
        return 1

    planned: list[tuple[pathlib.Path, str]] = []
    already = 0
    for name, edits in EDITS.items():
        path = root / name
        if not path.is_file():
            print(f"ERROR: falta {path}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        for old, new in edits:
            if new in text:
                already += 1
                continue
            if text.count(old) != 1:
                print(
                    f"ERROR: {name} no coincide con lo esperado "
                    f"({text.count(old)} coincidencias de un bloque). No se escribio nada.",
                    file=sys.stderr,
                )
                return 1
            text = text.replace(old, new)
        planned.append((path, text))

    total = sum(len(v) for v in EDITS.values())
    if already == total:
        print("El parche ya estaba aplicado. Nada que hacer.")
        return 0

    for path, text in planned:
        path.write_text(text, encoding="utf-8")
        print(f"OK {path.name}")
    print(
        "\nHecho. Ahora:\n"
        '  1) anade TELEGRAM_PREVIEW_PROFILE="max" a '
        "/etc/coinalyze-ai-bridge/coinalyze-ai-bridge.env\n"
        "  2) cd /opt/coinalyze-ai-bridge && ./.venv/bin/pip install --no-deps .\n"
        "  3) systemctl restart coinalyze-ai-bridge"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
