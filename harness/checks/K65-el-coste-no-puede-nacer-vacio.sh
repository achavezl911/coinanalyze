#!/bin/bash
# K65  UN MANIFIESTO NO PUEDE NACER SIN DECLARAR LO QUE CUESTA OPERAR.
#
# El manifiesto congela lo que se va a probar. Entre sus campos hay uno que decide si el
# resultado es un negocio o un adorno: el coste por lado. Hoy ese campo es OPCIONAL y su
# valor por defecto es VACIO -- lo dice el propio ayudante del congelador, en
# scripts/freeze_walk_forward_manifest.py:313: "Optional explicit taker fee scenario to
# freeze into the manifest. Empty by default." Un manifiesto congelado con
# execution_exchanges = [binance, bybit] y fee_bps_per_side = {} afirma, sin decirlo, que
# operar es gratis en los dos sitios.
#
# NO ES HIPOTETICO Y NO LO MIDO YO: el UNICO manifiesto que existe en produccion,
# pr11-fixed-kernel-v1, esta exactamente asi (hechos.tsv linea 831, medido 2026-08-28T02:23:40Z
# con psql en 140). Y el precio ya se pago: hechos.tsv:677 tuvo que declarar NO SE SABE
# sobre las comisiones al medir el tamano del efecto, porque no habia numero que sumar.
# Una ventaja bruta de 0.78-0.95 bps a h=1..3 no se puede juzgar sin el coste encima.
#
# LA FORMA DEL DEFECTO ES LA DE LA CASA, tercera familia en cuatro dias: el camino "no me
# lo dijeron" y el camino "no cuesta nada" comparten salida. K60 -el resumen contaba como
# cero lo que era nulo-, K63 -un error de permisos se publicaba como afirmacion sobre el
# dato-, K49 -"nada que empujar" y "el push fallo" salian los dos por la puerta buena-.
# Aqui: "nadie declaro el coste" sale por la misma puerta que "el coste es cero".
#
# QUE EXIGE, y se INDUCE llamando al congelador, no leyendo el fichero:
#   1 · el manifiesto POR DEFECTO -que es el que sale si nadie pasa tarifas- no puede
#       congelarse. Tiene que fallar ANTES de tocar la base: la conexion es un centinela
#       que estalla al primer atributo, asi que si el veredicto llega es que la guarda
#       corrio antes que la escritura, no despues.
#   2 · tampoco puede congelarse el PARCIAL: tarifa para un exchange y silencio para el
#       otro. Es el mismo fallo abierto, mas dificil de ver, y es el que sobrevive a
#       "acuerdate de pasar --fee-bps-per-side".
#   3 · CONTROL POSITIVO, obligatorio: con TODOS los exchanges tarifados el congelador
#       tiene que PASAR de largo la validacion y llegar a la base. Una guarda que rechaza
#       todo esta tan rota como la que no rechaza nada, y sin este brazo el check saldria
#       VERDE con un `raise ValueError` puesto en la primera linea de la funcion.
#   4 · LO YA CONGELADO SE SIGUE PUDIENDO LEER. El rechazo es al NACER, no al leer, y esto
#       se fija aqui a proposito para que nadie lo "endurezca" mas tarde sin saber lo que
#       tira: (a) la fila viva de 140 no se puede reparar sin la PUERTA 1 de Alejandro
#       -- mutar dato de produccion, y ademas cambia el manifest_hash que el propio informe
#       valida --, y (b) K60, hoy VERDE, corre scripts/evaluate_walk_forward.py contra
#       pr11-fixed-kernel-v1 en el espejo (K60:58). Fallar cerrado tambien en la lectura
#       cambiaria un informe que dice "no evaluable" por una excepcion, y se llevaria por
#       delante un check verde por un motivo que nada tiene que ver con lo que mide.
#       Un manifiesto muerto que se puede LEER es mas util que uno que revienta.
#
# LO QUE ESTE CHECK NO DICE, y conviene que quede escrito para que nadie lo lea de mas:
# no juzga si la tarifa es REALISTA. Un manifiesto que declare 0.0 bps PASA, porque la
# invariante es "esta declarado", no "es creible": lo primero se puede comprobar desde
# aqui y lo segundo no. Un cero declarado es una afirmacion que alguien firma; un mapa
# vacio no es ninguna afirmacion, y esa es toda la diferencia.
#
# NO ABRE NINGUNA CONEXION: importa app.signal_walk_forward, que no importa app.db, asi
# que no hay create_pool y no se escribe en market_assets ni en symbols. Comprobado con
# el centinela, que es justo lo que estalla si alguien toca la base.
#
# DE QUE ARBOL: codigo del repo de 143. No toca 140 ni el espejo.
set -uo pipefail
B=/srv/coinanalyze/harness
REPO=/srv/coinanalyze/repo
. "$B/env"

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

cd "$REPO" || { echo "NO MEDIDO: no se pudo entrar en $REPO"; exit 2; }

"$PY" - <<'PY'
import asyncio
import sys

sys.path.insert(0, "/srv/coinanalyze/repo")

try:
    from app.signal_walk_forward import (
        EXECUTION_EXCHANGES,
        WalkForwardManifestOptions,
        freeze_walk_forward_manifest,
    )
except Exception as exc:  # noqa: BLE001 - el canal, no el sujeto
    print(f"NO MEDIDO: no se pudo importar el congelador ({type(exc).__name__}: {exc})")
    sys.exit(2)


class TocoLaBase(Exception):
    """El centinela llego hasta la base: la validacion dejo pasar el manifiesto."""


class ConexionCentinela:
    """Conexion que estalla al primer atributo que se le pida.

    No es un simulacro de asyncpg: es un detector de umbral. Si el congelador
    valida ANTES de consultar -- que es lo que hace hoy, signal_walk_forward.py:539
    esta por encima del primer fetchrow de :542 -- este objeto nunca se toca y el
    veredicto es el ValueError. Si la validacion no rechaza, lo primero que ocurre
    es un acceso a atributo y sale TocoLaBase. Asi el brazo distingue "rechazado"
    de "aceptado" sin escribir una sola fila en ningun sitio.
    """

    def __getattr__(self, nombre):
        raise TocoLaBase(f"el congelador llego a conn.{nombre} sin rechazar el manifiesto")


def congela(opciones):
    """-> ('rechazado', mensaje) | ('aceptado', mensaje) | ('roto', mensaje)"""
    try:
        asyncio.run(freeze_walk_forward_manifest(ConexionCentinela(), opciones))
    except TocoLaBase as exc:
        return "aceptado", str(exc)
    except ValueError as exc:
        return "rechazado", str(exc)
    except Exception as exc:  # noqa: BLE001
        return "roto", f"{type(exc).__name__}: {exc}"
    return "roto", "el congelador devolvio sin tocar la base y sin rechazar"


exchanges = tuple(EXECUTION_EXCHANGES)
if not exchanges:
    print("NO MEDIDO: EXECUTION_EXCHANGES esta vacio; no hay nada que tarifar")
    sys.exit(2)

TARIFA = 5.0
todas = tuple((intercambio, TARIFA) for intercambio in exchanges)

# --- 3 · CONTROL POSITIVO PRIMERO ------------------------------------------------------
# Va delante a proposito: si el control no pasa, los rechazos de 1 y 2 no prueban nada,
# porque una guarda que rechaza todo los produce igual.
estado, detalle = congela(
    WalkForwardManifestOptions(exchanges=exchanges, fee_bps_per_side=todas)
)
if estado == "roto":
    print(f"NO MEDIDO: el control positivo no llego a juzgarse ({detalle})")
    sys.exit(2)
if estado != "aceptado":
    print(
        "CONTROL POSITIVO ROTO: un manifiesto con los "
        f"{len(exchanges)} exchanges tarifados a {TARIFA} bps tambien se rechaza "
        f"-- {detalle}. Una guarda que rechaza todo no distingue nada"
    )
    sys.exit(1)

# --- 1 · el manifiesto por defecto, que es el que sale si nadie pasa tarifas ------------
por_defecto = WalkForwardManifestOptions()
estado, detalle = congela(por_defecto)
if estado == "roto":
    print(f"NO MEDIDO: el brazo del manifiesto por defecto no llego a juzgarse ({detalle})")
    sys.exit(2)
if estado != "rechazado":
    print(
        f"SE PUEDE CONGELAR UN MANIFIESTO SIN COSTE: execution_exchanges="
        f"{list(por_defecto.exchanges)} con fee_bps_per_side={dict(por_defecto.fee_bps_per_side)} "
        f"pasa la validacion y {detalle}. Operar sale gratis en "
        f"{len(por_defecto.exchanges)} exchanges porque nadie lo declaro"
    )
    sys.exit(1)
razon_defecto = detalle

# --- 2 · el parcial: tarifa para uno, silencio para el resto ----------------------------
if len(exchanges) < 2:
    razon_parcial = (
        f"no juzgado: EXECUTION_EXCHANGES tiene un solo elemento ({exchanges[0]}), "
        "asi que no existe manifiesto parcial que inducir"
    )
else:
    sin_tarifa = exchanges[1:]
    estado, detalle = congela(
        WalkForwardManifestOptions(exchanges=exchanges, fee_bps_per_side=todas[:1])
    )
    if estado == "roto":
        print(f"NO MEDIDO: el brazo del manifiesto parcial no llego a juzgarse ({detalle})")
        sys.exit(2)
    if estado != "rechazado":
        print(
            "SE PUEDE CONGELAR UN MANIFIESTO A MEDIO TARIFAR: "
            f"{exchanges[0]} declara {TARIFA} bps y {list(sin_tarifa)} no declara nada, "
            f"y aun asi pasa la validacion y {detalle}. El silencio de "
            f"{len(sin_tarifa)} exchange(s) se lee como cero"
        )
        sys.exit(1)
    razon_parcial = f"rechazado nombrando {list(sin_tarifa)}"

# --- 4 · lo ya congelado se sigue pudiendo leer -----------------------------------------
# La fila viva de 140 trae fee_bps_per_side={} y no se puede reparar sin la PUERTA 1.
# El camino de LECTURA -- _options_from_spec, y por debajo validate_manifest_options --
# tiene que seguir aceptandolo, o K60 se cae con el.
try:
    from app.signal_walk_forward import validate_manifest_options
except Exception as exc:  # noqa: BLE001
    print(f"NO MEDIDO: no se pudo importar el validador de lectura ({type(exc).__name__}: {exc})")
    sys.exit(2)

try:
    validate_manifest_options(
        WalkForwardManifestOptions(), require_declared_execution_cost=False
    )
except TypeError:
    # Todavia no existe el interruptor: hoy el validador acepta el mapa vacio para todo el
    # mundo, asi que la lectura esta a salvo por el mismo motivo por el que el brazo 1
    # esta ROJO. No es este el brazo que tiene que enrojecer.
    lectura = "el validador todavia no distingue nacer de leer"
except ValueError as exc:
    print(
        "EL RECHAZO SE COLO EN LA LECTURA: un manifiesto ya congelado con "
        f"fee_bps_per_side={{}} deja de poder leerse -- {exc}. La fila viva de 140 no se "
        "puede reparar sin la PUERTA 1, y K60 evalua esa misma fila contra el espejo: "
        "esto no arregla el coste, tira un check verde"
    )
    sys.exit(1)
else:
    lectura = "la lectura de lo ya congelado sigue aceptando el mapa vacio"

print(
    f"un manifiesto sin coste NO PUEDE NACER: el congelador rechaza el de por defecto "
    f"-- {razon_defecto} -- y el parcial -- {razon_parcial} --, los dos ANTES de tocar la "
    f"base, mientras el mismo congelador con los {len(exchanges)} exchanges "
    f"{list(exchanges)} tarifados llega a la base -control positivo-. Y {lectura}. "
    f"Declarado 0.0 bps PASA: la invariante es que este declarado, no que sea creible"
)
PY
exit $?
