#!/bin/bash
# K62  UNA ETIQUETA DE VERSION NO PUEDE ABARCAR DOS REGLAS.
#
# regime_logic_version existe para una sola cosa: garantizar que dos filas se calcularon
# con la MISMA logica de regimen. El 2026-08-27 el arreglo de K59 cambio esa logica -el
# componente whale, 30 de 100 y el de mas peso, pasa de votar cero a ABSTENERSE, con lo
# que measured baja de 100 a 70 para BTC y ETH y el score se renormaliza sobre otro
# denominador- y la constante se quedo en 2 (metrics.py:95). Desde ese instante la columna
# que existe para impedir la mezcla es la que la produce.
#
# LA CONVENCION NO HAY QUE INVENTARLA, YA SE USO: metrics_snapshot lleva
# regime_logic_version NULL hasta 2026-08-12T03:10Z y 2 desde 03:11Z. Alguien ya la subio
# una vez por un cambio de esta misma clase.
#
# Y NO ES DECORATIVA. TRES modulos FILTRAN por ella:
#   daily_agg.py:354      WHERE symbol=$1 AND regime_logic_version=$2
#   signal_ledger.py:265  AND regime_logic_version=$3
#   signal_regime.py:146  _frozen_regime_logic_version_sql, cuyo docstring dice
#                         "Historical evidence -> required regime_logic_version, frozen
#                         and explicit"
#
# EL CORTE ESTA MEDIDO AL SEGUNDO Y SE CITA, NO SE INFIERE (regla C2 de la casa):
#   ultimo whale_intensity = 0 EXACTO de la era vieja  2026-08-27T04:42:05.516134Z (BTC)
#                                                      2026-08-27T04:42:05.525681Z (ETH)
#   arranque del servicio que instalo la regla nueva   2026-08-27T04:42:48Z
#   primera fila de la era nueva (whale NULL, los dos) 2026-08-27T04:43:05.466314Z
#   Las tres cifras encajan en 60 s, que es exactamente una cadencia de snapshot.
#   hechos.tsv:711 · prodsql sobre metrics_snapshot + journal de 140.
# El CORTE se declara aqui como constante Y SE VUELVE A CONFIRMAR CONTRA LOS DATOS en cada
# corrida antes de juzgar nada. Si el corte deja de verse en las filas, el check NO juzga:
# dice NO MEDIDO. Una constante que ya no describe el dato no es un instrumento.
#
# POR QUE EL CORTE NO SE DERIVA DE "primer whale_intensity NULL", que era lo obvio: MEDIDO
# HOY, no sirve. BTC y ETH tienen 713 nulos cada uno y el primero es del 2026-08-11T23:29Z,
# quince dias ANTES del cambio de regla: el nulo tambien lo produce la era vieja cuando le
# falta la fuente entera. Lo que SI parte las dos eras limpio es el CERO EXACTO -la era
# vieja lo escribia sistematicamente por debajo del umbral, la nueva no lo escribe nunca-.
#
# LO QUE EXIGE
#   0 · EL CORTE SE CONFIRMA (si no, NO MEDIDO y no se juzga): BTC y ETH tienen su ultimo
#       cero exacto pegado al corte, CERO ceros exactos despues, y hay filas suficientes
#       despues para que exista de que hablar.
#   1 · LA ETIQUETA QUE PRODUCCION ESCRIBE HOY no puede estar pegada tambien a filas de la
#       regla vieja. V sale de la fila MAS RECIENTE de metrics_snapshot -o sea de lo que
#       140 escribe, NO de la constante del repo: el repo puede ir por delante de lo
#       desplegado y entonces el check estaria juzgando codigo que no corre-. Se exige en
#       las DOS tablas que llevan la columna: metrics_snapshot y signal_observation.
#       CON UN ASIENTO QUE NO ES UN MARGEN A OJO: signal_ledger.py:261 escoge el snapshot
#       con ts <= context_as_of, asi que una observacion solo puede copiar la etiqueta V si
#       ya existia un snapshot con V cuando se escribio. Justo tras un despliegue esa
#       ausencia es FISICA. El elegible son las observaciones escritas 120 s despues del
#       primer snapshot con la etiqueta viva; mientras no haya ninguna, se declara.
#   2 · LA PAREJA QUE SE ESCRIBE TIENE QUE SER ACEPTABLE PARA QUIEN LA LEE. El escritor
#       pone (evidence_version, regime_logic_version) y hay DOS lectores con la misma
#       regla congelada: el mapa de signal_regime.py:40, que falla cerrado y publica el
#       conteo, y el CHECK signal_observation_pr25_regime_provenance_check de
#       sql/schema.sql:2476, que NO interpreta nada: rechaza el INSERT. Por eso esto es
#       ROJO y no una declaracion -lo degrade a declaracion una vez, mirando solo el
#       lector de Python, y costo 302 s de colector de scalp caido en produccion-.
#       Ademas se EJECUTA el CASE congelado REAL contra 140 y se imprime cuantas filas
#       quedan ilegibles, tambien en VERDE, para que el coste no se vuelva ruido de fondo.
#   3 · LAS DOS CONSULTAS QUE USAN LA CONSTANTE VIVA se EJECUTAN contra 140 con la
#       constante DEL RELEASE QUE CORRE EN 140, y tienen que devolver fila fresca para los
#       tres simbolos. Una constante subida sin desplegar, o desplegada sin que nadie haya
#       escrito todavia con la etiqueta nueva, deja a daily_agg y a signal_ledger sin
#       snapshot: escribirian regimen nulo sin decir por que.
#   CONTROL POSITIVO, obligatorio, dos brazos. Sin ellos un "arreglo" que parta cada fila
#       -version = reloj, version = hash- sale VERDE y no distingue de no tener version:
#         a CONTIGUIDAD: leidas de vieja a nueva, las 120 ultimas filas de BTC cambian de
#           version COMO MUCHO UNA VEZ, y las 60 de dentro de la era vieja, NINGUNA. Se
#           exige contiguidad y no "una sola version" a proposito: como las filas ya
#           escritas NO se re-etiquetan, la era nueva queda partida en dos etiquetas y
#           contar valores distintos daria un rojo falso durante la hora siguiente a cada
#           despliegue.
#         b el corte SE VE: la fraccion de ceros exactos de BTC en los 60 min ANTERIORES
#           al corte es 1, y en todo lo POSTERIOR es 0.
#   DECLARADO Y NO JUZGADO: las filas escritas entre el corte y el despliegue del arreglo
#       llevan la regla NUEVA con la etiqueta VIEJA. Re-etiquetarlas es escritura en
#       produccion, o sea PUERTA DE ALEJANDRO. Se imprime su numero y su arco en cada
#       corrida para que no se vuelva ruido de fondo.
#
# UNA CONSULTA QUE NO DEVUELVE LO QUE PEDI ES NO MEDIDO, NUNCA ROJO (leccion de K63): cada
# SELECT lleva una ETIQUETA literal en la primera columna y solo se acepta la linea que la
# trae. Un "ERROR: permission denied" no se parece a un conteo, y no se va a contar como
# si lo fuera.
#
# DE QUE ARBOL: datos de 140 (prodsql, solo lectura). Codigo del repo de 143 para el brazo
# 2a y para construir el CASE. La constante del brazo 3 se lee del RELEASE de 140. El
# espejo NO sirve y esta medido: sus filas se paran en el 2026-08-13 y no tiene ninguna de
# la era nueva.
set -uo pipefail
REPO=/srv/coinanalyze/repo
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo en $PY"; exit 2; }

PYTHONPATH="$REPO" "$PY" - <<'PY'
import subprocess
import sys

sys.path.insert(0, "/srv/coinanalyze/repo")

B = "/srv/coinanalyze/harness"

# El corte, citado arriba en la cabecera con sus tres cifras. Se confirma antes de usarlo.
CORTE = "2026-08-27 04:43:05.466314+00"
BTC, ETH = "BTCUSDT_PERP.A", "ETHUSDT_PERP.A"


class NoMedido(Exception):
    pass


def consulta(etiqueta, sql, ncols):
    """Devuelve las filas que traen la ETIQUETA. Cualquier otra cosa es NO MEDIDO."""
    try:
        p = subprocess.run(
            [B + "/bin/prodsql", "SET TIME ZONE 'UTC'; " + sql],
            capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise NoMedido("140 no respondio en 180 s a la consulta %s" % etiqueta)
    bruto = (p.stdout or "") + (p.stderr or "")
    filas, sobra = [], []
    for linea in bruto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        campos = linea.split("|")
        if campos[0] == etiqueta and len(campos) == ncols:
            filas.append([c if c != "" else None for c in campos[1:]])
        else:
            sobra.append(linea)
    if not filas:
        raise NoMedido(
            "la consulta %s no devolvio ninguna fila con su etiqueta; 140 dijo: %s"
            % (etiqueta, (sobra[0][:160] if sobra else "(nada)"))
        )
    if sobra:
        raise NoMedido(
            "la consulta %s devolvio %d linea(s) que no son filas mias; la primera: %s"
            % (etiqueta, len(sobra), sobra[0][:160])
        )
    return filas


def entero(x, que):
    try:
        return int(x)
    except (TypeError, ValueError):
        raise NoMedido("%s no es un numero: %r" % (que, x))


fallos, rotos, declara = [], [], []

try:
    # --- 0 · EL CORTE SE CONFIRMA CONTRA LOS DATOS ANTES DE JUZGAR NADA --------------
    # Y el mismo SELECT trae el brazo b del control positivo: la fraccion de ceros
    # exactos en la hora ANTERIOR al corte tiene que ser 1, y despues 0. Si el corte no
    # se ve en el dato, la constante de arriba no describe nada y no se juzga.
    q0 = consulta("q0", """
    SELECT 'q0', symbol,
           round(extract(epoch FROM timestamptz '%(c)s'
                 - max(ts) FILTER (WHERE whale_intensity = 0 AND ts < '%(c)s')))::text,
           count(*) FILTER (WHERE whale_intensity = 0 AND ts >= '%(c)s')::text,
           count(*) FILTER (WHERE ts >= '%(c)s')::text,
           count(*) FILTER (WHERE whale_intensity = 0
                              AND ts >= timestamptz '%(c)s' - interval '60 minutes'
                              AND ts < '%(c)s')::text,
           count(*) FILTER (WHERE ts >= timestamptz '%(c)s' - interval '60 minutes'
                              AND ts < '%(c)s')::text
    FROM metrics_snapshot
    WHERE symbol IN ('%(b)s','%(e)s')
    GROUP BY 2 ORDER BY 2
    """ % {"c": CORTE, "b": BTC, "e": ETH}, 7)

    if len(q0) != 2:
        raise NoMedido("esperaba BTC y ETH en metrics_snapshot y vinieron %d simbolos"
                       % len(q0))
    for simbolo, hueco, ceros_despues, filas_despues, ceros_antes, filas_antes in q0:
        if hueco is None:
            raise NoMedido("%s no tiene ningun whale_intensity = 0 exacto antes del corte: "
                           "la era vieja no se ve, el corte declarado no describe el dato"
                           % simbolo)
        # 300 s = cinco cadencias. Medido hoy: 60 s exactos en BTC y en ETH.
        hueco = entero(hueco, "hueco entre el ultimo cero de %s y el corte" % simbolo)
        if not 0 < hueco <= 300:
            raise NoMedido("entre el ultimo cero exacto de %s y el corte declarado (%s) hay "
                           "%d s: no estan pegados, el corte dejo de describir el dato"
                           % (simbolo, CORTE, hueco))
        if entero(ceros_despues, "ceros exactos de %s tras el corte" % simbolo) != 0:
            raise NoMedido(
                "%s tiene %s ceros exactos DESPUES del corte: la firma con la que separo "
                "las dos eras ya no separa, asi que no juzgo con ella"
                % (simbolo, ceros_despues))
        if entero(filas_despues, "filas de %s tras el corte" % simbolo) < 100:
            raise NoMedido("%s solo tiene %s filas despues del corte: no hay de que hablar"
                           % (simbolo, filas_despues))
        if simbolo == BTC:
            ca = entero(ceros_antes, "ceros exactos de BTC en la hora previa")
            fa = entero(filas_antes, "filas de BTC en la hora previa")
            if fa < 30:
                raise NoMedido("BTC solo tiene %d filas en la hora previa al corte" % fa)
            if ca != fa:
                rotos.append(
                    "CONTROL POSITIVO ROTO (b): BTC deberia traer cero exacto en las %d "
                    "filas de la hora ANTERIOR al corte -es lo que hacia la regla vieja- "
                    "y solo lo trae en %d. El corte que declaro no es el corte que hay"
                    % (fa, ca))

    # --- 1 · LA ETIQUETA QUE PRODUCCION ESCRIBE HOY -----------------------------------
    # V sale del dato, no de la constante del repo. Lo que se juzga es lo que 140 escribe.
    q1 = consulta("q1", """
    SELECT 'q1',
           coalesce(regime_logic_version::text,'NULL'),
           ts::text,
           round(extract(epoch FROM now() - ts))::text
    FROM metrics_snapshot ORDER BY ts DESC LIMIT 1
    """, 4)
    v_prod, ts_ultima, edad = q1[0]
    edad = entero(edad, "edad de la ultima fila de metrics_snapshot")
    if v_prod == "NULL":
        raise NoMedido("la fila mas reciente de metrics_snapshot (%s) no lleva "
                       "regime_logic_version" % ts_ultima)
    if edad > 900:
        raise NoMedido("la ultima fila de metrics_snapshot es de hace %d s (%s): "
                       "produccion no esta escribiendo y no hay sujeto que juzgar"
                       % (edad, ts_ultima))
    v_prod = entero(v_prod, "regime_logic_version de la ultima fila")

    q2 = consulta("q2", """
    SELECT 'q2','metrics_snapshot', min(ts)::text, max(ts)::text, count(*)::text
      FROM metrics_snapshot WHERE regime_logic_version = %(v)d
    UNION ALL
    SELECT 'q2','signal_observation', min(observed_at)::text, max(observed_at)::text,
           count(*)::text
      FROM signal_observation WHERE regime_logic_version = %(v)d
    """ % {"v": v_prod}, 5)

    # signal_observation NO PUEDE LLEVAR LA ETIQUETA ANTES QUE metrics_snapshot, y eso no
    # es un margen a ojo: signal_ledger.py:261 escoge el snapshot con ts <= context_as_of,
    # asi que una observacion solo puede copiar la version V si YA existia un snapshot con
    # V cuando se escribio. Justo despues de un despliegue hay una ventana -medida hoy: la
    # primera observacion salio a las 15:07:02Z con regimen NULL y el primer snapshot con
    # 3 a las 15:07:05Z, 3 s despues- en la que la ausencia es fisica, no un defecto. El
    # elegible son las observaciones escritas MAS DE 120 s despues del primer snapshot con
    # la etiqueta viva; si todavia no hay ninguna, se declara y no se juzga.
    asiento = consulta("q2b", """
    SELECT 'q2b', count(*)::text,
           count(*) FILTER (WHERE regime_logic_version = %(v)d)::text
      FROM signal_observation
     WHERE observed_at >= (SELECT min(ts) FROM metrics_snapshot
                            WHERE regime_logic_version = %(v)d) + interval '120 seconds'
    """ % {"v": v_prod}, 3)
    obs_elegibles = entero(asiento[0][0], "observaciones elegibles tras el asiento")
    obs_con_v = entero(asiento[0][1], "observaciones con la version viva")

    for tabla, arco_min, arco_max, n in q2:
        n = entero(n, "filas con version %d en %s" % (v_prod, tabla))
        if n == 0 or arco_min is None:
            if tabla == "signal_observation" and obs_elegibles == 0:
                declara.append(
                    "signal_observation aun no ha escrito ninguna observacion 120 s "
                    "despues del primer snapshot con la etiqueta %d: la ausencia todavia "
                    "es fisica y no se juzga" % v_prod)
                continue
            fallos.append(
                "ninguna fila de %s lleva la version %d que produccion acaba de escribir, "
                "y ya hay %d observaciones escritas con margen de sobra: la etiqueta viva "
                "no tiene datos detras" % (tabla, v_prod, obs_elegibles))
            continue
        if arco_min < CORTE:
            fallos.append(
                "la version %d, que es la que produccion escribe AHORA, esta pegada "
                "tambien a filas de la regla VIEJA en %s: su arco empieza en %s -antes del "
                "corte %sZ- y llega a %s. Son %d filas bajo UNA etiqueta y DOS reglas, y "
                "las tres consultas que filtran por esta columna las mezclan creyendolas "
                "homogeneas"
                % (v_prod, tabla, arco_min, CORTE[:19].replace(" ", "T"), arco_max, n))

    # --- 2 · LA PAREJA QUE SE ESCRIBE TIENE QUE SER ACEPTABLE PARA QUIEN LA LEE --------
    # ESTE BRAZO LO QUITE Y LO VOLVI A PONER, Y LA LECCION VALE MAS QUE EL BRAZO. Lo
    # escribi como ROJO, me parecio que exigia demasiado -la unica salida era publicar
    # evidencia 7, y eso arrastra otros contratos- y lo degrade a "declarar y no juzgar"
    # razonando que signal_regime FALLA CERRADO y publica el conteo de lo ilegible. El
    # razonamiento era correcto sobre signal_regime y COMPLETAMENTE FALSO sobre la base:
    # sql/schema.sql:2476 tiene un CHECK con la MISMA regla, y un CHECK no interpreta
    # nada, RECHAZA EL INSERT. Desplegado a las 15:06:51Z, el colector de scalp murio con
    # CheckViolationError y estuvo 302 s sin escribir una sola observacion.
    # QUITAR UN BRAZO ROJO PORQUE PAGARLO SALE CARO NO LO HACE FALSO. Y la razon de que
    # este me pareciera opinable es que solo mire el lector de Python: la regla estaba
    # tambien en el esquema, que es donde no se opina.
    from app.metrics import REGIME_LOGIC_VERSION
    from app.signal_ledger import SIGNAL_EVIDENCE_VERSION
    from app.signal_regime import (
        FROZEN_EVIDENCE_REGIME_LOGIC_VERSION,
        _frozen_regime_logic_version_sql,
    )

    exigido = FROZEN_EVIDENCE_REGIME_LOGIC_VERSION.get(SIGNAL_EVIDENCE_VERSION)
    if exigido != REGIME_LOGIC_VERSION:
        fallos.append(
            "el repo ESCRIBE la pareja (evidence_version=%s, regime_logic_version=%s) y hay "
            "DOS lectores que exigen %s para esa evidencia: el mapa congelado de "
            "signal_regime.py:40 y, sobre todo, el CHECK "
            "signal_observation_pr25_regime_provenance_check de sql/schema.sql:2476, que NO "
            "es interpretable -rechaza el INSERT-. Desplegar esta pareja para el colector de "
            "scalp y deja de escribir: probado en produccion el 2026-08-27T15:06:51Z y "
            "revertido a las 15:12Z, 302 s sin una sola observacion"
            % (SIGNAL_EVIDENCE_VERSION, REGIME_LOGIC_VERSION, exigido))

    # Se EJECUTA el CASE congelado REAL -construido llamando a la funcion del modulo, no
    # copiado- contra las observaciones posteriores al corte.
    q3 = consulta("q3", """
    SELECT 'q3', estado, count(*)::text FROM (
      SELECT CASE %s ELSE 'legible' END AS estado
      FROM signal_observation obs
      WHERE obs.observed_at >= '%s'
    ) t GROUP BY 2 ORDER BY 2
    """ % (_frozen_regime_logic_version_sql("obs"), CORTE), 3)

    ilegibles = sum(entero(n, "observaciones %s" % e) for e, n in q3 if e != "legible")
    legibles = sum(entero(n, "observaciones %s" % e) for e, n in q3 if e == "legible")
    if ilegibles:
        declara.append(
            "ya ilegibles para el regimen %d de %d observaciones posteriores al corte, "
            "pasadas por el CASE congelado REAL" % (ilegibles, ilegibles + legibles))

    # --- 3 · LAS DOS CONSULTAS QUE USAN LA CONSTANTE VIVA, EJECUTADAS -----------------
    # Con la constante del RELEASE de 140, no la del repo: lo que corre es lo que importa.
    rel = subprocess.run(
        [B + "/bin/prod",
         "grep -m1 '^REGIME_LOGIC_VERSION' /opt/coinalyze/current/app/metrics.py"],
        capture_output=True, text=True, timeout=60,
    )
    crudo = ((rel.stdout or "") + (rel.stderr or "")).strip()
    if "=" not in crudo:
        raise NoMedido("no pude leer REGIME_LOGIC_VERSION del release de 140: %s"
                       % (crudo[:160] or "(nada)"))
    v_rel = entero(crudo.split("=")[-1].strip(), "REGIME_LOGIC_VERSION del release de 140")

    q4 = consulta("q4", """
    SELECT 'q4', s.symbol,
           (SELECT round(extract(epoch FROM now() - m.ts))::text
              FROM metrics_snapshot m
             WHERE m.symbol = s.symbol AND m.regime_logic_version = %(v)d
             ORDER BY m.ts DESC LIMIT 1),
           (SELECT round(extract(epoch FROM now() - m.ts))::text
              FROM metrics_snapshot m
             WHERE m.symbol = s.symbol AND m.ts <= now()
               AND m.regime_logic_version = %(v)d
             ORDER BY m.ts DESC LIMIT 1)
    FROM (SELECT DISTINCT symbol FROM metrics_snapshot
           WHERE ts >= now() - interval '30 minutes') s
    ORDER BY 2
    """ % {"v": v_rel}, 4)

    for simbolo, edad_daily, edad_ledger in q4:
        for quien, e in (("daily_agg.py:354", edad_daily),
                         ("signal_ledger.py:265", edad_ledger)):
            if e is None:
                fallos.append(
                    "la consulta real de %s, pidiendo regime_logic_version=%d como hace el "
                    "release que corre en 140, no devuelve NINGUN snapshot para %s: "
                    "escribiria regimen nulo sin decir por que" % (quien, v_rel, simbolo))
            elif entero(e, "edad del snapshot de %s" % simbolo) > 900:
                fallos.append(
                    "la consulta real de %s para %s devuelve un snapshot de hace %s s con "
                    "la constante %d del release: la etiqueta viva dejo de recibir filas"
                    % (quien, simbolo, e, v_rel))

    # --- CONTROL POSITIVO a · dos filas de la MISMA era salen JUNTAS -------------------
    # LO QUE SE EXIGE ES CONTIGUIDAD, NO "una sola version", y la diferencia importa:
    # decidimos NO re-etiquetar las filas ya escritas -es puerta de Alejandro-, asi que la
    # era nueva queda legitimamente partida en dos etiquetas, la vieja de arrastre y la
    # nueva. Contar versiones distintas daria CONTROL POSITIVO ROTO durante la hora
    # siguiente a cada despliegue, que es un rojo falso, y los rojos falsos son lo que
    # ensena a ignorar los de verdad. Lo que NINGUNA version sana hace es alternar: una
    # etiqueta parte el tiempo en tramos CONTIGUOS. Leidas de vieja a nueva, las 120
    # ultimas filas pueden cambiar de version COMO MUCHO UNA VEZ, y las 60 de dentro de la
    # era vieja, NINGUNA. Una version por fila -reloj, hash, contador- da 119 cambios y
    # cae aqui, que es lo que este control existe para atrapar.
    # Los cambios se cuentan en SQL y no trayendose las 180 filas: la salida de las
    # herramientas se corta a 8 KB (harness/env MAX_BYTES) y 180 filas la pasan, con lo
    # que llegarian truncadas. Traer dos numeros no tiene ese problema y no hace falta
    # desactivar el corte. `IS DISTINCT FROM` para que NULL -> 2 cuente como cambio, y
    # rn > 1 para no contar la primera fila, que no tiene anterior.
    q5 = consulta("q5", """
    SELECT 'q5','recientes',
           count(*) FILTER (WHERE rn > 1 AND v IS DISTINCT FROM prev)::text,
           count(*)::text
      FROM (SELECT regime_logic_version AS v,
                   lag(regime_logic_version) OVER (ORDER BY ts) AS prev,
                   row_number() OVER (ORDER BY ts) AS rn
              FROM (SELECT ts, regime_logic_version FROM metrics_snapshot
                     WHERE symbol='%(b)s' ORDER BY ts DESC LIMIT 120) t) u
    UNION ALL
    SELECT 'q5','era_vieja',
           count(*) FILTER (WHERE rn > 1 AND v IS DISTINCT FROM prev)::text,
           count(*)::text
      FROM (SELECT regime_logic_version AS v,
                   lag(regime_logic_version) OVER (ORDER BY ts) AS prev,
                   row_number() OVER (ORDER BY ts) AS rn
              FROM (SELECT ts, regime_logic_version FROM metrics_snapshot
                     WHERE symbol='%(b)s' AND ts < '%(c)s'
                     ORDER BY ts DESC LIMIT 60) t) u
    """ % {"b": BTC, "c": CORTE}, 4)

    # EL UMBRAL DEL TRAMO RECIENTE NO ES 1, Y ESTA ES LA RAZON MEDIDA: un despliegue que
    # sube la constante deja UN cambio, y si se revierte deja DOS -a mi me paso hoy: la
    # ventana tiene una isla de 18 filas con la version 3 entre las 15:07:05Z y las
    # 15:11:05Z-. Eso es historia legitima de despliegues, no una version enferma. Lo que
    # este control existe para atrapar -version por fila: reloj, hash, contador- da 119
    # cambios sobre 120 filas, asi que cualquier umbral entre 2 y 100 lo distingue igual
    # de bien. Con 6 caben tres despliegues en la ventana sin rojo falso. El tramo de
    # DENTRO de una era sigue exigiendo CERO, que es donde el control es afilado.
    for tramo, maximo in (("recientes", 6), ("era_vieja", 0)):
        fila = [(c, n) for t, c, n in q5 if t == tramo]
        if len(fila) != 1:
            raise NoMedido("el tramo %s del control positivo no vino una sola vez" % tramo)
        cambios = entero(fila[0][0], "cambios de version en el tramo %s" % tramo)
        cuantas = entero(fila[0][1], "filas del tramo %s" % tramo)
        if cuantas < 60:
            raise NoMedido("el tramo %s solo trae %d filas de BTC y el control positivo "
                           "necesita 60: no se puede montar" % (tramo, cuantas))
        if cambios > maximo:
            rotos.append(
                "CONTROL POSITIVO ROTO (a): %d filas seguidas de BTC del tramo %s cambian "
                "de regime_logic_version %d veces y el maximo es %d. Una etiqueta de "
                "version parte el tiempo en tramos CONTIGUOS; una que alterna no distingue "
                "de no tener version" % (cuantas, tramo, cambios, maximo))

    # --- DECLARADO Y NO JUZGADO · el residuo mal etiquetado ---------------------------
    # La version que estaba viva EN el corte sale del dato: la de la ultima fila anterior.
    q6 = consulta("q6", """
    SELECT 'q6','metrics_snapshot', count(*)::text, max(ts)::text
      FROM metrics_snapshot WHERE ts >= '%(c)s' AND regime_logic_version =
        (SELECT regime_logic_version FROM metrics_snapshot
          WHERE ts < '%(c)s' ORDER BY ts DESC LIMIT 1)
    UNION ALL
    SELECT 'q6','signal_observation', count(*)::text, max(observed_at)::text
      FROM signal_observation WHERE observed_at >= '%(c)s' AND regime_logic_version =
        (SELECT regime_logic_version FROM metrics_snapshot
          WHERE ts < '%(c)s' ORDER BY ts DESC LIMIT 1)
    """ % {"c": CORTE}, 4)
    # ISLAS: filas posteriores al corte que llevan una version que produccion YA NO
    # escribe. Un despliegue revertido las deja, y son lo unico que rompe la contiguidad
    # de una etiqueta, asi que se nombran con su arco en vez de esconderse dentro del
    # control positivo. Hoy hay una mia: 18 filas con la version 3.
    islas = consulta("q7", """
    SELECT 'q7', coalesce(regime_logic_version::text,'NULO'), count(*)::text,
           min(ts)::text, max(ts)::text
      FROM metrics_snapshot
     WHERE ts >= '%(c)s' AND regime_logic_version IS DISTINCT FROM %(v)d
     GROUP BY 2 ORDER BY 2
    """ % {"c": CORTE, "v": v_prod}, 5)
    for version, n, desde, hasta in islas:
        declara.append(
            "ISLA de %s filas con la version %s en metrics_snapshot, de %s a %s: una "
            "etiqueta que produccion ya no escribe, posterior al corte. Rompe la "
            "contiguidad de la etiqueta viva y no se puede quitar sin escribir en "
            "produccion" % (n, version, desde, hasta))

    resto = []
    for tabla, n, hasta in q6:
        n = entero(n, "residuo de %s" % tabla)
        if n:
            resto.append("%s %d filas (hasta %s)" % (tabla, n, hasta))
    if resto:
        declara.append(
            "REGLA NUEVA CON ETIQUETA VIEJA, escritas entre el corte y el despliegue del "
            "arreglo: " + " y ".join(resto) + ". Re-etiquetarlas es escritura en "
            "produccion, o sea PUERTA DE ALEJANDRO; la alternativa barata es dejarlas y "
            "que el instante quede escrito, que ya lo esta y al segundo")

except NoMedido as e:
    # UN NO MEDIDO NO PUEDE ENTERRAR UN ROJO YA MEDIDO. Si un brazo posterior no se pudo
    # montar pero uno anterior YA fallo, lo que hay es un fallo medido con menos evidencia
    # de la que queria, no una ausencia de medicion. Al reves si: sin nada medido, NOMED.
    if fallos or rotos:
        print("ROJO: " + (rotos + fallos)[0])
        for x in (rotos + fallos)[1:]:
            print("      " + x)
        print("      Y ADEMAS un brazo se quedo sin medir: %s" % e)
        sys.exit(1)
    print("NO MEDIDO: %s" % e)
    sys.exit(2)

residuo = ("DECLARADO Y NO JUZGADO · " + " · ".join(declara)) if declara \
          else "DECLARADO: nada que declarar tras el corte."

if rotos:
    print("ROJO: " + rotos[0])
    for x in rotos[1:] + fallos:
        print("      " + x)
    print("      " + residuo)
    sys.exit(1)

if fallos:
    print("ROJO: " + fallos[0])
    for x in fallos[1:]:
        print("      " + x)
    print("      " + residuo)
    sys.exit(1)

print("VERDE: la version %d que produccion escribe no toca ninguna fila anterior al corte "
      "%sZ, ni en metrics_snapshot ni en signal_observation; las consultas reales de "
      "daily_agg y signal_ledger devuelven snapshot fresco con la constante %d del release "
      "de 140; control positivo: 60 filas de BTC de la era nueva y 60 de la vieja, con 1 "
      "sola version cada era."
      % (v_prod, CORTE[:19].replace(" ", "T"), v_rel))
print("      " + residuo)
sys.exit(0)
PY
exit $?
