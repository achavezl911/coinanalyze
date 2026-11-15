"""DATOS B (fable-f4 H1): el despliegue que se defiende. deploy/140/deploy-coinalyze corrido ENTERO contra dobles:
sus rutas reescritas a un tmp, y systemctl, curl, pg_dump, psql y chown en el PATH. El curl doble sirve un healthz
por guion y apunta su argv: asi se ve que el token no viaja en el argv. Sin base ni red.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "token-de-prueba-que-no-sale-en-argv"
NUEVO = "a" * 40
VIEJO = "b" * 40

SYSTEMCTL = """#!/usr/bin/env bash
# Doble de systemctl: apunta cada llamada; is-active/is-failed segun el estado que dejan stop/start/restart.
echo "$*" >> "$SB/systemctl.log"
cmd=$1; shift
[ "${1:-}" = --quiet ] && shift
case "$cmd" in
  stop) for u in "$@"; do touch "$SB/parado-$u"; done ;;
  start|restart) for u in "$@"; do rm -f "$SB/parado-$u"; done ;;
  is-failed) [ "${FAILED_UNIT:-}" = "$1" ] ;;
  is-active) [ "${FAILED_UNIT:-}" != "$1" ] && [ ! -e "$SB/parado-$1" ] ;;
  *) exit 0 ;;
esac
"""

# healthz por guion: ESCENA=arranca:N da N respuestas «degraded» con el latido de ingest de antes del reinicio y luego
# «ok»; ESCENA=muerto, siempre «degraded» (el colector no vuelve); ESCENA=error, el latido de ingest en error DESPUES
# del reinicio.
CURL = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$SB/curl.argv"
url=${!#}
ahora=$(date -u +%FT%TZ)
case "$url" in
  */api/healthz)
    n=$(cat "$SB/healthz.n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$SB/healthz.n"
    estado=ok; ingest_ts=$ahora; ingest_st=ok
    case "$ESCENA" in
      arranca:*) [ "$n" -le "${ESCENA#arranca:}" ] && { estado=degraded; ingest_ts=1970-01-01T00:00:00Z; } ;;
      muerto) estado=degraded; ingest_ts=1970-01-01T00:00:00Z ;;
      error) estado=degraded; ingest_st=error ;;
    esac
    printf '{"status":"%s","missing_services":[],"missing_symbols":[],"informative_services":[],"symbols":[],' "$estado"
    printf '"services":[{"service":"api","status":"ok","updated_at":"%s"},' "$ahora"
    printf '{"service":"ingest","status":"%s","updated_at":"%s","detail":"x"},' "$ingest_st" "$ingest_ts"
    printf '{"service":"ws","status":"ok","updated_at":"%s"},{"service":"scalp","status":"ok","updated_at":"%s"}]}' "$ahora" "$ahora"
    ;;
  */api/symbols) printf '[{"symbol":"BTCUSDT_PERP.A"}]' ;;
  *) printf '{}' ;;
esac
"""

PYTHON3 = f"""#!/usr/bin/env bash
# python3 -m venv DIR: un venv de mentira con un pip que no hace nada. Lo demas, el python de verdad.
if [ "${{1:-}}" = -m ] && [ "${{2:-}}" = venv ]; then
  mkdir -p "$3/bin"; printf '#!/bin/sh\\nexit 0\\n' > "$3/bin/pip"; chmod 755 "$3/bin/pip"; exit 0
fi
exec {sys.executable} "$@"
"""


def _x(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _release(d: Path) -> None:
    for sub in ("app", "static", "sql", "scripts"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    (d / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (d / "requirements.lock").write_text("", encoding="utf-8")
    (d / "sql" / "schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
    shutil.copy(ROOT / "scripts" / "smoke_test.sh", d / "scripts" / "smoke_test.sh")


def _banco(tmp_path: Path, *, recupera: bool = False, smoke_max: int = 3) -> dict:
    sb = tmp_path
    bin_ = sb / "bin"
    bin_.mkdir(parents=True)
    _x(bin_ / "systemctl", SYSTEMCTL)
    _x(bin_ / "curl", CURL)
    _x(bin_ / "python3", PYTHON3)
    _x(bin_ / "pg_dump", "#!/bin/sh\necho volcado\n")
    _x(bin_ / "psql", "#!/bin/sh\necho 0\n")
    _x(bin_ / "chown", "#!/bin/sh\nexit 0\n")
    app = sb / "opt"
    (app / "releases").mkdir(parents=True)
    _release(app / "releases" / VIEJO)
    (app / "current").symlink_to(app / "releases" / VIEJO)
    units = sb / "units"
    units.mkdir()
    for u in ("coinalyze-api", "coinalyze-ingest", "coinalyze-ws", "coinalyze-scalp", "coinalyze-daily"):
        (units / f"{u}.service").write_text(f"WorkingDirectory={app / 'current'}\n", encoding="utf-8")
    if recupera:
        (units / "coinalyze-recupera.timer").write_text("[Timer]\n", encoding="utf-8")
        (units / "coinalyze-recupera.service").write_text("[Service]\n", encoding="utf-8")
    env_file = sb / "coinalyze.env"
    env_file.write_text(f"PG_USER=u\nPG_DB=d\nAPI_INTERNAL_TOKEN={TOKEN}\nMETRICS_ENABLED=false\n", encoding="utf-8")
    incoming = sb / "incoming"
    incoming.mkdir()
    fuente = sb / "fuente"
    _release(fuente)
    art = incoming / "art.tar.gz"
    with tarfile.open(art, "w:gz") as t:
        t.add(fuente, arcname=".")
    rutas = {
        "APP_ROOT": app, "STATE": sb / "deployment.json", "LOGDIR": sb / "log", "ENV_FILE": env_file,
        "INCOMING": incoming, "BACKUPDIR": sb / "backups", "LOCKFILE": sb / "lock", "UNIT_DIR": units,
        "SMOKE_MAX_WAIT": smoke_max, "SMOKE_SLEEP": 1,
    }
    texto = (ROOT / "deploy" / "140" / "deploy-coinalyze").read_text(encoding="utf-8")
    for k, v in rutas.items():
        texto, n = re.subn(rf"^{k}=.*$", f"{k}={v}", texto, count=1, flags=re.M)
        assert n == 1, k
    texto = texto.replace('[ "$(id -u)" -eq 0 ] ||', "true ||", 1)
    wrapper = sb / "deploy-coinalyze"
    _x(wrapper, texto)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "SB": str(sb), "ESCENA": "arranca:0"}
    env.pop("FAILED_UNIT", None)
    return {"sb": sb, "app": app, "wrapper": wrapper, "art": art, "env": env,
            "sha": hashlib.sha256(art.read_bytes()).hexdigest()}


def _despliega(b: dict, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(b["wrapper"]), "deploy", str(b["art"]), b["sha"], NUEVO],
                          env={**b["env"], **env}, text=True, capture_output=True, timeout=120, check=False)


def _current(b: dict) -> str:
    return Path(os.readlink(b["app"] / "current")).name


def _log(b: dict, nombre: str) -> str:
    f = b["sb"] / nombre
    return f.read_text(encoding="utf-8") if f.exists() else ""


def test_un_degraded_de_arranque_que_pasa_a_ok_no_revierte(tmp_path):
    b = _banco(tmp_path, smoke_max=30)
    r = _despliega(b, ESCENA="arranca:2")
    assert r.returncode == 0, r.stderr[-2000:]
    assert f"DEPLOY_OK {NUEVO}" in r.stdout
    assert _current(b) == NUEVO
    assert int(_log(b, "healthz.n")) == 3  # dos «degraded» de arranque esperados, el tercero «ok»


def test_un_colector_que_no_vuelve_da_degraded_y_revierte(tmp_path):
    b = _banco(tmp_path, smoke_max=3)
    r = _despliega(b, ESCENA="muerto")
    assert r.returncode == 10, r.stderr[-2000:]
    assert "smoke FAILED after 3s" in r.stderr
    assert "restoring previous release" in r.stderr
    assert _current(b) == VIEJO
    assert "restart coinalyze-api" in _log(b, "systemctl.log")
    assert not (b["sb"] / "deployment.json").exists()


def test_un_latido_en_error_tras_el_reinicio_revierte_sin_esperar(tmp_path):
    b = _banco(tmp_path, smoke_max=60)
    t0 = time.monotonic()
    r = _despliega(b, ESCENA="error")
    assert r.returncode == 10, r.stderr[-2000:]
    assert "definitive" in r.stderr and "ingest reported 'error' after the restart" in r.stderr
    assert time.monotonic() - t0 < 30  # no se agota la espera de 60 s
    assert _current(b) == VIEJO


def test_una_unidad_failed_revierte_sin_esperar(tmp_path):
    b = _banco(tmp_path, smoke_max=60)
    t0 = time.monotonic()
    r = _despliega(b, FAILED_UNIT="coinalyze-ingest")
    assert r.returncode == 10, r.stderr[-2000:]
    assert "coinalyze-ingest (failed)" in r.stderr
    assert time.monotonic() - t0 < 30
    assert _current(b) == VIEJO


def test_el_token_no_viaja_en_el_argv_de_curl(tmp_path):
    b = _banco(tmp_path)
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    argv = _log(b, "curl.argv")
    assert "/api/healthz" in argv and "-H @" in argv
    assert TOKEN not in argv and TOKEN not in r.stderr and TOKEN not in _log(b, "log/deploy.log")


def test_el_smoke_corre_todo_smoke_test_sh(tmp_path):
    b = _banco(tmp_path)
    assert _despliega(b).returncode == 0
    argv = _log(b, "curl.argv")
    for ruta in ("/api/symbols", "/api/ai/profiles", "/api/dashboard/state", "/api/external-macro"):
        assert ruta in argv, ruta


def test_el_recuperador_se_para_y_se_arranca_solo_si_esta_instalado(tmp_path):
    b = _banco(tmp_path / "con", recupera=True)
    assert _despliega(b).returncode == 0
    lineas = _log(b, "systemctl.log").splitlines()
    i_opt = lineas.index("stop coinalyze-recupera.timer coinalyze-recupera.service")
    i_app = next(i for i, x in enumerate(lineas) if x.startswith("stop coinalyze-api"))
    i_start = next(i for i, x in enumerate(lineas) if x.startswith("start coinalyze-api"))
    assert i_opt < i_app < i_start < lineas.index("start coinalyze-recupera.timer")

    s = _banco(tmp_path / "sin")
    assert _despliega(s).returncode == 0
    assert "recupera" not in _log(s, "systemctl.log")


def test_un_release_sin_el_contrato_de_smoke_no_pasa(tmp_path):
    b = _banco(tmp_path)
    viejo = b["app"] / "releases" / VIEJO / "scripts" / "smoke_test.sh"
    viejo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    r = subprocess.run(["bash", str(b["wrapper"]), "status"], env=b["env"], text=True, capture_output=True,
                       timeout=60, check=False)
    assert r.returncode == 1 and "smoke: FAILED" in r.stdout
    assert "no smoke_test.sh with smoke-contract 2" in r.stderr
