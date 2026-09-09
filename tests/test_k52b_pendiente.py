"""K52b: un cubo que aún no puede contestar no es un cubo que calla.

QUÉ PASÓ. El 2026-09-08, al enseñarle a K52b el campo `missing_minutes`, escribí en su comentario
que si el cubo no se ha cerrado «`juzgable()` ya lo habrá eximido más arriba». **Era falso.** Los
dos asentamientos son distintos y no se hablan:

    el check   ASIENTO = 6 min, medido contra el ARRANQUE   (`a + ancho > ahora - ASIENTO`)
    la ruta    10 min, medido contra el FIN DEL CUBO        (`cubo + ancho <= now() - 10`)

Como un arranque puede caer en el primer segundo de su cubo, el check llegaba a juzgar hasta
CUATRO minutos antes de que la ruta pudiera contestar, y salía un rojo falso **intermitente y
dependiente del reloj** — de los que se miran una vez, salen verdes al reintentar y se archivan
como «cosas del canal». La cabecera del propio check lo dice: un rojo falso repetido es lo que
enseña a ignorar el que sí lo es.

NO SE ARREGLÓ HACIENDO QUE 6 Y 10 COINCIDAN. Dos constantes que casan por acuerdo se separan
solas la próxima vez que alguien toque una: es lo que le pasó a K18 con su ventana copiada y a
`SESSION_MIN_COVERAGE_RATIO` contra `MUESTRAS_MINIMAS_DIA`. **Se le pregunta a la fila.**

Y HAY DOS NULOS QUE NO SON EL MISMO, que es la regla de K03 otra vez:
    el campo NO ESTÁ          -> la ruta no publica esto: NO es excusa, se condena
    el campo está y vale NULO -> la ruta no puede contestar aún: no juzgable, y se declara
Sin esa distinción el check se pondría verde contra la respuesta vieja, que es aflojarlo.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
CHECK = RAIZ / "harness" / "checks" / "K52b-la-ruta-no-falla-abierta.sh"
# El check hace `. /srv/coinanalyze/harness/env` con ruta fija. Donde no exista -CI- no se puede
# ejecutar, y se dice en vez de fingir que paso.
ENV_ARNES = Path("/srv/coinanalyze/harness/env")

pytestmark = pytest.mark.skipif(
    not ENV_ARNES.exists(),
    reason="K52b carga /srv/coinanalyze/harness/env con ruta fija; aqui no esta (corre en 143)",
)

ANCHO = timedelta(minutes=15)


def _cubo(inicio: datetime, missing, *, present: int = 15, short: int = 0) -> dict:
    fila = {
        "bucket": inicio.isoformat().replace("+00:00", "Z"),
        "whale_delta": 0.0, "covered_seconds_min": 60,
        "short_minutes": short, "unknown_minutes": 0,
        "minutes_expected": 15, "minutes_present": present,
    }
    if missing is not ...:            # `...` = la ruta VIEJA, que no publica el campo
        fila["missing_minutes"] = missing
    return fila


def _monta(tmp_path: Path, missing) -> tuple[Path, Path]:
    """Un arco de 24 h de cubos completos y, al final, EL CASO: un cubo que cerró hace 8 minutos
    —dentro del asentamiento de la ruta y fuera del del check— con un arranque a los 30 s de
    abrirse. Ese es el hueco entre los dos márgenes."""
    ahora = datetime.now(UTC)
    inicio = ahora - timedelta(minutes=8) - ANCHO
    arranque = inicio + timedelta(seconds=30)

    filas, t = [], inicio - timedelta(hours=24)
    while t < inicio:
        filas.append(_cubo(t, 0 if missing is not ... else ...))
        t += ANCHO
    filas.append(_cubo(inicio, missing, present=14))

    cuerpo = tmp_path / "cuerpo.json"
    cuerpo.write_text(json.dumps({"rows": filas}), encoding="utf-8")
    suelo = (inicio - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    journal = tmp_path / "journal.txt"
    journal.write_text(
        f"{suelo} h systemd[1]: Started coinalyze-ws.service.\n"
        f"{arranque.strftime('%Y-%m-%dT%H:%M:%S+00:00')} h systemd[1]: Started coinalyze-ws.service.\n",
        encoding="utf-8",
    )
    return cuerpo, journal


def _correr(cuerpo: Path, journal: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(CHECK)],
        env={**os.environ, "K52B_CUERPO": str(cuerpo), "K52B_JOURNAL": str(journal)},
        capture_output=True, text=True, check=False,
    )


def test_un_cubo_que_aun_no_puede_contestar_NO_es_un_rojo(tmp_path):
    """C2 · con `missing_minutes` NULO el check NO condena. Sale NO MEDIDO (rc=2) porque en este
    banco el único arranque queda sin juzgar, que es lo correcto: no es verde, es «no lo sé»."""
    r = _correr(*_monta(tmp_path, None))
    assert r.returncode != 1, f"rojo falso: {r.stdout[:200]}"
    assert r.returncode == 2, r.stdout[:200]


def test_el_MISMO_payload_con_un_numero_da_la_vuelta_al_veredicto(tmp_path):
    """D2 · EL CONTROL QUE LO AÍSLA. Cambia UN campo —NULO por 1— y el veredicto se mueve, así
    que lo que decidía era el NULO y no otra cosa del banco."""
    r = _correr(*_monta(tmp_path, 1))
    assert r.returncode == 0, r.stdout[:300]


def test_el_campo_AUSENTE_no_es_excusa_y_sigue_condenando(tmp_path):
    """EL BRAZO QUE IMPIDE AFLOJAR EL CHECK. La ruta vieja no publica `missing_minutes`; eso NO
    es «no puedo contestar aún», es «no lo publico». Tiene que seguir siendo rojo, o el arreglo
    habría sido apagar el check en vez de arreglarlo."""
    r = _correr(*_monta(tmp_path, ...))
    assert r.returncode == 1, f"dejo de condenar la respuesta vieja: {r.stdout[:300]}"
    assert "SIN PUBLICAR" in r.stdout


def test_un_pendiente_no_envenena_a_los_demas_y_se_DECLARA(tmp_path):
    """C3 · con un arranque declarado y otro pendiente, el check sale VERDE y dice cuántos
    quedaron sin juzgar y por qué. Un no-juzgado que no se cuenta es un silencio."""
    ahora = datetime.now(UTC)
    ini_pend = ahora - timedelta(minutes=8) - ANCHO
    ini_ok = ini_pend - timedelta(hours=3)
    filas, t = [], ini_pend - timedelta(hours=24)
    while t < ini_pend:
        filas.append(_cubo(t, 1, present=14) if t == ini_ok else _cubo(t, 0))
        t += ANCHO
    filas.append(_cubo(ini_pend, None, present=14))
    cuerpo = tmp_path / "c.json"
    cuerpo.write_text(json.dumps({"rows": filas}), encoding="utf-8")
    suelo = (ini_pend - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    journal = tmp_path / "j.txt"
    journal.write_text(
        "\n".join(
            [f"{suelo} h systemd[1]: Started coinalyze-ws.service."]
            + [f"{(x + timedelta(seconds=30)).strftime('%Y-%m-%dT%H:%M:%S+00:00')} h systemd[1]: "
               "Started coinalyze-ws.service." for x in (ini_ok, ini_pend)]
        ) + "\n",
        encoding="utf-8",
    )
    r = _correr(cuerpo, journal)
    assert r.returncode == 0, r.stdout[:300]
    assert "aun no puede contestar" in r.stdout, r.stdout[:400]
