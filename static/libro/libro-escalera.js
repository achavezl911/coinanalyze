'use strict';
/* LA ESCALERA (campana 145, OF-4b; profesional en la campana 149, ronda A): el libro VIVO de la familia por nivel, en
 * una TABLA del DOM. Lo pintado es el propio DOM: cada fila lleva su nivel y sus cifras en data-* y su texto es lo que
 * se ve (K111 lee las dos cosas y las compara con lo servido).
 *
 * POR VENUE, su estado: `vivo`; `sin_libro` (el colector dice que su libro no es valido, y por que); `sin_dato` (la API
 * aun no lo ha oido); `rancio` (su ultimo aviso llego a la API hace mas de ESC_RANCIO_S). Solo los vivos suman: un
 * venue sin libro valido se dice con su motivo y NUNCA se pinta con su ultimo libro.
 * POR NIVEL (libro-calculo.js): la suma de los vivos que lo conocen, cuantos son de los N de la familia (la columna
 * n/N solo escribe cuando n < N), las mejores marcadas y la acumulada desde el medio («≥» si pasa por niveles que no
 * conocen todos), oculta salvo con ACUM. Lo que no conoce ninguno: celdas VACIAS, y un rotulo en la frontera.
 * COLUMNAS: @bid reciente | compra | precio | venta | @ask reciente | n/N. Las barras de compra y venta crecen hacia el
 * precio, en UNA escala (el p95 de lo visible); las grandes, con borde y negrita. Lo reciente sale de la cinta
 * (sumaReciente); la ultima operacion y el maximo y minimo de la sesion UTC se marcan en la columna del precio.
 * Las filas se REUTILIZAN: una por nivel, que se anaden y quitan por los extremos.
 */

const ESC_RANCIO_S = 10;
const ESC_FILA_DEF = 18;
const ESC_FILA_MIN = 14;
const ESC_FILA_MAX = 28;
const ESC_RECENTRA_FILAS = 10;
const ESC_DESTELLO_MS = 1000;
const ESC_CLASES = ['acum c', 'rec b', 'c', 'nivel', 'v', 'rec a', 'acum v', 'n'];
// lo que se escribe donde no hay dato: NADA (ni un cero, ni la palabra en cada celda)
const AUSENTE = '';
const SIN_CINTA = '';

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

function leeFila() {
  try {
    const n = Number(window.localStorage.getItem('libro.fila'));
    return n >= ESC_FILA_MIN && n <= ESC_FILA_MAX ? n : ESC_FILA_DEF;
  } catch (e) {
    return ESC_FILA_DEF;
  }
}

function guardaFila(n) {
  try {
    window.localStorage.setItem('libro.fila', String(n));
  } catch (e) {
    /* sin almacen (modo privado): se queda en esta pagina */
  }
}

function pon(td, t) {
  if (td._t !== t) {
    td._t = t;
    td.textContent = t;
  }
}

function dato(nodo, clave, v) {
  if (v === null || v === undefined) {
    if (clave in nodo.dataset) delete nodo.dataset[clave];
  } else if (nodo.dataset[clave] !== v) {
    nodo.dataset[clave] = v;
  }
}

function clase(nodo, c) {
  if (nodo.className !== c) nodo.className = c;
}

/* `opciones.pide()` pide un repintado; `opciones.limpia()` vacia lo reciente (el boton Limpiar). */
function creaEscalera(raiz, opciones) {
  const op = opciones || {};
  const cuerpo = raiz.querySelector('#esc-filas tbody');
  const cabezaT = raiz.querySelector('#esc-filas thead');
  const venuesT = raiz.querySelector('#esc-venues tbody');
  const cabeza = raiz.querySelector('#esc-cabeza');
  const caja = raiz.querySelector('.esc-tabla');
  const centro = raiz.querySelector('.esc-centro');
  const totalesD = raiz.querySelector('#esc-totales');
  const aviso = raiz.querySelector('#esc-aviso');
  const botonAcum = raiz.querySelector('#esc-acum');
  const porK = new Map();
  let cuadros = 0;
  let alto = leeFila();
  let encima = false;
  let centrar = true;
  let altoMedido = 0;  // la altura de fila que midio la pinta anterior: sincroniza no fuerza otro layout
  let vistaClave = null;
  let destello = null;
  raiz.style.setProperty('--fila', alto + 'px');
  const repinta = () => { if (op.pide) op.pide(); };

  caja.addEventListener('mouseenter', () => { encima = true; });
  caja.addEventListener('mouseleave', () => { encima = false; });
  caja.addEventListener('wheel', (e) => {
    e.preventDefault();
    const d = e.deltaY < 0 ? -1 : e.deltaY > 0 ? 1 : 0;
    if (!d) return;
    if (e.ctrlKey) {
      const n = Math.min(ESC_FILA_MAX, Math.max(ESC_FILA_MIN, alto - d));
      if (n === alto) return;
      alto = n;
      altoMedido = 0;
      guardaFila(n);
      raiz.style.setProperty('--fila', n + 'px');
      centrar = true;
    } else {
      const h = cuerpo.firstChild ? cuerpo.firstChild.getBoundingClientRect().height : alto;
      caja.scrollTop += d * h;
    }
    repinta();
  }, { passive: false });
  if (botonAcum) {
    botonAcum.addEventListener('click', () => {
      const si = raiz.classList.toggle('con-acum');
      botonAcum.setAttribute('aria-pressed', si ? 'true' : 'false');
      repinta();
    });
  }
  const boton = (id, f) => {
    const b = raiz.querySelector(id);
    if (b) b.addEventListener('click', () => { f(); repinta(); });
  };
  boton('#esc-centrar', () => { centrar = true; });
  boton('#esc-limpiar', () => { if (op.limpia) op.limpia(); });
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || (e.key !== 'c' && e.key !== 'C')) return;
    const t = e.target && e.target.tagName;
    if (t === 'INPUT' || t === 'SELECT' || t === 'TEXTAREA') return;
    centrar = true;
    repinta();
  });

  function celda(tr, cl, texto) {
    const td = el('td', cl, texto);
    tr.appendChild(td);
    return td;
  }

  function nueva(k) {
    const tr = el('tr');
    tr._c = ESC_CLASES.map((c) => { const td = celda(tr, c, ''); td._t = ''; return td; });
    tr._k = k;
    porK.set(k, tr);
    return tr;
  }

  /* Deja en el cuerpo una fila por nivel de kTop a kBot (de arriba abajo), quitando y anadiendo por los extremos y
   * compensando el desplazamiento para que lo que se ve no salte. Devuelve true si tuvo que rehacerlo entero. */
  function sincroniza(kTop, kBot) {
    const primero = cuerpo.firstChild;
    if (!primero || primero._k < kBot || cuerpo.lastChild._k > kTop) {
      vaciar(cuerpo);
      porK.clear();
      for (let k = kTop; k >= kBot; k--) cuerpo.appendChild(nueva(k));
      return true;
    }
    const h = altoMedido || alto;
    let mueve = 0;
    while (cuerpo.firstChild._k > kTop) {
      porK.delete(cuerpo.firstChild._k);
      cuerpo.removeChild(cuerpo.firstChild);
      mueve -= h;
    }
    while (cuerpo.lastChild._k < kBot) {
      porK.delete(cuerpo.lastChild._k);
      cuerpo.removeChild(cuerpo.lastChild);
    }
    for (let k = cuerpo.firstChild._k + 1; k <= kTop; k++) {
      cuerpo.insertBefore(nueva(k), cuerpo.firstChild);
      mueve += h;
    }
    for (let k = cuerpo.lastChild._k - 1; k >= kBot; k--) cuerpo.appendChild(nueva(k));
    if (mueve) caja.scrollTop += mueve;
    return false;
  }

  function vaciaRec(tr) {
    tr._nb = 0;
    tr._na = 0;
  }

  /* Pinta y devuelve el contrato: `vista` (activo, familia, paso, unidad, hasta), `venues` de la familia, `libros` por
   * venue ({ m, llegadaMs }), `canal` (lo que dice el vivo), `extra` = { rec (sumaReciente), cinta ('ok' | 'pendiente' |
   * 'caida' | 'fija'), motivo (por que esta caida), perfil ({ dia, niveles } de /api/orderflow/perfil, o null) }. */
  function pinta(vista, venues, libros, canal, ahoraMs, extra) {
    const t0 = performance.now();
    const x = extra || {};
    const P = vista.paso;
    const M = modeloEscalera(venues, libros, P, vista.unidad, ahoraMs);
    const s = M.suma;
    const N = venues.length;
    const clave = [vista.activo, vista.familia, P, vista.unidad, vista.hasta || ''].join('|');
    if (clave !== vistaClave) {
      vistaClave = clave;
      centrar = true;
    }
    const cinta = x.cinta || 'pendiente';
    const rec = x.rec || null;
    const recOk = cinta === 'ok' && !!rec && rec.primado;
    const ultima = recOk && rec.ultima ? rec.ultima : null;
    const ext = cinta === 'fija' ? null : extremosSesion(x.perfil || null, rec, P);
    if (!destello) destello = getComputedStyle(raiz).getPropertyValue('--esc-destello').trim() || 'rgba(242, 204, 96, 0.45)';

    const modelo = new Map();
    if (s) {
      if (sincroniza(s.hi + 1, s.lo - 1)) centrar = true;
      M.filas.forEach((f) => modelo.set(f.k, f));
      modelo.set(s.hi + 1, { k: s.hi + 1, n: 0, frontera: 'arriba' });
      modelo.set(s.lo - 1, { k: s.lo - 1, n: 0, frontera: 'abajo' });
    } else {
      vaciar(cuerpo);
      porK.clear();
    }

    const acum = (q, parcial) => (q === null || q === undefined ? '' : (parcial ? '≥' : '') + cifra(q));
    porK.forEach((tr, k) => {
      const f = modelo.get(k);
      const c = tr._c;
      clase(tr, [f.mejor_compra ? 'mejor-compra' : '', f.mejor_venta ? 'mejor-venta' : '',
        !f.n ? 'desconocido' : f.n < f.N ? 'parcial' : '', f.frontera ? 'frontera' : ''].filter(Boolean).join(' '));
      dato(tr, 'k', String(k));
      dato(tr, 'nivel', nivelTexto(k, P));
      dato(tr, 'n', String(f.n));
      dato(tr, 'compra', f.n ? String(f.compra) : null);
      dato(tr, 'venta', f.n ? String(f.venta) : null);
      dato(tr, 'acumCompra', f.n && f.acum_compra !== null ? String(f.acum_compra) : null);
      dato(tr, 'acumVenta', f.n && f.acum_venta !== null ? String(f.acum_venta) : null);
      pon(c[0], f.n ? acum(f.acum_compra, f.acum_parcial_compra) : '');
      pon(c[2], f.n ? cifra(f.compra) : AUSENTE);
      pon(c[3], nivelTexto(k, P));
      pon(c[4], f.n ? cifra(f.venta) : AUSENTE);
      pon(c[6], f.n ? acum(f.acum_venta, f.acum_parcial_venta) : '');
      pon(c[7], f.n ? (f.n < f.N ? f.n + '/' + f.N : '') : '0/' + N);
      dato(c[4], 'rotulo', f.frontera === 'arriba' ? 'desconocido ↑' : null);
      dato(c[2], 'rotulo', f.frontera === 'abajo' ? 'desconocido ↓' : null);
      // lo reciente @bid / @ask de este nivel, y un destello cuando entra una operacion nueva
      const r = recOk ? recienteEn(rec, k, vista.unidad) : null;
      const nr = recOk ? rec.niveles.get(k) : null;
      [[c[1], 0, 'nb', '_nb'], [c[5], 1, 'na', '_na']].forEach(([td, i, cuenta, mio]) => {
        dato(td, 'rec', r ? String(r[i]) : null);
        pon(td, r ? (r[i] > 0 ? cifra(r[i]) : '') : recOk ? '' : SIN_CINTA);
        const nn = nr ? nr[cuenta] : 0;
        if (tr[mio] !== undefined && nn > tr[mio] && td.animate) {
          td.animate([{ backgroundColor: destello }, { backgroundColor: 'transparent' }], { duration: ESC_DESTELLO_MS });
        }
        tr[mio] = nn;
      });
      if (!recOk) vaciaRec(tr);
      const esUlt = !!ultima && ultima.k === k;
      clase(c[3], ['nivel', esUlt ? 'ultima' : '', ext && ext.hi === k ? 'max-sesion' : '',
        ext && ext.lo === k ? 'min-sesion' : ''].filter(Boolean).join(' '));
      dato(c[3], 'ultima', esUlt ? cifra(vista.unidad === 'usd' ? ultima.usd : ultima.base) : null);
      dato(c[3], 'agresor', esUlt ? ultima.agresor : null);
    });

    // recentrado: el nivel del precio (la ultima operacion; si no, la mejor compra) a 10 filas o mas del centro
    const cajaR = caja.getBoundingClientRect();
    const arriba = cajaR.top + caja.clientTop;
    const thH = cabezaT ? cabezaT.getBoundingClientRect().height : 0;
    const zonaC = thH + (caja.clientHeight - thH) / 2;
    if (centro) {
      const top = Math.round(zonaC) + 'px';
      if (centro.style.top !== top) centro.style.top = top;
    }
    let kPrecio = null;
    if (s) {
      kPrecio = ultima && porK.has(ultima.k) ? ultima.k : Math.floor(Number(s.mejorCompra) / Number(P) + 1e-9);
      const tr = porK.get(kPrecio);
      if (tr) {
        const r = tr.getBoundingClientRect();
        altoMedido = r.height;
        const dist = (r.top + r.bottom) / 2 - arriba - zonaC;
        if (centrar || (!encima && Math.abs(dist) >= ESC_RECENTRA_FILAS * r.height)) caja.scrollTop += dist;
      }
      centrar = false;
    }

    // las filas VISIBLES (su centro dentro de la caja, bajo la cabecera fija): de ellas salen el tope, las grandes y
    // los totales
    const vis = [];
    const lim0 = arriba + thH;
    const lim1 = arriba + caja.clientHeight;
    porK.forEach((tr, k) => {
      const r = tr.getBoundingClientRect();
      const m = (r.top + r.bottom) / 2;
      if (m > lim0 && m < lim1) vis.push(modelo.get(k));
    });
    const med = medidasVisibles(vis);
    porK.forEach((tr, k) => {
      const f = modelo.get(k);
      [[tr._c[2], f.compra, med.media_compra], [tr._c[4], f.venta, med.media_venta]].forEach(([td, q, media]) => {
        const fr = f.n ? fraccionBarra(q, med.tope) : null;
        dato(td, 'barra', fr === null ? null : String(fr));
        if (td._f !== fr) {
          td._f = fr;
          if (fr === null) td.style.removeProperty('--f');
          else td.style.setProperty('--f', String(fr));
        }
        const g = !!f.n && esGrande(q, media);
        if (td.classList.contains('grande') !== g) td.classList.toggle('grande', g);
      });
    });

    let tot = null;
    if (s) {
      tot = totalesVisibles(vis, s.mejorCompra, s.mejorVenta);
    }
    if (totalesD) {
      dato(totalesD, 'filas', tot ? String(tot.filas) : null);
      dato(totalesD, 'compra', tot && tot.compra !== null ? String(tot.compra) : null);
      dato(totalesD, 'venta', tot && tot.venta !== null ? String(tot.venta) : null);
      dato(totalesD, 'pct', tot && tot.pct_compra !== null ? String(tot.pct_compra) : null);
      dato(totalesD, 'spread', tot && tot.spread !== null ? tot.spread : null);
      const txt = !tot ? 'sin libro vivo: no hay totales'
        : !tot.filas ? 'ninguna fila visible conocida · spread ' + tot.spread
          : 'visible: compra ' + cifra(tot.compra) + ' · venta ' + cifra(tot.venta)
            + (tot.pct_compra === null ? '' : ' · ' + tot.pct_compra.toFixed(1) + ' % compra') + ' · spread ' + tot.spread;
      if (totalesD.textContent !== txt) totalesD.textContent = txt;
    }

    if (aviso) {
      const partes = [];
      if (cinta === 'fija') partes.push('vista fija: el volumen reciente solo se cuenta en vivo');
      else if (cinta === 'caida') partes.push('la cinta no contesta (' + (x.motivo || 'sin motivo') + '): @bid y @ask sin dato');
      else if (!recOk) partes.push('volumen reciente: esperando la cinta');
      else partes.push('reciente desde ' + (rec.corte ? new Date(rec.corte).toISOString().slice(11, 19) + 'Z' : 'ahora'));
      if (rec && rec.falta && cinta !== 'fija') {
        partes.push(rec.falta.motivo === 'truncada' ? 'FALTAN OPERACIONES: una página truncada no solapa con la anterior'
          : 'FALTAN OPERACIONES: pasó más de un minuto entre dos páginas');
      }
      if (ext) {
        partes.push('sesión UTC máx ' + nivelTexto(ext.hi, P) + ' · mín ' + nivelTexto(ext.lo, P)
          + (ext.de_perfil ? '' : ' (solo la cinta: sin perfil)'));
      }
      if (ultima) {
        partes.push('última ' + (ultima.agresor || '?') + ' '
          + cifra(vista.unidad === 'usd' ? ultima.usd : ultima.base) + ' @ ' + ultima.precio + ' ' + ultima.venue);
      }
      const txt = partes.join(' · ');
      if (aviso.textContent !== txt) aviso.textContent = txt;
      dato(aviso, 'cinta', cinta);
      dato(aviso, 'falta', rec && rec.falta && cinta !== 'fija' ? rec.falta.motivo : null);
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

    const reciente = {};
    if (recOk) rec.niveles.forEach((_, k) => { reciente[k] = recienteEn(rec, k, vista.unidad); });
    const reg = { cuadro: ++cuadros, ahora_ms: ahoraMs, canal, activo: vista.activo, familia: vista.familia,
                  paso: vista.paso, unidad: vista.unidad, N, venues: M.venues,
                  mejor_compra: s ? s.mejorCompra : null, mejor_venta: s ? s.mejorVenta : null,
                  filas: cuerpo.children.length, fila: alto, tope: med.tope, media_compra: med.media_compra,
                  media_venta: med.media_venta, visibles: vis.map((f) => f.k), precio_k: kPrecio,
                  ultima: ultima ? { k: ultima.k, ts: ultima.ts, venue: ultima.venue, id: ultima.id, precio: ultima.precio,
                                     base: ultima.base, usd: ultima.usd, agresor: ultima.agresor } : null,
                  reciente, cinta, cinta_motivo: x.motivo || null,
                  falta_cinta: rec && rec.falta && cinta !== 'fija' ? rec.falta.motivo : null,
                  totales: tot, extremos: ext };
    reg.ms = performance.now() - t0;
    return reg;
  }

  return { pinta };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ESC_RANCIO_S, ESC_FILA_DEF, ESC_RECENTRA_FILAS, estadoVenue, modeloEscalera };
}
