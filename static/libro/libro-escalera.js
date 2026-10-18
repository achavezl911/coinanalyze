'use strict';
/* LA ESCALERA (campana 145, OF-4b): el libro VIVO de la familia por nivel, en una TABLA del DOM. Lo pintado es el
 * propio DOM: cada fila lleva su nivel y sus cifras en data-* y su texto es lo que se ve (K111 lee las dos cosas y
 * las compara con lo servido).
 *
 * POR VENUE, su estado: `vivo`; `sin_libro` (el colector dice que su libro no es valido, y por que); `sin_dato` (la API
 * aun no lo ha oido); `rancio` (su ultimo aviso llego a la API hace mas de ESC_RANCIO_S). Solo los vivos suman: un
 * venue sin libro valido se dice con su motivo y NUNCA se pinta con su ultimo libro.
 * POR NIVEL (libro-calculo.js): la suma de los vivos que lo conocen, cuantos son de los N de la familia, las mejores
 * marcadas y la acumulada desde el medio («≥» si pasa por niveles que no conocen todos; se corta donde no lo conoce
 * ninguno). Mas alla de lo que conoce alguno, una fila DESCONOCIDO a cada lado.
 */

const ESC_RANCIO_S = 10;

/* El estado de un venue a partir de su ultimo mensaje (`m`, el del websocket o el de /api/libro/ultimo) y de cuando
 * llego ese aviso a la API (`llegadaMs`, en el reloj de esta pagina). */
function estadoVenue(x, ahoraMs) {
  if (!x || !x.m) return { estado: 'sin_dato', motivo: 'todavía no ha llegado ningún aviso de este venue' };
  if (x.m.tipo === 'sin_dato') return { estado: 'sin_dato', motivo: x.m.motivo };
  if (x.m.tipo === 'sin_libro') return { estado: 'sin_libro', motivo: x.m.motivo };
  const edad = (ahoraMs - x.llegadaMs) / 1000;
  if (edad > ESC_RANCIO_S) return { estado: 'rancio', motivo: 'su último aviso llegó hace ' + Math.round(edad) + ' s' };
  return { estado: 'vivo', motivo: null };
}

function horaMs(ms) {
  return ms ? new Date(ms).toISOString().slice(11, 23) + 'Z' : '—';
}

/* Lo que se calcula de la escalera: los venues con su estado y la familia de los vivos (sin tocar el DOM). */
function modeloEscalera(venues, libros, paso, unidad, ahoraMs) {
  const vivos = [];
  const filasVenue = venues.map((v) => {
    const x = libros[v];
    const st = estadoVenue(x, ahoraMs);
    const m = x && x.m;
    const L = st.estado === 'vivo' ? libroDe(v, m.compra, m.venta, m.compras, m.ventas, paso) : null;
    if (L) vivos.push(L);
    return Object.assign({ venue: v }, st, {
      emitido_ms: m ? m.emitido_ms || null : null, api_ms: m ? m.api_ms || null : null, foto: m ? m.foto || null : null,
      ts_libro_ms: m && m.tipo === 'libro' ? m.ts_libro_ms : null,
      compra: m && m.tipo === 'libro' ? m.compra : null, venta: m && m.tipo === 'libro' ? m.venta : null,
      // cuantos niveles CONOCE cada lado al paso de la pantalla: de la mejor hacia fuera (kc / kv del relevo)
      conoce_compra: L ? L.qc.length : null, conoce_venta: L ? L.qv.length : null,
    });
  });
  const suma = sumaFamilia(vivos, venues.length);
  return { venues: filasVenue, suma, filas: escaleraFamilia(suma, paso, unidad) };
}

function creaEscalera(raiz) {
  const cuerpo = raiz.querySelector('#esc-filas tbody');
  const venuesT = raiz.querySelector('#esc-venues tbody');
  const cabeza = raiz.querySelector('#esc-cabeza');
  const caja = raiz.querySelector('.esc-tabla');
  let cuadros = 0;
  let tocado = 0;
  caja.addEventListener('scroll', () => { tocado = Date.now(); }, { passive: true });

  function celda(tr, clase, texto) {
    const td = el('td', clase, texto);
    tr.appendChild(td);
    return td;
  }

  /* Pinta y devuelve el contrato: `vista` (activo, familia, paso, unidad), `venues` de la familia, `libros` por venue
   * ({ m, llegadaMs }), `canal` (lo que dice el vivo). */
  function pinta(vista, venues, libros, canal, ahoraMs) {
    const M = modeloEscalera(venues, libros, vista.paso, vista.unidad, ahoraMs);
    const s = M.suma;
    vaciar(cuerpo);
    const desconocida = (k) => {
      const tr = el('tr', 'desconocido');
      tr.dataset.k = String(k);
      tr.dataset.nivel = nivelTexto(k, vista.paso);
      tr.dataset.n = '0';
      ['acum c', 'c'].forEach((c) => celda(tr, c, ''));
      celda(tr, 'nivel', nivelTexto(k, vista.paso));
      celda(tr, 'v', 'desconocido');
      celda(tr, 'acum v', '');
      celda(tr, 'n', '0/' + venues.length);
      cuerpo.appendChild(tr);
    };
    if (s) {
      desconocida(s.hi + 1);
      M.filas.forEach((f) => {
        const tr = el('tr', [f.mejor_compra ? 'mejor-compra' : '', f.mejor_venta ? 'mejor-venta' : '',
          !f.n ? 'desconocido' : f.n < f.N ? 'parcial' : ''].filter(Boolean).join(' ') || null);
        const d = tr.dataset;
        d.k = String(f.k);
        d.nivel = f.nivel;
        d.n = String(f.n);
        if (f.n) {
          d.compra = String(f.compra);
          d.venta = String(f.venta);
        }
        if (f.acum_compra !== null) d.acumCompra = String(f.acum_compra);
        if (f.acum_venta !== null) d.acumVenta = String(f.acum_venta);
        const acum = (q, parcial) => (q === null ? '' : (parcial ? '≥' : '') + cifra(q));
        celda(tr, 'acum c', acum(f.acum_compra, f.acum_parcial_compra));
        celda(tr, 'c', f.n ? cifra(f.compra) : 'desconocido');
        celda(tr, 'nivel', f.nivel);
        celda(tr, 'v', f.n ? cifra(f.venta) : 'desconocido');
        celda(tr, 'acum v', acum(f.acum_venta, f.acum_parcial_venta));
        celda(tr, 'n', f.n + '/' + f.N);
        cuerpo.appendChild(tr);
      });
      desconocida(s.lo - 1);
    }
    vaciar(venuesT);
    M.venues.forEach((f) => {
      const tr = el('tr');
      tr.dataset.venue = f.venue;
      tr.dataset.estado = f.estado;
      celda(tr, null, f.venue);
      const e = celda(tr, f.estado, f.estado === 'vivo' ? 'vivo' : f.estado.replace('_', ' ') + ': ' + f.motivo);
      e.title = f.motivo || '';
      celda(tr, null, horaMs(f.ts_libro_ms));
      celda(tr, null, f.conoce_compra === null ? '—' : 'c ' + f.conoce_compra + ' · v ' + f.conoce_venta);
      venuesT.appendChild(tr);
    });
    vaciar(cabeza);
    const linea = (...trozos) => {
      const p = el('div');
      trozos.forEach((t) => p.appendChild(typeof t === 'string' ? document.createTextNode(t) : t));
      cabeza.appendChild(p);
    };
    if (s) {
      const quien = (campo, valor) => M.venues.filter((f) => f.estado === 'vivo' && f[campo] === valor)
        .map((f) => f.venue).join(', ');
      const bps = ((Number(s.mejorVenta) - Number(s.mejorCompra)) / Number(s.mejorCompra)) * 1e4;
      linea(el('b', null, 'mejor compra ' + s.mejorCompra), ' (' + quien('compra', s.mejorCompra) + ') · ',
        el('b', null, 'mejor venta ' + s.mejorVenta), ' (' + quien('venta', s.mejorVenta) + ') · '
          + (bps < 0 ? 'cruzado entre venues ' : 'diferencia ') + bps.toFixed(2) + ' bps');
      linea(s.venues.length + ' de ' + venues.length + ' venues vivos · paso ' + vista.paso + ' · '
        + (vista.unidad === 'usd' ? 'en USD (al centro de cada nivel)' : 'en ' + vista.activo));
    } else {
      linea(noSe('ausente', 'ningún venue de la familia tiene un libro vivo ahora mismo'));
    }
    if (!tocado || Date.now() - tocado > 10000) {
      const mejor = cuerpo.querySelector('tr.mejor-compra');
      if (mejor) caja.scrollTop = mejor.offsetTop - caja.clientHeight / 2;
    }
    const reg = { cuadro: ++cuadros, ahora_ms: ahoraMs, canal, activo: vista.activo, familia: vista.familia,
                  paso: vista.paso, unidad: vista.unidad, N: venues.length, venues: M.venues,
                  mejor_compra: s ? s.mejorCompra : null, mejor_venta: s ? s.mejorVenta : null,
                  filas: cuerpo.children.length };
    return reg;
  }

  return { pinta };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ESC_RANCIO_S, estadoVenue, modeloEscalera };
}
