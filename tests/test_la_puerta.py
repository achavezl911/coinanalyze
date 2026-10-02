"""LA PUERTA (campana 133): que sirve cada ruta de pantalla, y como se pasa de una a otra.

`/` sirve la mesa, `/panel` el panel viejo y `/mesa` sigue sirviendo la mesa. Se prueba la TABLA
DE RUTAS de la aplicacion -el decorador-, no solo la funcion: una funcion correcta colgada de la
ruta equivocada pasaria un test que la llamara por su nombre.

Y desde cada pantalla se llega a la otra con un enlace VISIBLE: en la cabecera, con texto, y sin
nada que lo esconda por encima. El manual vuelve a la pantalla que su enlace dice.
"""
from __future__ import annotations

import asyncio
from html.parser import HTMLParser
from pathlib import Path

import app.api as api

RAIZ = Path(__file__).resolve().parents[1]
STATIC = RAIZ / "static"


def _ruta_get(camino: str):
    for r in api.app.routes:
        if getattr(r, "path", None) == camino and "GET" in (getattr(r, "methods", None) or ()):
            return r
    raise AssertionError(f"la aplicacion no declara GET {camino}")


def _fichero_servido(camino: str) -> str:
    respuesta = asyncio.run(_ruta_get(camino).endpoint())
    return Path(respuesta.path).name


def test_la_raiz_sirve_la_mesa():
    assert _fichero_servido("/") == "mesa.html"


def test_mesa_sigue_sirviendo_la_mesa():
    assert _fichero_servido("/mesa") == "mesa.html"


def test_el_panel_viejo_vive_en_panel():
    assert _fichero_servido("/panel") == "index.html"


def test_las_tres_puertas_existen_en_disco():
    for nombre in ("mesa.html", "index.html"):
        assert (STATIC / nombre).is_file(), nombre


class _Enlaces(HTMLParser):
    """Cada <a> con su href, su texto, y la pila de etiquetas que lo contienen."""

    VACIAS = {"meta", "link", "br", "img", "input", "hr", "source", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.pila: list[tuple[str, dict[str, str | None]]] = []
        self.enlaces: list[dict] = []
        self._abierto: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            self._abierto = {"href": a.get("href"), "attrs": a, "texto": "", "dentro": list(self.pila)}
        if tag not in self.VACIAS:
            self.pila.append((tag, a))

    def handle_endtag(self, tag):
        if tag == "a" and self._abierto is not None:
            self.enlaces.append(self._abierto)
            self._abierto = None
        for i in range(len(self.pila) - 1, -1, -1):
            if self.pila[i][0] == tag:
                del self.pila[i:]
                break

    def handle_data(self, data):
        if self._abierto is not None:
            self._abierto["texto"] += data


def _enlaces(fichero: str) -> list[dict]:
    p = _Enlaces()
    p.feed((STATIC / fichero).read_text(encoding="utf-8"))
    return p.enlaces


def _escondido(enlace: dict) -> bool:
    for _tag, attrs in enlace["dentro"] + [("a", enlace["attrs"])]:
        if "hidden" in attrs:
            return True
        estilo = (attrs.get("style") or "").replace(" ", "").lower()
        if "display:none" in estilo or "visibility:hidden" in estilo:
            return True
    return False


def _en_cabecera(enlace: dict) -> bool:
    return any(tag == "header" for tag, _ in enlace["dentro"])


def _unico_hacia(fichero: str, href: str) -> dict:
    hacia = [e for e in _enlaces(fichero) if e["href"] == href]
    assert len(hacia) == 1, f"{fichero}: {len(hacia)} enlaces a {href}"
    return hacia[0]


def test_la_mesa_enlaza_al_panel_viejo_a_la_vista():
    e = _unico_hacia("mesa.html", "/panel")
    assert _en_cabecera(e), "el enlace al panel tiene que estar en la cabecera de la mesa"
    assert not _escondido(e)
    assert "PANEL" in e["texto"].upper()


def test_el_panel_viejo_enlaza_a_la_mesa_a_la_vista():
    e = _unico_hacia("index.html", "/")
    assert _en_cabecera(e), "el enlace a la mesa tiene que estar en la cabecera del panel"
    assert not _escondido(e)
    assert "MESA" in e["texto"].upper()


def test_ninguna_pantalla_enlaza_a_si_misma_como_si_fuera_la_otra():
    # La mesa no puede llevar a `/` diciendo «panel», ni el panel a `/panel` diciendo «mesa».
    for e in _enlaces("mesa.html"):
        if e["href"] in ("/", "/mesa"):
            assert "PANEL" not in e["texto"].upper(), e
    for e in _enlaces("index.html"):
        if e["href"] == "/panel":
            assert "MESA" not in e["texto"].upper(), e


def test_el_manual_vuelve_a_la_pantalla_que_dice():
    (vuelta,) = [e for e in _enlaces("manual.html") if "volver" in e["texto"].lower()]
    assert vuelta["href"] == "/panel", vuelta
    assert "panel" in vuelta["texto"].lower(), vuelta


# EL CONTRATO DE LA MESA (harness/checks/K44-contrato-mesa.tsv) contra su CODIGO, en las dos
# direcciones. K44 lo contrasta con lo que un navegador pide de verdad; esto, con lo que la mesa
# esta escrita para pedir. Una ruta declarada que el codigo no pide es prosa; una que el codigo
# pide y el contrato calla es una peticion que K44 condenaria en produccion.
CONTRATO = RAIZ / "harness" / "checks" / "K44-contrato-mesa.tsv"


def _rutas_del_contrato() -> dict[str, set[str]]:
    rutas = {}
    for ln in CONTRATO.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        c = ln.split("\t")
        if c[0].startswith("/api/"):
            rutas[c[0]] = {x.strip() for x in c[1].split(",")}
    return rutas


def _rutas_que_la_mesa_pide() -> set[str]:
    import re

    pedidas = set()
    for js in sorted((STATIC / "mesa").glob("*.js")):
        pedidas |= set(re.findall(r"pedir\(\s*'(/api/[^'?]+)'", js.read_text(encoding="utf-8")))
    return pedidas


def test_el_contrato_de_la_mesa_casa_con_su_codigo():
    contrato, codigo = _rutas_del_contrato(), _rutas_que_la_mesa_pide()
    assert len(codigo) >= 10, f"el censo del codigo de la mesa salio corto: {sorted(codigo)}"
    assert sorted(set(contrato) - codigo) == [], "declaradas que el codigo NO pide"
    assert sorted(codigo - set(contrato)) == [], "pedidas por el codigo y NO declaradas"


def test_el_contrato_declara_un_nucleo_y_papeles_conocidos():
    # LA FORMA PRIMERO: un tabulador perdido junta dos columnas y la fila sigue «leyendose» (paso en la
    # 133, en la fila de quality/feeds). Cinco columnas en cada fila, ninguna vacia.
    filas = [ln.split("\t") for ln in CONTRATO.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert filas and all(len(f) == 5 and all(c.strip() for c in f) for f in filas), \
        [f[0] for f in filas if len(f) != 5 or not all(c.strip() for c in f)]
    contrato = _rutas_del_contrato()
    # La ruta va partida a proposito: escrita entera, bin/arquitectura acreditaria a este test como
    # consumidor de DECIDE (la autocontaminacion que cuenta harness/checks/K44-control.bash).
    assert [r for r, p in contrato.items() if "NUCLEO" in p] == ["/api" + "/mesa/decide"]
    assert set().union(*contrato.values()) <= {"NUCLEO", "PARTE", "ESTADO"}
