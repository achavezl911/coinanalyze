"""DISCO: la vigia del bot avisa del disco de / y del respaldo diario (coinalyze-backup), una vez al aparecer y una al
resolverse, por el mismo camino que los demas (problemas, transicion, mensajes). Lo que no se pudo leer no alarma ni
resuelve un aviso en pie (sin_juzgar), y se publica en `sin_juzgar`. Sin base: estas pruebas no la piden.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx

from app.bot import vigia

AHORA = datetime(2026, 11, 2, 10, tzinfo=UTC)
LATIDO = AHORA - timedelta(minutes=1)
GB = 10**9
BIEN = {"LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead", "Result": "success", "ExecMainStatus": "0",
        "ExecMainExitTimestamp": "Mon 2026-11-02 03:12:00 UTC"}
CAYO = BIEN | {"ActiveState": "failed", "SubState": "failed", "Result": "exit-code", "ExecMainStatus": "1"}
EN_CURSO = BIEN | {"ActiveState": "activating", "SubState": "start", "ExecMainExitTimestamp": ""}


def _p(disco_libre=None, respaldo=None) -> dict:
    return vigia.problemas(AHORA, {"ActiveState": "active"}, None, None, LATIDO, True, True, None,
                           disco_libre=disco_libre, respaldo=respaldo)


def _inciertos(disco_libre=None, respaldo=None) -> frozenset:
    return vigia.sin_juzgar(AHORA, LATIDO, None, disco_libre=disco_libre, respaldo=respaldo)


def test_las_dos_alarmas_aparecen_y_dicen_cuanto_queda():
    p = _p(int(4.2 * GB), CAYO)
    assert set(p) == {"disco", "respaldo"}
    assert "4.2 GB" in p["disco"] and "umbral 5 GB" in p["disco"]
    assert "failed/exit-code" in p["respaldo"] and "salida 1" in p["respaldo"]
    nuevos, resueltos, caducados = vigia.transicion({}, p, inciertos=_inciertos(int(4.2 * GB), CAYO))
    assert nuevos == p and resueltos == caducados == []
    [(tipo, texto)] = vigia.mensajes(nuevos, resueltos, {})
    assert tipo == "alerta" and p["disco"] in texto and p["respaldo"] in texto
    # la siguiente pasada con lo mismo no repite el aviso
    assert vigia.transicion(p, p, inciertos=_inciertos(int(4.2 * GB), CAYO)) == ({}, [], [])


def test_las_dos_se_resuelven():
    avisados = _p(int(4.2 * GB), CAYO)
    sano = _p(6 * GB, BIEN)
    assert sano == {} and _inciertos(6 * GB, BIEN) == frozenset({"bybit"})
    nuevos, resueltos, caducados = vigia.transicion(avisados, sano, inciertos=_inciertos(6 * GB, BIEN))
    assert nuevos == {} and sorted(resueltos) == ["disco", "respaldo"] and caducados == []
    [(tipo, texto)] = vigia.mensajes(nuevos, resueltos, avisados)
    assert tipo == "resuelto" and avisados["disco"] in texto and avisados["respaldo"] in texto


def test_el_umbral_es_5_gb_justos():
    assert "disco" in _p(5 * GB - 1, BIEN) and "disco" not in _p(5 * GB, BIEN)


def test_la_lectura_fallida_no_alarma_ni_se_calla():
    avisados = _p(int(4.2 * GB), CAYO)
    for respaldo in (None, {}, {"ActiveState": "inactive"}, BIEN | {"LoadState": "not-found"}):
        assert _p(None, respaldo) == {}  # no alarma
        inciertos = _inciertos(None, respaldo)
        assert {"disco", "respaldo"} <= inciertos
        assert vigia.transicion(avisados, {}, inciertos=inciertos) == ({}, [], [])  # y no da por resuelto lo avisado
        assert set(vigia.sin_leer(None, respaldo)) == {"disco", "respaldo"}  # y se publica


def test_un_respaldo_en_curso_no_es_problema_ni_resuelve():
    assert _p(6 * GB, EN_CURSO) == {}
    assert "respaldo" in _inciertos(6 * GB, EN_CURSO)
    assert vigia.transicion({"respaldo": "x"}, {}, inciertos=_inciertos(6 * GB, EN_CURSO)) == ({}, [], [])
    # sin ninguna corrida desde el arranque de la maquina, tampoco se sabe
    assert "respaldo" in vigia.sin_leer(6 * GB, BIEN | {"ExecMainExitTimestamp": ""})


def test_quien_ya_llama_a_problemas_sin_los_argumentos_nuevos_no_cambia():
    assert vigia.problemas(AHORA, {"ActiveState": "active"}, None, None, LATIDO, True, True, None) == {}


def test_la_base_caida_no_esconde_disco_ni_respaldo():
    p = vigia.problemas(AHORA, {"ActiveState": "active"}, None, "OSError x", None, False, False, None,
                        disco_libre=GB, respaldo=CAYO)
    assert set(p) == {"base", "disco", "respaldo"}


def _telegram(enviados: list):
    def responde(r):
        enviados.append(json.loads(r.content)["text"])
        return httpx.Response(200, json={"ok": True})
    return httpx.AsyncClient(transport=httpx.MockTransport(responde))


async def test_la_pasada_avisa_una_vez_publica_lo_no_leido_y_resuelve(tmp_path):
    async def sin_base():
        raise OSError("sin base en esta prueba")
    e = {"TELEGRAM_BOT_TOKEN": "1:p", "TELEGRAM_CHAT_ID": "-1", "BOT_INFORMES": str(tmp_path)}
    f, enviados, vivo = tmp_path / "estado.json", [], {"ActiveState": "active"}
    p = await vigia.pasada(e, _telegram(enviados), vivo, sin_base, f, AHORA, disco_libre=GB, respaldo=CAYO)
    assert {"disco", "respaldo"} <= set(p["notificados"]) and len(enviados) == 1 and p["sin_juzgar"] == {}
    p = await vigia.pasada(e, _telegram(enviados), vivo, sin_base, f, AHORA + timedelta(minutes=5))  # no se pudo leer
    assert set(p["sin_juzgar"]) == {"disco", "respaldo"} and {"disco", "respaldo"} <= set(p["notificados"])
    assert len(enviados) == 1
    p = await vigia.pasada(e, _telegram(enviados), vivo, sin_base, f, AHORA + timedelta(minutes=10), disco_libre=9 * GB,
                           respaldo=BIEN)
    assert not {"disco", "respaldo"} & set(p["notificados"]) and len(enviados) == 2 and "resuelto" in enviados[1]
