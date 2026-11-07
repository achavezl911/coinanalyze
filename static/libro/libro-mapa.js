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
 * eje, por columna visible sus celdas [k, compra, venta, n, indice, lado, n_honda] (reg.celdas = 'declaradas'; en un
 * gesto quedan 'pendientes' hasta EL_MAPA.declara() o DECLARA_MS despues), y la banda «ahora», el perfil del
 * libro, el del volumen y el volumen de abajo. K111 no se lo cree: lo recalcula de las respuestas y lee los pixeles.
 */

const MAPA = { EJE_P: 76, EJE_T: 20, AHORA: 28, VOLUMEN: 64, PERFIL: 64, BAJO: 40 };
MAPA.DERECHA = MAPA.AHORA + MAPA.VOLUMEN + MAPA.PERFIL + MAPA.EJE_P; // lo que no es mapa, a la derecha
MAPA.ABAJO = MAPA.BAJO + MAPA.EJE_T; // y debajo
MAPA.DECLARA_MS = 250; // las celdas del contrato, tanto despues del ultimo cuadro (fuera del gesto)
MAPA.GESTO_MS = 250; // un gesto (rueda, arrastre) dura hasta tanto despues de su ultimo evento: sin recortes
const MAPA_COLOR = {
  fondo: [10, 13, 18], desconocido: [26, 26, 26], hueco: [34, 29, 22], hueco_raya: [52, 42, 26], pendiente: [30, 36, 46],
  compra: '#60a5fa', venta: '#e05a5a', eje: '#8891a0', // E-02 (OF-6a): los colores propios de cada lado
  referencia: '#f2cc60', // el acento de la casa (--acento de flujo.css): el ultimo precio
  // (149 rC, E-05) la cruz y sus dos etiquetas: los de la cruz de /flujo (flujo-dibujo.js COLOR.cruz)
  cruz: 'rgba(230,233,238,0.55)', cruzFondo: '#2a313c', cruzTexto: '#e6e9ee', presente: 'rgba(230,233,238,0.3)',
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

/* (149 rC, I-02..I-04, H-08/I-07) EL ENCUADRE VERTICAL. V = {modo 'auto'|'manual', recentra 'ultimo'|'bbo'|'ninguno',
 * filas (null = las que caben), ancla (AUTO: el nivel alrededor del que se encuadra), c (MANUAL: el centro), visto (la
 * referencia del cuadro anterior), ya (recentrar ahora en la referencia)}. AUTO sin filas pedidas: todo si cabe; si no,
 * bandaDe alrededor del ancla, que la primera vez es `kb` (la mejor compra de la columna mas nueva a la vista: lo de
 * antes). El ancla salta a la referencia `kRef` (ultimo precio, o el medio de la mejor compra y venta) cuando esta
 * ENTRA en el 20 % de arriba o de abajo; con «ninguno», nunca. MANUAL: `filas` alrededor de `c`. Nunca fuera de lo que
 * guarda el mapa de bits (r con dos de margen). -> [lo, hi] */
function encuadreDe(V, datos, r, cy, kb, kRef) {
  const tope = Math.max(1, Math.min(cy, r[1] - r[0] + 5));
  const span = datos[1] - datos[0] + 1;
  const filas = V.filas ? Math.max(Math.min(8, tope), Math.min(tope, Math.round(V.filas))) : Math.min(cy, span);
  let hi;
  if (V.modo === 'manual') hi = Math.round(V.c + (filas - 1) / 2);
  else if (!V.filas && span <= cy) {
    V.visto = kRef;
    return datos.slice();
  } else if (span <= filas) {
    hi = Math.round((datos[0] + datos[1]) / 2 + (filas - 1) / 2);
    V.visto = kRef;
  } else {
    if (V.ancla === null || V.ancla === undefined) {
      V.ancla = kb;
      V.visto = kRef;
    }
    if (V.ya && kRef !== null) V.ancla = kRef;
    V.ya = false;
    let b = bandaDe(datos[0], datos[1], filas, V.ancla);
    const zona = Math.max(1, Math.floor(filas / 5));
    if (V.recentra !== 'ninguno' && kRef !== null && kRef !== V.visto && (kRef < b[0] + zona || kRef > b[1] - zona)) {
      V.ancla = kRef;
      b = bandaDe(datos[0], datos[1], filas, kRef);
    }
    V.visto = kRef;
    hi = b[1];
  }
  hi = Math.max(r[0] - 2 + filas - 1, Math.min(r[1] + 2, hi));
  return [hi - filas + 1, hi];
}

/* (149 rC, H-08/I-07) los modos de recentrado del menu del eje de precio */
const RECENTRA = { ultimo: 'Último precio', bbo: 'Mejor compra-venta', ninguno: 'Ninguno' };
const RECENTRA_CORTO = { ultimo: 'ÚLTIMO', bbo: 'MEJORES', ninguno: 'NINGUNO' };

/* (149 rC, H-09) LA FICHA de una celda: lo que dice el raton de la columna j y el nivel k, en la ficha y en #lectura
 * con las mismas palabras (las de la leyenda). Nunca un cero por lo que no se sabe: DESCONOCIDO, HUECO o «sin escribir
 * aún». `neg` = lo negociado del minuto de la columna (negociado() del mapa) o null. -> {..., lineas, texto} */
const FICHA_ESTADO = {
  hueco: 'HUECO: ningún venue de la familia tenía libro válido',
  pendiente: 'sin escribir aún',
  desconocido: 'DESCONOCIDO: ningún venue de la familia conoce este nivel en este instante',
};

function fichaDe(m, j, k, neg) {
  const col = m.columnas[j];
  const s = col.suma;
  const ts = isoZ(col.ts);
  const u = (q) => cifra(enUnidad(q, k, m.paso, m.unidad));
  const f = { ts, columna: j, nivel: k, precio: nivelTexto(k, m.paso), estado: col.estado, origen: col.origen,
              unidad: m.unidad, compra: null, venta: null, lado: null, n: null, N: m.N, venues: [], vivo: [], honda: [],
              fuente: null, mejor_compra: s ? s.mejorCompra : null, mejor_venta: s ? s.mejorVenta : null, huella: null,
              lineas: [] };
  f.lineas.push(['cab', ts.slice(5, 19).replace('T', ' ') + 'Z · nivel ' + f.precio
    + (col.origen === 'vivo' ? ' · columna del vivo' : '')]);
  const i = s && k >= s.lo && k <= s.hi ? k - s.lo : null;
  if (col.estado !== 'foto') f.lineas.push(['estado', FICHA_ESTADO[col.estado]]);
  else if (i === null || !s.n[i]) {
    f.estado = 'desconocido';
    f.lineas.push(['estado', FICHA_ESTADO.desconocido]);
  } else {
    f.compra = enUnidad(s.c[i], k, m.paso, m.unidad);
    f.venta = enUnidad(s.v[i], k, m.paso, m.unidad);
    f.lado = ladoDe(s.c[i], s.v[i]) ? 'venta' : 'compra';
    f.n = s.n[i];
    // quien lo conoce: del libro vivo de cada venue (col.libros en el vivo, col.fotos en la historia) y de la capa honda
    const libros = col.libros || (col.fotos || []).map((x) => libroDe(x.venue, x.compra, x.venta, x.compras, x.ventas, m.paso));
    libros.forEach((L) => {
      if (enNivel(L, k)) f.vivo.push(L.venue);
    });
    (s.hondaK || []).forEach(([venue, edad, nv]) => {
      if (nv.has(k)) f.honda.push({ venue, edad_s: edad });
    });
    f.venues = f.vivo.concat(f.honda.map((x) => x.venue));
    const hace = 'capa honda, foto de hace ' + f.honda.map((x) => x.venue + ' ' + Math.round(x.edad_s) + ' s').join(', ');
    f.fuente = !f.honda.length ? 'vivo' : !f.vivo.length ? hace : 'vivo (' + f.vivo.join(', ') + ') y ' + hace;
    f.lineas.push(['compra', 'compra ' + u(s.c[i])], ['venta', 'venta ' + u(s.v[i])],
                  ['venues', 'lo conocen ' + f.n + ' de ' + f.N + ' venues: ' + f.venues.join(', ')
                    + (f.n < f.N ? ' (la suma es de esos)' : '')],
                  ['fuente', f.fuente]);
    if (s.c[i] > 0 && s.v[i] > 0) f.lineas.push(['cruzado', 'compra y venta a la vez (venues cruzados): pinta el lado mayor']);
  }
  if (s) f.lineas.push(['mejor', 'mejor compra ' + s.mejorCompra + ' · mejor venta ' + s.mejorVenta]);
  const min = isoZ(Math.floor(col.ts / 60000) * 60000).slice(11, 16);
  if (neg && neg.velas.length) {
    const z = neg.niveles.get(k) || [0, 0];
    f.huella = { minuto: min, compra: enUnidad(z[0], k, m.paso, m.unidad), venta: enUnidad(z[1], k, m.paso, m.unidad) };
    f.lineas.push(['huella', 'footprint 1m ' + min + 'Z: compra ' + u(z[0]) + ' · venta ' + u(z[1])]);
  } else f.lineas.push(['huella', 'sin footprint']);
  f.texto = f.lineas.map((x) => x[1]).join(' · ');
  return f;
}

/* La columna «ahora»: la ultima de la ventana, si esta a la vista, tiene foto y no es vieja (en vivo: mas de dos
 * `cada` y 5 s). -> [indice, null] o [null, motivo]. */
function columnaAhora(m, j1, ahoraMs) {
  const n = m.columnas.length;
  if (j1 !== n - 1) return [null, 'la columna más nueva no está a la vista'];
  if (!m.fijo && ahoraMs !== null && ahoraMs - m.columnas[n - 1].ts > 2 * m.cada * 1000 + 5000) return [null, 'la última columna es vieja'];
  // (149 B r1) las «sin escribir aún» del final no se estiran ni tapan la banda: se salta a la más nueva CONOCIDA, y se
  // dice cuál (su hora en el rótulo). Si esa es un hueco o no tiene libro, no hay banda.
  let j = n - 1;
  while (j > 0 && m.columnas[j].estado === 'pendiente') j--;
  const c = m.columnas[j];
  if (c.estado !== 'foto' || !c.suma) return [null, 'la última columna conocida es ' + (c.estado === 'hueco' ? 'un HUECO' : c.estado === 'pendiente' ? 'sin escribir aún' : 'sin libro')];
  if (j < n - 1) return [j, 'las ' + (n - 1 - j) + ' últimas están sin escribir aún: es la de ' + isoZ(c.ts)];
  return [n - 1, null];
}

function creaMapa(canvas, alLeer, aviso, alEscala, alVista) {
  const L = { cv: canvas, ctx: canvas.getContext('2d'), pr: window.devicePixelRatio || 1, W: 0, H: 0, modelo: null,
              fin: 0, ver: 0, pedido: 0, sigue: true, pendiente: false, cuadros: 0, arrastre: null, bmp: null,
              esc: null, escClave: null, escT: -Infinity, escN: 0, escTimer: null, gestoT: -Infinity, clave: null, aviso,
              alEscala,
              pc: MAPA_PERCENTILES.slice(), raton: null, finTs: null, finFr: 0,
              V: { modo: 'auto', previo: 'auto', recentra: 'ultimo', filas: null, ancla: null, c: null, visto: null,
                   ya: false } };
  // (149 rC, E-05) la cruz va en SU capa, encima del mapa y sin raton: moverla no repinta el mapa de bits
  L.capa = document.createElement('canvas');
  L.capa.className = 'cruz';
  L.capa.setAttribute('aria-hidden', 'true');
  canvas.parentElement.appendChild(L.capa);

  function mide() {
    const r = L.cv.parentElement.getBoundingClientRect();
    L.W = Math.max(200 + MAPA.DERECHA, Math.floor(r.width));
    L.H = Math.max(200, Math.floor(r.height));
    L.cv.width = L.W * L.pr;
    L.cv.height = L.H * L.pr;
    L.cv.style.width = L.W + 'px';
    L.cv.style.height = L.H + 'px';
    L.capa.width = L.W * L.pr;
    L.capa.height = L.H * L.pr;
    L.capa.style.width = L.W + 'px';
    L.capa.style.height = L.H + 'px';
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
  function celda(m, j, k, esc, soloColor) {
    const col = m.columnas[j];
    const s = col.suma;
    if (col.estado === 'hueco') return soloColor ? colorHueco(j, k) : [colorHueco(j, k), null];
    if (col.estado !== 'foto') return soloColor ? MAPA_COLOR[col.estado] : [MAPA_COLOR[col.estado], null];
    if (!s || k < s.lo || k > s.hi || !s.n[k - s.lo]) return soloColor ? MAPA_COLOR.desconocido : [MAPA_COLOR.desconocido, null];
    const i = k - s.lo;
    const ix = esc.indice(enUnidad(s.c[i] + s.v[i], k, m.paso, m.unidad));
    const lado = ladoDe(s.c[i], s.v[i]);
    const color = ix < 0 ? MAPA_COLOR.fondo : (lado ? MAPA_LUT_VENTA : MAPA_LUT_COMPRA)[ix];
    return soloColor ? color : [color, [k, s.c[i], s.v[i], s.n[i], ix, lado ? 'v' : 'c', s.h ? s.h[i] : 0]];
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
        const c = celda(m, j, k, esc, true);
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
    // (149 B r1, P4) la respuesta se lee UNA vez por huella y paso, no en cada cuadro del gesto
    if (L.huellaDe !== h || L.huellaPaso !== m.paso) {
      const P = Number(m.paso);
      L.huellaDe = h;
      L.huellaPaso = m.paso;
      L.huellaLeida = h.velas.map((x) => {
        const t = Date.parse(x.ts);
        return [t, Number(x.compra), Number(x.venta), isoZ(t),
                (x.niveles || []).map((y) => [Math.round(Number(y.nivel) / P), Number(y.compra), Number(y.venta)])];
      });
    }
    const niveles = new Map();
    const velas = [];
    L.huellaLeida.forEach(([t, c, v, iso, nv]) => {
      if (t + 60000 <= tA || t >= tB) return;
      velas.push([t, c, v, iso]);
      nv.forEach(([k, yc, yv]) => {
        const z = niveles.get(k) || [0, 0];
        z[0] += yc;
        z[1] += yv;
        niveles.set(k, z);
      });
    });
    return { niveles, velas };
  }

  /* (149 rC, I-07) el precio al que se recentra: el cierre de la ultima vela del footprint que empieza antes del final de
   * la columna mas nueva a la vista (sin footprint, la mejor compra), o el medio de la mejor compra y la mejor venta */
  function referencia(m, j0, j1, kb) {
    const P = Number(m.paso);
    if (L.V.recentra === 'bbo') {
      for (let j = j1; j >= j0; j--) {
        const s = m.columnas[j].suma;
        if (s && s.mejorCompra !== null && s.mejorVenta !== null) {
          return Math.floor((Number(s.mejorCompra) + Number(s.mejorVenta)) / 2 / P + 1e-9);
        }
      }
      return kb;
    }
    const v = m.huella && m.huella.velas;
    const tB = m.columnas[j1].ts + m.cada * 1000;
    for (let i = (v ? v.length : 0) - 1; i >= 0; i--) {
      if (Date.parse(v[i].ts) < tB) return Math.floor(Number(v[i].cierre) / P + 1e-9);
    }
    return kb;
  }

  /* ------------------------------------------------------------ la cruz (E-05) y la ficha (H-09)
   * 1 px sobre el mapa por el centro de la celda bajo el raton; la horizontal sigue por «ahora» y los dos perfiles; el
   * precio de la fila (al paso) en su eje, la hora de la columna (HH:MM:SS) en el suyo. La geometria es la del ULTIMO
   * cuadro (su contrato): lo que dice la cruz es lo que se ve. Fuera de las celdas no hay cruz ni ficha. */
  function cruz() {
    const c = L.capa.getContext('2d');
    c.setTransform(L.pr, 0, 0, L.pr, 0, 0);
    c.clearRect(0, 0, L.W, L.H);
    const reg = window.LIBRO_PINTADO.mapa;
    const m = L.modelo;
    const e = reg && reg.eje;
    let j = null;
    let k = null;
    if (L.raton && m && e) {
      const { x, y } = L.raton;
      if (x >= 0 && x < e.ancho && y >= 0 && y < e.alto) {
        j = Math.floor(e.fin + 1 - (e.ancho - x) / e.columna);
        k = Math.floor(e.hi + 1 - y / e.fila);
        if (j < 0 || j >= m.columnas.length) j = null;
      }
    }
    if (j === null) {
      window.LIBRO_CRUZ = null;
      alLeer(null);
      return;
    }
    const xc = Math.round(e.ancho - (e.fin - j + 0.5) * e.columna) + 0.5;
    const yc = Math.round((e.hi - k + 0.5) * e.fila) + 0.5;
    const xP = L.W - MAPA.EJE_P;
    c.lineWidth = 1;
    c.strokeStyle = MAPA_COLOR.cruz;
    c.setLineDash([3, 3]);
    c.beginPath();
    c.moveTo(0, yc);
    c.lineTo(xP, yc);
    c.moveTo(xc, 0);
    c.lineTo(xc, e.alto + MAPA.BAJO);
    c.stroke();
    c.setLineDash([]);
    const precio = nivelTexto(k, m.paso);
    const hora = isoZ(m.columnas[j].ts).slice(11, 19);
    c.font = '10px ui-monospace, monospace';
    c.textBaseline = 'middle';
    c.fillStyle = MAPA_COLOR.cruzFondo;
    c.fillRect(xP, yc - 7.5, MAPA.EJE_P, 15);
    c.fillStyle = MAPA_COLOR.cruzTexto;
    c.textAlign = 'left';
    c.fillText(precio, xP + 6, yc);
    const wT = Math.ceil(c.measureText(hora).width) + 10;
    const xT = Math.max(0, Math.min(e.ancho - wT, xc - wT / 2));
    c.fillStyle = MAPA_COLOR.cruzFondo;
    c.fillRect(xT, L.H - MAPA.EJE_T, wT, MAPA.EJE_T);
    c.fillStyle = MAPA_COLOR.cruzTexto;
    c.textAlign = 'center';
    c.fillText(hora, xT + wT / 2, L.H - MAPA.EJE_T / 2);
    // la ficha: la celda, y lo negociado en su nivel en el minuto de la columna (footprint 1m)
    const t0 = Math.floor(m.columnas[j].ts / 60000) * 60000;
    const f = fichaDe(m, j, k, negociado(m, t0, t0 + 60000));
    window.LIBRO_CRUZ = { x: L.raton.x, y: L.raton.y, precio, nivel: k, columna: j, ts: f.ts, cuadro: reg.cuadro,
                          ejes: { precio, hora, x: xc, y: yc, x_precio: xP, y_hora: L.H - MAPA.EJE_T / 2 }, ficha: f };
    alLeer(f, L.raton);
  }

  /* ------------------------------------------------------------ pintar */
  function pinta(forzar) {
    pintaMapa(forzar);
    if (L.raton) cruz();
    // (149 rC) la pagina pinta lo suyo de la vista: «PRESENTE» encendido o parado
    if (alVista) alVista({ sigue: L.sigue, modo: L.V.modo, recentra: L.V.recentra });
  }

  function pintaMapa(forzar) {
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
    if (kb === null) kb = Math.floor((datos[0] + datos[1]) / 2);
    // (149 rC) el encuadre: el de siempre hasta que el raton o el recentrado lo mueven (encuadreDe)
    const kRef = referencia(m, j0, j1, kb);
    [lo, hi] = encuadreDe(L.V, datos, r, cy, kb, kRef);
    const filas = hi - lo + 1;
    // los cortes de color, de lo VISIBLE: como mucho una vez por segundo, salvo `forzar` (K111). (149 B r1, P4) Durante
    // un gesto (rueda o arrastre hace menos de GESTO_MS) no se rehacen: rehacerlos tira el mapa de bits de toda la
    // ventana y ese cuadro pasaba de 50 ms con datos de produccion; se rehacen al quedarse quieto
    const escClave = [j0, j1, lo, hi, L.pc.join(','), m.unidad, m.version || 0, n, m.columnas[0].ts].join('|');
    if (escClave !== L.escClave) {
      const t = performance.now();
      const enGesto = t - L.gestoT < MAPA.GESTO_MS;
      if (forzar || !L.esc || (!enGesto && t - L.escT >= 1000)) {
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
        }, Math.max(enGesto ? MAPA.GESTO_MS - (t - L.gestoT) : 0, 1000 - (t - L.escT)) + 5);
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
    // la banda «ahora»: la ultima columna CONOCIDA estirada hasta el borde (si esta a la vista, tiene foto y no es vieja)
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
    // (149 rC, H-10) sin seguir el presente, una vertical tenue en el instante actual: el borde derecho de la columna
    // mas nueva (si cae en el mapa o en la banda «ahora»; mas a la derecha no se ve)
    let presente = null;
    if (!L.sigue) {
      const x = Math.round(xDe(n - 1) + bs) + 0.5;
      presente = { ts: isoZ(m.columnas[n - 1].ts + cadaMs), x, visible: x <= ancho + MAPA.AHORA };
      if (presente.visible) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, alto + MAPA.BAJO);
        ctx.strokeStyle = MAPA_COLOR.presente;
        ctx.stroke();
      }
    }
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
      neg.velas.forEach(([t, c, v, iso]) => {
        const x0 = xT(t);
        const x1 = xT(t + 60000);
        const hc = bajo.tope > 0 ? (hb * c) / bajo.tope : 0;
        const hv = bajo.tope > 0 ? (hb * v) / bajo.tope : 0;
        const base = alto + MAPA.BAJO;
        ctx.fillStyle = MAPA_COLOR.compra;
        ctx.fillRect(x0 + 0.5, base - hc, Math.max(1, x1 - x0 - 1), hc);
        ctx.fillStyle = MAPA_COLOR.venta;
        ctx.fillRect(x0 + 0.5, base - hc - hv, Math.max(1, x1 - x0 - 1), hv);
        bajo.velas.push([iso, c, v, x0, x1]);
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
    // (149 rC, I-03) bajo el eje de precio, como esta su escala: AUTO y a que recentra, o MANUAL
    const modoTexto = L.V.modo === 'manual' ? 'MANUAL' : 'AUTO·' + RECENTRA_CORTO[L.V.recentra];
    ctx.font = 'bold 9px ui-monospace, monospace';
    ctx.fillStyle = L.V.modo === 'manual' ? MAPA_COLOR.referencia : MAPA_COLOR.eje;
    ctx.fillText(modoTexto, xEje, alto + 10);
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillStyle = MAPA_COLOR.eje;
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
    if (ja !== null && ja < n - 1) {
      ctx.textAlign = 'left';
      ctx.fillText(new Date(m.columnas[ja].ts).toISOString().slice(11, 19), ancho + 2, yT);
    } else ctx.fillText(ja === null ? '—' : 'ahora', ancho + MAPA.AHORA / 2, yT);
    // el contrato: lo que ACABA de pintarse
    Object.assign(reg, { escala: { tipo: 'cortes de lo visible', percentiles: esc.percentiles, corte: esc.corte,
                                   celdas: esc.n, columnas: esc.columnas, niveles: esc.niveles },
                         eje: { lo, hi, fila: fh, columna: bs, fin: L.fin, ver: L.ver, ancho, alto, pr: L.pr,
                                caben: [cx, cy], pedido: L.pedido, n, datos, sigue: L.sigue,
                                vertical: { modo: L.V.modo, recentra: L.V.recentra, texto: modoTexto, filas: L.V.filas,
                                            ancla: L.V.ancla, centro: L.V.c, ref: kRef } },
                         presente,
                         honda: m.honda || null,
                         ahora: { j: ja, ts: ja === null ? null : isoZ(m.columnas[ja].ts), x0: ancho, x1: ancho + MAPA.AHORA,
                                  motivo: porQueNo },
                         perfil, volumen, bajo, ultimo });
    const porDeclarar = [];
    for (let j = j0; j <= j1; j++) {
      const col = m.columnas[j];
      const s = col.suma;
      const x0 = xDe(j);
      if (!col.tsIso) col.tsIso = isoZ(col.ts);
      const c = { ts: col.tsIso, estado: col.estado, origen: col.origen, x0, x1: x0 + bs,
                  venues: s ? s.venues : [], lo: s ? s.lo : null, hi: s ? s.hi : null,
                  mejor_compra: s ? s.mejorCompra : null, mejor_venta: s ? s.mejorVenta : null,
                  y_compra: s ? Math.round(yPrecio(s.mejorCompra)) + 0.5 : null,
                  y_venta: s ? Math.round(yPrecio(s.mejorVenta)) + 0.5 : null,
                  honda: s && s.honda ? s.honda : [], alcance: alcanceColumna(col, m.paso), celdas: [] };
      if (s && col.estado === 'foto') porDeclarar.push([c, j, Math.max(lo, s.lo), Math.min(hi, s.hi)]);
      reg.columnas.push(c);
    }
    window.LIBRO_PINTADO.mapa = reg;
    // (149 B r1, P4) las celdas del contrato NO se declaran en cada cuadro: son cada celda conocida a la vista (BTC perp
    // 1 h con la capa honda, ~69 k arrays) y eran el coste del gesto (celda + recolector, perfil de CDP), no el mapa de
    // bits. Se declaran con `forzar`, cuando se pide el contrato (declara(), lo llama K111 al leer) o DECLARA_MS despues
    // del ultimo cuadro; hasta entonces reg.celdas = 'pendientes'.
    reg.celdas = 'pendientes';
    L.declara = () => {
      L.declara = null;
      if (L.declTimer) clearTimeout(L.declTimer);
      L.declTimer = null;
      porDeclarar.forEach(([c, j, a, b]) => {
        for (let k = a; k <= b; k++) {
          const d = celda(m, j, k, esc)[1];
          if (d) c.celdas.push(d);
        }
      });
      reg.celdas = 'declaradas';
    };
    if (L.declTimer) clearTimeout(L.declTimer);
    L.declTimer = null;
    if (forzar) L.declara();
    else L.declTimer = setTimeout(() => L.declara && L.declara(), MAPA.DECLARA_MS);
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
    if (L.sigue) L.fin = n - 1;
    recuerda();
  }

  /* (149 rC, I-05) sin seguir, la vista se sujeta a la columna de su borde derecho POR SU INSTANTE: el vivo anade por la
   * derecha y quita por la izquierda, y lo que se mira no se mueve */
  function recuerda() {
    const m = L.modelo;
    if (!m || !m.columnas.length) return;
    const i = Math.max(0, Math.floor(L.fin));
    L.finTs = m.columnas[i].ts;
    L.finFr = L.fin - i;
  }

  /* tras un gesto horizontal: si se fue atras, deja de seguir (solo Fin y «PRESENTE» lo vuelven a encender) */
  function horizontal(fin) {
    const n = L.modelo ? L.modelo.columnas.length : 0;
    if (!n) return;
    L.fin = Math.min(n - 1, Math.max(Math.min(n - 1, L.ver - 1), fin));
    if (L.fin < n - 1 - 1e-6) L.sigue = false;
    gesto();
  }

  function gesto() {
    L.gestoT = performance.now();
    acota();
    pide();
  }

  /* I-01: el zoom horizontal, con la columna bajo `x` quieta (en el borde de lo cargado, el tope manda) */
  function zoomX(f, x) {
    const n = L.modelo ? L.modelo.columnas.length : 0;
    if (!n) return;
    const ancho = L.W - MAPA.DERECHA;
    const xa = Math.max(0, Math.min(ancho, x));
    const ja = L.fin + 1 - ((ancho - xa) * L.ver) / ancho;
    L.pedido = L.ver * f;
    L.ver = verEfectivo(n, L.pedido, cabenEn(L.W, L.H, L.pr)[0]);
    horizontal(ja - 1 + ((ancho - xa) * L.ver) / ancho);
  }

  function eje() {
    const reg = window.LIBRO_PINTADO.mapa;
    return reg && reg.eje ? reg.eje : null;
  }

  function aManual(c, filas) {
    if (L.V.modo !== 'manual') L.V.previo = L.V.modo;
    Object.assign(L.V, { modo: 'manual', c, filas });
  }

  /* I-01 (Ctrl + rueda): el zoom vertical con el precio bajo el cursor quieto; la escala pasa a MANUAL */
  function zoomY(f, y) {
    const e = eje();
    if (!e) return;
    const filas = e.hi - e.lo + 1;
    let nf = Math.max(8, Math.round(filas * f));
    if (nf === filas && filas > 8) nf += f > 1 ? 1 : -1;
    const kc = e.hi + 1 - y / e.fila;
    aManual(kc - 1 + (y * nf) / e.alto - (nf - 1) / 2, nf);
    gesto();
  }

  /* I-02: la escala vertical desde su eje, con el centro quieto y el modo como estaba */
  function escalaY(filas0, c, nf) {
    nf = Math.max(8, Math.round(nf));
    if (nf === filas0) return;
    if (L.V.modo === 'manual') L.V.c = c;
    else L.V.ancla = Math.round(c);
    L.V.filas = nf;
    gesto();
  }

  /* I-04: doble clic en el eje de precio: recentra y vuelve al modo de antes */
  function recentraYa() {
    Object.assign(L.V, { modo: L.V.previo === 'manual' ? 'auto' : L.V.previo, filas: null, ancla: null, c: null,
                         ya: L.V.recentra !== 'ninguno' });
    gesto();
  }

  /* donde cae un punto del lienzo: el eje de precio, el de tiempo o el mapa (con sus perfiles) */
  function zonaDe(x, y) {
    if (x >= L.W - MAPA.EJE_P && y < L.H - MAPA.ABAJO) return 'precio';
    if (y >= L.H - MAPA.EJE_T && x < L.W - MAPA.DERECHA) return 'tiempo';
    return 'mapa';
  }

  function posDe(ev) {
    const r = L.cv.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top };
  }

  function ponRaton(ev) {
    L.raton = posDe(ev);
    cruz();
  }

  L.cv.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    const d = ev.deltaY || ev.deltaX;
    if (!L.modelo || !d) return;
    const { x, y } = posDe(ev);
    const z = zonaDe(x, y);
    const f = d > 0 ? 1.12 : 1 / 1.12;
    const e = eje();
    if (z === 'precio' && e) escalaY(e.hi - e.lo + 1, (e.lo + e.hi) / 2, (e.hi - e.lo + 1) * f);
    else if (ev.ctrlKey && z === 'mapa') zoomY(f, y);
    else if (ev.shiftKey && z === 'mapa') horizontal(L.fin + Math.sign(d) * Math.max(1, Math.round(L.ver / 10)));
    else zoomX(f, x);
    ponRaton(ev);
  }, { passive: false });
  L.cv.addEventListener('mousedown', (ev) => {
    if (ev.button !== 0 || !L.modelo) return;
    const p = posDe(ev);
    const e = eje();
    L.arrastre = { x: ev.clientX, y: ev.clientY, fin: L.fin, ver: L.ver, zona: zonaDe(p.x, p.y), h: false, v: false,
                   filas: e ? e.hi - e.lo + 1 : null, c: e ? (e.lo + e.hi) / 2 : null, fila: e ? e.fila : 1 };
  });
  window.addEventListener('mouseup', () => {
    L.arrastre = null;
  });
  L.cv.addEventListener('mousemove', (ev) => {
    const a = L.arrastre;
    if (a && L.modelo) {
      const dx = ev.clientX - a.x;
      const dy = ev.clientY - a.y;
      if (a.zona === 'precio' && a.filas) escalaY(L.V.filas || a.filas, a.c, a.filas * Math.exp(dy / 150));
      else if (a.zona === 'tiempo') {
        L.pedido = a.ver * Math.exp(-dx / 150);
        L.ver = verEfectivo(L.modelo.columnas.length, L.pedido, cabenEn(L.W, L.H, L.pr)[0]);
        horizontal(a.fin);
      } else {
        // I-03: el mapa se arrastra en los dos ejes; en vertical, la escala pasa a MANUAL
        a.h = a.h || Math.abs(dx) > 3;
        a.v = a.v || (Math.abs(dy) > 3 && a.filas !== null);
        if (a.v) aManual(a.c + dy / a.fila, a.filas);
        if (a.h) horizontal(a.fin - (dx * L.ver) / (L.W - MAPA.DERECHA));
        else if (a.v) gesto();
      }
    }
    ponRaton(ev);
  });
  L.cv.addEventListener('mouseleave', () => {
    L.raton = null;
    cruz();
  });
  L.cv.addEventListener('dblclick', (ev) => {
    const p = posDe(ev);
    if (zonaDe(p.x, p.y) === 'precio') recentraYa();
  });
  // I-06: con el foco en el mapa, las flechas una columna, Re Pag / Av Pag una pantalla, Inicio lo primero cargado, Fin
  // el presente (y seguirlo). La C es de la escalera; Esc, de quien tenga un menu abierto.
  L.cv.addEventListener('keydown', (ev) => {
    if (ev.ctrlKey || ev.altKey || ev.metaKey || !L.modelo) return;
    const accion = { ArrowLeft: () => horizontal(L.fin - 1), ArrowRight: () => horizontal(L.fin + 1),
                     PageUp: () => horizontal(L.fin - L.ver), PageDown: () => horizontal(L.fin + L.ver),
                     Home: () => horizontal(L.ver - 1), End: () => presente() }[ev.key];
    if (!accion) return;
    ev.preventDefault();
    accion();
  });

  /* I-05: ir al presente y seguirlo */
  function presente() {
    L.sigue = true;
    gesto();
  }
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
      L.sigue = true;
      Object.assign(L.V, { modo: 'auto', previo: 'auto', filas: null, ancla: null, c: null, visto: null, ya: false });
      acota();
      pide();
    },
    /* columnas nuevas (el vivo), o el footprint que llega: siguiendo, el presente; si no, la vista no se mueve */
    actualiza() {
      if (!L.modelo) return;
      L.modelo.version = (L.modelo.version || 0) + 1;
      const cs = L.modelo.columnas;
      if (L.sigue) L.fin = cs.length - 1;
      else if (L.finTs !== null) {
        let i = cs.length - 1;
        while (i >= 0 && cs[i].ts > L.finTs) i--;
        L.fin = i + L.finFr;
      }
      acota();
      pide();
    },
    /* (149 rC) lo que pide la pagina: ir al presente (I-05), el modo de recentrado del menu (H-08/I-07, recentra ya),
     * donde cae un punto del lienzo y como esta la vista */
    presente,
    recentra(modo, ahora) {
      if (!RECENTRA[modo]) return;
      const e = eje();
      if (ahora && e) {
        Object.assign(L.V, { modo: 'auto', previo: 'auto', filas: L.V.filas ? e.hi - e.lo + 1 : null, c: null,
                             ancla: Math.round((e.lo + e.hi) / 2), ya: modo !== 'ninguno' });
      }
      L.V.recentra = modo;
      if (ahora) gesto();
    },
    zonaDe,
    estado: () => ({ sigue: L.sigue, fin: L.fin, ver: L.ver, vertical: Object.assign({}, L.V) }),
    /* el mando de intensidad: los dos percentiles de los cortes */
    percentiles(pc) {
      L.pc = pc.slice();
      L.escClave = null;
      pinta(true);
    },
    /* el contrato entero ya: declara las celdas del ultimo cuadro si estaban pendientes */
    declara() {
      if (L.declara) L.declara();
    },
    pinta,
    pide,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MAPA, MAPA_COLOR, MAPA_LUT_COMPRA, MAPA_LUT_VENTA, lutLado, luminancia, colorHueco, ladoDe,
                     columnaAhora, cabenEn, verEfectivo, bandaDe, encuadreDe, fichaDe, FICHA_ESTADO, RECENTRA };
}
