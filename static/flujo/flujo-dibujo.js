'use strict';
/* EL FOOTPRINT · el lienzo (campana 142, OF-2).
 * ---------------------------------------------------------------------------
 * LIENZO PROPIO, NO LIGHTWEIGHT-CHARTS. Lo decidio P1 con el criterio archivado ANTES de medir
 * (entregas/20261017-1207-footprint-prediccion.md): en Chromium sin cabeza en 143, con 120 velas del maximo de niveles
 * medido, la serie propia de lightweight-charts 5.2.0 dio un p95 de 50.0 ms por fotograma al desplazar y 49.9 al hacer
 * zoom; este lienzo, 33.4 y 33.4 (x1-tmp/c142/banco-p1, tres repeticiones). El criterio era <= 33.4.
 *
 * NIVEL DE DETALLE: los numeros (venta x compra) solo se escriben si la fila mide >= 11 px y la vela >= 56 px; si no,
 * la celda es su color. Las marcas (POC, value area, desequilibrios, cobertura) se pintan siempre.
 *
 * EL CONTRATO DE LO PINTADO, que lee K109: cada vez que pinta, el lienzo deja en `window.FLUJO_PINTADO` lo que ACABA de
 * dibujar, apuntado en el mismo sitio donde se dibuja: por vela visible su estado y su marca, el POC y la value area con
 * sus pixeles, el resumen, y por nivel su rectangulo, el TEXTO que se le paso a fillText (null si no cupo), el color, el
 * filtro y los desequilibrios. Lo que no se pinta no se apunta.
 */

const LZ = {
  EJE_P: 76, // eje de precios, a la derecha
  EJE_T: 20, // eje de tiempo, abajo
  RESUMEN: 44, // tres filas por vela: delta, volumen, operaciones
  CABEZA: 16, // la marca de cobertura de cada vela, arriba
  FILA_TEXTO: 11,
  VELA_TEXTO: 56,
  VELA_RESUMEN: 40,
};
const COLOR = {
  fondo: '#0a0d12', rejilla: 'rgba(255,255,255,0.05)', eje: '#8891a0', texto: '#e6e9ee', mudo: '#5b6472',
  compra: [62, 207, 142], venta: [224, 90, 90], neutro: [136, 145, 160], poc: '#f2cc60', va: '#5b9dd9',
  ambar: '#e6b75a', fuerte_compra: '#7dffc0', fuerte_venta: '#ff8f8f', grande: '#ffffff',
};
const ALFAS = [0.14, 0.22, 0.3, 0.38, 0.46, 0.54, 0.62, 0.7, 0.78];

function rgba(c, a) {
  return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')';
}

function creaLienzo(canvas, alLeer) {
  const L = {
    cv: canvas, ctx: canvas.getContext('2d'), pr: window.devicePixelRatio || 1, W: 0, H: 0,
    modelo: null, fin: 0, ver: 40, sigue: true, pendiente: false, cuadros: 0, raton: null, arrastre: null,
  };

  function mide() {
    const r = L.cv.parentElement.getBoundingClientRect();
    L.W = Math.max(200, Math.floor(r.width));
    L.H = Math.max(200, Math.floor(r.height));
    L.cv.width = L.W * L.pr;
    L.cv.height = L.H * L.pr;
    L.cv.style.width = L.W + 'px';
    L.cv.style.height = L.H + 'px';
  }

  function geo() {
    const ancho = L.W - LZ.EJE_P;
    const arriba = LZ.CABEZA;
    const abajo = L.H - LZ.EJE_T - LZ.RESUMEN;
    const bs = ancho / L.ver;
    return { ancho, arriba, abajo, bs, x: (i) => ancho - (L.fin - i + 0.5) * bs };
  }

  function visibles(g) {
    const n = L.modelo ? L.modelo.velas.length : 0;
    const i0 = Math.max(0, Math.ceil(L.fin - L.ver + 0.5));
    const i1 = Math.min(n - 1, Math.floor(L.fin + 0.5));
    return { i0, i1, g };
  }

  function pide() {
    if (L.pendiente) return;
    L.pendiente = true;
    requestAnimationFrame(() => {
      L.pendiente = false;
      pinta();
    });
  }

  /* ------------------------------------------------------------ pintar */
  function pinta() {
    const ctx = L.ctx;
    ctx.setTransform(L.pr, 0, 0, L.pr, 0, 0);
    ctx.fillStyle = COLOR.fondo;
    ctx.fillRect(0, 0, L.W, L.H);
    const reg = { cuadro: ++L.cuadros, ancho: L.W, alto: L.H, ver: L.ver, fin: L.fin, velas: [] };
    const m = L.modelo;
    if (!m || !m.velas.length) {
      window.FLUJO_PINTADO = reg;
      return;
    }
    Object.assign(reg, { activo: m.activo, marco: m.marco, familia: m.familia, venues: m.venues, paso: m.paso,
                         unidad: m.unidad, umbrales: m.umbrales });
    const g = geo();
    const { i0, i1 } = visibles(g);
    const paso = Number(m.paso);
    let lo = Infinity;
    let hi = -Infinity;
    for (let i = i0; i <= i1; i++) {
      const nv = m.velas[i].niveles;
      if (!nv.length) continue;
      lo = Math.min(lo, Number(nv[0].nivel));
      hi = Math.max(hi, Number(nv[nv.length - 1].nivel) + paso);
    }
    if (lo === Infinity) {
      lo = 0;
      hi = 1;
    }
    const margen = Math.max(paso, (hi - lo) * 0.04);
    lo -= margen;
    hi += margen;
    const alto = g.abajo - g.arriba;
    const y = (p) => g.arriba + ((hi - p) / (hi - lo)) * alto;
    reg.escala = { lo, hi, arriba: g.arriba, abajo: g.abajo };
    rejilla(ctx, g, lo, hi, y, paso);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, g.ancho, L.H);
    ctx.clip();
    for (let i = i0; i <= i1; i++) reg.velas.push(pintaVela(ctx, m.velas[i], g.x(i), g, y, m));
    ctx.restore();
    // OF-3 (campana 143): las capas, encima de las velas, con la misma escala y su contrato (flujo-capas.js)
    reg.capas = m.capas && typeof pintaCapas === 'function' && i1 >= i0 ? pintaCapas(ctx, g, y, m, paso, i0, i1) : null;
    ejeTiempo(ctx, g, i0, i1, m);
    window.FLUJO_PINTADO = reg;
  }

  function rejilla(ctx, g, lo, hi, y, paso) {
    const dec = (String(L.modelo.paso).split('.')[1] || '').length;
    const filas = Math.max(1, Math.floor((g.abajo - g.arriba) / 32));
    // una etiqueta cada 1, 2, 5, 10, 20... pasos, la primera que deje >= 32 px entre dos
    let cada = paso;
    for (let k = 1; (hi - lo) / cada > filas; k++) cada = paso * [1, 2, 5][k % 3] * Math.pow(10, Math.floor(k / 3));
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (let p = Math.ceil(lo / cada) * cada; p <= hi; p += cada) {
      const yy = Math.round(y(p)) + 0.5;
      ctx.strokeStyle = COLOR.rejilla;
      ctx.beginPath();
      ctx.moveTo(0, yy);
      ctx.lineTo(g.ancho, yy);
      ctx.stroke();
      ctx.fillStyle = COLOR.eje;
      ctx.fillText(p.toFixed(dec), g.ancho + 6, yy);
    }
  }

  function ejeTiempo(ctx, g, i0, i1, m) {
    ctx.fillStyle = COLOR.eje;
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const cada = Math.max(1, Math.ceil(70 / g.bs));
    for (let i = Math.ceil(i0 / cada) * cada; i <= i1; i += cada) {
      const t = m.velas[i].ts;
      const txt = m.marco === '1d' ? t.slice(5, 10) : m.marco === '4h' ? t.slice(5, 10) + ' ' + t.slice(11, 16) : t.slice(11, 16);
      ctx.fillText(txt, g.x(i), L.H - LZ.EJE_T / 2);
    }
  }

  /* UNA VELA: lo que se dibuja y, en el mismo sitio, lo que se apunta. */
  function pintaVela(ctx, v, xc, g, y, m) {
    const w = Math.max(1, Math.floor(g.bs * 0.86));
    const x0 = Math.round(xc - w / 2);
    const paso = Number(m.paso);
    const r = { ts: v.ts, estado: v.estado, faltan: v.faltan, esperados: v.esperados, x0, ancho: w, marca: null,
                poc: null, va: null, resumen: null, niveles: [] };
    const nv = v.niveles;
    let yTop = g.arriba;
    let yBot = g.abajo;
    if (nv.length) {
      yTop = Math.round(y(Number(nv[nv.length - 1].nivel) + paso));
      yBot = Math.round(y(Number(nv[0].nivel)));
    }
    // LA COBERTURA SE VE: un hueco no se pinta como una vela, una incompleta dice cuanto le falta
    ctx.font = '9px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const marca = { abierta: 'en curso', hueco: 'hueco', vacia: '0 ops' }[v.estado] ||
      (v.estado === 'incompleta' ? 'faltan ' + v.faltan + '/' + v.esperados : null);
    if (v.estado === 'hueco') {
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = COLOR.mudo;
      ctx.strokeRect(x0 + 0.5, g.arriba + 0.5, w - 1, g.abajo - g.arriba - 1);
      ctx.setLineDash([]);
    } else if (v.estado === 'incompleta' || v.estado === 'abierta') {
      ctx.setLineDash(v.estado === 'abierta' ? [2, 3] : []);
      ctx.strokeStyle = v.estado === 'abierta' ? COLOR.eje : COLOR.ambar;
      ctx.strokeRect(x0 - 1.5, yTop - 1.5, w + 3, yBot - yTop + 3);
      ctx.setLineDash([]);
    }
    if (marca) {
      ctx.fillStyle = v.estado === 'incompleta' ? COLOR.ambar : COLOR.mudo;
      ctx.fillRect(xc - 2, 2, 4, 4);
      if (w >= ctx.measureText(marca).width + 4) {
        ctx.fillText(marca, xc, LZ.CABEZA / 2 + 3);
        r.marca = marca;
      }
    }
    // LAS CELDAS
    let maxAbs = 0;
    nv.forEach((l) => { maxAbs = Math.max(maxAbs, Math.abs(Number(l.delta))); });
    const alto1 = nv.length ? Math.abs(y(Number(nv[0].nivel)) - y(Number(nv[0].nivel) + paso)) : 0;
    const conTexto = alto1 >= LZ.FILA_TEXTO && w >= LZ.VELA_TEXTO;
    const des = v.des || [];
    nv.forEach((l, k) => {
      const y0 = Math.round(y(Number(l.nivel) + paso));
      const y1 = Math.round(y(Number(l.nivel)));
      const d = Number(l.delta);
      const color = d > 0 ? 'compra' : d < 0 ? 'venta' : 'neutro';
      const fil = filtro(l.total, m.filtro);
      const x = des[k] || {};
      const fila = { nivel: l.nivel, y0, y1, venta: l.venta, compra: l.compra, delta: l.delta, total: l.total,
                     texto_venta: null, texto_compra: null, color, filtro: fil, dc: !!x.dc, dv: !!x.dv, ac: !!x.ac,
                     av: !!x.av };
      if (fil === 'escondida') {
        r.niveles.push(fila);
        return;
      }
      const a = ALFAS[maxAbs ? Math.round((8 * Math.abs(d)) / maxAbs) : 0] * (fil === 'atenuada' ? 0.25 : 1);
      ctx.fillStyle = rgba(COLOR[color], a.toFixed(3));
      ctx.fillRect(x0, y0, w, Math.max(1, y1 - y0 - (conTexto ? 1 : 0)));
      if (fil === 'grande') {
        ctx.strokeStyle = COLOR.grande;
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, Math.max(1, y1 - y0 - 1));
      }
      // los desequilibrios: una barra en el borde de su lado (mas gruesa si es parte de un apilado)
      if (x.dc) {
        ctx.fillStyle = COLOR.fuerte_compra;
        ctx.fillRect(x0 + w - (x.ac ? 4 : 2), y0, x.ac ? 4 : 2, Math.max(1, y1 - y0 - 1));
      }
      if (x.dv) {
        ctx.fillStyle = COLOR.fuerte_venta;
        ctx.fillRect(x0, y0, x.av ? 4 : 2, Math.max(1, y1 - y0 - 1));
      }
      if (conTexto && fil !== 'atenuada') {
        const ym = (y0 + y1) / 2;
        ctx.font = (x.dv ? 'bold ' : '') + '10px ui-monospace, monospace';
        ctx.fillStyle = x.dv ? COLOR.fuerte_venta : COLOR.texto;
        ctx.textAlign = 'right';
        fila.texto_venta = cifra(l.venta);
        ctx.fillText(fila.texto_venta, xc - 4, ym);
        ctx.font = (x.dc ? 'bold ' : '') + '10px ui-monospace, monospace';
        ctx.fillStyle = x.dc ? COLOR.fuerte_compra : COLOR.texto;
        ctx.textAlign = 'left';
        fila.texto_compra = cifra(l.compra);
        ctx.fillText(fila.texto_compra, xc + 4, ym);
      }
      r.niveles.push(fila);
    });
    // EL POC de la vela, servido: un marco en su fila
    if (v.poc !== null && v.poc !== undefined) {
      const y0 = Math.round(y(Number(v.poc) + paso));
      const y1 = Math.round(y(Number(v.poc)));
      ctx.strokeStyle = COLOR.poc;
      ctx.lineWidth = 1;
      ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, Math.max(1, y1 - y0 - 1));
      r.poc = { nivel: v.poc, y0, y1 };
    }
    // LA VALUE AREA de la vela, servida: una barra a su izquierda de VAL a VAH + paso
    if (v.value_area) {
      const y0 = Math.round(y(Number(v.value_area.vah) + paso));
      const y1 = Math.round(y(Number(v.value_area.val)));
      ctx.fillStyle = COLOR.va;
      ctx.fillRect(x0 - 3, y0, 2, y1 - y0);
      r.va = { val: v.value_area.val, vah: v.value_area.vah, y0, y1 };
    }
    // EL RESUMEN de la vela, servido: delta, volumen y operaciones
    if (nv.length) {
      const yr = g.abajo + 4;
      const d = Number(v.delta);
      ctx.fillStyle = rgba(d > 0 ? COLOR.compra : d < 0 ? COLOR.venta : COLOR.neutro, 0.35);
      ctx.fillRect(x0, yr, w, 12);
      r.resumen = { delta: null, total: null, operaciones: null };
      if (w >= LZ.VELA_RESUMEN) {
        ctx.font = '9px ui-monospace, monospace';
        ctx.textAlign = 'center';
        ctx.fillStyle = COLOR.texto;
        r.resumen.delta = (d > 0 ? '+' : '') + cifra(v.delta);
        ctx.fillText(r.resumen.delta, xc, yr + 6);
        ctx.fillStyle = COLOR.eje;
        r.resumen.total = cifra(v.total);
        ctx.fillText(r.resumen.total, xc, yr + 20);
        r.resumen.operaciones = String(v.operaciones);
        ctx.fillText(r.resumen.operaciones, xc, yr + 34);
      }
    }
    return r;
  }

  /* --------------------------------------------------------- lo que se toca */
  function acota() {
    const n = L.modelo ? L.modelo.velas.length : 0;
    L.ver = Math.min(400, Math.max(5, L.ver));
    L.fin = Math.min(n - 1 + L.ver * 0.3, Math.max(L.ver * 0.3, L.fin));
    L.sigue = L.fin >= n - 1;
  }

  function lee(ev) {
    if (!L.modelo || !alLeer) return;
    const r = L.cv.getBoundingClientRect();
    const g = geo();
    const i = Math.round(L.fin - (g.ancho - (ev.clientX - r.left)) / g.bs + 0.5);
    const v = L.modelo.velas[i];
    if (!v) return alLeer(null);
    const reg = window.FLUJO_PINTADO || {};
    const yy = ev.clientY - r.top;
    const vela = (reg.velas || []).find((x) => x.ts === v.ts);
    const fila = vela && vela.niveles.find((f) => f.y0 <= yy && yy < f.y1);
    alLeer(v, fila || null);
  }

  L.cv.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    const r = L.cv.getBoundingClientRect();
    const g = geo();
    const dx = g.ancho - (ev.clientX - r.left);
    const bajo = L.fin - dx / g.bs;
    L.ver *= ev.deltaY > 0 ? 1.12 : 1 / 1.12;
    acota();
    L.fin = bajo + dx / ((L.W - LZ.EJE_P) / L.ver);
    acota();
    pide();
  }, { passive: false });
  L.cv.addEventListener('mousedown', (ev) => {
    L.arrastre = { x: ev.clientX, fin: L.fin };
  });
  window.addEventListener('mouseup', () => {
    L.arrastre = null;
  });
  L.cv.addEventListener('mousemove', (ev) => {
    if (L.arrastre) {
      L.fin = L.arrastre.fin - (ev.clientX - L.arrastre.x) / geo().bs;
      acota();
      pide();
    }
    lee(ev);
  });
  new ResizeObserver(() => {
    mide();
    pide();
  }).observe(L.cv.parentElement);
  mide();

  return {
    /* el modelo entero (una vista nueva): se mira el final, con `ver` velas */
    pon(modelo, ver) {
      L.modelo = modelo;
      L.ver = ver;
      L.fin = modelo.velas.length - 1;
      acota();
      pide();
    },
    /* velas que cambian (el latido): si se estaba mirando el final, se sigue mirando */
    actualiza() {
      if (L.sigue) L.fin = L.modelo.velas.length - 1;
      acota();
      pide();
    },
    pinta,
    pide,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LZ, creaLienzo };
}
