"""LA VIDA DE CADA POSICION (remates 6 y 7 de BOT-2). Pura: sin base, sin red y sin reloj propio. El bot le da lo que lee
(cada lectura de position/list y cada fila nueva de closed-pnl) y ella reconstruye, para cada symbol:side, sus vidas:
cual es nueva (se evalua una vez), cual cerro y con que filas (se puntua) y cual no se puede separar con certeza (se deja
«ambigua» y NO se puntua). La comprueba tests/simulador_bot.py contra la verdad, dentro y FUERA de estos supuestos.

LO QUE SE SUPONE (declarado; fuera de el, el simulador mide que sale ambigua o sin puntuar, no una cifra falsa):
 S1 una fila de closed-pnl paso entre b = min(createdTime, updatedTime) - MARGEN_FILA_MS y h = max(los dos) + MARGEN_FILA_MS
    (10 s: un desfase de hasta 8 s en los dos sentidos entre closed-pnl y position/list, y una orden de varias ejecuciones,
    que es UNA fila: createdTime la primera, updatedTime la ultima). Una lectura de position/list ensena lo que paso hasta
    B = max(su updatedTime, su hora local - DESFASE_MS): el updatedTime puede no moverse con un parcial o un anadido (y si
    con el funding), y el reloj de 140 va hasta 10 s del de Bybit. La fila con h <= B va antes de esa lectura; la que esta
    A CABALLO (b <= B < h) va al lado que no deja un tramo IMPOSIBLE (una lectura que ensena menos de lo que dejan las
    filas) y, si los dos son posibles, al de su hora cruda min(createdTime, updatedTime) contra el updatedTime de esa
    lectura (dentro de S1 es exacta: la ejecucion que deja lo que ensena la lectura tiene su misma hora). El validador midio que
    una sola regla de hora no vale: closed-pnl 1 ms detras del updatedTime daba cifras falsas, y adelantarla 10 s las daba
    al reves (un cierre de justo despues de una lectura, contado de antes).
 S2 closed-pnl trae cada cierre como mucho ESPERA_MS (35 min) despues. Por eso una vida se puntua pasados 35 min de su
    primera lectura, de cada lectura tras un tramo con anadidos y, si desaparecio, de su primera ausencia. Una fila mas
    tardia que eso puede faltar en una cifra ya emitida (el unico camino a una cifra falsa que queda; el simulador lo mide).
 S3 una lista vacia NO es un cierre: una vida solo cierra cuando sus filas cubren lo que tenia; ausente y sin filas, se
    queda ausente (nada pagado) y, si vuelve igual, es la misma; sin filas en SIN_FILAS_MS (2 h), «sin puntuar». Dos o mas
    lecturas SEGUIDAS sin la clave (VACIAS_SEGUIDAS) sirven para separar la vida siguiente si las filas cubren la de antes, y
    sin ninguna vida abierta, para que lo cerrado antes de la penultima sea de vidas que el bot no vio («limpia»): un cierre
    a otra entrada de antes de «limpia» ya no hace ambigua a la siguiente (A2 evitable); uno a SU entrada, si (puede ser un
    parcial suyo durante unas vacias falsas).
 S4 una entrada media IGUAL (TOL_E = 1e-9: solo el ruido de la coma flotante) es una vida sin anadidos: position/list y
    closed-pnl dan la entrada con todos sus decimales, y un anadido -tambien a un tick de la media- la mueve. Con 0.05 pb
    (R6) un anadido a un tick (0.045 pb en BTC) no se veia: un parcial del mismo tamano cubria justo y salia «cerrada y
    reabierta». Si Bybit redondeara distinto en las dos rutas, cada parcial pareceria un anadido sin ver: ambigua, nunca una
    cifra (lo mide bot_crudo). Lo que S4 no ve -una reapertura a la MISMA entrada; una orden de varias ejecuciones a caballo
    de una lectura- no parte la vida: sigue con el mismo id y sale A6; tambien si tras las filas que la cubren hay MAS a su
    entrada, o si tras un anadido sin ver cierran mas de lo que quedaba a la entrada que se ve despues.
CUANDO SALE AMBIGUA (y ninguna otra vez; el simulador comprueba la verdad de cada una):
 A1 entre dos lecturas hubo un anadido que el bot no vio (una fila a otra entrada, o mas cerrado que lo visto) seguido de
    cierres, y no se puede saber si llego a 0: la lectura siguiente ensena otra entrada, o los cierres tienen mas de una.
 A2 antes de la primera lectura de una vida nueva hubo cierres a OTRA entrada que la suya, despues de la ultima fila segura
    de la anterior y de «limpia» (sin registro, en cualquier momento): un anadido suyo, una vida entera que el bot no vio,
    o la anterior tras un anadido sin ver; o cierres a SU entrada de antes de «limpia». Es nueva (se evalua) pero no se
    puntua.
 A3 una fila sin lado (no se movio mas que la comision) cuando a su hora las dos direcciones del simbolo tenian vida y su
    entrada no casa con exactamente una de las dos.
 A4 el bot no leyo esa posicion en mas de 7 dias (lo que devuelve closed-pnl).
 A5 un registro anterior (otro bot, otro estado) separa la vida en una lectura sin una fila que la cierre.
 A6 sus filas la cierran a la misma entrada a la que se la ve despues (S4 roto: reapertura a la misma entrada, orden de
    varias ejecuciones), o tras un anadido sin ver cierran mas de lo que quedaba a la entrada que se ve despues: no se sabe
    si es la misma o una nueva; sigue con el mismo id.
 A7 desaparecio sin filas que la cierren y volvio distinta: un anadido mientras no se veia, o un cierre y otra con sus
    filas aun por llegar; sigue con el mismo id.
 X  (no deberia pasar dentro de S1-S4) una fila sin duda entre dos lecturas que ensenaban el mismo tamano y la misma entrada.
SIN PUNTUAR (no ambigua): desaparecio y closed-pnl no trajo en SIN_FILAS lo que cubre su tamano, o una lectura ensena menos
de lo que dicen sus filas y en ESPERA no llega lo que falta. Una vida ya ambigua cuyas filas cubren lo que se le vio abrir
cierra (ambigua) cuando desaparece, sin esperar las 2 h.
LA EVALUACION de una vida nueva se hace con su ultima lectura que es SUYA sin duda (su primera, o una enganchada por un
tramo que se pudo comprobar): nunca con otra vida pegada a ella.
"""

from __future__ import annotations

import bisect

from app.bot.bybit import lado_cierre

TOL_E = 1e-9  # dos entradas medias «iguales»: el ruido de la coma flotante (S4)
TOL_Q = 1e-6  # relativa: dos tamanos iguales
ESPERA_MS = 35 * 60_000  # S2
SIN_FILAS_MS = 2 * 3600_000  # S3: ausente sin filas que la cubran -> sin puntuar
MARGEN_FILA_MS = 10_000  # S1
DESFASE_MS = 10_000  # el reloj de 140 contra el de Bybit, para «vacia desde» (lecturas sin la clave)
HORIZONTE_MS = 7 * 86400_000
SEGUIDA_MS = 90_000  # dos lecturas «seguidas»: el bot lee cada minuto
VACIAS_SEGUIDAS = 2
INF = float("inf")
A3 = "A3: una fila sin lado en cobertura que no casa con la entrada de una sola de las dos"
A6 = "A6: sus filas la cierran a la misma entrada a la que se la ve despues: no se sabe si es la misma o una nueva"
A7 = "A7: desaparecio sin filas que la cierren y volvio distinta"


def hora_fila(creada, actualizada, tarde: bool = False) -> int | None:
    """Desde cuando pudo pasar una fila de closed-pnl (S1): la primera de sus dos horas menos el margen; con tarde, hasta
    cuando: la ultima mas el margen."""
    hs = []
    for x in (creada, actualizada):
        try:
            if x not in (None, "") and int(x) > 0:
                hs.append(int(x))
        except (TypeError, ValueError):
            continue
    if not hs:
        return None
    return max(hs) + MARGEN_FILA_MS if tarde else min(hs) - MARGEN_FILA_MS


def mismo(a, b) -> bool:
    return bool(a) and bool(b) and abs(a / b - 1) <= TOL_E


def _entradas(filas: list) -> list:
    """Las entradas distintas (+-TOL_E) de unas filas, en orden."""
    out: list = []
    for f in filas:
        if not any(mismo(f["e"], e) for e in out):
            out.append(f["e"])
    return out


def _antes(f: dict, limpia) -> bool:
    return limpia is not None and f["b"] <= limpia


def _suma(filas: list) -> float:
    return sum(f["q"] or 0 for f in filas)


def _sin_tamano(viejo: list, resto: list, post: tuple | None, tam: float) -> dict:
    """Desde la primera fila que delata un anadido sin ver (otra entrada, o mas cerrado que lo visto) el tamano no se sabe:
    cualquier cierre pudo dejarla a 0. Es la misma vida sin duda solo si esos cierres son de UNA entrada, la lectura
    siguiente ensena esa misma entrada y no suman mas de lo que quedaba (tam) antes del anadido: si suman mas, pudo cerrar
    entera y reabrirse a la misma entrada (S4 roto: A6). Si no, A1."""
    hasta = viejo[-1]["b"] if viejo else None  # la ultima fila segura de la vida (antes del anadido sin ver)
    viejo = viejo + resto
    es = _entradas(resto)
    if post is not None and len(es) == 1 and mismo(post[1], es[0]):
        if _suma(resto) > tam * (1 + TOL_Q) + 1e-12:
            return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True, "hasta": hasta,
                    "amb": "A6: tras un anadido sin ver cierran mas de lo que quedaba, a la entrada que se ve despues: siguio o se"
                           " reabrio a la misma entrada"}
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True}
    if post is None:
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sin_tamano": True, "hasta": hasta,
                "amb": None if len(es) == 1 else "A1: un anadido sin ver y despues cierres a mas de una entrada"}
    return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True, "hasta": hasta,
            "amb": "A1: un anadido sin ver y despues cierres entre dos lecturas: no se sabe si llego a 0 y se reabrio"}


def tramo(pre: tuple, filas: list, post: tuple | None, vacias: int = 0) -> dict:
    """Lo que paso entre dos lecturas de un symbol:side. pre = (tamano, entrada) de la de antes; post = la de despues, o
    None si la clave ya no esta (cola); vacias = las lecturas SEGUIDAS sin la clave entre las dos. filas: las de su lado
    entre las dos, en orden. -> viejo (filas de la vida de antes), fin (la fila que la deja a 0, o None), nuevo (filas de la
    siguiente antes de su primera lectura), amb / amb_nuevo, cuadra (los tamanos lo confirman), falta (la lectura ensena
    menos de lo que dicen las filas: faltan filas), hasta (la ultima fila segura de la de antes)."""
    tam, ent = pre
    viejo: list = []
    for j, f in enumerate(filas):
        if mismo(f["e"], ent):
            viejo.append(f)
            tam -= f["q"]
            if tam < -pre[0] * TOL_Q:  # cierran MAS de lo que se veia: hubo un anadido sin ver (que casi no movio la media)
                viejo.pop()
                return _con_vacias(_sin_tamano(viejo, filas[j:], post, tam + f["q"]), pre, filas, post, vacias)
            if tam <= pre[0] * TOL_Q:
                resto = filas[j + 1:]
                igual = [g for g in resto if mismo(g["e"], ent)]  # mas cierres a SU entrada: siguio (S4 roto) o una igual
                if post is None:  # lo de despues: vidas enteras que el bot no vio
                    if igual:
                        return {"viejo": viejo + igual, "fin": igual[-1], "nuevo": [], "cuadra": False, "amb": A6}
                    return {"viejo": viejo, "fin": f, "nuevo": [], "cuadra": True}
                if mismo(post[1], ent):  # «reabierta» a la misma entrada: S4 roto; no se parte (A6)
                    return {"viejo": viejo + resto, "fin": None, "nuevo": [], "cuadra": False, "sigue": True, "amb": A6,
                            "hasta": f["b"]}
                otras = [g for g in resto if not mismo(g["e"], post[1]) and not mismo(g["e"], ent)]
                a2 = (f"A2: antes de verla hubo {len(otras)} cierre(s) a otra entrada (un anadido suyo o una vida entera que el"
                      f" bot no vio)") if otras else None
                nuevo = [g for g in resto if mismo(g["e"], post[1])]
                if igual:
                    return {"viejo": viejo + igual, "fin": igual[-1], "nuevo": nuevo, "cuadra": False, "amb": A6, "amb_nuevo": a2}
                return {"viejo": viejo, "fin": f, "nuevo": nuevo, "cuadra": True, "amb_nuevo": a2}
        else:  # una fila a otra entrada: hubo un anadido que el bot no vio; desde aqui el tamano no se sabe
            return _con_vacias(_sin_tamano(viejo, filas[j:], post, tam), pre, filas, post, vacias)
    if post is None:
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False}
    if mismo(post[1], ent):
        if abs(post[0] - tam) <= pre[0] * TOL_Q:
            return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": True, "sigue": True}
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True, "falta": post[0] < tam}
    if vacias >= VACIAS_SEGUIDAS:  # se fue sin filas que la cierren y volvio distinta: no se parte (A7)
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True, "amb": A7}
    # anadidos despues de esos cierres: subirian el tamano; si ensena MENOS de lo que dejan las filas, faltan filas
    return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True, "falta": post[0] < tam - pre[0] * TOL_Q}


def _con_vacias(t: dict, pre: tuple, filas: list, post: tuple | None, vacias: int) -> dict:
    """Con dos o mas lecturas SEGUIDAS sin la clave entre medias (S3) y filas que cubren lo que tenia, la de antes cerro y
    la que vuelve es otra: las filas de la entrada de la que vuelve son suyas (parciales antes de verla) y el resto, si es de
    una sola entrada, de la de antes; si es de mas de una, no se puede repartir (A1 la de antes, A2 la que vuelve)."""
    if post is None or vacias < VACIAS_SEGUIDAS or not t.get("amb") or _suma(filas) < pre[0] * (1 - TOL_Q):
        return t
    nuevo = [g for g in filas if mismo(g["e"], post[1])]
    resto = [g for g in filas if not mismo(g["e"], post[1])]
    if not resto:
        return t
    if len(_entradas([g for g in resto if not mismo(g["e"], pre[1])])) <= 1:
        return {"viejo": resto, "fin": resto[-1], "nuevo": nuevo, "cuadra": False}
    return {"viejo": resto, "fin": None, "nuevo": nuevo, "cuadra": False, "hasta": t.get("hasta"), "termina": True,
            "amb": "A1: un anadido sin ver y despues cierres a mas de una entrada mientras no estaba en las lecturas",
            "amb_nuevo": "A2: antes de verla hubo cierres a mas de una entrada que no se pueden repartir"}


class Libro:
    """Las vidas de todas las posiciones. Estado serializable (estado()/desde()): por symbol:side, sus lecturas desde la
    ultima vida ya puntuada -cada tramo de lecturas seguidas con el mismo tamano y entrada: [primera, ultima, tamano,
    entrada, updatedTime primero, updatedTime ultimo, id, lecturas vacias seguidas justo antes]-, «vacia» (hora de Bybit
    hasta la que todo es de vidas ya puntuadas), «limpia» (S3: hasta la que lo cerrado es de vidas que el bot no vio),
    «ausente» ([primera, ultima, cuantas] lecturas seguidas sin ella) y «pasadas» (el tramo y las entradas de cada vida ya
    puntuada, 8 dias: deciden el lado de una fila sin lado)."""

    def __init__(self):
        self.claves: dict = {}
        self.filas: dict = {}  # symbol -> filas en orden de hora (S1)
        self.horas: dict = {}  # symbol -> sus horas, en el mismo orden (para buscar por biseccion)
        self.ordenes: dict = {}  # orden -> su hora: las ya vistas (8 dias)
        self.nada_desde = None  # hora desde la que toda clave sin registro estaba vacia (dos lecturas sin ella)
        self.previas: list = []  # las dos ultimas lecturas (hora de 140)
        self.ultima = None

    # ---------------------------------------------------------------- lo que entra
    def fila(self, f: dict):
        """Una fila de closed-pnl: orden, symbol, b y h (hora_fila: desde y hasta cuando pudo pasar), q (closedSize),
        e (avgEntryPrice), x (avgExitPrice), pnl. Se inserta en su sitio (sin reordenar todo)."""
        if f["orden"] in self.ordenes or None in (f.get("b"), f.get("q"), f.get("e")):
            return
        if not isinstance(f.get("h"), (int, float)):
            f = f | {"h": f["b"] + 2 * MARGEN_FILA_MS}
        self.ordenes[f["orden"]] = f["b"]
        lista, horas = self.filas.setdefault(f["symbol"], []), self.horas.setdefault(f["symbol"], [])
        i = bisect.bisect_right(horas, f["b"])
        horas.insert(i, f["b"])
        lista.insert(i, f)

    def lee(self, ahora: int, posiciones: list):
        """Una lectura de position/list (bybit.posiciones): las que se ven y, por omision, las que no."""
        vistas = {p["clave"]: p for p in posiciones}
        for clave, p in vistas.items():
            k = self.claves.get(clave)
            if k is None:
                k = self.claves[clave] = {"runs": [], "vacia": None, "limpia": self.nada_desde, "ausente": None, "pasadas": []}
            u = p.get("actualizada") or ahora
            r = k["runs"][-1] if k["runs"] else None
            au = k["ausente"]
            vacias = au[2] if au else 0
            if r and r[2] == p["cantidad"] and r[3] == p["entrada"] and not vacias:
                r[1], r[5] = ahora, max(r[5], u)
            else:
                k["runs"].append([ahora, ahora, p["cantidad"], p["entrada"], u, u, None, [au[0], vacias] if au else None])
            k["ausente"] = None
        for clave, k in self.claves.items():
            if clave in vistas:
                continue
            au = k["ausente"]
            seguida = au and ahora - au[1] <= SEGUIDA_MS  # la anterior sin ella fue la de hace un minuto (no antes de una caida)
            k["ausente"] = [au[0], ahora, au[2] + 1] if seguida else [ahora, ahora, 1]
            if not k["runs"] and seguida:  # sin vida abierta y dos vacias seguidas: lo de antes de la penultima, de otras
                k["limpia"] = max(k.get("limpia") or -INF, au[1] - DESFASE_MS)
        self.previas = (self.previas + [ahora])[-2:]
        if len(self.previas) == 2:
            self.nada_desde = self.previas[0] - DESFASE_MS
        self.ultima = ahora

    # ---------------------------------------------------------------- lo que sale
    def decide(self, ahora: int) -> dict:
        """-> presentes {id: clave} (las vidas que la ULTIMA lectura ensena), firmes {id: su ultima lectura que es suya sin
        duda} (con ella se evalua), notas {id: texto}, resultados [(id, {pnl, ordenes, nota, tramos})] de las vidas cerradas y
        ya seguras (cada una una sola vez; pnl None = sin puntuar) y suspensas {clave: error}: una excepcion en una clave la
        deja en suspenso (nada se paga sobre ella) sin tocar a las demas (remate 7)."""
        out: dict = {"presentes": {}, "notas": {}, "resultados": [], "firmes": {}, "suspensas": {}}
        for clave, k in self.claves.items():
            if not k["runs"]:
                continue
            try:
                self._decide_clave(clave, k, ahora, out)
            except Exception as e:  # noqa: BLE001 - la identidad no tumba la seguridad ni a las demas claves
                out["suspensas"][clave] = f"{type(e).__name__}: {str(e)[:120]}"
        self._poda(ahora)
        return out

    def _decide_clave(self, clave: str, k: dict, ahora: int, out: dict):
        vidas = self._vidas(clave, k, ahora)
        for v in vidas:
            for i in v["runs"]:
                k["runs"][i][6] = v["id"]
            if v.get("nota"):
                out["notas"][v["id"]] = v["nota"]
        ultima = vidas[-1]
        if k["ausente"] is None and k["runs"][-1][1] == self.ultima and ultima["fin"] is None:
            out["presentes"][ultima["id"]] = clave
            fr = ultima["firme_run"] if ultima["firme_run"] is not None else ultima["runs"][0]
            r = k["runs"][fr]  # su ultima lectura segura: con ella se evalua
            out["firmes"][ultima["id"]] = {"cantidad": r[2], "entrada": r[3], "actualizada": r[5], "visto": r[1],
                                           "actual": fr == len(k["runs"]) - 1, "desde": k["runs"][ultima["runs"][0]][0]}
        hechas = 0
        for v in vidas:  # las cerradas y seguras, en orden; cada una sale una vez y el registro avanza tras ella
            if v["fin"] is None or ahora < v["espera"] + ESPERA_MS:
                break
            out["resultados"].append((v["id"], self._resultado(v) | {"tramos": len(v["runs"])}))
            hechas = max(v["runs"]) + 1
            fin = max([v["fin"], k["runs"][max(v["runs"])][5]] + [f["b"] for f in v["filas"] if not v.get("amb")])
            k["pasadas"] = [p for p in k.get("pasadas", []) if p[1] > fin - HORIZONTE_MS - 86400_000] + \
                [[k["vacia"] if k["vacia"] is not None else k["runs"][min(v["runs"])][4] - 1, fin,
                  [k["runs"][i][3] for i in v["runs"]]]]
            k["vacia"] = v["fin"] if v.get("amb") else fin
        if hechas:
            del k["runs"][:hechas]
            if not k["runs"]:
                k["ausente"] = None

    def abiertas(self) -> bool:
        return any(k["runs"] for k in self.claves.values())

    def _poda(self, ahora: int):
        """Lo que ya no puede tocar ninguna vida abierta ni pendiente sale de la memoria (remate 7: sin cota, 207 ms por tic
        con 8000 filas)."""
        for sym in list(self.filas):
            limite = min([next((x for x in (k["vacia"], k.get("limpia")) if x is not None), -INF)
                          for c, k in self.claves.items() if c.split(":")[0] == sym] + [ahora - HORIZONTE_MS])
            if limite == -INF:  # una clave sin registro desde cuando estaba vacia: todo puede ser suyo
                continue
            i = bisect.bisect_left(self.horas[sym], limite - 86400_000)
            if i:
                del self.horas[sym][:i]
                del self.filas[sym][:i]
        viejas = [o for o, b in self.ordenes.items() if b < ahora - HORIZONTE_MS - 86400_000]
        for o in viejas:
            del self.ordenes[o]

    @staticmethod
    def _resultado(v: dict) -> dict:
        ordenes = [f["orden"] for f in v["filas"]]
        if v.get("amb"):
            return {"pnl": None, "ordenes": ordenes, "nota": f"ambigua: {v['amb']}"}
        if v.get("faltan"):
            return {"pnl": None, "ordenes": ordenes, "nota": "closed-pnl no trajo lo que cubre su tamano visto: sin puntuar"}
        if not v["filas"]:
            return {"pnl": None, "ordenes": [], "nota": "sin operaciones suyas en closed-pnl: sin puntuar"}
        return {"pnl": sum(f["pnl"] or 0 for f in v["filas"]), "ordenes": ordenes, "nota": v.get("nota")}

    @staticmethod
    def _viva(k: dict | None, b) -> list | None:
        """Las entradas de la vida de k que cubre la hora b, con su hora: las de la lectura de antes y de despues de b
        (abierta), o las de una ya puntuada cuyo tramo la contiene; None si ninguna la cubre (remate 7: antes juntaba todas)."""
        if not k:
            return None
        runs = k["runs"]
        if runs and (k["vacia"] is None or b > k["vacia"]):
            j = bisect.bisect_left([r[4] for r in runs], b)
            return [runs[x][3] for x in (j - 1, j) if 0 <= x < len(runs)]
        return next((p[2] for p in k.get("pasadas", []) if p[0] < b <= p[1]), None)

    def _filas_de(self, clave: str, k: dict) -> tuple[list, list]:
        """Las filas de ese symbol:side (desde su «vacia»), y las que no dicen su lado cuando a esa hora las dos direcciones
        tenian vida y su entrada no casa con exactamente una (A3). Cada lado es una clave aparte: la fila de un lado nunca
        acaba en el otro."""
        sym, lado = clave.split(":")[0], 1 if clave.endswith(":Buy") else -1
        otra = self.claves.get(f"{sym}:{'Sell' if lado > 0 else 'Buy'}")
        filas, horas = self.filas.get(sym, []), self.horas.get(sym, [])
        desde = bisect.bisect_right(horas, k["vacia"]) if k["vacia"] is not None else 0
        suyas, sin_lado = [], []
        for f in filas[desde:]:
            ld = lado_cierre(f["e"], f.get("x"), f["q"], f.get("pnl"))
            if ld == lado:
                suyas.append(f)
            elif ld is None:
                alli = self._viva(otra, f["b"])
                if alli is None:
                    suyas.append(f)
                    continue
                aqui = self._viva(k, f["b"]) or []
                en_esta, en_otra = any(mismo(f["e"], e) for e in aqui), any(mismo(f["e"], e) for e in alli)
                if en_esta and not en_otra:
                    suyas.append(f)
                elif en_esta == en_otra:
                    sin_lado.append(f)
        return suyas, sin_lado

    def _vidas(self, clave: str, k: dict, ahora: int) -> list:
        """Las vidas de un symbol:side desde su registro: lecturas + filas -> [{id, runs, filas, fin, espera, amb, nota}]."""
        filas, sin_lado = self._filas_de(clave, k)
        hs, hsl = [f["b"] for f in filas], [f["b"] for f in sin_lado]
        runs, limpia = k["runs"], k.get("limpia")

        def entre(xs: list, h: list, a, b) -> list:
            return xs[bisect.bisect_right(h, a) if a is not None else 0:bisect.bisect_right(h, b)]

        # S1: lo que ensena cada lectura llega hasta B; cada fila, al tramo de su b, y la que esta a caballo, donde cuadra
        B = [max(r[4], r[0] - DESFASE_MS) for r in runs]
        cortes = [k["vacia"], *B, INF]
        grupos = [entre(filas, hs, cortes[i], cortes[i + 1]) for i in range(len(runs) + 1)]
        for i in range(len(runs)):
            if any(f["h"] > B[i] for f in grupos[i]):
                grupos[i], grupos[i + 1] = self._reparte(k, i, grupos[i], grupos[i + 1], B[i])

        vidas: list = []
        v = None
        usados: set = set()

        def nueva(r: list, previas: list, amb, nacida, nota=None):
            rid = r[6] if r[6] and r[6] not in usados else None
            vid = rid or f"{clave}:{nacida + 1 if nacida is not None else r[4]}"
            usados.add(vid)
            return {"id": vid, "runs": [], "filas": list(previas), "fin": None, "espera": r[0], "amb": amb, "nota": nota,
                    "cadena": True, "firme_run": None}

        def cerrar(v: dict, fin):
            v["fin"] = fin
            vidas.append(v)

        for i, r in enumerate(runs):
            G, sl = grupos[i], entre(sin_lado, hsl, cortes[i], cortes[i + 1])
            vacias = (r[7] or [None, 0])[1]
            if cortes[i] is not None and r[4] - cortes[i] > HORIZONTE_MS and v is not None:
                v["amb"] = v["amb"] or "A4: mas de 7 dias sin leer esta posicion"
            if v is None:
                v = nueva(r, [f for f in G if mismo(f["e"], r[3]) and not _antes(f, limpia)], self._a2(G, r, limpia, k["vacia"]), None)
                if sl:
                    v["amb"] = v["amb"] or A3
            else:
                p = runs[i - 1]
                t = tramo((p[2], p[3]), G, (r[2], r[3]), vacias)
                v["filas"] += t["viejo"]
                if t.get("fin") or t.get("termina"):
                    fin = t["fin"]["b"] if t.get("fin") else max(x for x in (t.get("hasta"), p[5]) if x is not None)
                    if t.get("amb"):
                        v["amb"] = v["amb"] or t["amb"]
                    if any(f["b"] <= fin for f in sl):  # una fila sin lado ANTES de su cierre
                        v["amb"] = v["amb"] or A3
                    if vacias:
                        v["espera"] = max(v["espera"], r[7][0])  # sus filas pueden tardar ESPERA desde que dejo de verse
                    cerrar(v, fin)
                    v = nueva(r, t["nuevo"], t.get("amb_nuevo"), t["fin"]["b"] if t.get("fin") and not vacias else None,
                              nota=(f"cerrada la anterior y reabierta entre dos lecturas (closed-pnl, orden {t['fin']['orden']})"
                                    if t.get("fin") and not vacias else None))
                    if [f for f in sl if f["b"] > fin]:
                        v["amb"] = v["amb"] or A3
                elif r[6] and r[6] != v["id"] and r[6] not in usados:  # un registro anterior la separa aqui (A5)
                    v["amb"] = v["amb"] or "A5: un registro anterior la separa aqui sin una fila que la cierre"
                    cerrar(v, p[5])
                    v = nueva(r, [], "A5: un registro anterior la separa aqui sin una fila que la cierre", None)
                else:
                    if t.get("amb"):
                        v["amb"] = v["amb"] or t["amb"]
                        v["cadena"] = False  # la lectura que se ve puede ser otra vida: ni esta ni las de despues son suyas seguro
                    if not t["cuadra"]:
                        v["espera"] = max(v["espera"], r[0])
                        if ahora < r[0] + ESPERA_MS:  # enganchada sin filas que lo confirmen: lo sera pasado ESPERA
                            v["cadena"] = False
                    if t.get("falta") and ahora - r[0] >= ESPERA_MS:
                        v["faltan"] = True
                    if sl:
                        v["amb"] = v["amb"] or A3
            dentro = entre(filas, hs, r[0] + DESFASE_MS, r[1] - DESFASE_MS)
            if any(f["h"] < r[1] - DESFASE_MS for f in dentro):
                v["amb"] = v["amb"] or "X: una fila mientras el tamano y la entrada no cambiaban"
            v["runs"].append(i)
            if v["cadena"] or len(v["runs"]) == 1:  # su primera lectura siempre es suya (remate 7: nunca None)
                v["firme_run"] = i
        if v is None:
            return vidas
        if k["ausente"] is not None:  # la cola: la clave ya no esta en las lecturas
            r = runs[-1]
            t = tramo((r[2], r[3]), grupos[-1], None)
            v["filas"] += t["viejo"]
            if t.get("amb"):
                v["amb"] = v["amb"] or t["amb"]
            sl = entre(sin_lado, hsl, B[-1], t["fin"]["b"] if t.get("fin") else INF)  # despues de su cierre: de vidas que no vio
            if sl:
                v["amb"] = v["amb"] or A3
            cubre = t.get("fin") or (t.get("sin_tamano") and _suma(t["viejo"]) >= r[2] * (1 - TOL_Q))
            ambigua_cubierta = not cubre and v["amb"] and _suma(v["filas"]) >= self._abierto(runs, v["runs"]) * (1 - TOL_Q)
            if cubre or ambigua_cubierta:  # sus filas cubren lo que tenia: cerro (y se puntua pasada ESPERA desde que dejo de verse)
                v["espera"] = max(v["espera"], k["ausente"][0])
                if t.get("fin"):
                    v["fin"] = t["fin"]["b"]
                elif ambigua_cubierta or t.get("amb"):
                    v["fin"] = max(x for x in (t.get("hasta"), r[5], *(f["b"] for f in v["filas"])) if x is not None)
                else:
                    v["fin"] = max(f["b"] for f in t["viejo"])
            elif ahora - k["ausente"][0] >= SIN_FILAS_MS:  # S3: sin filas que la cubran en 2 h, sin puntuar
                v["fin"] = max([f["b"] for f in v["filas"]] + [r[5]]) if not t.get("amb") else \
                    max(x for x in (t.get("hasta"), r[5]) if x is not None)
                v["espera"] = min(v["espera"], k["ausente"][0])
                v["faltan"] = True
        vidas.append(v)
        return vidas

    @staticmethod
    def _abierto(runs: list, mios: list) -> float:
        """Lo que se le vio abrir a una vida: su primer tamano mas cada subida entre dos lecturas suyas (una cota baja)."""
        out = runs[mios[0]][2]
        for a, b in zip(mios, mios[1:], strict=False):
            out += max(0.0, runs[b][2] - runs[a][2])
        return out

    @staticmethod
    def _a2(G: list, r: list, limpia, vacia) -> str | None:
        """Lo que hace ambigua a la primera vida del registro (A2): cierres a otra entrada despues de «limpia», o a la suya
        de antes (un parcial suyo durante unas vacias falsas, o una vida igual que el bot no vio)."""
        otras = [f for f in G if not mismo(f["e"], r[3]) and not _antes(f, limpia)]
        if otras:
            return (f"A2: antes de verla hubo {len(otras)} cierre(s) a otra entrada"
                    + (" (el bot no tenia registro de esta clave)" if vacia is None and limpia is None else ""))
        if any(mismo(f["e"], r[3]) and _antes(f, limpia) for f in G):
            return "A2: antes de las lecturas sin la clave hubo cierres a su misma entrada"
        return None

    def _reparte(self, k: dict, i: int, G: list, siguiente: list, b: float) -> tuple[list, list]:
        """S1: las filas a caballo de la lectura i (b <= B < h), antes o despues de ella. Solo cuenta lo IMPOSIBLE: un tramo al
        que le faltan filas (ensena menos de lo que dejan). Dos historias posibles (cerrar y reabrir, o un anadido sin ver)
        no se desempatan por cual cuadra mejor sino por la hora cruda de la fila, min(createdTime, updatedTime), contra el
        updatedTime de la lectura.
        -> (las de antes de i, las de despues con las que ya iban despues)."""
        runs = k["runs"]
        r = runs[i]

        def faltas(antes: list, despues: list) -> int:
            n = 0
            if i > 0:
                p = runs[i - 1]
                n += bool(tramo((p[2], p[3]), antes, (r[2], r[3]), (r[7] or [None, 0])[1]).get("falta"))
            if i + 1 < len(runs):
                s = runs[i + 1]
                n += bool(tramo((r[2], r[3]), despues, (s[2], s[3]), (s[7] or [None, 0])[1]).get("falta"))
            return n

        def parte(quedan: list) -> tuple[list, list]:
            ids = {id(f) for f in quedan}
            return [f for f in G if id(f) in ids], [f for f in G if id(f) not in ids] + siguiente

        cruda = parte([f for f in G if f["h"] <= b or f["b"] + MARGEN_FILA_MS <= r[4]])
        opciones = [cruda, (G, siguiente), parte([f for f in G if f["h"] <= b])]
        return min(opciones, key=lambda o: faltas(*o))  # (con empate, la primera: la hora cruda)

    # ---------------------------------------------------------------- persistencia
    def estado(self) -> dict:
        return {"v": 7, "claves": self.claves, "nada_desde": self.nada_desde, "previas": self.previas}

    @classmethod
    def desde(cls, guardado, evaluadas: dict, filas: list, usadas=()) -> tuple[Libro, list]:
        """El libro del ultimo estado publicado, con lectura TOLERANTE (lo que no se entiende se descarta y se dice), mas lo
        visto al evaluar cada vida sin cierre (bot_evaluacion: un veredicto posterior al ultimo latido es una lectura mas,
        con su id) y las filas de bot_operacion, salvo las de un cierre ya apuntado (usadas). De un estado de R4/R5 («vidas»
        y «cerradas»): cada vida con sus lecturas y sin «vacia»; las cerradas sin puntuar, como ausentes desde su cierre.
        -> (libro, avisos)."""
        lib, avisos = cls(), []
        g = guardado if isinstance(guardado, dict) else {}
        if guardado is not None and not isinstance(guardado, dict):
            avisos.append(f"descarto el estado guardado: no es un objeto ({type(guardado).__name__})")
        libro = g.get("libro")
        cerradas_r5: dict = {}
        if isinstance(libro, dict):
            for clave, k in (libro.get("claves") or {}).items() if isinstance(libro.get("claves"), dict) else []:
                k = lib._clave_valida(k)
                if k:
                    lib.claves[clave] = k
                else:
                    avisos.append(f"descarto la clave {clave} del estado guardado: ilegible")
            if isinstance(libro.get("nada_desde"), (int, float)):
                lib.nada_desde = libro["nada_desde"]
        elif "vidas" in g:  # un estado de R4/R5
            vidas = g["vidas"]
            if not isinstance(vidas, dict):
                avisos.append(f"descarto las vidas del estado guardado: no son un diccionario ({type(vidas).__name__})")
                vidas = {}
            for clave, v in vidas.items():
                try:
                    obs = [[int(o[0]), float(o[1]), float(o[2])] for o in v["obs"]]
                    ap = int(str(v["id"]).rsplit(":", 1)[1])
                    if not obs or str(v["id"]).rsplit(":", 1)[0] != clave:
                        raise ValueError("sin lecturas")
                except (KeyError, TypeError, ValueError, IndexError) as e:
                    avisos.append(f"descarto la vida {clave} del estado guardado: ilegible ({type(e).__name__})")
                    continue
                # sin «vacia»: las filas de antes de su primera lectura (sus parciales) son suyas; las de las vidas que R5
                # ya puntuo no estan (usadas), y las demas a otra entrada la hacen ambigua (A2), no la parten
                lib.claves[clave] = {"runs": [[t, t, s, e, max(t, ap), max(t, ap), v["id"], None] for t, s, e in obs], "vacia": None,
                                     "limpia": None, "ausente": None, "pasadas": []}
            c5 = g.get("cerradas")
            cerradas_r5 = {i: c for i, c in c5.items() if isinstance(c, list) and c and isinstance(c[0], (int, float))} \
                if isinstance(c5, dict) else {}
        # lo visto al evaluar cada vida sin cierre: una lectura con su id (las cerradas de R5, ausentes desde su cierre)
        for i, ev in sorted(evaluadas.items(), key=lambda x: (x[1].get("visto") or 0)):
            p = ev.get("posicion") if isinstance(ev.get("posicion"), dict) else {}
            clave = i.rsplit(":", 1)[0]
            s, e, u = p.get("cantidad"), p.get("entrada"), p.get("actualizada")
            t = p.get("visto") or ev.get("visto") or u
            if not all(isinstance(x, (int, float)) and x for x in (s, e, u, t)):
                continue
            k = lib.claves.setdefault(clave, {"runs": [], "vacia": None, "limpia": lib.nada_desde, "ausente": None, "pasadas": []})
            if any(r[6] == i for r in k["runs"]):
                continue
            mismo_run = next((r for r in k["runs"] if r[4] <= u <= r[5] and r[2] == s and r[3] == e), None)
            if mismo_run:
                mismo_run[6] = mismo_run[6] or i
                continue
            if not k["runs"] or u > k["runs"][-1][5]:  # la mas reciente: una lectura posterior al ultimo latido
                au = k["ausente"]
                k["runs"].append([int(t), int(t), float(s), float(e), int(u), int(u), i,
                                  [au[0], au[2]] if au and au[0] < t else None])
                k["ausente"] = None
                if i in cerradas_r5:  # R5 la tenia cerrada esperando su puntuacion: ausente desde su cierre
                    fin = int(cerradas_r5[i][0])
                    k["ausente"] = [max(fin, int(t) + 1), max(fin, int(t) + 1), VACIAS_SEGUIDAS]
            else:
                k["runs"].append([int(t), int(t), float(s), float(e), int(u), int(u), i, None])
                k["runs"].sort(key=lambda r: (r[4], r[0]))
        for f in sorted(filas, key=lambda f: f["b"]):
            if f["orden"] in usadas:  # de una vida ya puntuada: apuntada (no se vuelve a escribir) y fuera de las vidas
                lib.ordenes[f["orden"]] = f["b"]
            else:
                lib.fila(f)
        return lib, avisos

    @staticmethod
    def _clave_valida(k) -> dict | None:
        if not (isinstance(k, dict) and isinstance(k.get("runs"), list) and isinstance(k.get("vacia"), (int, float, type(None)))):
            return None
        runs = []
        for r in k["runs"]:
            if not (isinstance(r, list) and len(r) in (7, 8) and all(isinstance(x, (int, float)) for x in r[:6])
                    and isinstance(r[6], (str, type(None)))):
                return None
            h = (r + [None])[7]
            if isinstance(h, (int, float)):  # R6 guardaba solo la hora de la primera vacia (dos o mas)
                h = [h, VACIAS_SEGUIDAS]
            runs.append(list(r[:7]) + [h if isinstance(h, list) and len(h) == 2 else None])
        a = k.get("ausente")
        if isinstance(a, list) and len(a) == 2:
            a = a + [VACIAS_SEGUIDAS if a[1] > a[0] else 1]
        pas = k.get("pasadas") if isinstance(k.get("pasadas"), list) else []
        lim = k.get("limpia")
        return {"runs": runs, "vacia": k.get("vacia"), "limpia": lim if isinstance(lim, (int, float)) else None,
                "ausente": list(a) if isinstance(a, list) and len(a) == 3 else None,
                "pasadas": [p for p in pas if isinstance(p, list) and len(p) == 3 and isinstance(p[2], list)]}
