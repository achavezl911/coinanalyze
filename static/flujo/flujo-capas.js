'use strict';
/* LAS CAPAS sobre el footprint (campana 143, OF-3): el perfil de cada SESION, el COMPUESTO de varias, el DINAMICO (lo
 * visible), el FIJO (un rango elegido) y el VWAP de la sesion con sus bandas de 1, 2 y 3 desviaciones.
 * ---------------------------------------------------------------------------
 * LO CALCULA EL SERVIDOR (/api/orderflow/sesiones, /vwap y /perfil): POC, VAH, VAL, niveles, VWAP y bandas llegan
 * servidos y aqui se PINTAN TAL CUAL, sobre la escala del footprint, que las capas NO cambian: lo que cae fuera de ella
 * no se ve, y el contrato lo dice (fuera: true).
 *
 * DONDE: el perfil de una sesion nace en su inicio (o en el borde izquierdo si empezo antes) y sus lineas POC/VAH/VAL
 * cruzan la sesion; el compuesto nace en el borde izquierdo del grafico y sus lineas, discontinuas, lo cruzan entero; el
 * dinamico nace en el borde derecho; el fijo, en el inicio de su rango, con el rango sombreado. El VWAP es una linea por
 * los centros de las velas, con sus bandas discontinuas a +-1, 2 y 3 desviaciones. POC en el centro de su fila; VAH en
 * el borde de ARRIBA de su fila y VAL en el de ABAJO: la value area es [VAL, VAH + paso), como la sirve el servidor.
 *
 * EL CONTRATO (lo lee K109): `window.FLUJO_PINTADO.capas`, apuntado donde se dibuja. Por perfil: sus x, su estado y la
 * marca escrita, POC/VAH/VAL con su nivel, su y y el texto que se paso a fillText (null si no se escribio), y cada barra
 * (nivel, total, filas y ancho). Por VWAP: por punto visible su vela, su x y, para el VWAP y para cada banda k (abajo y
 * arriba), el valor servido que se pinto y su y. */

const CAPA = {
  sesion: '#b48cff', compuesto: '#6fa8ff', dinamico: '#ffc65c', fijo: '#5ce0c0', poc: '#f2cc60', texto: '#e6e9ee',
  vwap: '#ffffff', ambar: '#e6b75a', BARRA: 160, PARTE_SESION: 0.35, PARTE_LADO: 0.22,
};
const BANDA_ALFA = { 1: 0.85, 2: 0.6, 3: 0.4 };

function pintaCapas(ctx, g, y, m, paso, i0, i1) {
  const c = m.capas || {};
  const reg = { sesiones: [], compuesto: null, dinamico: null, fijo: null, vwap: [] };
  const mMs = FLUJO_MARCOS[m.marco] * 60000;
  const t0 = Date.parse(m.velas[0].ts);
  const xT = (ms) => g.x(0) - g.bs / 2 + ((ms - t0) / mMs) * g.bs;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, g.arriba, g.ancho, g.abajo - g.arriba);
  ctx.clip();
  if (c.sesiones) {
    c.sesiones.datos.sesiones.forEach((s, k) => {
      const x0 = xT(Date.parse(s.inicio));
      const x1 = xT(Date.parse(s.corte));
      if (x1 < 0 || x0 > g.ancho) return;
      const st = estadoSesion(s);
      const parte = (Math.min(x1, g.ancho) - Math.max(0, x0)) * CAPA.PARTE_SESION;
      const r = pintaPerfil(ctx, g, y, paso, s, { x0, x1, ancla: Math.max(0, x0), dir: 1,
        ancho: Math.min(CAPA.BARRA, Math.max(8, parte)), color: CAPA.sesion, discontinua: false });
      Object.assign(r, { inicio: s.inicio, fin: s.fin, corte: s.corte }, st);
      r.marca = escribeMarca(ctx, 'perfil', st, Math.max(0, x0) + 3, g.arriba + 10 + 12 * (k % 2), false);
      reg.sesiones.push(r);
    });
  }
  if (c.compuesto && c.compuesto.datos.compuesto) {
    const s = c.compuesto.datos.compuesto;
    const st = estadoSesion(s);
    const r = pintaPerfil(ctx, g, y, paso, s, { x0: 0, x1: g.ancho, ancla: 0, dir: 1, ancho: g.ancho * CAPA.PARTE_LADO,
      color: CAPA.compuesto, discontinua: true });
    Object.assign(r, { inicio: s.inicio, corte: s.corte, sesiones: s.sesiones }, st);
    r.marca = escribeMarca(ctx, 'compuesto ' + s.sesiones, st, 3, g.abajo - 6, false);
    reg.compuesto = r;
  }
  [['dinamico', 'dinámico', CAPA.dinamico], ['fijo', 'fijo', CAPA.fijo]].forEach(([nombre, rotulo, color]) => {
    const capa = c[nombre];
    if (!capa) return;
    const p = capa.datos;
    let caja = { x0: g.ancho * (1 - CAPA.PARTE_LADO), x1: g.ancho, ancla: g.ancho, dir: -1,
                 ancho: g.ancho * CAPA.PARTE_LADO, color, discontinua: false };
    if (nombre === 'fijo') {
      const x0 = xT(Date.parse(p.desde));
      const x1 = xT(Date.parse(p.hasta));
      ctx.fillStyle = 'rgba(92,224,192,0.06)';
      ctx.fillRect(x0, g.arriba, x1 - x0, g.abajo - g.arriba);
      caja = { x0, x1, ancla: Math.max(0, x0), dir: 1, ancho: Math.min(CAPA.BARRA * 2, Math.max(8, (x1 - x0) * 0.5)),
               color, discontinua: false };
    }
    const r = pintaPerfil(ctx, g, y, paso, p, caja);
    Object.assign(r, { desde: p.desde, hasta: p.hasta }, capa.estado);
    r.marca = escribeMarca(ctx, rotulo, capa.estado, nombre === 'fijo' ? Math.max(0, caja.x0) + 3 : g.ancho - 3,
                           g.arriba + 34, nombre !== 'fijo');
    reg[nombre] = r;
  });
  if (c.vwap) {
    c.vwap.datos.sesiones.forEach((s, k) => {
      const r = pintaVwap(ctx, g, y, m, s, xT, i0, i1);
      if (!r) return;
      const st = estadoSesion(s);
      Object.assign(r, { inicio: s.inicio, fin: s.fin, corte: s.corte }, st);
      r.marca = escribeMarca(ctx, 'VWAP', st, Math.max(0, xT(Date.parse(s.inicio))) + 3,
                             g.arriba + 46 + 12 * (k % 2), false);
      reg.vwap.push(r);
    });
  }
  ctx.restore();
  return reg;
}

/* UNA marca de estado (en curso, hueco, faltan N/M): se escribe solo si hay algo que decir. */
function escribeMarca(ctx, quien, st, x, yy, derecha) {
  const m = marcaCapa(st);
  if (!m) return null;
  const t = quien + ' · ' + m;
  ctx.font = '9px ui-monospace, monospace';
  ctx.textAlign = derecha ? 'right' : 'left';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = st.estado === 'completa' ? CAPA.texto : CAPA.ambar;
  ctx.fillText(t, x, yy);
  return t;
}

/* UN PERFIL (de sesion, compuesto, dinamico o fijo): sus barras desde `ancla` hacia `dir`, y POC/VAH/VAL de x0 a x1. */
function pintaPerfil(ctx, g, y, paso, p, caja) {
  const r = { x0: Math.round(caja.x0), x1: Math.round(caja.x1), poc: null, vah: null, val: null, barras: [] };
  const niveles = p.niveles || [];
  let max = 0;
  niveles.forEach((l) => { max = Math.max(max, Number(l.total)); });
  const va = p.value_area;
  niveles.forEach((l) => {
    const n = Number(l.nivel);
    const y0 = Math.round(y(n + paso));
    const y1 = Math.round(y(n));
    const w = max ? (Number(l.total) / max) * caja.ancho : 0;
    const dentro = va && n >= Number(va.val) && n <= Number(va.vah);
    ctx.globalAlpha = l.nivel === p.poc ? 0.55 : dentro ? 0.38 : 0.2;
    ctx.fillStyle = l.nivel === p.poc ? CAPA.poc : caja.color;
    ctx.fillRect(caja.dir > 0 ? caja.ancla : caja.ancla - w, y0, w, Math.max(1, y1 - y0));
    r.barras.push({ nivel: l.nivel, total: l.total, y0, y1, ancho: Math.round(w * 10) / 10,
                    fuera: y1 < g.arriba || y0 > g.abajo });
  });
  ctx.globalAlpha = 1;
  const linea = (nombre, nivel, yy, color) => {
    const yl = Math.round(yy) + 0.5;
    const fuera = yl < g.arriba || yl > g.abajo;
    const x0 = Math.max(0, caja.x0);
    const x1 = Math.min(g.ancho, caja.x1);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.setLineDash(caja.discontinua ? [6, 4] : []);
    ctx.beginPath();
    ctx.moveTo(x0, yl);
    ctx.lineTo(x1, yl);
    ctx.stroke();
    ctx.setLineDash([]);
    let texto = null;
    if (!fuera && x1 - x0 > 60) {
      texto = nombre + ' ' + nivel;
      ctx.font = '9px ui-monospace, monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'bottom';
      ctx.fillStyle = color;
      ctx.fillText(texto, x1 - 3, yl - 1.5);
    }
    return { nivel, y: yl, texto, fuera };
  };
  if (p.poc !== null && p.poc !== undefined) r.poc = linea('POC', p.poc, y(Number(p.poc) + paso / 2), CAPA.poc);
  if (va) {
    r.vah = linea('VAH', va.vah, y(Number(va.vah) + paso), caja.color);
    r.val = linea('VAL', va.val, y(Number(va.val)), caja.color);
  }
  return r;
}

/* EL VWAP de una sesion y sus bandas, por los centros de las velas VISIBLES. */
function pintaVwap(ctx, g, y, m, s, xT, i0, i1) {
  const desde = Date.parse(m.velas[i0].ts);
  const hasta = Date.parse(m.velas[i1].ts);
  const puntos = (s.puntos || []).filter((p) => Date.parse(p.ts) >= desde && Date.parse(p.ts) <= hasta);
  if (!puntos.length) return null;
  const r = { puntos: [], texto: null };
  puntos.forEach((p) => {
    const x = xT(Date.parse(p.ts)) + g.bs / 2;
    const pt = { ts: p.ts, x: Math.round(x * 10) / 10, vwap: { valor: p.vwap, y: Math.round(y(Number(p.vwap)) * 10) / 10 },
                 bandas: {} };
    BANDAS_VWAP.forEach((k) => {
      const b = p.bandas[String(k)];
      pt.bandas[k] = { abajo: { valor: b[0], y: Math.round(y(Number(b[0])) * 10) / 10 },
                       arriba: { valor: b[1], y: Math.round(y(Number(b[1])) * 10) / 10 } };
    });
    r.puntos.push(pt);
  });
  const traza = (lado, alfa, discontinua) => {
    ctx.strokeStyle = CAPA.vwap;
    ctx.globalAlpha = alfa;
    ctx.lineWidth = discontinua ? 1 : 1.5;
    ctx.setLineDash(discontinua ? [4, 3] : []);
    ctx.beginPath();
    r.puntos.forEach((pt, i) => (i ? ctx.lineTo(pt.x, lado(pt).y) : ctx.moveTo(pt.x, lado(pt).y)));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
  };
  BANDAS_VWAP.forEach((k) => {
    traza((pt) => pt.bandas[k].abajo, BANDA_ALFA[k] * 0.6, true);
    traza((pt) => pt.bandas[k].arriba, BANDA_ALFA[k] * 0.6, true);
  });
  traza((pt) => pt.vwap, 1, false);
  const ult = r.puntos[r.puntos.length - 1];
  if (ult.vwap.y >= g.arriba && ult.vwap.y <= g.abajo) {
    r.texto = 'VWAP ' + ult.vwap.valor;
    ctx.font = '9px ui-monospace, monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = CAPA.vwap;
    ctx.fillText(r.texto, Math.min(g.ancho - 3, ult.x), ult.vwap.y - 2);
  }
  return r;
}

const BANDAS_VWAP = [1, 2, 3];

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { CAPA, pintaCapas };
}
