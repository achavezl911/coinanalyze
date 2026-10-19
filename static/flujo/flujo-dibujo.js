'use strict';
/* EL FOOTPRINT · el lienzo (campana 142, OF-2; los dos ejes, el aspecto y el raton: campana 148, OF-6a).
 * ---------------------------------------------------------------------------
 * LIENZO PROPIO, NO LIGHTWEIGHT-CHARTS. Lo decidio P1 con el criterio archivado ANTES de medir
 * (entregas/20261017-1207-footprint-prediccion.md): en Chromium sin cabeza en 143, con 120 velas del maximo de niveles
 * medido, la serie propia de lightweight-charts 5.2.0 dio un p95 de 50.0 ms por fotograma al desplazar y 49.9 al hacer
 * zoom; este lienzo, 33.4 y 33.4 (x1-tmp/c142/banco-p1, tres repeticiones). El criterio era <= 33.4.
 *
 * LOS DOS EJES (OF-6a). Horizontal: `ver` velas a la vista y `fin`, la vela del borde derecho; sin `ver` en el hash,
 * las que caben con LZ.ESPACIADO px por vela. Vertical: `fila` px por nivel y `centro`, el precio de la mitad del
 * grafico, en AUTO (sigue a la ultima vela a la vista: se recentra cuando se acerca al borde) o MANUAL (lo que dejo el
 * raton). Los gestos son las convenciones compartidas de la investigacion (entregas/20261018-2130-INVESTIGACION-
 * plataformas.md, I-01 a I-08): la rueda acerca el tiempo anclada al cursor, Mayus+rueda lo desplaza y Ctrl+rueda
 * acerca el precio; rueda o arrastre sobre un EJE escalan ese eje; arrastrar el grafico mueve los dos (y el precio
 * pasa a MANUAL, dicho en la esquina del eje); doble clic en el eje de precio vuelve a AUTO; Ctrl+arrastre mide. Mayus +
 * arrastre sigue marcando el perfil fijo (flujo-app.js).
 *
 * NIVEL DE DETALLE (F-09): una cifra se escribe si la fila mide >= LZ.FILA_TEXTO px y cabe en su sitio con 4 px de
 * holgura (la semicelda en bid x ask, la celda en los demas modos); la fuente va de 9 a 13 px con el alto de fila. Las
 * marcas (POC, value area, desequilibrios, cobertura) se pintan siempre.
 *
 * EL CONTRATO DE LO PINTADO, que leen K109, K112 y K113: cada vez que pinta, el lienzo deja en `window.FLUJO_PINTADO` lo
 * que ACABA de dibujar, apuntado en el mismo sitio donde se dibuja: por vela visible su estado y su marca, el POC (y los
 * empatados) y la value area con sus pixeles, el contorno, el resumen, y por nivel su rectangulo, el TEXTO que se le paso
 * a fillText (null si no cupo), el color y su paso, el filtro y los desequilibrios; y la escala de los dos ejes. La cruz,
 * la ficha y la regla se apuntan en `FLUJO_CRUZ`, `FLUJO_FICHA` y `FLUJO_REGLA`. Lo que no se pinta no se apunta.
 */

const LZ = {
  EJE_P: 76, // eje de precios, a la derecha
  EJE_T: 20, // eje de tiempo, abajo
  CABEZA: 16, // la marca de cobertura de cada vela, arriba
  FILA_RES: 16, // F-10: cada fila de resumen
  FILA_TEXTO: 10, // F-09: con filas mas bajas no se escribe ninguna cifra
  // P2 de la campana 148 (velas reales de 140, x1-tmp/c148/p2_mide.py): con la escala que ajusta lo visible la fila
  // de 5m, 15m y 1h queda por debajo de 10 px casi siempre; la vista por omision es una fila FIJA centrada en la ultima
  // vela, y el espaciado el que deja leer la p90 de las cifras de BTC 1m con la fuente de esa fila
  FILA_DEFECTO: 12,
  ESPACIADO: 81,
  VER_MIN: 5,
  // P1 de la 148 (criterio archivado: p95 <= 33.4 ms en cada gesto con los paneles; x1-tmp/c148/p1.jsonl): con 40 y
  // 120 velas aguanta (33.4 en el borde), con 400 no (p95 de 50 a 66.7 ms en los cinco gestos): el tope es 120
  VER_TOPE: 120,
};
const COLOR = {
  fondo: '#0a0d12', rejilla: 'rgba(255,255,255,0.05)', eje: '#8891a0', texto: '#e6e9ee', mudo: '#5b6472',
  // E-02: el comprador es AZUL (el verde de antes no pasa la deuteranopia: P2 de la 148), el vendedor rojo
  compra: [96, 165, 250], venta: [224, 90, 90], neutro: [136, 145, 160], volumen: [200, 206, 216], poc: '#f2cc60',
  va: '#c8ced8', ambar: '#e6b75a', fuerte_compra: '#93c5fd', fuerte_venta: '#ff8f8f', grande: '#ffffff',
  contorno: 'rgba(200,206,216,0.35)', cruz: 'rgba(230,233,238,0.55)', etiqueta: '#2a313c',
};
const ALFA_MIN = 0.1;
const ALFA_MAX = 0.86;

function rgba(c, a) {
  return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')';
}

/* F-04: la opacidad de un paso de color (0..PASOS_COLOR-1); sin paso (cero), casi nada. */
function alfaDe(k) {
  return k < 0 ? 0.06 : ALFA_MIN + (k * (ALFA_MAX - ALFA_MIN)) / (PASOS_COLOR - 1);
}

/* F-09: la fuente de las cifras de la celda, de 9 a 13 px segun el alto de fila. */
function fuenteDe(fila) {
  return Math.min(13, Math.max(9, Math.round(fila) - 2));
}

const ROTULO_RES = { vol: 'VOLUMEN', delta: 'DELTA', deltap: 'DELTA %', cvd: 'CVD SESIÓN', ops: 'OPERACIONES' };

function creaLienzo(canvas, op) {
  const opciones = op && typeof op === 'object' ? op : { alLeer: op };
  const L = {
    cv: canvas, ctx: canvas.getContext('2d'), pr: window.devicePixelRatio || 1, W: 0, H: 0,
    modelo: null, fin: 0, ver: 40, verAuto: true, sigue: true, fila: LZ.FILA_DEFECTO, centro: null, modoY: 'auto',
    vista: { celda: 'bidask', color: 'delta', ref: 'vela', numeros: true, filas: FILAS_RESUMEN.slice(), rueda: 'zoom',
             sesion: 'dia' },
    pendiente: false, cuadros: 0, raton: null, arrastre: null, regla: null, aviso: null,
    cruz: opciones.cruz || null, ficha: opciones.ficha || null,
  };

  function mide() {
    const r = L.cv.parentElement.getBoundingClientRect();
    L.W = Math.max(200, Math.floor(r.width));
    L.H = Math.max(200, Math.floor(r.height));
    L.cv.width = L.W * L.pr;
    L.cv.height = L.H * L.pr;
    L.cv.style.width = L.W + 'px';
    L.cv.style.height = L.H + 'px';
    if (L.verAuto) L.ver = verPorOmision();
    if (L.cruz) {
      const c = L.cruz.parentElement.getBoundingClientRect();
      L.cruz.width = Math.floor(c.width) * L.pr;
      L.cruz.height = Math.floor(c.height) * L.pr;
      L.cruz.style.width = Math.floor(c.width) + 'px';
      L.cruz.style.height = Math.floor(c.height) + 'px';
    }
  }

  function verPorOmision() {
    return Math.min(LZ.VER_TOPE, Math.max(LZ.VER_MIN, Math.floor((L.W - LZ.EJE_P) / LZ.ESPACIADO)));
  }

  function geo() {
    const ancho = L.W - LZ.EJE_P;
    const arriba = LZ.CABEZA;
    const resumen = (L.vista.filas || []).length * LZ.FILA_RES;
    const abajo = L.H - LZ.EJE_T - resumen;
    const bs = ancho / L.ver;
    return { ancho, arriba, abajo, resumen, bs, x: (i) => ancho - (L.fin - i + 0.5) * bs };
  }

  function visibles(g) {
    const n = L.modelo ? L.modelo.velas.length : 0;
    const i0 = Math.max(0, Math.ceil(L.fin - L.ver + 0.5));
    const i1 = Math.min(n - 1, Math.floor(L.fin + 0.5));
    return { i0, i1, g };
  }

  /* La escala vertical: `centro` en la mitad del grafico y `fila` px por nivel. */
  function escala(g, paso) {
    const media = ((g.abajo - g.arriba) / 2 / L.fila) * paso;
    return { lo: L.centro - media, hi: L.centro + media };
  }

  /* AUTO: la ultima vela a la vista con niveles tiene que quedar dentro, lejos del borde (un 10 % del alto); si no, se
   * recentra en la mitad de su rango. MANUAL no se mueve. */
  function autoCentra(g, paso, i0, i1) {
    const m = L.modelo;
    let u = null;
    for (let i = i1; i >= i0 && !u; i--) if (m.velas[i].niveles.length) u = m.velas[i];
    if (!u && L.centro === null) {
      u = m.velas.slice().reverse().find((v) => v.niveles.length) || null;
    }
    if (!u) {
      if (L.centro === null) L.centro = 0;
      return;
    }
    const a = Number(u.niveles[0].nivel);
    const b = Number(u.niveles[u.niveles.length - 1].nivel) + paso;
    if (L.modoY !== 'auto' && L.centro !== null) return;
    const e = escala(g, paso);
    const borde = (e.hi - e.lo) * 0.1;
    if (L.centro === null || a < e.lo + borde || b > e.hi - borde) L.centro = (a + b) / 2;
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
    const reg = { cuadro: ++L.cuadros, ancho: L.W, alto: L.H, ver: L.ver, fin: L.fin, velas: [], of6a: true,
                  n: L.modelo ? L.modelo.velas.length : 0,
                  sigue: L.sigue, celda: L.vista.celda, color_modo: L.vista.color, referencia: L.vista.ref,
                  numeros: L.vista.numeros, filas_resumen: (L.vista.filas || []).slice() };
    const m = L.modelo;
    if (!m || !m.velas.length) {
      window.FLUJO_PINTADO = reg;
      if (typeof pintaIndicadores === 'function') pintaIndicadores(null, null, 0, -1); // OF-5a: sin velas, sin paneles
      dibujaCruz();
      return;
    }
    Object.assign(reg, { activo: m.activo, marco: m.marco, familia: m.familia, venues: m.venues, paso: m.paso,
                         unidad: m.unidad, umbrales: m.umbrales });
    const g = geo();
    const { i0, i1 } = visibles(g);
    const paso = Number(m.paso);
    autoCentra(g, paso, i0, i1);
    const { lo, hi } = escala(g, paso);
    const alto = g.abajo - g.arriba;
    const y = (p) => g.arriba + ((hi - p) / (hi - lo)) * alto;
    reg.escala = { lo, hi, arriba: g.arriba, abajo: g.abajo, modo: L.modoY, fila: L.fila, centro: L.centro,
                   fuente: fuenteDe(L.fila), resumen: g.resumen };
    rejilla(ctx, g, lo, hi, y, paso);
    const refs = referencias(m, i0, i1);
    const cvd = cvdSesion(m.velas, leeSesion(L.vista.sesion) || leeSesion('dia'), m.arranques || {});
    reg.cvd_arranques = m.arranques ? Object.keys(m.arranques).length : 0;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, g.ancho, g.abajo);
    ctx.clip();
    for (let i = i0; i <= i1; i++) reg.velas.push(pintaVela(ctx, m.velas[i], g.x(i), g, y, m, refs, i));
    ctx.restore();
    // OF-3 (campana 143): las capas, encima de las velas, con la misma escala y su contrato (flujo-capas.js)
    reg.capas = m.capas && typeof pintaCapas === 'function' && i1 >= i0 ? pintaCapas(ctx, g, y, m, paso, i0, i1) : null;
    // OF-5a (campana 146): las grandes en su vela y a su precio, y los paneles bajo el footprint, con ESTA geometria
    reg.grandes = typeof pintaGrandes === 'function' ? pintaGrandes(ctx, g, y, m, i0, i1) : null;
    pintaResumen(ctx, g, m, i0, i1, reg.velas, cvd);
    ejeTiempo(ctx, g, i0, i1, m);
    ejeModo(ctx, g);
    window.FLUJO_PINTADO = reg;
    if (typeof pintaIndicadores === 'function') pintaIndicadores(g, m, i0, i1);
    dibujaCruz();
  }

  /* F-04: la referencia del 100 % de cada celda: su vela, lo visible o su sesion (el p98 de sus valores). */
  function referencias(m, i0, i1) {
    const campo = L.vista.color === 'volumen' ? 'total' : 'delta';
    const de = (velas) => referencia(velas.flatMap((v) => v.niveles.map((l) => Number(l[campo]))));
    const out = { campo, vela: (v) => de([v]) };
    if (L.vista.ref === 'visible') {
      const r = de(m.velas.slice(i0, i1 + 1));
      out.vela = () => r;
    } else if (L.vista.ref === 'sesion') {
      const ses = leeSesion(L.vista.sesion) || leeSesion('dia');
      const grupos = new Map();
      m.velas.forEach((v) => {
        const s = sesionDe(v.ts, ses);
        if (!grupos.has(s)) grupos.set(s, []);
        grupos.get(s).push(v);
      });
      const r = new Map([...grupos].map(([s, vs]) => [s, de(vs)]));
      out.vela = (v) => r.get(sesionDe(v.ts, ses));
    }
    return out;
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
      if (yy < g.arriba || yy > g.abajo) continue;
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
      ctx.fillText(horaDe(m.velas[i].ts, m.marco), g.x(i), L.H - LZ.EJE_T / 2);
    }
  }

  /* I-03: en la esquina del eje de precio, si la escala es AUTO o MANUAL. */
  function ejeModo(ctx, g) {
    ctx.font = 'bold 9px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = L.modoY === 'manual' ? COLOR.ambar : COLOR.mudo;
    ctx.fillText(L.modoY === 'manual' ? 'MANUAL' : 'AUTO', g.ancho + 6, LZ.CABEZA / 2);
  }

  /* UNA VELA: lo que se dibuja y, en el mismo sitio, lo que se apunta. */
  function pintaVela(ctx, v, xc, g, y, m, refs, iv) {
    const w = Math.max(1, Math.floor(g.bs * 0.86));
    const x0 = Math.round(xc - w / 2);
    const paso = Number(m.paso);
    const r = { ts: v.ts, estado: v.estado, faltan: v.faltan, esperados: v.esperados, x0, ancho: w, marca: null,
                poc: null, pocs: [], va: null, resumen: null, contorno: null, referencia: null, niveles: [], indice: iv };
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
      r.contorno = { x0, x1: x0 + w, y0: g.arriba, y1: g.abajo, estilo: 'hueco' };
    } else if (v.estado === 'incompleta' || v.estado === 'abierta') {
      ctx.setLineDash(v.estado === 'abierta' ? [2, 3] : []);
      ctx.strokeStyle = v.estado === 'abierta' ? COLOR.eje : COLOR.ambar;
      ctx.strokeRect(x0 - 1.5, yTop - 1.5, w + 3, yBot - yTop + 3);
      ctx.setLineDash([]);
      r.contorno = { x0: x0 - 2, x1: x0 + w + 2, y0: yTop - 2, y1: yBot + 2, estilo: v.estado };
    } else if (nv.length) {
      // F-08: la vela es su CONTORNO de 1 px (el rango de sus niveles): las celdas no guardan apertura ni cierre
      ctx.strokeStyle = COLOR.contorno;
      ctx.strokeRect(x0 - 0.5, yTop - 0.5, w + 1, yBot - yTop + 1);
      r.contorno = { x0: x0 - 1, x1: x0 + w + 1, y0: yTop - 1, y1: yBot + 1, estilo: 'contorno' };
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
    const modo = L.vista.celda;
    const dec = decimalesDe(m.activo, m.unidad);
    const fuente = fuenteDe(L.fila);
    const filaCabe = L.vista.numeros !== false && L.fila >= LZ.FILA_TEXTO;
    const ref = refs.vela(v);
    r.referencia = ref;
    let maxTot = 0;
    if (modo === 'perfil') nv.forEach((l) => { maxTot = Math.max(maxTot, Number(l.total)); });
    const des = v.des || [];
    nv.forEach((l, k) => {
      const y0 = Math.round(y(Number(l.nivel) + paso));
      const y1 = Math.round(y(Number(l.nivel)));
      const d = Number(l.delta);
      const color = d > 0 ? 'compra' : d < 0 ? 'venta' : 'neutro';
      const fil = filtro(l.total, m.filtro);
      const x = des[k] || {};
      const fila = { nivel: l.nivel, y0, y1, venta: l.venta, compra: l.compra, delta: l.delta, total: l.total,
                     operaciones: l.operaciones, texto_venta: null, texto_compra: null, texto: null, color,
                     paso_color: -1, filtro: fil, dc: !!x.dc, dv: !!x.dv, ac: !!x.ac, av: !!x.av, borde: null };
      if (fil === 'escondida' || y1 < g.arriba - 1 || y0 > g.abajo + 1) {
        r.niveles.push(fila);
        return;
      }
      fila.paso_color = pasoColor(Number(l[refs.campo]), ref);
      const a = alfaDe(fila.paso_color) * (fil === 'atenuada' ? 0.25 : 1);
      ctx.fillStyle = rgba(refs.campo === 'total' ? COLOR.volumen : COLOR[color], a.toFixed(3));
      ctx.fillRect(x0, y0, w, Math.max(1, y1 - y0 - (filaCabe ? 1 : 0)));
      if (modo === 'perfil' && maxTot > 0) {
        const pw = Math.max(1, Math.round(((w - 2) * Number(l.total)) / maxTot));
        ctx.fillStyle = rgba(COLOR[color], 0.85);
        ctx.fillRect(x0 + 1, y0 + 1, pw, Math.max(1, y1 - y0 - 2));
        fila.barra = pw;
      }
      if (fil === 'grande') {
        ctx.strokeStyle = COLOR.grande;
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, Math.max(1, y1 - y0 - 1));
      }
      // F-06: el APILADO, una barra de 2 px en el borde de su lado
      if (x.ac) {
        ctx.fillStyle = COLOR.fuerte_compra;
        ctx.fillRect(x0 + w - 2, y0, 2, Math.max(1, y1 - y0 - 1));
      }
      if (x.av) {
        ctx.fillStyle = COLOR.fuerte_venta;
        ctx.fillRect(x0, y0, 2, Math.max(1, y1 - y0 - 1));
      }
      const conTexto = filaCabe && fil !== 'atenuada' && modo !== 'perfil';
      const ym = (y0 + y1) / 2;
      let escrito = false;
      if (conTexto && modo === 'bidask') {
        // F-02: la venta del agresor (bid) a la izquierda del eje de la vela, la compra (ask) a la derecha
        const tv = cifraE04(l.venta, dec);
        const tc = cifraE04(l.compra, dec);
        ctx.font = (x.dv ? 'bold ' : '') + fuente + 'px ui-monospace, monospace';
        const wv = ctx.measureText(tv).width;
        ctx.font = (x.dc ? 'bold ' : '') + fuente + 'px ui-monospace, monospace';
        const wc = ctx.measureText(tc).width;
        if (wv + 4 <= w / 2 && wc + 4 <= w / 2) {
          ctx.font = (x.dv ? 'bold ' : '') + fuente + 'px ui-monospace, monospace';
          ctx.fillStyle = x.dv ? COLOR.fuerte_venta : COLOR.texto;
          ctx.textAlign = 'right';
          fila.texto_venta = tv;
          ctx.fillText(fila.texto_venta, xc - 3, ym);
          ctx.font = (x.dc ? 'bold ' : '') + fuente + 'px ui-monospace, monospace';
          ctx.fillStyle = x.dc ? COLOR.fuerte_compra : COLOR.texto;
          ctx.textAlign = 'left';
          fila.texto_compra = tc;
          ctx.fillText(fila.texto_compra, xc + 3, ym);
          escrito = true;
        }
      } else if (conTexto) {
        const t = modo === 'delta' ? (d > 0 ? '+' : '') + cifraE04(l.delta, dec)
          : modo === 'trades' ? cifraE04(l.operaciones, 0) : cifraE04(l.total, dec);
        const fuerte = modo === 'delta' && (x.dc || x.dv);
        ctx.font = (fuerte ? 'bold ' : '') + fuente + 'px ui-monospace, monospace';
        if (ctx.measureText(t).width + 4 <= w) {
          ctx.fillStyle = fuerte ? (x.dc ? COLOR.fuerte_compra : COLOR.fuerte_venta) : COLOR.texto;
          ctx.textAlign = 'right';
          fila.texto = t;
          ctx.fillText(t, x0 + w - 2, ym);
          escrito = true;
        }
      }
      // F-05: el desequilibrio, en el color y la negrita del lado fuerte; si la cifra no se escribe, un borde de 1 px
      if ((x.dc || x.dv) && !escrito) {
        ctx.strokeStyle = x.dc ? COLOR.fuerte_compra : COLOR.fuerte_venta;
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, Math.max(1, y1 - y0 - 1));
        if (x.dc && x.dv) {
          ctx.strokeStyle = COLOR.fuerte_venta;
          ctx.strokeRect(x0 + 1.5, y0 + 1.5, Math.max(1, w - 3), Math.max(1, y1 - y0 - 3));
        }
        fila.borde = x.dc && x.dv ? 'los dos' : x.dc ? 'compra' : 'venta';
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
      r.pocs.push(r.poc);
    }
    // F-07: si hay EMPATE en el volumen maximo, todos los empatados llevan su marco
    if (nv.length) {
      pocsDe(nv).filter((n) => n !== v.poc).forEach((n) => {
        const y0 = Math.round(y(Number(n) + paso));
        const y1 = Math.round(y(Number(n)));
        ctx.strokeStyle = COLOR.poc;
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, Math.max(1, y1 - y0 - 1));
        r.pocs.push({ nivel: n, y0, y1 });
      });
    }
    // LA VALUE AREA de la vela, servida: una barra a su izquierda de VAL a VAH + paso
    if (v.value_area) {
      const y0 = Math.round(y(Number(v.value_area.vah) + paso));
      const y1 = Math.round(y(Number(v.value_area.val)));
      ctx.fillStyle = COLOR.va;
      ctx.fillRect(x0 - 3, y0, 2, y1 - y0);
      r.va = { val: v.value_area.val, vah: v.value_area.vah, y0, y1 };
    }
    return r;
  }

  /* F-10: LAS FILAS DE RESUMEN bajo el grafico, una por metrica y alineadas con cada vela, con su rotulo en el margen
   * del eje: el color por signo (o por tamano, el volumen y las operaciones) con su intensidad en 20 pasos contra el
   * maximo de lo visible, y la cifra si cabe. Lo que no se sabe (una vela HUECO, el CVD tras un hueco) no se pinta. */
  function pintaResumen(ctx, g, m, i0, i1, regVelas, cvd) {
    const filas = L.vista.filas || [];
    if (!filas.length) {
      regVelas.forEach((r) => { r.resumen = null; });
      return;
    }
    const dec = decimalesDe(m.activo, m.unidad);
    const valores = [];
    for (let i = i0; i <= i1; i++) valores.push(resumenVela(m.velas[i], cvd[i]));
    const maximo = {};
    filas.forEach((f) => { maximo[f] = Math.max(0, ...valores.map((x) => Math.abs(Number(x[f] || 0)))); });
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, g.abajo, g.ancho, g.resumen);
    ctx.clip();
    ctx.font = '9px ui-monospace, monospace';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';
    regVelas.forEach((r, k) => {
      const val = valores[k];
      const v = m.velas[r.indice];
      r.resumen = { delta: null, total: null, operaciones: null, deltap: null, cvd: null, valores: val,
                    cvd_estado: cvd[r.indice] ? cvd[r.indice].estado : null };
      filas.forEach((f, j) => {
        const yr = g.abajo + j * LZ.FILA_RES;
        if (val[f] === null || val[f] === undefined) return;
        const x = Number(val[f]);
        const signo = f === 'vol' || f === 'ops' ? null : x > 0 ? COLOR.compra : x < 0 ? COLOR.venta : COLOR.neutro;
        const kk = pasoColor(x, maximo[f]);
        ctx.fillStyle = rgba(signo || COLOR.volumen, (alfaDe(kk) * 0.6).toFixed(3));
        ctx.fillRect(r.x0, yr + 1, r.ancho, LZ.FILA_RES - 2);
        if (f === 'cvd' && cvd[r.indice] && cvd[r.indice].estado === 'incompleta') {
          ctx.strokeStyle = COLOR.ambar;
          ctx.strokeRect(r.x0 + 0.5, yr + 1.5, r.ancho - 1, LZ.FILA_RES - 3);
        }
        const t = f === 'deltap' ? x.toFixed(1) + '%' : f === 'ops' ? cifraE04(val[f], 0)
          : (f === 'delta' || f === 'cvd') && x > 0 ? '+' + cifraE04(val[f], dec) : cifraE04(val[f], dec);
        if (ctx.measureText(t).width + 4 > r.ancho) return;
        ctx.fillStyle = COLOR.texto;
        ctx.fillText(t, r.x0 + r.ancho / 2, yr + LZ.FILA_RES / 2);
        r.resumen[{ vol: 'total', ops: 'operaciones' }[f] || f] = t;
      });
      if (v.estado === 'hueco') r.resumen.hueco = true;
    });
    ctx.restore();
    ctx.font = '9px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    filas.forEach((f, j) => {
      const yr = g.abajo + j * LZ.FILA_RES;
      ctx.strokeStyle = COLOR.rejilla;
      ctx.beginPath();
      ctx.moveTo(0, yr + 0.5);
      ctx.lineTo(L.W, yr + 0.5);
      ctx.stroke();
      ctx.fillStyle = COLOR.eje;
      ctx.fillText(ROTULO_RES[f], g.ancho + 6, yr + LZ.FILA_RES / 2);
    });
  }

  /* --------------------------------------------------------- donde esta el raton */
  function zona(px, py) {
    const g = geo();
    if (px >= g.ancho) return 'precio';
    if (py >= L.H - LZ.EJE_T) return 'tiempo';
    return py < g.abajo ? 'grafico' : 'resumen';
  }

  /* La vela bajo una x (la de centro mas cercano) y el nivel bajo una y (redondeado al paso, hacia abajo). */
  function bajo(px, py) {
    const m = L.modelo;
    if (!m || !m.velas.length) return null;
    const g = geo();
    const paso = Number(m.paso);
    const i = Math.round(L.fin - (g.ancho - px) / g.bs + 0.5);
    const v = m.velas[i] || null;
    const { lo, hi } = escala(g, paso);
    const precio = lo + ((g.abajo - py) / (g.abajo - g.arriba)) * (hi - lo);
    const dec = (String(m.paso).split('.')[1] || '').length;
    const nivel = py >= g.arriba && py < g.abajo ? (Math.floor(precio / paso + 1e-9) * paso).toFixed(dec) : null;
    return { i, v, precio, nivel, g };
  }

  /* E-05 y F-16: la CRUZ (1 px, con su precio y su hora en los ejes y la vertical por los paneles) y la FICHA de la
   * celda y la vela bajo el cursor, en una capa aparte (no repinta el footprint). #lectura dice lo mismo en una linea,
   * para el lector de pantalla. */
  function dibujaCruz() {
    const c = L.cruz;
    if (!c) return;
    const ctx = c.getContext('2d');
    ctx.setTransform(L.pr, 0, 0, L.pr, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    const reg = { visible: false };
    const r = L.raton;
    const b = r && L.modelo && L.modelo.velas.length ? bajo(r.x, r.y) : null;
    const dx = L.cv.getBoundingClientRect().left - c.getBoundingClientRect().left;
    const dy = L.cv.getBoundingClientRect().top - c.getBoundingClientRect().top;
    if (b && b.v && r.zona !== 'precio' && r.zona !== 'tiempo') {
      const g = b.g;
      const xv = Math.round(dx + g.x(b.i)) + 0.5;
      ctx.strokeStyle = COLOR.cruz;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(xv, dy + g.arriba);
      ctx.lineTo(xv, c.height / L.pr);
      if (r.sobre === 'grafico') {
        ctx.moveTo(dx, Math.round(dy + r.y) + 0.5);
        ctx.lineTo(dx + g.ancho, Math.round(dy + r.y) + 0.5);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = '10px ui-monospace, monospace';
      ctx.textBaseline = 'middle';
      const hora = horaDe(b.v.ts, L.modelo.marco);
      const ancho = ctx.measureText(hora).width + 8;
      ctx.fillStyle = COLOR.etiqueta;
      ctx.fillRect(xv - ancho / 2, dy + L.H - LZ.EJE_T + 1, ancho, LZ.EJE_T - 2);
      ctx.fillStyle = COLOR.texto;
      ctx.textAlign = 'center';
      ctx.fillText(hora, xv, dy + L.H - LZ.EJE_T / 2);
      Object.assign(reg, { visible: true, x: dx + g.x(b.i), vela: b.v.ts, texto_hora: hora, sobre: r.sobre,
                           x_lienzo: g.x(b.i), y_lienzo: r.y });
      if (r.sobre === 'grafico' && b.nivel !== null) {
        ctx.fillStyle = COLOR.etiqueta;
        ctx.fillRect(dx + g.ancho + 1, dy + r.y - 7, LZ.EJE_P - 2, 14);
        ctx.fillStyle = COLOR.texto;
        ctx.textAlign = 'left';
        ctx.fillText(b.nivel, dx + g.ancho + 6, dy + r.y);
        Object.assign(reg, { y: dy + r.y, nivel: b.nivel, texto_precio: b.nivel });
      }
      if (r.sobre === 'panel' && typeof cruzPanel === 'function') Object.assign(reg, cruzPanel(ctx, r, dx, dy));
    }
    window.FLUJO_CRUZ = reg;
    pintaRegla(ctx, dx, dy);
    ficha(b, r);
  }

  function ficha(b, r) {
    const f = L.ficha;
    const reg = { visible: false };
    if (f && b && b.v && r && r.sobre === 'grafico' && r.zona !== 'precio') {
      const v = b.v;
      const pin = (window.FLUJO_PINTADO.velas || []).find((x) => x.ts === v.ts);
      const fila = b.nivel !== null && pin ? pin.niveles.find((x) => Number(x.nivel) === Number(b.nivel)) : null;
      const cob = { abierta: 'en curso', hueco: 'HUECO: nadie la escuchó', vacia: 'escuchada entera, sin operaciones',
                    completa: 'completa', incompleta: 'INCOMPLETA: faltan ' + v.faltan + ' de ' + v.esperados
                    + ' minutos-venue' }[v.estado];
      const lineas = [v.ts.slice(5, 16).replace('T', ' ') + 'Z · ' + cob];
      if (fila) {
        const p = Number(L.modelo.paso);
        const dec = (String(L.modelo.paso).split('.')[1] || '').length;
        lineas.push('precio ' + fila.nivel + '–' + (Number(fila.nivel) + p).toFixed(dec));
        lineas.push('venta ' + fila.venta + ' × compra ' + fila.compra);
        lineas.push('Δ ' + fila.delta + ' · volumen ' + fila.total + ' · ' + fila.operaciones + ' operaciones');
        const marcas = [];
        if (fila.dc) marcas.push('desequilibrio COMPRADOR' + (fila.ac ? ' (apilado)' : ''));
        if (fila.dv) marcas.push('desequilibrio VENDEDOR' + (fila.av ? ' (apilado)' : ''));
        if (pin.pocs.some((x) => Number(x.nivel) === Number(fila.nivel))) marcas.push('POC');
        if (v.value_area && Number(fila.nivel) >= Number(v.value_area.val) && Number(fila.nivel) <= Number(v.value_area.vah)) {
          marcas.push('en la value area');
        }
        if (marcas.length) lineas.push(marcas.join(' · '));
      } else if (b.nivel !== null) {
        lineas.push('precio ' + b.nivel + ': sin operaciones en esta vela');
      }
      if (v.niveles.length) {
        lineas.push('vela: volumen ' + v.total + ' · Δ ' + v.delta + ' · ' + v.operaciones + ' operaciones · POC '
          + v.poc + (v.value_area ? ' · value area ' + v.value_area.val + '–' + v.value_area.vah : ''));
      }
      vaciar(f);
      lineas.forEach((t, k) => f.appendChild(el('div', k ? null : 'ficha-cab', t)));
      f.hidden = false;
      const caja = f.parentElement.getBoundingClientRect();
      const fw = f.offsetWidth;
      const fh = f.offsetHeight;
      const left = r.x + 16 + fw > caja.width - LZ.EJE_P ? r.x - 16 - fw : r.x + 16;
      const top = Math.min(Math.max(0, r.y + 16), Math.max(0, caja.height - fh - LZ.EJE_T));
      f.style.left = Math.max(0, left) + 'px';
      f.style.top = top + 'px';
      Object.assign(reg, { visible: true, vela: v.ts, nivel: fila ? fila.nivel : null, lineas,
                           x: Math.max(0, left), y: top });
    } else if (f) {
      f.hidden = true;
    }
    window.FLUJO_FICHA = reg;
    if (opciones.alLeer) {
      if (reg.visible) opciones.alLeer(reg.lineas.join(' · '));
      else if (!r) opciones.alLeer(null);
    }
  }

  /* I-08: LA REGLA (Ctrl + arrastre): de la vela y el nivel donde empieza a donde acaba, cuanto cambia el precio y el
   * tiempo, cuantas velas y su volumen sumado (exacto, de lo servido; las velas HUECO se cuentan aparte). */
  function midaRegla() {
    const q = L.regla;
    const m = L.modelo;
    if (!q || !m) return null;
    const a = bajo(q.x0, q.y0);
    const z = bajo(q.x1, q.y1);
    const n = m.velas.length;
    const i0 = Math.max(0, Math.min(n - 1, Math.min(a.i, z.i)));
    const i1 = Math.max(0, Math.min(n - 1, Math.max(a.i, z.i)));
    let e = 0;
    for (let i = i0; i <= i1; i++) e = Math.max(e, decimales(m.velas[i].total));
    let vol = 0n;
    let huecos = 0;
    let incompletas = 0;
    for (let i = i0; i <= i1; i++) {
      const v = m.velas[i];
      if (v.estado === 'hueco') huecos += 1;
      else vol += entero(v.total, e);
      if (v.estado === 'incompleta') incompletas += 1;
    }
    const mMs = FLUJO_MARCOS[m.marco] * 60000;
    const dec = (String(m.paso).split('.')[1] || '').length;
    const dp = a.nivel !== null && z.nivel !== null ? (Number(z.nivel) - Number(a.nivel)).toFixed(dec) : null;
    return { desde: m.velas[i0].ts, hasta: isoZ(Date.parse(m.velas[i1].ts) + mMs), velas: i1 - i0 + 1,
             minutos: ((i1 - i0 + 1) * mMs) / 60000, nivel_desde: a.nivel, nivel_hasta: z.nivel, delta_precio: dp,
             volumen: deEntero(vol, e), huecos, incompletas, unidad: m.unidad };
  }

  function pintaRegla(ctx, dx, dy) {
    const q = L.regla;
    const r = q ? midaRegla() : null;
    window.FLUJO_REGLA = r ? Object.assign({ visible: true }, r) : { visible: false };
    if (!r) return;
    const x0 = Math.min(q.x0, q.x1);
    const y0 = Math.min(q.y0, q.y1);
    ctx.fillStyle = 'rgba(242,204,96,0.08)';
    ctx.fillRect(dx + x0, dy + y0, Math.abs(q.x1 - q.x0), Math.abs(q.y1 - q.y0));
    ctx.strokeStyle = COLOR.poc;
    ctx.strokeRect(dx + x0 + 0.5, dy + y0 + 0.5, Math.abs(q.x1 - q.x0), Math.abs(q.y1 - q.y0));
    const u = r.unidad === 'usd' ? 'USD' : L.modelo.activo;
    const t = 'Δ precio ' + (r.delta_precio === null ? '—' : (Number(r.delta_precio) > 0 ? '+' : '') + r.delta_precio)
      + ' · Δ tiempo ' + (r.minutos >= 60 ? (r.minutos / 60).toFixed(r.minutos % 60 ? 1 : 0) + ' h' : r.minutos + ' min')
      + ' · ' + r.velas + ' velas · volumen ' + cifraE04(r.volumen, decimalesDe(L.modelo.activo, r.unidad)) + ' ' + u
      + (r.huecos ? ' (+' + r.huecos + ' hueco' + (r.huecos > 1 ? 's' : '') + ' sin dato)' : '');
    ctx.font = '10px ui-monospace, monospace';
    const w = ctx.measureText(t).width + 10;
    const xt = Math.min(dx + q.x1 + 8, dx + L.W - LZ.EJE_P - w);
    ctx.fillStyle = COLOR.etiqueta;
    ctx.fillRect(xt, dy + q.y1 - 9, w, 18);
    ctx.fillStyle = COLOR.texto;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(t, xt + 5, dy + q.y1);
    window.FLUJO_REGLA.texto = t;
  }

  /* --------------------------------------------------------- lo que se toca */
  function acota() {
    const n = L.modelo ? L.modelo.velas.length : 0;
    L.ver = Math.min(LZ.VER_TOPE, Math.max(LZ.VER_MIN, L.ver));
    L.fin = Math.min(n - 1 + L.ver * 0.3, Math.max(L.ver * 0.3, L.fin));
    L.fila = Math.min(FILA_MAX, Math.max(FILA_MIN, L.fila));
  }

  /* Tras un gesto del raton o del teclado: si se miraba el final se sigue mirando (I-05), y la vista va al hash. */
  function tocado(horizontal) {
    acota();
    if (horizontal && L.modelo) L.sigue = L.fin >= L.modelo.velas.length - 1 - 1e-6;
    pide();
    if (opciones.alCambiar) {
      clearTimeout(L.aviso);
      L.aviso = setTimeout(() => opciones.alCambiar(estadoVista()), 150);
    }
  }

  function estadoVista() {
    const n = L.modelo ? L.modelo.velas.length : 0;
    const dec = L.modelo ? (String(L.modelo.paso).split('.')[1] || '').length : 0;
    return { ver: L.verAuto ? null : Math.round(L.ver), x: L.sigue ? null : Math.max(0, Math.round((n - 1 - L.fin) * 10) / 10),
             y: L.modoY === 'manual' && L.centro !== null ? Math.max(0, L.centro).toFixed(Math.max(dec, 2)) : null,
             fila: L.modoY === 'manual' || L.fila !== LZ.FILA_DEFECTO ? Math.round(L.fila) : null };
  }

  /* Acercar el tiempo con `f`, dejando la vela de `px` donde esta (I-01). */
  function zoomTiempo(f, px) {
    const g = geo();
    const dx = g.ancho - px;
    const bajoX = L.fin - dx / g.bs;
    L.ver *= f;
    L.verAuto = false;
    acota();
    L.fin = bajoX + dx / ((L.W - LZ.EJE_P) / L.ver);
  }

  /* Acercar el precio con `f`, dejando el precio de `py` donde esta (o el centro, sin `py`): pasa a MANUAL. */
  function zoomPrecio(f, py) {
    const g = geo();
    const paso = L.modelo ? Number(L.modelo.paso) : 1;
    const medio = g.arriba + (g.abajo - g.arriba) / 2;
    const precio = py === undefined ? L.centro : L.centro + ((medio - py) / L.fila) * paso;
    L.fila *= f;
    acota();
    L.centro = precio - ((medio - (py === undefined ? medio : py)) / L.fila) * paso;
    L.modoY = 'manual';
  }

  function desplaza(velas) {
    L.fin += velas;
  }

  const pos = (ev) => {
    const r = L.cv.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top };
  };

  L.cv.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    if (!L.modelo) return;
    const p = pos(ev);
    const z = zona(p.x, p.y);
    const d = ev.deltaY || ev.deltaX;
    const f = Math.exp(d * 0.00113); // una muesca (100) = x1.12
    if (z === 'precio') zoomPrecio(1 / f);
    else if (z === 'tiempo') {
      L.ver *= f;
      L.verAuto = false;
    } else if (ev.ctrlKey || ev.metaKey) zoomPrecio(1 / f, p.y);
    else if (ev.shiftKey !== (L.vista.rueda === 'desplaza')) desplaza((d / 100) * Math.max(1, L.ver / 10));
    else zoomTiempo(f, p.x);
    tocado(z !== 'precio' && !(ev.ctrlKey || ev.metaKey));
  }, { passive: false });
  L.cv.addEventListener('mousedown', (ev) => {
    if (ev.button !== 0 || !L.modelo) return;
    const p = pos(ev);
    const z = zona(p.x, p.y);
    if (ev.ctrlKey && z !== 'precio' && z !== 'tiempo') {
      L.regla = { x0: p.x, y0: p.y, x1: p.x, y1: p.y, midiendo: true };
      dibujaCruz();
      return;
    }
    L.regla = null;
    L.arrastre = { z, x: p.x, y: p.y, fin: L.fin, ver: L.ver, fila: L.fila, centro: L.centro, vertical: false };
    ev.preventDefault();
  });
  window.addEventListener('mouseup', () => {
    if (L.regla && L.regla.midiendo) L.regla.midiendo = false;
    L.arrastre = null;
  });
  L.cv.addEventListener('mousemove', (ev) => {
    const p = pos(ev);
    const a = L.arrastre;
    if (L.regla && L.regla.midiendo) {
      L.regla.x1 = p.x;
      L.regla.y1 = p.y;
    } else if (a && L.modelo) {
      const g = geo();
      const paso = Number(L.modelo.paso);
      if (a.z === 'precio') {
        // I-02: arrastrar el eje de precio escala en vertical (hacia arriba acerca), con el centro quieto
        L.fila = a.fila * Math.exp(-(p.y - a.y) * 0.007);
        L.centro = a.centro;
        L.modoY = 'manual';
        tocado(false);
      } else if (a.z === 'tiempo') {
        // I-02: arrastrar el eje de tiempo cambia el espaciado (a la derecha, velas mas anchas), con el final quieto
        L.ver = a.ver * Math.exp(-(p.x - a.x) * 0.007);
        L.verAuto = false;
        L.fin = a.fin;
        tocado(true);
      } else {
        // I-03: arrastrar el grafico mueve los dos ejes; en vertical, la escala pasa a MANUAL
        L.fin = a.fin - (p.x - a.x) / g.bs;
        if (a.vertical || Math.abs(p.y - a.y) >= 3) {
          a.vertical = true;
          L.modoY = 'manual';
          L.centro = a.centro + ((p.y - a.y) / L.fila) * paso;
        }
        tocado(true);
      }
    }
    L.raton = { x: p.x, y: p.y, zona: zona(p.x, p.y), sobre: p.y < geo().abajo ? 'grafico' : 'resumen' };
    dibujaCruz();
  });
  L.cv.addEventListener('mouseleave', () => {
    L.raton = null;
    dibujaCruz();
  });
  L.cv.addEventListener('dblclick', (ev) => {
    const p = pos(ev);
    if (zona(p.x, p.y) === 'precio') api.auto();
  });
  L.cv.addEventListener('contextmenu', (ev) => {
    const p = pos(ev);
    if (zona(p.x, p.y) !== 'precio' || !opciones.alMenu) return;
    ev.preventDefault();
    opciones.alMenu(ev.clientX, ev.clientY);
  });
  new ResizeObserver(() => {
    mide();
    pide();
  }).observe(L.cv.parentElement);
  mide();

  const api = {
    /* el modelo entero (una vista nueva): se mira el final, o lo que diga el hash */
    pon(modelo, e) {
      L.modelo = modelo;
      L.centro = null;
      L.regla = null;
      api.vista(e || {}, true);
    },
    /* lo que el hash dice de la vista: el modo de la celda y el color, y el estado de los dos ejes */
    vista(e, nueva) {
      ['celda', 'color', 'ref', 'numeros', 'filas', 'rueda', 'sesion'].forEach((k) => {
        if (e[k] !== undefined) L.vista[k] = e[k];
      });
      if (!nueva && e.ver === undefined) {
        pide();
        return;
      }
      L.verAuto = !e.ver;
      L.ver = e.ver || verPorOmision();
      const n = L.modelo ? L.modelo.velas.length : 0;
      L.sigue = e.x === null || e.x === undefined;
      L.fin = n - 1 - (L.sigue ? 0 : e.x);
      L.fila = e.fila || LZ.FILA_DEFECTO;
      L.modoY = e.y ? 'manual' : 'auto';
      if (e.y) L.centro = Number(e.y);
      acota();
      pide();
    },
    /* velas que cambian (el latido): si se seguia la ultima, se sigue (I-05); si no, la vista no se mueve */
    actualiza() {
      if (L.sigue) L.fin = L.modelo.velas.length - 1;
      acota();
      pide();
    },
    /* I-04: la escala vertical vuelve a AUTO (la fila por omision, centrada en la ultima vela a la vista) */
    auto() {
      L.modoY = 'auto';
      L.fila = LZ.FILA_DEFECTO;
      L.centro = null;
      tocado(false);
    },
    manual() {
      L.modoY = 'manual';
      tocado(false);
    },
    /* I-05 e I-06: el teclado y el boton del presente */
    mueve(velas) {
      desplaza(velas);
      tocado(true);
    },
    pagina(k) {
      desplaza(k * L.ver);
      tocado(true);
    },
    presente() {
      L.fin = L.modelo ? L.modelo.velas.length - 1 : 0;
      tocado(true);
    },
    inicio() {
      L.fin = L.ver - 1;
      tocado(true);
    },
    borraRegla() {
      L.regla = null;
      dibujaCruz();
    },
    cruzEn(r) {
      L.raton = r;
      dibujaCruz();
    },
    estado: () => ({ ver: L.ver, fin: L.fin, sigue: L.sigue, fila: L.fila, centro: L.centro, modoY: L.modoY }),
    geo,
    pinta,
    pide,
  };
  return api;
}

/* La hora que se escribe de una vela en el eje de tiempo y en la cruz, segun su marco. */
function horaDe(t, marco) {
  return marco === '1d' ? t.slice(5, 10) : marco === '4h' ? t.slice(5, 10) + ' ' + t.slice(11, 16) : t.slice(11, 16);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LZ, COLOR, creaLienzo, fuenteDe, alfaDe, horaDe };
}
