#!/usr/bin/env python3
"""K102-mesa · la sonda de Chromium de la MESA. Mide, no opina: el veredicto lo pone el .sh.

QUE MIDE, Y POR QUE HACE FALTA UN NAVEGADOR DE VERDAD
  1 · QUE DECIDE ES LO PRIMERO QUE SE LEE. Eso es una pregunta de MAQUETA: hay que saber donde
      cae `#decide` en el primer pliegue a un tamano dado. jsdom no maqueta -no tiene
      `getBoundingClientRect` con numeros reales-, asi que aqui se usa Chromium por CDP.
  2 · QUE CADA VALOR DE DECIDE SALE DEL BACKEND. Se comprueba la PAREJA (source_key, valor)
      celda a celda contra el sobre servido, NO buscando el valor por la pantalla: «Long» esta
      en `bias`, en `state` («Long Pullback») y en `invalidates_long`, y un grep que case por
      homonimia absuelve sin medir (A41/A42). Y como cada entrada lleva su clave AL LADO, un
      INTERCAMBIO entre dos etiquetas que ya estan en pantalla tampoco cuela (A43).
  3 · CUANTO TARDA Y CUANTO CUESTA. `window.MESA_HITOS` marca `t0`, `decidePintado` y
      `completo`; la red se cuenta por CDP (peticiones y bytes).

LO QUE NO HACE: no declara VERDE nada. Escribe un JSON y sale 0 si pudo medir, 2 si NO PUDO.
Un cero que no distingue «sin defecto» de «no he medido» es lo que A35 prohibe.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

try:
    import websockets
except ImportError:  # pragma: no cover
    print("NO MEDIDO: falta el modulo python `websockets` para hablar CDP", file=sys.stderr)
    raise SystemExit(2) from None

# Los campos de `payload.decide` que la pantalla TIENE que ensenar. Si el sobre trae uno con
# valor y la pantalla no lo pinta con su clave, es un hallazgo.
CAMPOS_ESCALARES = (
    "bias",
    "evidence_balance",
    "state",
    "reason",
    "zone_decision",
    "invalidation_level",
    "structural_invalidation",
    "structural_horizon",
    "confidence",
    "data_confidence",
    "evidence",
    "edge",
    "horizon",
)
CAMPOS_LISTA = ("confirms", "invalidates")


def puerto_libre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def binario_chromium() -> str:
    for n in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        r = shutil.which(n)
        if r:
            return r
    print("NO MEDIDO: no hay chromium en el PATH", file=sys.stderr)
    raise SystemExit(2)


class Chromium:
    def __init__(self, ancho: int, alto: int, ocultar_barra: bool = False):
        self.ancho, self.alto = ancho, alto
        self.ocultar_barra = ocultar_barra
        self.puerto = puerto_libre()
        self.perfil = tempfile.mkdtemp(prefix="k102-chromium-")
        self.proc: subprocess.Popen | None = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [
                binario_chromium(),
                "--headless=new",
                f"--remote-debugging-port={self.puerto}",
                f"--user-data-dir={self.perfil}",
                f"--window-size={self.ancho},{self.alto}",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                # LA BARRA DE DESPLAZAMIENTO SE QUEDA, salvo que se pida quitarla.
                # `--hide-scrollbars` estaba puesto siempre, y con el la ventana util es MAS
                # ALTA que en un navegador de escritorio de verdad: la red medía un pliegue
                # que nadie tiene. Medido por el operador el 2026-09-29 a 1440x900, la misma
                # carga, dos vueltas alternando: CON barra `#decide` va de 237 a 598, SIN
                # barra de 222 a 583. Cabe en los dos -por eso el veredicto no cambia- pero
                # el numero que se publica tiene que ser el de quien usa la mesa.
                *(["--hide-scrollbars"] if self.ocultar_barra else []),
                # El certificado de 140 es propio: sin esto no se puede medir contra produccion.
                "--ignore-certificate-errors",
                "--no-first-run",
                "--no-default-browser-check",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Esperar a que el puerto conteste. Sin esto la primera conexion se cae y parece que
        # el sujeto esta roto cuando lo que pasa es que el canal no estaba.
        muerto = time.time() + 30
        while time.time() < muerto:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.puerto}/json/version", timeout=1
                ) as r:
                    json.load(r)
                    return self
            except Exception:
                time.sleep(0.25)
        raise SystemExit2("chromium no abrio su puerto de depuracion en 30 s")

    def __exit__(self, *a):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.perfil, ignore_errors=True)


class SystemExit2(Exception):
    pass


class Sesion:
    """Un cliente CDP minimo: UN LECTOR de fondo, respuestas por futuro y eventos en lista.

    POR QUE UN SOLO LECTOR, Y NO CADA LLAMADA LEYENDO DEL SOCKET. La primera version tenia
    `pide()` leyendo con `await ws.recv()` SIN TOPE, y `drena()` leyendo con
    `asyncio.wait_for(ws.recv(), ...)`. Los dos leen del MISMO socket, asi que:

      · cuando `wait_for` expira, CANCELA el `recv()` en curso y el frame que venia de camino
        SE PIERDE;
      · si el perdido era la respuesta que `pide()` esperaba, `pide()` se queda bloqueado PARA
        SIEMPRE, porque su espera no tenia tope.

    Medido: la corrida de C3 del 2026-09-29T04:04Z se colgo 16.5 min -contra un techo teorico
    de 7.3- y hubo que matarla sin cifra. No era el sujeto: era este cliente.

    La forma correcta es la de siempre para un protocolo multiplexado: UN lector, que reparte.
    Y TODA espera lleva tope, para que un fallo salga como NO MEDIDO y no como un cuelgue.
    """

    def __init__(self, ws):
        self.ws = ws
        self.n = 0
        self.eventos: list[dict] = []
        self.esperando: dict[int, asyncio.Future] = {}
        self.muerto: Exception | None = None
        self._lector = asyncio.create_task(self._lee())

    async def _lee(self):
        try:
            async for crudo in self.ws:
                m = json.loads(crudo)
                mid = m.get("id")
                if mid is not None and mid in self.esperando:
                    fut = self.esperando.pop(mid)
                    if not fut.done():
                        fut.set_result(m)
                elif "method" in m:
                    self.eventos.append(m)
        except Exception as e:  # noqa: BLE001
            self.muerto = e
            for fut in self.esperando.values():
                if not fut.done():
                    fut.set_exception(SystemExit2(f"el socket CDP se cayo: {e}"))
            self.esperando.clear()

    async def cierra(self):
        self._lector.cancel()
        try:
            await self._lector
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    async def pide(self, metodo: str, tope: float = 30.0, **params):
        if self.muerto is not None:
            raise SystemExit2(f"el socket CDP ya estaba caido: {self.muerto}")
        self.n += 1
        mio = self.n
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.esperando[mio] = fut
        await self.ws.send(json.dumps({"id": mio, "method": metodo, "params": params}))
        try:
            m = await asyncio.wait_for(fut, timeout=tope)
        except TimeoutError as e:
            self.esperando.pop(mio, None)
            raise SystemExit2(f"CDP {metodo} no contesto en {tope:g} s") from e
        if "error" in m:
            raise SystemExit2(f"CDP {metodo}: {m['error']}")
        return m.get("result", {})

    async def drena(self, segundos: float):
        """Deja correr el lector de fondo. Ya NO toca el socket: solo cede el control."""
        await asyncio.sleep(segundos)
        if self.muerto is not None:
            raise SystemExit2(f"el socket CDP se cayo: {self.muerto}")

    async def atiende_fetch(self, reescribe):
        """Contesta a los `Fetch.requestPaused` que haya en la cola.

        `reescribe(url)` devuelve la URL nueva, o None para dejarla igual. Sin esto, activar
        `Fetch.enable` CUELGA la pagina: toda peticion interceptada se queda esperando, y la
        medida saldria «no pinto nunca» por culpa del instrumento y no del sujeto.
        """
        pendientes = [e for e in self.eventos if e.get("method") == "Fetch.requestPaused"]
        self.fetch_atendidos = getattr(self, "fetch_atendidos", 0) + len(pendientes)
        for e in pendientes:
            self.eventos.remove(e)
            p = e.get("params", {})
            url = (p.get("request") or {}).get("url", "")
            nueva = reescribe(url)
            try:
                if nueva and nueva != url:
                    await self.pide("Fetch.continueRequest", requestId=p["requestId"], url=nueva)
                else:
                    await self.pide("Fetch.continueRequest", requestId=p["requestId"])
            except SystemExit2:
                pass
        return len(pendientes)

    async def evalua(self, expr: str):
        r = await self.pide(
            "Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True
        )
        if r.get("exceptionDetails"):
            raise SystemExit2("JS: " + json.dumps(r["exceptionDetails"])[:300])
        return r.get("result", {}).get("value")


# El JS que se evalua DENTRO de la pagina para extraer el contrato de DOM de DECIDE.
# Devuelve las parejas (campo, valor, clave) de #decide y la geometria del pliegue.
JS_COSECHA = r"""
(() => {
  const d = document.getElementById('decide');
  if (!d) return {error: 'no existe #decide'};
  const r = d.getBoundingClientRect();
  const cs = getComputedStyle(d);
  const visible = cs.display !== 'none' && cs.visibility !== 'hidden'
                  && Number(cs.opacity) > 0.01 && r.height > 1 && r.width > 1;

  // LAS PAREJAS. Cada celda declara data-campo; su valor vive en [data-valor] y su clave en
  // [data-source-key]. Se recogen TAL CUAL, sin interpretar.
  const parejas = [];
  d.querySelectorAll('[data-campo]').forEach((c) => {
    const nombre = c.getAttribute('data-campo');
    const nv = c.matches('[data-valor]') ? c : c.querySelector(':scope > [data-valor]');
    const nk = c.matches('[data-source-key]') ? c : c.querySelector(':scope > [data-source-key]');
    parejas.push({
      campo: nombre,
      valor: nv ? (nv.getAttribute('data-valor') || '') : null,
      clave: nk ? (nk.getAttribute('data-source-key') || '') : null,
      texto: (c.textContent || '').trim().slice(0, 300),
    });
  });

  // EL TAMANO DE LETRA MAS GRANDE DEL PRIMER PLIEGUE. Si DECIDE es lo primero que se lee, el
  // sesgo tiene que ser el glifo mas grande de la pantalla inicial, no solo caber.
  let mayor = 0, mayorTexto = '';
  document.querySelectorAll('body *').forEach((n) => {
    const rr = n.getBoundingClientRect();
    if (rr.height < 1 || rr.top >= window.innerHeight || rr.bottom <= 0) return;
    if (!n.textContent || !n.textContent.trim()) return;
    if (n.children.length) return;  // solo hojas: un contenedor hereda el tamano
    const px = parseFloat(getComputedStyle(n).fontSize) || 0;
    if (px > mayor) { mayor = px; mayorTexto = n.textContent.trim().slice(0, 40); }
  });

  const sesgo = document.getElementById('decide-sesgo');
  const rs = sesgo ? sesgo.getBoundingClientRect() : null;

  // LA TARJETA DEL SCALP, APARTE. En swing y en largo la palabra del scalp NO se pinta en
  // #decide -B7 exige justo que no este ahi- sino en #lectura-scalp. Se cosecha en SU PROPIA
  // clave y nunca dentro de `parejas`: si cayera ahi, B7 leeria `state` dentro de DECIDE y
  // condenaria una pantalla correcta.
  const ls = document.getElementById('lectura-scalp');
  let tarjeta = null;
  if (ls) {
    const pls = [];
    ls.querySelectorAll('[data-campo]').forEach((c) => {
      const nv = c.matches('[data-valor]') ? c : c.querySelector(':scope > [data-valor]');
      const nk = c.matches('[data-source-key]') ? c : c.querySelector(':scope > [data-source-key]');
      pls.push({
        campo: c.getAttribute('data-campo'),
        valor: nv ? (nv.getAttribute('data-valor') || '') : null,
        clave: nk ? (nk.getAttribute('data-source-key') || '') : null,
      });
    });
    const rot = document.getElementById('lectura-scalp-rotulo');
    tarjeta = {
      oculta: Boolean(ls.hidden),
      rotulo: rot ? (rot.textContent || '').trim() : null,
      parejas: pls,
    };
  }

  return {
    tarjeta_scalp: tarjeta,
    // LAS MARCAS DE LA TARJETA. `no-evaluable` y `rancio` son lo que la regla del handoff y el
    // tope de edad deciden AHORA sobre la pantalla: desde la v2 del sobre, `evaluable` ya no
    // decide la palabra, decide el rayado. Sin cosechar la clase, esa promesa no es medible.
    clases_decide: d.className || '',
    pliegue: {
      innerHeight: window.innerHeight,
      innerWidth: window.innerWidth,
      top: r.top, bottom: r.bottom, height: r.height, width: r.width,
      visible: visible,
      cabe_entero: visible && r.top >= 0 && r.bottom <= window.innerHeight,
      scrollY: window.scrollY,
      // Desplazamiento total del documento: si el primer pliegue ya exige rodar para ver
      // DECIDE, esto lo delata junto a cabe_entero.
      scrollHeight: document.documentElement.scrollHeight,
    },
    letra_mayor_px: mayor,
    letra_mayor_texto: mayorTexto,
    sesgo: sesgo ? {
      texto: (sesgo.textContent || '').trim(),
      px: parseFloat(getComputedStyle(sesgo).fontSize) || 0,
      top: rs.top, bottom: rs.bottom,
      dentro: rs.top >= 0 && rs.bottom <= window.innerHeight,
    } : null,
    parejas: parejas,
    hitos: window.MESA_HITOS || null,
  };
})()
"""


def _a_numero(v):
    """El numero que hay dentro de un texto de pantalla o de un valor servido, o None.

    Devuelve (numero, decimales_escritos). Los decimales son los que la PANTALLA escribio, y
    son la mitad del criterio de `casan_valores`.
    """
    if v is None or isinstance(v, bool):
        return None, 0
    if isinstance(v, (int, float)):
        return float(v), 6
    s = str(v).strip()
    if not s:
        return None, 0
    t = "".join(ch for ch in s if ch not in "   %").strip()
    # formato es-ES: miles con punto, decimales con coma
    cand = t.replace(".", "").replace(",", ".") if ("," in t) else t
    try:
        n = float(cand)
    except ValueError:
        return None, 0
    dec = len(cand.split(".")[1]) if "." in cand else 0
    return n, dec


# Lo que la pantalla dice de su edad, AHORA. Se lee del DOM, no del sobre: lo que se juzga es
# lo que el operador ve, no lo que el backend mando hace un rato.
JS_EDAD = r"""
(() => {
  const d = document.getElementById('decide');
  const e = document.getElementById('decide-edad');
  const sello = document.getElementById('decide-sello');
  const sesgo = document.getElementById('decide-sesgo');
  const reloj = document.getElementById('reloj');
  const texto = e ? (e.textContent || '') : '';
  // «edad del snapshot: 4.014.238,1 s (tope declarado 120 s)» -> 4014238.1
  const m = texto.match(/edad del snapshot:\s*([0-9.,]+)\s*s/);
  let edad = null;
  if (m) {
    const t = m[1];
    edad = parseFloat(t.indexOf(',') >= 0 ? t.replace(/\./g, '').replace(',', '.') : t);
  }
  return {
    edad_s: Number.isNaN(edad) ? null : edad,
    dice_rancio: /RANCIO/.test(texto) || (sello ? !sello.hidden : false),
    sello_visible: sello ? !sello.hidden : false,
    clase_rancio: d ? d.classList.contains('rancio') : false,
    sesgo: sesgo ? (sesgo.textContent || '').trim() : null,
    reloj: reloj ? (reloj.textContent || '').trim() : null,
    reloj_clase: reloj ? reloj.className : null,
  };
})()
"""


def normaliza(v) -> str:
    """Para comparar TEXTOS. Los numeros NO se comparan con esto: ver `casan_valores`."""
    if v is None:
        return ""
    return " ".join(str(v).split()).casefold()


def casan_valores(pintado, servido) -> bool:
    """La celda pinta FIELMENTE el valor servido, A LA PRECISION CON QUE LO PINTA?

    ESTE CRITERIO ESTABA MAL Y CONDENABA PAGINAS FIELES. La version anterior pasaba los dos
    lados a numero y exigia igualdad a CUATRO decimales. Pero la mesa redondea al pintar
    -`num(v, 1)`-, asi que con el backend sirviendo 63385.45 la pantalla escribe '63.385,5' y
    el check gritaba «el valor de la celda no es el servido» sobre una pantalla IMPECABLE.
    Medido por el operador el 2026-09-29: TRES hallazgos B3 en una pagina fiel. Y esa precision
    es la de produccion, no un caso de laboratorio: por esta ruta llegan hoy BTC
    nearest_support.center 82930.62, ETH horizonte 1h 2694.64, SOL 1h 119.08.

    EL CRITERIO BUENO: el texto pintado tiene que ser UN REDONDEO FIEL del valor servido, o sea
    que la diferencia no pase de MEDIA UNIDAD EN EL ULTIMO DECIMAL QUE LA PANTALLA ESCRIBIO.
    Con '63.385,5' (1 decimal) se admite +-0.05, asi que 63385.45 casa; con '71 %' (0 decimales)
    se admite +-0.5, asi que 71.429 casa. Lo que NO casa sigue sin casar: un 81.2 servido no se
    pinta como '80,20' ni con la tolerancia mas generosa de esta regla, porque la diferencia es
    1.0 contra una tolerancia de 0.005.

    NO SE USA `round()` A PROPOSITO: el redondeo de la mitad exacta difiere entre JS -medio
    hacia arriba- y Python -al par-, y esa discrepancia condenaria pantallas fieles justo en el
    borde. La distancia no tiene ese problema.
    """
    np_, dec = _a_numero(pintado)
    ns_, _ = _a_numero(servido)
    if np_ is not None and ns_ is not None:
        tolerancia = 0.5 * (10 ** -dec) + 1e-9
        return abs(ns_ - np_) <= tolerancia
    return normaliza(pintado) == normaliza(servido)


def resuelve(sobre: dict, ruta: str):
    """Sigue `a.b[0].c` dentro del sobre. Devuelve (encontrado, valor)."""
    nodo = sobre
    for tramo in ruta.replace("]", "").split("."):
        if "[" in tramo:
            nombre, idx = tramo.split("[", 1)
            if nombre:
                if not isinstance(nodo, dict) or nombre not in nodo:
                    return False, None
                nodo = nodo[nombre]
            if not isinstance(nodo, list) or int(idx) >= len(nodo):
                return False, None
            nodo = nodo[int(idx)]
        else:
            if not isinstance(nodo, dict) or tramo not in nodo:
                return False, None
            nodo = nodo[tramo]
    return True, nodo


async def corre(args) -> dict:
    # LA PUERTA ES `/` DESDE LA CAMPANA 133: la mesa se juzga donde la abre quien opera. `/mesa`
    # sigue sirviendo los mismos bytes, y eso lo comprueba el .sh antes de lanzar la sonda.
    url = args.base.rstrip("/") + args.puerta + "#" + args.marco + "/" + args.activo + (
        "/status" if args.vista == "estado" else ""
    )
    out: dict = {
        "url": url,
        "puerta": args.puerta,
        "base": args.base,
        "marco": args.marco,
        "activo": args.activo,
        "vista": args.vista,
        "ancho": args.ancho,
        "alto": args.alto,
        "medido_en": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out["barra_de_desplazamiento"] = (
        "OCULTA (--sin-barra): la ventana util es mas alta que en un navegador de escritorio"
        if args.sin_barra
        else "VISIBLE, como en un navegador de escritorio"
    )
    with Chromium(args.ancho, args.alto, ocultar_barra=args.sin_barra) as c:
        # `/json/new` EXIGE PUT desde Chromium 111 (medido aqui con 152: con GET contesta
        # 405 Method Not Allowed). Un 405 leido como "el sujeto esta roto" seria el canal
        # disfrazado de veredicto, asi que se pide como toca y si falla se cae a la pestana
        # que el navegador ya tiene abierta.
        destino = None
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{c.puerto}/json/new?about:blank", method="PUT"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                destino = json.load(r)
        except Exception:
            with urllib.request.urlopen(f"http://127.0.0.1:{c.puerto}/json/list", timeout=10) as r:
                for t in json.load(r):
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        destino = t
                        break
        if not destino or not destino.get("webSocketDebuggerUrl"):
            raise SystemExit2("chromium no dio una pestana con webSocketDebuggerUrl")
        async with websockets.connect(
            destino["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024
        ) as ws:
            s = Sesion(ws)
            await s.pide("Page.enable")
            await s.pide("Runtime.enable")
            await s.pide("Network.enable")
            await s.pide("Network.setCacheDisabled", cacheDisabled=bool(args.frio))
            await s.pide(
                "Emulation.setDeviceMetricsOverride",
                width=args.ancho,
                height=args.alto,
                deviceScaleFactor=1,
                mobile=False,
            )
            if args.cabecera:
                k, _, v = args.cabecera.partition(":")
                await s.pide("Network.setExtraHTTPHeaders", headers={k.strip(): v.strip()})

            # EL CAMINO LENTO, FORZADO DESDE EL INSTRUMENTO Y NO DESDE EL PRODUCTO.
            # C3 exige que la medida PUEDA CONDENAR: una carga por el camino lento tiene que
            # salir por encima del objetivo. El camino lento es el de antes de esta campana
            # -DECIDE esperando al sobre de ~140 KB-, y se reproduce redirigiendo la peticion
            # de `/api/mesa/decide` a `/api/ai/context`. Se hace con `Fetch` de CDP, o sea
            # FUERA del producto: la mesa no lleva ni una linea de codigo muerto para esto, y
            # cuando el navegador se cierra no queda rastro.
            if args.lento:
                await s.pide("Fetch.enable", patterns=[{"urlPattern": "*/api/mesa/decide*"}])
                out["camino"] = "LENTO FORZADO: /api/mesa/decide -> /api/ai/context"
            else:
                out["camino"] = "normal"

            def ids_decide():
                """Los requestId de las respuestas de /api/mesa/decide vistas hasta AHORA."""
                return [
                    e["params"]["requestId"]
                    for e in s.eventos
                    if e.get("method") == "Network.responseReceived"
                    and "/api/mesa/decide" in ((e["params"].get("response") or {}).get("url") or "")
                ]

            async def lee_cuerpo(ids):
                """El cuerpo de la ULTIMA respuesta de la lista, que es la que la pagina pinto."""
                for rid in reversed(ids or []):
                    try:
                        r = await s.pide("Network.getResponseBody", requestId=rid)
                        crudo = (
                            base64.b64decode(r["body"]).decode("utf-8", "replace")
                            if r.get("base64Encoded")
                            else r.get("body", "")
                        )
                        return json.loads(crudo)
                    except (SystemExit2, ValueError, KeyError):
                        continue
                return None

            def reescribe(url: str):
                if not args.lento:
                    return None
                if "/api/mesa/decide" not in url:
                    return None
                base, _, cola = url.partition("?")
                sim = ""
                for trozo in cola.split("&"):
                    if trozo.startswith("symbol="):
                        sim = trozo
                return base.replace("/api/mesa/decide", "/api/ai/context") + (
                    "?" + sim + "&profile=default" if sim else "?profile=default"
                )

            async def una_carga(primera: bool):
                """Una carga completa, cronometrada. Devuelve (decide_s, completo_s, cosecha).

                EL HITO, NO UN RELOJ. `decidePintado` lo pone la propia mesa cuando DECIDE ya
                ensena datos: esperar "2 segundos y mirar" mediria el reloj, no el hito.
                """
                # Una recarga por hash no vuelve a arrancar la mesa: hay que navegar a otra
                # cosa y volver, o la segunda medida seria de una pagina que no se recargo.
                if not primera:
                    await s.pide("Page.navigate", url="about:blank")
                    await s.drena(0.15)
                t = time.time()
                await s.pide("Page.navigate", url=url)
                fin = t + args.espera
                d_s = c_s = None
                while time.time() < fin:
                    await s.drena(0.05)
                    await s.atiende_fetch(reescribe)
                    try:
                        if d_s is None:
                            v = await s.evalua(
                                "(window.MESA_HITOS && window.MESA_HITOS.decidePintado) || null"
                            )
                            if v:
                                d_s = round(time.time() - t, 4)
                        if d_s is not None:
                            v = await s.evalua(
                                "(window.MESA_HITOS && window.MESA_HITOS.completo) || null"
                            )
                            if v:
                                c_s = round(time.time() - t, 4)
                                break
                    except SystemExit2:
                        pass
                # LA COSECHA VA CON SU PROPIO TOPE Y NO PUEDE TUMBAR LA CORRIDA. Estaba fuera
                # del `try` y era la que reventaba la medida del camino lento: si la pagina no
                # llego a pintar, aqui se devuelve None y quien lo lea declara NO MEDIDO, en vez
                # de perder tambien las cifras de tiempo que SI se habian medido.
                #
                # Y LA COSECHA Y EL SOBRE SE TOMAN JUNTOS, ATADOS AL MISMO INSTANTE. Esto es el
                # arreglo de R7 y es la TERCERA vez que esta red condenaba una pagina fiel:
                # antes la pantalla se cosechaba aqui, luego se observaba 18 s -y el refresco de
                # 15 s cae DENTRO- y solo despues se leia el cuerpo, que ya era el de la SEGUNDA
                # respuesta. O sea que comparaba la pantalla de la primera contra el sobre de la
                # segunda: «B3: edge: pantalla '80,20' / sobre 81.2» sobre una pantalla
                # impecable, con su propia linea diciendo «2 peticion(es) vistas».
                #
                # El guardia del bucle es por si un refresco cae JUSTO durante la cosecha: se
                # mira la lista de respuestas antes y despues, y si cambio se vuelve a cosechar.
                # A la tercera se declara en vez de insistir.
                cos, cuerpo, reintentos = None, None, 0
                for intento in range(3):
                    reintentos = intento
                    ids_antes = ids_decide()
                    try:
                        cos = await s.evalua(JS_COSECHA)
                    except SystemExit2 as e:
                        cos = {"error": f"la cosecha no se pudo leer: {e}"}
                        break
                    if ids_decide() == ids_antes:
                        cuerpo = await lee_cuerpo(ids_antes)
                        break
                else:
                    cos = {"error": "llegaron refrescos en las 3 cosechas: no se pudo atar "
                                    "la pantalla a una respuesta concreta"}
                return d_s, c_s, cos, cuerpo, reintentos

            # CARGA 1 = EN FRIO (la cache del navegador esta vacia recien abierto). Las
            # siguientes son EN CALIENTE, en el MISMO navegador: si cada carga abriese su
            # propio Chromium, "caliente" no existiria y las dos columnas medirian lo mismo.
            cargas = []
            for i in range(max(1, args.repite)):
                if i == 1:
                    # a partir de la segunda se deja la cache trabajar, que es lo que
                    # significa "en caliente"
                    await s.pide("Network.setCacheDisabled", cacheDisabled=False)
                d_s, c_s, cosecha, cuerpo_pintado, reint = await una_carga(primera=(i == 0))
                cargas.append(
                    {"n": i + 1, "clase": "frio" if i == 0 else "caliente",
                     "decide_s": d_s, "completo_s": c_s}
                )
            out["cargas"] = cargas
            # CUANTAS PETICIONES SE INTERCEPTARON DE VERDAD. Sin esta cuenta, un `--lento` que
            # no llegue a interceptar nada mediria el camino NORMAL y lo llamaria «lento»: el
            # control saldria por debajo del objetivo y se leeria como «el instrumento no puede
            # condenar», cuando lo que pasa es que no planto nada.
            out["fetch_atendidos"] = getattr(s, "fetch_atendidos", 0)

            # SE APAGA LA INTERCEPCION EN CUANTO ACABAN LAS CARGAS, Y ESTO ERA UN FALLO REAL:
            # con `Fetch` activo, la peticion que este programa hace DESPUES -la del sobre, para
            # comparar la pantalla con lo servido- tambien se quedaba pausada, y nadie la
            # atendia porque el bucle que las atiende ya habia terminado. Sintoma: «CDP
            # Runtime.evaluate no contesto en 30 s», o sea el instrumento acusandose a si mismo.
            if args.lento:
                await s.pide("Fetch.disable")
            out["decide_pintado_s"] = cargas[0]["decide_s"]
            out["completo_s"] = cargas[0]["completo_s"]
            out["cosecha"] = cosecha

            # LA OBSERVACION EN EL TIEMPO · lo que R3 necesita y ningun brazo de UNA SOLA FOTO
            # puede ver. Se mira la MISMA pagina, SIN recargar, durante `--observa` segundos, y
            # se apunta que dice de su edad y si ha vuelto a pedir DECIDE. Un check que solo
            # mira el instante del render da VERDE sobre una pantalla que lleva una hora
            # congelada: ese defecto solo existe DESPUES del render.
            if args.observa > 0:
                def _cuenta_decide():
                    return len(
                        [
                            e
                            for e in s.eventos
                            if e.get("method") == "Network.requestWillBeSent"
                            and "/api/mesa/decide"
                            in ((e["params"].get("request") or {}).get("url") or "")
                        ]
                    )

                pedidas0 = _cuenta_decide()
                muestras = []
                t_obs = time.time()
                while time.time() - t_obs < args.observa:
                    await s.drena(1.0)
                    try:
                        m = await s.evalua(JS_EDAD)
                    except SystemExit2:
                        break
                    if not isinstance(m, dict):
                        break
                    m["t"] = round(time.time() - t_obs, 1)
                    m["peticiones_decide"] = _cuenta_decide() - pedidas0
                    muestras.append(m)
                out["observacion"] = {"segundos": args.observa, "recargas": 0, "muestras": muestras}

            # LA RED: peticiones y bytes, de los eventos de CDP.
            peticiones, bytes_tot = {}, 0
            for e in s.eventos:
                m = e.get("method")
                p = e.get("params", {})
                if m == "Network.requestWillBeSent":
                    peticiones[p.get("requestId")] = {
                        "url": (p.get("request") or {}).get("url", ""),
                        "bytes": 0,
                        "status": None,
                    }
                elif m == "Network.responseReceived" and p.get("requestId") in peticiones:
                    peticiones[p["requestId"]]["status"] = (p.get("response") or {}).get("status")
                elif m == "Network.loadingFinished" and p.get("requestId") in peticiones:
                    n = int(p.get("encodedDataLength") or 0)
                    peticiones[p["requestId"]]["bytes"] = n
                    bytes_tot += n
            out["red"] = {
                "peticiones": len(peticiones),
                "bytes": bytes_tot,
                "detalle": sorted(
                    (
                        {
                            "url": v["url"].replace(args.base, ""),
                            "bytes": v["bytes"],
                            "status": v["status"],
                        }
                        for v in peticiones.values()
                    ),
                    key=lambda x: -x["bytes"],
                )[:30],
            }

            # EL SOBRE CONTRA EL QUE SE COMPARA ES **EL QUE LA PAGINA RECIBIO**, no otro.
            #
            # LA VERSION ANTERIOR PEDIA `/api/mesa/decide` UNA SEGUNDA VEZ desde la pagina y
            # comparaba la pantalla contra ESA respuesta. Esta mal, y no de forma sutil: DECIDE
            # cambia entre una peticion y la siguiente. Medido por el operador contra 140 el
            # 2026-09-29T06:03Z, 20 parejas de `/api/scalp/summary` separadas 2 s: `edge`
            # distinto en 20 de 20, `reason` en 20 de 20, `state` y `confidence` en 8 de 20.
            # O sea que mi red condenaba paginas FIELES por el simple hecho de que el mercado
            # se movio entre las dos peticiones -y peor: se le podia colar un cambio real,
            # porque comparaba contra un sobre que nadie pinto-.
            #
            # LO CORRECTO ES EL CUERPO DE LA RESPUESTA QUE LA PAGINA USO, que CDP guarda por
            # `requestId`. Cero peticiones extra, y el patron es EXACTAMENTE lo que se pinto.
            # Y SE TOMA JUNTO A LA COSECHA, NO DESPUES DE OBSERVAR. Leerlo aqui abajo -como se
            # hacia- significa leer el cuerpo de la ULTIMA respuesta, y si durante la
            # observacion entro un refresco esa ya no es la que la pantalla pinto. `una_carga`
            # devuelve las dos cosas atadas al mismo instante.
            if args.vista != "estado":
                out["sobre"] = cuerpo_pintado
                vistas = len(ids_decide())
                if cuerpo_pintado is None:
                    out["sobre_origen"] = (
                        f"NO SE PUDO LEER el cuerpo que recibio la pagina ({vistas} "
                        "peticion(es) vistas en toda la corrida)"
                    )
                else:
                    out["sobre_origen"] = (
                        "Network.getResponseBody del requestId que la pantalla PINTO, leido "
                        f"junto a la cosecha ({reint} reintento(s) por refresco); {vistas} "
                        "peticion(es) a /api/mesa/decide en toda la corrida; CERO peticiones extra"
                    )

            if args.captura:
                r = await s.pide(
                    "Page.captureScreenshot", tope=90.0, format="png", captureBeyondViewport=False
                )
                pathlib.Path(args.captura).write_bytes(base64.b64decode(r["data"]))
                out["captura"] = args.captura
            if args.captura_entera:
                r = await s.pide(
                    "Page.captureScreenshot", tope=90.0, format="png", captureBeyondViewport=True
                )
                pathlib.Path(args.captura_entera).write_bytes(base64.b64decode(r["data"]))
                out["captura_entera"] = args.captura_entera

            consola = [
                (e.get("params", {}).get("args") or [{}])[0].get("value")
                for e in s.eventos
                if e.get("method") == "Runtime.consoleAPICalled"
                and e.get("params", {}).get("type") == "error"
            ]
            out["errores_consola"] = [str(x)[:200] for x in consola if x][:10]
            await s.cierra()
    return out


def compara(out: dict) -> dict:
    """Empareja lo servido con lo pintado. Devuelve el reparto, sin dar veredictos."""
    sobre = out.get("sobre") or {}
    cosecha = out.get("cosecha") or {}
    parejas = {p["campo"]: p for p in (cosecha.get("parejas") or [])}
    dec = (sobre or {}).get("decide") or {}

    casan, discrepan, no_pintados, sin_clave = [], [], [], []
    for nombre in CAMPOS_ESCALARES:
        campo = dec.get(nombre)
        if not isinstance(campo, dict):
            continue
        servido = campo.get("value")
        if servido is None or servido == "":
            continue  # un «no se» servido no obliga a pintar un valor
        p = parejas.get(nombre)
        if p is None:
            no_pintados.append({"campo": nombre, "servido": servido})
            continue
        if not p.get("clave"):
            sin_clave.append({"campo": nombre, "servido": servido})
            continue
        # LA PAREJA: la clave de la celda tiene que ser la del sobre, y el valor el mismo.
        if p["clave"] != campo.get("source_key"):
            discrepan.append(
                {
                    "campo": nombre,
                    "motivo": "la clave de la celda no es la servida",
                    "clave_pantalla": p["clave"],
                    "clave_sobre": campo.get("source_key"),
                }
            )
            continue
        if not casan_valores(p.get("valor"), servido):
            discrepan.append(
                {
                    "campo": nombre,
                    "motivo": "el valor de la celda no es el servido",
                    "pantalla": p.get("valor"),
                    "sobre": servido,
                }
            )
            continue
        # Y LA CLAVE TIENE QUE RESOLVER EN EL SOBRE: una clave inventada que casualmente
        # coincida con el texto no vale como procedencia.
        hay, _ = resuelve(sobre, str(campo.get("source_key")))
        casan.append({"campo": nombre, "clave": campo.get("source_key"), "clave_resuelve": hay})

    for nombre in CAMPOS_LISTA:
        entradas = dec.get(nombre)
        if not isinstance(entradas, list):
            continue
        for i, campo in enumerate(entradas):
            if not isinstance(campo, dict):
                continue
            servido = campo.get("value")
            if servido is None or servido == "":
                continue
            p = parejas.get(f"{nombre}[{i}]")
            if p is None:
                no_pintados.append({"campo": f"{nombre}[{i}]", "servido": servido})
                continue
            if p.get("clave") != campo.get("source_key"):
                discrepan.append(
                    {
                        "campo": f"{nombre}[{i}]",
                        "motivo": "la clave de la celda no es la servida",
                        "clave_pantalla": p.get("clave"),
                        "clave_sobre": campo.get("source_key"),
                    }
                )
                continue
            if not casan_valores(p.get("valor"), servido):
                discrepan.append(
                    {
                        "campo": f"{nombre}[{i}]",
                        "motivo": "el valor de la celda no es el servido",
                        "pantalla": p.get("valor"),
                        "sobre": servido,
                    }
                )
                continue
            casan.append({"campo": f"{nombre}[{i}]", "clave": campo.get("source_key")})

    # UN CONTROL DE HOMONIMIA DENTRO DEL PROPIO INSTRUMENTO (A41): una clave que el sobre NO
    # sirve no puede aparecer como procedencia de ninguna celda.
    claves_sobre = set()

    def recoge(nodo):
        if isinstance(nodo, dict):
            if "source_key" in nodo and isinstance(nodo["source_key"], str):
                claves_sobre.add(nodo["source_key"])
            for v in nodo.values():
                recoge(v)
        elif isinstance(nodo, list):
            for v in nodo:
                recoge(v)

    recoge(dec)
    claves_pantalla = {p["clave"] for p in parejas.values() if p.get("clave")}
    out["claves_de_pantalla_que_el_sobre_no_sirve"] = sorted(claves_pantalla - claves_sobre)

    out["reparto"] = {
        "casan": casan,
        "discrepan": discrepan,
        "no_pintados": no_pintados,
        "sin_clave": sin_clave,
        "n_casan": len(casan),
        "n_discrepan": len(discrepan),
        "n_no_pintados": len(no_pintados),
        "n_sin_clave": len(sin_clave),
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="p.ej. http://127.0.0.1:8099")
    ap.add_argument("--puerta", default="/", choices=("/", "/mesa"),
                    help="la ruta de pantalla que se abre: `/` desde la campana 133")
    ap.add_argument("--marco", default="scalp", choices=("scalp", "swing", "largo"))
    ap.add_argument("--activo", default="BTC", choices=("BTC", "ETH", "SOL"))
    ap.add_argument("--vista", default="mesa", choices=("mesa", "estado"))
    ap.add_argument("--ancho", type=int, default=1920)
    ap.add_argument("--alto", type=int, default=1080)
    ap.add_argument("--espera", type=float, default=30.0)
    ap.add_argument(
        "--observa",
        type=float,
        default=0.0,
        help="segundos mirando la MISMA pagina sin recargar, apuntando que dice de su edad. "
             "Es lo unico que puede ver una pantalla que se congela DESPUES del render",
    )
    ap.add_argument(
        "--repite",
        type=int,
        default=1,
        help="cargas en el MISMO navegador: la 1 es en frio, las demas en caliente",
    )
    ap.add_argument("--frio", action="store_true", help="sin cache del navegador")
    ap.add_argument(
        "--sin-barra",
        action="store_true",
        help="oculta la barra de desplazamiento. POR OMISION NO se oculta: la mesa se juzga "
             "en las condiciones de quien la usa, no en una ventana mas alta que la real",
    )
    ap.add_argument(
        "--lento",
        action="store_true",
        help="fuerza el camino de ANTES (DECIDE esperando al sobre): es el control de C3",
    )
    ap.add_argument("--captura", default=None)
    ap.add_argument("--captura-entera", default=None)
    ap.add_argument("--cabecera", default=os.environ.get("K102_CABECERA") or None)
    ap.add_argument(
        "--cabecera-fichero",
        default=None,
        help="lee la cabecera de un fichero (modo 600). Asi la credencial de nginx NO aparece "
             "en la linea de ordenes ni en el entorno del proceso (A55)",
    )
    ap.add_argument("--salida", default=None, help="escribe el JSON aqui en vez de stdout")
    a = ap.parse_args()

    if a.cabecera_fichero:
        try:
            a.cabecera = pathlib.Path(a.cabecera_fichero).read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"NO MEDIDO: no se pudo leer la cabecera de {a.cabecera_fichero}: {e}",
                  file=sys.stderr)
            return 2

    # UN TECHO DE RELOJ PARA TODA LA CORRIDA. No es cinturon de mas: la corrida del
    # 2026-09-29T04:04Z se colgo 16.5 min y hubo que matarla a mano, sin cifra. Con esto, un
    # fallo que no haya previsto sale como NO MEDIDO -que se lee y se arregla- en vez de como
    # un proceso que nadie sabe si sigue midiendo.
    techo = 60.0 + a.espera * max(1, a.repite) * 1.5 + a.observa * 1.5

    async def con_techo():
        try:
            return await asyncio.wait_for(corre(a), timeout=techo)
        except TimeoutError as e:
            raise SystemExit2(
                f"la corrida entera paso de {techo:g} s (espera={a.espera:g} x repite={a.repite})"
            ) from e

    try:
        out = asyncio.run(con_techo())
    except SystemExit2 as e:
        print(f"NO MEDIDO: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"NO MEDIDO: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    out = compara(out)
    texto = json.dumps(out, ensure_ascii=False, indent=1)
    if a.salida:
        pathlib.Path(a.salida).write_text(texto, encoding="utf-8")
        print(a.salida)
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
