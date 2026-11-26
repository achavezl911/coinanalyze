"""REINICIO R1: un despliegue que no cambia el esquema ni el codigo de un colector no lo reinicia.

deploy/140/deploy-coinalyze corrido ENTERO sobre el banco de test_deploy_wrapper.py (rutas a un tmp, dobles en el PATH),
con un systemctl doble que ademas imita lo que hacen las unidades de deploy/140: orderflow, libro y bot llevan
PartOf=coinalyze-api.service (un stop/restart de la API los arrastra salvo con --job-mode=ignore-requirements) y
WantedBy=coinalyze-api.service (un start de la API los arranca). Cada efecto sobre una unidad queda en efecto.log, y el
MainPID de cada una tiene su cwd en $SB/proc/<pid>/cwd: el release del que corre.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from test_deploy_wrapper import (
    NUEVO,
    ROOT,
    VIEJO,
    _banco,
    _current,
    _despliega,
    _log,
    _release,
    _tar,
    _x,
)

PARTOF = ("coinalyze-orderflow", "coinalyze-libro", "coinalyze-bot")
SERVICIOS = ("coinalyze-api", "coinalyze-ingest", "coinalyze-ws", "coinalyze-scalp", "coinalyze-daily")
COLECTORES = ("coinalyze-ingest", "coinalyze-ws", "coinalyze-scalp", "coinalyze-daily", *PARTOF)

SYSTEMCTL = r"""#!/usr/bin/env bash
echo "$*" >> "$SB/systemctl.log"
modo=normal; args=()
for a in "$@"; do
  case "$a" in
    --job-mode=ignore-requirements|--job-mode=ignore-dependencies) modo=ignora ;;
    --quiet|--job-mode=*) ;;
    *) args+=("$a") ;;
  esac
done
set -- "${args[@]}"
cmd=$1; shift
efecto(){
  echo "$1 $2" >> "$SB/efecto.log"
  if [ "$1" = stop ]; then
    touch "$SB/parado-$2"; echo 0 > "$SB/pid-$2"
  else
    rm -f "$SB/parado-$2"; n=$(( $(cat "$SB/pid.n" 2>/dev/null || echo 100) + 1 )); echo "$n" > "$SB/pid.n"
    mkdir -p "$SB/proc/$n"; ln -sfn "$(readlink -f "$SB/opt/current")" "$SB/proc/$n/cwd"; echo "$n" > "$SB/pid-$2"
  fi
}
case "$cmd" in
  stop|start|restart|try-restart)
    for u in "$@"; do
      u=${u%.service}
      [ "$cmd" = try-restart ] && [ -e "$SB/parado-$u" ] && continue
      efecto "$cmd" "$u"
      [ "$u" = coinalyze-api ] && [ "$modo" = normal ] || continue
      for p in coinalyze-orderflow coinalyze-libro coinalyze-bot; do
        [ -f "$SB/units/$p.service" ] || continue
        case "$cmd" in
          stop) efecto stop "$p" ;;
          start) [ -e "$SB/parado-$p" ] && efecto start "$p" ;;
          *) [ -e "$SB/parado-$p" ] || efecto restart "$p" ;;
        esac
      done
    done ;;
  show) cat "$SB/pid-${!#}" 2>/dev/null || echo 0 ;;
  is-failed) [ "${FAILED_UNIT:-}" = "$1" ] ;;
  is-active) [ "${FAILED_UNIT:-}" != "$1" ] && [ ! -e "$SB/parado-$1" ] ;;
  *) exit 0 ;;
esac
"""

# Un app/ de juguete con la forma de la de verdad: imports absolutos, relativos, perezosos (dentro de una funcion) y un
# paquete que se corre con -m (app.bot -> __init__ + __main__).
APP = {
    "app/__init__.py": "",
    "app/comun.py": "X = 1\n",
    "app/db.py": "",
    "app/api.py": "from app import comun\nfrom app.db import *\n",
    "app/ingest.py": "from app.comun import X\nimport app.db\n",
    "app/ws_collector.py": "import json\n\ndef f():\n    from . import comun\n    return comun\n",
    "app/scalp_collector.py": "import asyncio\n",
    "app/daily_agg.py": "from app import db\n",
    "app/orderflow.py": "",
    "app/libro.py": "from app.libro_util import y\n",
    "app/libro_util.py": "y = 1\n",
    "app/bot/__init__.py": "",
    "app/bot/__main__.py": "from app.bot import motor\n",
    "app/bot/motor.py": "",
    "static/app.js": "1;\n",
}


def _arbol(d: Path, cambios: dict[str, str]) -> None:
    _release(d)
    for rel, texto in {**APP, **cambios}.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(texto, encoding="utf-8")
    guion = ROOT / "scripts" / "cierre_imports.py"
    if guion.exists():
        shutil.copy(guion, d / "scripts" / "cierre_imports.py")


def _corre_desde(b: dict, unidad: str, release: str) -> None:
    n = 9000 + len(list((b["sb"] / "proc").glob("*")))
    (b["sb"] / "proc" / str(n)).mkdir(parents=True)
    (b["sb"] / "proc" / str(n) / "cwd").symlink_to(b["app"] / "releases" / release)
    (b["sb"] / f"pid-{unidad}").write_text(f"{n}\n", encoding="utf-8")


def _banco_r1(tmp_path: Path, cambios: dict[str, str], **kw) -> dict:
    """VIEJO con APP; el candidato que sirve GitHub, APP con `cambios`. Las ocho unidades instaladas y corriendo de VIEJO."""
    b = _banco(tmp_path, **kw)
    sb = b["sb"]
    _x(sb / "bin" / "systemctl", SYSTEMCTL)
    _x(sb / "bin" / "psql", '#!/bin/sh\necho "$*" >> "$SB/psql.log"\necho 0\n')
    for u in PARTOF:
        (sb / "units" / f"{u}.service").write_text("PartOf=coinalyze-api.service\n", encoding="utf-8")
    _arbol(b["app"] / "releases" / VIEJO, {})
    fuente = sb / "fuente"
    _arbol(fuente, cambios)
    _tar(fuente, sb / "github.tgz", "achavezl911-coinanalyze-aaaaaaa")
    for u in (*SERVICIOS, *PARTOF):
        _corre_desde(b, u, VIEJO)
    # La ruta de /proc del guion, al banco (como _banco hace con las demas).
    texto = b["wrapper"].read_text(encoding="utf-8")
    texto, n = re.subn(r"^PROC=.*$", f"PROC={sb / 'proc'}", texto, count=1, flags=re.M)
    b["wrapper"].write_text(texto, encoding="utf-8")
    return b


def _efectos(b: dict) -> list[str]:
    return _log(b, "efecto.log").splitlines()


def _tocadas(b: dict) -> set[str]:
    return {linea.split()[1] for linea in _efectos(b)}


def test_solo_la_api_y_static_cambian_no_para_ni_reinicia_ningun_colector(tmp_path):
    b = _banco_r1(tmp_path, {"app/api.py": "from app import comun\n# cambio\n", "static/app.js": "2;\n"})
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    assert _current(b) == NUEVO
    assert "restart coinalyze-api" in _efectos(b)
    assert _tocadas(b) == {"coinalyze-api"}, _efectos(b)
    assert _log(b, "psql.log") == "", "sin cambio de esquema no se para nada ni se aplica nada"
    for u in COLECTORES:
        assert re.search(rf"restart plan: {u} keep \(", r.stderr), (u, r.stderr[-3000:])
    assert "restarted: coinalyze-api" in _log(b, "log/deploy.log")


def test_el_esquema_cambiado_para_todo_lo_aplica_y_arranca_todo(tmp_path):
    b = _banco_r1(tmp_path, {"sql/schema.sql": "SELECT 2;\n"})
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    for u in (*SERVICIOS, *PARTOF):
        assert f"stop {u}" in _efectos(b), u
        assert f"start {u}" in _efectos(b), u
    assert "-f " in _log(b, "psql.log")
    assert "sql/schema.sql changed" in r.stderr


def test_el_codigo_de_un_colector_reinicia_ese_colector_y_la_api(tmp_path):
    b = _banco_r1(tmp_path, {"app/libro_util.py": "y = 2\n"})
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    assert _tocadas(b) == {"coinalyze-api", "coinalyze-libro"}, _efectos(b)
    assert "restart coinalyze-libro" in _efectos(b)
    assert re.search(r"restart plan: coinalyze-libro restart \(.*app/libro_util\.py", r.stderr), r.stderr[-3000:]


def test_un_modulo_compartido_reinicia_a_todos_los_que_lo_importan_tambien_perezoso(tmp_path):
    b = _banco_r1(tmp_path, {"app/comun.py": "X = 2\n"})
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    assert _tocadas(b) == {"coinalyze-api", "coinalyze-ingest", "coinalyze-ws"}, _efectos(b)


def test_un_paquete_con_main_se_sigue_por_su_main(tmp_path):
    b = _banco_r1(tmp_path, {"app/bot/motor.py": "# cambio\n"})
    assert _despliega(b).returncode == 0
    assert _tocadas(b) == {"coinalyze-api", "coinalyze-bot"}, _efectos(b)


def test_requirements_cambiado_reinicia_todos(tmp_path):
    b = _banco_r1(tmp_path, {"requirements.lock": "httpx==9\n"})
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    assert _tocadas(b) == {*SERVICIOS, *PARTOF}, _efectos(b)
    assert _log(b, "psql.log") == ""


def test_un_colector_parado_se_arranca_como_hoy_y_uno_arrastrado_parado_no(tmp_path):
    b = _banco_r1(tmp_path, {"app/api.py": "# cambio\n"})
    (b["sb"] / "pid-coinalyze-daily").write_text("0\n", encoding="utf-8")
    (b["sb"] / "pid-coinalyze-bot").write_text("0\n", encoding="utf-8")
    (b["sb"] / "parado-coinalyze-bot").touch()
    assert _despliega(b).returncode == 0
    assert _tocadas(b) == {"coinalyze-api", "coinalyze-daily"}, _efectos(b)


def test_la_poda_no_borra_el_release_del_que_corre_un_servicio_vivo(tmp_path):
    b = _banco_r1(tmp_path, {"app/api.py": "# cambio\n"})
    rels = b["app"] / "releases"
    ahora = time.time()
    viejos = [f"{i}" * 40 for i in range(1, 7)]
    for i, sha in enumerate(viejos):
        _arbol(rels / sha, {})
        os.utime(rels / sha, (ahora - 1000 + i, ahora - 1000 + i))  # el 1... es el mas viejo
    os.utime(rels / VIEJO, (ahora - 10, ahora - 10))
    _corre_desde(b, "coinalyze-ingest", viejos[0])
    r = _despliega(b)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "coinalyze-ingest" not in _tocadas(b)
    assert (rels / viejos[0]).is_dir(), "ingest corre de ahi"
    assert f"keeping {viejos[0]}" in r.stderr
    assert not (rels / viejos[1]).exists() and not (rels / viejos[2]).exists()  # la poda sigue podando lo demas


def test_un_humo_que_falla_en_el_camino_parcial_revierte_solo_lo_reiniciado(tmp_path):
    b = _banco_r1(tmp_path, {"app/api.py": "# cambio\n"}, smoke_max=2)
    r = _despliega(b, ESCENA="muerto")
    assert r.returncode == 10, r.stderr[-2000:]
    assert _current(b) == VIEJO
    assert _tocadas(b) == {"coinalyze-api"}, _efectos(b)
    assert [e for e in _efectos(b) if e == "restart coinalyze-api"] == ["restart coinalyze-api"] * 2


def test_el_rollback_reinicia_todo_como_hoy(tmp_path):
    b = _banco_r1(tmp_path, {})
    _arbol(b["app"] / "releases" / NUEVO, {"app/api.py": "# cambio\n"})
    (b["app"] / "current").unlink()
    (b["app"] / "current").symlink_to(b["app"] / "releases" / NUEVO)
    (b["sb"] / "deployment.json").write_text(f'{{"commit": "{NUEVO}", "previous_commit": "{VIEJO}"}}\n',
                                             encoding="utf-8")
    r = subprocess.run(["bash", str(b["wrapper"]), "rollback"], env=b["env"], text=True, capture_output=True,
                       timeout=120, check=False)
    assert r.returncode == 0, r.stderr[-2000:]
    assert _current(b) == VIEJO
    assert "restart coinalyze-api coinalyze-ingest coinalyze-ws coinalyze-scalp coinalyze-daily" in _log(
        b, "systemctl.log")
    assert _tocadas(b) == {*SERVICIOS, *PARTOF}


def _entradas_del_guion() -> dict[str, str]:
    texto = (ROOT / "deploy" / "140" / "deploy-coinalyze").read_text(encoding="utf-8")
    bloque = re.search(r"^declare -A ENTRY=\((.*?)^\)", texto, flags=re.M | re.S)
    assert bloque, "deploy-coinalyze no declara ENTRY"
    return dict(re.findall(r"\[([\w-]+)\]=([\w.]+)", bloque.group(1)))


def test_el_punto_de_entrada_declarado_es_el_execstart_de_cada_unidad():
    entradas = _entradas_del_guion()
    assert set(entradas) == {*SERVICIOS, *PARTOF}
    for u, mod in entradas.items():
        unidad = next(p for p in (ROOT / "deploy" / "140" / f"{u}.service", ROOT / "deploy" / "systemd" / f"{u}.service")
                      if p.exists())
        exec_start = re.search(r"^ExecStart=(.*)$", unidad.read_text(encoding="utf-8"), flags=re.M).group(1)
        assert re.search(rf"(-m {re.escape(mod)}|\b{re.escape(mod)}:app)(\s|$)", exec_start), (u, exec_start)


def _cierre(mod: str) -> set[str]:
    r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "cierre_imports.py"), "closure", str(ROOT), mod],
                       text=True, capture_output=True, timeout=60, check=False)
    assert r.returncode == 0, r.stderr
    return set(r.stdout.split())


def test_en_el_app_de_verdad_ningun_colector_importa_la_api():
    """La premisa de R1 sobre el codigo real: un cambio solo en app/api.py no toca el cierre de ningun colector."""
    api = _cierre("app.api")
    assert {"app/api.py", "app/__init__.py", "app/db.py"} <= api
    for u, mod in _entradas_del_guion().items():
        cierre = _cierre(mod)
        assert cierre and all(f.startswith("app/") for f in cierre), (u, sorted(cierre)[:5])
        if u != "coinalyze-api":
            assert "app/api.py" not in cierre, u
    assert "app/db.py" in _cierre("app.ingest")
