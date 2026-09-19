"""Quien publica un SESGO o una ESTRUCTURA por horizonte dentro del sobre, y en que se
diferencia de los vecinos que publican lo mismo con el mismo nombre.

POR QUE EXISTE ESTE FICHERO, medido y no supuesto. El sobre de produccion de BTC del
2026-09-18 23:42:40Z (profile=max) trae, para el MISMO horizonte 1d:

    structure_horizons.1d.bias        bajista   structure_horizons.1d.structure       LH_LL
    trend_matrix.timeframes.1d.bias   alcista   trend_matrix.timeframes.1d.structure  mixed

Dos campos que se llaman IGUAL, para el MISMO dia, diciendo lo CONTRARIO. Sobre las 15
parejas de los tres simbolos de ese minuto: 4 opuestas, 9 con una nula y la otra con
direccion, 1 iguales, 1 distintas sin ser opuestas. Ninguno de los dos numeros esta mal:
son dos calculos distintos con el mismo nombre, y el sobre no lo decia en ninguna parte.

LO QUE ESTE FICHERO NO HACE, Y ES A PROPOSITO: no cambia NI UN VALOR. No decide cual de
los dos sesgos tiene razon, no unifica calculos y no toca `trend_matrix` -su score se
persiste y se puntua a diario, y cambiar su calculo romperia esa serie-. Lo unico que
anade es lo que el sobre DICE de si mismo.

LOS HORIZONTES NO SE COPIAN AQUI: llegan por argumento desde las mismas tuplas que usan
los calculos (`_ALERT_HORIZONS`, `_TREND_TF`, `_MS_LAYER_HORIZONS`, `_INTRADAY_WINDOWS`,
`_DIVERGENCE_WINDOWS` y `_PF_HORIZONS`). Una lista copiada a mano se queda vieja en cuanto
alguien anada un marco, y entonces el glosario mentiria con mas autoridad que el silencio
de hoy.

LAS RUTAS DE `may_disagree_with` SON LAS DE `path`, LETRA POR LETRA, Y ESTAN TODAS: cada
publicador nombra a TODOS los demas de su mismo tipo. K101 lo cruza. Se hace por lista
completa y no por «los que solapan» a proposito: las capas de `market_structure` se miden
sobre TRAMOS (1m-15m, 30m-4h, 1d-7d) y no comparten etiqueta exacta con nadie, asi que un
criterio por solape las dejaria sin vigilancia justo a ellas. Y hay una trampa medida en
las etiquetas: en `divergences.windows` el sufijo `s` es SEMANAS -2s, 4s, 6s-, no
segundos; cualquier criterio que convierta etiquetas a segundos se equivoca ahi.
"""

from __future__ import annotations

from typing import Any

ENVELOPE_KEY = "field_disambiguation"

# Los dos tipos de cosa que este glosario vigila. Un bloque que publique una de las dos
# para un horizonte tiene que aparecer aqui, y nombrar a todos los de su tipo.
SESGO = "sesgo"
ESTRUCTURA = "estructura"

# Las rutas, una sola vez, para que `path` y `may_disagree_with` no puedan divergir.
P_SD_STATE = "structure_detail.horizons.<h>.state"
P_SH_STRUCT = "structure_horizons.<h>.structure"
P_TM_STRUCT = "trend_matrix.timeframes.<h>.structure"
P_MS_STRUCT = "market_structure.layers[i].price_structure"
P_SH_BIAS = "structure_horizons.<h>.bias"
P_TM_BIAS = "trend_matrix.timeframes.<h>.bias"
P_MS_BIAS = "market_structure.layers[i].bias"
P_DV_INTRA = "divergences.intraday.windows.<h>.divergence"
P_DV_SESION = "divergences.windows.<h>.divergence"

_PIVOTES_K2 = (
    "estado de estructura por PIVOTES de precio (k=2: un pivote necesita 2 barras a cada "
    "lado). Intradia sobre 120 barras remuestreadas del marco; diario sobre hasta 400 "
    "sesiones de daily_session_agg"
)
_PIVOTES_TREND = (
    "estado de estructura por PIVOTES de precio con OTRA parametrizacion: intradia k=2 "
    "sobre 60 barras (la mitad de profundidad que structure_detail) y diario k=1 sobre "
    "hasta 60 sesiones. Por eso puede decir 'mixed' donde structure_detail dice 'LH_LL'"
)
_OTRO_TRAMO = "SI discrepa: se mide sobre un TRAMO de marcos (1m-15m, 30m-4h, 1d-7d), no sobre uno"
_ES_DIVERGENCIA = "SI discrepa: es precio CONTRA CVD spot en su ventana, no una lectura de tendencia"
_ES_ESTRUCTURA = "no comparable: aquello es un estado de estructura, esto es una direccion"


def build(
    alert_horizons: tuple[str, ...],
    trend_timeframes: tuple[str, ...],
    layer_horizons: tuple[str, ...],
    intraday_divergence_windows: tuple[str, ...],
    session_divergence_windows: tuple[str, ...],
    passive_horizons: tuple[str, ...],
) -> dict[str, Any]:
    """El bloque que viaja en el sobre. Cada lista de horizontes llega del calculo real."""
    ah, tt, lh = list(alert_horizons), list(trend_timeframes), list(layer_horizons)
    comunes = [h for h in ah if h in tt]
    medido = (
        f"Medido el 2026-09-18 23:42Z sobre los {len(comunes)} horizontes comunes "
        f"({'/'.join(comunes)}) por 3 simbolos: 4 opuestas de 15, 9 con una nula y la otra "
        f"con direccion, 1 iguales"
    )
    return {
        "why": (
            "Varios bloques de este sobre publican un SESGO o una ESTRUCTURA para el mismo "
            "horizonte, con el mismo nombre de campo y calculos distintos. Discrepan de "
            "verdad. " + medido + ". Ninguna de las dos cifras esta mal: son dos preguntas "
            "distintas con el mismo nombre."
        ),
        "how_to_read": (
            "Antes de citar un 'bias' o una 'structure' de este sobre, busca su camino en "
            "publishers y usa 'measures' para decir QUE es. Dos caminos distintos NUNCA se "
            "promedian ni se presentan como confirmacion mutua: 'may_disagree_with' dice "
            "con quien puede chocar y por que. Un null no es un 'neutral' y un 'neutral' no "
            "es un null: cada publicador declara su vocabulario en 'values', y un "
            "'values': null significa que ese vocabulario NO esta declarado -no que sea "
            "libre-. Un campo puede no aparecer en su camino: eso no es null, es que su "
            "contenedor vino con available=false."
        ),
        "canonical_for_levels": (
            "structure_detail.horizons.<h> es la fuente de los NIVELES -bos_level, "
            "choch_level, invalidation_level- y de los pivotes que los sostienen. El panel "
            "dibuja esos niveles y la Mesa escribe con ellos su disparador y su "
            "invalidacion. Los demas bloques publican lecturas, no niveles."
        ),
        "publishers": [
            {
                "path": P_SD_STATE,
                "publishes": ESTRUCTURA,
                "horizons": ah,
                "measures": _PIVOTES_K2 + ". Es la CANONICA: de aqui salen los niveles",
                "values": ["HH_HL", "LH_LL", "mixed", None],
                "may_disagree_with": {
                    P_SH_STRUCT: (
                        "MISMO CALCULO, DOS CORTES: aquel no copia este campo, vuelve a "
                        "evaluarlo. horizon_structure llama a structure_detail SIN as_of, asi "
                        "que resuelve su propio clock_timestamp(), distinto del corte "
                        "compartido con el que el sobre llama a este bloque. Con la misma "
                        "vela cerrada dan lo mismo; si entra una vela entre los dos cortes, "
                        "pueden diferir SIN que ninguno este roto"
                    ),
                    P_TM_STRUCT: (
                        "SI discrepa: otra profundidad y otra k. Medido el 2026-09-18 23:42Z, "
                        "en 1d BTC decia LH_LL aqui y mixed alli"
                    ),
                    P_MS_STRUCT: _OTRO_TRAMO,
                },
            },
            {
                "path": P_SH_STRUCT,
                "publishes": ESTRUCTURA,
                "horizons": ah,
                "measures": (
                    "el MISMO calculo que " + P_SD_STATE + " -horizon_structure lo pide a "
                    "structure_detail- pero en una SEGUNDA evaluacion con SU PROPIO corte: se "
                    "le llama sin as_of, asi que resuelve su propio clock_timestamp(). No es "
                    "una copia del campo que viaja en este mismo sobre. Existe para que el "
                    "sesgo de este bloque viaje con la estructura de la que sale"
                ),
                "values": ["HH_HL", "LH_LL", "mixed", None],
                "may_disagree_with": {
                    P_SD_STATE: (
                        "MISMO CALCULO, DOS CORTES: coinciden mientras los dos cortes caigan "
                        "sobre la misma vela cerrada, y pueden diferir si entra una vela entre "
                        "ellos, sin que ninguno este roto. No es la copia que decia este "
                        "glosario hasta el 2026-09-19"
                    ),
                    P_TM_STRUCT: "SI discrepa: otra profundidad y otra k, igual que con su origen",
                    P_MS_STRUCT: _OTRO_TRAMO,
                },
            },
            {
                "path": P_TM_STRUCT,
                "publishes": ESTRUCTURA,
                "horizons": tt,
                "measures": (
                    _PIVOTES_TREND + ". NO es la que sostiene los niveles del panel ni el "
                    "disparador de la Mesa: esa es " + P_SD_STATE
                ),
                "values": ["HH_HL", "LH_LL", "mixed", None],
                "may_disagree_with": {
                    P_SD_STATE: (
                        "SI discrepa: aquella es la canonica para los NIVELES y mira mas "
                        "profundo (120 barras / 400 sesiones, k=2 siempre)"
                    ),
                    P_SH_STRUCT: "SI discrepa: es la copia de la canonica",
                    P_MS_STRUCT: _OTRO_TRAMO,
                },
            },
            {
                "path": P_MS_STRUCT,
                "publishes": ESTRUCTURA,
                "horizons": lh,
                "measures": (
                    "patron de pivotes del timeframe BASE de la capa, sobre un TRAMO de "
                    "marcos y no sobre un marco concreto. Es un COMPONENTE del voto de la "
                    "capa, no su resultado: el resultado es 'bias'"
                ),
                "values": ["HH/HL", "LH/LL", "mixta", None],
                "may_disagree_with": {
                    P_SD_STATE: "SI discrepa: otro tramo y otra fuente de barras",
                    P_SH_STRUCT: "SI discrepa: otro tramo y otra fuente de barras",
                    P_TM_STRUCT: "SI discrepa: otro tramo y otra fuente de barras",
                },
            },
            {
                "path": P_SH_BIAS,
                "publishes": SESGO,
                "horizons": ah,
                "measures": (
                    "direccion derivada de UNA SOLA senal: el estado de pivotes de "
                    "structure_detail. HH_HL->alcista, LH_LL->bajista, y CUALQUIER OTRO "
                    "estado -mixed, o sin muestra- -> null. Ese null significa 'la "
                    "estructura no es decisiva', NO 'neutral' y NO 'falta el dato'"
                ),
                "values": ["alcista", "bajista", None],
                "may_disagree_with": {
                    P_TM_BIAS: (
                        "SI discrepa, y mucho: aquel es mayoria de estructura+flujo+momentum "
                        "y NUNCA es null. " + medido
                    ),
                    P_MS_BIAS: "SI discrepa: voto multi-senal sobre un tramo de marcos",
                    P_DV_INTRA: _ES_DIVERGENCIA,
                    P_DV_SESION: _ES_DIVERGENCIA,
                },
            },
            {
                "path": P_TM_BIAS,
                "publishes": SESGO,
                "horizons": tt,
                "measures": (
                    "MAYORIA SIMPLE de hasta tres votos -estructura (el 'structure' de ESTE "
                    "bloque, que no es el de structure_detail), flujo (signo de spot y de "
                    "futuros en intradia; CVD spot en 1d/3d) y momentum-. Nunca es null: si "
                    "los votos empatan o no hay ninguno sale 'neutral'. votes_up y "
                    "votes_down dicen con cuantos se decidio"
                ),
                "values": ["alcista", "bajista", "neutral"],
                "may_disagree_with": {
                    P_SH_BIAS: (
                        "SI discrepa: aquel mira SOLO estructura y puede ser null. Un "
                        "'neutral' de aqui no es el null de alli. " + medido
                    ),
                    P_MS_BIAS: "SI discrepa: otro tramo de marcos y otros componentes",
                    P_DV_INTRA: _ES_DIVERGENCIA,
                    P_DV_SESION: _ES_DIVERGENCIA,
                },
            },
            {
                "path": P_MS_BIAS,
                "publishes": SESGO,
                "horizons": lh,
                "measures": (
                    "VOTO MULTI-SENAL (method=multi_signal_vote) de 4-5 componentes -CVD, "
                    "precio, OI, liquidaciones y pivotes- sobre un TRAMO de marcos. Mayoria "
                    "simple sin pesos; 'components' trae el voto de cada uno"
                ),
                "values": ["alcista", "bajista", "neutral"],
                "may_disagree_with": {
                    P_SH_BIAS: "SI discrepa: aquel es solo estructura, y por marco",
                    P_TM_BIAS: "SI discrepa: otros componentes, y por marco",
                    P_DV_INTRA: _ES_DIVERGENCIA,
                    P_DV_SESION: _ES_DIVERGENCIA,
                },
            },
            {
                "path": P_DV_INTRA,
                "publishes": SESGO,
                "horizons": list(intraday_divergence_windows),
                "measures": (
                    "DIVERGENCIA entre la pendiente del precio y la del CVD spot acumulado "
                    "en esa ventana intradia: 'alcista' = el precio baja mientras el CVD "
                    "sube. NO es una lectura de tendencia; es la contradiccion entre dos "
                    "series. 'sin_divergencia' es el valor POR DEFECTO y el caso normal, no "
                    "una rareza: medido el 2026-09-19 sobre 4 sobres, 18 de los 21 valores "
                    "presentes. Y una ventana sin barras suficientes no escribe este campo: "
                    "trae available=false en su lugar"
                ),
                "values": ["alcista", "bajista", "sin_divergencia", None],
                "may_disagree_with": {
                    P_SH_BIAS: "SI discrepa: aquel es estructura de pivotes",
                    P_TM_BIAS: "SI discrepa: aquel es tendencia",
                    P_MS_BIAS: "SI discrepa: aquel es voto multi-senal",
                    P_DV_SESION: (
                        "misma pregunta, otra escala: aquella va por SESIONES cerradas y "
                        "esta por ventanas de minutos"
                    ),
                },
            },
            {
                "path": P_DV_SESION,
                "publishes": SESGO,
                "horizons": list(session_divergence_windows),
                "measures": (
                    "la misma divergencia precio/CVD spot pero por SESIONES cerradas. OJO "
                    "CON LAS ETIQUETAS: aqui el sufijo 's' es SEMANAS (2s = 2 semanas), no "
                    "segundos. Anade 'sin_divergencia' a su vocabulario"
                ),
                "values": ["alcista", "bajista", "sin_divergencia", None],
                "may_disagree_with": {
                    P_SH_BIAS: "SI discrepa: aquel es estructura de pivotes",
                    P_TM_BIAS: "SI discrepa: aquel es tendencia",
                    P_MS_BIAS: "SI discrepa: aquel es voto multi-senal",
                    P_DV_INTRA: (
                        "misma pregunta, otra escala: aquella va por ventanas de minutos y "
                        "esta por sesiones cerradas"
                    ),
                },
            },
        ],
        # LISTA BLANCA DE HOMONIMOS QUE NO SON NI UN SESGO NI UNA ESTRUCTURA. Va escrita y
        # no callada por dos motivos medidos: la palabra 'neutral' la comparten con los
        # sesgos -quien barra el sobre por VALOR los encuentra al lado-, y el nombre
        # 'reading' lo publican CUATRO bloques para los mismos marcos con contenidos
        # distintos. Tolerar por lista blanca, nunca por descarte: lo que no este aqui ni
        # en publishers, K101 lo condena.
        "not_a_bias": [
            {
                "path": "passive_flow.horizons.<h>.reading",
                "horizons": list(passive_horizons),
                "measures": (
                    "CATEGORIA de absorcion pasiva. Comparte la palabra 'neutral' con los "
                    "sesgos y no es un sesgo. Es la unica 'reading' del sobre con vocabulario "
                    "cerrado: las otras tres son prosa"
                ),
                "values": ["reacumulacion_silenciosa", "redistribucion_silenciosa", "neutral"],
            },
            {
                "path": "market_impact.windows[i].reading",
                "horizons": ["las de market_impact.windows[].window"],
                "measures": (
                    "PROSA libre sobre el impacto de precio por millon de USD en esa "
                    "ventana. Mismo nombre que passive_flow...reading y para los mismos "
                    "marcos, y no es lo mismo ni tiene vocabulario cerrado"
                ),
                "values": None,
            },
            {
                "path": "divergences.windows.<h>.reading",
                "horizons": list(session_divergence_windows),
                "measures": (
                    "PROSA libre que explica la divergencia de esa ventana. El dato con "
                    "vocabulario es 'divergence', no esto"
                ),
                "values": None,
            },
            {
                "path": "divergences.intraday.windows.<h>.reading",
                "horizons": list(intraday_divergence_windows),
                "measures": "PROSA libre, como la anterior pero de la ventana intradia",
                "values": None,
            },
            {
                "path": "structure_detail.horizons.<h>.group",
                "horizons": ah,
                "measures": (
                    "GRUPO del calculo: 'med' -intradia, por remuestreo de ohlcv- o 'long' "
                    "-diario, por daily_session_agg-. El valor 'long' es un grupo, no una "
                    "direccion"
                ),
                "values": ["med", "long"],
            },
            {
                "path": "structure_horizons.<h>.group",
                "horizons": ah,
                "measures": "el mismo grupo del anterior; tampoco es una direccion",
                "values": ["med", "long"],
            },
        ],
        # SESGOS SIN MARCO. Existen, se llaman 'bias' y NO caben en la comparacion por
        # horizonte porque no tienen uno. Se nombran para que nadie los empareje con los de
        # arriba, y cada uno con SU vocabulario, que tampoco es el mismo.
        #
        # ERA UN MAPA DE PROSA Y AHORA ES UNA LISTA CON `values`, y el cambio de forma tiene
        # un motivo medido: la prosa NO SE PODIA CONTRASTAR, y bajo esa prosa habia CUATRO
        # vocabularios mal declarados que K101 no podia ver -los cuatro escritos por quien
        # escribio este fichero el 2026-09-18-:
        #   operator_read.bias                   decia None      y el codigo escribe "No Trade"
        #   swing_score.bias                     olvidaba        "SIN_DATOS"
        #   external_macro_context...internal_bias  lo mismo, porque es su copia en mayusculas
        #   market_memory_2y.historical_tilt     decia LONG/SHORT y el codigo tiene NEUTRAL
        # Medido el 2026-09-19 sobre 4 sobres (3 de produccion + el espejo): historical_tilt
        # sale NEUTRAL en 2 de 4. Consumidores de la forma vieja: NINGUNO -esta clave nacio
        # el 2026-09-18, no esta desplegada y el motor de K101 no la leia-.
        "bias_without_a_timeframe": [
            {
                "path": "operator_read.bias",
                "measures": "lectura de scalp del instante, por diferencia de long_score y short_score",
                "values": ["Long", "Short", "No Trade"],
            },
            {
                "path": "swing_score.bias",
                "measures": (
                    "balance de evidencia a dias-semanas. 'SIN_DATOS' NO es 'NEUTRAL': sale "
                    "cuando ningun componente pudo medirse"
                ),
                "values": ["LONG", "SHORT", "NEUTRAL", "SIN_DATOS"],
            },
            {
                "path": "trend_matrix.medium_term_alignment",
                "measures": (
                    "resumen de los sesgos de ESTE bloque sobre 4h+8h+1d. NO es la alineacion "
                    "de structure_horizons -que no tiene ninguna- ni la de market_structure"
                ),
                "values": ["alcista", "bajista", "mixto"],
            },
            {
                "path": "market_structure.alignment",
                "measures": "resumen de las tres capas de ESTE bloque",
                "values": ["alineado_alcista", "alineado_bajista", "mixto"],
            },
            {
                "path": "divergences.summary",
                "measures": (
                    "resumen de las ventanas SOSTENIDAS de este bloque. Lleva DOS cuentas "
                    "-cuantas confirman y cuantas se evaluaron-, al contrario que el de "
                    "intraday, que lleva una"
                ),
                "values": ["sin_divergencia", "mixta", "<alcista|bajista>_en_N_de_M_ventanas"],
            },
            {
                "path": "divergences.intraday.summary",
                "measures": "resumen de las ventanas intradia frescas de este bloque",
                "values": ["sin_divergencia", "mixta", "<alcista|bajista>_en_N_ventanas"],
            },
            {
                "path": "market_memory_2y.historical_tilt",
                "measures": "sesgo del analogo historico a 2 anos",
                "values": ["LONG", "SHORT", "NEUTRAL"],
            },
            {
                "path": "external_macro_context.alignment.internal_bias",
                "measures": (
                    "copia EN MAYUSCULAS de swing_score.bias para compararla con el macro "
                    "externo; no es una lectura independiente y arrastra su vocabulario entero"
                ),
                "values": ["LONG", "SHORT", "NEUTRAL", "SIN_DATOS"],
            },
            {
                "path": "wyckoff.bias.bias",
                "measures": (
                    "lectura del rango de Wyckoff, no de un marco temporal. Su vocabulario NO "
                    "esta declarado aqui: no lo he medido, y una lista inventada seria peor "
                    "que el hueco"
                ),
                "values": None,
            },
        ],
    }
