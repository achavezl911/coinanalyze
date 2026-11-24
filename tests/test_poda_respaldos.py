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
    # 1 · pre-despliegue fuera de los 2 mas nuevos -> desaparece
    ("predeploy-aaaa1111-20260901000000.sql.gz", 10, False),
    ("predeploy-cccc3333-20260904000000.sql.gz", 4, False),
    # 2 · los 2 pre-despliegue mas nuevos -> sobreviven
    ("predeploy-bbbb2222-20260907000000.sql.gz", 1, True),
    ("predeploy-dddd4444-20260908000000.sql.gz", 0, True),
    # 3 · cifrado dentro de SU vida (4 dias): los cifrados se podan por edad, no por cuenta
    ("coinalyze-full-20260906T031500Z.tar.gz.enc", 4, True),
    ("coinalyze-full-20260906T031500Z.tar.gz.enc.sha256", 4, True),
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
             "PREDEPLOY_KEEP": "2", "BACKUP_RETENTION_DAYS": "4"},
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


def test_la_cuenta_es_un_DATO_y_se_puede_cambiar_sin_tocar_la_logica(directorio: Path):
    """CONTROL QUE SE MUEVE. Con PREDEPLOY_KEEP=3 el tercero mas nuevo (4 d) sobrevive; con 2, no.
    Si la cuenta estuviera incrustada en el bucle, este test no podria moverla."""
    r = subprocess.run(
        ["bash", str(BACKUP), "--solo-podar"],
        env={**os.environ, "BACKUP_DIR": str(directorio), "PREDEPLOY_KEEP": "3"},
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    assert (directorio / "predeploy-cccc3333-20260904000000.sql.gz").exists(), (
        "con la cuenta en 3 el tercero tenia que sobrevivir: la cuenta no se esta leyendo"
    )
    assert not (directorio / "predeploy-aaaa1111-20260901000000.sql.gz").exists()


def test_cuenta_cero_se_niega_y_no_borra(directorio: Path):
    """Con 0 la poda se llevaria el volcado del release que corre: el guion se niega."""
    r = subprocess.run(
        ["bash", str(BACKUP), "--solo-podar"],
        env={**os.environ, "BACKUP_DIR": str(directorio), "PREDEPLOY_KEEP": "0"},
        capture_output=True, text=True, check=False,
    )
    assert r.returncode != 0
    assert len(list(directorio.glob("predeploy-*.sql.gz"))) == 4


def test_las_dos_reglas_estan_declaradas_por_separado():
    """Los cifrados por edad y los pre-despliegue por cuenta, cada uno con su numero."""
    fuente = BACKUP.read_text(encoding="utf-8")
    assert "PREDEPLOY_KEEP=${PREDEPLOY_KEEP:-2}" in fuente
    assert "BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-4}" in fuente


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



def test_antes_del_stage_solo_predeploy_y_los_cifrados_tras_el_respaldo():
    """PRUEBA DEL ORDEN EN EL FICHERO, no de comportamiento: correr el respaldo entero pide
    Postgres y la llave. Dos cosas a la vez:
    - Antes del `mktemp` del STAGE hay una poda de PRE-DESPLIEGUE (`podar_predeploy`): si solo se
      podaba al final, un respaldo que moria por falta de disco no podaba nunca (140, 2026-11-02).
    - Antes del STAGE NO hay `podar_respaldos`: esa poda tambien los cifrados, y si el respaldo
      falla 15 dias seguidos los cifrados caducarian uno a uno hasta no quedar ninguno. Los
      cifrados se podan solo DESPUES de un respaldo correcto: `podar_respaldos` tras el STAGE.
    Cae contra ced2f13, que llamaba a `podar_respaldos` antes del STAGE."""
    lineas = BACKUP.read_text(encoding="utf-8").splitlines()

    def llamadas(nombre: str) -> list[int]:
        return [i for i, ln in enumerate(lineas) if ln.strip() == nombre]

    stage = next(i for i, ln in enumerate(lineas) if ln.startswith("STAGE=$(mktemp"))
    fin_puerta = next(i for i, ln in enumerate(lineas) if "--solo-podar ]]" in ln) + 4  # su `fi`
    assert lineas[fin_puerta].strip() == "fi"
    tramo = range(fin_puerta + 1, stage)
    assert [i for i in llamadas("podar_predeploy") if i in tramo], (
        "no hay poda de pre-despliegue entre la puerta --solo-podar y el mktemp del STAGE"
    )
    assert not [i for i in llamadas("podar_respaldos") if i in tramo], (
        "podar_respaldos antes del STAGE: poda cifrados sin saber si el respaldo de hoy sale"
    )
    assert [i for i in llamadas("podar_respaldos") if i > stage], (
        "falta la poda de cifrados tras el respaldo"
    )


# ---------------------------------------------------------------------------------------------
# MANT R2 · LOS PRE-DESPLIEGUE SE QUEDAN EN LOS 2 MAS NUEVOS. El 2026-11-23 el disco de 140 llego
# al 100 %: 11 `predeploy-*.sql.gz` de ~3.6 GB, todos DENTRO de la vida de 3 dias, asi que la poda
# por edad no borraba ninguno. Contra el backup.sh de main caen los dos tests de abajo: el primero
# porque los 5 estan dentro de los 3 dias y main no borra nada; el segundo porque main borra
# TODOS, tambien el del release activo.
# ---------------------------------------------------------------------------------------------

def _planta(d: Path, edades_h: list[float]) -> list[str]:
    ahora = time.time()
    nombres = []
    for k, h in enumerate(edades_h):
        nombre = f"predeploy-{k:04x}beef-2026112{k}T000000Z.sql.gz"
        for f in (d / nombre, d / f"{nombre}.sha256"):
            f.write_bytes(b"x")
            os.utime(f, (ahora - h * 3600, ahora - h * 3600))
        nombres.append(nombre)
    return nombres


def _cifrados(d: Path) -> list[str]:
    ahora = time.time()
    casos = {"coinalyze-full-20261122T031500Z.tar.gz.enc": 1, "coinalyze-full-20261101T031500Z.tar.gz.enc": 20}
    for nombre, dias in casos.items():
        for f in (d / nombre, d / f"{nombre}.sha256"):
            f.write_bytes(b"x")
            os.utime(f, (ahora - dias * DIAS, ahora - dias * DIAS))
    return sorted(casos)


def _poda_por_defecto(d: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("PREDEPLOY_KEEP", "PREDEPLOY_RETENTION_DAYS",
                                                         "BACKUP_RETENTION_DAYS")}
    return subprocess.run(["bash", str(BACKUP), "--solo-podar"], env={**env, "BACKUP_DIR": str(d)},
                          capture_output=True, text=True, check=False)


def test_cinco_predeploy_quedan_los_dos_mas_nuevos_y_los_cifrados_igual(tmp_path: Path):
    # Edades en horas, desordenadas a proposito: el orden sale del mtime, no del nombre.
    nombres = _planta(tmp_path, [30, 2, 50, 10, 70])
    viejo, nuevo = _cifrados(tmp_path)  # orden por nombre: 1101 (20 d) antes que 1122 (1 d)
    r = _poda_por_defecto(tmp_path)
    assert r.returncode == 0, r.stderr
    quedan = sorted(p.name for p in tmp_path.glob("predeploy-*"))
    assert quedan == sorted([nombres[1], f"{nombres[1]}.sha256", nombres[3], f"{nombres[3]}.sha256"]), quedan
    # Los cifrados, con su poda de siempre: el de 1 dia vive, el de 20 cae, cada uno con su .sha256.
    assert sorted(p.name for p in tmp_path.glob("coinalyze-full-*")) == [nuevo, f"{nuevo}.sha256"]
    assert viejo.endswith("1101T031500Z.tar.gz.enc")
    # Su log: una linea por volcado borrado.
    assert r.stderr.count("poda predeploy: borro predeploy-") == 3, r.stderr


def test_los_dos_mas_nuevos_viven_aunque_pasen_de_tres_dias(tmp_path: Path):
    """Una semana sin desplegar: el volcado del release activo sigue siendo el que revierte."""
    nombres = _planta(tmp_path, [24 * 9, 24 * 5, 24 * 7, 24 * 6, 24 * 8])
    r = _poda_por_defecto(tmp_path)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in tmp_path.glob("predeploy-*.sql.gz")) == sorted([nombres[1], nombres[3]])


def test_sha256_huerfano_se_poda(tmp_path: Path):
    nombres = _planta(tmp_path, [1, 2])
    huerfano = tmp_path / "predeploy-dead0000-20261101T000000Z.sql.gz.sha256"
    huerfano.write_bytes(b"x")
    assert _poda_por_defecto(tmp_path).returncode == 0
    assert not huerfano.exists()
    assert all((tmp_path / f"{n}.sha256").exists() for n in nombres)
