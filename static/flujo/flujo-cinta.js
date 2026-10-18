'use strict';
/* LA CINTA a la derecha del footprint (campana 146, OF-5a): las ORDENES DE MERCADO AGREGADAS de la familia.
 * ---------------------------------------------------------------------------
 * LA ORDEN AGREGADA (P2 de la campana): las operaciones del mismo venue, el mismo milisegundo y el mismo lado del
 * agresor. Contra la verdad de suelo (taker_order_id de Coinbase, seq de Bybit, starbase_timestamp de Deribit) ninguna
 * orden de verdad abarca mas de un milisegundo. La agrega el SERVIDOR (/api/orderflow/ordenes) antes de filtrar: una
 * orden de 50 operaciones pequenas pasa el filtro si su suma lo pasa.
 *
 * EL FILTRO por omision, por activo, es el de P2: el menor escalon 1-2-5 con el que el minuto mediano de una hora real
 * de los perpetuos da <= 20 ordenes (BTC 200 000, ETH 200 000, SOL 50 000 USD; un domingo: un laborable da mas).
 *
 * EL VIVO PIDE SOLO LO NUEVO: cada CINTA_VIVO_S, (desde, hasta] con desde = el hasta servido la vez anterior; el
 * servidor sirve hasta «ahora - 8 s» para que la orden no salga partida. Una ventana fija (`hasta=` en el hash) pide
 * una vez lo de la hora anterior a su final.
 *
 * Es una tabla del DOM: lo pintado es el propio DOM (texto y data-* de cada fila), como la escalera del libro. */

const CINTA_FILTRO = { BTC: '200000', ETH: '200000', SOL: '50000' };
const CINTA_VIVO_S = 2;
const CINTA_FILAS = 200;
const RUTA_ORDENES = '/api/orderflow/ordenes';
const CINTA_VENUE = { binance_usdm: 'BIN-F', bybit_linear: 'BYB-F', okx_swap: 'OKX-F', bitget_usdt: 'BGT-F',
                      binance_spot: 'BIN-S', bybit_spot: 'BYB-S', okx_spot: 'OKX-S', coinbase_spot: 'CB',
                      deribit_perp: 'DRB' };
const CINTA = { pide: 0, filas: [], hasta: null, fallo: null, latido: null, vista: null, ultimaMs: 0, pidiendo: false,
                aplicadas: [] };

function filtroCinta(e) {
  return e.cinta || CINTA_FILTRO[e.activo];
}

function horaMs(iso) {
  return iso.slice(11, 23);
}

/* El precio que se escribe: hasta donde llego la orden en el sentido de su agresor (la compra, su precio mas alto; la
 * venta, el mas bajo) y una flecha si barrio mas de un precio. El rango entero va en el title y en los data-*. */
function precioCinta(o) {
  const p = o.agresor === 'compra' ? o.precio_max : o.precio_min;
  return o.precio_min === o.precio_max ? p : p + (o.agresor === 'compra' ? '↑' : '↓');
}

/* ------------------------------------------------------------- el DOM */
function pintaCinta() {
  const caja = document.getElementById('cinta');
  if (!caja || caja.hidden) return;
  const e = CINTA.vista;
  const fam = FAMILIAS[e.familia];
  const filtro = filtroCinta(e);
  const cab = vaciar(document.getElementById('cinta-fuente'));
  cab.appendChild(document.createTextNode('órdenes agregadas · ' + fam.rotulo + ' (' + fam.venues.join(', ') + ') · '
    + 'mismo venue, milisegundo y lado · ≥ ' + Number(filtro).toLocaleString('es-ES') + ' USD'));
  const est = vaciar(document.getElementById('cinta-estado'));
  let texto;
  if (CINTA.fallo) {
    est.appendChild(noSe('error', 'HTTP ' + CINTA.fallo.http + ' · ' + (CINTA.fallo.motivo || '')));
    texto = null;
  } else if (e.hasta) {
    texto = 'ventana fija: la hora anterior a ' + e.hasta.slice(11, 16) + 'Z (la cinta se guarda 48 h)';
  } else {
    texto = 'vivo: pide lo nuevo cada ' + CINTA_VIVO_S + ' s, hasta 8 s antes de ahora' + (CINTA.hasta
      ? ' · servido hasta ' + horaMs(CINTA.hasta) + 'Z' : '');
  }
  if (texto) est.appendChild(document.createTextNode(texto));
  est.setAttribute('data-estado', CINTA.fallo ? 'error' : e.hasta ? 'fija' : 'vivo');
  const cuerpo = vaciar(document.querySelector('#cinta-tabla tbody'));
  if (!CINTA.filas.length && !CINTA.fallo) {
    const tr = el('tr', 'vacia');
    const td = el('td', null, CINTA.hasta ? 'ninguna orden ≥ el filtro en lo servido' : 'pidiendo…');
    td.colSpan = 6;
    tr.appendChild(td);
    cuerpo.appendChild(tr);
  }
  CINTA.filas.forEach((o) => {
    const tr = el('tr', o.agresor);
    Object.assign(tr.dataset, { ts: o.ts, venue: o.venue, agresor: o.agresor, usd: o.usd, base: o.base,
                                operaciones: String(o.operaciones), pmin: o.precio_min, pmax: o.precio_max });
    [horaMs(o.ts), CINTA_VENUE[o.venue] || o.venue, o.agresor === 'compra' ? 'C' : 'V', cifra(o.usd), precioCinta(o),
      String(o.operaciones)].forEach((t, k) => tr.appendChild(el('td', ['h', 'v', 'l', 'u', 'p', 'n'][k], t)));
    tr.title = o.venue + ' · ' + o.operaciones + ' operaciones · ' + o.base + ' base · precio ' + o.precio_min
      + (o.precio_min === o.precio_max ? '' : '–' + o.precio_max);
    cuerpo.appendChild(tr);
  });
  window.FLUJO_CINTA = { vista: escribeHash(e), filtro, venues: fam.venues, hasta: CINTA.hasta, filas: CINTA.filas.length,
                         aplicadas: CINTA.aplicadas.slice() };
}

/* ------------------------------------------------------------- pedir */
function paraCinta() {
  if (CINTA.latido !== null) clearInterval(CINTA.latido);
  CINTA.latido = null;
}

/* Una vista nueva: la historia (la ultima hora hasta su final, o hasta ahora - 8 s) y, si es viva, el latido. */
async function cargaCinta(e, alPedir) {
  paraCinta();
  const mia = ++CINTA.pide;
  CINTA.vista = e;
  CINTA.filas = [];
  CINTA.hasta = null;
  CINTA.fallo = null;
  CINTA.aplicadas = [];
  const caja = document.getElementById('cinta');
  caja.hidden = !(e.ind || []).includes('cinta') || e.modo === 'tpo';
  if (caja.hidden) {
    window.FLUJO_CINTA = { vista: escribeHash(e), apagada: true };
    return;
  }
  pintaCinta();
  const q = { symbol: e.activo, venues: FAMILIAS[e.familia].venues.join(','), min_usd: filtroCinta(e),
              limit: CINTA_FILAS };
  if (e.hasta) {
    q.hasta = e.hasta;
    q.desde = isoZ(Date.parse(e.hasta) - 3600000);
  }
  const sobre = await pedir(RUTA_ORDENES, q);
  if (alPedir) alPedir(sobre);
  if (mia !== CINTA.pide) return;
  aplicaCinta(sobre);
  if (!e.hasta) CINTA.latido = setInterval(() => lateCinta(mia, alPedir), CINTA_VIVO_S * 1000);
}

async function lateCinta(mia, alPedir) {
  if (CINTA.pidiendo || document.hidden || !CINTA.hasta || mia !== CINTA.pide) return;
  CINTA.pidiendo = true;
  const e = CINTA.vista;
  const sobre = await pedir(RUTA_ORDENES, { symbol: e.activo, venues: FAMILIAS[e.familia].venues.join(','),
                                            min_usd: filtroCinta(e), desde: CINTA.hasta, limit: CINTA_FILAS });
  CINTA.pidiendo = false;
  if (alPedir) alPedir(sobre);
  if (mia !== CINTA.pide || CINTA.latido === null) return;
  aplicaCinta(sobre);
}

function aplicaCinta(sobre) {
  if (!sobre.ok) {
    CINTA.fallo = sobre;
    pintaCinta();
    return;
  }
  CINTA.fallo = null;
  CINTA.hasta = sobre.datos.hasta;
  CINTA.filas = sobre.datos.ordenes.concat(CINTA.filas).slice(0, CINTA_FILAS);
  CINTA.aplicadas.push({ desde: sobre.datos.desde, hasta: sobre.datos.hasta, n: sobre.datos.ordenes.length,
                         as_of: sobre.datos.as_of });
  pintaCinta();
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { CINTA_FILTRO, filtroCinta, precioCinta };
}
