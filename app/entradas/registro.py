"""El REGISTRO de las entradas en la base (campana 135, E1): lo UNICO del generador que escribe.

Tres tablas append-only (sql/schema.sql, bloque de la campana 135):
  entrada_reglamento  se escribe ANTES de emitir nada: la huella de cada (etiqueta, bloque) del
                      reglamento y de cada version del codigo. Si la base ya tiene una etiqueta
                      con OTRA huella, o una registrada que el fichero ya no trae, no se emite
                      ningun candidato y el motivo queda en el latido.
  entrada_registro    las transiciones del motor. Un DISPARADO que la base rechaza por tardio
                      (EN001) se registra como SOMBRA «tardio» con la MISMA foto: ninguna
                      evaluacion tardia emite DISPARADO. Dos vivos en una clave (EN002) se apuntan
                      como rechazo y no se reintentan.
  entrada_latido      cada pasada, con su estado y su fallo.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import asyncpg

from app.entradas import motor as M
from app.entradas import reglamento as R

TARDIO = "EN001"
DOS_VIVOS = "EN002"

_INSERTA_REGISTRO = """
INSERT INTO entrada_registro (
    version, familia, perfil, lado, symbol, clave, episodio, estado, motivo, vela_cierre,
    inicio_episodio, caduca_en, tope_retraso_s, huella_familia, huella_comun, huella_calendario,
    huella_calendario_datos, huella_lectura, huella_papel, codigo_version, huella_codigo,
    huella_foto, foto
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
    $21, $22, $23::json
)
RETURNING registro_id, registered_at, retraso_s
"""


def filas_esperadas(doc: dict[str, Any], codigo_registrado: dict[str, str],
                    codigo_version: str, codigo_contenido: dict[str, Any]) -> list[dict[str, Any]]:
    """Lo que entrada_reglamento tiene que guardar: cada bloque de cada version, cada revision
    del calendario y cada version del codigo (la actual con su contenido; las viejas por huella)."""
    filas = R.registros_esperados(doc)
    for etiqueta, huella in codigo_registrado.items():
        contenido = codigo_contenido if etiqueta == codigo_version else {"huella_registrada": huella}
        filas.append({"etiqueta": etiqueta, "bloque": "codigo", "huella": huella,
                      "contenido": contenido})
    return filas


async def registrar_reglamento(conn: asyncpg.Connection, doc: dict[str, Any],
                               codigo_registrado: dict[str, str], codigo_version: str,
                               codigo_contenido: dict[str, Any]) -> dict[str, Any]:
    """Registra por huella ANTES de emitir. ok=False -> ningun candidato, con el motivo."""
    calculada = R.huella(codigo_contenido)
    if codigo_registrado.get(codigo_version) != calculada:
        return {
            "ok": False,
            "motivo": f"el codigo {codigo_version} tiene huella {calculada} y config/entradas/"
            f"codigo.json registra {codigo_registrado.get(codigo_version)!r}: subir la version",
            "conflictos": [],
            "huerfanas": [],
        }
    filas = filas_esperadas(doc, codigo_registrado, codigo_version, codigo_contenido)
    async with conn.transaction():
        for fila in filas:
            contenido = fila["contenido"]
            # La fila de un codigo viejo no recalcula su contenido: solo afirma su huella.
            await conn.execute(
                "INSERT INTO entrada_reglamento (etiqueta, bloque, huella, contenido) "
                "VALUES ($1, $2, $3, $4::json) ON CONFLICT (etiqueta, bloque) DO NOTHING",
                fila["etiqueta"],
                fila["bloque"],
                fila["huella"],
                R.canonico(contenido),
            )
    en_base = {
        (r["etiqueta"], r["bloque"]): r["huella"]
        for r in await conn.fetch("SELECT etiqueta, bloque, huella FROM entrada_reglamento")
    }
    esperadas = {(f["etiqueta"], f["bloque"]): f["huella"] for f in filas}
    conflictos = [
        {"etiqueta": e, "bloque": b, "fichero": h, "base": en_base.get((e, b))}
        for (e, b), h in esperadas.items()
        if en_base.get((e, b)) != h
    ]
    huerfanas = [{"etiqueta": e, "bloque": b} for (e, b) in en_base if (e, b) not in esperadas]
    motivo = None
    if conflictos:
        motivo = "una etiqueta ya registrada con OTRA huella: una etiqueta no abarca dos reglas"
    elif huerfanas:
        motivo = "la base tiene registrado algo que el fichero ya no trae: nada registrado se borra"
    return {"ok": not conflictos and not huerfanas, "motivo": motivo, "conflictos": conflictos,
            "huerfanas": huerfanas, "filas": len(filas)}


def ventana_previos(versiones: list[dict[str, Any]], perfil: str) -> timedelta:
    """Cuanto registro hace falta mirar hacia atras para conocer el estado de cada clave."""
    minutos = 0
    for v in versiones:
        pc = R.valores(v["bloques"]["comun"])
        vela = pc["perfiles"][perfil]["vela_min"]
        minutos = max(
            minutos,
            pc["vigilando_max_min"][perfil] + 2 * vela,
            pc["caducidad_min"][perfil] + 2 * vela,
            pc["separacion_ventana_velas"][perfil] * vela + 2 * vela,
        )
    return timedelta(minutes=minutos)


async def cargar_previos(conn: asyncpg.Connection, *, symbol: str, perfil: str,
                         versiones: list[str], desde: datetime, T: datetime) -> list[dict[str, Any]]:
    filas = await conn.fetch(
        """
        SELECT registro_id, version, familia, perfil, lado, symbol, clave, episodio, estado,
               vela_cierre, inicio_episodio, caduca_en, foto::text AS foto
        FROM entrada_registro
        WHERE symbol = $1 AND perfil = $2 AND version = ANY($3::text[])
          AND vela_cierre >= $4 AND vela_cierre < $5
        ORDER BY vela_cierre, registro_id
        """,
        symbol,
        perfil,
        versiones,
        desde,
        T,
    )
    return [
        {
            "orden": f["registro_id"],
            "version": f["version"],
            "familia": f["familia"],
            "perfil": f["perfil"],
            "lado": f["lado"],
            "symbol": f["symbol"],
            "clave": f["clave"],
            "episodio": f["episodio"],
            "estado": f["estado"],
            "vela_cierre": f["vela_cierre"],
            "inicio_episodio": f["inicio_episodio"],
            "caduca_en": f["caduca_en"],
            "foto": json.loads(f["foto"]),
        }
        for f in filas
    ]


def _argumentos(t: dict[str, Any], huella_codigo: str) -> tuple:
    h = t["huellas"]
    return (
        t["version"], t["familia"], t["perfil"], t["lado"], t["symbol"], t["clave"],
        t["episodio"], t["estado"], t["motivo"], t["vela_cierre"], t["inicio_episodio"],
        t["caduca_en"], t["tope_retraso_s"], h["familia"], h["comun"], h["calendario"],
        h["calendario_datos"], h["lectura"], h["papel"], t["codigo_version"], huella_codigo,
        t["huella_foto"], M.foto_canonica(t["foto"]),
    )


def como_sombra_tardia(t: dict[str, Any]) -> dict[str, Any]:
    """El mismo plan, la misma foto: solo cambia el estado. La foto no sabe la hora de registro."""
    return {**t, "estado": "SOMBRA", "motivo": "tardio", "caduca_en": None}


async def insertar(conn: asyncpg.Connection, t: dict[str, Any], huella_codigo: str) -> dict[str, Any]:
    """Inserta una transicion. Un DISPARADO tardio pasa a SOMBRA «tardio»: lo decide la base."""
    if t["estado"] == "DISPARADO":
        ahora = await conn.fetchval("SELECT clock_timestamp()")
        if (ahora - t["vela_cierre"]).total_seconds() > t["tope_retraso_s"]:
            t = como_sombra_tardia(t)
    try:
        fila = await conn.fetchrow(_INSERTA_REGISTRO, *_argumentos(t, huella_codigo))
    except asyncpg.PostgresError as exc:
        estado = getattr(exc, "sqlstate", None)
        if estado == TARDIO and t["estado"] == "DISPARADO":
            t = como_sombra_tardia(t)
            fila = await conn.fetchrow(_INSERTA_REGISTRO, *_argumentos(t, huella_codigo))
        elif estado == DOS_VIVOS:
            return {"registrado": False, "estado": t["estado"], "rechazo": str(exc)[:300]}
        else:
            raise
    return {
        "registrado": True,
        "registro_id": fila["registro_id"],
        "estado": t["estado"],
        "motivo": t["motivo"],
        "retraso_s": float(fila["retraso_s"]),
        "familia": t["familia"],
        "lado": t["lado"],
        "symbol": t["symbol"],
    }


async def latir(conn: asyncpg.Connection, *, vela_cierre: datetime | None, estado: str,
                duracion_s: float | None, detalle: dict[str, Any], error: str | None) -> None:
    await conn.execute(
        "INSERT INTO entrada_latido (vela_cierre, estado, duracion_s, codigo_version, detalle, error) "
        "VALUES ($1, $2, $3, $4, $5::json, $6)",
        vela_cierre,
        estado,
        duracion_s,
        M.CODIGO_VERSION,
        json.dumps(detalle, ensure_ascii=False, default=str),
        error,
    )


async def ultimo_tick(conn: asyncpg.Connection) -> datetime | None:
    return await conn.fetchval("SELECT max(vela_cierre) FROM entrada_latido WHERE estado = 'ok'")
