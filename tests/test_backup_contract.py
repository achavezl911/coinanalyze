import gzip
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def test_full_backup_is_encrypted_complete_and_excludes_its_key() -> None:
    source = Path("scripts/backup.sh").read_text(encoding="utf-8")

    assert "pg_dump" in source
    assert "source.backup(target)" in source
    assert "copy_tree /opt/coinalyze" in source
    assert "copy_tree /opt/coinalyze-ai-bridge" in source
    assert "copy_tree /etc/coinalyze-ai-bridge" in source
    assert "openssl enc -aes-256-cbc" in source
    assert "--exclude 'backup.key'" in source
    assert "The encryption key is intentionally excluded" in source


def test_backup_excludes_python_build_artifacts() -> None:
    source = Path("scripts/backup.sh").read_text(encoding="utf-8")

    assert "--exclude 'build'" in source


# ---------------------------------------------------------------------------------------------
# D-05 · EL RESPALDO SE VERIFICA ANTES DE PUBLICARSE CON NOMBRE BUENO. Hasta respaldo-r1 el
# guion hacia `mv "$FINAL_PATH.tmp" "$FINAL_PATH"` y DESPUES descifraba y pasaba `gzip -t`: si
# la verificacion fallaba, quedaba un `coinalyze-full-*.tar.gz.enc` sin `.sha256` que la poda
# contaba y la restauracion (K01b) cogia por ser el mas nuevo.
#
# CONDUCTA, no subcadenas: se corre el bloque REAL de backup.sh -su trampa EXIT y todo lo que
# va del cifrado al `.sha256`- con openssl de verdad y una llave temporal del test. El guion
# entero no se puede correr aqui (root, Postgres, /opt). Contra el backup.sh de main caen los
# brazos 2, 3 y 4; el 1 es el control y pasa con los dos.
# ---------------------------------------------------------------------------------------------

ANTES = "coinalyze-full-20261121T030000Z.tar.gz.enc"
AHORA = "coinalyze-full-20261122T030000Z.tar.gz.enc"


def _bloque() -> str:
    sh = (RAIZ / "scripts/backup.sh").read_text(encoding="utf-8")
    trampa = next(ln for ln in sh.splitlines() if ln.startswith("trap ") and "FINAL_PATH.tmp" in ln)
    ini = sh.index("openssl enc -aes-256-cbc -salt")
    fin = sh.rindex("\npodar_respaldos\n")
    return f"{trampa}\n{sh[ini:fin]}\n"


def _corre(d: Path, nombre: str, carga: bytes, corrompe: bool = False) -> subprocess.CompletedProcess[str]:
    real = shutil.which("openssl")
    assert real, "la prueba necesita openssl de verdad"
    stage = d / f".stage-{nombre}"
    stage.mkdir()
    (stage / "payload.tar.gz").write_bytes(carga)
    env = {"PATH": "/usr/bin:/bin"}
    if corrompe:
        # El cifrado sale, pero recortado: deja de ser multiplo del bloque y NO descifra.
        shim = d / "bin/openssl"
        shim.parent.mkdir(exist_ok=True)
        shim.write_text(
            f'#!/bin/bash\n"{real}" "$@" || exit $?\n'
            f'if [[ " $* " == *" -salt "* ]]; then truncate -s -5 "{d}/{nombre}.tmp"; fi\n'
        )
        shim.chmod(0o755)
        env["PATH"] = f"{shim.parent}:/usr/bin:/bin"
    guion = (
        f'set -Eeuo pipefail\numask 077\nBACKUP_DIR="{d}"\nBACKUP_KEY_FILE="{d}/llave"\n'
        f'STAGE="{stage}"\nPLAIN_ARCHIVE="$STAGE/payload.tar.gz"\nFINAL_NAME="{nombre}"\n'
        f'FINAL_PATH="$BACKUP_DIR/$FINAL_NAME"\n{_bloque()}'
    )
    return subprocess.run(["bash", "-c", guion], capture_output=True, text=True, env=env, check=False)


def _quedan(d: Path) -> list[str]:
    return sorted(p.name for p in d.glob("coinalyze-full-*"))


def _sha_cuadra(d: Path, nombre: str) -> bool:
    r = subprocess.run(["sha256sum", "-c", f"{nombre}.sha256"], cwd=d, capture_output=True, check=False)
    return r.returncode == 0


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    (tmp_path / "llave").write_text("llave temporal del test, no la de 140\n")
    return tmp_path


def test_d05_cifrado_bueno_publica_enc_y_sha256(banco: Path) -> None:
    r = _corre(banco, AHORA, gzip.compress(b"respaldo\n"))
    assert r.returncode == 0, r.stderr
    assert _quedan(banco) == [AHORA, f"{AHORA}.sha256"]
    assert _sha_cuadra(banco, AHORA)


def test_d05_carga_que_no_es_gzip_no_deja_nada_con_nombre_de_respaldo(banco: Path) -> None:
    r = _corre(banco, AHORA, b"esto no es un gzip\n")
    assert r.returncode != 0
    assert _quedan(banco) == []


def test_d05_cifrado_que_no_descifra_no_deja_nada_con_nombre_de_respaldo(banco: Path) -> None:
    r = _corre(banco, AHORA, gzip.compress(b"respaldo\n"), corrompe=True)
    assert r.returncode != 0
    assert _quedan(banco) == []


def test_d05_respaldo_corrupto_no_pisa_al_bueno_anterior(banco: Path) -> None:
    assert _corre(banco, ANTES, gzip.compress(b"ayer\n")).returncode == 0
    r = _corre(banco, AHORA, gzip.compress(b"hoy\n"), corrompe=True)
    assert r.returncode != 0
    # El mas nuevo con nombre de respaldo -el que cogeria K01b- sigue siendo el bueno de ayer.
    assert _quedan(banco) == [ANTES, f"{ANTES}.sha256"]
    assert _sha_cuadra(banco, ANTES)
