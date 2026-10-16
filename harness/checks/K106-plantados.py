#!/usr/bin/env python3
"""K106-plantados · el escenario bueno y cada plantado de K106-control (campana 137).

  base <dsn> <dir>      sobre una base DESECHABLE ya sembrada por K105-control-siembra (BTC con un
                        DISPARADO vivo por version, con el generador REAL), pide la respuesta a la
                        ruta de verdad -vista.construir del arbol- y la deja en <dir>/base.json
  lista                 una linea por brazo: nombre, veredicto esperado, patron del hallazgo que lo
                        tiene que condenar, opciones de la sonda y que se planta
  planta <nombre> <dir> deja el brazo listo: <dir>/respuesta.json (lo que el banco sirve; si el
                        brazo es «la ruta caida», no existe) y <dir>/sobre/ (los ficheros de static/
                        que el banco sirve EN VEZ de los del arbol: la pantalla plantada). Imprime
                        la huella de lo servido antes -el escenario bueno- y despues.

Un plantado de RESPUESTA cambia lo que la ruta sirve; uno de PANTALLA anade al final del fichero de
la vista unas lineas que pintan lo que no se puede pintar. El arbol no se toca: el banco sirve el
fichero plantado desde <dir>/sobre.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))


# LAS SERIES REGISTRADAS que fabrica el banco (campana 138), terminadas en el corte a 13.9 s.
_SERIES = {"LONG": ["LONG"] * 40, "SHORT": ["SHORT"] * 40, "NO OPERAR": ["NO OPERAR"] * 40,
           "oscila": ["LONG", "NO OPERAR"] * 20, "parado": ["LONG"] * 40}


def _decide(scalp: str | None, edad: float = 5.0, *, patron: str | None = None, instante: str | None = None,
            grande: str | None = None):
    """Lo que build_mesa_decide(frame="swing") sirve, reducido a lo que la vista lee de el. v3 (campana 138): la
    palabra del scalp es la que el sistema SOSTIENE, con la memoria FIEL que da la regla de la RUTA sobre una serie
    fabricada (`patron`; por omision, la de `scalp`) y la palabra del instante (por omision, `scalp`). `grande`
    planta la palabra grande TAL CUAL, que es como un brazo monta una que no sale de su regla."""
    if scalp is None:
        return None
    from datetime import UTC

    from app import ai_context as A

    corte = datetime.now(UTC)
    patron = patron or ("LONG" if scalp == "NO EVALUABLE" else scalp)
    palabras = _SERIES[patron]
    ultima = corte - timedelta(seconds=90 if patron == "parado" else 3)
    serie = [(ultima - timedelta(seconds=13.9 * (len(palabras) - 1 - i)), p) for i, p in enumerate(palabras)]
    inst = instante or scalp
    m = A.palabra_sostenida(serie, instante=inst, as_of=corte,
                            motivo_instante="data_confidence 12 < 70" if inst == "NO EVALUABLE" else None)
    assert grande or m["value"] == scalp, f"plantados: la regla da {m['value']} y el escenario fiel pide {scalp}"
    return {"max_age_s": 120.0, "age": {"snapshot_lag_seconds": {"value": edad, "status": "ok"}},
            "envelope_cut": {"as_of": corte.isoformat()},
            "decide": {"bias": {"value": "NO EVALUABLE", "source_key": "mesa.decide.frame",
                                "motivo": "la lectura del operador es del SCALP, no de SWING"}},
            "lectura_scalp": {"bias": {"value": grande or m["value"], "source_key": A.MEMORIA_FUENTE,
                                       "motivo": m["motivo"]},
                              "instante": {"value": inst, "source_key": "operator_read.state", "status": "ok"},
                              "memoria": {k: v for k, v in m.items() if k not in ("value", "motivo")}}}


async def base(dsn: str, destino: Path) -> None:
    import asyncpg

    from app.entradas import registro as G
    from app.entradas import vista as V

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET TIME ZONE 'UTC'")
        T = await conn.fetchval("SELECT max(vela_cierre) FROM entrada_registro")
        await G.latir(conn, vela_cierre=T, estado="ok", duracion_s=1.0, detalle={}, error=None)

        async def palabra(_c, _s, *, frame):
            return _decide("LONG")

        r = await V.construir(conn, symbol="BTCUSDT_PERP.A", activo="BTC", palabra_de_decide=palabra)
    finally:
        await conn.close()
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "base.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    vivos = [p for c in r["vivo"]["celdas"] for v in c["por_version"] for p in v["disparados"]]
    print(f"base: {len(json.dumps(r, ensure_ascii=False).encode())} B · {len(vivos)} DISPARADOS vivos "
          f"({', '.join(sorted({p['version'] for p in vivos}))}) · "
          f"{sum(len(v['vigilando']) for c in r['vivo']['celdas'] for v in c['por_version'])} VIGILANDO")


# --------------------------------------------------------------------------- utiles de plantado


def _vivos(r):
    return [p for c in r["vivo"]["celdas"] for v in c["por_version"] for p in v["disparados"]]


def _vigilando(r):
    return [p for c in r["vivo"]["celdas"] for v in c["por_version"] for p in v["vigilando"]]


def _mas(r, segundos: float) -> str:
    return (datetime.fromisoformat(r["as_of"]) + timedelta(seconds=segundos)).isoformat()


def _caduca(r, segundos: float):
    for p in _vivos(r):
        p["caduca_en"] = _mas(r, segundos)
    for v in r["reciente"]["por_version"]:
        for p in v["disparados"]:
            p["caduca_en"] = _mas(r, segundos)


def _coste(r, bps: float, fraccion: float):
    """El DISPARADO con T1 a 932,1 bps -el escenario base ya lo trae asi: es el plan que midio el operador,
    con su pata del objetivo a 2,00 bps, 0,002 del objetivo- y la pata del objetivo costando `bps`, que
    son `fraccion` del objetivo. En lo vivo y en lo reciente: es el mismo plan."""
    for p in [*_vivos(r), *(p for v in r["reciente"]["por_version"] for p in v["disparados"])]:
        p["t1_distancia_bps"] = 932.1
        p["costes"][1].update(bps=bps, x_objetivo=fraccion)


def _no_disponible(r):
    """Lo que vista.componer sirve cuando la base no tiene las tablas del registro."""
    for k in [k for k in r if k not in ("esquema", "as_of", "symbol", "activo", "que_es", "frescura", "decide")]:
        r.pop(k)
    r.update(disponible=False, motivo="esta base no tiene las tablas del registro de entradas: falta desplegar")


def _a_medias(r):
    """El ultimo latido es de la vela ANTERIOR a la de los planes servidos: la pasada esta en curso."""
    from app.entradas import reglamento as R
    from app.entradas import vista as V
    lat = r["generador"]["ultimo_latido"]
    ultima = max(p["vela_cierre"] for p in _vivos(r) + _vigilando(r))
    lat["vela_cierre"] = (datetime.fromisoformat(ultima) - timedelta(minutes=15)).isoformat()
    r["generador"]["pasada_en_curso"] = V.pasada_en_curso(R.cargar_valido(), ultima, lat["vela_cierre"])
    assert r["generador"]["pasada_en_curso"], "plantados: la pasada no quedo a medias"


def _palabra(r, scalp, edad: float = 5.0, **memoria):
    from app.entradas import vista as V
    r["decide"] = V._decide(_decide(scalp, edad, **memoria), None if scalp else "DECIDE fallo al calcularse (RuntimeError)")


def _cruza(r, palabra_pintada, frase_de):
    """La RESPUESTA ya viene cruzada: la palabra de una y la frase (y las etiquetas) de otra."""
    from app.entradas import vista as V
    _palabra(r, frase_de)
    x = r["decide"]["perfiles"]["intradia"]
    x["palabra"], x["rotulo"] = palabra_pintada, palabra_pintada
    if palabra_pintada == "NO EVALUABLE":
        x["motivo"] = "data_confidence 12 < 70"
    assert V  # la frase y `para` siguen siendo las de `frase_de`


def _resultado(r, salida: str | None, hace_s: float) -> dict:
    """El resultado que la vista sirve (campana 139) para una salida, acabado hace `hace_s`: siempre con las
    MISMAS claves, para que dos que solo difieren en la salida solo difieran en su texto. Sin salida, CADUCADO."""
    from app.entradas import resolutor as RES
    from app.entradas import vista as V
    gana = salida == "objetivo"
    instante = (datetime.fromisoformat(r["as_of"]) - timedelta(seconds=hace_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return V._resultado({"estado": RES.ACABADO, "salida": salida or RES.CADUCADO, "firmeza": RES.FINAL,
                         "instante": instante, "motivo": None, "asentado_en": instante,
                         "entrada": {"instante": instante, "precio": 100.0}, "precio": 102.0 if gana else 99.0,
                         "pnl": {"r_neto": 1.5 if gana else -1.0, "bps_netos": 150.0 if gana else -100.0}})


def _resueltos(r, orden, misma_hora: bool = False):
    """Tres DISPARADOS caducados de la activa, a horas distintas (o a la MISMA: el empate), con un
    RESULTADO cada uno (el que sirve la E3). Con n < 30, ni el color ni el orden pueden depender de el."""
    activa = r["reciente"]["por_version"][0]
    modelo = copy.deepcopy((activa["disparados"] or _vivos(r))[0])
    activa["disparados"] = []
    for i, resultado in enumerate(orden):
        p = copy.deepcopy(modelo)
        hace = 5 if misma_hora else i + 5
        p.update({"registro_id": 9000 + (len(orden) - i if misma_hora else i), "vela_cierre": _mas(r, -3600 * hace),
                  "registered_at": _mas(r, -3600 * hace + 140),
                  "caduca_en": _mas(r, -3600 * (i + 1)), "caducado": True, "vivo": False,
                  "resultado": _resultado(r, resultado, 3600 * (i + 1))})
        activa["disparados"].append(p)
    activa["sin_planes"] = None


def _acaba_vivo(r):
    """El primer DISPARADO de lo vivo acaba en su STOP hace 10 min, y la respuesta lo sirve COMO LO SERVIRIA LA
    RUTA (gemelo fiel para toda la red): fuera de lo vivo, con la frase de su celda vacia, y en lo reciente no
    vivo y con su resultado. Devuelve su registro_id."""
    from app.entradas import vista as V
    for c in r["vivo"]["celdas"]:
        for v in c["por_version"]:
            if v["disparados"]:
                p = v["disparados"].pop(0)
                if not v["disparados"] and not v["vigilando"]:
                    v["sin_planes"] = (f"{v['version']} no tiene ningun plan vivo en {c['perfil']} · {c['lado']}: "
                                       "ningun episodio abierto ni DISPARADO vivo (los que ya acabaron estan en lo "
                                       "reciente, con su salida)")
                for b in r["reciente"]["por_version"]:
                    for q in b["disparados"]:
                        if q["registro_id"] == p["registro_id"]:
                            q.update(vivo=False, resultado=_resultado(r, "stop", 600))
                assert V
                return p["registro_id"]
    raise AssertionError("plantados: no hay ningun DISPARADO vivo que acabar")


def _anterior(r):
    """Un DISPARADO anterior a la ventana en lo reciente de la activa: su fila corta y su resultado (E3)."""
    from app.entradas import vista as V
    activa = r["reciente"]["por_version"][0]
    modelo = _vivos(r)[0]
    activa["anteriores"] = [{"registro_id": 8000, "version": activa["version"], "familia": modelo["familia"],
                             "perfil": modelo["perfil"], "lado": modelo["lado"], "vela_cierre": _mas(r, -3 * 86400),
                             "caduca_en": _mas(r, -3 * 86400 + 4 * 3600), "resultado": _resultado(r, "stop", 2 * 86400)}]
    activa["anteriores_que_es"] = V.ANTERIORES_QUE_ES


# Lo que se anade al FINAL de static/mesa/mesa-entradas.js para plantar una pantalla.
def _tras_pintar(cuerpo: str) -> str:
    return ("\n/* PLANTADO por K106-plantados.py */\n(function () {\n  const pintar0 = pintarEntradas;\n"
            "  pintarEntradas = function (sobre) {\n    pintar0(sobre);\n" + cuerpo + "\n  };\n})();\n")


def _tras_tic(cuerpo: str) -> str:
    return ("\n/* PLANTADO por K106-plantados.py */\n(function () {\n  const tic0 = entTicTac;\n"
            "  entTicTac = function () {\n    tic0();\n" + cuerpo + "\n  };\n})();\n")


def _escribe(texto: str) -> str:
    return _tras_pintar("    const f = document.querySelector('#ent-vivo [data-plan]') || document.getElementById('ent-vivo');\n"
                        "    const s = document.createElement('span');\n"
                        f"    s.textContent = {json.dumps(' ' + texto, ensure_ascii=False)};\n    f.appendChild(s);")


POR_RESULTADO = ("    const res = {};\n    ((_ent && _ent.datos.reciente.por_version) || []).forEach((v) => v.disparados.forEach((p) => { res[p.registro_id] = p.resultado && (/^OBJETIVO/.test(p.resultado.rotulo || '') ? 'objetivo' : 'stop'); }));\n"
                 "    const filas = Array.from(document.querySelectorAll('#ent-reciente [data-plan]')).filter((f) => res[f.dataset.plan]);\n")
NO_REPINTA = ("\n/* PLANTADO por K106-plantados.py */\n(function () {\n  const pintar0 = pintarEntradas;\n  let hecho = false;\n"
              "  pintarEntradas = function (sobre) {\n    if (hecho) return;\n    hecho = true;\n    pintar0(sobre);\n  };\n})();\n")


def _segunda(r):
    """La respuesta que llega en el refresco siguiente: OTRO instante del mercado."""
    r["frescura"]["refresco_s"] = 3
    _palabra(r, "SHORT")
    for v in _vigilando(r):
        v["distancia"].update(pct=round(v["distancia"]["pct"] + 1.23, 2))
    r["precio"]["valor"] = round(r["precio"]["valor"] + 1.0, 3)


# Brazos con DOS respuestas: la sonda ejecuta {D}/cambia.sh a media observacion y el banco pasa a servir esta.
SEGUNDA = {"dos_respuestas": _segunda, "no_repinta": _segunda}
SIEMPRE_VIVO = _tras_tic("    document.querySelectorAll('#ent-vivo [data-plan]').forEach((f) => {\n      f.setAttribute('data-vivo', 'si');\n"
                         "      const c = f.querySelector('[data-chip]');\n"
                         "      if (c && _ent) c.textContent = f.dataset.tipo === 'disparado' ? _ent.datos.vivo.rotulos.disparado_vivo : _ent.datos.vivo.rotulos.vigilando;\n    });\n"
                         "    const a = document.getElementById('ent-aviso'); a.hidden = true; while (a.firstChild) a.removeChild(a.firstChild);\n"
                         "    document.getElementById('vista-entradas').classList.remove('ent-no-se-sabe');")
RELOJ_PARADO = ("\n/* PLANTADO por K106-plantados.py */\n(function () {\n  const tic0 = entTicTac;\n  let hecho = false;\n"
                "  entTicTac = function () {\n    if (hecho) return;\n    hecho = true;\n    tic0();\n  };\n})();\n")

# nombre, veredicto, patron, opciones de la sonda, que hace a la respuesta (o None), que anade a la
# pantalla (o None), que se planta. `{D}` es el directorio del brazo.
# El formato de antes de R2: la fraccion del objetivo redondeada a dos decimales en el cliente.
DOS_DECIMALES = "\n/* PLANTADO por K106-plantados.py */\nFMT.x = (v) => 'x' + num(v, 2) + ' del objetivo';\n"

BRAZOS: list[tuple] = [
    # ---- C1 · lo vivo, lo caducado, sin dato, dos versiones
    ("vivo", "PASA", "", ["--luego", "@3"], None, None,
     "el escenario bueno: un DISPARADO vivo por version, entero y con su cuenta atras corriendo"),
    ("caducado", "PASA", "", [], lambda r: _caduca(r, -60), None,
     "el mismo DISPARADO ya caducado y todavia servido entre lo vivo: la pantalla lo da por caducado"),
    ("caducado_pintado_vivo", "CONDENA", "E4 el DISPARADO .* caduco hace .* sigue en pantalla como vivo", [],
     lambda r: _caduca(r, -60), SIEMPRE_VIVO, "una pantalla que lo sigue pintando como vivo"),
    ("caduca_en_pantalla", "PASA", "", ["--luego", "@12"], lambda r: _caduca(r, 8), None,
     "caduca a los 8 s de cargar: a los 12 la pantalla ya no lo da por vivo, sin recargar"),
    ("caduca_y_sigue_vivo", "CONDENA", "E4 el DISPARADO .* caduco hace .* sigue en pantalla como vivo", ["--luego", "@12"],
     lambda r: _caduca(r, 8), SIEMPRE_VIVO, "caduca en pantalla y la pantalla no se entera"),
    ("ruta_caida", "PASA", "", [], "CAIDA", None, "la ruta no contesta al cargar: la pantalla lo dice arriba"),
    ("ruta_caida_callada", "CONDENA", "E4 la ruta no dio dato .* la vista NO lo dice arriba", [], "CAIDA", SIEMPRE_VIVO,
     "la ruta no contesta y la pantalla no dice nada"),
    ("ruta_cae_despues", "PASA", "", ["--luego", "{D}/cae.sh@7"],
     lambda r: r["frescura"].update(refresco_s=3), None,
     "la ruta cae con la vista abierta: al primer refresco fallido lo dice y nada queda como vivo"),
    ("cae_y_sigue_vivo", "CONDENA", "E4 la ruta no dio dato .* (NO lo dice arriba|siguen en pantalla como vivos)",
     ["--luego", "{D}/cae.sh@7"], lambda r: r["frescura"].update(refresco_s=3), SIEMPRE_VIVO,
     "la ruta cae y la pantalla deja lo viejo como vivo"),
    ("no_disponible", "PASA", "", [],
     _no_disponible,
     None, "la ruta contesta que no esta disponible, con su motivo"),
    ("no_disponible_callado", "CONDENA", "E4 la ruta no dio dato .no disponible. y la vista NO lo dice arriba", [],
     _no_disponible,
     SIEMPRE_VIVO, "«no disponible» y la pantalla calla"),
    ("generador_parado", "PASA", "", [], lambda r: r["generador"]["ultimo_latido"].update(registered_at=_mas(r, -2000)), None,
     "el generador lleva mas de dos velas sin latir y la ruta contesta: la pantalla lo dice arriba"),
    ("generador_parado_callado", "CONDENA", "E4 el generador no late .* (NO lo dice arriba|siguen en pantalla como vivos)", [],
     lambda r: r["generador"]["ultimo_latido"].update(registered_at=_mas(r, -2000)), SIEMPRE_VIVO,
     "el generador parado y lo viejo sigue como vivo"),
    ("se_para_en_pantalla", "PASA", "", ["--luego", "@12"],
     lambda r: r["generador"]["ultimo_latido"].update(registered_at=_mas(r, -1793)), None,
     "el generador cruza su tope con la vista abierta: lo dice sin recargar"),
    ("reloj_parado", "CONDENA", "(E3 .* NO avanzaron|E4 el generador no late .* NO lo dice arriba)", ["--luego", "@12"],
     lambda r: r["generador"]["ultimo_latido"].update(registered_at=_mas(r, -1793)), RELOJ_PARADO,
     "una edad pintada UNA vez: el reloj de la pantalla no corre (A78)"),
    ("pasada_a_medias", "PASA", "", [], lambda r: _a_medias(r), None,
     "hay planes de una vela que aun no ha latido: la ruta lo dice y la pantalla lo pinta sobre lo vivo"),
    ("pasada_a_medias_callada", "CONDENA", "E8 la respuesta trae 1 hoja.* generador.pasada_en_curso", [],
     lambda r: _a_medias(r),
     _tras_pintar("    document.querySelectorAll('.ent-en-curso').forEach((n) => n.parentNode.removeChild(n));"),
     "la ruta dice que la pasada esta a medias y la pantalla se lo calla"),
    ("versiones_confundidas", "CONDENA", "E2 el plan .* dos versiones confundidas", [], None,
     _tras_pintar("    document.querySelectorAll('#ent-vivo [data-celda]').forEach((c) => {\n"
                  "      const b = c.querySelectorAll('[data-bloque-version]');\n"
                  "      if (b.length > 1) b[1].querySelectorAll('[data-plan]').forEach((f) => b[0].appendChild(f));\n    });"),
     "los planes del ancla pintados dentro del bloque de la activa, sobre la misma zona"),
    # ---- la fidelidad: lo pintado es lo servido, a la precision con que se pinta (A76, A77)
    ("mas_decimales_servidos", "PASA", "", [],
     lambda r: (_vivos(r)[0].update(r_neto=1.6543, p_equilibrio=0.37669), _vivos(r)[0]["stop"].update(distancia_bps=102.5357)), None,
     "la ruta sirve MAS decimales de los que la pantalla pinta: una pagina fiel pasa (A77)"),
    ("precio_de_miles", "PASA", "", [],
     lambda r: (_vigilando(r)[0]["zona"].update(low=63385.0, high=64120.0), r["precio"].update(valor=63000.0)), None,
     "un precio de cinco cifras SIN decimales: la pantalla escribe «63.385» y son sesenta y tres mil"),
    # ---- un coste que no es cero no se pinta como cero (remate R2)
    ("coste_pequeno", "PASA", "", [], lambda r: _coste(r, 0.3, 0.0003), None,
     "T1 a 932,1 bps y una pata que cuesta 0,30 bps, 0,0003 del objetivo: la pantalla lo dice («x0,0003 del objetivo»)"),
    ("coste_pequeno_en_cero", "CONDENA", "E2 .*costes\\[1\\]\\.x_objetivo: se pinta como CERO", [],
     lambda r: _coste(r, 0.3, 0.0003), DOS_DECIMALES,
     "la misma respuesta con el formato de antes, a dos decimales: «x0,00 del objetivo» para un coste que no es cero"),
    ("coste_del_operador_en_cero", "CONDENA", "E2 .*costes\\[1\\]\\.x_objetivo: se pinta como CERO .* sirve 0.002", [],
     None, DOS_DECIMALES,
     "el escenario base TAL CUAL (2,00 bps a 932,1 bps: 0,002) con el formato de antes: es la captura que señalo el operador"),
    ("coste_cero", "PASA", "", [], lambda r: _coste(r, 0.0, 0.0), None,
     "el gemelo: una pata que de verdad cuesta cero se pinta como cero («0,00 bps», «x0,00 del objetivo»)"),
    # ---- la tabla de recuentos dice que cuenta (remate R3)
    ("recuentos_callados", "CONDENA", "E2 la tabla de recuentos se pinta sin decir que cuenta", [], None,
     _tras_pintar("    const n = document.querySelector('#ent-marco [data-k=\"marco.cuentas_que_cuentan\"]'); n.parentNode.removeChild(n);"),
     "la pantalla pinta la tabla de recuentos y se calla la frase que dice que cuenta cada columna"),
    ("recuentos_sin_frase_servida", "CONDENA", "E2 la tabla de recuentos se pinta sin decir que cuenta", [],
     lambda r: r["marco"].pop("cuentas_que_cuentan"), None,
     "la ruta deja de servir la frase y la tabla se sigue pintando: nadie dice que cuenta"),
    ("recuentos_con_la_cabecera_de_antes", "CONDENA", "E2 marco.cuentas_rotulos.VIGILANDO: pinta 'VIGILANDO'", [], None,
     _tras_pintar("    document.querySelector('#ent-marco [data-k=\"marco.cuentas_rotulos.VIGILANDO\"]').textContent = 'VIGILANDO';"),
     "la columna vuelve a llamarse VIGILANDO, como el estado de un plan vivo"),
    ("cifra_cambiada", "CONDENA", "E2 .*stop.precio: pinta .* y la respuesta sirve", [], None,
     _tras_pintar("    const n = document.querySelector('#ent-vivo [data-k$=\".stop.precio\"]'); n.textContent = '1,23';"),
     "el stop pintado no es el servido"),
    ("clave_inventada", "CONDENA", "E2 pinta plan.confianza .* que la respuesta no sirve", [], None,
     _tras_pintar("    const f = document.querySelector('#ent-vivo [data-plan]'); const s = document.createElement('span');\n"
                  "    s.setAttribute('data-k', 'plan.confianza'); s.textContent = 'media'; f.appendChild(s);"),
     "la pantalla pinta una clave que la ruta no sirve"),
    ("plan_inventado", "CONDENA", "E2 se pinta el plan 424242 .* y la respuesta no lo sirve", [], None,
     _tras_pintar("    const f = document.querySelector('#ent-vivo [data-plan]'); const c = f.cloneNode(true);\n"
                  "    c.setAttribute('data-plan', '424242'); f.parentNode.appendChild(c);"),
     "un plan pintado que nadie sirvio"),
    ("plan_escondido", "CONDENA", "E2 el plan .* esta servido en .vivo. y no se ve", [], None,
     _tras_pintar("    const f = document.querySelector('#ent-vivo [data-tipo=\"vigilando\"]'); f.parentNode.removeChild(f);"),
     "un plan servido que la pantalla no ensena"),
    ("disparado_a_medias", "CONDENA", "E2 un DISPARADO sin su plan entero: .*costes", [], None,
     _tras_pintar("    document.querySelectorAll('#ent-vivo [data-k*=\".costes[\"]').forEach((n) => { n.parentNode.removeChild(n); });"),
     "un DISPARADO vivo sin el coste de sus patas"),
    ("dos_respuestas", "PASA", "", ["--luego", "{D}/cambia.sh@8"], lambda r: r["frescura"].update(refresco_s=3), None,
     "el refresco trae OTRA respuesta (otra palabra, otro precio): cada pantalla se compara con la SUYA (A76)"),
    ("no_repinta", "CONDENA", "E2 .*: pinta .* y la respuesta sirve", ["--luego", "{D}/cambia.sh@8"],
     lambda r: r["frescura"].update(refresco_s=3), NO_REPINTA,
     "llega otra respuesta y la pantalla se queda con la vieja"),
    # ---- C2 · lo que la vista no puede decir, forma a forma, y sus gemelos permitidos
    ("fraccion", "CONDENA", "E5 fraccion o porcentaje", [], None, _escribe("3/7"), "«3/7» pintado en un plan"),
    ("porcentaje", "CONDENA", "E5 fraccion o porcentaje", [], None, _escribe("43 %"), "«43 %» pintado en un plan"),
    ("tasa", "CONDENA", "E5 palabra de tasa", [], None, _escribe("0.43 de acierto"), "«0.43 de acierto»"),
    ("tres_de_siete", "CONDENA", "E5 fraccion o porcentaje", [], None, _escribe("3 de 7"), "«3 de 7», la fraccion con palabras"),
    ("por_ciento", "CONDENA", "E5 fraccion o porcentaje", [], None, _escribe("43 por ciento"), "«43 por ciento»"),
    ("favorable", "CONDENA", "E5 palabra que promete", [], None, _escribe("favorable"), "«favorable»"),
    ("alta_probabilidad", "CONDENA", "E5 palabra", [], None, _escribe("alta probabilidad"), "«alta probabilidad»"),
    ("buena_entrada", "CONDENA", "E5 palabra que promete", [], None, _escribe("buena entrada"), "«buena entrada»"),
    ("porcentaje_servido", "CONDENA", "E5 fraccion o porcentaje en .*distancia.donde", [],
     lambda r: _vigilando(r)[0]["distancia"].update(donde="43 % de las veces"), None,
     "un «43 %» servido por la ruta en un campo que la pantalla pinta fielmente"),
    ("parecidos_permitidos", "PASA", "", [],
     lambda r: (_vivos(r)[0]["costes"][0].update(x_objetivo=0.43), _vigilando(r)[0]["distancia"].update(pct=0.43)), None,
     "las cifras PERMITIDAS que se les parecen: «x0,43 del objetivo» y «0,43 %» de distancia"),
    ("color_por_resultado", "CONDENA", "E6 un color puesto a mano", [], lambda r: _resueltos(r, ["objetivo", "stop", "objetivo"]),
     _tras_pintar(POR_RESULTADO + "    filas.forEach((f) => { f.style.color = res[f.dataset.plan] === 'objetivo' ? 'rgb(62, 207, 142)' : 'rgb(224, 90, 90)'; });"),
     "con n < 30, las filas en verde o en rojo segun su resultado (estilo en linea)"),
    ("color_por_clase", "CONDENA", "E6 el plan .* lleva clases que no son las de su estado", [],
     lambda r: _resueltos(r, ["objetivo", "stop", "objetivo"]),
     _tras_pintar(POR_RESULTADO + "    filas.forEach((f) => f.classList.add(res[f.dataset.plan] === 'objetivo' ? 'req-cumple' : 'req-falla'));"),
     "el mismo color, puesto con una clase que ya existe en la vista"),
    ("orden_por_resultado", "CONDENA", "E6 el plan .* el orden es por estado y por hora", [],
     lambda r: _resueltos(r, ["stop", "objetivo", "objetivo"]),
     _tras_pintar(POR_RESULTADO + "    filas.filter((f) => res[f.dataset.plan] === 'objetivo').reverse().forEach((f) => f.parentNode.insertBefore(f, filas[0]));"),
     "con n < 30, los que tocaron objetivo primero"),
    ("orden_por_resultado_empate", "CONDENA", "E6 el plan .* el orden es por estado y por hora", [],
     lambda r: _resueltos(r, ["stop", "objetivo", "objetivo"], misma_hora=True),
     _tras_pintar(POR_RESULTADO + "    filas.filter((f) => res[f.dataset.plan] === 'objetivo').reverse().forEach((f) => f.parentNode.insertBefore(f, filas[0]));"),
     "lo mismo con las tres a la MISMA hora: el empate no deja sitio al resultado"),
    ("empate_bien_ordenado", "PASA", "", [], lambda r: _resueltos(r, [None, None, None], misma_hora=True), None,
     "su gemelo: tres caducados a la misma hora, sin resultado: la vista real los ordena por registro"),
    # ---- C3 · las cinco palabras, cada una con su frase; y la frase de una servida para otra
    ("decide_long", "PASA", "", [], lambda r: _palabra(r, "LONG"), None, "DECIDE en LONG: un plan largo va de su lado, uno corto EN CONTRA"),
    ("decide_short", "PASA", "", [], lambda r: _palabra(r, "SHORT"), None, "DECIDE en SHORT"),
    ("decide_no_operar", "PASA", "", [], lambda r: _palabra(r, "NO OPERAR"), None, "NO OPERAR: «plan condicional: el sistema no sostiene un lado»"),
    ("decide_no_evaluable", "PASA", "", [], lambda r: _palabra(r, "NO EVALUABLE"), None, "NO EVALUABLE: ni respalda ni desaconseja"),
    ("decide_sin_respuesta", "PASA", "", [], lambda r: _palabra(r, None), None, "DECIDE no contesta y la ruta si"),
    ("decide_rancio", "PASA", "", ["--luego", "@12"], lambda r: _palabra(r, "LONG", 112.0), None,
     "la palabra cruza su tope de 120 s con la vista abierta: sale rancia, sin recargar"),
    ("rancio_callado", "CONDENA", "E7 .* la palabra pasa de su tope", ["--luego", "@12"],
     lambda r: _palabra(r, "LONG", 112.0), RELOJ_PARADO, "la palabra cruza su tope y la pantalla la sigue dando por buena"),
    ("frase_de_otra", "CONDENA", "E7 intradia: con NO OPERAR la frase es de OTRA palabra", [],
     lambda r: _cruza(r, "NO OPERAR", "LONG"), None, "la RESPUESTA trae NO OPERAR con la frase de LONG"),
    ("long_con_frase_de_no_operar", "CONDENA", "E7 intradia: con LONG la frase es de OTRA palabra", [],
     lambda r: _cruza(r, "LONG", "NO OPERAR"), None, "LONG con «plan condicional»"),
    ("no_evaluable_como_un_no", "CONDENA", "E7 intradia.*: con (DECIDE )?NO EVALUABLE", [],
     lambda r: _cruza(r, "NO EVALUABLE", "SHORT"), None,
     "NO EVALUABLE presentado como que el sistema desaconseja el plan (la frase y el «EN CONTRA» de SHORT)"),
    ("no_evaluable_en_rojo", "CONDENA", "E7 intradia: NO EVALUABLE pintado con el color de un lado", [],
     lambda r: _palabra(r, "NO EVALUABLE"),
     _tras_pintar("    document.querySelectorAll('.ent-palabra.sesgo-NOEVAL').forEach((n) => { n.className = 'ent-palabra sesgo-SHORT'; });"),
     "NO EVALUABLE pintado con el rojo de SHORT"),
    ("en_contra_callado", "CONDENA", "E7 intradia/largo: con DECIDE SHORT la celda dice", [], lambda r: _palabra(r, "SHORT"),
     _tras_pintar("    document.querySelectorAll('.ent-rel.rel-en_contra').forEach((n) => { n.textContent = 'mismo lado que DECIDE (SHORT)'; });"),
     "un plan largo con DECIDE en SHORT y la pantalla no dice que va en contra"),
    # ---- C4 de la campana 138 · la palabra GRANDE de INTRADIA, por la regla que la respuesta declara
    ("grande_oscila", "PASA", "", [], lambda r: _palabra(r, "NO OPERAR", patron="oscila"), None,
     "b · la serie oscila en cada evaluacion: la grande es NO OPERAR, con su frase de «no sostiene»"),
    ("lado_donde_no_lo_hay", "CONDENA", "E9 intradia: la palabra GRANDE servida", [],
     lambda r: _palabra(r, "NO OPERAR", patron="oscila", grande="LONG"), None,
     "b · LONG servido, y pintado con su frase, sobre una serie que oscila: la regla no da lado"),
    ("calla_lado_sostenido", "CONDENA", "E9 intradia: la palabra GRANDE servida", [],
     lambda r: _palabra(r, "LONG", grande="NO OPERAR"), None, "a · NO OPERAR servido sobre una serie LONG sostenida"),
    # (su gemelo fiel es decide_no_evaluable: LONG sostenido y la puerta del instante cerrada)
    ("lado_con_la_puerta_cerrada", "CONDENA", "E9 intradia: la palabra GRANDE servida", [],
     lambda r: _palabra(r, "NO EVALUABLE", grande="LONG"), None, "c y d · LONG con la puerta del instante cerrada"),
    ("colector_parado", "PASA", "", [], lambda r: _palabra(r, "NO EVALUABLE", patron="parado", instante="LONG"), None,
     "e · el colector dejo de escribir: la grande es NO EVALUABLE y su motivo lo dice"),
    ("colector_parado_con_lado", "CONDENA", "E9 intradia: la palabra GRANDE servida", [],
     lambda r: _palabra(r, "NO EVALUABLE", patron="parado", instante="LONG", grande="LONG"), None,
     "e · LONG con el colector parado: afirma lo que no ve"),
    ("instante_en_grande", "CONDENA", "E9 intradia: la palabra pintada .*INSTANTE", [],
     lambda r: _palabra(r, "LONG", instante="NO OPERAR"),
     _tras_pintar("    const x = document.querySelector('[data-decide=intradia] .ent-palabra');\n"
                  "    if (x && _ent) { x.textContent = _ent.datos.decide.perfiles.intradia.recalculo.instante;"
                  " x.dataset.palabra = x.textContent; }"),
     "f · la pantalla pinta la palabra del INSTANTE en el sitio de la grande"),
    ("edad_prestada", "CONDENA", "E2 decide.perfiles.intradia.edad_de_la_palabra: pinta", [], None,
     _tras_pintar("    const e = document.querySelector('[data-k=\"decide.perfiles.intradia.edad_de_la_palabra\"]');\n"
                  "    if (e && _ent) e.textContent = 'edad ' + _ent.datos.decide.edad_s + ' s';"),
     "g · la edad de la instantanea pintada en el sitio de la edad de la palabra"),
    ("rotulo_de_antes", "CONDENA", "E9 la pantalla rotula", [], None,
     _tras_pintar("    document.querySelectorAll('#ent-decide .venue').forEach((n) => {"
                  " n.firstChild.textContent = 'edad de la palabra: '; });"),
     "g · la edad del dato, rotulada otra vez «edad de la palabra» (lo de antes de la 138)"),
    # ---- C4 · quien pide que
    ("principal_pide_entradas", "CONDENA", "E8 la vista principal pide .* que solo es de ENTRADAS", ["--vista", "mesa"], None, "APP",
     "la vista PRINCIPAL pidiendo la ruta de entradas en su ola 2"),
    ("entradas_pide_parte", "CONDENA", "E8 la vista de entradas pide /api/scalp/signals, que no es de su papel", [], None,
     _tras_pintar("    if (sobre.ok) pedir('/api/scalp/signals', { symbol: simbolo(ESTADO.activo) });"),
     "la vista de entradas pidiendo una PARTE de la mesa que no pinta"),
    # ---- C5 · el peso y el ritmo
    ("ruta_entera", "CONDENA", "E8 .* pesa [0-9]+ B: pasa del presupuesto", [],
     lambda r: r.update(registro_entero=[{"foto": "x" * 3800} for _ in range(60)]), None,
     "la MISMA ruta, con el mismo nombre, trayendo en cada peticion el peso del registro entero"),
    ("ritmo_servido", "PASA", "", ["--luego", "@8"], lambda r: r["frescura"].update(refresco_s=3), None,
     "la ruta sirve una cadencia de 3 s y la vista la obedece"),
    ("fuera_de_ritmo", "CONDENA", "E8 la vista volvio a pedir a los .* y su cadencia servida", ["--luego", "@8"],
     lambda r: r["frescura"].update(refresco_s=3),
     "\n/* PLANTADO por K106-plantados.py */\nsetInterval(() => { if (ESTADO.vista === 'entradas' && _ent) olaEntradas(); }, 1000);\n",
     "una vista que vuelve a pedir cada segundo, diga lo que diga la cadencia servida"),
    # ---- campana 139 (E3) · el resultado de cada DISPARADO, pintado; lo acabado nunca VIVO; ninguna frecuencia
    ("acabado_servido_no_se_pinta_vivo", "PASA", "", [], _acaba_vivo, None,
     "un DISPARADO de lo vivo cuyo resultado servido dice que acabo: el arbol pinta su salida y no lo llama VIVO"),
    ("acabado_pintado_vivo", "CONDENA", "E11 el DISPARADO .* acabo .* y la pantalla lo pinta VIVO", [], _acaba_vivo,
     _tras_tic("    document.querySelectorAll('#ent-reciente [data-tipo=\"disparado\"] [data-chip]').forEach((c) => { c.textContent = _ent.datos.vivo.rotulos.disparado_vivo; });"),
     "el mismo con un reloj de pantalla que lo devuelve a VIVO por su cuenta atras: lo que pintaba la de antes de la E3"),
    ("chip_no_es_su_resultado", "CONDENA", "E11 el DISPARADO .* acabo y su estado dice", [],
     lambda r: _resueltos(r, ["stop"]),
     _tras_tic("    document.querySelectorAll('#ent-reciente [data-chip]').forEach((c) => { c.textContent = _ent.datos.vivo.rotulos.disparado_caducado; });"),
     "un DISPARADO que acabo en su stop, con el estado «caducado» en vez de su resultado servido"),
    ("rotulo_cambiado", "CONDENA", "E2 .*resultado.rotulo: pinta", [], lambda r: _resueltos(r, ["stop"]),
     _tras_pintar("    const n = document.querySelector('#ent-reciente [data-k$=\".resultado.rotulo\"]');\n    if (n) n.textContent = 'OBJETIVO (T1)';"),
     "el resultado de un DISPARADO pintado distinto del servido (OBJETIVO donde se sirve STOP)"),
    ("anterior_con_su_resultado", "PASA", "", [], _anterior, None,
     "un DISPARADO anterior a la ventana, en su fila corta con su resultado: lo reciente aunque tenga mas de 24 h"),
    ("anterior_pintado_vivo", "CONDENA", "E11 el DISPARADO 8000 acabo", [], _anterior,
     _tras_tic("    document.querySelectorAll('[data-anterior] [data-chip]').forEach((c) => { c.textContent = _ent.datos.vivo.rotulos.disparado_vivo; });"),
     "el anterior, acabado en su stop, con el estado VIVO"),
    ("frecuencia_de_resultados", "CONDENA", "E5 fraccion o porcentaje en el texto de la pantalla", [], None,
     _tras_pintar("    const s = document.createElement('p');\n    s.textContent = '1 de 2 tocaron T1';\n    document.getElementById('ent-papel').appendChild(s);"),
     "con n < 30, «1 de 2 tocaron T1» escrito junto a la cuenta de papel"),
    ("porcentaje_en_el_papel", "CONDENA", "E5 fraccion o porcentaje en papel", [],
     lambda r: r["papel"]["por_version"][0].update(meta="50 % de las operaciones llegaron a T1"), None,
     "un «50 %» de resultados SERVIDO en la cuenta de papel, que la pantalla pinta fielmente"),
]


def huella(dir_: Path) -> str:
    h = hashlib.sha256()
    for f in [dir_ / "respuesta.json", *sorted((dir_ / "sobre").rglob("*"))]:
        if f.is_file():
            h.update(f.name.encode() + b"\0" + f.read_bytes())
    return h.hexdigest()[:12]


def planta(nombre: str, dir_: Path) -> None:
    brazo = next((b for b in BRAZOS if b[0] == nombre), None)
    if brazo is None:
        raise SystemExit(f"plantados: no conozco el brazo {nombre!r}")
    _, _, _, _, respuesta, pantalla, _ = brazo
    bueno = json.loads((dir_ / "base.json").read_text(encoding="utf-8"))
    shutil.rmtree(dir_ / "sobre", ignore_errors=True)
    (dir_ / "sobre" / "mesa").mkdir(parents=True)
    (dir_ / "respuesta.json").write_text(json.dumps(bueno, ensure_ascii=False), encoding="utf-8")
    # lo que la sonda ejecuta a media observacion para tirar la ruta (--luego {D}/cae.sh@7)
    (dir_ / "cae.sh").write_text(f"#!/bin/sh\nrm -f '{dir_}/respuesta.json'\n", encoding="utf-8")
    (dir_ / "cae.sh").chmod(0o755)
    (dir_ / "cambia.sh").write_text(f"#!/bin/sh\ncp '{dir_}/segunda.json' '{dir_}/respuesta.json'\n", encoding="utf-8")
    (dir_ / "cambia.sh").chmod(0o755)
    (dir_ / "segunda.json").unlink(missing_ok=True)
    antes = huella(dir_)
    if respuesta == "CAIDA":
        (dir_ / "respuesta.json").unlink()
    elif respuesta is not None:
        r = copy.deepcopy(bueno)
        respuesta(r)
        (dir_ / "respuesta.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    if nombre in SEGUNDA:
        otra = copy.deepcopy(bueno)
        SEGUNDA[nombre](otra)
        (dir_ / "segunda.json").write_text(json.dumps(otra, ensure_ascii=False), encoding="utf-8")
    if pantalla == "APP":
        fuente = (REPO / "static/mesa/mesa-app.js").read_text(encoding="utf-8")
        ancla = "  const claves = Object.keys(trabajos);"
        assert fuente.count(ancla) == 1, "plantados: no encuentro donde plantar en mesa-app.js"
        ruta = "/api" + "/mesa/entradas"
        (dir_ / "sobre/mesa/mesa-app.js").write_text(
            fuente.replace(ancla, f"  trabajos.plantado = pedir('{ruta}', {{ symbol: s }});\n" + ancla), encoding="utf-8")
    elif pantalla is not None:
        fuente = (REPO / "static/mesa/mesa-entradas.js").read_text(encoding="utf-8")
        (dir_ / "sobre/mesa/mesa-entradas.js").write_text(fuente + pantalla, encoding="utf-8")
    print(f"{nombre}: huella {antes} -> {huella(dir_)}")


def copia(arbol: str, dsn: str, esquema: str, reloj: str, simbolo: str, destino: str) -> None:
    """/api/mesa/entradas del ARBOL dado sobre la copia del registro (K107-resultado.py carga) a la hora `reloj`,
    con el DECIDE fingido fiel de aqui. Con `python -S`: asi `import app` es el del arbol (main o la rama)."""
    import asyncio

    sys.path[:0] = [arbol]
    sys.path += [str(d) for d in sorted((Path(sys.executable).parents[1] / "lib").glob("python3*/site-packages"))]
    import app
    assert app.__file__.startswith(arbol.rstrip("/") + "/"), f"plantados: app viene de {app.__file__}"
    import asyncpg

    from app.entradas import vista as V

    async def una() -> None:
        c = await asyncpg.connect(dsn)
        await c.execute(f"SET search_path TO {esquema}, pg_catalog, public")
        await c.execute("SET TIME ZONE 'UTC'")
        desfase = await c.fetchval("SELECT ($1::timestamptz - pg_catalog.clock_timestamp())::text",
                                   datetime.fromisoformat(reloj.replace("Z", "+00:00")))
        await c.execute("SELECT set_config('reloj.desfase', $1, false)", desfase)

        async def palabra(_c, _s, *, frame):
            return _decide("LONG")

        r = await V.construir(c, symbol=simbolo, activo=simbolo.split("USDT")[0], palabra_de_decide=palabra)
        Path(destino).write_text(json.dumps(r, ensure_ascii=False, default=str), encoding="utf-8")
        await c.close()

    asyncio.run(una())
    print(f"copia: {arbol} sirve {Path(destino).stat().st_size} B a las {reloj}")


def main() -> None:
    orden = sys.argv[1]
    if orden == "base":
        asyncio.run(base(sys.argv[2], Path(sys.argv[3])))
    elif orden == "lista":
        for nombre, veredicto, patron, sonda, _, _, que in BRAZOS:
            print("\t".join([nombre, veredicto, patron or "-", " ".join(sonda) or "-", que]))
    elif orden == "planta":
        planta(sys.argv[2], Path(sys.argv[3]))
    elif orden == "resueltos":  # <dir> <orden separado por comas>: para la no-interferencia
        dir_ = Path(sys.argv[2])
        r = json.loads((dir_ / "base.json").read_text(encoding="utf-8"))
        _resueltos(r, sys.argv[3].split(","))
        shutil.rmtree(dir_ / "sobre", ignore_errors=True)
        (dir_ / "sobre" / "mesa").mkdir(parents=True)
        (dir_ / "respuesta.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        print(f"resueltos {sys.argv[3]}: huella {huella(dir_)}")
    elif orden == "copia":  # <arbol> <dsn> <esquema> <reloj> <simbolo> <destino>: con python -S
        copia(*sys.argv[2:8])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
