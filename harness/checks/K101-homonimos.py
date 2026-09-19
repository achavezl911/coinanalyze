"""K101 · motor. Juzga UN sobre: quien publica un sesgo o una estructura por horizonte,
y si el sobre lo declara.

No decide donde sale el sobre ni como se consigue: eso es del `.sh`. Aqui solo entra un
JSON, y sale un veredicto con sus nombres.

    uso:  K101-homonimos.py <sujeto> <sobre.json> [inventario-extra.json ...]
    sale:  0 VERDE   ·   1 ROJO   ·   2 NO MEDIDO

LOS CINCO BRAZOS, y cada uno dice A QUE ALCANCE juzga (A44):

  A · DECLARADO -> EXISTE. Cada `publishers[].path` del glosario tiene que existir de
      verdad en el sobre, y con los horizontes que declara. Caza un glosario que se quedo
      viejo, que es la forma de mentira mas cara: tiene autoridad.
  B1· EXISTE -> DECLARADO, POR NOMBRE. Toda hoja que se llame como una hoja declarada
      (bias, structure, state, price_structure, divergence...) y cuelgue de un horizonte
      tiene que estar cubierta por un publicador o por la lista blanca `not_a_bias`.
      Funciona aunque el sobre venga sin valores.
  B2· EXISTE -> DECLARADO, POR VALOR. Toda hoja cuyo VALOR sea una direccion o un estado
      de estructura y cuelgue de un horizonte, se llame como se llame. Este es el brazo
      que caza un nombre NUEVO. Necesita un sobre CON valores: si no hay ni uno, NO MEDIDO
      y lo dice -un cero en las dos direcciones no es un aprobado-.
  C · LOS VECINOS. Cada publicador nombra a TODOS los demas de su tipo en
      `may_disagree_with`, y cada ruta nombrada es la de un publicador de verdad.
  D · EL PROMPT. Todo camino con punto y todo identificador snake_case que cite el prompt
      tiene que existir en el sobre. El inventario se puede AMPLIAR con otros sobres
      (`inventario-extra.json`): asi un arbol que aun no esta desplegado se juzga contra
      las claves que produccion ya sirve MAS las que el arbol anade. Sin inventario
      suficiente, NO MEDIDO y nombra lo que no pudo resolver.
  D2· LOS GRUPOS DEL PROMPT. Una frase que nombre un bloque CON GRUPOS no puede atribuirle
      los grupos de otro bloque. Se juzga frase a frase, y solo las frases que nombran algun
      bloque que tenga grupos.
  E · EL VOCABULARIO. Lo que el glosario declara que un campo PUEDE valer, contra lo que
      vale donde hay dato. Cubre `publishers`, `not_a_bias` y `bias_without_a_timeframe`.
      Un `values: null` es «no declarado» y se nombra sin juzgar. Nacio el 2026-09-19 de un
      agujero medido: el glosario declaraba vocabularios y nadie los contrastaba.
  F · LOS AGREGADOS. El prompt no puede presentar el resumen de un bloque como si fuera el
      del vecino. Tambien del 2026-09-19, y tambien de un defecto que ningun otro brazo
      veia porque el camino citado EXISTIA.
  G · LAS INVARIANTES. Un «NO discrepa» del glosario es una PROMESA sobre los datos y este
      brazo la cobra horizonte a horizonte. Del mismo dia: el glosario prometia que
      structure_horizons.<h>.structure era copia literal de structure_detail, y no lo es.

CONTROL POSITIVO EN CADA BRAZO (A36): si un brazo no llego a mirar ni un sujeto, no dice
VERDE: dice NO MEDIDO. Un brazo que aprueba sin sujeto es peor que no tenerlo.

LO QUE ESTE CHECK NO HACE: no compara VALORES entre bloques ni dice cual tiene razon. Que
structure_horizons.1d.bias diga bajista y trend_matrix.timeframes.1d.bias diga alcista el
mismo minuto es CORRECTO -son dos calculos-; lo que se condena es que el sobre no lo diga.
"""

import json
import re
import sys

# Valores que son una DIRECCION. Se dejan fuera 'long' y 'short' en minuscula a
# proposito y esta medido por que: en este sobre 'long' es el GRUPO de horizonte de
# structure_detail y el LADO de una liquidacion, no una direccion. Meterlos daba 13
# bloques con "sesgo" el 2026-09-18, casi todos falsos.
DIRECCION = {
    "alcista", "bajista", "neutral", "mixto", "mixta", "sin_divergencia",
    "LONG", "SHORT", "NEUTRAL", "Long", "Short", "Neutral",
}
# Valores que son un ESTADO DE ESTRUCTURA. Medido: cero falsos positivos en el sobre de
# produccion del 2026-09-18, los 18 aciertos de los cuatro bloques que la publican.
ESTRUCTURA = {"HH_HL", "LH_LL", "mixed", "HH/HL", "LH/LL", "mixta", "Mixta"}

# Una etiqueta de horizonte se reconoce por su FORMA, no por sus segundos. Es
# deliberado: en `divergences.windows` la 's' de 2s/4s/6s es SEMANAS, y cualquier
# criterio que convierta etiquetas a segundos se equivoca justo ahi.
ETIQUETA = re.compile(r"^\d+(s|m|h|d|w|min)$")
TRAMO = re.compile(r"^\d+(s|m|h|d|w)-\d+(s|m|h|d|w)$")
CLAVES_MARCO = ("horizon", "timeframe", "window", "marco")


def es_horizonte(t):
    return bool(ETIQUETA.match(str(t)) or TRAMO.match(str(t)))


def canon(camino):
    """Un camino real -> su plantilla. 'a.1d.b' -> 'a.<h>.b'; 'a.[3].b' -> 'a[i].b'."""
    out = ""
    for s in camino.split("."):
        if re.match(r"^\[\d+\]$", s):
            out += "[i]"
        elif es_horizonte(s):
            out += (":" if out else "") + "<h>"
        else:
            out += (":" if out else "") + str(s)
    return out.replace(":", ".").replace(".[i]", "[i]")


def canon_declarado(p):
    """La misma forma para lo que viene escrito en el glosario, para poder comparar."""
    return re.sub(r"<[a-z]+>", "<h>", str(p)).replace(".[i]", "[i]")


def recorre(nodo, camino, marco, hojas):
    """Junta (camino, valor, horizonte) de cada hoja. El horizonte sale del propio camino
    o de un campo horizon/timeframe/window del objeto que la contiene."""
    if isinstance(nodo, dict):
        m = marco
        for k in CLAVES_MARCO:
            v = nodo.get(k)
            if isinstance(v, str) and es_horizonte(v):
                m = v
        for k, v in nodo.items():
            recorre(v, camino + [str(k)], k if es_horizonte(k) else m, hojas)
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            m = marco
            if isinstance(v, dict):
                for k in CLAVES_MARCO:
                    x = v.get(k)
                    if isinstance(x, str) and es_horizonte(x):
                        m = x
            recorre(v, [*camino, f"[{i}]"], m, hojas)
    elif camino:
        hojas.append((".".join(camino), nodo, marco))


# ---------------------------------------------------------------- brazo D · el prompt
def inventario(sobre):
    """Claves y valores de texto del sobre, SIN el prompt: contarse a si mismo no vale."""
    claves, valores = set(), set()

    def anda(n):
        if isinstance(n, dict):
            for k, v in n.items():
                claves.add(str(k))
                anda(v)
        elif isinstance(n, list):
            for v in n:
                anda(v)
        elif isinstance(n, str):
            valores.add(n)

    anda({k: v for k, v in sobre.items() if k != "interpretation_prompt"})
    return claves, valores


def tramos(camino):
    out = []
    for parte in camino.split("."):
        m = re.match(r"^([a-z_][a-z0-9_]*)((?:\[[a-z_]\])*)$", parte)
        if not m:
            return None
        out.append(m.group(1))
        out.extend(re.findall(r"\[[a-z_]\]", m.group(2)))
    return out


def baja(nodo, ts):
    for t in ts:
        if isinstance(nodo, list):
            nodo = nodo[0] if nodo else None
        if t.startswith("["):
            if isinstance(nodo, dict) and nodo:
                nodo = next(iter(nodo.values()))
                continue
            return False
        if not isinstance(nodo, dict) or t not in nodo:
            return False
        nodo = nodo[t]
    return True


def en_algun_sitio(nodo, ts, prof=0):
    if prof > 6:
        return False
    if isinstance(nodo, dict):
        if ts[0] in nodo and baja(nodo, ts):
            return True
        return any(en_algun_sitio(v, ts, prof + 1) for v in nodo.values())
    if isinstance(nodo, list):
        return any(en_algun_sitio(v, ts, prof + 1) for v in nodo)
    return False


CAMINO = re.compile(r"\b([a-z_][a-z0-9_]*)((?:\.[a-z_][a-z0-9_]*|\[[a-z_]\])+)")
PALABRA = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")


def grupos_por_bloque(sobre):
    """Que GRUPOS usa cada bloque de primer nivel, leidos del sobre y no de una lista.

    Un grupo es el valor de una clave llamada 'group' o 'layer'. Medido en el sobre del
    2026-09-18: market_structure usa micro/mid/macro y structure_detail y
    structure_horizons usan med/long. Solo esos tres bloques tienen grupos.
    """
    out = {}

    def anda(n, acc):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in ("group", "layer") and isinstance(v, str):
                    acc.add(v)
                anda(v, acc)
        elif isinstance(n, list):
            for v in n:
                anda(v, acc)

    for bloque, v in sobre.items():
        if bloque == "interpretation_prompt":
            continue
        acc = set()
        anda(v, acc)
        if acc:
            out[bloque] = acc
    return out


def brazo_agregados(prompt, sobre, agregados):
    """F · UN AGREGADO ES DE SU BLOQUE, Y EL PROMPT NO PUEDE PRESTARLO.

    EL DEFECTO QUE LO TRAJO, del 2026-09-18 y escrito por quien escribio este check:
        «structure_horizons NO tiene esas capas: su "group" es 'med' ..., y su alineacion
         por marco la resume trend_matrix.medium_term_alignment sobre 4h+8h+1d»
    `medium_term_alignment` resume los sesgos DE trend_matrix (`mid = [tfs[t]["bias"] ...]`)
    y structure_horizons no tiene agregado ninguno. Ningun otro brazo lo veia: el camino
    EXISTE (brazo D lo resuelve) y la frase no nombra ningun grupo (brazo D2 no entra).

    LA REGLA, y es de gramatica y no de semantica: **en la frase donde se cita un AGREGADO,
    el ultimo nombre de bloque que aparece ANTES de el tiene que ser su propio bloque.** En
    castellano lo que va delante de «su X» es el poseedor, asi que si delante hay otro
    bloque, la frase se lo esta atribuyendo. Las menciones que SOLAPAN con el propio camino
    no cuentan -`trend_matrix` esta dentro de `trend_matrix.medium_term_alignment`-.

    El alcance son los caminos que el glosario declara en `bias_without_a_timeframe`: son
    justo los resumenes de bloque, que es donde este error se puede cometer.
    """
    bloques = [b for b in sobre if b != "interpretation_prompt"]
    if not agregados or not bloques:
        return [], 0
    alternativas = "|".join(sorted(map(re.escape, bloques), key=len, reverse=True))
    rx_bloque = re.compile(rf"\b({alternativas})\b")
    fallos, juzgados = [], 0
    for frase in re.split(r"(?<=\.)\s+|\n", prompt):
        for camino in agregados:
            raiz = camino.split(".")[0]
            for m in re.finditer(re.escape(camino), frase):
                juzgados += 1
                previos = [
                    b for b in rx_bloque.finditer(frase)
                    if b.end() <= m.start() and not (b.start() >= m.start() and b.end() <= m.end())
                ]
                if previos and previos[-1].group(1) != raiz:
                    fallos.append(
                        f"la frase presenta {camino} como de '{previos[-1].group(1)}', y ese "
                        f"agregado resume los campos de '{raiz}' y de ningun otro bloque. "
                        f"Frase: «{frase.strip()[:200]}»"
                    )
    return fallos, juzgados


def brazo_grupos(prompt, sobres):
    """EL BRAZO QUE CAZA LA FRASE DE S3: «Mide alineacion micro/mid/macro via
    structure_horizons». structure_horizons NO tiene micro/mid/macro -sus grupos son med y
    long-; quien los tiene es market_structure.

    Se juzga FRASE A FRASE, y SOLO las frases que nombran algun bloque QUE TIENE GRUPOS.
    Lo segundo no es prudencia: es lo que impide que la palabra 'macro' de «usa solo
    intradia/macro» -una frase que habla de data_quality, que no tiene grupos- se lea como
    una atribucion. Lo permitido es la UNION de los grupos de los bloques nombrados en esa
    frase; cualquier otra palabra de grupo que aparezca ahi es una atribucion falsa.
    """
    gpb = {}
    for s in sobres:
        for b, g in grupos_por_bloque(s).items():
            gpb.setdefault(b, set()).update(g)
    vocab = set().union(*gpb.values()) if gpb else set()
    if not vocab:
        return [], 0
    rx = re.compile(r"\b({})\b".format("|".join(sorted(map(re.escape, vocab)))))
    fallos, juzgadas = [], 0
    for frase in re.split(r"(?<=[.;:])\s+|\n", prompt):
        nombrados = [b for b in gpb if re.search(rf"\b{re.escape(b)}\b", frase)]
        if not nombrados:
            continue
        juzgadas += 1
        permitidos = set().union(*(gpb[b] for b in nombrados))
        malos = sorted({m.group(1) for m in rx.finditer(frase)} - permitidos)
        if malos:
            fallos.append(
                "el prompt atribuye el grupo {} a {}, que usa {}. Quien usa {} es {}. "
                "Frase: «{}»".format(
                    malos, sorted(nombrados), sorted(permitidos), malos,
                    sorted(b for b in gpb if set(malos) & gpb[b]) or "nadie",
                    frase.strip()[:160],
                )
            )
    return fallos, juzgadas


MUDOS_MAX = 3


def mudos(sobre):
    """Bloques de primer nivel que no publican nada: ausentes, vacios o available=false."""
    out = set()
    for k, v in sobre.items():
        if v is None or v == {} or v == [] or isinstance(v, dict) and v.get("available") is False:
            out.add(k)
    return out


def brazo_prompt(prompt, sobres):
    """Devuelve (fallos, resueltos, sin_juzgar).

    EL TERCER CUBO, otra vez, y aqui es la diferencia entre un check util y uno que
    condena por una base sin datos. Medido el 2026-09-18: el sobre construido contra una
    conexion que no contesta trae 15 bloques MUDOS de 51 -snapshot, oi_context, wyckoff,
    volume_profile...- y el de produccion solo 2. Una cita a `snapshot.regime_score` es
    CORRECTA y no resuelve en el sobre seco: condenarla seria medir la base, no el prompt.
      · un camino cuyo bloque raiz esta MUDO en todos los sobres -> sin juzgar, nombrado
      · un identificador suelto solo se condena si el inventario es LLENO (algun sobre con
        MUDOS_MAX o menos bloques mudos); si no, sin juzgar y nombrado
    """
    invs = [inventario(s) for s in sobres]
    mudos_por_sobre = [mudos(s) for s in sobres]
    lleno = any(len(m) <= MUDOS_MAX for m in mudos_por_sobre)
    fallos, ok, sin_juzgar = [], [], []
    vistos = set()
    for m in CAMINO.finditer(prompt):
        c = m.group(0)
        if c in vistos:
            continue
        vistos.add(c)
        ts = tramos(c)
        if not ts:
            continue
        if any(
            (ts[0] in s and baja(s, ts)) or (ts[0] not in s and en_algun_sitio(s, ts))
            for s in sobres
        ):
            ok.append(c)
        elif all(ts[0] in mu for mu in mudos_por_sobre):
            sin_juzgar.append(f"{c} (el bloque '{ts[0]}' esta mudo en todos los sobres)")
        else:
            fallos.append(f"camino que no existe en ningun sobre: {c}")
    for m in PALABRA.finditer(prompt):
        p = m.group(1)
        if p in vistos or any(p == c.split(".")[0].split("[")[0] for c in vistos):
            continue
        if any(p in cl or p in va or any(p in v for v in va) for cl, va in invs):
            ok.append(p)
            continue
        if p in [f.split(": ")[-1] for f in fallos] or any(p in s for s in sin_juzgar):
            continue
        if lleno:
            fallos.append(f"identificador que no esta en ningun sobre: {p}")
        else:
            peor = min(len(m) for m in mudos_por_sobre)
            sin_juzgar.append(
                f"{p} (identificador suelto, y ningun sobre del inventario esta lleno: "
                f"el mas completo tiene {peor} bloques mudos)"
            )
    return fallos, ok, sin_juzgar


# ---------------------------------------------------------------------------- veredicto
def main():
    if len(sys.argv) < 3:
        print("NO MEDIDO: uso K101-homonimos.py <sujeto> <sobre.json> [extra.json ...]")
        return 2
    sujeto = sys.argv[1]

    def leer(ruta):
        with open(ruta) as fh:
            return json.load(fh)

    try:
        sobre = leer(sys.argv[2])
        extras = [leer(p) for p in sys.argv[3:]]
    except Exception as e:
        print(f"NO MEDIDO: no se pudo leer un sobre de {sujeto}: {e}")
        return 2

    gloss = sobre.get("field_disambiguation")
    if not isinstance(gloss, dict) or not isinstance(gloss.get("publishers"), list):
        print(
            f"ROJO [{sujeto}]: el sobre no trae field_disambiguation.publishers, asi que publica "
            "un 'bias' y una 'structure' por horizonte desde varios bloques SIN decir en "
            "ninguna parte que miden ni de cual se diferencian"
        )
        return 1

    pubs = gloss["publishers"]
    nob = gloss.get("not_a_bias") or []
    # `bias_without_a_timeframe` fue un mapa de prosa hasta el 2026-09-19 y ahora es una
    # lista con `values`. Se aceptan las dos formas para que el motor pueda juzgar un sobre
    # de produccion viejo sin reventar, y la del mapa sale SIN VOCABULARIO -que es justo lo
    # que era: prosa incontrastable-.
    swt = gloss.get("bias_without_a_timeframe")
    if isinstance(swt, dict):
        swt = [{"path": k, "measures": v, "values": None} for k, v in swt.items()]
    elif not isinstance(swt, list):
        swt = []
    rutas_pub = {canon_declarado(p.get("path")): p for p in pubs}
    rutas_nob = {canon_declarado(p.get("path")) for p in nob}
    hojas_declaradas = {r.split(".")[-1].split("[")[0] for r in rutas_pub}
    hojas_declaradas |= {r.split(".")[-1].split("[")[0] for r in rutas_nob}

    hojas = []
    recorre(sobre, [], None, hojas)
    reales = {}
    for c, v, marco in hojas:
        d = reales.setdefault(
            canon(c), {"marcos": set(), "valores": [], "ejemplo": c, "por_marco": {}}
        )
        if marco:
            d["marcos"].add(marco)
            d["por_marco"].setdefault(marco, []).append(v)
        d["valores"].append(v)

    rojos, lineas = [], []

    # --- A · DECLARADO -> EXISTE
    # EL TERCER CUBO, y no es un adorno: un contenedor que este vacio porque su fuente no
    # trajo datos -`available: false`- no publica NADA, asi que exigirle sus rutas seria
    # condenar al glosario por una base sin datos. Se NOMBRA y no se juzga. Lo que si es
    # ROJO es que el contenedor ESTE, con contenido, y la ruta declarada no aparezca.
    #
    # RECORRE EL CAMINO ENTERO Y NO SOLO SU PRIMER TRAMO, y esto se pago: hasta el
    # 2026-09-19 esta funcion mirava solo la raiz, asi que con
    # `divergences = {available: true, intraday: {available: false, windows: {}}}` -lo que
    # produccion sirve cuando en 17 h no hay filas que casen- K101 daba ROJO diciendo que
    # `divergences.intraday.windows.<h>.divergence` "NO EXISTE", cuando lo que pasaba es
    # que el SUB-BLOQUE estaba mudo. Un sub-bloque mudo no es una ruta sin declarar (A54).
    def contenedor_mudo(ruta):
        nodo, recorrido = sobre, []
        for tramo in ruta.replace("[i]", ".[i]").split("."):
            if tramo in ("<h>", "[i]"):
                # El comodin: si el contenedor esta vacio, es que no hay ni un horizonte.
                if isinstance(nodo, dict | list) and not nodo:
                    return f"'{'.'.join(recorrido)}' no trae ningun horizonte"
                if isinstance(nodo, dict):
                    nodo = next(iter(nodo.values()))
                elif isinstance(nodo, list):
                    nodo = nodo[0]
                else:
                    return None
                recorrido.append(tramo)
                continue
            if not isinstance(nodo, dict):
                return None
            if tramo not in nodo:
                # Es la HOJA declarada la que falta, con su contenedor presente y poblado:
                # eso no es mudez, es una ruta que no existe. Lo juzga quien llama.
                return None
            nodo = nodo[tramo]
            recorrido.append(tramo)
            camino = ".".join(recorrido)
            if nodo is None:
                return f"'{camino}' viene a null"
            if isinstance(nodo, dict):
                if nodo.get("available") is False:
                    return f"'{camino}' viene con available=false"
                if not nodo:
                    return f"'{camino}' viene vacio"
            elif isinstance(nodo, list) and not nodo:
                return f"'{camino}' viene como lista vacia"
        return None

    vistos_a, sin_juzgar_a, sin_datos_a = 0, [], []
    for r, p in sorted(rutas_pub.items()):
        if r not in reales:
            motivo = contenedor_mudo(r)
            if motivo:
                sin_juzgar_a.append(f"{r} · {motivo}")
            else:
                rojos.append(f"A · el glosario declara {r} y en el sobre NO EXISTE esa ruta")
            continue
        vistos_a += 1
        # LA COMPARACION DE HORIZONTES ES ASIMETRICA, y esta medido por que.
        # PRESENTE Y SIN DECLARAR es ROJO: alguien anadio un marco y el glosario no se
        # entero, que es justo la deriva que este brazo persigue.
        # DECLARADO Y AUSENTE solo se NOMBRA: una ventana sin datos no escribe su clave
        # -medido el 2026-09-18 en produccion, `divergences.windows` publica 'divergence'
        # solo en las ventanas con available=true, y ese dia era 1 de 8-. Condenarlo
        # convertiria este check en un termometro del mercado (A53).
        decl = {str(h) for h in (p.get("horizons") or [])}
        real = reales[r]["marcos"]
        faltan = sorted(decl - real)
        sobran = sorted(real - decl)
        if sobran:
            rojos.append(
                f"A · {r} trae los horizontes {sorted(real)} y el glosario NO declara {sobran}"
            )
        if faltan:
            sin_datos_a.append(
                f"{r} · declarados y sin clave en este sobre: {faltan} (de {sorted(decl)})"
            )
    if vistos_a == 0:
        print(
            f"NO MEDIDO [{sujeto}]: brazo A sin ni un publicador que mirar "
            f"({len(sin_juzgar_a)} con el bloque mudo)"
        )
        for s in sin_juzgar_a:
            print(f"   sin juzgar · {s}")
        return 2
    mudo_txt = (
        f" · {len(sin_juzgar_a)} SIN JUZGAR por contenedor mudo: {'; '.join(sin_juzgar_a)}"
        if sin_juzgar_a else ""
    )
    sin_datos_txt = (
        " · horizontes declarados sin clave en este sobre (no condena): "
        + "; ".join(sin_datos_a)
        if sin_datos_a else ""
    )
    lineas.append(
        f"A declarado->existe: {vistos_a} de {len(rutas_pub)} publicadores"
        f"{mudo_txt}{sin_datos_txt}"
    )

    # --- B1 · EXISTE -> DECLARADO, POR NOMBRE
    vistos_b1 = 0
    for r, d in sorted(reales.items()):
        hoja = r.split(".")[-1].split("[")[0]
        if hoja not in hojas_declaradas or not d["marcos"]:
            continue
        vistos_b1 += 1
        if r not in rutas_pub and r not in rutas_nob:
            rojos.append(
                f"B1 · {r} publica '{hoja}' para los horizontes {sorted(d['marcos'])} y NO "
                f"esta en el glosario (ejemplo real: {d['ejemplo']})"
            )
    if vistos_b1 == 0:
        print(f"NO MEDIDO [{sujeto}]: brazo B1 no encontro ni una hoja con nombre declarado")
        return 2
    lineas.append(f"B1 por nombre: {vistos_b1} rutas con horizonte miradas")

    # --- B2 · EXISTE -> DECLARADO, POR VALOR
    vistos_b2 = 0
    b2_rojos = []
    for r, d in sorted(reales.items()):
        if not d["marcos"]:
            continue
        clase = None
        for v in d["valores"]:
            if isinstance(v, str) and v in ESTRUCTURA:
                clase = "estructura"
                break
            if isinstance(v, str) and v in DIRECCION:
                clase = "sesgo"
                break
        if not clase:
            continue
        vistos_b2 += 1
        if r not in rutas_pub and r not in rutas_nob:
            b2_rojos.append(
                f"B2 · {r} lleva un valor de {clase} ({d['valores'][0]}) para los "
                f"horizontes {sorted(d['marcos'])} y NO esta en el glosario"
            )
    rojos.extend(b2_rojos)
    if vistos_b2 == 0:
        lineas.append(
            "B2 por valor: NO MEDIDO · este sobre no trae ni un valor de sesgo ni de "
            "estructura (sobre de forma, sin datos). El brazo que caza un NOMBRE NUEVO no "
            "se ejercito en este sujeto"
        )
    else:
        lineas.append(f"B2 por valor: {vistos_b2} rutas con valor miradas")

    # --- C · LOS VECINOS
    vistos_c = 0
    for r, p in sorted(rutas_pub.items()):
        tipo = p.get("publishes")
        vecinos = {canon_declarado(k) for k in (p.get("may_disagree_with") or {})}
        debidos = {q for q, o in rutas_pub.items() if o.get("publishes") == tipo and q != r}
        for v in sorted(vecinos):
            vistos_c += 1
            if v not in rutas_pub:
                rojos.append(f"C · {r} dice diferenciarse de {v}, que no es un publicador")
        faltan = sorted(debidos - vecinos)
        if faltan:
            rojos.append(
                f"C · {r} publica un '{tipo}' y NO dice nada de {faltan}, que publica(n) lo mismo"
            )
    if vistos_c == 0:
        print(f"NO MEDIDO [{sujeto}]: brazo C sin ni una referencia cruzada que seguir")
        return 2
    lineas.append(f"C vecinos: {vistos_c} referencias cruzadas seguidas")

    # --- D · EL PROMPT
    prompt = sobre.get("interpretation_prompt") or ""
    if not prompt:
        lineas.append("D prompt: NO MEDIDO · este sobre no lleva interpretation_prompt")
    else:
        n_sobres = 1 + len(extras)
        fallos, ok, sin_juzgar = brazo_prompt(prompt, [sobre, *extras])
        if not ok:
            lineas.append(
                f"D prompt: NO MEDIDO · ni una cita del prompt resolvio contra "
                f"{n_sobres} sobre(s); el inventario no da para juzgar"
            )
        else:
            sj = (
                f" · {len(sin_juzgar)} SIN JUZGAR: {'; '.join(sin_juzgar)}"
                if sin_juzgar else ""
            )
            lineas.append(f"D prompt: {len(ok)} citas resueltas contra {n_sobres} sobre(s){sj}")
            for f in fallos:
                rojos.append(f"D · {f}")
        g_fallos, g_juzgadas = brazo_grupos(prompt, [sobre, *extras])
        if g_juzgadas == 0:
            lineas.append(
                "D2 grupos: NO MEDIDO · ni una frase del prompt nombra un bloque con grupos"
            )
        else:
            lineas.append(f"D2 grupos: {g_juzgadas} frases juzgadas")
            for f in g_fallos:
                rojos.append(f"D2 · {f}")
        agregados = [
            canon_declarado(e.get("path")) for e in swt
            if "." in str(e.get("path", "")) and str(e.get("path")).split(".")[0] in sobre
        ]
        f_fallos, f_juzgados = brazo_agregados(prompt, sobre, agregados)
        if f_juzgados == 0:
            lineas.append(
                f"F agregados: NO MEDIDO · el prompt no cita ninguno de los {len(agregados)} "
                "agregados que el glosario declara"
            )
        else:
            lineas.append(
                f"F agregados: {f_juzgados} cita(s) de agregado juzgadas sobre "
                f"{len(agregados)} declarados"
            )
            for f in f_fallos:
                rojos.append(f"F · {f}")

    # --- E · EL VOCABULARIO · lo que el glosario dice que un campo PUEDE valer, contra lo
    # que vale donde hay dato.
    #
    # ESTE BRAZO NACIO DE UN AGUJERO MEDIDO: hasta el 2026-09-19 el glosario declaraba
    # vocabularios y NADIE los contrastaba, asi que K101 daba VERDE con
    # divergences.intraday.windows.<h>.divergence declarando alcista/bajista/null mientras
    # el campo valia 'sin_divergencia' en 18 de los 21 valores presentes.
    #
    # SOLO MIRA LOS CAMPOS QUE DECLARAN `values`. Un `values: null` significa «no
    # declarado» y se NOMBRA sin juzgar: inventar una lista para poder condenar seria peor
    # que el hueco.
    #
    # UN VOCABULARIO PUEDE SER UNA PLANTILLA, y saltarselas no vale. `divergences.summary`
    # vale cosas como 'bajista_en_2_ventanas': si la plantilla se ignora, ese valor sale
    # «fuera de vocabulario» y el brazo condena una declaracion CORRECTA -me paso al
    # escribirlo, el 2026-09-19, y lo cazo el control con los datos de produccion-. Se
    # traduce a una expresion: `<a|b>` es una alternativa y `N` o `M` es un entero.
    def a_patron(v):
        if not isinstance(v, str) or ("<" not in v and "N" not in v and "M" not in v):
            return None
        trozos = []
        for t in v.split("_"):
            if t.startswith("<") and t.endswith(">"):
                alt = "|".join(re.escape(x) for x in t[1:-1].split("|"))
                trozos.append(f"(?:{alt})")
            elif t in ("N", "M"):
                trozos.append(r"\d+")
            else:
                trozos.append(re.escape(t))
        patron = "_".join(trozos)
        return re.compile(f"^{patron}$") if patron != re.escape(v) else None

    # SE CUENTAN DOS DENOMINADORES Y NO UNO. «57 valores contrastados» suena a mucho y
    # puede ser 57 nulls: en el sobre seco del arbol lo es casi entero. El que dice si el
    # brazo se ejercito de verdad es el de los valores NO NULOS (A35).
    vocab_mirados, vocab_no_nulos = 0, 0
    vocab_sin_declarar, vocab_sin_dato, vocab_patrones = [], [], 0
    for entrada in [*pubs, *nob, *swt]:
        r = canon_declarado(entrada.get("path"))
        vals = entrada.get("values")
        if vals is None:
            if "values" in entrada or r in reales:
                vocab_sin_declarar.append(r)
            continue
        patrones = [p for p in (a_patron(v) for v in vals) if p]
        vocab_patrones += len(patrones)
        declarados = {
            json.dumps(v, ensure_ascii=False) for v in vals if a_patron(v) is None
        }
        d = reales.get(r)
        if not d:
            vocab_sin_dato.append(f"{r} (no hay ni un valor en este sobre)")
            continue
        fuera = {}
        for v in d["valores"]:
            vocab_mirados += 1
            if v is not None:
                vocab_no_nulos += 1
            j = json.dumps(v, ensure_ascii=False)
            if j in declarados:
                continue
            if isinstance(v, str) and any(p.match(v) for p in patrones):
                continue
            fuera[j] = fuera.get(j, 0) + 1
        if fuera:
            detalle = ", ".join(f"{k} x{n}" for k, n in sorted(fuera.items()))
            rojos.append(
                f"E · {r} vale {detalle} y su vocabulario declarado es "
                f"{sorted(str(v) for v in vals)} (sobre {len(d['valores'])} valores en este sobre)"
            )
    if vocab_no_nulos == 0:
        lineas.append(
            f"E vocabulario: NO MEDIDO · {vocab_mirados} valores mirados y NINGUNO no nulo, "
            "asi que este brazo no se ejercito en este sujeto. "
            + (f"Sin dato: {'; '.join(vocab_sin_dato)}" if vocab_sin_dato else "")
        )
    else:
        extra = []
        if vocab_sin_dato:
            extra.append(f"{len(vocab_sin_dato)} sin dato ({'; '.join(vocab_sin_dato)})")
        if vocab_sin_declarar:
            extra.append(
                f"{len(vocab_sin_declarar)} con el vocabulario SIN DECLARAR y no juzgados "
                f"({', '.join(sorted(vocab_sin_declarar))})"
            )
        if vocab_patrones:
            extra.append(f"{vocab_patrones} vocabulario(s) declarado(s) como plantilla")
        lineas.append(
            f"E vocabulario: {vocab_mirados} valores contrastados, {vocab_no_nulos} de ellos "
            f"NO NULOS" + (" · " + " · ".join(extra) if extra else "")
        )

    # --- G · LAS INVARIANTES DECLARADAS SE COMPRUEBAN CON LOS VALORES.
    #
    # Cuando el glosario dice de un vecino «NO discrepa», esta haciendo una PROMESA sobre
    # los datos, no un comentario. Este brazo la cobra: empareja los dos caminos horizonte
    # a horizonte y condena si difieren.
    #
    # EL DEFECTO QUE LO TRAJO: hasta el 2026-09-19 el glosario decia que
    # structure_horizons.<h>.structure era «una copia literal, sin recalcular nada» de
    # structure_detail.horizons.<h>.state y que «si algun dia difieren, uno de los dos esta
    # roto». No es verdad: horizon_structure vuelve a llamar a structure_detail SIN as_of,
    # con su propio clock_timestamp(), asi que pueden diferir sin que nada este roto. La
    # medida estaba en la §7 de la entrega del dia anterior y la invariante se publico
    # igual. Ahora esa promesa, si se escribe, se paga.
    invariantes, g_mirados = 0, 0
    for r, p in sorted(rutas_pub.items()):
        for vecino, texto in (p.get("may_disagree_with") or {}).items():
            if not str(texto).strip().upper().startswith("NO DISCREPA"):
                continue
            invariantes += 1
            v = canon_declarado(vecino)
            a, b = reales.get(r), reales.get(v)
            if not a or not b:
                continue
            comunes = sorted(set(a["por_marco"]) & set(b["por_marco"]))
            for marco in comunes:
                g_mirados += 1
                va, vb = a["por_marco"][marco], b["por_marco"][marco]
                if va != vb:
                    rojos.append(
                        f"G · el glosario promete que {r} NO discrepa de {v}, y en {marco} "
                        f"vale {va} contra {vb}"
                    )
    if invariantes == 0:
        lineas.append("G invariantes: ninguna. El glosario no promete que dos caminos coincidan")
    elif g_mirados == 0:
        lineas.append(
            f"G invariantes: NO MEDIDO · {invariantes} promesa(s) de coincidencia y ningun "
            "horizonte comun con dato para cobrarlas"
        )
    else:
        lineas.append(
            f"G invariantes: {invariantes} promesa(s) de coincidencia, {g_mirados} "
            "horizonte(s) comparados"
        )

    if rojos:
        print(f"ROJO [{sujeto}]: {len(rojos)} defecto(s) · {rojos[0]}")
        for r in rojos:
            print(f"   {r}")
        print("   --- lo que si se miro ---")
        for lin in lineas:
            print(f"   {lin}")
        return 1
    print(
        f"VERDE [{sujeto}]: los {len(rutas_pub)} publicadores de sesgo/estructura por "
        f"horizonte del sobre se declaran y se nombran entre si"
    )
    for lin in lineas:
        print(f"   {lin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
