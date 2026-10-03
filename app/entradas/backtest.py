"""BACKTEST EN MUESTRA del generador de entradas (campana 135, C6). Solo CUENTA: no resuelve.

Corre el MISMO motor (motor.paso) vela a vela sobre una base que NO es la de produccion ni el
espejo -una COPIA desechable del espejo, que se borra al terminar- con el registro en MEMORIA:
aqui no se escribe nada en ninguna tabla.

Lo que el espejo no tiene se DECLARA y no manda a SOMBRA (modo BACKTEST en el motor): el libro
(orderbook_snapshot dura ~6 h) -coste = solo comision, spread NO MEDIDO-, y con el el mid de
Bybit; la referencia del plan es la apertura de 1 min del minuto que abre en T. El calendario sin
cubrir tambien sale NO MEDIDO. Es BACKTEST EN MUESTRA: reglas escritas despues de ver el periodo
y datos revisados. No alimenta ningun cambio de reglamento.

    python -m app.entradas.backtest --dsn postgresql:///<copia> --desde 2026-07-24 --hasta 2026-08-13
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from app.entradas import insumos as I
from app.entradas import motor as M
from app.entradas import reglamento as R


def simular(
    secuencia: list[tuple[datetime, dict[str, Any]]],
    *,
    symbol: str,
    perfil: str,
    versiones: list[dict[str, Any]],
    revision: dict[str, Any] | None,
    codigo: str,
    modo: str = M.BACKTEST,
    registro: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Encadena motor.paso sobre (T, insumos) en orden, con el registro en memoria."""
    registro = [] if registro is None else registro
    evaluaciones = []
    for T, insumos in secuencia:
        previos = [
            f for f in registro
            if f["symbol"] == symbol and f["perfil"] == perfil and f["vela_cierre"] < T
        ]
        resultado = M.paso(T=T, symbol=symbol, perfil=perfil, modo=modo, versiones=versiones,
                           insumos=insumos, previos=previos, revision=revision, codigo=codigo)
        for t in resultado["transiciones"]:
            registro.append({**t, "orden": len(registro)})
        evaluaciones.append({"T": T, **resultado["evaluacion"]})
    return {"registro": registro, "evaluaciones": evaluaciones}


def _cuantiles(valores: list[float]) -> dict[str, float] | None:
    if not valores:
        return None
    v = sorted(valores)
    n = len(v)
    return {"n": n, "min": round(v[0], 3), "p25": round(v[n // 4], 3), "mediana": round(v[n // 2], 3),
            "p75": round(v[(3 * n) // 4], 3), "max": round(v[-1], 3)}


def _cuenta(registro: list[dict[str, Any]]) -> dict[str, Any]:
    por_dia: Counter = Counter()
    sombras: Counter = Counter()
    celdas: Counter = Counter()
    combinaciones: Counter = Counter()
    r_neto: list[float] = []
    distancias: dict[str, list[float]] = {"t1_bps": [], "stop_bps": [], "racimos_saltados": []}
    for f in registro:
        if f["estado"] not in ("DISPARADO", "SOMBRA"):
            continue
        dia = f["vela_cierre"].strftime("%Y-%m-%d")
        por_dia[(dia, f["familia"], f["perfil"], f["lado"], f["estado"])] += 1
        celdas[(f["familia"], f["perfil"], f["lado"], f["estado"])] += 1
        plan = f["foto"]["plan"]
        if plan["r"]["neto"] is not None:
            r_neto.append(plan["r"]["neto"])
        if plan["distancias_bps"]["t1"] is not None:
            distancias["t1_bps"].append(plan["distancias_bps"]["t1"])
        if plan["distancias_bps"]["stop"] is not None:
            distancias["stop_bps"].append(plan["distancias_bps"]["stop"])
        distancias["racimos_saltados"].append(len(plan["stop"]["racimos_saltados"]))
        if f["estado"] == "SOMBRA":
            decision = f["foto"]["decision"]
            combinaciones[" + ".join(sorted(decision["motivo"]))] += 1
            for motivo in decision["motivo"]:
                sombras[motivo] += 1
            sombras[f"tipo:{decision['tipo_sombra']}"] += 1
            for etiqueta in decision["etiquetas"]:
                sombras[f"etiqueta:{etiqueta}"] += 1
    dias = sorted({k[0] for k in por_dia})
    return {
        "por_dia": [list(k) + [v] for k, v in sorted(por_dia.items())],
        "por_celda": [list(k) + [v] for k, v in sorted(celdas.items())],
        "sombras_por_motivo": dict(sorted(sombras.items())),
        "sombras_por_combinacion": dict(combinaciones.most_common(12)),
        "r_neto_t1": _cuantiles(r_neto),
        "distancias": {k: _cuantiles(v) for k, v in distancias.items()},
        "dias_con_candidatos": len(dias),
        "estados": dict(Counter(f["estado"] for f in registro)),
    }


async def correr(conn, *, desde: datetime, hasta: datetime, doc: dict[str, Any],
                 bases: dict[str, str], codigo: str, simbolos: list[str] | None = None) -> dict:
    versiones = R.versiones_en_curso(doc)
    comun = R.valores(versiones[0]["bloques"]["comun"])
    calendario = R.valores(versiones[0]["bloques"]["calendario"])
    paso = timedelta(minutes=min(p["vela_min"] for p in comun["perfiles"].values()))
    registro: list[dict[str, Any]] = []
    evaluaciones: Counter = Counter()
    motivos_no_evaluable: Counter = Counter()
    T = desde
    while hasta >= T:
        revision = R.revision_vigente(doc, T)
        for perfil, p in comun["perfiles"].items():
            if int(T.timestamp()) % (p["vela_min"] * 60):
                continue
            for symbol in simbolos or comun["simbolos"]:
                insumos = await I.cargar(conn, symbol=symbol, base_asset=bases[symbol], T=T,
                                         perfil=perfil, comun=comun, calendario=calendario,
                                         modo=M.BACKTEST)
                resultado = simular([(T, insumos)], symbol=symbol, perfil=perfil,
                                    versiones=versiones, revision=revision, codigo=codigo,
                                    registro=registro)
                for e in resultado["evaluaciones"]:
                    evaluaciones[(perfil, e["estado"])] += 1
                    if e["estado"] != "ok":
                        motivos_no_evaluable[e["motivo"].split(":")[0]] += 1
        T += paso
    return {
        "modo": "BACKTEST EN MUESTRA",
        "desde": M.iso(desde),
        "hasta": M.iso(hasta),
        "evaluaciones": {f"{k[0]}:{k[1]}": v for k, v in sorted(evaluaciones.items())},
        "no_evaluables_por_motivo": dict(motivos_no_evaluable.most_common()),
        **_cuenta(registro),
    }


def main(argv: list[str] | None = None) -> int:
    import asyncpg

    from app.config import MARKET_SYMBOL_CATALOG
    from app.entradas import codigo as C

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", required=True, help="la COPIA desechable, nunca el espejo ni 140")
    parser.add_argument("--desde", required=True)
    parser.add_argument("--hasta", required=True)
    parser.add_argument("--simbolos", default="")
    args = parser.parse_args(argv)
    if "coinalyze_espejo" in args.dsn.split("/")[-1].split("?")[0]:
        raise SystemExit("el backtest no corre sobre el espejo: haz una copia desechable")

    async def _corre() -> dict:
        conn = await asyncpg.connect(args.dsn, server_settings={"timezone": "UTC"})
        try:
            return await correr(
                conn,
                desde=datetime.fromisoformat(args.desde).replace(tzinfo=UTC),
                hasta=datetime.fromisoformat(args.hasta).replace(tzinfo=UTC),
                doc=R.cargar_valido(),
                bases={i.symbol: i.base_asset for i in MARKET_SYMBOL_CATALOG},
                codigo=C.huella_codigo(),
                simbolos=[s for s in args.simbolos.split(",") if s] or None,
            )
        finally:
            await conn.close()

    print(json.dumps(asyncio.run(_corre()), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
