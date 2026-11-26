"""ESTRUCTURA R1: genera tests/fixtures/estructura_r1_dorado.json corriendo la REFERENCIA (el bridge de 140) sobre las cargas.

La referencia NO esta en el repo (copia del 11-26 de /opt/coinalyze-ai-bridge en 140): se importa de su directorio.
    python3 tests/genera_dorado_estructura.py /srv/coinanalyze/x1-tmp/ref-bridge
Cada paso es el modo alert_only de scheduler.py:159-182 (run_once): build_structural_alert; sin texto,
record_structural_state; con texto, send_message y, si Telegram no lanza, mark_structural_alert_sent. La carga entra
como en analyzer.py:589-599 (collect_payload por /api/ai/context/bundle).
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types

AQUI = pathlib.Path(__file__).parent / "fixtures"


def referencia(ruta: str):
    pkg = types.ModuleType("refbridge")
    pkg.__path__ = [ruta]
    sys.modules["refbridge"] = pkg
    cliente = types.ModuleType("refbridge.coinalyze_client")
    cliente.CoinalyzeClient = object  # analyzer.py:9 solo lo usa como tipo
    sys.modules["refbridge.coinalyze_client"] = cliente
    spec = importlib.util.spec_from_file_location("refbridge.analyzer", pathlib.Path(ruta) / "analyzer.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["refbridge.analyzer"] = mod
    spec.loader.exec_module(mod)
    return mod


class Estado:
    """El StateStore del bridge (state.db) reducido a lo que usan las funciones de estructura."""

    def __init__(self):
        self.kv: dict = {}
        self.t: dict = {}

    def get_kv(self, k):
        return self.kv.get(k)

    def set_kv(self, k, v):
        self.kv[k] = str(v)

    def get_float(self, k, defecto=None):
        return self.t.get(k, defecto)

    def set_float(self, k, v):
        self.t[k] = float(v)


def main(ruta: str):
    an = referencia(ruta)
    cargas = json.loads((AQUI / "estructura_r1_cargas.json").read_text(encoding="utf-8"))
    u = cargas["umbrales"]
    kw = {"floor_usd": float(u["LIQ_BURST_FLOOR_USD"]), "mult": float(u["LIQ_BURST_MULT"]),
          "cooldown_s": float(u["MIN_SEND_INTERVAL_SECONDS"])}
    salida = {"enviar": corre(an, cargas, kw, con_fallos=True), "sombra": corre(an, cargas, kw, con_fallos=False)}
    (AQUI / "estructura_r1_dorado.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print({k: f"{len(v)} pasos, {sum(x['envia'] for x in v)} con aviso" for k, v in salida.items()})


def corre(an, cargas: dict, kw: dict, con_fallos: bool) -> list:
    """enviar: el paso con falla_envio es un Telegram que lanza (no se marca). sombra: todos se dan por entregados."""
    st, salida = Estado(), []
    for p in cargas["pasos"]:
        b = p["carga"]
        payload = an.MarketPayload(generated_at=str(b.get("generated_at")), symbols=[x for x in b["symbols"] if isinstance(x, dict)],
                                   local_alerts=b.get("local_alerts") or [], health={"status": "ok"})
        texto = an.build_structural_alert(payload, st, now=p["ahora"], **kw)
        if not texto:
            an.record_structural_state(payload, st)
        elif not (con_fallos and p["falla_envio"]):
            an.mark_structural_alert_sent(payload, st, now=p["ahora"], **kw)
        salida.append({"texto": texto, "envia": bool(texto), "kv": dict(sorted(st.kv.items())), "t": dict(sorted(st.t.items()))})
    return salida


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/srv/coinanalyze/x1-tmp/ref-bridge")
