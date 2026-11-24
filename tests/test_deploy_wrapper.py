"""DATOS B (fable-f4 H1 y fable-f8 F1): el despliegue que se defiende. deploy/140/deploy-coinalyze corrido ENTERO
contra dobles: sus rutas reescritas a un tmp, y systemctl, curl, runuser, pg_dump, psql y chown en el PATH. El curl
doble sirve un healthz por guion, el sha de main de GitHub y su tarball, y apunta su argv: asi se ve que el token no viaja en el
argv. Sin base ni red.
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
# del reinicio; ESCENA=marca:N da N respuestas con el latido de ingest DESPUES del reinicio en «degraded» y su compuesto
# de ARRANQUE (el de la foto de 11df0b4), y luego «ok»; ESCENA=marca-sigue, ese arranque siempre.
CURL = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$SB/curl.argv"
url=${!#}
ahora=$(date -u +%FT%TZ)
case "$url" in
  https://api.github.com/repos/achavezl911/coinanalyze/commits/main)
    [ -z "${GH_FALLA:-}" ] || exit 22
    printf '%s' "$GH_MAIN" ;;
  https://api.github.com/repos/achavezl911/coinanalyze/tarball/*)
    echo "$url" >> "$SB/tarball.log"
    [ -z "${TARBALL_FALLA:-}" ] || exit 22
    while [ $# -gt 1 ]; do [ "$1" = -o ] && cp "$SB/github.tgz" "$2"; shift; done ;;
  */api/healthz)
    n=$(cat "$SB/healthz.n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$SB/healthz.n"
    estado=ok; ingest_ts=$ahora; ingest_st=ok; ingest_det=x
    marca='collector starting; awaiting successful cycle'
    case "$ESCENA" in
      arranca:*) [ "$n" -le "${ESCENA#arranca:}" ] && { estado=degraded; ingest_ts=1970-01-01T00:00:00Z; } ;;
      muerto) estado=degraded; ingest_ts=1970-01-01T00:00:00Z ;;
      error) estado=degraded; ingest_st=error ;;
      marca:*|marca-sigue)
        if [ "$ESCENA" = marca-sigue ] || [ "$n" -le "${ESCENA#marca:}" ]; then
          estado=degraded; ingest_st=degraded; ingest_det="metrics_5m=degraded:$marca;ohlcv_1m=degraded:$marca"
        fi ;;
    esac
    printf '{"status":"%s","missing_services":[],"missing_symbols":[],"informative_services":[],"symbols":[],' "$estado"
    printf '"services":[{"service":"api","status":"ok","updated_at":"%s"},' "$ahora"
    printf '{"service":"ingest","status":"%s","updated_at":"%s","detail":"%s"},' "$ingest_st" "$ingest_ts" "$ingest_det"
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


# runuser -u USUARIO -- CMD...: apunta quien y que, y lo corre (aqui no hay usuario coinalyze).
RUNUSER = """#!/usr/bin/env bash
echo "$*" >> "$SB/runuser.log"
[ "$1" = -u ] && [ "$3" = -- ] || exit 64
shift 3
exec "$@"
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
    _x(bin_ / "chown", "#!/bin/sh\necho \"$*\" >> \"$SB/chown.log\"\n")
    _x(bin_ / "runuser", RUNUSER)
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
    # Lo que serviria GitHub por el commit: el arbol bajo su carpeta de cabeza, con .github/ (el artefacto de hoy no
    # la trae).
    fuente = sb / "fuente"
    _release(fuente)
    (fuente / ".github" / "workflows").mkdir(parents=True)
    (fuente / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    _tar(fuente, sb / "github.tgz", "achavezl911-coinanalyze-aaaaaaa")
    rutas = {
        "APP_ROOT": app, "STATE": sb / "deployment.json", "LOGDIR": sb / "log", "ENV_FILE": env_file,
        "BACKUPDIR": sb / "backups", "LOCKFILE": sb / "lock", "UNIT_DIR": units,
        "SMOKE_MAX_WAIT": smoke_max, "SMOKE_SLEEP": 1,
    }
    texto = (ROOT / "deploy" / "140" / "deploy-coinalyze").read_text(encoding="utf-8")
    for k, v in rutas.items():
        texto, n = re.subn(rf"^{k}=.*$", f"{k}={v}", texto, count=1, flags=re.M)
        assert n == 1, k
    # El envoltorio de antes de R1 aceptaba el tar solo bajo INCOMING: asi se le puede pasar el banco y ver que cae.
    texto = re.sub(r"^INCOMING=.*$", f"INCOMING={sb / 'incoming'}", texto, count=1, flags=re.M)
    texto = texto.replace('[ "$(id -u)" -eq 0 ] ||', "true ||", 1)
    wrapper = sb / "deploy-coinalyze"
    _x(wrapper, texto)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "SB": str(sb), "ESCENA": "arranca:0", "GH_MAIN": NUEVO}
    env.pop("FAILED_UNIT", None)
    return {"sb": sb, "app": app, "wrapper": wrapper, "env": env}


def _tar(origen: Path, destino: Path, cabeza: str) -> str:
    def ajeno(ti: tarfile.TarInfo) -> tarfile.TarInfo:
        ti.uid, ti.gid, ti.uname, ti.gname = 4242, 4242, "", ""  # el paquete dice de quien son sus ficheros
        return ti

    with tarfile.open(destino, "w:gz") as t:
        t.add(origen, arcname=cabeza, filter=ajeno)
    return hashlib.sha256(destino.read_bytes()).hexdigest()


def _suyo(b: dict) -> tuple[str, str]:
    """El tar de quien llama, como lo entrega el workflow de hoy: el release con un smoke PLANTADO que deja testigo."""
    suyo = b["sb"] / "suyo"
    shutil.copytree(b["sb"] / "fuente", suyo, ignore=shutil.ignore_patterns(".github"))
    (suyo / "scripts" / "smoke_test.sh").write_text('# smoke-contract: 2 \ntouch "$SB/testigo"\nexit 0\n',
                                                     encoding="utf-8")
    (b["sb"] / "incoming").mkdir()
    art = b["sb"] / "incoming" / "art.tar.gz"
    return str(art), _tar(suyo, art, ".")


def _despliega(b: dict, commit: str = NUEVO, *, vieja: bool = False, **env: str) -> subprocess.CompletedProcess:
    """`deploy <commit>`; con vieja=True, la firma del workflow de hoy con el tar de _suyo delante."""
    args = [*_suyo(b), commit] if vieja else [commit]
    return subprocess.run(["bash", str(b["wrapper"]), "deploy", *args],
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


def test_un_arranque_de_colector_tras_el_reinicio_que_pasa_a_ok_no_revierte(tmp_path):
    # Despliegue R1: el latido de ingest ya es POSTERIOR al reinicio y dice solo que el colector arranca.
    b = _banco(tmp_path, smoke_max=30)
    r = _despliega(b, ESCENA="marca:2")
    assert r.returncode == 0, r.stderr[-2000:]
    assert f"DEPLOY_OK {NUEVO}" in r.stdout and "definitive" not in r.stderr
    assert _current(b) == NUEVO
    assert int(_log(b, "healthz.n")) == 3


def test_un_arranque_de_colector_que_no_pasa_a_ok_en_el_plazo_revierte(tmp_path):
    b = _banco(tmp_path, smoke_max=3)
    r = _despliega(b, ESCENA="marca-sigue")
    assert r.returncode == 10, r.stderr[-2000:]
    assert "smoke FAILED after 3s (rc=75)" in r.stderr and "definitive" not in r.stderr
    assert "restoring previous release" in r.stderr
    assert _current(b) == VIEJO


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


def test_solo_se_despliega_lo_que_es_main_en_github(tmp_path):
    for i, (env, motivo) in enumerate(((dict(GH_MAIN="c" * 40), "main=" + "c" * 40), (dict(GH_FALLA="1"), "main=unreachable"))):
        b = _banco(tmp_path / str(i))
        r = _despliega(b, **env)
        assert r.returncode == 16, r.stderr[-2000:]
        assert f"is not origin/main on GitHub ({motivo})" in r.stderr
        assert _current(b) == VIEJO and not (b["app"] / "releases" / NUEVO).exists()
        assert _log(b, "systemctl.log") == "" and not (b["sb"] / "backups").exists()  # ni para ni respalda


def test_un_sha_corto_no_se_acepta(tmp_path):
    b = _banco(tmp_path)
    r = _despliega(b, commit=NUEVO[:12], GH_MAIN=NUEVO[:12])
    assert r.returncode == 2 and "bad commit sha" in r.stderr


def test_el_venv_lo_construye_el_usuario_del_servicio(tmp_path):
    b = _banco(tmp_path)
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    rel = b["app"] / "releases" / NUEVO
    lineas = _log(b, "runuser.log").splitlines()
    assert any(x.startswith("-u coinalyze -- env HOME=/nonexistent PIP_NO_CACHE_DIR=1 python3 -m venv") for x in lineas)
    assert sum(f"{rel}/.venv/bin/pip install" in x for x in lineas) == 2 and all("-u coinalyze --" in x for x in lineas)
    chown = _log(b, "chown.log").splitlines()
    assert chown == [f"-R coinalyze:coinalyze {rel}", f"-R root:coinalyze {rel}"]  # lo construye el, lo sirve root
    assert (rel / "pyproject.toml").stat().st_uid != 4242  # tar no hace caso del dueno que trae el paquete


# ENVOLTORIO R1 (D-01 y D-02, CATALOGO-HALLAZGOS-20261120): el codigo lo baja root de GitHub por el commit, con las
# dos firmas; el tar y la suma de quien llama no cuentan; el release activo no se reconstruye encima.
def _restos(b: dict) -> list[str]:
    return sorted(p.name for p in (b["app"] / "releases").glob(".stage*"))


def test_las_dos_firmas_bajan_el_codigo_de_github_y_no_el_tar_de_quien_llama(tmp_path):
    for i, vieja in enumerate((False, True)):
        b = _banco(tmp_path / str(i))
        r = _despliega(b, vieja=vieja)
        assert r.returncode == 0, r.stderr[-2000:]
        assert _current(b) == NUEVO and f"source fetched from GitHub ({NUEVO})" in r.stderr
        assert _log(b, "tarball.log") == f"https://api.github.com/repos/achavezl911/coinanalyze/tarball/{NUEVO}\n"
        rel = b["app"] / "releases" / NUEVO
        assert (rel / "scripts" / "smoke_test.sh").read_bytes() == (ROOT / "scripts" / "smoke_test.sh").read_bytes()
        assert not (b["sb"] / "testigo").exists()  # el smoke plantado en el tar de quien llama no corre
        assert (rel / ".github" / "workflows" / "ci.yml").is_file()  # sin la carpeta de cabeza: el arbol, a la raiz
        assert _restos(b) == []


def test_un_sha_que_no_es_main_da_16_sin_bajar_nada(tmp_path):
    for i, vieja in enumerate((False, True)):
        b = _banco(tmp_path / str(i))
        r = _despliega(b, vieja=vieja, GH_MAIN="c" * 40)
        assert r.returncode == 16, r.stderr[-2000:]
        assert _current(b) == VIEJO and _log(b, "tarball.log") == "" and _log(b, "systemctl.log") == ""
        assert not (b["sb"] / "backups").exists() and _restos(b) == []


def test_redesplegar_el_activo_da_17_sin_tocar_el_release(tmp_path):
    for i, vieja in enumerate((False, True)):
        b = _banco(tmp_path / str(i))
        marca = b["app"] / "releases" / VIEJO / ".venv" / "bin" / "MARCA"
        marca.parent.mkdir(parents=True)
        marca.write_text("el venv que corre\n", encoding="utf-8")
        r = _despliega(b, VIEJO, vieja=vieja, GH_MAIN=VIEJO)
        assert r.returncode == 17, r.stderr[-2000:]
        assert "already the active release" in r.stderr
        assert marca.exists() and _current(b) == VIEJO
        assert _log(b, "systemctl.log") == "" and _log(b, "tarball.log") == "" and not (b["sb"] / "backups").exists()


def test_github_que_no_sirve_el_tarball_falla_cerrado_sin_parar_servicios(tmp_path):
    for i, (vieja, env) in enumerate(((False, {"TARBALL_FALLA": "1"}), (True, {"TARBALL_FALLA": "1"}), (False, {}))):
        b = _banco(tmp_path / str(i))
        if not env:
            (b["sb"] / "github.tgz").write_bytes(b"<html>no es un tar</html>\n")  # llega algo que no es un tar
        r = _despliega(b, vieja=vieja, **env)
        assert r.returncode == 3, r.stderr[-2000:]
        assert f"could not fetch {NUEVO} from GitHub" in r.stderr
        assert _current(b) == VIEJO and not (b["app"] / "releases" / NUEVO).exists()
        assert _log(b, "systemctl.log") == "" and not (b["sb"] / "backups").exists() and _restos(b) == []


def test_una_firma_que_no_es_ninguna_de_las_dos_no_se_acepta(tmp_path):
    b = _banco(tmp_path)
    for args in ([], ["x", NUEVO], ["x", "y", NUEVO, "z"]):
        r = subprocess.run(["bash", str(b["wrapper"]), "deploy", *args], env=b["env"], text=True,
                           capture_output=True, timeout=60, check=False)
        assert r.returncode == 2 and "usage: deploy <commit>" in r.stderr, args
    assert _log(b, "curl.argv") == "" and _current(b) == VIEJO


def test_el_volcado_nuevo_poda_los_predeploy_previos_y_deja_el_mas_reciente(tmp_path):
    """PODA R1: un dia con 9 despliegues llenaba el disco de 140 (3.3 GB por volcado, podados solo de madrugada)."""
    b = _banco(tmp_path, smoke_max=30)
    bk = b["sb"] / "backups"
    bk.mkdir()
    ahora = time.time()
    previos = []
    for i, dias in enumerate((4, 3, 2, 1)):  # 4 volcados previos, el de hace 1 dia es el del release activo
        f = bk / f"predeploy-{'c' * 39}{i}-2026112{i}000000.sql.gz"
        f.write_text("x", encoding="utf-8")
        os.utime(f, (ahora - dias * 86400, ahora - dias * 86400))
        previos.append(f)
    (bk / f"{previos[0].name}.sha256").write_text("h", encoding="utf-8")
    ajenos = [bk / "coinalyze-full-20261120.sql.gz.enc", bk / "coinalyze-full-20261123.sql.gz.enc"]
    for f in ajenos:
        f.write_text("y", encoding="utf-8")
        os.utime(f, (ahora - 5 * 86400, ahora - 5 * 86400))
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    quedan = sorted(p.name for p in bk.glob("predeploy-*"))
    nuevo = [n for n in quedan if n.startswith(f"predeploy-{NUEVO}-")]
    assert len(quedan) == 2 and len(nuevo) == 1 and previos[-1].name in quedan, quedan
    assert all(f.exists() for f in ajenos) and not (bk / f"{previos[0].name}.sha256").exists()
    assert r.stderr.count("pruned pre-deploy backup:") == 3
