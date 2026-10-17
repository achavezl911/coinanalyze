'use strict';
/* EL TPO · el perfil de mercado (campana 143, OF-3): la otra vista de /flujo (`#.../modo=tpo`), en su propio lienzo.
 * ---------------------------------------------------------------------------
 * Una columna por sesion (la ultima a la derecha). En cada fila (un nivel al paso del TPO), una letra por cada periodo
 * de 30 min que TOCO ese nivel, en orden: A es la primera media hora de la sesion. Las letras de un periodo con minutos
 * sin escuchar enteros van en ambar. A la izquierda de la columna, la value area del 70 % de los TPO (azul) y el
 * balance inicial (verde: la primera hora); el POC, un marco en su fila; los single prints, una marca naranja a la
 * derecha. Todo SERVIDO por /api/orderflow/tpo y pintado tal cual.
 *
 * Las filas tienen ALTO FIJO (rueda: mas o menos alto; arrastre: moverse en precio y entre sesiones): con 9 px o mas se
 * escriben las letras; por debajo, cada TPO es un bloque de su color.
 *
 * EL CONTRATO (lo lee K109): `window.FLUJO_TPO`, apuntado donde se dibuja: la escala, y por sesion su columna, su estado
 * y su marca, POC, value area, balance inicial y single prints con sus filas, y por fila su nivel, sus y, las letras
 * servidas y el TEXTO que se escribio letra a letra (null si no se escribio). */

const TPO = { FILA: 12, LETRA: 7, EJE_P: 76, CABEZA: 34, MARGEN: 18, TEXTO_MIN: 9, ANCHO_MIN: 150 };

function creaLienzoTPO(canvas) {
  const L = { cv: canvas, ctx: canvas.getContext('2d'), pr: window.devicePixelRatio || 1, W: 0, H: 0, modelo: null,
              fila: TPO.FILA, centro: null, dx: 0, arrastre: null, pendiente: false, cuadros: 0 };

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

  function pinta() {
    const ctx = L.ctx;
    ctx.setTransform(L.pr, 0, 0, L.pr, 0, 0);
    ctx.fillStyle = COLOR.fondo;
    ctx.fillRect(0, 0, L.W, L.H);
    const reg = { cuadro: ++L.cuadros, ancho: L.W, alto: L.H, sesiones: [] };
    const m = L.modelo;
    if (!m || !m.sesiones.length) {
      window.FLUJO_TPO = reg;
      return;
    }
    const p = Number(m.paso);
    const medio = TPO.CABEZA + (L.H - TPO.CABEZA) / 2;
    const y = (n) => medio - ((n - L.centro) / p) * L.fila;
    const ancho = L.W - TPO.EJE_P;
    Object.assign(reg, { activo: m.activo, familia: m.familia, venues: m.venues, paso: m.paso, sesion: m.sesion,
                         escala: { centro: L.centro, fila: L.fila, medio, cabeza: TPO.CABEZA } });
    // la rejilla y el eje de precios: una etiqueta cada k filas, las que dejen >= 28 px entre dos
    const k = Math.max(1, Math.ceil(28 / L.fila));
    const dec = (String(m.paso).split('.')[1] || '').length;
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const arriba = L.centro + ((medio - TPO.CABEZA) / L.fila) * p;
    for (let j = Math.ceil(arriba / (p * k)); y(j * p * k) <= L.H; j--) {
      const n = j * p * k;
      const yy = Math.round(y(n + p / 2)) + 0.5;
      if (yy < TPO.CABEZA) continue;
      ctx.strokeStyle = COLOR.rejilla;
      ctx.beginPath();
      ctx.moveTo(0, yy);
      ctx.lineTo(ancho, yy);
      ctx.stroke();
      ctx.fillStyle = COLOR.eje;
      ctx.fillText(n.toFixed(dec), ancho + 6, yy);
    }
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, ancho, L.H);
    ctx.clip();
    let x1 = ancho - TPO.MARGEN + L.dx;
    for (let i = m.sesiones.length - 1; i >= 0; i--) {
      const s = m.sesiones[i];
      const maxTpo = s.niveles.reduce((a, l) => Math.max(a, l.tpo), 0);
      const w = Math.max(TPO.ANCHO_MIN, 16 + maxTpo * TPO.LETRA);
      const x0 = x1 - w;
      if (x1 > 0 && x0 < ancho) reg.sesiones.push(pintaSesion(ctx, s, x0, x1, y, p, m));
      x1 = x0 - TPO.MARGEN;
    }
    ctx.restore();
    window.FLUJO_TPO = reg;
  }

  /* UNA SESION: lo que se dibuja y, en el mismo sitio, lo que se apunta. */
  function pintaSesion(ctx, s, x0, x1, y, p, m) {
    const st = estadoSesion(s);
    const r = Object.assign({ inicio: s.inicio, fin: s.fin, corte: s.corte, x0: Math.round(x0), x1: Math.round(x1),
                              marca: null, titulo: null, poc: null, va: null, ib: null, single: [], filas: [] }, st);
    const fila = (n) => ({ y0: Math.round(y(n + p)), y1: Math.round(y(n)) });
    // la cabecera: el dia y la hora de inicio, y su estado (en curso, hueco, faltan N/M)
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = COLOR.texto;
    r.titulo = s.inicio.slice(5, 10) + ' ' + s.inicio.slice(11, 16) + 'Z';
    ctx.fillText(r.titulo, x0 + 4, 9);
    const marca = marcaCapa(st);
    if (marca) {
      ctx.font = '9px ui-monospace, monospace';
      ctx.fillStyle = st.estado === 'completa' ? COLOR.mudo : COLOR.ambar;
      ctx.fillText(marca, x0 + 4, 23);
      r.marca = marca;
    }
    if (st.estado === 'hueco') {
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = COLOR.mudo;
      ctx.strokeRect(x0 + 0.5, TPO.CABEZA + 0.5, x1 - x0 - 1, L.H - TPO.CABEZA - 1);
      ctx.setLineDash([]);
    }
    const incompletos = new Set(s.periodos.filter((q) => q.cobertura.minutos_esperados > 0 && !q.cobertura.completa)
      .map((q) => q.letra));
    const conTexto = L.fila >= TPO.TEXTO_MIN;
    // la value area y el balance inicial: barras a la izquierda de la columna
    if (s.value_area) {
      const a = fila(Number(s.value_area.vah));
      const b = fila(Number(s.value_area.val));
      ctx.fillStyle = COLOR.va;
      ctx.fillRect(x0 + 1, a.y0, 2, b.y1 - a.y0);
      r.va = { val: s.value_area.val, vah: s.value_area.vah, y0: a.y0, y1: b.y1 };
    }
    if (s.balance_inicial) {
      const a = fila(Number(s.balance_inicial.hi));
      const b = fila(Number(s.balance_inicial.lo));
      ctx.fillStyle = rgba(COLOR.compra, 0.9);
      ctx.fillRect(x0 + 5, a.y0, 2, b.y1 - a.y0);
      r.ib = { lo: s.balance_inicial.lo, hi: s.balance_inicial.hi, y0: a.y0, y1: b.y1 };
    }
    s.single_prints.forEach((t) => {
      const a = fila(Number(t.hasta));
      const b = fila(Number(t.desde));
      ctx.fillStyle = '#ff9f43';
      ctx.fillRect(x1 - 4, a.y0, 2, b.y1 - a.y0);
      r.single.push({ desde: t.desde, hasta: t.hasta, extremo: t.extremo, y0: a.y0, y1: b.y1 });
    });
    // las filas: una letra por cada periodo que toco el nivel
    s.niveles.forEach((l) => {
      const f = fila(Number(l.nivel));
      const apunte = { nivel: l.nivel, y0: f.y0, y1: f.y1, letras: l.letras, texto: null,
                       fuera: f.y1 <= TPO.CABEZA || f.y0 >= L.H };
      if (!apunte.fuera) {
        const ym = (f.y0 + f.y1) / 2;
        ctx.font = '10px ui-monospace, monospace';
        ctx.textAlign = 'left';
        let texto = '';
        for (let i = 0; i < l.letras.length; i++) {
          const letra = l.letras[i];
          const xl = x0 + 10 + i * TPO.LETRA;
          ctx.fillStyle = incompletos.has(letra) ? COLOR.ambar : COLOR.texto;
          if (conTexto) {
            ctx.fillText(letra, xl, ym);
            texto += letra;
          } else {
            ctx.globalAlpha = 0.7;
            ctx.fillRect(xl, f.y0, TPO.LETRA - 1, Math.max(1, f.y1 - f.y0 - 1));
            ctx.globalAlpha = 1;
          }
        }
        if (conTexto) apunte.texto = texto;
      }
      r.filas.push(apunte);
    });
    if (s.poc !== null && s.poc !== undefined) {
      const f = fila(Number(s.poc));
      const l = s.niveles.find((x) => x.nivel === s.poc);
      ctx.strokeStyle = COLOR.poc;
      ctx.strokeRect(x0 + 8.5, f.y0 + 0.5, 4 + (l ? l.tpo : 1) * TPO.LETRA, Math.max(1, f.y1 - f.y0 - 1));
      r.poc = { nivel: s.poc, y0: f.y0, y1: f.y1 };
    }
    return r;
  }

  L.cv.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    L.fila = Math.min(22, Math.max(4, L.fila * (ev.deltaY > 0 ? 1 / 1.15 : 1.15)));
    pide();
  }, { passive: false });
  L.cv.addEventListener('mousedown', (ev) => {
    L.arrastre = { x: ev.clientX, y: ev.clientY, centro: L.centro, dx: L.dx };
  });
  window.addEventListener('mouseup', () => {
    L.arrastre = null;
  });
  L.cv.addEventListener('mousemove', (ev) => {
    if (!L.arrastre || !L.modelo) return;
    L.dx = L.arrastre.dx + (ev.clientX - L.arrastre.x);
    L.centro = L.arrastre.centro + ((ev.clientY - L.arrastre.y) / L.fila) * Number(L.modelo.paso);
    pide();
  });
  new ResizeObserver(() => {
    mide();
    pide();
  }).observe(L.cv.parentElement);
  mide();

  return {
    /* una vista nueva se centra en el POC de la ultima sesion con TPO; el latido de la misma vista no mueve nada */
    pon(modelo) {
      const nueva = !L.modelo || L.modelo.clave !== modelo.clave;
      L.modelo = modelo;
      if (nueva || L.centro === null) {
        const ult = modelo.sesiones.slice().reverse().find((s) => s.poc !== null && s.poc !== undefined);
        L.centro = ult ? Number(ult.poc) : 0;
        L.dx = 0;
      }
      pide();
    },
    pinta,
    pide,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { TPO, creaLienzoTPO };
}
