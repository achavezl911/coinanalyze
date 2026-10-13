#!/usr/bin/env python3
"""K106-vista · abre la vista ENTRADAS de la mesa en un Chromium de verdad y la JUZGA (campana 137).

Reutiliza el cliente CDP de K102-mesa.py (Chromium, Sesion, casan_valores, resuelve). Lo pintado se
compara con LA RESPUESTA QUE ESA PANTALLA PINTO -el cuerpo de la ultima peticion de la ruta antes
de la cosecha, leido por CDP (A76)- y a la precision con que se pinta (A77).

LOS BRAZOS, y que condena cada uno:
  E1 existe      la vista no esta, o no pinto nada ni dijo por que
  E2 fiel        un nodo data-k cuyo texto no es el valor servido en su ruta; un plan servido que no
                 se ve, o uno pintado que nadie sirvio; un plan en el bloque de otra version; un
                 DISPARADO sin su plan ENTERO
  E3 reloj       una edad o una cuenta atras que no sale de su instante servido, o que no avanza
  E4 sin dato    la ruta caida, «no disponible» o el generador parado sin decirlo ARRIBA y en grande,
                 o con algo todavia en pantalla como vivo; un DISPARADO caducado que sigue «vivo»
  E5 no puede    una fraccion, un porcentaje o una tasa de los planes, o una palabra que promete
  E6 orden       un orden que no es por estado y por hora; un color que no sale de la clase
  E7 decide      la palabra pintada no es la servida, o su frase es la de OTRA palabra (A83)
  E8 peso        la vista pide una ruta que no es de su papel, o mas bytes que su presupuesto, o la
                 respuesta trae hojas que la pantalla no pinta ni usa

LAS CIFRAS QUE LA VISTA SI PUEDE LLEVAR, una a una, y por que ninguna es una tasa de aciertos (A84):
  precio          un nivel del plan o el ultimo cierre: unidades de precio
  distancia-pct   lo que separa una zona del precio, en % DEL PRECIO: mide distancia, no aciertos
  bps             distancia al stop o a T1, o coste de una pata: diezmilesimas del precio
  x-objetivo      coste como fraccion de la distancia a T1 («x0,04 del objetivo»): un coste
  r               R bruto y neto del PLAN: beneficio a T1 entre riesgo al stop, de su foto
  p-equilibrio    la p a partir de la cual el plan no pierde, calculada de su R y sus costes ANTES
                  de saber como acaba: es del plan, no de un resultado
  recuento        cuantas filas hay en un estado: un numero de planes, sin denominador
  dias            lo que le queda al calendario
  muestra         el rotulo «... (n/30)»: la UNICA barra permitida; cuenta resueltos contra el minimo
                  de exposicion, con n < minimo, y no lleva porcentaje
  y, calculadas por el reloj: una edad y una cuenta atras (horas, minutos, segundos)
Los MOTIVOS y REGLAS servidos (prosa del registro o del reglamento) se pintan tal cual y pueden
contar minutos («58 de 60 minutos») o citar su alfa; se exige que sean EXACTAMENTE lo servido.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("k102_mesa", AQUI / "K102-mesa.py")
K = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(K)

RUTA = "/api" + "/mesa/entradas"
CONTRATO = AQUI / "K44-contrato-mesa.tsv"
# Lo que una peticion de la vista puede pesar. Medido el 2026-10-13 con datos de produccion: la
# respuesta mas gorda es la de SOL, 29 600 B (43 sombras y 1 disparado en 24 h). La ruta ENTERA del
# registro pesa 253 278 B, y de 49 037 a 130 232 B para un solo activo.
PRESUPUESTO_B = 48_000
BORDE_S = 2.5

CIFRAS = {  # clase -> como se escribe (es-ES). Nada fuera de aqui puede ser una cifra.
    "precio": r"-?\d{1,3}(\.\d{3})*(,\d+)?|-?\d+(,\d+)?",
    "distancia-pct": r"\d+,\d{2} %",
    "bps": r"\d+(\.\d{3})*,\d{1,2} bps",
    "x-objetivo": r"x\d+,\d{2} del objetivo",
    "r": r"-?\d+,\d{2}",
    "p-equilibrio": r"0,\d{3}|1,000",
    "recuento": r"\d+",
    "dias": r"-?\d+(\.\d{3})*,\d d",
    "muestra": r".*\((\d+)/(\d+)\)",
}
# Prosa servida: reglas, motivos y textos del reglamento. Se exige igualdad exacta con lo servido
# (E2) y por eso no se le busca forma de cifra; las palabras que prometen se le buscan igual.
PROSA = re.compile(r"(\.motivo|\.regla|\.reloj|\.frase|\.fuente|\.definicion|\.sin_planes|\.tipo_disparo|"
                   r"\.resueltos_motivo|\.por_que_este_marco|\.etiqueta|\.que|\.error|"
                   r"^que_es|^vivo\.que_es|^marco\.cuentas_ambito|^reciente\.falta_el_resultado|"
                   r"^reciente\.recortada|^marco\.hipotesis_activa\.\w+|^frescura\.regla|"
                   r"^generador\.pasada_en_curso)$")
FRACCION = re.compile(r"\d\s*/\s*\d|\d\s*%|\d+\s+de\s+(cada\s+)?\d+|\bpor\s+cien(to)?\b", re.I)
TASA = re.compile(r"\b(tasas?|aciertos?|acert\w+|win ?rate|hit ?rate|probabilidad(es)?|frecuencias?|"
                  r"[eé]xitos?)\b", re.I)
PROMESA = re.compile(r"\b(favorables?|alta probabilidad|probabilidad alta|buenas? (entrada|oportunidad)\w*|"
                     r"oportunidad(es)?|recomendad[oa]s?|recomendaci[oó]n|garantizad[oa]s?|ganador(a|es)?|"
                     r"entrada (segura|[oó]ptima|clara)|seguro que|va a (subir|bajar))\b", re.I)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
# Lo que la respuesta trae y la pantalla NO pinta como texto, con su motivo. Todo lo demas se pinta.
NO_SE_PINTA = re.compile(
    r"^(esquema|symbol|disponible|motivo)$"                      # identidad; el motivo va en el aviso
    r"|^frescura\.(refresco_s|sin_dato_s|sin_dato_frase)$"         # la cadencia y el tope del reloj; el aviso
    r"|^generador\.(tope_s|parado_frase)$"                          # el tope del reloj; el aviso
    r"|^decide\.(edad_s|max_age_s)$"                                # las usa el reloj
    r"|^decide\.perfiles\.\w+\.(palabra|sin_respuesta|motivo)$"     # van en `rotulo` y en `frase`
    r"|\.para\.\w+\.relacion$|^vivo\.rotulos\.\w+$"                # claves de presentacion
    r"|\.(registro_id|caducado|vivo|caducidad_min)$"               # identidad y banderas del reloj
    r"|\.no_puede\.requisitos\[\d+\]$"                             # va dentro de su frase
    r"|^marco\.disponible$"
    r"|\.muestra\.(n|minimo)$"                                     # van dentro del rotulo
    r"|^vivo\.celdas\[\d+\]\.por_version\[\d+\]\.(vigilando|disparados)\[\d+\]\.(perfil|lado)$"  # los dice la celda
)

JS = r"""
(() => {
  const raiz = document.getElementById('vista-entradas');
  if (!raiz) return {existe: false, mesa: !!document.getElementById('vista-mesa')};
  const visible = (n) => {
    for (let x = n; x && x !== document.documentElement; x = x.parentElement) {
      if (x.hidden || getComputedStyle(x).display === 'none') return false;
    }
    return true;
  };
  const txt = (n) => (n.innerText || '').replace(/\s+/g, ' ').trim();
  const dat = (n, sel, k) => { const x = n.closest(sel); return x ? x.dataset[k] : null; };
  const clon = raiz.cloneNode(true);
  clon.querySelectorAll('[hidden],[data-k],[data-calc]').forEach((n) => n.remove());
  const top = (id) => { const n = document.getElementById(id); return n ? n.getBoundingClientRect().top + window.scrollY : null; };
  return {
    existe: true,
    oculta: raiz.hidden,
    ahora: Date.now() / 1000,
    hash: location.hash,
    nodos: [...raiz.querySelectorAll('[data-k]')].map((n) => ({
      k: n.dataset.k, t: txt(n), cifra: n.dataset.cifra || null, vis: visible(n), plan: dat(n, '[data-plan]', 'plan'),
      seccion: n.closest('#ent-vivo') ? 'vivo' : n.closest('#ent-reciente') ? 'reciente' : null })),
    calc: [...raiz.querySelectorAll('[data-calc]')].map((n) => ({
      tipo: n.dataset.calc, instante: n.dataset.instante, t: txt(n), vis: visible(n) })),
    planes: [...raiz.querySelectorAll('[data-plan]')].map((n) => ({
      id: Number(n.dataset.plan), version: n.dataset.version, tipo: n.dataset.tipo, vivo: n.dataset.vivo || null,
      seccion: n.closest('#ent-vivo') ? 'vivo' : 'reciente', bloque: dat(n, '[data-bloque-version]', 'bloqueVersion'),
      papel: dat(n, '[data-bloque-version]', 'papel'), celda: dat(n, '[data-celda]', 'celda'),
      chip: n.querySelector('[data-chip]') ? txt(n.querySelector('[data-chip]')) : null,
      clases: n.className, ver: n.querySelector('.ent-ver') ? txt(n.querySelector('.ent-ver')) : null })),
    bloques: [...raiz.querySelectorAll('[data-bloque-version]')].map((n) => ({
      version: n.dataset.bloqueVersion, papel: n.dataset.papel, celda: dat(n, '[data-celda]', 'celda'),
      seccion: n.closest('#ent-vivo') ? 'vivo' : 'reciente' })),
    avisos: [...raiz.querySelectorAll('[data-aviso]')].map((n) => ({
      cual: n.dataset.aviso, t: txt(n), vis: visible(n), top: n.getBoundingClientRect().top + window.scrollY,
      px: parseFloat(getComputedStyle(n).fontSize) })),
    tops: {cabeza: top('ent-cabeza'), decide: top('ent-decide'), vivo: top('ent-vivo')},
    alto: window.innerHeight,
    literal: (clon.textContent || '').replace(/\s+/g, ' ').trim(),
    visible_todo: txt(raiz),
    colores: [...raiz.querySelectorAll('*')].filter(visible).map((n) => {
      const cs = getComputedStyle(n);
      const camino = [];
      for (let x = n; x && x !== raiz; x = x.parentElement) camino.push(x.tagName + '.' + x.className);
      return {camino: camino.join(' < ') + ' @' + raiz.className, color: cs.color, fondo: cs.backgroundColor,
              borde: cs.borderTopColor + ' ' + cs.borderLeftColor, estilo: n.getAttribute('style') || '',
              clases: n.className};
    }),
    palabras: [...raiz.querySelectorAll('[data-decide]')].map((n) => {
      const p = n.querySelector('.ent-palabra');
      return {perfil: n.dataset.decide, palabra: p ? p.dataset.palabra : null, rotulo: p ? txt(p) : null,
              clases: p ? p.className : null,
              frase: [...n.querySelectorAll('.ent-frase')].filter(visible).map(txt).join(' | ')};
    }),
    relaciones: [...raiz.querySelectorAll('[data-celda]')].map((n) => ({
      celda: n.dataset.celda,
      visibles: [...n.querySelectorAll('.ent-rel')].filter(visible).map((x) => ({t: txt(x), k: x.dataset.k, clases: x.className})) })),
    clases_raiz: raiz.className,
    desborda: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  };
})()
"""


def hojas(nodo, ruta=""):
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            yield from hojas(v, f"{ruta}.{k}" if ruta else k)
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            yield from hojas(v, f"{ruta}[{i}]")
    elif nodo is not None and nodo != "":
        yield ruta, nodo


def hora(iso, seg=False):
    t = str(iso)
    return t[5:10] + " " + t[11:19 if seg else 16] + "Z"


def casa(nodo, servido) -> bool:
    """El texto del nodo es lo servido? Un instante se pinta como su hora; una lista, unida."""
    t = nodo["t"]
    if servido is None:
        return t == "" or t.startswith("NULO") or t.startswith("SIN DATO")
    if isinstance(servido, list):
        return K.normaliza(t) == K.normaliza(", ".join(map(str, servido)))
    if isinstance(servido, str) and ISO.match(servido):
        return t in (hora(servido), hora(servido, True))
    if nodo["cifra"] and nodo["cifra"] != "muestra":
        # LA VISTA ESCRIBE EN es-ES: el punto es SIEMPRE de miles y la coma el decimal. «63.385» son
        # sesenta y tres mil; leerlo como 63,385 condenaria una pagina fiel (K102._a_numero solo
        # quita los puntos cuando hay coma). Se compara a la precision pintada (A77).
        numero = re.search(r"-?\d[\d.]*(,\d+)?", t)
        if not numero or isinstance(servido, (str, bool)):
            return False
        entero, _, decimales = numero.group(0).partition(",")
        pintado = float(entero.replace(".", "") + ("." + decimales if decimales else ""))
        return abs(float(servido) - pintado) <= 0.5 * 10 ** -len(decimales) + 1e-9
    if isinstance(servido, str):
        return K.normaliza(t) in (K.normaliza(servido), K.normaliza(servido.replace("_", " ")))
    return K.casan_valores(t, servido)


def segundos(texto: str):
    """«2 h 13 min» -> (7980, 60): los segundos que dice y la resolucion con que lo dice."""
    valor, fino = 0, None
    for n, u in re.findall(r"(\d+) (d|h|min|s)\b", texto):
        paso = {"d": 86400, "h": 3600, "min": 60, "s": 1}[u]
        valor += int(n) * paso
        fino = paso
    return (valor, fino) if fino else (None, None)


def roles() -> dict[str, set[str]]:
    salida = {}
    for linea in CONTRATO.read_text(encoding="utf-8").splitlines():
        c = linea.split("\t")
        if len(c) >= 2 and c[0].startswith("/api/"):
            salida[c[0]] = {x.strip() for x in c[1].split(",") if x.strip()}
    return salida


def juzga(c: dict, cuerpo: dict | None, ultimo: dict | None, pasado: float, pets: list[dict],
          antes: dict | None = None) -> list[str]:
    """Los hallazgos de UNA cosecha. `cuerpo` es la ultima respuesta BUENA -la que la pantalla
    pinta- y `ultimo` el ultimo intento: si ese fallo, la pantalla tiene que decirlo."""
    h: list[str] = []
    ok = bool(ultimo) and ultimo["estado"] == 200 and ultimo["disponible"]
    visibles = [n for n in c["nodos"] if n["vis"]]

    # ---- E2 · fiel a su respuesta
    if cuerpo:
        for n in visibles:
            hay, servido = K.resuelve(cuerpo, n["k"])
            if not hay:
                h.append(f"E2 pinta {n['k']} = {n['t'][:40]!r}, que la respuesta no sirve")
            elif not casa(n, servido):
                h.append(f"E2 {n['k']}: pinta {n['t'][:50]!r} y la respuesta sirve {str(servido)[:50]!r}")
        servidos = {}
        for celda in cuerpo["vivo"]["celdas"]:
            for v in celda["por_version"]:
                for tipo, nombre in (("disparados", "disparado"), ("vigilando", "vigilando")):
                    for p in v[tipo]:
                        servidos[("vivo", p["registro_id"])] = (v["version"], nombre, f"{celda['perfil']}/{celda['lado']}")
        for v in cuerpo["reciente"]["por_version"]:
            for tipo, nombre in (("disparados", "disparado"), ("sombras", "sombra")):
                for p in v[tipo]:
                    servidos[("reciente", p["registro_id"])] = (v["version"], nombre, None)
        pintados = {(p["seccion"], p["id"]): p for p in c["planes"]}
        for clave, (version, tipo, celda) in servidos.items():
            p = pintados.get(clave)
            if p is None:
                h.append(f"E2 el plan {clave[1]} ({version}, {tipo}) esta servido en «{clave[0]}» y no se ve")
                continue
            if p["bloque"] != version or p["version"] != version or p["ver"] != version:
                h.append(f"E2 el plan {clave[1]} es de {version} y se pinta como {p['ver']} en el bloque de {p['bloque']}: dos versiones confundidas")
            if celda and p["celda"] != celda:
                h.append(f"E2 el plan {clave[1]} es de {celda} y se pinta en la celda {p['celda']}")
        for clave in pintados:
            if clave not in servidos:
                h.append(f"E2 se pinta el plan {clave[1]} en «{clave[0]}» y la respuesta no lo sirve ahi")
        papel_de = {v["version"]: v["papel"] for v in cuerpo["reciente"]["por_version"]}
        for b in c["bloques"]:
            if papel_de.get(b["version"]) != b["papel"]:
                h.append(f"E2 el bloque de {b['version']} dice {b['papel']!r} y la respuesta dice {papel_de.get(b['version'])!r}")
        ks = {n["k"] for n in visibles}
        for ruta, _ in hojas(cuerpo):
            if re.search(r"\.disparados\[\d+\]\.", ruta) and not NO_SE_PINTA.search(ruta) and ruta not in ks:
                h.append(f"E2 un DISPARADO sin su plan entero: {ruta} esta servido y no se ve")

    # ---- E3 · el reloj: cada edad y cada cuenta atras sale de su instante servido
    if cuerpo:
        as_of = _epoch(cuerpo["as_of"])
        for n in c["calc"]:
            if not n["vis"] or n["tipo"] == "edad-decide":
                continue
            dicho, fino = segundos(n["t"])
            if dicho is None or not n["instante"]:
                h.append(f"E3 una {n['tipo']} sin cifra o sin instante: {n['t']!r}")
                continue
            real = (as_of - _epoch(n["instante"])) + pasado
            if n["tipo"] == "cuenta":
                real = -real if n["t"].startswith("caduca en") else real
            real = max(real, 0.0)
            if not ok and n["tipo"] == "cuenta":
                continue  # sin dato la cuenta atras no se ensena: lo juzga E4
            if not (-fino - 3 <= real - dicho <= fino + 3):
                h.append(f"E3 {n['tipo']} {n['t']!r}: desde su instante servido son {real:.0f} s")
        if antes is not None:
            quietas = [a["t"] for a, d in zip(antes["calc"], c["calc"], strict=False)
                       if a["vis"] and d["vis"] and a["t"] == d["t"] and (segundos(a["t"])[1] or 99) == 1]
            if quietas:
                h.append(f"E3 {len(quietas)} cifra(s) del reloj que se pintan al segundo NO avanzaron: {quietas[0]!r}")

    # ---- E4 · sin dato: se dice ARRIBA y en grande, y nada queda en pantalla como vivo
    debe = []
    en_el_borde = False
    if not ok:
        debe.append("la ruta no dio dato" + (" (no se pidio)" if not ultimo else " (no disponible)"
                                             if ultimo["estado"] == 200 else f" (HTTP {ultimo['estado']})"))
    else:
        lat = cuerpo["generador"]["ultimo_latido"]
        sin_latir = None if lat is None else (_epoch(cuerpo["as_of"]) - _epoch(lat["registered_at"])) + pasado
        if lat is None or sin_latir > cuerpo["generador"]["tope_s"]:
            debe.append("el generador no late desde hace mas que su tope")
        if pasado > cuerpo["frescura"]["sin_dato_s"]:
            debe.append("la ultima respuesta buena pasa de su tope")
        # A MENOS DE 2,5 s DE UN TOPE no se juzga: la pantalla late cada segundo y la sonda mira en
        # un instante; cada una puede estar a un lado del cruce sin que ninguna mienta.
        en_el_borde = (abs(pasado - cuerpo["frescura"]["sin_dato_s"]) < BORDE_S
                       or (sin_latir is not None and abs(sin_latir - cuerpo["generador"]["tope_s"]) < BORDE_S))
    avisos = [a for a in c["avisos"] if a["vis"]]
    vivos = [p for p in c["planes"] if p["seccion"] == "vivo" and p["vivo"] == "si"]
    if ok and en_el_borde:
        pass
    elif debe:
        if not avisos:
            h.append(f"E4 {debe[0]} y la vista NO lo dice arriba")
        else:
            otros = [t for t in c["tops"].values() if t is not None]
            if any(a["top"] > min(otros) for a in avisos if otros) or avisos[0]["top"] > c["alto"]:
                h.append("E4 el aviso de sin dato no esta ARRIBA, por encima de todo lo demas")
            if min(a["px"] for a in avisos) < 18:
                h.append(f"E4 el aviso de sin dato no va en grande ({min(a['px'] for a in avisos):g} px)")
        if vivos:
            h.append(f"E4 {debe[0]} y {len(vivos)} plan(es) siguen en pantalla como vivos (el {vivos[0]['id']})")
    elif avisos:
        h.append(f"E4 la vista avisa de sin dato sin motivo: {avisos[0]['t'][:60]!r}")
    if cuerpo and ok and not debe:
        as_of = _epoch(cuerpo["as_of"])
        caduca = {p["registro_id"]: p["caduca_en"] for cel in cuerpo["vivo"]["celdas"]
                  for v in cel["por_version"] for p in v["disparados"]}
        rot = cuerpo["vivo"]["rotulos"]
        for p in c["planes"]:
            if p["seccion"] != "vivo":
                continue
            if p["tipo"] == "disparado":
                resta = _epoch(caduca[p["id"]]) - as_of - pasado if p["id"] in caduca else None
                if resta is not None and resta < -2 and (p["vivo"] == "si" or p["chip"] == rot["disparado_vivo"]):
                    h.append(f"E4 el DISPARADO {p['id']} caduco hace {-resta:.0f} s y sigue en pantalla como vivo")
                if resta is not None and resta > 2 and p["chip"] != rot["disparado_vivo"]:
                    h.append(f"E4 el DISPARADO {p['id']} esta vivo y su estado dice {p['chip']!r}")
            elif p["chip"] != rot["vigilando"]:
                h.append(f"E4 el VIGILANDO {p['id']} lleva el estado {p['chip']!r}")

    # ---- E5 · lo que la vista no puede decir
    for cual, texto in (("fraccion o porcentaje", FRACCION), ("palabra de tasa", TASA), ("palabra que promete", PROMESA)):
        m = texto.search(c["literal"])
        if m:
            h.append(f"E5 {cual} en el texto de la pantalla: «{c['literal'][max(0, m.start() - 25):m.end() + 25]}»")
    for n in visibles:
        m = PROMESA.search(n["t"])
        if m:
            h.append(f"E5 palabra que promete en {n['k']}: «{m.group(0)}»")
        if n["cifra"]:
            if n["cifra"] not in CIFRAS:
                h.append(f"E5 {n['k']} es una cifra de clase {n['cifra']!r}, que no esta entre las permitidas")
            elif not re.fullmatch(CIFRAS[n["cifra"]], n["t"]):
                h.append(f"E5 {n['k']} ({n['cifra']}) se escribe {n['t']!r}, que no es la forma de su clase")
            elif n["cifra"] == "muestra":
                a, b = map(int, re.fullmatch(CIFRAS["muestra"], n["t"]).groups())
                if a >= b:
                    h.append(f"E5 el rotulo de muestra {n['t']!r} no es de muestra insuficiente")
        elif not PROSA.search(n["k"]):
            for cual, texto in (("fraccion o porcentaje", FRACCION), ("palabra de tasa", TASA)):
                m = texto.search(n["t"])
                if m and not ISO.match(str(K.resuelve(cuerpo or {}, n["k"])[1] or "")):
                    h.append(f"E5 {cual} en {n['k']}: {n['t'][:60]!r}")

    # ---- E6 · el orden es por estado y por hora; el color sale de la clase y de nada mas
    if cuerpo and ok:
        orden = [(p["seccion"], p["bloque"], p["celda"], p["tipo"], p["id"]) for p in c["planes"]]
        hora_de = {}
        for ruta, v in hojas(cuerpo):
            m = re.match(r"(.*\[\d+\])\.vela_cierre$", ruta)
            if m:
                hora_de[K.resuelve(cuerpo, m.group(1) + ".registro_id")[1]] = v
        rango = {"disparado": 0, "vigilando": 1, "sombra": 1}
        for (s1, b1, c1, t1, i1), (s2, b2, c2, t2, i2) in zip(orden, orden[1:], strict=False):
            if (s1, b1, c1) != (s2, b2, c2) or i1 not in hora_de or i2 not in hora_de:
                continue
            if rango[t1] > rango[t2] or (t1 == t2 and (hora_de.get(i1), i1) < (hora_de.get(i2), i2)):
                h.append(f"E6 el plan {i2} va detras del {i1} y el orden es por estado y por hora (la mas reciente primero)")
        primeros = [b["papel"] for b in c["bloques"] if b["seccion"] == "reciente"]
        if primeros and "ACTIVA" in " ".join(primeros) and not primeros[0].startswith("ACTIVA"):
            h.append(f"E6 la version activa no es la que se lee primero: {primeros}")
    por_camino: dict[str, set] = {}
    for x in c["colores"]:
        por_camino.setdefault(x["camino"], set()).add((x["color"], x["fondo"], x["borde"]))
        if re.search(r"color|background|border", x["estilo"]):
            h.append(f"E6 un color puesto a mano en un nodo ({x['estilo'][:50]!r}): el color sale de la clase")
    distintos = [k for k, v in por_camino.items() if len(v) > 1]
    if distintos:
        h.append(f"E6 nodos de la MISMA clase con colores distintos ({len(distintos)}): {distintos[0][:90]}")
    for p in c["planes"]:
        if p["clases"] != f"ent-plan ent-{p['tipo']}":
            h.append(f"E6 el plan {p['id']} lleva clases que no son las de su estado: {p['clases']!r}")

    # ---- E7 · la palabra de DECIDE, y que su frase sea la de ESA palabra
    if cuerpo and ok:
        edad_decide = None if cuerpo["decide"]["edad_s"] is None else cuerpo["decide"]["edad_s"] + pasado
        tope_decide = cuerpo["decide"]["max_age_s"]
        rancio = bool(edad_decide is not None and tope_decide and edad_decide > tope_decide)
        borde_decide = bool(edad_decide is not None and tope_decide and abs(edad_decide - tope_decide) < BORDE_S)
        for x in ([] if borde_decide else c["palabras"]):
            srv = cuerpo["decide"]["perfiles"].get(x["perfil"]) or {}
            pal = srv.get("palabra")
            if x["rotulo"] != (pal or "SIN RESPUESTA"):
                h.append(f"E7 {x['perfil']}: pinta {x['rotulo']!r} y DECIDE sirve {pal!r}")
            if pal in (None, "NO EVALUABLE") and not re.search(r"sesgo-NOEVAL", x["clases"] or ""):
                h.append(f"E7 {x['perfil']}: {pal or 'sin respuesta'} pintado con el color de un lado ({x['clases']})")
            if rancio:
                if "ya no se sostiene" not in x["frase"]:
                    h.append(f"E7 {x['perfil']}: la palabra pasa de su tope y la vista no dice que es rancia")
                continue
            frase = x["frase"]
            quiere, sobra = _frase_de(pal)
            if not all(q in frase for q in quiere) or any(s in frase for s in sobra):
                h.append(f"E7 {x['perfil']}: con {pal or 'sin respuesta'} la frase es de OTRA palabra: {frase[:90]!r}")
        for cel in ([] if borde_decide else c["relaciones"]):
            perfil, lado = cel["celda"].split("/")
            srv = cuerpo["decide"]["perfiles"][perfil]
            pal = srv.get("palabra")
            dicho = " | ".join(v["t"] for v in cel["visibles"])
            if rancio:
                if "rancio" not in dicho:
                    h.append(f"E7 {cel['celda']}: la palabra pasa de su tope y la celda sigue diciendo {dicho[:60]!r}")
                continue
            quiere = ("EN CONTRA" if pal in ("LONG", "SHORT") and {"LONG": "largo", "SHORT": "corto"}[pal] != lado
                      else "mismo lado" if pal in ("LONG", "SHORT") else "plan condicional: el sistema no toma lado"
                      if pal == "NO OPERAR" else "ni respalda ni desaconseja" if pal == "NO EVALUABLE" else "sin respuesta")
            if quiere not in dicho or dicho != srv["para"][lado]["etiqueta"]:
                h.append(f"E7 {cel['celda']}: con DECIDE {pal or 'sin respuesta'} la celda dice {dicho[:70]!r}")

    # ---- E8 · que pide, cuanto pesa, y que todo lo que trae se pinta o se usa
    papeles = roles()
    for p in pets:
        if not p["camino"].startswith("/api/"):
            continue
        if "ENTRADAS" not in papeles.get(p["camino"], set()):
            h.append(f"E8 la vista de entradas pide {p['camino']}, que no es de su papel "
                     f"({', '.join(sorted(papeles.get(p['camino'], {'FUERA DEL CONTRATO'})))})")
        if p["bytes"] is not None and p["bytes"] > PRESUPUESTO_B:
            h.append(f"E8 {p['camino']} pesa {p['bytes']} B: pasa del presupuesto de {PRESUPUESTO_B} B por peticion")
    if cuerpo and ok:
        ks = {n["k"] for n in c["nodos"]}
        sin = [r for r, _ in hojas(cuerpo) if r not in ks and re.sub(r"\[\d+\]$", "", r) not in ks
               and not NO_SE_PINTA.search(r)]
        if sin:
            h.append(f"E8 la respuesta trae {len(sin)} hoja(s) que la pantalla ni pinta ni usa: {', '.join(sin[:4])}")
    return h


def _frase_de(palabra):
    """Lo que la frase de cada palabra TIENE que decir y lo que NO puede: se contrasta con la
    palabra, no con lo que la respuesta diga que es su frase (A83)."""
    if palabra in ("LONG", "SHORT"):
        return [f"toma {palabra}", "EN CONTRA"], ["plan condicional", "ni los respalda", "Sin respuesta"]
    if palabra == "NO OPERAR":
        return ["plan condicional: el sistema no toma lado"], ["EN CONTRA", "ni los respalda", "Sin respuesta", "toma LONG", "toma SHORT"]
    if palabra == "NO EVALUABLE":
        return ["dice NO EVALUABLE", "ni los respalda ni los desaconseja"], ["EN CONTRA", "plan condicional", "mismo lado", "toma LONG", "toma SHORT"]
    return ["Sin respuesta de DECIDE", "No se sabe"], ["EN CONTRA", "plan condicional", "ni los respalda", "toma LONG", "toma SHORT"]


def _epoch(iso: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()


async def corre(a) -> dict:
    url = f"{a.base.rstrip('/')}{a.puerta}#{a.marco}/{a.activo}{'/entradas' if a.vista == 'entradas' else ''}"
    out: dict = {"url": url, "activo": a.activo, "vista": a.vista, "cosechas": []}
    with K.Chromium(a.ancho, a.alto) as c:
        req = urllib.request.Request(f"http://127.0.0.1:{c.puerto}/json/new?about:blank", method="PUT")
        with urllib.request.urlopen(req, timeout=10) as r:
            destino = json.load(r)
        async with K.websockets.connect(destino["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as ws:
            s = K.Sesion(ws)
            for metodo in ("Page.enable", "Runtime.enable", "Network.enable"):
                await s.pide(metodo)
            await s.pide("Network.setCacheDisabled", cacheDisabled=True)
            await s.pide("Emulation.setDeviceMetricsOverride", width=a.ancho, height=a.alto,
                         deviceScaleFactor=1, mobile=False)
            if a.cabecera_fichero:
                k, _, v = pathlib.Path(a.cabecera_fichero).read_text().strip().partition(":")
                await s.pide("Network.setExtraHTTPHeaders", headers={k.strip(): v.strip()})
            await s.pide("Page.navigate", url=url)

            pesos: dict[str, int] = {}  # bytes del cuerpo SIN comprimir de cada respuesta leida

            def peticiones():
                """Cada peticion a /api/ que la pagina hizo: camino, estado, bytes y cuando acabo."""
                porid: dict[str, dict] = {}
                for e in s.eventos:
                    p, m = e.get("params", {}), e.get("method")
                    rid = p.get("requestId")
                    if m == "Network.requestWillBeSent":
                        camino = p["request"]["url"].split("//", 1)[-1]
                        camino = "/" + camino.split("/", 1)[-1] if "/" in camino else "/"
                        porid[rid] = {"id": rid, "camino": camino.split("?")[0].split("#")[0],
                                      "consulta": camino.split("?", 1)[1] if "?" in camino else "",
                                      "pared": p.get("wallTime"), "t0": p.get("timestamp"),
                                      "estado": None, "bytes": None, "fin": None, "cuerpo_b": pesos.get(rid)}
                    elif rid in porid and m == "Network.responseReceived":
                        porid[rid]["estado"] = p["response"]["status"]
                    elif rid in porid and m == "Network.loadingFinished":
                        porid[rid]["bytes"] = p.get("encodedDataLength")
                        porid[rid]["fin"] = porid[rid]["pared"] + (p["timestamp"] - porid[rid]["t0"])
                    elif rid in porid and m == "Network.loadingFailed":
                        porid[rid]["estado"] = porid[rid]["estado"] or 0
                        porid[rid]["fin"] = porid[rid]["pared"] + (p["timestamp"] - porid[rid]["t0"])
                return [x for x in porid.values() if x["camino"].startswith("/api/")]

            async def cuerpo_de(rid):
                try:
                    r = await s.pide("Network.getResponseBody", requestId=rid)
                    crudo = base64.b64decode(r["body"]) if r.get("base64Encoded") else r.get("body", "").encode()
                    return json.loads(crudo), len(crudo)
                except (K.SystemExit2, ValueError, KeyError):
                    return None, None

            async def cosecha():
                """La pantalla ATADA a la respuesta que pinto: si llega otra durante la cosecha, se repite."""
                for _ in range(4):
                    antes = [p for p in peticiones() if p["camino"] == RUTA and p["fin"] is not None]
                    dom = await s.evalua(JS)
                    despues = [p for p in peticiones() if p["camino"] == RUTA and p["fin"] is not None]
                    if len(antes) == len(despues):
                        break
                    await s.drena(0.4)
                else:
                    raise K.SystemExit2("llego una respuesta nueva en las 4 cosechas: no se pudo atar pantalla y respuesta")
                buena, pasado, ultimo, rid = None, 0.0, None, None
                for p in reversed(antes):
                    cuerpo, n = (await cuerpo_de(p["id"])) if p["estado"] == 200 else (None, None)
                    bueno = bool(cuerpo) and cuerpo.get("disponible") is True
                    if ultimo is None:
                        ultimo = {"estado": p["estado"], "disponible": bueno}
                    if n is not None:
                        pesos[p["id"]] = n
                    if bueno:
                        buena, pasado = cuerpo, dom["ahora"] - p["fin"] if dom.get("existe") else 0.0
                        break
                    rid = p["id"]
                return {"dom": dom, "cuerpo": buena, "ultimo": ultimo, "pasado": pasado,
                        "rid": rid if buena else None, "peticiones": peticiones()}

            # esperar a que la vista diga algo: su hito, o su aviso
            tope = asyncio.get_running_loop().time() + a.espera
            listo = False
            while asyncio.get_running_loop().time() < tope and not listo:
                await s.drena(0.25)
                listo = await s.evalua(
                    "(() => { const r = document.getElementById('vista-entradas'); if (!r) return document.readyState === 'complete';"
                    " return !!(window.MESA_HITOS && window.MESA_HITOS.completo) || !!r.querySelector('[data-aviso]'); })()")
            await s.drena(0.3)
            out["cosechas"].append(await cosecha())
            if a.captura:
                r = await s.pide("Page.captureScreenshot", tope=90.0, format="png", captureBeyondViewport=False)
                pathlib.Path(a.captura).write_bytes(base64.b64decode(r["data"]))
            if a.captura_entera:
                r = await s.pide("Page.captureScreenshot", tope=90.0, format="png", captureBeyondViewport=True)
                pathlib.Path(a.captura_entera).write_bytes(base64.b64decode(r["data"]))
            if a.tramos:
                # la pagina entera a trozos del tamano de la ventana, para LEERLA a su resolucion
                total = await s.evalua("document.documentElement.scrollHeight")
                for i in range(min(14, -(-total // (a.alto - 80)))):
                    await s.evalua(f"window.scrollTo(0, {i * (a.alto - 80)})")
                    await s.drena(0.2)
                    r = await s.pide("Page.captureScreenshot", tope=90.0, format="png", captureBeyondViewport=False)
                    pathlib.Path(f"{a.tramos}-{i:02d}.png").write_bytes(base64.b64decode(r["data"]))
                await s.evalua("window.scrollTo(0, 0)")
            for i, paso in enumerate(a.luego or []):
                orden, _, espera = paso.rpartition("@")
                if orden:
                    subprocess.run(orden, shell=True, check=True)  # noqa: S602 - el control cambia el escenario
                await s.drena(float(espera))
                out["cosechas"].append(await cosecha())
                if a.captura_luego and i == len(a.luego) - 1:
                    r = await s.pide("Page.captureScreenshot", tope=90.0, format="png", captureBeyondViewport=False)
                    pathlib.Path(a.captura_luego).write_bytes(base64.b64decode(r["data"]))
            await s.cierra()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--puerta", default="/")
    ap.add_argument("--marco", default="scalp")
    ap.add_argument("--activo", default="BTC")
    ap.add_argument("--vista", default="entradas", choices=("entradas", "mesa"))
    ap.add_argument("--ancho", type=int, default=1440)
    ap.add_argument("--alto", type=int, default=900)
    ap.add_argument("--espera", type=float, default=40.0)
    ap.add_argument("--luego", action="append", metavar="[ORDEN@]SEGUNDOS",
                    help="tras la primera cosecha: ejecutar ORDEN, esperar y cosechar otra vez")
    ap.add_argument("--cabecera-fichero")
    ap.add_argument("--captura")
    ap.add_argument("--captura-entera")
    ap.add_argument("--captura-luego")
    ap.add_argument("--tramos", metavar="PREFIJO", help="capturar la pagina entera a trozos: PREFIJO-NN.png")
    ap.add_argument("--salida", help="volcar aqui la cosecha entera (JSON)")
    ap.add_argument("--firma", action="store_true", help="imprimir la firma de lo que la pantalla ensena")
    a = ap.parse_args()
    try:
        out = asyncio.run(asyncio.wait_for(corre(a), timeout=120 + a.espera + sum(float(p.rpartition('@')[2]) for p in a.luego or [])))
    except (K.SystemExit2, TimeoutError, OSError) as e:
        print(f"NO MEDIDO: {e}")
        return 2
    if a.salida:
        pathlib.Path(a.salida).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    primera = out["cosechas"][0]
    if a.vista == "mesa":
        # LA VISTA PRINCIPAL NO PIDE LO QUE SOLO ES DE ENTRADAS (y esto lo ve el navegador, exacto).
        papeles = roles()
        malas = sorted({p["camino"] for p in primera["peticiones"] if papeles.get(p["camino"]) == {"ENTRADAS"}})
        pedidas = sorted({p["camino"] for p in primera["peticiones"]})
        print(f"vista principal [{a.activo}]: {len(pedidas)} rutas pedidas")
        for m in malas:
            print(f"   - E8 la vista principal pide {m}, que solo es de ENTRADAS")
        return 1 if malas else 0
    if not primera["dom"].get("existe"):
        print(f"SIN VISTA: {url_de(out)} no trae #vista-entradas")
        return 3
    hallazgos: list[str] = []
    antes = None
    for i, c in enumerate(out["cosechas"]):
        pets = [p for p in c["peticiones"] if p["fin"] is not None]
        # «no avanzo» solo se juzga entre dos cosechas de la MISMA respuesta: otra reinicia la cuenta
        mismo = antes is not None and c["rid"] is not None and c["rid"] == out["cosechas"][i - 1]["rid"]
        for hz in juzga(c["dom"], c["cuerpo"], c["ultimo"], c["pasado"], pets, antes if mismo else None):
            hallazgos.append(f"[{a.activo} cosecha {i + 1}] {hz}")
        antes = c["dom"]
    ult = out["cosechas"][-1]
    ruta = [p for p in ult["peticiones"] if p["camino"] == RUTA and p["fin"] is not None]
    pesos = [p.get("cuerpo_b") or p["bytes"] for p in ruta if p["estado"] == 200]
    ritmo = [round(b["fin"] - a_["fin"], 1) for a_, b in zip(ruta, ruta[1:], strict=False)]
    # EL RITMO: la vista vuelve a pedir a la cadencia que la ruta SIRVE, ni mas ni menos.
    if ult["cuerpo"] and len(out["cosechas"]) > 1:
        cada = ult["cuerpo"]["frescura"]["refresco_s"]
        mirado = sum(float(p.rpartition("@")[2]) for p in a.luego or [])
        if mirado > cada + 6 and not ritmo:
            hallazgos.append(f"[{a.activo}] E8 la vista no volvio a pedir en {mirado:g} s y su cadencia servida es de {cada} s")
        for r in ritmo:
            if not 0.85 * cada <= r <= 1.15 * cada + 4:
                hallazgos.append(f"[{a.activo}] E8 la vista volvio a pedir a los {r} s y su cadencia servida es de {cada} s")
    dom = primera["dom"]
    print(f"entradas [{a.activo}] {a.ancho}x{a.alto}: {len(dom['planes'])} planes pintados, {len([n for n in dom['nodos'] if n['vis']])} "
          f"nodos servidos, {len(ruta)} peticion(es) a la ruta" + (f", {max(pesos)} B la mayor" if pesos else "")
          + (f", cada {ritmo} s" if ritmo else "") + f", {len({p['camino'] for p in ult['peticiones']})} ruta(s) distinta(s)")
    for hz in dict.fromkeys(hallazgos):
        print(f"   - {hz}")
    if a.firma:
        # lo que la pantalla ensena y como: el orden y la clase de cada plan, cada texto servido,
        # el texto propio y cada color. Dos respuestas que solo difieren en un RESULTADO tienen
        # que dar la misma firma.
        d = out["cosechas"][-1]["dom"]
        visto = [[(p["seccion"], p["bloque"], p["id"], p["clases"], p["chip"]) for p in d["planes"]],
                 [(n["k"], n["t"]) for n in d["nodos"] if n["vis"]], d["literal"],
                 [(x["camino"], x["color"], x["fondo"], x["borde"], x["estilo"]) for x in d["colores"]]]
        print("firma " + hashlib.sha256(json.dumps(visto, ensure_ascii=False).encode()).hexdigest()[:16])
    return 1 if hallazgos else 0


def url_de(out: dict) -> str:
    return out["url"].split("#")[0]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 - un fallo de la sonda no acusa a la pantalla
        print(f"NO MEDIDO: la sonda de K106 fallo y no juzgo nada ({type(e).__name__}: {str(e)[:160]})")
        sys.exit(2)
