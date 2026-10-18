'use strict';
/* LOS INDICADORES bajo el footprint (campana 146, OF-5a): delta por vela, CVD, interes abierto (Binance y Bybit) y su
 * cambio, funding y el predicho, largos/cortos y liquidaciones (las de 5 min y las sueltas); y las MARCAS de las
 * operaciones grandes sobre el footprint.
 * ---------------------------------------------------------------------------
 * EL MISMO EJE DE TIEMPO: los paneles se pintan en el MISMO fotograma que el footprint (flujo-dibujo.js llama aqui al
 * acabar), con su geometria: el mismo ancho, el mismo `fin` y las mismas `ver` velas. Un instante t cae en
 * x = x(0) - bs/2 + (t - t0) / marco * bs, como las capas de OF-3.
 *
 * DE DONDE SALE CADA PANEL Y LO QUE DICE (cada uno lo escribe en su cabecera):
 *   delta, CVD          las velas del footprint que ya se pidieron (su familia, su cobertura). El CVD empieza en la
 *                       PRIMERA vela de la ventana y, tras un HUECO, vuelve a empezar en 0: lo que no se escucho no se
 *                       suma ni se supone. Una vela incompleta suma lo que se escucho y lleva su marca.
 *   OI, funding, L/C,   /api/orderflow/indicadores: series de 5 min de Coinalyze (su BTCUSDT_PERP.A es BINANCE), en
 *   liquidaciones       cubos de max(5 min, marco): con velas de 1 min, un ESCALON de 5 velas. Un cubo sin dato es
 *                       HUECO (o pendiente, si aun no tocaba): nunca un cero. Las liquidaciones de 5 min sin fila
 *                       son cero solo si el barrido de la ingesta las certifica (lo dice el servidor).
 *   sueltas             las liquidaciones de binance y bybit una a una, desde su retencion (12 h en 140): puntos.
 *   grandes             /api/orderflow/grandes de la familia: un circulo en su vela, a su hora y a su precio.
 *
 * EL CONTRATO (lo lee K112): `window.FLUJO_INDICADORES`, apuntado donde se dibuja: por panel su clave, el TEXTO de su
 * cabecera tal como se paso a fillText, su caja, su escala, y por punto su instante, su x, su valor servido (o
 * recalculado: el CVD, en texto exacto), su y y su estado; los huecos y las marcas. Las grandes, en
 * `FLUJO_PINTADO.grandes`. Lo que no se pinta no se apunta. */

const IND_PANEL = { ALTO: 88, CABEZA: 16, PIE: 6 };
const IND_COLOR = {
  linea: '#e6e9ee', segunda: '#6fa8ff', ambar: '#e6b75a', mudo: '#5b6472', cero: 'rgba(255,255,255,0.18)',
  hueco: 'rgba(230,183,90,0.10)', pendiente: 'rgba(136,145,160,0.10)',
};
// Los paneles, en su orden de arriba a abajo, y lo que necesita cada uno de /api/orderflow/indicadores
const IND_PANELES = ['delta', 'cvd', 'oi', 'oib', 'funding', 'ls', 'liq'];
const IND_SERIE = { oi: ['oi_binance'], oib: ['oi_bybit'], funding: ['funding', 'funding_predicho'],
                    ls: ['largos_cortos'], liq: ['liquidaciones'] };
const RUTA_IND = '/api/orderflow/indicadores';
const RUTA_GRANDES = '/api/orderflow/grandes';
const IND = { datos: null, grandes: null, fallos: [], pide: 0, canvas: null, ctx: null, pr: 1, W: 0, H: 0, cuadros: 0 };

/* ------------------------------------------------------------- lo puro (node --test y K112 lo recalculan) */
function deEntero(n, e) {
  const neg = n < 0n;
  const s = (neg ? -n : n).toString().padStart(e + 1, '0');
  let r = e ? s.slice(0, s.length - e) + '.' + s.slice(s.length - e) : s;
  if (e) r = r.replace(/0+$/, '').replace(/\.$/, '');
  return (neg && r !== '0' ? '-' : '') + r;
}

/* El CVD de las velas de la ventana, EXACTO (BigInt sobre el texto servido): desde la primera vela y, tras un hueco,
 * desde 0 otra vez. -> [{ts, valor (texto) | null, origen (ts de su primera vela) | null}] */
function cvdDe(velas) {
  let e = 0;
  velas.forEach((v) => { e = Math.max(e, decimales(v.delta)); });
  let acum = 0n;
  let origen = null;
  return velas.map((v) => {
    if (v.estado === 'hueco') {
      origen = null;
      return { ts: v.ts, valor: null, origen: null };
    }
    if (origen === null) {
      origen = v.ts;
      acum = 0n;
    }
    acum += entero(v.delta, e);
    return { ts: v.ts, valor: deEntero(acum, e), origen };
  });
}

/* El cambio de una serie de nivel de un cubo al siguiente (solo entre dos cubos CON dato y seguidos). */
function cambiosDe(cubos, clave) {
  return cubos.map((c, i) => {
    const a = i ? cubos[i - 1] : null;
    if (!a || !a.valores || !c.valores) return { ts: c.ts, valor: null };
    const e = Math.max(decimales(a.valores[clave]), decimales(c.valores[clave]));
    return { ts: c.ts, valor: deEntero(entero(c.valores[clave], e) - entero(a.valores[clave], e), e) };
  });
}

/* La cabecera de un panel: su fuente y su alcance, tal como se escriben. */
function tituloPanel(clave, d, ctx) {
  const s = (k) => d.series[k];
  const esc = d ? 'escalon de ' + d.cubo_minutos + ' min' : ''; // delta y CVD no usan la ruta de las series
  switch (clave) {
    case 'delta':
      return 'delta por vela · ' + ctx.familia + ' (celdas de OF-1) · compra - venta del agresor, en ' + ctx.unidad;
    case 'cvd':
      return 'CVD · ' + ctx.familia + ' · desde ' + ctx.origen + ' (inicio de la ventana) · tras un hueco vuelve a 0';
    case 'oi':
    case 'oib':
      return s(IND_SERIE[clave][0]).fuente + ' · ' + esc + ' · en USD · barras: su cambio';
    case 'funding':
      return s('funding').fuente + ' · y el predicho (discontinuo) · ' + esc + ' · ' + s('funding').unidad;
    case 'ls':
      return s('largos_cortos').fuente + ' · % de cuentas en largo · ' + esc;
    case 'liq':
      return s('liquidaciones').fuente + ' · largos abajo, cortos arriba · ' + esc + ' · puntos: ' + d.sueltas.fuente
        .replace('liquidaciones sueltas · ', 'sueltas de ') + ', desde ' + d.sueltas.desde_dato.slice(11, 16) + 'Z';
    default:
      return clave;
  }
}

/* ------------------------------------------------------------- pedir */
function indicadoresQuePide(e) {
  return (e.ind || []).filter((c) => IND_SERIE[c]);
}

/* Pide lo que la vista necesita de la ventana del footprint (`w`): las series (si algun panel las usa) y las grandes
 * (si sus marcas estan encendidas). La ultima peticion manda; lo que no llega se dice con su codigo. */
async function cargaIndicadores(e, w, alAcabar) {
  const mia = ++IND.pide;
  const pide = [];
  if (indicadoresQuePide(e).length) {
    pide.push(['indicadores', RUTA_IND, { symbol: e.activo, desde: w.desde, hasta: w.hasta, marco: e.marco }]);
  }
  if ((e.ind || []).includes('grandes')) {
    pide.push(['grandes', RUTA_GRANDES, { symbol: e.activo, desde: w.desde, hasta: w.hasta,
                                          venues: FAMILIAS[e.familia].venues.join(','), limit: 5000 }]);
  }
  if (!pide.some(([n]) => n === 'indicadores')) IND.datos = null;
  if (!pide.some(([n]) => n === 'grandes')) IND.grandes = null;
  const sobres = await Promise.all(pide.map(([, ruta, q]) => pedir(ruta, q)));
  if (mia !== IND.pide) return;
  IND.fallos = [];
  pide.forEach(([nombre], i) => {
    const s = sobres[i];
    if (alAcabar) alAcabar(s);
    if (!s.ok) {
      IND.fallos.push([nombre, s]);
      if (nombre === 'indicadores') IND.datos = null;
      else IND.grandes = null;
      return;
    }
    if (nombre === 'indicadores') IND.datos = s.datos;
    else IND.grandes = s.datos;
  });
}

/* ------------------------------------------------------------- el lienzo de los paneles */
function creaIndicadores(canvas) {
  IND.canvas = canvas;
  IND.ctx = canvas.getContext('2d');
  IND.pr = window.devicePixelRatio || 1;
  return IND;
}

/* El alto de la caja de los paneles: lo fija la VISTA (su hash), no el dato, para que el footprint no salte. */
function panelesDe(e) {
  return e.modo === 'tpo' ? [] : IND_PANELES.filter((c) => (e.ind || []).includes(c));
}

function midePaneles(e) {
  const caja = IND.canvas.parentElement;
  const n = panelesDe(e).length;
  caja.hidden = !n;
  caja.style.height = n * IND_PANEL.ALTO + 'px';
  document.body.classList.toggle('con-ind', !!n);
}

/* Pinta los paneles con la geometria del footprint que se acaba de pintar: g (ancho, bs, x), m (el modelo), i0..i1
 * (las velas visibles). Llamado desde flujo-dibujo.js, en el mismo fotograma. */
function pintaIndicadores(g, m, i0, i1) {
  const e = VISTA;
  const lista = panelesDe(e);
  const reg = { cuadro: ++IND.cuadros, paneles: [], ancho: 0, alto: 0 };
  if (!IND.canvas || !lista.length || !m || !m.velas.length) {
    window.FLUJO_INDICADORES = reg;
    return reg;
  }
  const r = IND.canvas.parentElement.getBoundingClientRect();
  const W = Math.max(200, Math.floor(r.width));
  const Hh = lista.length * IND_PANEL.ALTO;
  if (W !== IND.W || Hh !== IND.H) {
    IND.W = W;
    IND.H = Hh;
    IND.canvas.width = W * IND.pr;
    IND.canvas.height = Hh * IND.pr;
    IND.canvas.style.width = W + 'px';
    IND.canvas.style.height = Hh + 'px';
  }
  const ctx = IND.ctx;
  ctx.setTransform(IND.pr, 0, 0, IND.pr, 0, 0);
  ctx.fillStyle = COLOR.fondo;
  ctx.fillRect(0, 0, W, Hh);
  const mMs = FLUJO_MARCOS[m.marco] * 60000;
  const t0 = Date.parse(m.velas[0].ts);
  const xT = (ms) => g.x(0) - g.bs / 2 + ((ms - t0) / mMs) * g.bs;
  Object.assign(reg, { ancho: W, alto: Hh, pr: IND.pr,
                       eje: { ancho: g.ancho, bs: g.bs, x0: g.x(0), t0: m.velas[0].ts, marco: m.marco } });
  const ctxTit = { familia: FAMILIAS[m.familia].rotulo, unidad: m.unidad === 'usd' ? 'USD' : m.activo,
                   origen: m.velas[0].ts.slice(11, 16) + 'Z' };
  lista.forEach((clave, k) => {
    const y0 = k * IND_PANEL.ALTO;
    const caja = { clave, y0, y1: y0 + IND_PANEL.ALTO, arriba: y0 + IND_PANEL.CABEZA,
                   abajo: y0 + IND_PANEL.ALTO - IND_PANEL.PIE, puntos: [], huecos: [], marcas: [], cambios: [] };
    ctx.strokeStyle = COLOR.rejilla;
    ctx.beginPath();
    ctx.moveTo(0, y0 + 0.5);
    ctx.lineTo(W, y0 + 0.5);
    ctx.stroke();
    const necesita = IND_SERIE[clave];
    let titulo = null;
    if (necesita && !IND.datos) {
      const fallo = IND.fallos.find(([n]) => n === 'indicadores');
      titulo = clave + ' · ' + (fallo ? 'ERROR HTTP ' + fallo[1].http : 'pidiendo…');
      caja.sin_dato = true;
    } else {
      titulo = tituloPanel(clave, IND.datos, ctxTit);
    }
    ctx.font = '9px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = caja.sin_dato ? IND_COLOR.ambar : COLOR.eje;
    ctx.fillText(titulo, 6, y0 + IND_PANEL.CABEZA / 2);
    caja.titulo = titulo;
    if (!caja.sin_dato) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, caja.arriba, g.ancho, caja.abajo - caja.arriba);
      ctx.clip();
      if (clave === 'delta') pintaDelta(ctx, caja, g, m, i0, i1);
      else if (clave === 'cvd') pintaCvd(ctx, caja, g, m, i0, i1);
      else if (clave === 'liq') pintaLiq(ctx, caja, g, xT, IND.datos);
      else pintaSerie(ctx, caja, g, xT, IND.datos, clave);
      ctx.restore();
      ejeDe(ctx, caja, g, clave === 'funding' ? 4 : clave === 'ls' ? 2 : 0);
    }
    reg.paneles.push(caja);
  });
  window.FLUJO_INDICADORES = reg;
  return reg;
}

function escalaDe(vals, centro) {
  const xs = vals.filter((v) => Number.isFinite(v));
  let lo = xs.length ? Math.min(...xs) : 0;
  let hi = xs.length ? Math.max(...xs) : 1;
  if (centro !== undefined) {
    const mx = Math.max(Math.abs(lo - centro), Math.abs(hi - centro)) || 1;
    lo = centro - mx;
    hi = centro + mx;
  } else if (hi === lo) {
    lo -= Math.abs(lo) * 0.001 || 1;
    hi += Math.abs(hi) * 0.001 || 1;
  }
  const margen = (hi - lo) * 0.06;
  return { lo: lo - margen, hi: hi + margen };
}

function yDe(caja, esc) {
  return (v) => caja.arriba + ((esc.hi - v) / (esc.hi - esc.lo)) * (caja.abajo - caja.arriba);
}

function ejeDe(ctx, caja, g, dec) {
  if (!caja.escala) return;
  ctx.font = '9px ui-monospace, monospace';
  ctx.textAlign = 'left';
  ctx.fillStyle = COLOR.eje;
  const y = yDe(caja, caja.escala);
  [caja.escala.hi, caja.escala.lo].forEach((v, k) => {
    const yy = k ? caja.abajo - 4 : caja.arriba + 4;
    ctx.fillText(dec ? v.toFixed(dec) : cifra(String(v)), g.ancho + 6, yy);
  });
  if (caja.escala.lo < 0 && caja.escala.hi > 0) {
    ctx.strokeStyle = IND_COLOR.cero;
    ctx.beginPath();
    ctx.moveTo(0, Math.round(y(0)) + 0.5);
    ctx.lineTo(g.ancho, Math.round(y(0)) + 0.5);
    ctx.stroke();
  }
}

/* Un hueco (o un pendiente) es una banda rayada de su ancho: nunca una barra ni un punto a cero. */
function pintaHueco(ctx, caja, x0, x1, estado) {
  ctx.fillStyle = estado === 'pendiente' ? IND_COLOR.pendiente : IND_COLOR.hueco;
  ctx.fillRect(x0, caja.arriba, Math.max(1, x1 - x0), caja.abajo - caja.arriba);
  caja.huecos.push({ x0: Math.round(x0 * 10) / 10, x1: Math.round(x1 * 10) / 10, estado });
}

function pintaDelta(ctx, caja, g, m, i0, i1) {
  const vis = [];
  for (let i = i0; i <= i1; i++) vis.push(m.velas[i]);
  caja.escala = escalaDe(vis.filter((v) => v.estado !== 'hueco').map((v) => Number(v.delta)), 0);
  const y = yDe(caja, caja.escala);
  for (let i = i0; i <= i1; i++) {
    const v = m.velas[i];
    const w = Math.max(1, Math.floor(g.bs * 0.86));
    const x0 = Math.round(g.x(i) - w / 2);
    if (v.estado === 'hueco') {
      pintaHueco(ctx, caja, x0, x0 + w, 'hueco');
      caja.huecos[caja.huecos.length - 1].ts = v.ts;
      continue;
    }
    const d = Number(v.delta);
    const ya = Math.round(y(Math.max(0, d)));
    const yb = Math.round(y(Math.min(0, d)));
    ctx.fillStyle = rgba(d > 0 ? COLOR.compra : d < 0 ? COLOR.venta : COLOR.neutro, 0.75);
    ctx.fillRect(x0, ya, w, Math.max(1, yb - ya));
    if (v.estado === 'incompleta' || v.estado === 'abierta') {
      ctx.setLineDash(v.estado === 'abierta' ? [2, 2] : []);
      ctx.strokeStyle = v.estado === 'abierta' ? COLOR.eje : IND_COLOR.ambar;
      ctx.strokeRect(x0 - 0.5, ya - 0.5, w + 1, Math.max(1, yb - ya) + 1);
      ctx.setLineDash([]);
    }
    caja.puntos.push({ ts: v.ts, x0, ancho: w, valor: v.delta, y0: ya, y1: Math.max(ya + 1, yb), estado: v.estado });
  }
}

function pintaCvd(ctx, caja, g, m, i0, i1) {
  const todos = cvdDe(m.velas);
  const vis = todos.slice(i0, i1 + 1);
  caja.escala = escalaDe(vis.filter((p) => p.valor !== null).map((p) => Number(p.valor)));
  const y = yDe(caja, caja.escala);
  ctx.strokeStyle = IND_COLOR.linea;
  ctx.lineWidth = 1.5;
  let abierto = false;
  ctx.beginPath();
  for (let i = i0; i <= i1; i++) {
    const p = todos[i];
    const v = m.velas[i];
    if (p.valor === null) {
      const w = Math.max(1, Math.floor(g.bs * 0.86));
      pintaHueco(ctx, caja, Math.round(g.x(i) - w / 2), Math.round(g.x(i) - w / 2) + w, 'hueco');
      caja.huecos[caja.huecos.length - 1].ts = v.ts;
      abierto = false;
      continue;
    }
    const x = Math.round(g.x(i) * 10) / 10;
    const yy = Math.round(y(Number(p.valor)) * 10) / 10;
    if (!abierto || p.origen === p.ts) ctx.moveTo(x, yy);
    else ctx.lineTo(x, yy);
    abierto = true;
    caja.puntos.push({ ts: v.ts, x, valor: p.valor, y: yy, estado: v.estado, origen: p.origen });
  }
  ctx.stroke();
  ctx.lineWidth = 1;
  caja.puntos.forEach((p) => {
    if (p.estado !== 'incompleta' && p.estado !== 'abierta') return;
    ctx.fillStyle = p.estado === 'abierta' ? COLOR.eje : IND_COLOR.ambar;
    ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
    caja.marcas.push({ ts: p.ts, que: p.estado });
  });
}

/* Una o dos series de 5 min como ESCALONES: cada cubo, una linea horizontal de su inicio a su fin; un cubo sin dato,
 * un hueco rayado. OI y OI de Bybit llevan ademas su CAMBIO de cubo a cubo en barras (abajo, escala propia). */
function pintaSerie(ctx, caja, g, xT, d, clave) {
  const cMs = d.cubo_minutos * 60000;
  const series = IND_SERIE[clave].map((k) => d.series[k]);
  const campo = { oi: 'oi', oib: 'oi', funding: 'funding', ls: 'largos' }[clave];
  const visibles = (s) => s.cubos.filter((c) => xT(Date.parse(c.ts) + cMs) > 0 && xT(Date.parse(c.ts)) < g.ancho);
  const vals = [];
  series.forEach((s) => visibles(s).forEach((c) => { if (c.valores) vals.push(Number(c.valores[campo])); }));
  caja.escala = escalaDe(vals);
  const y = yDe(caja, caja.escala);
  series.forEach((s, k) => {
    const segunda = k === 1;
    ctx.strokeStyle = segunda ? IND_COLOR.segunda : IND_COLOR.linea;
    ctx.setLineDash(segunda ? [4, 3] : []);
    let ant = null;
    visibles(s).forEach((c) => {
      const x0 = xT(Date.parse(c.ts));
      const x1 = xT(Date.parse(c.ts) + cMs);
      if (!c.valores) {
        if (!segunda) {
          pintaHueco(ctx, caja, x0, x1, c.estado);
          caja.huecos[caja.huecos.length - 1].ts = c.ts;
        }
        ant = null;
        return;
      }
      const yy = Math.round(y(Number(c.valores[campo])) * 10) / 10;
      ctx.beginPath();
      if (ant !== null) {
        ctx.moveTo(x0, ant);
        ctx.lineTo(x0, yy);
      }
      ctx.moveTo(x0, yy);
      ctx.lineTo(x1, yy);
      ctx.stroke();
      ant = yy;
      caja.puntos.push({ serie: IND_SERIE[clave][k], ts: c.ts, x0: Math.round(x0 * 10) / 10,
                         x1: Math.round(x1 * 10) / 10, valor: c.valores[campo], y: yy, estado: c.estado });
    });
    ctx.setLineDash([]);
  });
  if (clave === 'oi' || clave === 'oib') {
    const s = series[0];
    const cambios = cambiosDe(s.cubos, 'oi');
    const vis = cambios.filter((c) => xT(Date.parse(c.ts) + cMs) > 0 && xT(Date.parse(c.ts)) < g.ancho);
    const mx = Math.max(1, ...vis.filter((c) => c.valor !== null).map((c) => Math.abs(Number(c.valor))));
    caja.escala_cambio = { max: mx, base: caja.abajo, alto: Math.round((caja.abajo - caja.arriba) * 0.35) };
    vis.forEach((c) => {
      if (c.valor === null) return;
      const h = Math.max(1, Math.round((Math.abs(Number(c.valor)) / mx) * caja.escala_cambio.alto));
      const x0 = xT(Date.parse(c.ts));
      const x1 = xT(Date.parse(c.ts) + cMs);
      ctx.fillStyle = rgba(Number(c.valor) >= 0 ? COLOR.compra : COLOR.venta, 0.45);
      ctx.fillRect(x0 + 1, caja.abajo - h, Math.max(1, x1 - x0 - 2), h);
      caja.cambios.push({ ts: c.ts, x0: Math.round(x0 * 10) / 10, x1: Math.round(x1 * 10) / 10, valor: c.valor, alto: h });
    });
  }
}

/* Liquidaciones: las de 5 min, barras (largos liquidados hacia abajo, cortos hacia arriba); las sueltas, puntos a su
 * hora (arriba los cortos, abajo los largos), con un radio por su tamano. Antes de su retencion no hay sueltas. */
function pintaLiq(ctx, caja, g, xT, d) {
  const s = d.series.liquidaciones;
  const cMs = d.cubo_minutos * 60000;
  const vis = s.cubos.filter((c) => xT(Date.parse(c.ts) + cMs) > 0 && xT(Date.parse(c.ts)) < g.ancho);
  const mx = Math.max(...vis.filter((c) => c.valores).map((c) => Math.max(Number(c.valores.largos),
                                                                         Number(c.valores.cortos))), 0);
  caja.escala = { lo: -(mx || 1) * 1.06, hi: (mx || 1) * 1.06 };
  const y = yDe(caja, caja.escala);
  const y0 = Math.round(y(0));
  vis.forEach((c) => {
    const x0 = xT(Date.parse(c.ts));
    const x1 = xT(Date.parse(c.ts) + cMs);
    if (!c.valores) {
      pintaHueco(ctx, caja, x0, x1, c.estado);
      caja.huecos[caja.huecos.length - 1].ts = c.ts;
      return;
    }
    const yc = Math.round(y(Number(c.valores.cortos)));
    const yl = Math.round(y(-Number(c.valores.largos)));
    ctx.fillStyle = rgba(COLOR.compra, 0.7);
    if (yc < y0) ctx.fillRect(x0 + 1, yc, Math.max(1, x1 - x0 - 2), y0 - yc);
    ctx.fillStyle = rgba(COLOR.venta, 0.7);
    if (yl > y0) ctx.fillRect(x0 + 1, y0, Math.max(1, x1 - x0 - 2), yl - y0);
    if (c.estado !== 'completo') {
      ctx.strokeStyle = IND_COLOR.ambar;
      ctx.strokeRect(x0 + 0.5, caja.arriba + 0.5, Math.max(1, x1 - x0 - 1), caja.abajo - caja.arriba - 1);
    }
    caja.puntos.push({ ts: c.ts, x0: Math.round(x0 * 10) / 10, x1: Math.round(x1 * 10) / 10, largos: c.valores.largos,
                       cortos: c.valores.cortos, y_cortos: yc, y_largos: yl, estado: c.estado });
  });
  // antes de la retencion de las sueltas no hay dato: se raya (no es «ninguna»)
  const borde = xT(Date.parse(d.sueltas.desde_dato));
  if (borde > 0) {
    ctx.fillStyle = IND_COLOR.pendiente;
    ctx.fillRect(0, caja.arriba, Math.min(borde, g.ancho), 6);
    caja.sin_sueltas = { hasta_x: Math.round(Math.min(borde, g.ancho) * 10) / 10, desde_dato: d.sueltas.desde_dato };
  }
  const mxs = Math.max(1, ...d.sueltas.eventos.map((ev) => Number(ev.usd)));
  d.sueltas.eventos.forEach((ev) => {
    const x = xT(Date.parse(ev.ts));
    if (x < 0 || x > g.ancho) return;
    const r = 1.5 + 3.5 * Math.sqrt(Number(ev.usd) / mxs);
    const yy = ev.lado === 'short' ? caja.arriba + 6 : caja.abajo - 6;
    ctx.fillStyle = ev.lado === 'short' ? COLOR.fuerte_compra : COLOR.fuerte_venta;
    ctx.beginPath();
    ctx.arc(x, yy, r, 0, 2 * Math.PI);
    ctx.fill();
    caja.marcas.push({ ts: ev.ts, exchange: ev.exchange, lado: ev.lado, usd: ev.usd, x: Math.round(x * 10) / 10, y: yy,
                       r: Math.round(r * 10) / 10 });
  });
}

/* ------------------------------------------------------------- las grandes sobre el footprint */
/* Un circulo por operacion grande, en SU vela (a su hora dentro de la vela) y a su precio. Llamado desde
 * flujo-dibujo.js con el contexto del footprint, ya recortado a su ancho. */
function pintaGrandes(ctx, g, y, m, i0, i1) {
  const d = IND.grandes;
  if (!d || !(VISTA.ind || []).includes('grandes') || i1 < i0) return null;
  const mMs = FLUJO_MARCOS[m.marco] * 60000;
  const t0 = Date.parse(m.velas[0].ts);
  const out = [];
  const umbral = Number(d.umbral_usd_vigente) || 1;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, g.arriba, g.ancho, g.abajo - g.arriba);
  ctx.clip();
  d.operaciones.forEach((o) => {
    const t = Date.parse(o.ts);
    const i = Math.floor((t - t0) / mMs);
    if (i < i0 || i > i1) return;
    const w = Math.max(1, Math.floor(g.bs * 0.86));
    const x0 = Math.round(g.x(i) - w / 2);
    const x = x0 + (w * (t - (t0 + i * mMs))) / mMs;
    const yy = y(Number(o.precio));
    const r = Math.min(14, 3 + 3 * Math.sqrt(Number(o.usd) / umbral));
    ctx.beginPath();
    ctx.arc(x, yy, r, 0, 2 * Math.PI);
    ctx.fillStyle = o.agresor === 'compra' ? 'rgba(62,207,142,0.35)' : 'rgba(224,90,90,0.35)';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.stroke();
    out.push({ ts: o.ts, venue: o.venue, id: o.id, agresor: o.agresor, usd: o.usd, precio: o.precio, vela: m.velas[i].ts,
               x: Math.round(x * 10) / 10, y: Math.round(yy * 10) / 10, r: Math.round(r * 10) / 10,
               fuera: yy < g.arriba || yy > g.abajo });
  });
  ctx.restore();
  return { umbral_usd: d.umbral_usd_vigente, truncada: d.truncada, marcas: out };
}

/* ------------------------------------------------------------- los mandos (una fila de la cabecera) */
function pintaMandosIndicadores() {
  document.querySelectorAll('#mandos-ind input[data-ind]').forEach((c) => {
    c.checked = (VISTA.ind || []).includes(c.dataset.ind);
  });
  document.getElementById('sel-cinta').value = filtroCinta(VISTA);
}

function atiendeMandosIndicadores() {
  const cajas = () => [...document.querySelectorAll('#mandos-ind input[data-ind]')];
  cajas().forEach((c) => c.addEventListener('change', () => {
    const encendidos = cajas().filter((x) => x.checked).map((x) => x.dataset.ind);
    cambia({ ind: INDICADORES.filter((x) => encendidos.includes(x)) });
  }));
  document.getElementById('sel-cinta').addEventListener('change', (ev) => {
    const v = ev.target.value;
    cambia({ cinta: /^\d+(\.\d+)?$/.test(v) && Number(v) > 0 && v !== CINTA_FILTRO[VISTA.activo] ? v : null });
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { IND_PANELES, IND_SERIE, deEntero, cvdDe, cambiosDe, tituloPanel, panelesDe };
}
