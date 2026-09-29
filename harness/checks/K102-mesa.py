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
    def __init__(self, ancho: int, alto: int):
        self.ancho, self.alto = ancho, alto
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
                "--hide-scrollbars",
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

  return {
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


def normaliza(v) -> str:
    """Compara valores de pantalla con valores servidos sin pelearse con el formato.

    `num()` del cliente escribe 83.546,40 y el backend sirve 83546.4: son EL MISMO numero. Se
    normaliza a numero cuando ambos lo son, y a texto plegado cuando no.
    """
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    t = s.replace(" ", " ").replace("%", "").strip()
    # formato es-ES: miles con punto, decimales con coma
    cand = t.replace(".", "").replace(",", ".") if ("," in t) else t.replace(" ", "")
    try:
        return f"{float(cand):.4f}".rstrip("0").rstrip(".")
    except ValueError:
        pass
    try:
        return f"{float(t):.4f}".rstrip("0").rstrip(".")
    except ValueError:
        pass
    return " ".join(s.split()).casefold()


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
    url = args.base.rstrip("/") + "/mesa#" + args.marco + "/" + args.activo + (
        "/status" if args.vista == "estado" else ""
    )
    out: dict = {
        "url": url,
        "base": args.base,
        "marco": args.marco,
        "activo": args.activo,
        "vista": args.vista,
        "ancho": args.ancho,
        "alto": args.alto,
        "medido_en": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with Chromium(args.ancho, args.alto) as c:
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
                try:
                    cos = await s.evalua(JS_COSECHA)
                except SystemExit2 as e:
                    cos = {"error": f"la cosecha no se pudo leer: {e}"}
                return d_s, c_s, cos

            # CARGA 1 = EN FRIO (la cache del navegador esta vacia recien abierto). Las
            # siguientes son EN CALIENTE, en el MISMO navegador: si cada carga abriese su
            # propio Chromium, "caliente" no existiria y las dos columnas medirian lo mismo.
            cargas = []
            for i in range(max(1, args.repite)):
                if i == 1:
                    # a partir de la segunda se deja la cache trabajar, que es lo que
                    # significa "en caliente"
                    await s.pide("Network.setCacheDisabled", cacheDisabled=False)
                d_s, c_s, cosecha = await una_carga(primera=(i == 0))
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

            # EL SOBRE SERVIDO, PEDIDO POR LA PROPIA PAGINA (mismo origen, misma auth que la
            # mesa). Es el patron contra el que se comparan las parejas.
            if args.vista != "estado":
                sobre = await s.evalua(
                    "fetch('/api/mesa/decide?symbol=' + encodeURIComponent("
                    "  ({BTC:'BTCUSDT_PERP.A',ETH:'ETHUSDT_PERP.A',SOL:'SOLUSDT_PERP.A'})"
                    f"['{args.activo}']) + '&frame={args.marco}')"
                    ".then(r => r.ok ? r.json() : ({__http: r.status}))"
                    ".catch(e => ({__error: String(e)}))"
                )
                out["sobre"] = sobre

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
        if normaliza(p.get("valor")) != normaliza(servido):
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
            if normaliza(p.get("valor")) != normaliza(servido):
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
    ap.add_argument("--marco", default="scalp", choices=("scalp", "swing", "largo"))
    ap.add_argument("--activo", default="BTC", choices=("BTC", "ETH", "SOL"))
    ap.add_argument("--vista", default="mesa", choices=("mesa", "estado"))
    ap.add_argument("--ancho", type=int, default=1920)
    ap.add_argument("--alto", type=int, default=1080)
    ap.add_argument("--espera", type=float, default=30.0)
    ap.add_argument(
        "--repite",
        type=int,
        default=1,
        help="cargas en el MISMO navegador: la 1 es en frio, las demas en caliente",
    )
    ap.add_argument("--frio", action="store_true", help="sin cache del navegador")
    ap.add_argument(
        "--lento",
        action="store_true",
        help="fuerza el camino de ANTES (DECIDE esperando al sobre): es el control de C3",
    )
    ap.add_argument("--captura", default=None)
    ap.add_argument("--captura-entera", default=None)
    ap.add_argument("--cabecera", default=os.environ.get("K102_CABECERA") or None)
    ap.add_argument("--salida", default=None, help="escribe el JSON aqui en vez de stdout")
    a = ap.parse_args()

    # UN TECHO DE RELOJ PARA TODA LA CORRIDA. No es cinturon de mas: la corrida del
    # 2026-09-29T04:04Z se colgo 16.5 min y hubo que matarla a mano, sin cifra. Con esto, un
    # fallo que no haya previsto sale como NO MEDIDO -que se lee y se arregla- en vez de como
    # un proceso que nadie sabe si sigue midiendo.
    techo = 60.0 + a.espera * max(1, a.repite) * 1.5

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
