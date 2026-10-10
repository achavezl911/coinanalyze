#!/usr/bin/env python3
"""Siembra de K105-control: el escenario correcto y cada plantado de C5, en una base DESECHABLE.

  escenario <dsn> <release>   escribe un release de control (v1 y v2 del arbol, cada una con SU
                              tope de retraso -los dos caben en la vela T actual; en una vela mas
                              vieja solo el de v2- y un calendario que cubre), registra su
                              reglamento y codigo, siembra BTC y ETH en la vela T y la evalua con
                              el generador real: en CADA version un DISPARADO (BTC) y una SOMBRA
                              «solo perpetuo» (ETH), con sus VIGILANDO.
  planta <caso> <dsn>         una fila mala sobre esa base: sin_stop, posterior, sin_spot,
                              dos_vivos, evento_ajeno; y las de DOS VERSIONES (campana 136):
                              tope_gemelo (un DISPARADO de v2 por encima del tope de v1 y dentro
                              del suyo: es CORRECTO), tope_ajeno (uno de v1 con ese mismo retraso,
                              que la base acepta porque trae el tope de v2) y huella_ajena (una
                              fila de v1 con la huella de comun de v2).
                              Imprime la huella de la foto antes/despues.
  release_evento <release>    mete en el calendario del release un evento ANTERIOR a su revision.

Nunca toca una base que no se llame k105_ctl_*.
"""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import sys
import uuid
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

import asyncpg  # noqa: E402
import entradas_banco as B  # noqa: E402

from app.entradas import codigo as C  # noqa: E402
from app.entradas import motor as M  # noqa: E402
from app.entradas import registro as G  # noqa: E402
from app.entradas import reglamento as R  # noqa: E402
from app.entradas import servicio as S  # noqa: E402

SIMBOLOS = (("BTCUSDT_PERP.A", "BTC"), ("ETHUSDT_PERP.A", "ETH"), ("SOLUSDT_PERP.A", "SOL"))


def _desechable(dsn: str) -> None:
    nombre = dsn.split("?")[0].rsplit("/", 1)[-1]
    if not nombre.startswith("k105_ctl_"):
        raise SystemExit(f"siembra: {nombre} no es una base desechable k105_ctl_*")


# Los topes de control, en segundos sobre lo que lleva cerrada la vela T al sembrar. En el de v1 cabe
# la vela T y NO la anterior (15 min mas vieja); en el de v2 caben las dos. Asi una fila de la vela
# anterior queda por encima del tope de v1 y dentro del de v2: el sitio donde juzgar con el tope de
# OTRA version da el veredicto contrario.
TOPE_SOBRE_LO_PASADO = {"v1": 870.0, "v2": 1500.0}


def _release(T, pasado_s: float, ruta: Path) -> dict:
    doc = B.doc_de_prueba(T, "v1", "v2",
                          tope_s={v: round(pasado_s + s, 3) for v, s in TOPE_SOBRE_LO_PASADO.items()})
    destino = ruta / "config" / "entradas"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "reglamento.json").write_text(R.formatea(doc) + "\n", encoding="utf-8")
    shutil.copy(C.REGISTRO, destino / "codigo.json")
    assert R.validar(doc) == [], R.validar(doc)
    return doc


async def escenario(dsn: str, release: str) -> None:
    conn = await asyncpg.connect(dsn, server_settings={"timezone": "UTC"})
    try:
        for symbol, base in SIMBOLOS:
            await conn.execute("INSERT INTO market_assets(base_asset) VALUES($1) ON CONFLICT DO NOTHING", base)
            await conn.execute("INSERT INTO symbols(symbol, base_asset) VALUES($1, $2) ON CONFLICT DO NOTHING",
                               symbol, base)
        T = await conn.fetchval("SELECT date_bin('15 minutes', clock_timestamp(), TIMESTAMPTZ '1970-01-01 00:00:00+00')")
        pasado = (await conn.fetchval("SELECT clock_timestamp()") - T).total_seconds()
        doc = _release(T, pasado, Path(release))
        reg = await G.registrar_reglamento(conn, doc, C.registradas(), M.CODIGO_VERSION, C.contenido())
        assert reg["ok"], reg
        await B.sembrar(conn, T, B.insumos(T), "BTCUSDT_PERP.A", "BTC")
        await B.sembrar(conn, T, B.insumos(T, spot_vela=-1e6), "ETHUSDT_PERP.A", "ETH")
        salida = await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo=C.huella_codigo(), esperar=False)
        estados = sorted(r["estado"] for v in salida for r in v["registradas"])
        # un latido de verdad: sin filas, un DELETE no dispara nada y el control no mediria (A35)
        await G.latir(conn, vela_cierre=T, estado="ok", duracion_s=0.0,
                      detalle={"velas": salida}, error=None)
        topes = {v["version"]: R.valores(v["bloques"]["comun"])["tope_retraso_s"] for v in doc["versiones"]}
        print(f"escenario T={M.iso(T)} (cerrada hace {pasado:.0f} s) topes de control={topes} "
              f"registradas={estados} + 1 latido")
    finally:
        await conn.close()


async def planta(caso: str, dsn: str) -> None:
    conn = await asyncpg.connect(dsn, server_settings={"timezone": "UTC"})
    try:
        de_v2 = caso == "tope_gemelo"
        base = ("SELECT * , foto::text AS foto_texto FROM entrada_registro WHERE estado = 'DISPARADO' "
                "AND symbol = 'BTCUSDT_PERP.A' AND version = $1 ORDER BY registro_id LIMIT 1")
        fila = await conn.fetchrow(base, "v2" if de_v2 else "v1")
        otra = await conn.fetchrow(base, "v1" if de_v2 else "v2")
        foto = json.loads(fila["foto_texto"])
        antes = M.huella_foto(foto)
        t = {
            "version": fila["version"], "familia": fila["familia"], "perfil": fila["perfil"],
            "lado": fila["lado"], "symbol": "SOLUSDT_PERP.A", "clave": "zona:1.0:2.0",
            "episodio": uuid.uuid4().hex + uuid.uuid4().hex, "estado": "DISPARADO",
            "motivo": None, "vela_cierre": fila["vela_cierre"],
            "inicio_episodio": fila["inicio_episodio"], "caduca_en": fila["caduca_en"],
            "tope_retraso_s": float(fila["tope_retraso_s"]), "codigo_version": fila["codigo_version"],
            "huellas": foto["huellas"],
        }
        foto = copy.deepcopy(foto)
        if caso == "sin_stop":
            foto["plan"]["stop"]["precio"] = None
        elif caso == "posterior":
            ahora = await conn.fetchval("SELECT clock_timestamp()")
            foto["libro_bybit"]["ts"] = M.iso(ahora + timedelta(hours=1))
        elif caso == "sin_spot":
            foto["flujos"]["spot"]["vela"]["completo"] = False
        elif caso == "dos_vivos":
            t.update({"symbol": "BTCUSDT_PERP.A", "clave": "zona:94.8:95.2"})
        elif caso == "evento_ajeno":
            t.update({"estado": "SOMBRA", "motivo": "calendario", "caduca_en": None})
            foto["decision"]["etiquetas"] = ["evento"]
            foto["decision"]["estado"] = "SOMBRA"
            foto["filtros"]["calendario"] = {"estado": "falla", "valor": ["fantasma"], "umbral": 3,
                                             "motivo": "plantado"}
            foto["calendario"]["revision"] = "cal-fantasma"
            foto["huellas"]["calendario_datos"] = "f" * 64
            t["huellas"] = foto["huellas"]
        elif caso in ("tope_gemelo", "tope_ajeno"):
            # una fila de la vela ANTERIOR: su retraso pasa del tope de v1 y cabe en el de v2
            anterior = fila["vela_cierre"] - timedelta(minutes=15)
            t.update({"vela_cierre": anterior, "inicio_episodio": anterior - timedelta(minutes=15),
                      "clave": "zona:1.0:2.0" if de_v2 else "zona:3.0:4.0"})
            if caso == "tope_ajeno":  # de v1, pero con el tope de v2: la base la deja pasar
                t["tope_retraso_s"] = float(otra["tope_retraso_s"])
        elif caso == "huella_ajena":  # dice ser de v1 y lleva la regla comun de v2
            t.update({"clave": "zona:5.0:6.0",
                      "huellas": {**foto["huellas"], "comun": otra["huella_comun"]}})
        else:
            raise SystemExit(f"caso desconocido {caso}")
        t["foto"] = foto
        t["huella_foto"] = M.huella_foto(foto)
        r = await G.insertar(conn, t, "c" * 64)
        if caso == "dos_vivos":
            cambio = f"clave {fila['clave']} -> {t['clave']} (misma foto)"
        elif caso in ("tope_gemelo", "tope_ajeno"):
            cambio = (f"{t['version']} · retraso {r.get('retraso_s', 0):.0f} s · tope de la fila "
                      f"{float(fila['tope_retraso_s']):g} -> {t['tope_retraso_s']:g} · topes de control v1 "
                      f"{float((otra if de_v2 else fila)['tope_retraso_s']):g}, v2 "
                      f"{float((fila if de_v2 else otra)['tope_retraso_s']):g} (misma foto {antes[:12]})")
        elif caso == "huella_ajena":
            cambio = (f"{t['version']} · huella_comun {fila['huella_comun'][:12]} -> "
                      f"{t['huellas']['comun'][:12]} (misma foto {antes[:12]})")
        else:
            cambio = f"huella de la foto {antes[:12]} -> {t['huella_foto'][:12]}"
        print(f"plantado {caso}: {cambio} registrado={r['registrado']} estado={r.get('estado')}")
    finally:
        await conn.close()


async def solo_reglamento(dsn: str, release: str) -> None:
    """Una base con el reglamento del release registrado y NINGUNA fila de registro."""
    conn = await asyncpg.connect(dsn, server_settings={"timezone": "UTC"})
    try:
        doc = R.cargar(Path(release) / "config" / "entradas" / "reglamento.json")
        reg = await G.registrar_reglamento(conn, doc, C.registradas(), M.CODIGO_VERSION, C.contenido())
        assert reg["ok"], reg
        print(f"solo reglamento: {reg['filas']} filas registradas")
    finally:
        await conn.close()


def release_evento(release: str) -> None:
    ruta = Path(release) / "config" / "entradas" / "reglamento.json"
    antes = R.huella(json.loads(ruta.read_text(encoding="utf-8")))
    doc = json.loads(ruta.read_text(encoding="utf-8"))
    rev = doc["calendario"]["revisiones"][-1]
    desde = R.instante(rev["vigente_desde"])
    rev["eventos"].append({"clave": "pce-rellenado-hacia-atras", "titulo": "PCE",
                           "hora_utc": M.iso(desde - timedelta(hours=6)), "importancia": 3,
                           "fuente": "plantado"})
    rev["huella"] = R.huella_revision(rev)
    ruta.write_text(R.formatea(doc) + "\n", encoding="utf-8")
    print(f"plantado release_evento: huella del reglamento {antes[:12]} -> {R.huella(doc)[:12]}")


def main() -> None:
    orden = sys.argv[1]
    if orden == "escenario":
        _desechable(sys.argv[2])
        asyncio.run(escenario(sys.argv[2], sys.argv[3]))
    elif orden == "planta":
        _desechable(sys.argv[3])
        asyncio.run(planta(sys.argv[2], sys.argv[3]))
    elif orden == "release_evento":
        release_evento(sys.argv[2])
    elif orden == "reglamento":
        _desechable(sys.argv[2])
        asyncio.run(solo_reglamento(sys.argv[2], sys.argv[3]))
    else:
        raise SystemExit(f"orden desconocida {orden}")


if __name__ == "__main__":
    main()
