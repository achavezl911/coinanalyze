"""LA VIDA DE CADA POSICION (remate 6 de BOT-2). Pura: sin base, sin red y sin reloj propio. El bot le da lo que lee
(cada lectura de position/list y cada fila nueva de closed-pnl) y ella reconstruye, para cada symbol:side, sus vidas:
cual es nueva (se evalua una vez), cual cerro y con que filas (se puntua) y cual no se puede separar con certeza (se deja
«ambigua» y NO se puntua). La comprueba tests/simulador_bot.py contra la verdad de miles de secuencias, con invariantes.

COMO SE SABE, y lo que se supone (declarado; si un supuesto falla, la vida puede salir MAL, no ambigua):
 S1 la hora de cada fila de closed-pnl y el updatedTime de position/list son del MISMO reloj (Bybit), y updatedTime cambia
    con cada apertura, anadido, cierre parcial o cambio de stop. Asi una fila con hora <= el updatedTime de una lectura
    paso ANTES de esa lectura, sin mirar el reloj de 140 (el desfase de R5). No contrastado con la doc de Bybit.
 S2 closed-pnl trae cada cierre como mucho ESPERA_MS (10 min) despues. Por eso una vida se puntua cuando han pasado ESPERA
    desde lo que no se puede comprobar por tamanos (su primera lectura; un tramo con anadidos), o al momento si cuadra.
 S3 una lista vacia falsa (retCode 0) dura como mucho una lectura.
 S4 un anadido mueve la entrada media mas de TOL_E (0.05 pb), la entrada media de position/list y la de closed-pnl salen
    con esa precision (no contrastado: si difieren por redondeo, la vida sale ambigua, nunca falsa), y una vida nueva no
    abre a +-TOL_E de la entrada media de la que cerro: una fila «a la entrada de la vida» es un cierre de esa vida sin
    anadido entre medias. Un anadido de 1 lote a una posicion de cientos, a pocos pb de su media, no la mueve tanto: ese
    caso puede salir MAL (el bot lo tomaria por la misma entrada).
CUANDO SALE AMBIGUA (y ninguna otra vez; el simulador lo comprueba contra la verdad):
 A1 entre dos lecturas de la vida hubo un anadido que el bot no vio (una fila a otra entrada) seguido de cierres, y no se
    puede saber si llego a 0: la lectura siguiente ensena otra entrada que la de esos cierres, o esos cierres tienen mas
    de una entrada, o la posicion desaparecio con cierres a mas de una entrada. La posicion que se ve SIGUE con el mismo id
    (no se paga otra evaluacion) y la vida no se puntua.
 A2 antes de la primera lectura de una vida nueva hubo cierres a OTRA entrada que la suya, despues del fin cierto de la
    anterior (o, sin registro de esa clave, en cualquier momento): un anadido suyo antes de verla o una vida entera que el
    bot no vio. Es nueva (se evalua) pero no se puntua.
 A3 una fila que no dice su lado (no se movio mas que la comision) cuando las dos direcciones del simbolo tienen vida y su
    entrada no casa con exactamente una de las dos.
 A4 el bot no leyo esa posicion en mas de 7 dias (lo que devuelve closed-pnl): lo de entretanto no se puede reconstruir.
 X  (no deberia pasar si se cumplen S1-S4) una fila mientras lecturas seguidas ensenaban el mismo tamano y la misma entrada.
    Unas filas que cierran MAS de lo que se veia abierto son un anadido sin ver (A1 si no se puede separar), no X.
Y SIN PUNTUAR (no ambigua): la posicion desaparecio y closed-pnl no trajo en ESPERA lo que cubre su tamano visto.
"""

from __future__ import annotations

from app.bot.bybit import lado_cierre

TOL_E = 5e-6  # 0.05 pb: dos entradas medias «iguales» (un anadido real la mueve mas: S4)
TOL_Q = 1e-6  # relativa: dos tamanos iguales
ESPERA_MS = 10 * 60_000
DESFASE_MS = 10_000  # el reloj de 140 contra el de Bybit, solo para «vacia desde» (lecturas sin la clave)
HORIZONTE_MS = 7 * 86400_000
SEGUIDA_MS = 90_000  # dos lecturas «seguidas»: el bot lee cada minuto
INF = float("inf")
A3 = "A3: una fila sin lado en cobertura que no casa con la entrada de una sola de las dos"


def mismo(a, b) -> bool:
    return bool(a) and bool(b) and abs(a / b - 1) <= TOL_E


def _entradas(filas: list) -> list:
    """Las entradas distintas (+-1 pb) de unas filas, en orden."""
    out: list = []
    for f in filas:
        if not any(mismo(f["e"], e) for e in out):
            out.append(f["e"])
    return out


def _sin_tamano(viejo: list, resto: list, post: tuple | None) -> dict:
    """Desde la primera fila que delata un anadido sin ver (otra entrada, o mas cerrado que lo visto) el tamano no se sabe:
    cualquier cierre pudo dejarla a 0. Es la misma vida sin duda solo si esos cierres son de UNA entrada y la lectura
    siguiente ensena esa misma entrada (una reabierta traeria otra: S4); si no, A1."""
    hasta = viejo[-1]["b"] if viejo else None  # la ultima fila segura de la vida (antes del anadido sin ver)
    viejo = viejo + resto
    es = _entradas(resto)
    if post is not None and len(es) == 1 and mismo(post[1], es[0]):
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True}
    if post is None:
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sin_tamano": True, "hasta": hasta,
                "amb": None if len(es) == 1 else "A1: un anadido sin ver y despues cierres a mas de una entrada"}
    return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True,
            "amb": "A1: un anadido sin ver y despues cierres entre dos lecturas: no se sabe si llego a 0 y se reabrio"}


def tramo(pre: tuple, filas: list, post: tuple | None) -> dict:
    """Lo que paso entre dos lecturas de un symbol:side. pre = (tamano, entrada) de la lectura de antes; post = la de
    despues, o None si la clave ya no esta (cola). filas: las de su lado entre las dos, en orden de hora de Bybit.
    -> viejo (filas de la vida de antes), fin (la fila que la deja a 0, o None), nuevo (filas de la vida siguiente antes de
    su primera lectura), amb / amb_nuevo (A1/A2), cuadra (los tamanos lo confirman: no puede faltar ninguna fila),
    falta (con la misma entrada, la lectura ensena menos de lo que dicen las filas: faltan filas por llegar)."""
    tam, ent = pre
    viejo: list = []
    for j, f in enumerate(filas):
        if mismo(f["e"], ent):
            viejo.append(f)
            tam -= f["q"]
            if tam < -pre[0] * TOL_Q:  # cierran MAS de lo que se veia: hubo un anadido sin ver (que casi no movio la media)
                viejo.pop()
                return _sin_tamano(viejo, filas[j:], post)
            if tam <= pre[0] * TOL_Q:
                resto = filas[j + 1:]
                if post is None:  # lo de despues: vidas enteras que el bot no vio
                    return {"viejo": viejo, "fin": f, "nuevo": [], "cuadra": True}
                otras = [g for g in resto if not mismo(g["e"], post[1])]
                return {"viejo": viejo, "fin": f, "nuevo": [g for g in resto if mismo(g["e"], post[1])], "cuadra": True,
                        "amb_nuevo": f"A2: antes de verla hubo {len(otras)} cierre(s) a otra entrada (un anadido suyo o una vida"
                                     f" entera que el bot no vio)" if otras else None}
        else:  # una fila a otra entrada: hubo un anadido que el bot no vio; desde aqui el tamano no se sabe
            return _sin_tamano(viejo, filas[j:], post)
    if post is None:
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False}
    if mismo(post[1], ent):
        if abs(post[0] - tam) <= pre[0] * TOL_Q:
            return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": True, "sigue": True}
        return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True, "falta": post[0] < tam}
    return {"viejo": viejo, "fin": None, "nuevo": [], "cuadra": False, "sigue": True}  # anadidos despues de esos cierres


def tramo_hueco(pre: tuple, filas: list, post_e) -> dict:
    """Un tramo con al menos dos lecturas SIN la clave entre medias: por S3 la vida de antes CERRO; la de despues (si
    hay) es nueva sin duda. Lo que falta es repartir las filas: las de la entrada de antes, primero, son de ella (hasta
    cubrir su tamano: su cierre); las de la entrada de la nueva, de la nueva (sus parciales antes de verla, S4); y el resto:
    si es de una sola entrada, de la vieja tras un anadido sin ver; si es de mas de una, no se puede repartir (A1 la vieja,
    A2 la nueva)."""
    tam, ent = pre
    a: list = []
    for j, f in enumerate(filas):
        if not mismo(f["e"], ent):
            break
        a.append(f)
        tam -= f["q"]
        if tam <= pre[0] * TOL_Q:
            resto = filas[j + 1:]
            otras = [g for g in resto if not mismo(g["e"], post_e)] if post_e else []
            return {"viejo": a, "fin": f, "nuevo": [g for g in resto if post_e and mismo(g["e"], post_e)],
                    "amb_nuevo": f"A2: antes de verla hubo {len(otras)} cierre(s) a otra entrada (un anadido suyo o una vida"
                                 f" entera que el bot no vio)" if otras else None}
    resto = filas[len(a):]
    nuevo = [g for g in resto if post_e and mismo(g["e"], post_e)]
    c = [g for g in resto if not (post_e and mismo(g["e"], post_e))]
    if not c:
        return {"viejo": a, "fin": a[-1] if a else None, "nuevo": nuevo, "falta": True}
    if len(_entradas(c)) == 1:
        return {"viejo": a + c, "fin": c[-1], "nuevo": nuevo}
    # el registro solo avanza hasta su ultima fila SEGURA: las dudosas pueden ser de la nueva y la dejan A2
    return {"viejo": a + c, "fin": a[-1] if a else None, "nuevo": nuevo,
            "amb": "A1: un anadido sin ver y despues cierres a mas de una entrada mientras no estaba en las lecturas",
            "amb_nuevo": "A2: antes de verla hubo cierres a mas de una entrada que no se pueden repartir" if post_e else None}


class Libro:
    """Las vidas de todas las posiciones. Estado serializable (estado()/desde()): por symbol:side, sus lecturas desde la
    ultima vida ya puntuada -cada tramo de lecturas seguidas con el mismo tamano y entrada: [primera, ultima, tamano,
    entrada, updatedTime primero, updatedTime ultimo, id]-, «vacia» (hora de Bybit desde la que se sabe vacia) y
    «ausente» (las lecturas seguidas sin ella)."""

    def __init__(self):
        self.claves: dict = {}
        self.filas: dict = {}  # symbol -> filas en orden de hora de Bybit
        self.ordenes: set = set()
        self.nada_desde = None  # hora de Bybit desde la que toda clave sin registro estaba vacia (dos lecturas sin ella)
        self.previas: list = []  # las dos ultimas lecturas (hora de 140)
        self.ultima = None

    # ---------------------------------------------------------------- lo que entra
    def fila(self, f: dict):
        """Una fila de closed-pnl: orden, symbol, b (su hora, ms de Bybit), q (closedSize), e (avgEntryPrice), x
        (avgExitPrice), pnl."""
        if f["orden"] in self.ordenes or None in (f.get("b"), f.get("q"), f.get("e")):
            return
        self.ordenes.add(f["orden"])
        lista = self.filas.setdefault(f["symbol"], [])
        lista.append(f)
        if len(lista) > 1 and lista[-2]["b"] > f["b"]:
            lista.sort(key=lambda g: g["b"])

    def lee(self, ahora: int, posiciones: list):
        """Una lectura de position/list (bybit.posiciones): las que se ven y, por omision, las que no."""
        vistas = {p["clave"]: p for p in posiciones}
        for clave, p in vistas.items():
            k = self.claves.get(clave)
            if k is None:
                k = self.claves[clave] = {"runs": [], "vacia": self.nada_desde, "ausente": None}
            u = p.get("actualizada") or ahora
            r = k["runs"][-1] if k["runs"] else None
            # dos o mas lecturas seguidas sin ella: S3 dice que la de antes cerro (hueco = la primera de esas lecturas)
            hueco = k["ausente"][0] if k["ausente"] and k["ausente"][1] > k["ausente"][0] else None
            if r and not hueco and r[2] == p["cantidad"] and r[3] == p["entrada"]:
                r[1], r[5] = ahora, max(r[5], u)
            else:
                k["runs"].append([ahora, ahora, p["cantidad"], p["entrada"], u, u, None, hueco])
            k["ausente"] = None
        for clave, k in self.claves.items():
            if clave not in vistas and k["runs"]:
                # seguidas de verdad: la anterior sin ella fue la lectura de hace un minuto (no la de antes de una caida)
                seguida = k["ausente"] and ahora - k["ausente"][1] <= SEGUIDA_MS
                k["ausente"] = [k["ausente"][0], ahora] if seguida else [ahora, ahora]
        self.previas = (self.previas + [ahora])[-2:]
        if len(self.previas) == 2:
            self.nada_desde = self.previas[0] - DESFASE_MS
        self.ultima = ahora

    # ---------------------------------------------------------------- lo que sale
    def decide(self, ahora: int) -> dict:
        """-> presentes {id: clave} (las vidas que la ULTIMA lectura ensena), firmes {id: su ultima lectura que es suya
        sin duda} (con ella se evalua: una lectura enganchada por un tramo con anadidos no lo es hasta que pasa ESPERA sin
        que closed-pnl diga otra cosa), notas {id: texto} y resultados [(id, {pnl, ordenes, nota})] de las vidas cerradas y
        ya seguras (cada una una sola vez; pnl None = sin puntuar)."""
        out: dict = {"presentes": {}, "notas": {}, "resultados": [], "firmes": {}}
        for clave, k in self.claves.items():
            if not k["runs"]:
                continue
            vidas = self._vidas(clave, k, ahora)
            for v in vidas:
                for i in v["runs"]:
                    k["runs"][i][6] = v["id"]
                if v.get("nota"):
                    out["notas"][v["id"]] = v["nota"]
            ultima = vidas[-1]
            if k["ausente"] is None and k["runs"][-1][1] == self.ultima and ultima["fin"] is None:
                out["presentes"][ultima["id"]] = clave
                r = k["runs"][ultima["firme_run"]]  # su ultima lectura segura: con ella se evalua (R6, I1/I2)
                out["firmes"][ultima["id"]] = {"cantidad": r[2], "entrada": r[3], "actualizada": r[5], "visto": r[1],
                                               "actual": ultima["firme_run"] == len(k["runs"]) - 1}
            # las cerradas y seguras, en orden; cada una sale una vez y el registro avanza tras ella
            hechas = 0
            for v in vidas:
                if v["fin"] is None or ahora < v["espera"] + ESPERA_MS:
                    break
                out["resultados"].append((v["id"], self._resultado(v)))
                hechas = max(v["runs"]) + 1
                fin = max(v["fin"], k["runs"][max(v["runs"])][5])
                # su tramo y sus entradas se recuerdan 8 dias: deciden de que lado es una fila sin lado de la otra direccion
                k["pasadas"] = [p for p in k.get("pasadas", []) if p[1] > fin - HORIZONTE_MS - 86400_000] + \
                    [[k["vacia"] if k["vacia"] is not None else k["runs"][min(v["runs"])][4] - 1, fin,
                      [k["runs"][i][3] for i in v["runs"]]]]
                k["vacia"] = fin
            if hechas:
                del k["runs"][:hechas]
                if not k["runs"]:
                    k["ausente"] = None
        return out

    def abiertas(self) -> bool:
        return any(k["runs"] for k in self.claves.values())

    @staticmethod
    def _resultado(v: dict) -> dict:
        ordenes = [f["orden"] for f in v["filas"]]
        if v.get("amb"):
            return {"pnl": None, "ordenes": ordenes, "nota": f"ambigua: {v['amb']}"}
        if v.get("faltan"):
            return {"pnl": None, "ordenes": ordenes, "nota": f"closed-pnl no trajo en {ESPERA_MS // 60_000} min lo que cubre su"
                                                              " tamano visto: sin puntuar"}
        if not v["filas"]:
            return {"pnl": None, "ordenes": [], "nota": "sin operaciones suyas en closed-pnl: sin puntuar"}
        return {"pnl": sum(f["pnl"] or 0 for f in v["filas"]), "ordenes": ordenes, "nota": v.get("nota")}

    @staticmethod
    def _viva(k: dict | None, b) -> list | None:
        """Las entradas de la vida de k que cubre la hora b (la abierta o una ya puntuada), o None si ninguna la cubre."""
        if not k:
            return None
        if k["runs"] and (k["vacia"] is None or b > k["vacia"]):
            return [r[3] for r in k["runs"]]
        return next((p[2] for p in k.get("pasadas", []) if p[0] < b <= p[1]), None)

    def _filas_de(self, clave: str, k: dict) -> tuple[list, list]:
        """Las filas de ese symbol:side, y las que no dicen su lado cuando a esa hora las dos direcciones tenian vida y
        su entrada no casa con exactamente una (A3)."""
        sym, lado = clave.split(":")[0], 1 if clave.endswith(":Buy") else -1
        otra = self.claves.get(f"{sym}:{'Sell' if lado > 0 else 'Buy'}")
        suyas, sin_lado = [], []
        for f in self.filas.get(sym, []):
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
        runs, corte = k["runs"], k["vacia"]
        entre = lambda xs, a, b: [f for f in xs if (a is None or f["b"] > a) and f["b"] <= b]  # noqa: E731
        vidas: list = []
        v = None
        usados: set = set()

        def nueva(r: list, previas: list, amb, nacida, nota=None):
            rid = r[6] if r[6] and r[6] not in usados else None
            vid = rid or f"{clave}:{nacida + 1 if nacida is not None else r[4]}"
            usados.add(vid)
            return {"id": vid, "runs": [], "filas": list(previas), "fin": None, "espera": r[0], "amb": amb, "nota": nota, "cadena": True,
                    "firme_run": None}

        for i, r in enumerate(runs):
            G, sl = entre(filas, corte, r[4]), entre(sin_lado, corte, r[4])
            if corte is not None and r[4] - corte > HORIZONTE_MS and v is not None:
                v["amb"] = v["amb"] or "A4: mas de 7 dias sin leer esta posicion"
            if v is None:
                otras = [f for f in G if not mismo(f["e"], r[3])]
                amb = (f"A2: antes de verla hubo {len(otras)} cierre(s) a otra entrada"
                       + (" (el bot no tenia registro de esta clave)" if corte is None else "")) if otras else None
                v = nueva(r, [f for f in G if mismo(f["e"], r[3])], amb, None)
            elif r[7] is not None:  # hueco: la de antes cerro seguro; esta es nueva
                p = runs[i - 1]
                t = tramo_hueco((p[2], p[3]), G, r[3])
                v["filas"] += t["viejo"]
                v["fin"] = t["fin"]["b"] if t.get("fin") else p[5]
                v["espera"] = max(v["espera"], r[7])  # sus filas pueden tardar ESPERA desde que dejo de verse
                if t.get("amb"):
                    v["amb"] = v["amb"] or t["amb"]
                if t.get("falta"):
                    v["faltan"] = True
                if any(f["b"] <= v["fin"] for f in sl):
                    v["amb"] = v["amb"] or A3
                vidas.append(v)
                v = nueva(r, t["nuevo"], t.get("amb_nuevo"), None)
                sl = [f for f in sl if f["b"] > vidas[-1]["fin"]]
            else:
                p = runs[i - 1]
                t = tramo((p[2], p[3]), G, (r[2], r[3]))
                v["filas"] += t["viejo"]
                if t.get("fin"):
                    v["fin"] = t["fin"]["b"]
                    if any(f["b"] <= v["fin"] for f in sl):  # una fila sin lado ANTES de su cierre
                        v["amb"] = v["amb"] or A3
                    sl = [f for f in sl if f["b"] > v["fin"]]
                    vidas.append(v)
                    hora = t["fin"]["b"]
                    v = nueva(r, t["nuevo"], t.get("amb_nuevo"), hora,
                              nota=f"cerrada la anterior y reabierta entre dos lecturas (closed-pnl, orden {t['fin']['orden']})")
                else:
                    if r[6] and r[6] != v["id"] and r[6] not in usados:  # un registro anterior la separa aqui
                        v["amb"] = v["amb"] or "A1: un registro anterior la separa aqui sin una fila que la cierre"
                        v["fin"] = p[5]
                        vidas.append(v)
                        v = nueva(r, [], v["amb"], None)
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
            if entre(filas, r[4], r[5]):
                v["amb"] = v["amb"] or "X: una fila mientras el tamano y la entrada no cambiaban"
            v["runs"].append(i)
            if v["cadena"]:
                v["firme_run"] = i  # la ultima lectura que es suya sin duda
            corte = r[5]
        if v is None:
            return vidas
        if k["ausente"] is not None:  # la cola: la clave ya no esta en las lecturas
            r = runs[-1]
            t = tramo((r[2], r[3]), entre(filas, corte, INF), None)
            v["filas"] += t["viejo"]
            if t.get("amb"):
                v["amb"] = v["amb"] or t["amb"]
            sl = entre(sin_lado, corte, t["fin"]["b"] if t.get("fin") else INF)  # despues de su cierre: de vidas que no vio
            if sl:
                v["amb"] = v["amb"] or A3
            if t.get("fin"):
                v["fin"] = t["fin"]["b"]
            elif k["ausente"][1] > k["ausente"][0] and ahora - k["ausente"][0] >= ESPERA_MS:
                # dos lecturas sin ella y ESPERA despues: cerro, y lo que closed-pnl trajo es todo lo que hay
                # el registro avanza hasta su ultima fila segura (con A1, las dudosas pueden ser de otra vida)
                v["fin"] = max([x for x in (t.get("hasta"), r[5]) if x is not None]) if t.get("amb") else \
                    max([f["b"] for f in v["filas"]] + [r[5]])
                if not t.get("sin_tamano"):
                    v["faltan"] = True
        vidas.append(v)
        return vidas

    # ---------------------------------------------------------------- persistencia
    def estado(self) -> dict:
        return {"v": 6, "claves": self.claves, "nada_desde": self.nada_desde, "previas": self.previas}

    @classmethod
    def desde(cls, guardado, evaluadas: dict, filas: list) -> tuple[Libro, list]:
        """El libro del ultimo estado publicado, con lectura TOLERANTE (lo que no se entiende se descarta y se dice), mas
        lo visto al evaluar cada vida sin cierre (bot_evaluacion: un veredicto posterior al ultimo latido -remate 6, R-B-
        es una lectura mas, con su id) y las filas de bot_operacion. De un estado de R4/R5 («vidas»): cada vida, con sus
        lecturas y vacia desde su apertura. -> (libro, avisos)."""
        lib, avisos = cls(), []
        g = guardado if isinstance(guardado, dict) else {}
        if guardado is not None and not isinstance(guardado, dict):
            avisos.append(f"descarto el estado guardado: no es un objeto ({type(guardado).__name__})")
        libro = g.get("libro")
        if isinstance(libro, dict):
            for clave, k in (libro.get("claves") or {}).items() if isinstance(libro.get("claves"), dict) else []:
                ok = isinstance(k, dict) and isinstance(k.get("runs"), list) and all(
                    isinstance(r, list) and len(r) in (7, 8) and all(isinstance(x, (int, float)) for x in r[:6])
                    and isinstance(r[6], (str, type(None))) and isinstance((r + [None])[7], (int, float, type(None)))
                    for r in k["runs"])
                if ok and isinstance(k.get("vacia"), (int, float, type(None))):
                    a, pas = k.get("ausente"), k.get("pasadas") if isinstance(k.get("pasadas"), list) else []
                    lib.claves[clave] = {"runs": [(list(r) + [None])[:8] for r in k["runs"]], "vacia": k.get("vacia"),
                                         "ausente": list(a) if isinstance(a, list) and len(a) == 2 else None,
                                         "pasadas": [p for p in pas if isinstance(p, list) and len(p) == 3 and isinstance(p[2], list)]}
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
                lib.claves[clave] = {"runs": [[t, t, s, e, t, t, v["id"], None] for t, s, e in obs], "vacia": ap - 1, "ausente": None}
        for i, ev in evaluadas.items():  # lo visto al evaluar: una lectura con su id
            p = ev.get("posicion") if isinstance(ev.get("posicion"), dict) else {}
            clave = i.rsplit(":", 1)[0]
            s, e, u = p.get("cantidad"), p.get("entrada"), p.get("actualizada")
            t = p.get("visto") or ev.get("visto") or u
            if not all(isinstance(x, (int, float)) and x for x in (s, e, u, t)):
                continue
            k = lib.claves.setdefault(clave, {"runs": [], "vacia": lib.nada_desde, "ausente": None})
            if any(r[6] == i for r in k["runs"]):
                continue
            hueco = next((r for r in k["runs"] if r[4] <= u <= r[5] and r[2] == s and r[3] == e), None)
            if hueco:
                hueco[6] = hueco[6] or i
                continue
            if not k["runs"] or u > k["runs"][-1][5]:  # la mas reciente: una lectura posterior al ultimo latido
                au = k["ausente"]
                hueco = au[0] if au and au[1] > au[0] and au[0] < t else None
                k["runs"].append([int(t), int(t), float(s), float(e), int(u), int(u), i, hueco])
                k["ausente"] = None  # se vio despues de la ausencia guardada
            else:
                k["runs"].append([int(t), int(t), float(s), float(e), int(u), int(u), i, None])
                k["runs"].sort(key=lambda r: (r[4], r[0]))
        for f in filas:
            lib.fila(f)
        return lib, avisos
