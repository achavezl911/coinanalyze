"""DATOS B (fable-f8 F3): lo que root ejecuta en 143 sale de una copia congelada de main, no del arbol de trabajo.
deploy/143/instala.sh corrido ENTERO contra un repo git de tmp y dobles de systemctl, crontab y chown; sus rutas
reescritas a un tmp. Sin red y sin tocar 143.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEL_ARBOL = ("/srv/coinanalyze/repo", "/srv/coinanalyze/harness/bin")
COPIADOS = (
    "deploy/143/coinalyze-bot-semanal.service", "deploy/143/coinalyze-bot-semanal.timer",
    "deploy/143/coinalyze-libretas.service", "deploy/systemd/coinalyze-libretas.timer",
    "harness/bin/capta-healthz", "harness/bin/respalda-libretas", "tools/bot/semanal.py",
)
CRONTAB = """#!/usr/bin/env bash
# crontab -l -u root | crontab -u root FICHERO, sobre $SB/crontab
if [ "$1" = -l ]; then cat "$SB/crontab"; else cp "$3" "$SB/crontab"; fi
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def _x(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _banco(tmp_path: Path) -> dict:
    sb = tmp_path
    repo = sb / "repo"
    for rel in COPIADOS:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, repo / rel)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main")
    main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", main)
    _git(repo, "checkout", "-q", "-b", "campana")
    (repo / "harness/bin/capta-healthz").write_text("#!/bin/sh\necho RAMA\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "rama")
    rama = _git(repo, "rev-parse", "HEAD")
    (repo / "harness/bin/capta-healthz").write_text("#!/bin/sh\necho SIN COMMITEAR\n", encoding="utf-8")
    bin_ = sb / "bin"
    bin_.mkdir()
    _x(bin_ / "systemctl", '#!/bin/sh\necho "$*" >> "$SB/systemctl.log"\n')
    _x(bin_ / "chown", "#!/bin/sh\nexit 0\n")
    _x(bin_ / "crontab", CRONTAB)
    (sb / "crontab").write_text("MAILTO=\"\"\n* * * * * /srv/coinanalyze/harness/bin/capta-healthz\n"
                                "0 3 * * * /usr/local/bin/otra-cosa\n", encoding="utf-8")
    units = sb / "units"
    units.mkdir()
    rutas = {"REPO": repo, "BASE": sb / "opt143", "UNIT_DIR": units, "CRON_FILE": sb / "cron.d-capta"}
    texto = (ROOT / "deploy/143/instala.sh").read_text(encoding="utf-8")
    for k, v in rutas.items():
        texto, n = re.subn(rf"^{k}=.*$", f"{k}={v}", texto, count=1, flags=re.M)
        assert n == 1, k
    texto = texto.replace('[ "$(id -u)" -eq 0 ] ||', "true ||", 1)
    guion = sb / "instala.sh"
    _x(guion, texto)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "SB": str(sb)}
    return {"sb": sb, "guion": guion, "env": env, "main": main, "rama": rama, "units": units, **rutas}


def _corre(b: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(b["guion"]), *args], env=b["env"], text=True, capture_output=True,
                          timeout=60, check=False)


def test_instala_desde_la_copia_congelada_de_main(tmp_path):
    b = _banco(tmp_path)
    r = _corre(b)
    assert r.returncode == 0, r.stderr[-2000:]
    copia = b["BASE"] / b["main"]
    assert os.readlink(b["BASE"] / "current") == b["main"]
    # lo commiteado en main: ni la rama sacada ni lo que hay sin commitear en el arbol
    assert (copia / "harness/bin/capta-healthz").read_bytes() == (ROOT / "harness/bin/capta-healthz").read_bytes()
    for p in [copia, *copia.rglob("*")]:
        assert not p.lstat().st_mode & (stat.S_IWGRP | stat.S_IWOTH), p
    for u in ("coinalyze-bot-semanal.service", "coinalyze-bot-semanal.timer",
              "coinalyze-libretas.service", "coinalyze-libretas.timer"):
        texto = "\n".join(x for x in (b["units"] / u).read_text(encoding="utf-8").splitlines() if not x.startswith("#"))
        assert not any(x in texto for x in DEL_ARBOL), u
    assert "/opt/coinalyze-143/current/tools/bot/semanal.py" in (b["units"] / "coinalyze-bot-semanal.service").read_text()
    assert "/opt/coinalyze-143/current/harness/bin/respalda-libretas" in (b["units"] / "coinalyze-libretas.service").read_text()
    assert "enable --now coinalyze-bot-semanal.timer coinalyze-libretas.timer" in (b["sb"] / "systemctl.log").read_text()
    cron = b["CRON_FILE"].read_text(encoding="utf-8")
    assert f"* * * * * root {b['BASE']}/current/harness/bin/capta-healthz" in cron
    crontab = (b["sb"] / "crontab").read_text(encoding="utf-8")
    assert "capta-healthz" not in crontab and "otra-cosa" in crontab and "MAILTO" in crontab


def test_un_sha_que_no_esta_en_main_no_se_instala(tmp_path):
    b = _banco(tmp_path)
    r = _corre(b, b["rama"])
    assert r.returncode == 1 and "no esta en origin/main" in r.stderr
    assert not b["BASE"].exists() and not any(b["units"].iterdir()) and not b["CRON_FILE"].exists()
    assert "capta-healthz" in (b["sb"] / "crontab").read_text(encoding="utf-8")


def test_lo_de_143_no_ejecuta_el_arbol_de_trabajo():
    for u in ("coinalyze-bot-semanal.service", "coinalyze-libretas.service"):
        execs = [x for x in (ROOT / "deploy/143" / u).read_text().splitlines() if x.startswith("ExecStart=")]
        assert execs and not any(a in x for x in execs for a in DEL_ARBOL), u
    # semanal.py llama a prod/prodsql de SU arbol: desde la copia congelada, a los congelados
    semanal = (ROOT / "tools/bot/semanal.py").read_text(encoding="utf-8")
    assert 'H = os.path.join(RAIZ, "harness", "bin")' in semanal and '"/srv/coinanalyze/harness/bin"' not in semanal


def test_el_repo_no_trae_ganchos_de_claude_code():
    assert not (ROOT / ".claude" / "settings.json").exists()
