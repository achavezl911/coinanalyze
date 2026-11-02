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
NODO = AHORA - timedelta(hours=7)  # la marca del nodo de la copia de esta madrugada


def _p(disco_libre=None, respaldo=None, nodo=NODO) -> dict:
    return vigia.problemas(AHORA, {"ActiveState": "active"}, None, None, LATIDO, True, True, None,
                           disco_libre=disco_libre, respaldo=respaldo, nodo=nodo)


def _inciertos(disco_libre=None, respaldo=None, nodo=NODO) -> frozenset:
    return vigia.sin_juzgar(AHORA, LATIDO, None, disco_libre=disco_libre, respaldo=respaldo, nodo=nodo)


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
        assert set(vigia.sin_leer(None, respaldo, NODO)) == {"disco", "respaldo"}  # y se publica


def test_un_respaldo_en_curso_no_es_problema_ni_resuelve():
    assert _p(6 * GB, EN_CURSO) == {}
    assert "respaldo" in _inciertos(6 * GB, EN_CURSO)
    assert vigia.transicion({"respaldo": "x"}, {}, inciertos=_inciertos(6 * GB, EN_CURSO)) == ({}, [], [])
    # sin ninguna corrida desde el arranque de la maquina, tampoco se sabe
    assert "respaldo" in vigia.sin_leer(6 * GB, BIEN | {"ExecMainExitTimestamp": ""}, NODO)


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
    p = await vigia.pasada(e, _telegram(enviados), vivo, sin_base, f, AHORA, disco_libre=GB, respaldo=CAYO,
                           nodo=NODO)
    assert {"disco", "respaldo"} <= set(p["notificados"]) and len(enviados) == 1 and p["sin_juzgar"] == {}
    p = await vigia.pasada(e, _telegram(enviados), vivo, sin_base, f, AHORA + timedelta(minutes=5))  # no se pudo leer
    assert set(p["sin_juzgar"]) == {"disco", "respaldo", "respaldo_nodo"} and {"disco", "respaldo"} <= set(p["notificados"])
    assert len(enviados) == 1
    p = await vigia.pasada(e, _telegram(enviados), vivo, sin_base, f, AHORA + timedelta(minutes=10), disco_libre=9 * GB,
                           respaldo=BIEN, nodo=NODO)
    assert not {"disco", "respaldo"} & set(p["notificados"]) and len(enviados) == 2 and "resuelto" in enviados[1]


# --- P148 · respaldo_nodo: los completos viven en el nodo, y el nodo toca NODO_OK tras cada copia correcta ---

def test_el_nodo_reciente_es_sano_y_resuelve():
    assert _p(6 * GB, BIEN, NODO) == {} and "respaldo_nodo" not in _inciertos(6 * GB, BIEN, NODO)
    assert "respaldo_nodo" not in _p(6 * GB, BIEN, AHORA - timedelta(hours=vigia.NODO_MAX_H))  # 36 h justas aun no
    assert vigia.transicion({"respaldo_nodo": "x"}, {}, inciertos=_inciertos(6 * GB, BIEN, NODO)) == ({}, ["respaldo_nodo"], [])


def test_el_nodo_viejo_es_problema_y_dice_cuantas_horas():
    assert vigia.NODO_MAX_H == 36
    p = _p(6 * GB, BIEN, AHORA - timedelta(hours=50, minutes=20))
    assert p == {"respaldo_nodo": "los respaldos no llegan al nodo desde hace 50 h"}
    assert "respaldo_nodo" in _p(6 * GB, BIEN, AHORA - timedelta(hours=36, seconds=1))


def test_el_nodo_ausente_no_alarma_ni_resuelve(tmp_path):
    assert vigia.marca_nodo(tmp_path / "no-existe.ok") is None
    assert _p(6 * GB, BIEN, None) == {}  # nunca problema
    inciertos = _inciertos(6 * GB, BIEN, None)
    assert "respaldo_nodo" in inciertos and "respaldo_nodo" in vigia.sin_leer(6 * GB, BIEN, None)
    assert vigia.transicion({"respaldo_nodo": "x"}, {}, inciertos=inciertos) == ({}, [], [])  # nunca sano


def test_marca_nodo_lee_el_mtime(tmp_path):
    import os
    f = tmp_path / "respaldo-nodo.ok"
    f.write_bytes(b"")
    os.utime(f, (NODO.timestamp(), NODO.timestamp()))
    assert vigia.marca_nodo(f) == NODO


LUNES_TARDE = datetime(2026, 11, 2, 14, tzinfo=UTC)  # lunes, pasadas las 13:30Z: el informe ya se espera


def _informe(apagado: bool | None) -> dict:
    extra = {} if apagado is None else {"informe_apagado": apagado}
    return vigia.problemas(LUNES_TARDE, {"ActiveState": "active"}, None, None, LUNES_TARDE - timedelta(minutes=1), True, False,
                           None, **extra)


def test_apagado_calla_el_informe_y_sin_el_nada_cambia():
    assert [k for k in _informe(None) if k.startswith("informe:")] == [f"informe:{vigia.semana_iso(LUNES_TARDE)}"]
    assert _informe(False) == _informe(None)
    assert not [k for k in _informe(True) if k.startswith("informe:")]


async def test_la_pasada_mira_apagado_en_bot_informes(tmp_path):
    e = {"BOT_INFORMES": str(tmp_path)}  # sin canal: no envia nada
    vivo = {"ActiveState": "active"}
    # sin base el informe no se juzga: una base fingida que contesta lo justo (late, parte si, informe no)
    class Db:
        async def fetchval(self, sql, *a):
            if "SELECT ts FROM bot_estado" in sql:
                return LUNES_TARDE - timedelta(minutes=1)
            if "EXISTS" in sql:
                return "parte" in sql  # parte si, informe no
            return None
        async def execute(self, *a):
            return None
        async def close(self):
            return None
    async def con_base():
        return Db()
    p = await vigia.pasada(e, _telegram([]), vivo, con_base, tmp_path / "e1.json", LUNES_TARDE, 6 * GB, BIEN)
    assert any(k.startswith("informe:") for k in p["problemas"])
    (tmp_path / "APAGADO").write_bytes(b"")
    p = await vigia.pasada(e, _telegram([]), vivo, con_base, tmp_path / "e2.json", LUNES_TARDE, 6 * GB, BIEN)
    assert not any(k.startswith("informe:") for k in p["problemas"])
