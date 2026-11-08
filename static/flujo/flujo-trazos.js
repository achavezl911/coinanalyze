'use strict';
/* EL DIBUJO SOBRE EL FOOTPRINT (campana 146-D, OF-6 primera parte; su contrato, `trazos`).
 * ---------------------------------------------------------------------------
 * Cuatro herramientas en el lienzo del footprint (en el TPO no): NIVEL (un clic, un precio, de lado a lado con su
 * precio en el eje), LINEA (dos clics, el segmento), FIBONACCI (dos clics: 0, 0.236, 0.382, 0.5, 0.618, 0.786 y 1 del
 * precio del 1er punto al del 2o, del instante del 1o hacia la derecha) y CANAL DE REGRESION (dos clics que eligen un
 * tramo: la recta de minimos cuadrados de los CIERRES de sus velas, x = indice de la vela dentro del tramo, y dos
 * paralelas a +-2 sigma; sigma de la POBLACION, n = velas del tramo con cierre; una vela «hueco» ocupa su indice pero
 * no cuenta; con menos de 3, no se pinta y lo dice).
 *
 * ANCLADOS AL DATO: cada punto es (instante en ms UTC, precio). La x de un instante sale de las velas que la pagina
 * tiene (xDeInstante): dentro de la vela que lo contiene, en su fraccion; en un minuto que falta entre dos velas, el
 * borde derecho de la anterior; fuera de lo cargado, extrapolado con la duracion del marco desde la primera o la
 * ultima. NUNCA (t - t0) / marco, que se corre en cuanto falta una vela.
 *
 * SE GUARDAN POR ACTIVO en localStorage (GUARDADO, version VERSION), cada lectura y escritura en try/catch: sin
 * almacenamiento o con basura, la pantalla funciona sin trazos; un trazo malo se descarta y los buenos se quedan.
 *
 * EL CONTRATO: `FLUJO_PINTADO.trazos`, una lista con, por trazo, tipo, id, puntos [{t, p}] y lo pintado en pixeles
 * del lienzo (px: la x, y de cada punto; nivel: y; fib: la razon, el precio y la y de cada linea; canal: pendiente,
 * ordenada, sigma, n y los extremos de las tres rectas). El estado de la botonera, en `FLUJO_TRAZOS`.
 */

const TRAZOS_TIPOS = { nivel: 1, linea: 2, fib: 2, canal: 2 };
const RAZONES_FIB = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const MARCO_MS = { '1m': 60000, '5m': 300000, '15m': 900000, '1h': 3600000, '4h': 14400000, '1d': 86400000 };
const GUARDADO = 'flujo.trazos';
const VERSION = 1;
const CERCA_PX = 6;
const CANAL_SIGMAS = 2;

/* ------------------------------------------------------------ lo puro */

/* Las siete lineas de Fibonacci entre el precio del 1er punto (razon 0) y el del 2o (razon 1). */
function fibonacci(p0, p1) {
  return RAZONES_FIB.map((r) => ({ razon: r, precio: p0 + (p1 - p0) * r }));
}

/* Minimos cuadrados de `ys` contra su indice (null no cuenta, pero ocupa su indice). sigma, la de la POBLACION:
 * raiz(suma de residuos^2 / n). Con menos de 3 puntos, null. */
function regresion(ys) {
  const pts = [];
  ys.forEach((y, i) => {
    if (y !== null && y !== undefined && Number.isFinite(Number(y))) pts.push([i, Number(y)]);
  });
  const n = pts.length;
  if (n < 3) return null;
  const mx = pts.reduce((a, [x]) => a + x, 0) / n;
  const my = pts.reduce((a, [, y]) => a + y, 0) / n;
  let sxy = 0;
  let sxx = 0;
  pts.forEach(([x, y]) => {
    sxy += (x - mx) * (y - my);
    sxx += (x - mx) * (x - mx);
  });
  const pendiente = sxx ? sxy / sxx : 0;
  const ordenada = my - pendiente * mx;
  const ss = pts.reduce((a, [x, y]) => a + (y - (ordenada + pendiente * x)) ** 2, 0);
  return { pendiente, ordenada, sigma: Math.sqrt(ss / n), n };
}

/* La distancia de (px, py) al segmento (x0, y0)-(x1, y1). */
function distSegmento(px, py, x0, y0, x1, y1) {
  const dx = x1 - x0;
  const dy = y1 - y0;
  const l2 = dx * dx + dy * dy;
  const u = l2 ? Math.max(0, Math.min(1, ((px - x0) * dx + (py - y0) * dy) / l2)) : 0;
  return Math.hypot(px - (x0 + u * dx), py - (y0 + u * dy));
}

/* El indice de la ultima vela que empieza en o antes de `t` (-1 si todas empiezan despues). `ts`, ordenado. */
function velaHasta(ts, t) {
  let a = 0;
  let b = ts.length - 1;
  let r = -1;
  while (a <= b) {
    const k = (a + b) >> 1;
    if (ts[k] <= t) {
      r = k;
      a = k + 1;
    } else b = k - 1;
  }
  return r;
}

/* La x de un instante: `ts` los inicios de las velas (ms), `x0` el centro de la vela 0 y `bs` el ancho de una vela.
 * Dentro de una vela, su fraccion; en lo que falta entre dos velas, el borde derecho de la anterior; fuera de lo
 * cargado, extrapolado con la duracion del marco desde la primera o la ultima. */
function xDeInstante(t, ts, marcoMs, x0, bs) {
  const n = ts.length;
  if (!n) return null;
  const izq = (i) => x0 + (i - 0.5) * bs;
  if (t < ts[0]) return izq(0) + ((t - ts[0]) / marcoMs) * bs;
  const i = velaHasta(ts, t);
  if (i === n - 1) return izq(i) + ((t - ts[i]) / marcoMs) * bs;
  return izq(i) + Math.min(1, (t - ts[i]) / marcoMs) * bs;
}

/* El instante de una x (la inversa de xDeInstante dentro de las velas y fuera de ellas). */
function instanteDeX(x, ts, marcoMs, x0, bs) {
  const n = ts.length;
  if (!n) return null;
  const u = (x - x0) / bs + 0.5; // en velas desde el borde izquierdo de la vela 0
  const i = Math.floor(u);
  if (i < 0) return Math.round(ts[0] + u * marcoMs);
  if (i >= n) return Math.round(ts[n - 1] + (u - (n - 1)) * marcoMs);
  return Math.round(ts[i] + (u - i) * marcoMs);
}

/* El tramo de un canal: las velas cargadas que se solapan con [min(ta, tb), max(ta, tb)] -> [iA, iB] o null. */
function tramoDe(ta, tb, ts, marcoMs) {
  const a = Math.min(ta, tb);
  const b = Math.max(ta, tb);
  let iA = velaHasta(ts, a);
  if (iA < 0 || ts[iA] + marcoMs <= a) iA += 1;
  const iB = velaHasta(ts, b);
  return iA <= iB && iA < ts.length && iB >= 0 ? [iA, iB] : null;
}

/* La regresion de un canal sobre las velas iA..iB: x = indice dentro del tramo; la vela hueco o sin cierre no cuenta. */
function canalDe(velas, iA, iB) {
  const ys = [];
  for (let i = iA; i <= iB; i++) {
    const v = velas[i];
    ys.push(v.estado === 'hueco' || v.cierre === null || v.cierre === undefined ? null : Number(v.cierre));
  }
  return regresion(ys);
}

/* Un trazo guardado es bueno si su tipo existe, tiene id y el numero de puntos de su tipo, cada uno con t y p
 * finitos. -> el trazo limpio o null. */
function trazoValido(x) {
  if (!x || typeof x !== 'object' || !Object.prototype.hasOwnProperty.call(TRAZOS_TIPOS, x.tipo)) return null;
  if (typeof x.id !== 'string' || !x.id || !Array.isArray(x.puntos) || x.puntos.length !== TRAZOS_TIPOS[x.tipo]) return null;
  const puntos = [];
  for (const q of x.puntos) {
    if (!q || typeof q !== 'object') return null;
    const t = Number(q.t);
    const p = Number(q.p);
    if (!Number.isFinite(t) || !Number.isFinite(p) || q.t === null || q.p === null) return null;
    puntos.push({ t: Math.round(t), p });
  }
  return { tipo: x.tipo, id: x.id, puntos };
}

/* Lo guardado (el texto de localStorage) -> los trazos buenos de `activo`. Basura, otra version o nada: []. */
function leeGuardado(texto, activo) {
  let d;
  try {
    d = JSON.parse(texto);
  } catch (e) {
    return [];
  }
  if (!d || typeof d !== 'object' || d.version !== VERSION || !d.activos || typeof d.activos !== 'object') return [];
  const lista = d.activos[activo];
  if (!Array.isArray(lista)) return [];
  const vistos = new Set();
  return lista.map(trazoValido).filter((x) => x && !vistos.has(x.id) && vistos.add(x.id));
}

/* El texto nuevo con los trazos de `activo` y los de los demas activos como estaban (si lo previo se deja leer). */
function escribeGuardado(previo, activo, trazos) {
  let d = null;
  try {
    d = JSON.parse(previo);
  } catch (e) {
    d = null;
  }
  if (!d || typeof d !== 'object' || d.version !== VERSION || !d.activos || typeof d.activos !== 'object') {
    d = { version: VERSION, activos: {} };
  }
  d.activos[activo] = trazos.map((x) => ({ tipo: x.tipo, id: x.id, puntos: x.puntos.map((q) => ({ t: q.t, p: q.p })) }));
  return JSON.stringify(d);
}

/* ------------------------------------------------------------ la pagina */
const r2 = (v) => Math.round(v * 100) / 100;

const TRZ = {
  herramienta: null, trazos: [], activo: null, pendiente: null, cursor: null, sel: null, arrastre: null,
  geo: null, ctl: null, siguiente: 1,
};

function almacen() {
  try {
    return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null;
  } catch (e) {
    return null;
  }
}

function cargaTrazos(activo) {
  TRZ.activo = activo;
  TRZ.sel = null;
  TRZ.pendiente = null;
  TRZ.trazos = [];
  const s = almacen();
  if (!s) return;
  try {
    TRZ.trazos = leeGuardado(s.getItem(GUARDADO), activo);
  } catch (e) {
    TRZ.trazos = [];
  }
}

function guardaTrazos() {
  const s = almacen();
  if (!s || !TRZ.activo) return;
  try {
    let previo = null;
    try {
      previo = s.getItem(GUARDADO);
    } catch (e) {
      previo = null;
    }
    s.setItem(GUARDADO, escribeGuardado(previo, TRZ.activo, TRZ.trazos));
  } catch (e) {
    /* sin sitio o sin permiso: los trazos siguen en la pantalla y no se guardan */
  }
}

function nuevoId() {
  return Date.now().toString(36) + '-' + (TRZ.siguiente++).toString(36);
}

/* La geometria del ultimo pintado: de instante a x y de precio a y, y al reves. */
function geoTrazos(g, lo, hi, m) {
  const ts = m.velas.map((v) => Date.parse(v.ts));
  const marcoMs = MARCO_MS[m.marco] || 60000;
  const alto = g.abajo - g.arriba;
  const x0 = g.x(0);
  return {
    g, lo, hi, m, ts, marcoMs,
    x: (t) => xDeInstante(t, ts, marcoMs, x0, g.bs),
    t: (x) => instanteDeX(x, ts, marcoMs, x0, g.bs),
    y: (p) => g.arriba + ((hi - p) / (hi - lo)) * alto,
    p: (y) => hi - ((y - g.arriba) / alto) * (hi - lo),
  };
}

function decimalesPaso(m) {
  return (String(m.paso).split('.')[1] || '').length;
}

/* Lo que se pinta de un trazo, en pixeles: el registro del contrato y las piezas que se dibujan (segmentos). */
function geometria(z, G) {
  const px = z.puntos.map((q) => ({ x: r2(G.x(q.t)), y: r2(G.y(q.p)) }));
  const r = { tipo: z.tipo, id: z.id, puntos: z.puntos.map((q) => ({ t: q.t, p: q.p })), px, sel: TRZ.sel === z.id };
  const segs = [];
  const ancho = G.g.ancho;
  if (z.tipo === 'nivel') {
    r.y = px[0].y;
    r.precio = z.puntos[0].p;
    segs.push([0, px[0].y, ancho, px[0].y]);
  } else if (z.tipo === 'linea') {
    segs.push([px[0].x, px[0].y, px[1].x, px[1].y]);
  } else if (z.tipo === 'fib') {
    const x0 = px[0].x;
    r.lineas = fibonacci(z.puntos[0].p, z.puntos[1].p).map((f) => ({ razon: f.razon, precio: f.precio, y: r2(G.y(f.precio)),
                                                                       x0, x1: ancho }));
    r.lineas.forEach((f) => segs.push([x0, f.y, Math.max(x0, ancho), f.y]));
    segs.push([px[0].x, px[0].y, px[1].x, px[1].y]);
  } else if (z.tipo === 'canal') {
    const tramo = tramoDe(z.puntos[0].t, z.puntos[1].t, G.ts, G.marcoMs);
    const reg = tramo ? canalDe(G.m.velas, tramo[0], tramo[1]) : null;
    r.tramo = tramo ? { desde: G.m.velas[tramo[0]].ts, hasta: G.m.velas[tramo[1]].ts, velas: tramo[1] - tramo[0] + 1 } : null;
    if (!reg) {
      Object.assign(r, { pintado: false, motivo: 'menos de 3 velas con cierre en el tramo',
                         n: tramo ? canalN(G.m.velas, tramo[0], tramo[1]) : 0 });
    } else {
      const xa = G.g.x(tramo[0]);
      const xb = G.g.x(tramo[1]);
      const k = tramo[1] - tramo[0];
      const recta = (d) => {
        const ya = reg.ordenada + d;
        const yb = reg.ordenada + reg.pendiente * k + d;
        return { x0: r2(xa), y0: r2(G.y(ya)), x1: r2(xb), y1: r2(G.y(yb)), p0: ya, p1: yb };
      };
      Object.assign(r, { pintado: true, pendiente: reg.pendiente, ordenada: reg.ordenada, sigma: reg.sigma, n: reg.n,
                         rectas: { media: recta(0), alta: recta(CANAL_SIGMAS * reg.sigma), baja: recta(-CANAL_SIGMAS * reg.sigma) } });
      ['media', 'alta', 'baja'].forEach((q) => {
        const s = r.rectas[q];
        segs.push([s.x0, s.y0, s.x1, s.y1]);
      });
    }
  }
  return { r, segs };
}

function canalN(velas, iA, iB) {
  let n = 0;
  for (let i = iA; i <= iB; i++) if (velas[i].estado !== 'hueco' && velas[i].cierre != null) n += 1;
  return n;
}

const COLOR_TRAZO = { nivel: '#f59e0b', linea: '#e6e9ee', fib: '#c084fc', canal: '#34d399' };

/* Pinta los trazos del activo de `m` con la geometria de este pintado; devuelve el contrato. Lo llama el lienzo. */
function pintaTrazos(ctx, g, y, m, lo, hi) {
  if (!m || !m.velas || !m.velas.length) {
    TRZ.geo = null;
    return [];
  }
  if (TRZ.activo !== m.activo) cargaTrazos(m.activo);
  const G = geoTrazos(g, lo, hi, m);
  TRZ.geo = G;
  const dec = decimalesPaso(m);
  const out = [];
  const lista = TRZ.trazos.slice();
  const prov = provisional(G);
  if (prov) lista.push(prov);
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, g.arriba, g.ancho, g.abajo - g.arriba);
  ctx.clip();
  const etiquetas = [];
  lista.forEach((z) => {
    const { r, segs } = geometria(z, G);
    const col = COLOR_TRAZO[z.tipo];
    ctx.strokeStyle = col;
    ctx.lineWidth = r.sel ? 2 : 1;
    ctx.setLineDash(z.provisional ? [4, 3] : []);
    segs.forEach(([a, b, c, d], k) => {
      ctx.globalAlpha = z.tipo === 'canal' && k > 0 ? 0.7 : 1;
      ctx.beginPath();
      ctx.moveTo(a, b);
      ctx.lineTo(c, d);
      ctx.stroke();
    });
    ctx.globalAlpha = 1;
    ctx.fillStyle = col;
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';
    if (z.tipo === 'fib') {
      r.lineas.forEach((f) => ctx.fillText(f.razon + ' · ' + f.precio.toFixed(dec), f.x0 + 3, f.y - 2));
    } else if (z.tipo === 'canal' && !r.pintado) {
      ctx.fillText('canal: menos de 3 velas', r.px[0].x + 3, r.px[0].y - 4);
    } else if (z.tipo === 'nivel') {
      etiquetas.push([r.y, z.puntos[0].p.toFixed(dec), col]);
    }
    if (r.sel) r.px.forEach((q) => ctx.fillRect(q.x - 3, q.y - 3, 6, 6));
    if (!z.provisional) out.push(r);
  });
  ctx.restore();
  // el precio de cada NIVEL, en el eje
  ctx.font = '10px monospace';
  ctx.textAlign = 'left';
  etiquetas.forEach(([yy, t, col]) => {
    if (yy < g.arriba || yy > g.abajo) return;
    ctx.fillStyle = col;
    ctx.fillRect(g.ancho, Math.round(yy) - 7, LZ.EJE_P, 14);
    ctx.fillStyle = '#0a0d12';
    ctx.fillText(t, g.ancho + 4, Math.round(yy) + 4);
  });
  if (typeof window !== 'undefined') publicaEstado();
  return out;
}

/* El trazo a medio poner (el 1er punto y el cursor), para verlo mientras se elige el 2o. */
function provisional(G) {
  if (!TRZ.pendiente || !TRZ.cursor) return null;
  return { tipo: TRZ.herramienta, id: '(provisional)', provisional: true,
           puntos: [TRZ.pendiente, { t: G.t(TRZ.cursor.x), p: G.p(TRZ.cursor.y) }] };
}

function publicaEstado() {
  window.FLUJO_TRAZOS = { herramienta: TRZ.herramienta, sel: TRZ.sel, pendiente: TRZ.pendiente, activo: TRZ.activo,
                          n: TRZ.trazos.length };
  if (typeof document === 'undefined') return;
  document.querySelectorAll('#sel-trazo button[data-trazo]').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.trazo === TRZ.herramienta));
  });
}

/* El trazo y la parte bajo (px, py): {z, punto} con punto el indice del punto a <= CERCA_PX, o -1 si es el cuerpo. */
function tocaTrazo(px, py) {
  const G = TRZ.geo;
  if (!G) return null;
  let mejor = null;
  TRZ.trazos.forEach((z) => {
    const { r, segs } = geometria(z, G);
    r.px.forEach((q, k) => {
      const d = Math.hypot(px - q.x, py - q.y);
      if (d <= CERCA_PX && (!mejor || d < mejor.d)) mejor = { z, punto: z.tipo === 'nivel' ? -1 : k, d };
    });
    segs.forEach(([a, b, c, d2]) => {
      const d = distSegmento(px, py, a, b, c, d2);
      if (d <= CERCA_PX && (!mejor || d < mejor.d - 0.5)) mejor = { z, punto: -1, d };
    });
  });
  return mejor;
}

function eligeHerramienta(h) {
  TRZ.herramienta = h && TRAZOS_TIPOS[h] ? (TRZ.herramienta === h ? null : h) : null;
  TRZ.pendiente = null;
  TRZ.cursor = null;
  pideTrazos();
}

function pideTrazos() {
  if (TRZ.ctl) TRZ.ctl.pide();
  else if (typeof window !== 'undefined') publicaEstado();
}

/* El raton del lienzo pasa por aqui primero: devuelve true si el gesto es del dibujo (y el lienzo no hace lo suyo).
 * Sin herramienta y lejos de todo trazo, false: el lienzo hace exactamente lo de siempre. */
function trazosRaton(tipo, p, ev) {
  const G = TRZ.geo;
  if (tipo === 'suelta') {
    if (!TRZ.arrastre) return false;
    TRZ.arrastre = null;
    guardaTrazos();
    return true;
  }
  if (!G || p.x >= G.g.ancho || p.y < G.g.arriba || p.y > G.g.abajo) {
    if (tipo === 'mueve' && TRZ.pendiente) {
      TRZ.cursor = null;
      pideTrazos();
    }
    return tipo === 'mueve' && !!TRZ.arrastre;
  }
  if (tipo === 'mueve') {
    const a = TRZ.arrastre;
    if (a) {
      const z = TRZ.trazos.find((x) => x.id === a.id);
      if (!z) return false;
      const dx = p.x - a.x;
      const dp = G.p(p.y) - G.p(a.y);
      z.puntos = a.puntos.map((q, k) => (a.punto === -1 || a.punto === k
        ? { t: z.tipo === 'nivel' ? q.t : G.t(G.x(q.t) + dx), p: q.p + dp } : { t: q.t, p: q.p }));
      pideTrazos();
      return true;
    }
    if (TRZ.pendiente) {
      TRZ.cursor = { x: p.x, y: p.y };
      pideTrazos();
    }
    return false;
  }
  // tipo === 'baja'
  if (ev && (ev.ctrlKey || ev.shiftKey || ev.metaKey || ev.altKey)) return false;
  const punto = { t: G.t(p.x), p: G.p(p.y) };
  if (TRZ.herramienta) {
    const h = TRZ.herramienta;
    if (TRAZOS_TIPOS[h] === 1 || TRZ.pendiente) {
      const z = { tipo: h, id: nuevoId(), puntos: TRAZOS_TIPOS[h] === 1 ? [punto] : [TRZ.pendiente, punto] };
      TRZ.trazos.push(z);
      TRZ.sel = z.id;
      TRZ.pendiente = null;
      TRZ.cursor = null;
      guardaTrazos();
    } else {
      TRZ.pendiente = punto;
      TRZ.cursor = { x: p.x, y: p.y };
    }
    pideTrazos();
    return true;
  }
  const t = tocaTrazo(p.x, p.y);
  if (!t) {
    if (TRZ.sel) {
      TRZ.sel = null;
      pideTrazos();
    }
    return false;
  }
  TRZ.sel = t.z.id;
  TRZ.arrastre = { id: t.z.id, punto: t.punto, x: p.x, y: p.y, puntos: t.z.puntos.map((q) => ({ t: q.t, p: q.p })) };
  pideTrazos();
  return true;
}

/* Esc suelta la herramienta (y el punto a medio poner); Supr borra el trazo elegido. Sin nada de eso, nada. */
function trazosTecla(ev) {
  if (ev.key === 'Escape' && (TRZ.herramienta || TRZ.pendiente)) {
    eligeHerramienta(null);
  } else if ((ev.key === 'Delete' || ev.key === 'Supr') && TRZ.sel) {
    if (ev.target && ev.target.closest && ev.target.closest('input, select, textarea, dialog')) return;
    TRZ.trazos = TRZ.trazos.filter((x) => x.id !== TRZ.sel);
    TRZ.sel = null;
    guardaTrazos();
    pideTrazos();
    ev.preventDefault();
  }
}

function borraTodos() {
  if (!TRZ.trazos.length) return;
  if (!window.confirm('¿Borrar los ' + TRZ.trazos.length + ' trazos de ' + TRZ.activo + '?')) return;
  TRZ.trazos = [];
  TRZ.sel = null;
  guardaTrazos();
  pideTrazos();
}

/* El lienzo se presenta (creaLienzo): con que repintar. La botonera y el teclado, una vez. */
function conectaTrazos(ctl) {
  TRZ.ctl = ctl;
  if (typeof document === 'undefined' || TRZ.conectado) return;
  TRZ.conectado = true;
  const caja = document.getElementById('sel-trazo');
  if (caja) {
    caja.addEventListener('click', (ev) => {
      const b = ev.target.closest('button');
      if (!b) return;
      if (b.dataset.trazo) eligeHerramienta(b.dataset.trazo);
      else if (b.id === 'b-borra-trazos') borraTodos();
    });
  }
  window.addEventListener('keydown', trazosTecla);
  publicaEstado();
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { RAZONES_FIB, MARCO_MS, GUARDADO, VERSION, TRAZOS_TIPOS, fibonacci, regresion, distSegmento, xDeInstante,
                     instanteDeX, tramoDe, canalDe, trazoValido, leeGuardado, escribeGuardado };
}
