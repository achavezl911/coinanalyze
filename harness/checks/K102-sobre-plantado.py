#!/usr/bin/env python3
"""Un servidor que sirve la mesa DEL ARBOL y un `/api/mesa/decide` PLANTADO.

POR QUE HACE FALTA. Dos de las promesas de K102 no se pueden ejercitar contra un backend de
verdad, y no por comodidad sino porque el sujeto no existe alli:

  · R3 · «pasado `max_age_s` la pantalla lo dice SIN que nadie recargue» necesita un DECIDE
    FRESCO -lag pequeno- y un tope que se CRUCE mientras se mira. El espejo de 143 sirve un
    snapshot de hace 46 dias: nace rancio, asi que con el no se puede ver la TRANSICION, que es
    justo lo que se promete. Y produccion no sirve la ruta todavia.
  · R1 · «en un marco que no es scalp la palabra no es la del scalp» se ve mejor cuando el
    scalp SI tiene veredicto. Con data_confidence 0 -lo que da el espejo- los tres marcos
    saldrian NO EVALUABLE por motivos distintos y el plantado no distinguiria nada.

LO QUE ESTE SERVIDOR NO ES: no es la mesa, y no se parece a produccion. Sirve un sobre
CONSTRUIDO, lo dice en el propio sobre (`plantado`), y solo lo usa el control. La mesa real se
mide contra el espejo y contra 140.

  --lag N      segundos de `snapshot_lag_seconds` en el sobre servido
  --tope N     `max_age_s` del sobre servido
  --bias X     LONG | SHORT | NEUTRAL  (el veredicto del scalp)
  --dc N       `data_confidence.quality_score`
"""
from __future__ import annotations

import argparse
import http.server
import json
import pathlib
from datetime import UTC, datetime

REPO = pathlib.Path("/srv/coinanalyze/repo")
TIPOS = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8"}
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)
CFG: dict = {}


def campo(v, k, estado="ok"):
    return {"value": v, "source_key": k, "status": estado}


_pedidas = {"n": 0}


def sobre(frame: str) -> dict:
    ahora = datetime.now(UTC)
    _pedidas["n"] += 1
    lag = float(CFG["lag"])
    tope = float(CFG["tope"])
    bias = CFG["bias"]
    dc = float(CFG["dc"])
    evaluable = dc >= 70.0
    es_scalp = frame == "scalp"

    # EL SOBRE PLANTADO TIENE QUE TENER LA MISMA FORMA QUE LA RUTA, o los controles verifican
    # un contrato que no existe. Aqui se reproducen los DOS veredictos de `build_mesa_decide`:
    # el del SCALP -que solo depende de la calidad- y el del MARCO.
    if not evaluable:
        bias_scalp, src_scalp = "NO EVALUABLE", "data_confidence.quality_score"
        motivo_scalp = f"data_confidence {dc} < 70"
    else:
        bias_scalp, src_scalp, motivo_scalp = bias, "operator_read.bias", None

    if not es_scalp:
        display, src = "NO EVALUABLE", "mesa.decide.frame"
        motivo = f"la lectura del operador es del SCALP, no de {frame.upper()}"
    else:
        display, src, motivo = bias_scalp, src_scalp, motivo_scalp

    d = {
        "schema_version": "mesa.decide.v1",
        "plantado": (
            "SOBRE CONSTRUIDO por K102-sobre-plantado.py para un control. NO es un dato de "
            "mercado y no sale de ninguna base"
        ),
        "symbol": "BTCUSDT_PERP.A",
        "asset": "BTC",
        "frame": frame,
        "generated_at": ahora.isoformat(),
        "max_age_s": tope,
        "no_evaluable_under": 70.0,
        "envelope_cut": {"as_of": ahora.isoformat(), "snapshot": "repeatable_read",
                         "snapshot_reason": None, "meaning": "plantado"},
        "age": {
            "snapshot_lag_seconds": campo(lag, "data_confidence.snapshot_lag_seconds"),
            "price_cutoff_at": campo(ahora.isoformat(), "snapshot.price_cutoff_at"),
            "metrics_cutoff_at": campo(ahora.isoformat(), "snapshot.metrics_cutoff_at"),
            "stale": lag > tope,
            "stale_rule": f"snapshot_lag_seconds > max_age_s ({tope:g} s)",
        },
        "decide": {
            "bias": {"value": display, "source_key": src, "status": "ok",
                     "raw": bias, "motivo": motivo},
            "evaluable": {"value": evaluable, "source_key": "data_confidence.quality_score",
                          "status": "ok", "threshold": 70.0,
                          "rule": "handoff: data_confidence por debajo de 70 -> NO EVALUABLE"},
            "zone": {
                "center": campo(63244.77, "price_barriers.active_zone.center"),
                "low": campo(63067.46, "price_barriers.active_zone.low"),
                "high": campo(63509.14, "price_barriers.active_zone.high"),
                "difficulty": campo("fuerte", "price_barriers.active_zone.difficulty"),
            },
            "zone_decision": campo("ESPERAR: zona en disputa", "price_barriers.decision"),
            "structural_invalidation": campo(
                62999.99, "structure_detail.horizons.1h.invalidation_level"),
            "structural_horizon": campo("1h", "structure_detail.horizons.1h"),
            "data_confidence": campo(dc, "data_confidence.quality_score"),
        },
    }
    lectura = {
        "state": campo("Long Pullback", "operator_read.state"),
        "reason": campo("ΔFut1m -742774, book ok/L5 0.47", "scalp.reason"),
        "confidence": campo("media", "operator_read.confidence"),
        # CON `--varia`, EL SOBRE CAMBIA EN CADA PETICION. Reproduce lo que hace el mercado de
        # verdad -20 de 20 parejas de `/api/scalp/summary` separadas 2 s traen `edge` distinto,
        # medido en 140 el 2026-09-29T06:03Z- y es el gemelo que desenmascara a una red que
        # compare la pantalla contra un sobre pedido APARTE.
        "edge": campo(
            round(80.2 + (_pedidas["n"] - 1 if CFG.get("varia") else 0), 2),
            "operator_read.edge",
        ),
        "evidence": campo(71.429, "scalp.evidence_coverage_pct"),
        "confirms": [campo("Rechazo confirmado sobre 62736.46",
                           "price_barriers.long_case.rejection")],
        "invalidates": [campo("price_rejects_below_vwap", "operator_read.invalidates_long[0]")],
        "invalidation_level": campo(63385.45, "price_barriers.nearest_support.center"),
        "horizon": {"value": "mediana 1 min · p90 3 min", "source_key": "scalp_persistence.etiqueta",
                    "status": "ok", "outside_cut": True, "dias": 30},
        "no_trade_reasons": campo([], "operator_read.no_trade_reasons"),
        "warnings": campo([], "operator_read.warnings"),
    }
    if es_scalp:
        d["decide"].update(lectura)
    else:
        d["lectura_scalp"] = {
            "de_marco": "scalp",
            "aviso": f"lectura del SCALP, no un veredicto de {frame.upper()}",
            "donde": "/mesa#scalp/BTC",
            "ventana": "deltas de 1 y 3 min, libro L5, liquidaciones de 5 min",
            # SU PROPIO VEREDICTO, igual que lo sirve la ruta. Sin esto el plantado no podria
            # ejercitar R5 y las capturas ensenarian una tarjeta sin lado.
            "bias": {"value": bias_scalp, "source_key": src_scalp, "status": "ok",
                     "raw": bias, "motivo": motivo_scalp},
            **lectura,
        }
    d["build_started_at"] = ahora.isoformat()
    d["build_finished_at"] = ahora.isoformat()
    return d


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _envia(self, codigo, cuerpo: bytes, tipo: str):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        try:
            self.wfile.write(cuerpo)
        except BrokenPipeError:
            pass

    def do_GET(self):  # noqa: N802
        ruta, _, cola = self.path.partition("?")
        if ruta == "/api/mesa/decide":
            frame = "scalp"
            for t in cola.split("&"):
                if t.startswith("frame="):
                    frame = t[len("frame="):]
            if CFG.get("sin_refresco") and _pedidas["n"] >= 1:
                # Se declara el fallo, no se disfraza: la mesa lo pintara como ERROR y la edad
                # del sobre que YA tiene seguira corriendo, que es lo que se quiere observar.
                self._envia(503, b'{"error":"sin refresco: es lo que este control mide"}',
                            "application/json")
                return
            self._envia(200, json.dumps(sobre(frame)).encode(), "application/json")
            return
        if ruta.startswith("/api/"):
            # LAS DEMAS RUTAS NO SE INVENTAN: se dice que no estan. Un panel relleno de datos
            # falsos seria justo lo contrario de lo que mide este control.
            self._envia(503, b'{"error":"este banco solo sirve /api/mesa/decide"}',
                        "application/json")
            return
        f = REPO / "static" / "mesa.html" if ruta == "/mesa" else None
        if ruta.startswith("/static/"):
            try:
                f = (REPO / "static" / ruta[len("/static/"):]).resolve()
                f.relative_to((REPO / "static").resolve())
            except (ValueError, OSError):
                self._envia(403, b"no", "text/plain")
                return
        if not f or not f.is_file():
            self._envia(404, b"no", "text/plain")
            return
        self._envia(200, f.read_bytes(), TIPOS.get(f.suffix, "application/octet-stream"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--puerto", type=int, default=8096)
    ap.add_argument("--lag", type=float, default=5.0)
    ap.add_argument("--tope", type=float, default=120.0)
    ap.add_argument("--bias", default="LONG", choices=("LONG", "SHORT", "NEUTRAL"))
    ap.add_argument("--dc", type=float, default=100.0)
    ap.add_argument("--varia", action="store_true",
                    help="el sobre cambia en CADA peticion (edge +1), como el mercado")
    ap.add_argument(
        "--sin-refresco",
        action="store_true",
        help="devuelve 503 a partir de la SEGUNDA peticion. Para ver la transicion a RANCIO "
             "hace falta que el dato NO se renueve: si se renueva, la edad se reinicia y la "
             "transicion no llega a ocurrir",
    )
    a = ap.parse_args()
    CFG.update(vars(a))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.puerto), H)
    print(f"plantado en http://127.0.0.1:{a.puerto} lag={a.lag} tope={a.tope} "
          f"bias={a.bias} dc={a.dc}", flush=True)
    srv.serve_forever()
