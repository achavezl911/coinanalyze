"""DATOS B (fable-f6 R2): la vigia mira el latido del recuperador de huecos (scripts/recupera_huecos.py). Dos causas nuevas:
«el recuperador no late» y «hueco recuperable sin recuperar con poco reloj». Sin el latido (no instalado o ilegible), sin
juzgar: ni alarma ni resuelve. Quien no le pasa el latido no cambia. Sin base: estas pruebas no la piden.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx

from app.bot import vigia

AHORA = datetime(2026, 11, 15, 10, tzinfo=UTC)
LATIDO = AHORA - timedelta(minutes=1)


def _r(ts=AHORA - timedelta(minutes=20), vence=None, pendientes=0) -> dict:
    urgente = None if vence is None else {"feed": "ohlcv_1min", "symbol": "BTCUSDT_PERP.A", "inicio": "2026-11-14T20:00:00+00:00",
                                          "fin": "2026-11-14T23:00:00+00:00", "vence": vence.isoformat()}
    return {"ts": ts.isoformat(), "pedidas": 3, "pendientes": pendientes, "urgente": urgente}


def _p(recupera) -> dict:
    return vigia.problemas(AHORA, {"ActiveState": "active"}, None, None, LATIDO, True, True, None, recupera=recupera)


def test_un_recuperador_que_late_sin_pendientes_es_sano():
    assert _p(_r()) == {}


def test_el_recuperador_que_no_late_es_problema_y_dice_desde_cuando():
    p = _p(_r(ts=AHORA - timedelta(minutes=91)))
    assert set(p) == {"recupera_latido"} and "no late desde hace 91 min" in p["recupera_latido"]
    assert _p(_r(ts=AHORA - timedelta(minutes=90))) == {}


def test_poco_reloj_avisa_y_mucho_reloj_no():
    p = _p(_r(vence=AHORA + timedelta(hours=11, minutes=59), pendientes=2))
    assert set(p) == {"recupera_reloj"}
    assert p["recupera_reloj"].startswith("hueco recuperable sin recuperar con poco reloj")
    assert "BTCUSDT_PERP.A" in p["recupera_reloj"] and "~11 h" in p["recupera_reloj"] and "2 hueco(s)" in p["recupera_reloj"]
    assert _p(_r(vence=AHORA + timedelta(hours=12), pendientes=2)) == {}


def test_las_dos_a_la_vez_y_con_la_base_caida_tambien():
    r = _r(ts=AHORA - timedelta(hours=3), vence=AHORA + timedelta(hours=1), pendientes=1)
    p = vigia.problemas(AHORA, {"ActiveState": "active"}, None, "OSError x", None, False, False, None, recupera=r)
    assert {"recupera_latido", "recupera_reloj", "base"} <= set(p)


def test_sin_latido_legible_ni_alarma_ni_resuelve_y_se_publica():
    assert _p(None) == {}
    inciertos = vigia.sin_juzgar(AHORA, LATIDO, None, recupera=None)
    assert {"recupera_latido", "recupera_reloj"} <= inciertos
    nuevos, resueltos, _ = vigia.transicion({"recupera_reloj": "x"}, _p(None), inciertos=inciertos)
    assert nuevos == {} and resueltos == []
    assert set(vigia.sin_leer(1, None, AHORA, None)) >= {"recupera_latido", "recupera_reloj"}


def test_quien_no_pasa_el_latido_no_cambia():
    assert vigia.problemas(AHORA, {"ActiveState": "active"}, None, None, LATIDO, True, True, None) == {}
    assert not {"recupera_latido", "recupera_reloj"} & set(vigia.sin_leer(1, None, AHORA))


def test_lee_recupera(tmp_path):
    f = tmp_path / "latido.json"
    assert vigia.lee_recupera(f) is None
    f.write_text("{medio", encoding="utf-8")
    assert vigia.lee_recupera(f) is None
    f.write_text(json.dumps(_r()), encoding="utf-8")
    assert vigia.lee_recupera(f)["pedidas"] == 3


async def test_la_pasada_avisa_del_reloj_una_vez_y_lo_resuelve(tmp_path):
    enviados: list[str] = []

    def responde(r):
        enviados.append(json.loads(r.content)["text"])
        return httpx.Response(200, json={"ok": True})

    async def sin_base():
        raise OSError("sin base en esta prueba")

    def http():
        return httpx.AsyncClient(transport=httpx.MockTransport(responde))

    e = {"TELEGRAM_BOT_TOKEN": "1:p", "TELEGRAM_CHAT_ID": "-1", "BOT_INFORMES": str(tmp_path)}
    f, vivo = tmp_path / "estado.json", {"ActiveState": "active"}
    corto = _r(vence=AHORA + timedelta(hours=2), pendientes=1)
    p = await vigia.pasada(e, http(), vivo, sin_base, f, AHORA, recupera=corto)
    assert "recupera_reloj" in p["notificados"] and "poco reloj" in enviados[-1]
    n = len(enviados)
    p = await vigia.pasada(e, http(), vivo, sin_base, f, AHORA + timedelta(minutes=5), recupera=None)  # ilegible
    assert "recupera_reloj" in p["notificados"] and "recupera_reloj" in p["sin_juzgar"]
    p = await vigia.pasada(e, http(), vivo, sin_base, f, AHORA + timedelta(minutes=10), recupera=_r(ts=AHORA + timedelta(minutes=9)))
    assert "recupera_reloj" not in p["notificados"] and any("resuelto" in t for t in enviados[n:])
