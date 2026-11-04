'use strict';
/* EL MAPA DE LIQUIDEZ · el lienzo (campana 145, OF-4b; profesional en la 149 B).
 * ---------------------------------------------------------------------------
 * UN MAPA DE BITS, NO UN RECTANGULO POR CELDA (145 P1, entregas/20261018-0444-libro-pantalla-prediccion.md): cada celda
 * son 2x2 pixeles del mapa de bits de TODA la ventana, que se rehace cuando cambian las columnas o los cortes de color;
 * por fotograma, UN drawImage escalado y sin suavizado, y encima el precio, los perfiles y los ejes.
 *
 * LO QUE SE PINTA EN CADA CELDA (columna = un instante, fila = un nivel al paso):
 *   la cantidad de la familia     BICROMO (E-02): el lado mayor manda; compra en la familia de MAPA_COLOR.compra, venta
 *                                 en la de MAPA_COLOR.venta, 256 escalones del fondo al color lleno. El indice sale de
 *                                 los dos cortes de lo VISIBLE (escalaCortes: p20 y p98 por omision, el mando de
 *                                 intensidad los mueve): debajo, el fondo; entre, lineal; encima, saturado (los muros
 *                                 salen como lineas vivas). Un cero CONOCIDO es el fondo.
 *   un nivel que conocen n de N   el MISMO color (P2, entregas/20261104-0722-libro-pro-b-prediccion.md); n de N lo dice
 *                                 la lectura. El damero de la 145 se fue.
 *   un nivel que no conoce nadie  DESCONOCIDO: un neutro apenas distinto del fondo, nunca un color de la paleta
 *   un instante HUECO             rayado tenue, y «sin datos» debajo: ningun venue tenia libro; no se rellena
 *   un instante sin escribir aun  la columna de su color
 * La capa honda (/api/libro/honda) entra en la suma de cada columna antes de pintar (libro-calculo.js, juntaHonda).
 * Alrededor: la mejor compra y la mejor venta en escalones de 1 px, el ultimo precio en el acento; a la derecha la
 * banda «ahora» (la ultima columna estirada), el perfil del volumen negociado de lo visible (footprint 1m) y el perfil
 * del libro de ahora; debajo, el volumen por minuto.
 *
 * CADA PIXEL ES DE UNA CELDA (145 R1): una celda tiene al menos 2x2 pixeles de PANTALLA. Lo que no cabe NO SE ALEJA; la
 * linea de debajo del mapa lo dice, y el contrato tambien.
 *
 * EL CONTRATO DE LO PINTADO, que lee K111: `window.LIBRO_PINTADO.mapa`: la escala (sus cortes y de que celdas salen), el
 * eje, por columna visible sus celdas [k, compra, venta, n, indice, lado, n_honda], y la banda «ahora», el perfil del
 * libro, el del volumen y el volumen de abajo. K111 no se lo cree: lo recalcula de las respuestas y lee los pixeles.
 */

const MAPA = { EJE_P: 76, EJE_T: 20, AHORA: 28, VOLUMEN: 64, PERFIL: 64, BAJO: 40 };
MAPA.DERECHA = MAPA.AHORA + MAPA.VOLUMEN + MAPA.PERFIL + MAPA.EJE_P; // lo que no es mapa, a la derecha
MAPA.ABAJO = MAPA.BAJO + MAPA.EJE_T; // y debajo
const MAPA_COLOR = {
  fondo: [10, 13, 18], desconocido: [26, 26, 26], hueco: [34, 29, 22], hueco_raya: [52, 42, 26], pendiente: [30, 36, 46],
  compra: '#60a5fa', venta: '#e05a5a', eje: '#8891a0', // E-02 (OF-6a): los colores propios de cada lado
  referencia: '#f2cc60', // el acento de la casa (--acento de flujo.css): el ultimo precio
};
function hexRgb(h) {
  return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
}
/* Las dos familias, 256 escalones cada una: del fondo (0) al color lleno del lado (255), en linea recta. */
function lutLado(hex) {
  const a = MAPA_COLOR.fondo;
  const b = hexRgb(hex);
  const out = [];
  for (let i = 0; i < 256; i++) out.push(a.map((c, j) => Math.round(c + ((b[j] - c) * i) / 255)));
  return out;
}
const MAPA_LUT_COMPRA = lutLado(MAPA_COLOR.compra);
const MAPA_LUT_VENTA = lutLado(MAPA_COLOR.venta);

function luminancia(c) {
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

/* El color de un instante HUECO en (columna j, nivel k): rayas diagonales, una de cada tres. */
function colorHueco(j, k) {
  return (j + k) % 3 === 0 ? MAPA_COLOR.hueco_raya : MAPA_COLOR.hueco;
}

/* El lado de una celda: el mayor manda (0 compra, 1 venta; empate, compra). */
function ladoDe(c, v) {
  return v > c ? 1 : 0;
}

function rgb(c) {
  return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
}

/* Las columnas y los niveles que caben en un lienzo de W x H (CSS) con pr pixeles de pantalla por pixel CSS: 2 por celda. */
function cabenEn(W, H, pr) {
  return [Math.max(1, Math.floor(((W - MAPA.DERECHA) * pr) / 2)), Math.max(1, Math.floor(((H - MAPA.ABAJO) * pr) / 2))];
}

/* Las columnas a la vista: las pedidas (al menos 10), nunca mas de las que hay ni de las que caben. */
function verEfectivo(n, pedido, cabenX) {
  return Math.max(1, Math.min(n, cabenX, Math.max(10, Math.round(pedido))));
}

/* Los niveles a la vista: todos [lo, hi] si caben; si no, `cy` alrededor del nivel kb, dentro de [lo, hi]. */
function bandaDe(lo, hi, cy, kb) {
  if (hi - lo + 1 <= cy) return [lo, hi];
  const a = Math.min(hi - cy + 1, Math.max(lo, kb - Math.floor(cy / 2)));
  return [a, a + cy - 1];
}

/* La columna «ahora»: la ultima de la ventana, si esta a la vista, tiene foto y no es vieja (en vivo: mas de dos
 * `cada` y 5 s). -> [indice, null] o [null, motivo]. */
function columnaAhora(m, j1, ahoraMs) {
  const n = m.columnas.length;
  const c = m.columnas[n - 1];
  if (j1 !== n - 1) return [null, 'la columna más nueva no está a la vista'];
  if (c.estado !== 'foto' || !c.suma) return [null, 'la última columna es ' + (c.estado === 'hueco' ? 'un HUECO' : c.estado === 'pendiente' ? 'sin escribir aún' : 'sin libro')];
  if (!m.fijo && ahoraMs !== null && ahoraMs - c.ts > 2 * m.cada * 1000 + 5000) return [null, 'la última columna es vieja'];
  return [n - 1, null];
}

function creaMapa(canvas, alLeer, aviso, alEscala) {
  const L = { cv: canvas, ctx: canvas.getContext('2d'), pr: window.devicePixelRatio || 1, W: 0, H: 0, modelo: null,
              fin: 0, ver: 0, pedido: 0, sigue: true, pendiente: false, cuadros: 0, arrastre: null, bmp: null,
              esc: null, escClave: null, escT: -Infinity, escN: 0, escTimer: null, clave: null, aviso, alEscala,
              pc: MAPA_PERCENTILES.slice() };

  function mide() {
    const r = L.cv.parentElement.getBoundingClientRect();
    L.W = Math.max(200 + MAPA.DERECHA, Math.floor(r.width));
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

  /* El color de la celda (columna j, nivel k) y lo que el contrato dice de ella. */
  function celda(m, j, k, esc) {
    const col = m.columnas[j];
    const s = col.suma;
    if (col.estado === 'hueco') return [colorHueco(j, k), null];
    if (col.estado !== 'foto') return [MAPA_COLOR[col.estado], null];
    if (!s || k < s.lo || k > s.hi || !s.n[k - s.lo]) return [MAPA_COLOR.desconocido, null];
    const i = k - s.lo;
    const ix = esc.indice(enUnidad(s.c[i] + s.v[i], k, m.paso, m.unidad));
    const lado = ladoDe(s.c[i], s.v[i]);
    return [ix < 0 ? MAPA_COLOR.fondo : (lado ? MAPA_LUT_VENTA : MAPA_LUT_COMPRA)[ix],
            [k, s.c[i], s.v[i], s.n[i], ix, lado ? 'v' : 'c', s.h ? s.h[i] : 0]];
  }

  /* El mapa de bits de las columnas [j0, j1] y las filas [kLo, kHi] (k alto arriba), con la escala `esc`. */
  function mapaDeBits(m, j0, j1, kLo, kHi, esc) {
    const w = 2 * (j1 - j0 + 1);
    const h = 2 * (kHi - kLo + 1);
    const img = new ImageData(w, h);
    const px = img.data;
    for (let j = j0; j <= j1; j++) {
      const x0 = 2 * (j - j0);
      for (let k = kHi; k >= kLo; k--) {
        const c = celda(m, j, k, esc)[0];
        const y0 = 2 * (kHi - k);
        for (let q = 0; q < 4; q++) {
          const o = ((y0 + (q >> 1)) * w + x0 + (q & 1)) * 4;
          px[o] = c[0];
          px[o + 1] = c[1];
          px[o + 2] = c[2];
          px[o + 3] = 255;
        }
      }
    }
    const cv = document.createElement('canvas');
    cv.width = w;
    cv.height = h;
    cv.getContext('2d').putImageData(img, 0, 0);
    return cv;
  }

  /* Lo negociado de las velas del footprint que tocan [tA, tB): por nivel (al paso de la vista) y por minuto. */
  function negociado(m, tA, tB) {
    const h = m.huella;
    if (!h || !h.velas) return null;
    const P = Number(m.paso);
    const niveles = new Map();
    const velas = [];
    h.velas.forEach((x) => {
      const t = Date.parse(x.ts);
      if (t + 60000 <= tA || t >= tB) return;
      velas.push([t, Number(x.compra), Number(x.venta)]);
      (x.niveles || []).forEach((y) => {
        const k = Math.round(Number(y.nivel) / P);
        const z = niveles.get(k) || [0, 0];
        z[0] += Number(y.compra);
        z[1] += Number(y.venta);
        niveles.set(k, z);
      });
    });
    return { niveles, velas };
  }

  /* ------------------------------------------------------------ pintar */
  function pinta(forzar) {
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
      if (L.aviso) L.aviso.textContent = '';
      return;
    }
    const ancho = L.W - MAPA.DERECHA;
    const alto = L.H - MAPA.ABAJO;
    const n = m.columnas.length;
    const [cx, cy] = cabenEn(L.W, L.H, L.pr);
    const j0 = Math.max(0, Math.floor(L.fin - L.ver + 1));
    const j1 = Math.min(n - 1, Math.ceil(L.fin));
    // lo visible en vertical: lo que conocen (vivo y capa honda) las columnas que se ven, con dos filas de margen; si
    // no cabe, la banda de la mejor compra de la columna mas nueva a la vista que tiene libro
    let lo = Infinity;
    let hi = -Infinity;
    let kb = null;
    for (let j = j1; j >= j0; j--) {
      const s = m.columnas[j].suma;
      if (s) {
        lo = Math.min(lo, s.lo);
        hi = Math.max(hi, s.hi);
        if (kb === null) kb = Math.floor(Number(s.mejorCompra) / Number(m.paso) + 1e-9);
      }
    }
    if (lo === Infinity) [lo, hi] = r;
    const datos = [lo - 2, hi + 2];
    [lo, hi] = bandaDe(datos[0], datos[1], cy, kb === null ? Math.floor((datos[0] + datos[1]) / 2) : kb);
    const filas = hi - lo + 1;
    // los cortes de color, de lo VISIBLE: como mucho una vez por segundo (al arrastrar), salvo `forzar` (K111)
    const escClave = [j0, j1, lo, hi, L.pc.join(','), m.unidad, m.version || 0, n, m.columnas[0].ts].join('|');
    if (escClave !== L.escClave) {
      const t = performance.now();
      if (forzar || !L.esc || t - L.escT >= 1000) {
        L.esc = escalaCortes(m.columnas, j0, j1, lo, hi, m.paso, m.unidad, L.pc);
        L.esc.columnas = [isoZ(m.columnas[j0].ts), isoZ(m.columnas[j1].ts)];
        L.esc.niveles = [lo, hi];
        L.escClave = escClave;
        L.escT = t;
        L.escN += 1;
        if (L.alEscala) L.alEscala(L.esc, m);
      } else if (!L.escTimer) {
        L.escTimer = setTimeout(() => {
          L.escTimer = null;
          pide();
        }, 1000 - (t - L.escT) + 5);
      }
    }
    const esc = L.esc;
    // el mapa de bits de TODA la ventana (145 P1: B), con los cortes de ahora: se rehace cuando cambian las columnas o
    // los cortes; sus filas, las de la ventana con dos de margen (las que puede pedir lo visible)
    const clave = [n, m.columnas[0].ts, m.columnas[n - 1].ts, r[0], r[1], m.unidad, m.version || 0, L.escN].join('|');
    if (clave !== L.clave) {
      L.bmp = mapaDeBits(m, 0, n - 1, r[0] - 2, r[1] + 2, esc);
      L.clave = clave;
    }
    const bs = ancho / L.ver;
    const fh = alto / filas;
    const xDe = (j) => ancho - (L.fin - j + 1) * bs;
    const yDe = (k) => (hi - k) * fh; // el borde de ARRIBA de la fila k
    const yPrecio = (p) => (hi + 1 - Number(p) / Number(m.paso)) * fh;
    const cadaMs = m.cada * 1000;
    const xT = (t) => xDe(j0) + ((t - m.columnas[j0].ts) / cadaMs) * bs;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, ancho, alto);
    ctx.clip();
    ctx.drawImage(L.bmp, 2 * (L.fin - L.ver + 1), 2 * (r[1] + 2 - hi), 2 * L.ver, 2 * filas, 0, 0, ancho, alto);
    ctx.restore();
    // la banda «ahora»: la ultima columna estirada hasta el borde (si esta a la vista, tiene foto y no es vieja)
    const [ja, porQueNo] = columnaAhora(m, j1, m.ahora ? m.ahora() : null);
    if (ja !== null) {
      ctx.drawImage(L.bmp, 2 * ja, 2 * (r[1] + 2 - hi), 2, 2 * filas, ancho, 0, MAPA.AHORA, alto);
    }
    // el precio: la mejor compra y la mejor venta en escalones de 1 px, sin halo; el ultimo precio en el acento
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, ancho + MAPA.AHORA, alto);
    ctx.clip();
    ctx.lineWidth = 1;
    [['mejorCompra', MAPA_COLOR.compra], ['mejorVenta', MAPA_COLOR.venta]].forEach(([campo, color]) => {
      ctx.beginPath();
      let dentro = false;
      for (let j = j0; j <= j1; j++) {
        const s = m.columnas[j].suma;
        if (!s || m.columnas[j].estado !== 'foto') {
          dentro = false;
          continue;
        }
        const y = Math.round(yPrecio(s[campo])) + 0.5;
        if (dentro) ctx.lineTo(xDe(j), y);
        else ctx.moveTo(xDe(j), y);
        ctx.lineTo(xDe(j) + bs, y);
        dentro = true;
      }
      ctx.strokeStyle = color;
      ctx.stroke();
    });
    const tA = m.columnas[j0].ts;
    const tB = m.columnas[j1].ts + cadaMs;
    const neg = negociado(m, tA, tB);
    let ultimo = null;
    if (m.huella && m.huella.velas && m.huella.velas.length) {
      const v = m.huella.velas[m.huella.velas.length - 1];
      ultimo = { precio: v.cierre, ts: v.ts, y: Math.round(yPrecio(v.cierre)) + 0.5 };
      ctx.beginPath();
      ctx.moveTo(0, ultimo.y);
      ctx.lineTo(ancho + MAPA.AHORA, ultimo.y);
      ctx.strokeStyle = MAPA_COLOR.referencia;
      ctx.stroke();
    }
    ctx.restore();
    // a la derecha: el perfil de lo negociado en lo visible (dos barras por nivel: compra arriba, venta abajo) y el del
    // libro de ahora (una barra por nivel, del color de su lado mayor), con la escala vertical del mapa
    const xVol = ancho + MAPA.AHORA;
    const xPerf = xVol + MAPA.VOLUMEN;
    const barras = (x0, w, filasDe) => {
      let tope = 0;
      filasDe.forEach((f) => {
        tope = Math.max(tope, f[1], f[2]);
      });
      return { tope, largo: (q) => (tope > 0 ? ((w - 4) * q) / tope : 0) };
    };
    const volumen = { desde: isoZ(tA), hasta: isoZ(tB), barras: [], tope: 0,
                      pedido: m.huella ? [m.huella.desde, m.huella.hasta] : null };
    if (neg) {
      const fs = [];
      for (let k = lo; k <= hi; k++) {
        const z = neg.niveles.get(k);
        if (z) fs.push([k, z[0], z[1]]);
      }
      const b = barras(xVol, MAPA.VOLUMEN, fs);
      volumen.tope = b.tope;
      fs.forEach(([k, c, v]) => {
        const y = yDe(k);
        const hm = fh / 2;
        ctx.fillStyle = MAPA_COLOR.compra;
        ctx.fillRect(xVol + 2, y, b.largo(c), hm);
        ctx.fillStyle = MAPA_COLOR.venta;
        ctx.fillRect(xVol + 2, y + hm, b.largo(v), hm);
        volumen.barras.push([k, c, v, b.largo(c), b.largo(v)]);
      });
    }
    const perfil = { ts: ja === null ? null : isoZ(m.columnas[ja].ts), x0: xPerf + 2, barras: [], tope: 0, motivo: porQueNo };
    if (ja !== null) {
      const s = m.columnas[ja].suma;
      const fs = [];
      for (let k = Math.max(lo, s.lo); k <= Math.min(hi, s.hi); k++) {
        const i = k - s.lo;
        if (s.n[i]) fs.push([k, enUnidad(s.c[i] + s.v[i], k, m.paso, m.unidad), 0, ladoDe(s.c[i], s.v[i])]);
      }
      const b = barras(xPerf, MAPA.PERFIL, fs);
      perfil.tope = b.tope;
      fs.forEach(([k, q, , lado]) => {
        ctx.fillStyle = lado ? MAPA_COLOR.venta : MAPA_COLOR.compra;
        ctx.fillRect(xPerf + 2, yDe(k), b.largo(q), fh);
        perfil.barras.push([k, q, lado ? 'v' : 'c', b.largo(q)]);
      });
    }
    // debajo: el volumen por minuto, compra abajo y venta encima, alineado con el tiempo del mapa
    const bajo = { tope: 0, velas: [] };
    if (neg) {
      neg.velas.forEach((x) => {
        bajo.tope = Math.max(bajo.tope, x[1] + x[2]);
      });
      const hb = MAPA.BAJO - 4;
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, alto, ancho, MAPA.BAJO);
      ctx.clip();
      neg.velas.forEach(([t, c, v]) => {
        const x0 = xT(t);
        const x1 = xT(t + 60000);
        const hc = bajo.tope > 0 ? (hb * c) / bajo.tope : 0;
        const hv = bajo.tope > 0 ? (hb * v) / bajo.tope : 0;
        const base = alto + MAPA.BAJO;
        ctx.fillStyle = MAPA_COLOR.compra;
        ctx.fillRect(x0 + 0.5, base - hc, Math.max(1, x1 - x0 - 1), hc);
        ctx.fillStyle = MAPA_COLOR.venta;
        ctx.fillRect(x0 + 0.5, base - hc - hv, Math.max(1, x1 - x0 - 1), hv);
        bajo.velas.push([isoZ(t), c, v, x0, x1]);
      });
      ctx.restore();
    }
    // los ejes: los precios a la derecha del todo; las horas debajo, sin pisar los huecos («sin datos») ni «ahora»
    ctx.fillStyle = MAPA_COLOR.eje;
    ctx.font = '10px ui-monospace, monospace';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    const xEje = xPerf + MAPA.PERFIL + 6;
    const cada = Math.max(1, Math.ceil(28 / fh));
    for (let k = Math.ceil(lo / cada) * cada; k <= hi; k += cada) {
      ctx.fillText(nivelTexto(k, m.paso), xEje, yDe(k) + fh / 2);
    }
    const yT = L.H - MAPA.EJE_T / 2;
    ctx.textAlign = 'center';
    const huecos = [];
    for (let j = j0; j <= j1; j++) {
      if (m.columnas[j].estado !== 'hueco') continue;
      if (huecos.length && huecos[huecos.length - 1][1] === j - 1) huecos[huecos.length - 1][1] = j;
      else huecos.push([j, j]);
    }
    const enHueco = (x) => huecos.some(([a, b]) => x >= xDe(a) - 30 && x <= xDe(b) + bs + 30);
    const ct = Math.max(1, Math.ceil(80 / bs));
    for (let j = Math.ceil(j0 / ct) * ct; j <= j1; j += ct) {
      const x = xDe(j) + bs / 2;
      if (x < 30 || x > ancho - 24 || enHueco(x)) continue;
      ctx.fillText(new Date(m.columnas[j].ts).toISOString().slice(11, 19), x, yT);
    }
    ctx.fillStyle = rgb(MAPA_COLOR.hueco_raya.map((c) => Math.min(255, c * 3)));
    huecos.forEach(([a, b]) => {
      ctx.fillText('sin datos', Math.max(24, Math.min(ancho - 24, (xDe(a) + xDe(b) + bs) / 2)), yT);
    });
    ctx.fillStyle = MAPA_COLOR.eje;
    ctx.fillText(ja === null ? '—' : 'ahora', ancho + MAPA.AHORA / 2, yT);
    // el contrato: lo que ACABA de pintarse
    Object.assign(reg, { escala: { tipo: 'cortes de lo visible', percentiles: esc.percentiles, corte: esc.corte,
                                   celdas: esc.n, columnas: esc.columnas, niveles: esc.niveles },
                         eje: { lo, hi, fila: fh, columna: bs, fin: L.fin, ver: L.ver, ancho, alto, pr: L.pr,
                                caben: [cx, cy], pedido: L.pedido, n, datos },
                         honda: m.honda || null,
                         ahora: { j: ja, ts: ja === null ? null : isoZ(m.columnas[ja].ts), x0: ancho, x1: ancho + MAPA.AHORA,
                                  motivo: porQueNo },
                         perfil, volumen, bajo, ultimo });
    for (let j = j0; j <= j1; j++) {
      const col = m.columnas[j];
      const s = col.suma;
      const x0 = xDe(j);
      const c = { ts: isoZ(col.ts), estado: col.estado, origen: col.origen, x0, x1: x0 + bs,
                  venues: s ? s.venues : [], lo: s ? s.lo : null, hi: s ? s.hi : null,
                  mejor_compra: s ? s.mejorCompra : null, mejor_venta: s ? s.mejorVenta : null,
                  y_compra: s ? Math.round(yPrecio(s.mejorCompra)) + 0.5 : null,
                  y_venta: s ? Math.round(yPrecio(s.mejorVenta)) + 0.5 : null,
                  honda: s && s.honda ? s.honda : [], celdas: [] };
      if (s && col.estado === 'foto') {
        for (let k = Math.max(lo, s.lo); k <= Math.min(hi, s.hi); k++) {
          const d = celda(m, j, k, esc)[1];
          if (d) c.celdas.push(d);
        }
      }
      reg.columnas.push(c);
    }
    window.LIBRO_PINTADO.mapa = reg;
    // lo que se ve del mapa, dicho: cuanto de la ventana y por que no mas; la capa honda; el footprint
    const conocidos = datos[1] - datos[0] + 1;
    if (L.aviso) {
      const hh = (iso) => (iso ? String(iso).slice(11, 16) : '?');
      L.aviso.textContent = 'mapa: ' + L.ver + ' de ' + n + ' columnas y ' + filas + ' de ' + conocidos + ' niveles a la'
        + ' vista (cada celda, al menos 2×2 píxeles de pantalla)'
        + (L.ver < Math.min(n, Math.max(10, Math.round(L.pedido))) ? ' · en este ancho caben ' + cx + ' columnas: no se'
          + ' aleja más; las demás, arrastrando' : '')
        + (filas < conocidos ? ' · en este alto caben ' + cy + ' niveles: los de la mejor compra de la última columna;'
          + ' con un paso mayor caben más' : '')
        + (m.honda ? ' · capa honda: ' + (m.honda.pinta ? m.honda.columnas + ' de ' + n + ' columnas' : m.honda.motivo) : '')
        + (m.huella ? ' · volumen: footprint 1m de ' + hh(m.huella.desde) + ' a ' + hh(m.huella.hasta) + 'Z, a la vista '
          + hh(volumen.desde) + '–' + hh(volumen.hasta) + 'Z' : m.huellaFallo ? ' · volumen: ' + m.huellaFallo : '');
    }
  }

  /* --------------------------------------------------------- lo que se toca */
  function acota() {
    const n = L.modelo ? L.modelo.columnas.length : 0;
    L.ver = verEfectivo(n, L.pedido, cabenEn(L.W, L.H, L.pr)[0]);
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
    if (!col || x > reg.eje.ancho || y > reg.eje.alto) return alLeer(null);
    alLeer(col, Math.floor(reg.eje.hi + 1 - y / reg.eje.fila));
  }

  L.cv.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    L.pedido = L.ver * (ev.deltaY > 0 ? 1.12 : 1 / 1.12);
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
      L.fin = L.arrastre.fin - (ev.clientX - L.arrastre.x) / ((L.W - MAPA.DERECHA) / L.ver);
      acota();
      pide();
    }
    lee(ev);
  });
  new ResizeObserver(() => {
    mide();
    acota();
    pide();
  }).observe(L.cv.parentElement);
  mide();

  return {
    /* el modelo entero (una vista nueva): `ver` columnas pedidas (por omision, todas; a la vista, las que caben), la
     * mas nueva a la derecha */
    pon(modelo, ver) {
      L.modelo = modelo;
      L.clave = null;
      L.escClave = null;
      L.esc = null;
      L.bmp = null;
      const n = modelo ? modelo.columnas.length : 0;
      L.pedido = ver || n;
      L.fin = n - 1;
      acota();
      pide();
    },
    /* columnas nuevas (el vivo), o el footprint que llega: si se miraba el final, se sigue mirando */
    actualiza() {
      if (!L.modelo) return;
      L.modelo.version = (L.modelo.version || 0) + 1;
      if (L.sigue) L.fin = L.modelo.columnas.length - 1;
      acota();
      pide();
    },
    /* el mando de intensidad: los dos percentiles de los cortes */
    percentiles(pc) {
      L.pc = pc.slice();
      L.escClave = null;
      pinta(true);
    },
    pinta,
    pide,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MAPA, MAPA_COLOR, MAPA_LUT_COMPRA, MAPA_LUT_VENTA, lutLado, luminancia, colorHueco, ladoDe,
                     columnaAhora, cabenEn, verEfectivo, bandaDe };
}
