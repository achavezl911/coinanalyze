#!/usr/bin/env python3
"""Siembra de K105-control: el escenario correcto y cada plantado de C5, en una base DESECHABLE.

  escenario <dsn> <release>   escribe un release de control (v1 con tope de retraso 900 s para
                              que la vela T actual entre, y un calendario que cubre 10 dias),
                              registra su reglamento y codigo, siembra BTC y ETH en la vela T y la
                              evalua con el generador real: un DISPARADO (BTC) y una SOMBRA «solo
                              perpetuo» (ETH), con sus VIGILANDO.
  planta <caso> <dsn>         una fila mala sobre esa base: sin_stop, posterior, sin_spot,
                              dos_vivos, evento_ajeno. Imprime la huella de la foto antes/despues.
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


def _release(T, ruta: Path) -> dict:
    doc = R.cargar()
    v1 = doc["versiones"][0]
    v1["bloques"]["comun"]["parametros"]["tope_retraso_s"]["valor"] = 900
    v1["huellas"] = {n: R.huella_bloque(v1["bloques"][n]) for n in R.BLOQUES}
    rev = B.revision(cubre_hasta=T + timedelta(days=10))
    rev.update({"revision": "cal-control", "vigente_desde": M.iso(T - timedelta(days=1))})
    rev["huella"] = R.huella_revision(rev)
    doc["calendario"]["revisiones"] = [rev]
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
        doc = _release(T, Path(release))
        reg = await G.registrar_reglamento(conn, doc, C.registradas(), M.CODIGO_VERSION, C.contenido())
        assert reg["ok"], reg
        await B.sembrar(conn, T, B.insumos(T), "BTCUSDT_PERP.A", "BTC")
        await B.sembrar(conn, T, B.insumos(T, spot_vela=-1e6), "ETHUSDT_PERP.A", "ETH")
        salida = await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo=C.huella_codigo(), esperar=False)
        estados = sorted(r["estado"] for v in salida for r in v["registradas"])
        # un latido de verdad: sin filas, un DELETE no dispara nada y el control no mediria (A35)
        await G.latir(conn, vela_cierre=T, estado="ok", duracion_s=0.0,
                      detalle={"velas": salida}, error=None)
        print(f"escenario T={M.iso(T)} registradas={estados} + 1 latido")
    finally:
        await conn.close()


async def planta(caso: str, dsn: str) -> None:
    conn = await asyncpg.connect(dsn, server_settings={"timezone": "UTC"})
    try:
        fila = await conn.fetchrow(
            "SELECT * , foto::text AS foto_texto FROM entrada_registro WHERE estado = 'DISPARADO' "
            "AND symbol = 'BTCUSDT_PERP.A' ORDER BY registro_id LIMIT 1")
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
        else:
            raise SystemExit(f"caso desconocido {caso}")
        t["foto"] = foto
        t["huella_foto"] = M.huella_foto(foto)
        r = await G.insertar(conn, t, "c" * 64)
        cambio = (f"clave {fila['clave']} -> {t['clave']} (misma foto)" if caso == "dos_vivos"
                  else f"huella de la foto {antes[:12]} -> {t['huella_foto'][:12]}")
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
