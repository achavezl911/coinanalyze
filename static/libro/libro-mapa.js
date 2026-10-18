'use strict';
/* EL MAPA DE LIQUIDEZ · el lienzo (campana 145, OF-4b).
 * ---------------------------------------------------------------------------
 * UN MAPA DE BITS, NO UN RECTANGULO POR CELDA. Lo decidio P1 con el criterio archivado antes de medir
 * (entregas/20261018-0444-libro-pantalla-prediccion.md): en Chromium sin cabeza en 143, con fotos reales de produccion
 * (BTC perpetuos 1 h y 4 h), un fillRect por celda dio un p95 de 50-67 ms por fotograma; el mapa de bits, 16.7-16.8 ms,
 * hecho una vez (B) o rehecho en cada fotograma con lo visible (B'); entre los dos, el criterio se queda con el de menos
 * trabajo por fotograma, B (pintar p95 0.6-0.7 ms contra 5.7-8.5; x1-tmp/c145/p1, tres repeticiones). Cada celda son
 * 2x2 pixeles del mapa de bits de TODA la ventana, que se rehace solo cuando cambian las columnas (llega una del vivo);
 * por fotograma, UN drawImage escalado y sin suavizado, y encima el precio y los ejes.
 *
 * LO QUE SE PINTA EN CADA CELDA (columna = un instante, fila = un nivel al paso):
 *   la cantidad de la familia     su color: su PERCENTIL entre las celdas de la ventana (escalaPercentil, P2); un
 *                                 cero CONOCIDO es el fondo
 *   un nivel que conocen n de N   damero: de los 4 subpixeles, round(4n/N) del color y el resto DESCONOCIDO
 *   un nivel que no conoce nadie  DESCONOCIDO, nunca el fondo (nunca cero)
 *   un instante HUECO             la columna entera de su color: ningun venue tenia libro; no se rellena ni se estira
 *   un instante sin escribir aun  la columna de su color
 * Encima, la mejor compra y la mejor venta de la familia en cada instante.
 *
 * EL CONTRATO DE LO PINTADO, que lee K111: cada vez que pinta, el lienzo deja en `window.LIBRO_PINTADO.mapa` lo que
 * ACABA de dibujar: la escala, el eje (que nivel va en que pixel) y, por columna visible, su instante, su estado, sus
 * pixeles, los venues con foto, las mejores y su y, y por celda conocida su nivel, compra, venta, cuantos la conocen y
 * su indice de color. K111 no se lo cree a pies juntillas: lee los pixeles del lienzo.
 */

const MAPA = { EJE_P: 76, EJE_T: 20 };
const MAPA_COLOR = {
  fondo: [10, 13, 18], desconocido: [46, 46, 46], hueco: [70, 48, 20], pendiente: [30, 36, 46],
  compra: '#3ecf8e', venta: '#e05a5a', eje: '#8891a0',
  rampa: [[28, 30, 72], [86, 30, 110], [190, 50, 70], [245, 140, 40], [255, 245, 180]],
};
// la rampa en 256 escalones (de la cantidad mas pequena a la mayor)
const MAPA_LUT = (() => {
  const out = [];
  const r = MAPA_COLOR.rampa;
  for (let i = 0; i < 256; i++) {
    const x = (i / 255) * (r.length - 1);
    const a = Math.min(r.length - 2, Math.floor(x));
    const f = x - a;
    out.push(r[a].map((c, j) => Math.round(c + (r[a + 1][j] - c) * f)));
  }
  return out;
})();
// los subpixeles que se colorean, en este orden: con 2 de 4, un damero
const MAPA_SUB = [[0, 0], [1, 1], [1, 0], [0, 1]];

function cuadritos(n, N) {
  return n >= N ? 4 : Math.max(1, Math.round((4 * n) / N));
}

function rgb(c) {
  return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
}

function creaMapa(canvas, alLeer) {
  const L = { cv: canvas, ctx: canvas.getContext('2d'), pr: window.devicePixelRatio || 1, W: 0, H: 0, modelo: null,
              fin: 0, ver: 0, sigue: true, pendiente: false, cuadros: 0, arrastre: null, bmp: null, esc: null,
              clave: null };

  function mide() {
    const r = L.cv.parentElement.getBoundingClientRect();
    L.W = Math.max(200, Math.floor(r.width));
    L.H = Math.max(200, Math.floor(r.height));
    L.cv.width = L.W * L.pr;
    L.cv.height = L.H * L.pr;
    L.cv.style.width = L.W + 'px';
    L.cv.style.height = L.H + 'px';
  }

  function pide() {
    if (L.pendiente) return;
    L.pendiente = true;
    requestAnimationFrame(() => {
      L.pendiente = false;
      pinta();
    });
  }

  function rango(m) {
    let kMin = Infinity;
    let kMax = -Infinity;
    m.columnas.forEach((c) => {
      if (c.suma) {
        kMin = Math.min(kMin, c.suma.lo);
        kMax = Math.max(kMax, c.suma.hi);
      }
    });
    return kMin === Infinity ? null : [kMin, kMax];
  }

  /* El mapa de bits de las columnas [j0, j1] y las filas [kLo, kHi] (k alto arriba), con la escala `esc`. */
  function mapaDeBits(m, j0, j1, kLo, kHi, esc) {
    const w = 2 * (j1 - j0 + 1);
    const h = 2 * (kHi - kLo + 1);
    const img = new ImageData(w, h);
    const px = img.data;
    const pon = (x, y, c) => {
      const o = (y * w + x) * 4;
      px[o] = c[0];
      px[o + 1] = c[1];
      px[o + 2] = c[2];
      px[o + 3] = 255;
    };
    for (let j = j0; j <= j1; j++) {
      const col = m.columnas[j];
      const x0 = 2 * (j - j0);
      const s = col.suma;
      for (let k = kHi; k >= kLo; k--) {
        const y0 = 2 * (kHi - k);
        let base;
        let color = null;
        let sub = 0;
        if (col.estado !== 'foto') base = MAPA_COLOR[col.estado];
        else if (!s || k < s.lo || k > s.hi || !s.n[k - s.lo]) base = MAPA_COLOR.desconocido;
        else {
          const i = k - s.lo;
          const ix = esc.indice(enUnidad(s.c[i] + s.v[i], k, m.paso, m.unidad));
          sub = cuadritos(s.n[i], s.N);
          color = ix < 0 ? MAPA_COLOR.fondo : MAPA_LUT[ix];
          base = sub === 4 ? color : MAPA_COLOR.desconocido;
        }
        pon(x0, y0, base);
        pon(x0 + 1, y0, base);
        pon(x0, y0 + 1, base);
        pon(x0 + 1, y0 + 1, base);
        for (let q = 0; q < sub && sub < 4; q++) pon(x0 + MAPA_SUB[q][0], y0 + MAPA_SUB[q][1], color);
      }
    }
    const cv = document.createElement('canvas');
    cv.width = w;
    cv.height = h;
    cv.getContext('2d').putImageData(img, 0, 0);
    return cv;
  }

  /* ------------------------------------------------------------ pintar */
  function pinta() {
    const ctx = L.ctx;
    ctx.setTransform(L.pr, 0, 0, L.pr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = rgb(MAPA_COLOR.fondo);
    ctx.fillRect(0, 0, L.W, L.H);
    const m = L.modelo;
    const reg = { cuadro: ++L.cuadros, ancho: L.W, alto: L.H, columnas: [] };
    if (m) {
      Object.assign(reg, { activo: m.activo, familia: m.familia, venues: m.venues, N: m.N, paso: m.paso, cada: m.cada,
                           unidad: m.unidad });
    }
    const r = m && rango(m);
    if (!m || !m.columnas.length || !r) {
      window.LIBRO_PINTADO.mapa = reg;
      return;
    }
    const ancho = L.W - MAPA.EJE_P;
    const alto = L.H - MAPA.EJE_T;
    const n = m.columnas.length;
    const j0 = Math.max(0, Math.floor(L.fin - L.ver + 1));
    const j1 = Math.min(n - 1, Math.ceil(L.fin));
    // lo visible en vertical: lo que conocen las columnas que se ven, con dos filas de margen
    let lo = Infinity;
    let hi = -Infinity;
    for (let j = j0; j <= j1; j++) {
      const s = m.columnas[j].suma;
      if (s) {
        lo = Math.min(lo, s.lo);
        hi = Math.max(hi, s.hi);
      }
    }
    if (lo === Infinity) [lo, hi] = r;
    lo -= 2;
    hi += 2;
    const filas = hi - lo + 1;
    // el mapa de bits de TODA la ventana (P1: B), con la escala (P2) de toda la ventana: se rehace cuando cambian las
    // columnas; sus filas, las de la ventana con dos de margen (las que puede pedir lo visible)
    const clave = [n, m.columnas[0].ts, m.columnas[n - 1].ts, r[0], r[1], m.unidad, m.version || 0].join('|');
    if (clave !== L.clave) {
      L.esc = escalaPercentil(m.columnas, 0, n - 1, m.paso, m.unidad);
      L.bmp = mapaDeBits(m, 0, n - 1, r[0] - 2, r[1] + 2, L.esc);
      L.clave = clave;
    }
    const esc = L.esc;
    const bs = ancho / L.ver;
    const fh = alto / filas;
    const xDe = (j) => ancho - (L.fin - j + 1) * bs;
    const yDe = (k) => (hi - k) * fh; // el borde de ARRIBA de la fila k
    const yPrecio = (p) => (hi + 1 - Number(p) / Number(m.paso)) * fh;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, ancho, alto);
    ctx.clip();
    ctx.drawImage(L.bmp, 2 * (L.fin - L.ver + 1), 2 * (r[1] + 2 - hi), 2 * L.ver, 2 * filas, 0, 0, ancho, alto);
    // el precio encima: la mejor compra y la mejor venta de la familia en cada instante (con un halo oscuro, para que
    // se lea sobre cualquier color del mapa)
    [['mejorCompra', MAPA_COLOR.compra], ['mejorVenta', MAPA_COLOR.venta]].forEach(([campo, color]) => {
      ctx.beginPath();
      let dentro = false;
      for (let j = j0; j <= j1; j++) {
        const s = m.columnas[j].suma;
        if (!s) {
          dentro = false;
          continue;
        }
        const x = xDe(j) + bs / 2;
        const y = yPrecio(s[campo]);
        if (dentro) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
        dentro = true;
      }
      ctx.strokeStyle = 'rgba(0,0,0,0.75)';
      ctx.lineWidth = 4;
      ctx.stroke();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
    ctx.restore();
    // los ejes
    ctx.fillStyle = MAPA_COLOR.eje;
    ctx.font = '10px ui-monospace, monospace';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    const cada = Math.max(1, Math.ceil(28 / fh));
    for (let k = Math.ceil(lo / cada) * cada; k <= hi; k += cada) {
      ctx.fillText(nivelTexto(k, m.paso), ancho + 6, yDe(k) + fh / 2);
    }
    ctx.textAlign = 'center';
    const ct = Math.max(1, Math.ceil(80 / bs));
    for (let j = Math.ceil(j0 / ct) * ct; j <= j1; j += ct) {
      if (xDe(j) + bs / 2 < 30) continue;
      ctx.fillText(new Date(m.columnas[j].ts).toISOString().slice(11, 19), xDe(j) + bs / 2, L.H - MAPA.EJE_T / 2);
    }
    // el contrato: lo que ACABA de pintarse
    Object.assign(reg, { escala: { tipo: 'percentil de la ventana', celdas: esc.n, desde: isoZ(m.columnas[0].ts),
                                   hasta: isoZ(m.columnas[n - 1].ts) },
                         eje: { lo, hi, fila: fh, columna: bs, fin: L.fin, ver: L.ver, ancho, alto } });
    for (let j = j0; j <= j1; j++) {
      const col = m.columnas[j];
      const s = col.suma;
      const x0 = xDe(j);
      const c = { ts: isoZ(col.ts), estado: col.estado, origen: col.origen, x0, x1: x0 + bs,
                  venues: s ? s.venues : [], lo: s ? s.lo : null, hi: s ? s.hi : null,
                  mejor_compra: s ? s.mejorCompra : null, mejor_venta: s ? s.mejorVenta : null,
                  y_compra: s ? yPrecio(s.mejorCompra) : null, y_venta: s ? yPrecio(s.mejorVenta) : null, celdas: [] };
      if (s && col.estado === 'foto') {
        for (let k = Math.max(lo, s.lo); k <= Math.min(hi, s.hi); k++) {
          const i = k - s.lo;
          if (!s.n[i]) continue;
          const q = enUnidad(s.c[i] + s.v[i], k, m.paso, m.unidad);
          c.celdas.push([k, s.c[i], s.v[i], s.n[i], esc.indice(q)]);
        }
      }
      reg.columnas.push(c);
    }
    window.LIBRO_PINTADO.mapa = reg;
  }

  /* --------------------------------------------------------- lo que se toca */
  function acota() {
    const n = L.modelo ? L.modelo.columnas.length : 0;
    L.ver = Math.min(Math.max(n, 10), Math.max(10, L.ver));
    L.fin = Math.min(n - 1, Math.max(Math.min(n - 1, L.ver - 1), L.fin));
    L.sigue = L.fin >= n - 1;
  }

  function lee(ev) {
    const m = L.modelo;
    const reg = window.LIBRO_PINTADO.mapa;
    if (!m || !reg || !reg.eje || !alLeer) return;
    const r = L.cv.getBoundingClientRect();
    const x = ev.clientX - r.left;
    const y = ev.clientY - r.top;
    const j = Math.floor(L.fin + 1 - (reg.eje.ancho - x) / reg.eje.columna);
    const col = m.columnas[j];
    if (!col || x > reg.eje.ancho) return alLeer(null);
    alLeer(col, Math.floor(reg.eje.hi + 1 - y / reg.eje.fila));
  }

  L.cv.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    L.ver *= ev.deltaY > 0 ? 1.12 : 1 / 1.12;
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
    if (L.arrastre && L.modelo) {
      L.fin = L.arrastre.fin - (ev.clientX - L.arrastre.x) / ((L.W - MAPA.EJE_P) / L.ver);
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
    /* el modelo entero (una vista nueva): `ver` columnas a la vista (por omision, todas), la mas nueva a la derecha */
    pon(modelo, ver) {
      L.modelo = modelo;
      L.clave = null;
      L.bmp = null;
      const n = modelo ? modelo.columnas.length : 0;
      L.ver = Math.max(10, Math.min(n, ver || n));
      L.fin = n - 1;
      acota();
      pide();
    },
    /* columnas nuevas (el vivo): si se miraba el final, se sigue mirando */
    actualiza() {
      if (!L.modelo) return;
      L.modelo.version = (L.modelo.version || 0) + 1;
      if (L.sigue) L.fin = L.modelo.columnas.length - 1;
      acota();
      pide();
    },
    pinta,
    pide,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MAPA, MAPA_COLOR, MAPA_LUT, MAPA_SUB, cuadritos };
}
