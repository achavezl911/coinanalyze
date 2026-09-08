"""La poda de respaldos, EJERCITADA: se plantan ficheros y se corre la poda de verdad.

QUE ESTABA ROTO. `scripts/backup.sh` poda por PATRON DE NOMBRE, y sus tres patrones se
escribieron para los respaldos cifrados (`coinalyze-full-*`). Los volcados pre-despliegue
—`predeploy-<sha>-<fecha>.sql.gz`, que escribe el wrapper `/usr/local/sbin/deploy-coinalyze`,
que NO esta en este arbol— no casaban con ninguno, asi que **nada los borraba nunca**. El
2026-09-08 habia 41 ocupando 14.82 GB con el disco de 140 al 88 %; el 2026-08-29 esto ya tiro
produccion con Postgres en bucle de recuperacion por `No space left`.

POR QUE ESTE TEST PLANTA FICHEROS EN VEZ DE COMPROBAR EL PATRON. Afirmar que una cadena casa con
un glob es afirmar sobre el instrumento, no sobre el comportamiento: el defecto original era
justamente que el glob era correcto y la POBLACION estaba incompleta. Aqui la poda ACTUA, y se
cuenta quien sobrevivio.

EL CONTROL, y sin el esto no valdria: los mismos casos contra `scripts/backup.sh` de
`origin/main` dejan VIVOS los dos pre-despliegue viejos. Esta comprobado a mano
(`x1-tmp/po-control.sh`, 2 fallos del banco contra el viejo y 0 contra el nuevo). Aqui no se
repite porque un test no deberia depender de que exista un remoto.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
BACKUP = RAIZ / "scripts" / "backup.sh"

DIAS = 86400
# nombre, edad en dias, sobrevive
CASOS = [
    # 1 · pre-despliegue pasado de su vida (3 dias) -> desaparece
    ("predeploy-aaaa1111-20260901000000.sql.gz", 10, False),
    ("predeploy-cccc3333-20260904000000.sql.gz", 4, False),
    # 2 · pre-despliegue dentro de su vida -> sobrevive
    ("predeploy-bbbb2222-20260907000000.sql.gz", 1, True),
    ("predeploy-dddd4444-20260908000000.sql.gz", 0, True),
    # 3 · cifrado dentro de SU vida, que son 14 y no 3: dos vidas distintas a proposito
    ("coinalyze-full-20260906T031500Z.tar.gz.enc", 5, True),
    ("coinalyze-full-20260906T031500Z.tar.gz.enc.sha256", 5, True),
    ("coinalyze-full-20260801T031500Z.tar.gz.enc", 40, False),
    # 4 · AJENOS de cualquier edad: la poda no puede llevarselos por delante. Los tres del medio
    #     estan elegidos para que se parezcan: llevan «predeploy» o «.sql.gz» o «coinalyze-full»
    #     en el nombre y aun asi no son ninguna de las dos clases.
    ("postgresql.conf.bak", 400, True),
    ("predeploy-notas.txt", 400, True),
    ("mi-predeploy-aaaa.sql.gz", 400, True),
    ("informe.sql.gz", 400, True),
    ("coinalyze-full-README.md", 400, True),
]


@pytest.fixture
def directorio(tmp_path: Path) -> Path:
    ahora = time.time()
    for nombre, dias, _ in CASOS:
        f = tmp_path / nombre
        f.write_bytes(b"x")
        os.utime(f, (ahora - dias * DIAS, ahora - dias * DIAS))
    # Un subdirectorio: `-maxdepth 1` significa que la poda no baja, y hay que verlo.
    sub = tmp_path / "subdir"
    sub.mkdir()
    hondo = sub / "predeploy-eeee5555-2026.sql.gz"
    hondo.write_bytes(b"x")
    os.utime(hondo, (ahora - 400 * DIAS, ahora - 400 * DIAS))
    return tmp_path


def podar(directorio: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(BACKUP), "--solo-podar"],
        env={**os.environ, "BACKUP_DIR": str(directorio),
             "PREDEPLOY_RETENTION_DAYS": "3", "BACKUP_RETENTION_DAYS": "14"},
        capture_output=True, text=True, check=False,
    )


def test_la_poda_actua_y_deja_exactamente_lo_que_debe(directorio: Path):
    """EL BRAZO QUE IMPORTA: se planta, se poda de verdad, y se cuenta quien queda."""
    r = podar(directorio)
    assert r.returncode == 0, r.stderr
    errores = []
    for nombre, dias, sobrevive in CASOS:
        existe = (directorio / nombre).exists()
        if existe is not sobrevive:
            errores.append(
                f"{nombre} ({dias} d): esperaba {'VIVE' if sobrevive else 'BORRADO'}, "
                f"salio {'VIVE' if existe else 'BORRADO'}"
            )
    assert not errores, "\n".join(errores)
    # Las dos cifras, no una: cuantos habia y cuantos quedan.
    quedan = sum(1 for n, _, s in CASOS if s)
    assert len(list(directorio.glob("*"))) == quedan + 1, "sobra o falta algo en el directorio"


def test_la_poda_no_baja_de_directorio(directorio: Path):
    """`-maxdepth 1`: un pre-despliegue de 400 dias en un subdirectorio NO se toca. Podar mas
    hondo de lo declarado seria borrar cosas de las que este script no responde."""
    podar(directorio)
    assert (directorio / "subdir" / "predeploy-eeee5555-2026.sql.gz").exists()


def test_la_vida_es_un_DATO_y_se_puede_cambiar_sin_tocar_la_logica(directorio: Path):
    """CONTROL QUE SE MUEVE. Con la vida en 30 dias, el de 10 sobrevive; con 3, no. Si la vida
    estuviera incrustada en la linea del `find`, este test no podria moverla."""
    r = subprocess.run(
        ["bash", str(BACKUP), "--solo-podar"],
        env={**os.environ, "BACKUP_DIR": str(directorio), "PREDEPLOY_RETENTION_DAYS": "30"},
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    assert (directorio / "predeploy-aaaa1111-20260901000000.sql.gz").exists(), (
        "con la vida en 30 dias el de 10 tenia que sobrevivir: la vida no se esta leyendo"
    )


def test_las_dos_vidas_estan_declaradas_por_separado():
    """Son dos vidas distintas y tienen que verse como dos. Un solo numero para las dos clases
    fue lo que dejo a los pre-despliegue sin podar."""
    fuente = BACKUP.read_text(encoding="utf-8")
    assert "PREDEPLOY_RETENTION_DAYS=${PREDEPLOY_RETENTION_DAYS:-3}" in fuente
    assert "BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}" in fuente


def test_podar_el_directorio_de_produccion_sigue_exigiendo_root():
    """La guarda se afino para poder probar, NO se quito. Sin root y contra el directorio de
    verdad, el script tiene que negarse."""
    if os.geteuid() == 0:
        pytest.skip("se corre como root: esta guarda solo se puede ver desde un usuario normal")
    r = subprocess.run(
        ["bash", str(BACKUP), "--solo-podar"],
        env={k: v for k, v in os.environ.items() if k != "BACKUP_DIR"},
        capture_output=True, text=True, check=False,
    )
    assert r.returncode != 0
    assert "root" in r.stderr
