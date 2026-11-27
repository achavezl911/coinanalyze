"""CADA guion de harness/bin que carga un env, ejecutado desde una COPIA DE ROOT, no carga uno que otro usuario puede cambiar (V45 N3).

Hermana de test_api_entorno_copia.py (que fija api con detalle). Aqui la lista de guiones NO esta escrita a mano: sale de
harness/bin, de toda linea (no comentario) que hace `. <algo>/env` o `. <algo>/_entorno`. Las units de root de 143
(coinalyze-bot-semanal, coinalyze-diario-*) corren /opt/coinalyze-143/current y llaman `sh <arbol>/harness/bin/prodsql`,
`prod` y `api`; un guion que cargara `/srv/coinanalyze/harness/env` dejaria a devops (dueno de /srv/coinanalyze, puede
renombrar harness/) hacer que root ejecute su env. Sin root real: arboles temporales, las rutas fijas /srv/coinanalyze y
/etc/coinalyze-143 cambiadas por las del banco, y dobles de ssh, psql y curl. El env plantado deja una MARCA al cargarse.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parent.parent / "harness" / "bin"
CARGA = re.compile(r"""(?:^|[;&|]|\bthen\b|\bdo\b)\s*(?:\.|source)\s+[^;&|#\n]*?(?:/env|_entorno)"?(?=\s|$|;)""", re.M)


def _codigo(t: str) -> str:
    return "\n".join(ln for ln in t.splitlines() if not ln.lstrip().startswith("#"))


def _cargan() -> list[str]:
    return sorted(p.name for p in BIN.iterdir()
                  if p.is_file() and p.name != "_entorno" and CARGA.search(_codigo(p.read_text(errors="replace"))))


GUIONES = _cargan()
DOBLES = {
    "curl": """#!/bin/sh
o=; u=
while [ $# -gt 0 ]; do
  case "$1" in -o) o=$2; shift ;; -w|--netrc-file|--max-time) shift ;; -*) ;; *) u=$1 ;; esac
  shift
done
if [ -n "$o" ]; then printf '{"url":"%s"}' "$u" > "$o"; printf 200; else printf '{"url":"%s"}' "$u"; fi
""",
    # el ssh de prod/prodsql: deja sus argumentos (sin el remoto, que es base64) y contesta una fila
    "ssh": """#!/bin/sh
printf '%s\\n' "$@" > "$HOME/ssh.args"
printf '42|x\\n'
""",
    "psql": "#!/bin/sh\nprintf '1\\n'\n",
}


def _env(dest: Path, marca: Path, tmp: Path, quien: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"touch '{marca}'\nPROD_HOST=h-{quien}\nPROD_SSH_USER=u\nPROD_SSH_KEY={tmp}/clave-{quien}\n"
                    f"PROD_KNOWN_HOSTS={tmp}/kh\nPROD_PG_USER=p\nPROD_PG_DB=d\nAPI_PROD=http://{quien}\n"
                    f"NETRC={tmp}/netrc\nESPEJO_DB=e\nMAX_BYTES=8000\n")
    dest.chmod(0o644)


def _banco(tmp: Path, copia: Path, srv: Path, etc: Path) -> Path:
    """Copia harness/bin entero a {copia}/harness/bin con /srv/coinanalyze y /etc/coinalyze-143 apuntando al banco."""
    b = copia / "harness" / "bin"
    b.mkdir(parents=True)
    for p in BIN.iterdir():
        if p.is_file():
            t = p.read_text(errors="replace").replace("/srv/coinanalyze", str(srv)).replace("/etc/coinalyze-143", str(etc))
            (b / p.name).write_text(t)
            (b / p.name).chmod(0o755)
    fb = tmp / "fakebin"
    fb.mkdir(exist_ok=True)
    for n, t in DOBLES.items():
        (fb / n).write_text(t)
        (fb / n).chmod(0o755)
    (tmp / "netrc").write_text("machine x login a password b\n")
    (tmp / "netrc").chmod(0o600)
    return b


def _corre(tmp: Path, guion: Path, *args: str) -> subprocess.CompletedProcess:
    shell = "bash" if guion.read_text(errors="replace").startswith("#!/bin/bash") else "sh"
    env = {"PATH": f"{tmp / 'fakebin'}:/usr/bin:/bin", "HOME": str(tmp)}
    return subprocess.run([shell, str(guion), *args], capture_output=True, text=True, env=env, timeout=60,
                          input="", cwd=tmp)


def _ajeno(d: Path, como: str) -> None:
    """Hace {d} cambiable por otro usuario: o+w sin pegajoso, o (como root) dueno nobody."""
    if como == "modo":
        d.chmod(0o777)
    else:
        os.chown(d, 65534, 65534)
        d.chmod(0o755)


FORMAS = ["modo"] + (["dueno"] if os.geteuid() == 0 else [])


def test_el_censo_ve_los_guiones_del_canal():
    """El censo no esta vacio y ve, al menos, los tres que llaman las units de root (api, prod, prodsql)."""
    assert {"api", "prod", "prodsql", "_corta"} <= set(GUIONES), GUIONES


@pytest.mark.parametrize("como", FORMAS)
@pytest.mark.parametrize("nombre", GUIONES)
def test_copia_de_root_no_carga_env_de_cadena_ajena(tmp_path, nombre, como):
    """Copia en arbol seguro, sin /etc/coinalyze-143/env, y el env del dia bajo una cadena ajena: no se carga, rc 4."""
    srv, marca = tmp_path / "srv", tmp_path / "EJECUTADO-dia"
    _env(srv / "harness" / "env", marca, tmp_path, "dia")
    b = _banco(tmp_path, tmp_path / "opt" / "copia", srv, tmp_path / "etc-sin")
    _ajeno(srv, como)
    r = _corre(tmp_path, b / nombre, "SELECT 1")
    assert not marca.exists(), f"{nombre} desde la copia de root EJECUTO el env de una cadena ajena (rc={r.returncode})"
    assert r.returncode == 4 and "otro usuario" in r.stderr, (r.returncode, r.stderr[-300:])


@pytest.mark.parametrize("nombre", GUIONES)
def test_copia_de_root_carga_el_env_de_root(tmp_path, nombre):
    """Con /etc/coinalyze-143/env seguro, la copia carga ESE y el del dia (ajeno) ni se toca."""
    srv, etc = tmp_path / "srv", tmp_path / "etc"
    _env(srv / "harness" / "env", tmp_path / "EJECUTADO-dia", tmp_path, "dia")
    _env(etc / "env", tmp_path / "EJECUTADO-root", tmp_path, "root")
    b = _banco(tmp_path, tmp_path / "opt" / "copia", srv, etc)
    _ajeno(srv, "modo")
    r = _corre(tmp_path, b / nombre, "SELECT 1")
    assert not (tmp_path / "EJECUTADO-dia").exists(), nombre
    assert (tmp_path / "EJECUTADO-root").exists(), (nombre, r.returncode, r.stderr[-300:])


@pytest.mark.parametrize("ajeno", [True, False])
@pytest.mark.parametrize("nombre", GUIONES)
def test_arnes_del_dia_sigue_igual(tmp_path, nombre, ajeno):
    """devops (o root) desde /srv/coinanalyze/harness/bin: carga harness/env como siempre, nunca el de root."""
    srv, etc = tmp_path / "srv", tmp_path / "etc"
    _env(srv / "harness" / "env", tmp_path / "EJECUTADO-dia", tmp_path, "dia")
    _env(etc / "env", tmp_path / "EJECUTADO-root", tmp_path, "root")
    b = _banco(tmp_path, srv, srv, etc)
    if ajeno:
        _ajeno(srv, "modo")
    r = _corre(tmp_path, b / nombre, "SELECT 1")
    assert (tmp_path / "EJECUTADO-dia").exists(), (nombre, r.returncode, r.stderr[-300:])
    assert not (tmp_path / "EJECUTADO-root").exists(), nombre


@pytest.mark.parametrize("nombre,arg", [("prodsql", "SELECT 1"), ("prod", "ls /")])
def test_prodsql_y_prod_sirven_al_bot_y_al_diario_desde_la_copia(tmp_path, nombre, arg):
    """Como los llaman tools/bot/semanal.py y app.diario (`sh <copia>/harness/bin/<g> ...`): rc 0, la fila, y el ssh
    con la clave y el host del env de ROOT."""
    srv, etc = tmp_path / "srv", tmp_path / "etc"
    _env(srv / "harness" / "env", tmp_path / "EJECUTADO-dia", tmp_path, "dia")
    _env(etc / "env", tmp_path / "EJECUTADO-root", tmp_path, "root")
    b = _banco(tmp_path, tmp_path / "opt" / "copia", srv, etc)
    _ajeno(srv, "modo")
    r = _corre(tmp_path, b / nombre, arg)
    assert r.returncode == 0, r.stderr[-300:]
    assert r.stdout.strip() == "42|x", r.stdout
    a = (tmp_path / "ssh.args").read_text().splitlines()
    assert f"{tmp_path}/clave-root" in a and "u@h-root" in a, a


@pytest.mark.parametrize("nombre", GUIONES)
def test_nadie_carga_un_env_fijo_fuera_de_entorno(nombre):
    """Las rutas del env viven SOLO en _entorno: ningun guion hace `. .../harness/env` o `. "$B/env"` por su cuenta."""
    c = _codigo((BIN / nombre).read_text(errors="replace"))
    assert "_entorno" in c and not re.search(r"""(?:^|[;&|])\s*(?:\.|source)\s+[^;&|#\n]*/env\b""", c, re.M), nombre
