"""Despliegue R1: el humo no confunde el arranque de un colector con un fallo. La foto de /api/healthz que tumbo el
despliegue de 11df0b4 (tests/fixtures/healthz_arranque_11df0b4.json, horas relativas al reinicio) da 75 (arranque,
se espera); cualquier otro motivo, una mezcla con un error o el marcador con texto detras siguen dando 86.
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FOTO = json.loads((ROOT / "tests" / "fixtures" / "healthz_arranque_11df0b4.json").read_text(encoding="utf-8"))
REINICIO = 1_800_000_000
MARCA = "collector starting; awaiting successful cycle"


def _x(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _humo(tmp_path: Path, foto: dict) -> subprocess.CompletedProcess:
    sano = copy.deepcopy(foto)
    for row in sano["services"]:
        ts = datetime.datetime.fromtimestamp(REINICIO + row.pop("updated_at_s"), datetime.UTC)
        row["updated_at"] = ts.isoformat()
    (tmp_path / "healthz.json").write_text(json.dumps(sano), encoding="utf-8")
    _x(tmp_path / "systemctl", '#!/bin/sh\n[ "$1" = is-failed ] && exit 1\nexit 0\n')  # todo activo, nada failed
    _x(
        tmp_path / "curl",
        '#!/usr/bin/env bash\nurl=${!#}\ncase "$url" in\n'
        f'  */api/healthz) cat "{tmp_path}/healthz.json" ;;\n'
        "  */api/symbols) printf '[]' ;;\n  *) printf '{}' ;;\nesac\n",
    )
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "METRICS_ENABLED": "false",
        "REQUIRED_SYSTEMD_SERVICES": "coinalyze-api",
        "REQUIRED_HEARTBEATS": "api ingest",
        "DEPLOY_RESTART_EPOCH": str(REINICIO),
        "COINALYZE_ENV_FILE": str(tmp_path / "no-existe.env"),
    }
    return subprocess.run(["bash", str(ROOT / "scripts" / "smoke_test.sh")], env=env,
                          text=True, capture_output=True, check=False)


def _con(**detalles: tuple[str, str]) -> dict:
    """La foto con los servicios dados cambiados a (estado, detalle)."""
    foto = copy.deepcopy(FOTO)
    for row in foto["services"]:
        if row["service"] in detalles:
            row["status"], row["detail"] = detalles[row["service"]]
    return foto


def test_la_foto_real_del_arranque_es_arranque(tmp_path):
    r = _humo(tmp_path, FOTO)
    assert r.returncode == 75, r.stderr
    assert "collector starting since restart: ingest" in r.stderr
    assert "Smoke test OK" not in r.stdout


def test_un_colector_degraded_por_otro_motivo_es_definitivo(tmp_path):
    r = _humo(tmp_path, _con(**{"ingest:metrics_5m": ("degraded", "HTTPStatusError: 429 Too Many Requests")}))
    assert r.returncode == 86, r.stderr
    assert "ingest:metrics_5m reported 'degraded' after the restart: HTTPStatusError" in r.stderr


@pytest.mark.parametrize("estado_ingest", ["degraded", "error"])
def test_un_compuesto_con_arranque_y_error_es_definitivo(tmp_path, estado_ingest):
    # El compuesto SOLO cambia la segunda parte: aunque las filas de componente sigan en arranque, el compuesto manda.
    compuesto = f"metrics_5m=degraded:{MARCA};ohlcv_1m=error:ReadTimeout: upstream"
    r = _humo(tmp_path, _con(ingest=(estado_ingest, compuesto)))
    assert r.returncode == 86, r.stderr
    assert "ingest reported" in r.stderr


@pytest.mark.parametrize("servicio,detalle", [
    ("ingest:ohlcv_1m", MARCA + " (retry 3)"),
    ("ingest:ohlcv_1m", MARCA + ";"),
    ("ingest:ohlcv_1m", "x" + MARCA),
    ("ingest", f"metrics_5m=degraded:{MARCA};ohlcv_1m=degraded:{MARCA} after ValueError"),
    ("ingest", f"metrics_5m=degraded:{MARCA}x;ohlcv_1m=degraded:{MARCA}"),
    ("ingest", f"basura;metrics_5m=degraded:{MARCA}"),
    ("ingest", "metrics_5m=ok:;ohlcv_1m=ok:"),  # degraded sin ninguna parte de arranque
])
def test_el_marcador_con_texto_pegado_es_definitivo(tmp_path, servicio, detalle):
    r = _humo(tmp_path, _con(**{servicio: ("degraded", detalle)}))
    assert r.returncode == 86, r.stderr
    assert f"{servicio} reported 'degraded' after the restart" in r.stderr


def test_un_compuesto_con_arranque_y_ok_es_arranque(tmp_path):
    # ohlcv_1m late cada minuto y metrics_5m cada 300 s (app/ingest.py:1103-1126): unos minutos asi tras el reinicio.
    foto = _con(
        ingest=("degraded", f"metrics_5m=degraded:{MARCA};ohlcv_1m=ok:rows=812 rollup_5m=3"),
        **{"ingest:ohlcv_1m": ("ok", "rows=812 rollup_5m=3")},
    )
    r = _humo(tmp_path, foto)
    assert r.returncode == 75, r.stderr


def test_el_estado_global_error_no_es_arranque_aunque_el_detalle_lo_sea(tmp_path):
    foto = copy.deepcopy(FOTO)
    foto["status"] = "error"
    r = _humo(tmp_path, foto)
    assert r.returncode == 86, r.stderr


def test_cada_marcador_declarado_es_el_texto_que_escribe_su_colector():
    texto = (ROOT / "scripts" / "smoke_test.sh").read_text(encoding="utf-8")
    declarados = re.findall(r'^    ("[^"]+"),  # (app/[a-z_]+\.py):\d+$', texto, flags=re.M)
    assert len(declarados) == 2
    for literal, fuente in declarados:
        assert literal in (ROOT / fuente).read_text(encoding="utf-8"), (literal, fuente)
    assert MARCA in {lit.strip('"') for lit, _ in declarados}
