"""harness/bin/api ejecutado desde una COPIA DE ROOT no carga un `env` cuya cadena puede cambiar otro usuario (Fable V45 N3).

La unit coinalyze-diario-cuarto de 143 corre como root /opt/coinalyze-143/current (root:root 755), cuyo harness/bin/api
hacia `. /srv/coinanalyze/harness/env`. /srv/coinanalyze es devops:devops 755: devops no escribe en harness/ (root) pero SI
puede renombrarlo y poner otro con su `env`, que root ejecutaba cada 15 min. Sin root real: se imita la LOGICA con arboles
temporales. «Otro usuario puede cambiarlo» = un directorio de la cadena escribible por grupo/otros sin bit pegajoso, o (si
la prueba corre como root) cuyo dueno no es root. Se copian api, _corta y _entorno (si existe) y en la copia se cambian las
dos rutas fijas (/srv/coinanalyze/harness y /etc/coinalyze-143) por las del banco; curl es un doble que devuelve la URL.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parent.parent / "harness" / "bin"
CURL = """#!/bin/sh
o=; u=
while [ $# -gt 0 ]; do
  case "$1" in -o) o=$2; shift ;; -w|--netrc-file|--max-time) shift ;; -*) ;; *) u=$1 ;; esac
  shift
done
printf '{"url":"%s"}' "$u" > "$o"; printf 200
"""


def _env(dest: Path, api_prod: str, netrc: Path, marca: Path | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    trampa = f"touch '{marca}'\n" if marca else ""
    dest.write_text(f"{trampa}API_PROD={api_prod}\nNETRC={netrc}\nMAX_BYTES=8000\n")
    dest.chmod(0o644)


def _banco(tmp: Path, copia: Path, dia: Path, etc: Path) -> Path:
    """Copia los guiones de harness/bin a {copia}/harness/bin con las rutas fijas apuntando al banco."""
    b = copia / "harness" / "bin"
    b.mkdir(parents=True)
    for n in ("api", "_corta", "_entorno"):
        if (BIN / n).exists():
            t = (BIN / n).read_text().replace("/srv/coinanalyze/harness", str(dia)).replace("/etc/coinalyze-143", str(etc))
            (b / n).write_text(t)
            (b / n).chmod(0o755)
    fb = tmp / "fakebin"
    fb.mkdir(exist_ok=True)
    (fb / "curl").write_text(CURL)
    (fb / "curl").chmod(0o755)
    netrc = tmp / "netrc"
    netrc.write_text("machine x login a password b\n")
    netrc.chmod(0o600)
    return b / "api"


def _corre(tmp: Path, api: Path) -> subprocess.CompletedProcess:
    env = {"PATH": f"{tmp / 'fakebin'}:/usr/bin:/bin", "HOME": str(tmp)}
    return subprocess.run(["sh", str(api), "/api/x"], capture_output=True, text=True, env=env, timeout=30)


def _ajeno(d: Path, como: str) -> None:
    """Hace {d} cambiable por otro usuario: o+w sin pegajoso, o (como root) dueno nobody."""
    if como == "modo":
        d.chmod(0o777)
    else:
        os.chown(d, 65534, 65534)
        d.chmod(0o755)


FORMAS = ["modo"] + (["dueno"] if os.geteuid() == 0 else [])


@pytest.mark.parametrize("como", FORMAS)
def test_copia_de_root_no_carga_env_de_cadena_ajena(tmp_path, como):
    """La copia vive en un arbol seguro; el `env` del dia, bajo un directorio que otro usuario puede renombrar: no se carga."""
    srv = tmp_path / "srv"          # imita /srv/coinanalyze (devops)
    marca = tmp_path / "EJECUTADO"
    _env(srv / "harness" / "env", "http://malo", tmp_path / "netrc", marca)
    api = _banco(tmp_path, tmp_path / "opt" / "copia", srv / "harness", tmp_path / "etc-sin")
    _ajeno(srv, como)
    r = _corre(tmp_path, api)
    assert not marca.exists(), f"la copia de root EJECUTO el env de una cadena ajena (rc={r.returncode} {r.stdout!r})"
    assert r.returncode != 0 and r.stdout == ""
    assert "otro usuario" in r.stderr and "coinalyze-143/env" in r.stderr.replace(str(tmp_path / "etc-sin"), "coinalyze-143"), r.stderr


def test_copia_de_root_usa_el_env_de_root(tmp_path):
    """Con /etc/coinalyze-143/env (cadena de root) la copia lo usa y el del dia, ajeno, ni se toca."""
    srv, etc = tmp_path / "srv", tmp_path / "etc"
    marca = tmp_path / "EJECUTADO"
    _env(srv / "harness" / "env", "http://malo", tmp_path / "netrc", marca)
    _env(etc / "env", "http://bueno", tmp_path / "netrc")
    api = _banco(tmp_path, tmp_path / "opt" / "copia", srv / "harness", etc)
    _ajeno(srv, "modo")
    r = _corre(tmp_path, api)
    assert not marca.exists()
    assert r.returncode == 0, r.stderr
    assert r.stdout == '{"url":"http://bueno/api/x"}'


def test_copia_de_root_rechaza_env_de_root_escribible(tmp_path):
    """Un /etc/coinalyze-143/env escribible por otros tampoco vale: falla cerrado."""
    srv, etc = tmp_path / "srv", tmp_path / "etc"
    _env(srv / "harness" / "env", "http://malo", tmp_path / "netrc")
    _env(etc / "env", "http://bueno", tmp_path / "netrc")
    (etc / "env").chmod(0o666)
    api = _banco(tmp_path, tmp_path / "opt" / "copia", srv / "harness", etc)
    _ajeno(srv, "modo")
    r = _corre(tmp_path, api)
    assert r.returncode != 0 and r.stdout == "", r.stdout


def test_arnes_del_dia_sigue_igual(tmp_path):
    """devops: el guion vive en /srv/coinanalyze (su propia cadena ya es cambiable) -> carga harness/env como siempre."""
    srv, etc = tmp_path / "srv", tmp_path / "etc"
    _env(srv / "harness" / "env", "http://dia", tmp_path / "netrc")
    _env(etc / "env", "http://root", tmp_path / "netrc")
    api = _banco(tmp_path, srv / "repo", srv / "harness", etc)
    _ajeno(srv, "modo")
    r = _corre(tmp_path, api)
    assert r.returncode == 0, r.stderr
    assert r.stdout == '{"url":"http://dia/api/x"}'


def test_arnes_del_dia_en_cadena_propia(tmp_path):
    """devops dueno de toda su cadena (nada ajeno): sigue mandando harness/env del dia, no el de root."""
    srv, etc = tmp_path / "srv", tmp_path / "etc"
    _env(srv / "harness" / "env", "http://dia", tmp_path / "netrc")
    _env(etc / "env", "http://root", tmp_path / "netrc")
    api = _banco(tmp_path, srv / "repo", srv / "harness", etc)
    r = _corre(tmp_path, api)
    assert r.returncode == 0, r.stderr
    assert r.stdout == '{"url":"http://dia/api/x"}'


def test_api_real_no_lee_rutas_fijas_fuera_de_entorno():
    """Las rutas del env viven SOLO en _entorno: api y _corta no hacen `. /srv/coinanalyze/harness/env` por su cuenta."""
    for n in ("api", "_corta"):
        t = (BIN / n).read_text()
        assert "harness/env" not in "\n".join(ln for ln in t.splitlines() if not ln.lstrip().startswith("#")), n

