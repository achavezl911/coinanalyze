'use strict';
/* LA MESA · los paneles que no son DECIDE
 * ---------------------------------------------------------------------------
 * REGLA DE TODO ESTE FICHERO: si el backend no lo sirve, se DECLARA el hueco con su motivo.
 * No se rellena con un placeholder bonito, no se deja en blanco, y no se pinta un 0.
 * Los huecos que ya estaban medidos por el operador el 2026-09-11 (PARADA-01) se declaran
 * con su nombre en el panel al que afectan: escalera del libro por nivel, histograma del
 * perfil por bins, y eje de TIEMPO del mapa de liquidaciones.
 */

/* Cabecera de panel con su VENUE. Cada tarjeta declara de donde sale su dato. */
function panel(titulo, venue) {
  const s = el('section', 'tarjeta');
  const cab = el('div', 'panel-rotulo');
  cab.appendChild(el('h3', null, titulo));
  if (venue) cab.appendChild(el('span', 'venue', venue));
  s.appendChild(cab);
  return s;
}

function pie(nodo, texto) {
  nodo.appendChild(el('p', 'pie', texto));
  return nodo;
}

function hueco(nodo, titulo, motivo) {
  const h = el('div', 'hueco');
  h.appendChild(el('b', null, titulo + ' — '));
  h.appendChild(document.createTextNode(motivo));
  nodo.appendChild(h);
  return nodo;
}

/* Un fallo de ruta se pinta como fallo, con su codigo. */
function fallo(nodo, sobre) {
  const h = el('div', 'hueco');
  h.appendChild(el('b', null, 'no se pudo leer ' + (sobre.ruta || '') + ' — '));
  h.appendChild(document.createTextNode('HTTP ' + sobre.http + ' · ' + (sobre.motivo || '')));
  nodo.appendChild(h);
  return nodo;
}

/* ------------------------------------------------- tira de fuentes, con venue */
function pintarTira(sobre, nodo) {
  const caja = vaciar(nodo);
  if (!sobre.ok) return fallo(caja, sobre);
  const feeds = (sobre.datos && sobre.datos.feeds) || [];
  if (!feeds.length) return hueco(caja, 'fuentes', 'la ruta contesto sin feeds');

  feeds.forEach((f) => {
    const d = el('div', 'fuente');
    const est = String(f.status || '').toUpperCase();
    const clase = est === 'OK' ? 'ok' : est === 'STALE' || est === 'DEGRADED' ? 'rancio' : 'mal';
    d.appendChild(el('span', 'punto ' + clase));
    d.appendChild(el('span', null, String(f.feed || '?').toUpperCase()));
    // EL VENUE, PEGADO AL FEED. Es la correccion 4.4 del operador: una cifra de OI sin venue
    // es ambigua, y la tira es donde se declara para los siete feeds.
    d.appendChild(el('span', 'venue', f.exchange || 's/venue'));
    const lat = f.latency_seconds;
    d.appendChild(
      el('span', 'venue', esNada(lat) ? 'lat N/D' : num(lat, 0) + ' s')
    );
    if (!esNada(f.coverage_pct)) d.appendChild(el('span', 'venue', num(f.coverage_pct, 0) + '%'));
    caja.appendChild(d);
  });
  caja.appendChild(
    el('span', 'venue', '· ' + feeds.length + ' feeds · una respuesta, cada uno con su edad')
  );
  return caja;
}

/* ------------------------------------------------------------------- SCAN */
function pintarScan(sobre, nodo) {
  const caja = vaciar(nodo);
  if (!sobre.ok) return fallo(caja, sobre);
  const filas = Array.isArray(sobre.datos) ? sobre.datos : sobre.datos.rows || sobre.datos.signals || [];
  if (!filas.length) {
    return hueco(caja, 'scan', 'la ruta de señales contesto sin filas: no hay nada que mirar');
  }
  filas.slice(0, 4).forEach((s) => {
    const c = el('div', 'chip');
    const ev = el('span', 'ev ev-vivo', 'VIVO');
    c.appendChild(ev);
    c.appendChild(el('div', 'titulo', s.state || s.name || s.title || '—'));
    if (s.confidence) c.appendChild(el('span', 'venue mono', 'confianza ' + s.confidence));
    if (s.ts) c.appendChild(el('span', 'venue mono', 'hace ' + (edad(s.ts) || 'N/D')));
    caja.appendChild(c);
  });
  return caja;
}

/* --------------------------------------------------------- matriz de delta */
function pintarMatriz(sobre, nodo, nodoPie, nodoVenue) {
  const caja = vaciar(nodo);
  if (!sobre.ok) return fallo(caja, sobre);
  const filas = sobre.datos.rows || sobre.datos.windows || sobre.datos.matrix || [];
  if (!filas.length) return hueco(caja, 'matriz', 'la ruta contesto sin ventanas');

  const t = el('table', 'rejilla');
  const thead = el('thead');
  const tr = el('tr');
  [
    'horizonte',
    'cobertura',
    'Δ spot',
    'Δ futuros',
    'Δ/vol spot',
    'Δ/vol fut',
    'cuadrante',
    'vol. fut',
    'ΔOI',
  ].forEach((h) => tr.appendChild(el('th', null, h)));
  thead.appendChild(tr);
  t.appendChild(thead);

  const tb = el('tbody');
  filas.forEach((f) => {
    const r = el('tr');
    // LA BARRA DE ACENTO SALE DE UN CAMPO SERVIDO (`fut_delta_context.band`), no de un umbral
    // escrito aqui.
    const banda = (f.fut_delta_context && f.fut_delta_context.band) || null;
    const clase =
      banda === 'extreme' || banda === 'high'
        ? 'banda-violeta'
        : banda === 'elevated'
          ? 'banda-azul'
          : '';
    const c0 = el('td', 'acento ' + clase, f.window || '?');
    r.appendChild(c0);

    const cob = el('td');
    if (esNada(f.spot_delta) && esNada(f.fut_delta)) cob.appendChild(el('span', 'nd', 'N/D'));
    else cob.textContent = f.windows_are_nested === false ? 'independiente' : 'anidada';
    r.appendChild(cob);

    // CADA CELDA SIN MEDIDA ES N/D, NUNCA 0. `spot_delta` llega null en las ventanas cortas.
    const celdaNum = (v, f2) => {
      const td = el('td');
      const s = f2 ? f2(v) : usd(v);
      if (s === null) td.appendChild(el('span', 'nd', 'N/D'));
      else {
        td.textContent = s;
        td.classList.add(Number(v) < 0 ? 'neg' : 'pos');
      }
      return td;
    };
    r.appendChild(celdaNum(f.spot_delta));
    r.appendChild(celdaNum(f.fut_delta));
    r.appendChild(celdaNum(f.spot_imbalance, (v) => num(v, 3)));
    r.appendChild(celdaNum(f.fut_imbalance, (v) => num(v, 3)));

    // EL CUADRANTE ES DERIVADO Y SE MARCA COMO TAL en la cabecera de la tarjeta (ver pie).
    const q = el('td');
    if (esNada(f.spot_delta) || esNada(f.fut_delta)) q.appendChild(el('span', 'nd', 'N/D'));
    else {
      const s = Number(f.spot_delta) >= 0 ? '+' : '−';
      const u = Number(f.fut_delta) >= 0 ? '+' : '−';
      q.textContent = 'spot ' + s + ' / fut ' + u;
    }
    r.appendChild(q);

    r.appendChild(celdaNum(f.fut_volume));
    r.appendChild(celdaNum(f.oi_change_pct, (v) => pct(v, 3)));
    tb.appendChild(r);
  });
  t.appendChild(tb);
  caja.appendChild(t);

  if (nodoVenue) nodoVenue.textContent = sobre.datos.symbol || '';
  if (nodoPie) {
    vaciar(nodoPie).textContent =
      filas.length +
      ' ventanas servidas por /api/scalp/delta-matrix · as_of ' +
      ((filas[0] && filas[0].as_of) || 'N/D') +
      ' · el CUADRANTE es DERIVADO (el signo de Δ spot combinado con el de Δ futuros), no un ' +
      'campo del backend · las celdas sin medida dicen N/D, no 0';
  }
  return caja;
}

/* ------------------------------------------------------------ INSPECT */
function pintarInspect(marco, datos, nodo) {
  const caja = vaciar(nodo);
  caja.className = marco === 'largo' ? 'grid-2' : 'grid-3';

  if (marco === 'scalp') {
    caja.appendChild(panelLibro(datos.libro));
    caja.appendChild(panelCinta(datos.decide, datos.libro));
    caja.appendChild(panelPrecioHueco('1m / 5m'));
  } else if (marco === 'swing') {
    caja.appendChild(panelWyckoff(datos.wyckoff));
    caja.appendChild(panelDerivados(datos.oi));
    caja.appendChild(panelPrecioHueco('15m / 30m / 1h'));
  } else {
    caja.appendChild(panelEstructura(datos.estructura));
    caja.appendChild(panelBasis(datos.basis));
  }
  return caja;
}

function panelLibro(sobre) {
  const p = panel('Libro · profundidad', 'binance + bybit (agregado)');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const d = sobre.datos;
  const comb = d.combined || d;
  const t = el('table', 'rejilla');
  const filas = [
    ['spread', esNada(comb.spread_bps) ? null : num(comb.spread_bps, 3) + ' bps'],
    ['bid L1', usd(comb.bid_notional_l1)],
    ['ask L1', usd(comb.ask_notional_l1)],
    ['bid L5', usd(comb.bid_notional_l5)],
    ['ask L5', usd(comb.ask_notional_l5)],
  ];
  filas.forEach(([k, v]) => {
    const r = el('tr');
    r.appendChild(el('td', null, k));
    const td = el('td');
    if (v === null) td.appendChild(el('span', 'nd', 'N/D'));
    else td.textContent = v;
    r.appendChild(td);
    t.appendChild(r);
  });
  p.appendChild(t);

  const fr = d.freshness || {};
  pie(
    p,
    'frescura: ' +
      (esNada(fr.age_seconds) ? 'N/D' : num(fr.age_seconds, 1) + ' s') +
      ' contra un tope de ' +
      (esNada(fr.max_age_seconds) ? 'N/D' : num(fr.max_age_seconds, 0) + ' s') +
      ' · estado ' +
      (fr.status || 'N/D')
  );
  // PENDIENTE 1 del operador, declarado en el panel al que afecta.
  hueco(
    p,
    'escalera del libro por nivel',
    'el mockup dibuja ORDER BOOK L5 con cinco precios y su tamaño a cada lado. ' +
      '/api/scalp/orderbook sirve profundidad AGREGADA (L1/L5/L10) por venue, no una escalera ' +
      'por precio: dibujar cinco precios exigiria inventarlos. Se pinta la profundidad real.'
  );
  return p;
}

function panelCinta(sobreDecide, sobreLibro) {
  const p = panel('Cinta', 'binance + bybit');
  const tiles = el('div', 'tiles');
  const dec = (sobreDecide && sobreDecide.ok && sobreDecide.datos) || null;

  const tile = (rotulo, valor, nota) => {
    const t = el('div', 'tile');
    t.appendChild(el('div', 'rotulo', rotulo));
    const v = el('div', 'valor');
    if (valor === null || valor === undefined) v.appendChild(noSe('ausente', nota || null));
    else v.textContent = valor;
    t.appendChild(v);
    if (nota && valor !== null && valor !== undefined) t.appendChild(el('div', 'pie', nota));
    return t;
  };

  if (!dec) {
    tiles.appendChild(tile('CINTA', null, 'DECIDE no llego: sin el sobre no hay cinta'));
  } else {
    const a = dec.age || {};
    tiles.appendChild(
      tile(
        'edad del snapshot',
        esNada(a.snapshot_lag_seconds && a.snapshot_lag_seconds.value)
          ? null
          : num(a.snapshot_lag_seconds.value, 1) + ' s',
        'tope declarado ' + num(dec.max_age_s, 0) + ' s'
      )
    );
    const p2 = a.price_cutoff_at && a.price_cutoff_at.value;
    const m2 = a.metrics_cutoff_at && a.metrics_cutoff_at.value;
    if (p2 && m2) {
      const dif = Math.abs(Date.parse(p2) - Date.parse(m2)) / 1000;
      tiles.appendChild(
        tile(
          'las dos vendimias del bloque',
          num(dif, 0) + ' s',
          'precio recortado a ' +
            String(p2).slice(11, 19) +
            ' · métricas a ' +
            String(m2).slice(11, 19) +
            ' — el silencio también informa'
        )
      );
    }
    const ev = dec.decide && dec.decide.evidence;
    tiles.appendChild(
      tile('evidencia', ev && !esNada(ev.value) ? num(ev.value, 0) + ' %' : null, ev && ev.source_key)
    );
  }

  if (sobreLibro && sobreLibro.ok) {
    const c = sobreLibro.datos.combined || {};
    tiles.appendChild(
      tile(
        'imbalance L5',
        esNada(c.bid_notional_l5) || esNada(c.ask_notional_l5)
          ? null
          : num(
              Number(c.bid_notional_l5) /
                (Number(c.bid_notional_l5) + Number(c.ask_notional_l5)),
              3
            ),
        'DERIVADO de bid/ask L5 servidos'
      )
    );
  }
  p.appendChild(tiles);
  // PENDIENTES 5 y 6 del operador.
  hueco(
    p,
    'serie de funding y BUY/SELL RATIO',
    'el backend publica `current_pct` y tres puntos (btr_15m, btr_1h, btr_24h), no una serie: ' +
      'una linea dibujada sobre tres puntos seria una serie inventada.'
  );
  return p;
}

function panelPrecioHueco(marcos) {
  const p = panel('Precio + CVD · ' + marcos, 'binance');
  hueco(
    p,
    'lienzo de precio',
    'esta parada trae DECIDE, la matriz, el libro y la estructura con sus datos reales. El ' +
      'lienzo de precio con su superposicion de CVD no esta dibujado todavia: se declara como ' +
      'hueco en vez de pintar una linea de ejemplo. Las rutas que lo alimentarian ya existen ' +
      '(/api/ohlcv con OHLC real e `is_complete`, /api/cvd).'
  );
  return p;
}

function panelWyckoff(sobre) {
  const p = panel('Estructura · Wyckoff', 'binance (velas diarias)');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const d = sobre.datos;
  if (d.available === false) {
    return hueco(p, 'wyckoff', 'el backend dice available:false para este simbolo');
  }
  const t = el('table', 'rejilla');
  // TRAMPA 2 del operador: `phase` y `bias` son OBJETOS. Pintar `d.wyckoff.phase` a pelo
  // escribe «[object Object]».
  const fase = d.phase || {};
  const bias = d.bias || {};
  const rango = d.range || {};
  [
    ['fase', [fase.code, fase.state].filter(Boolean).join(' · ') || null],
    ['explicacion', fase.explanation || null],
    ['sesgo', bias.bias || null],
    ['lectura', bias.reading || null],
    ['score', esNada(bias.score) ? null : num(bias.score, 1)],
    ['evidencia', esNada(bias.evidence_coverage_pct) ? null : num(bias.evidence_coverage_pct, 0) + ' %'],
    ['rango', esNada(rango.low) || esNada(rango.high) ? null : num(rango.low, 1) + ' … ' + num(rango.high, 1)],
    ['barras', esNada(rango.bars) ? null : String(rango.bars)],
  ].forEach(([k, v]) => {
    const r = el('tr');
    r.appendChild(el('td', null, k));
    const td = el('td');
    if (v === null) td.appendChild(el('span', 'nd', 'N/D'));
    else td.textContent = v;
    r.appendChild(td);
    t.appendChild(r);
  });
  p.appendChild(t);
  pie(p, 'fase y sesgo son objetos servidos (`wyckoff.phase.{code,state}`, `wyckoff.bias.{bias,reading}`)');
  return p;
}

function panelDerivados(sobre) {
  const p = panel('Derivados · OI con su cobertura', 'binance + bybit');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const d = sobre.datos;
  const t = el('table', 'rejilla');
  const venue = d.by_venue || {};
  [
    ['OI total', usd(d.oi_total_usd)],
    ['OI binance', usd(venue.binance_oi_usd)],
    ['OI bybit', usd(venue.bybit_oi_usd)],
    ['percentil 1a', esNada(d.percentile_1y) ? null : num(d.percentile_1y, 1)],
  ].forEach(([k, v]) => {
    const r = el('tr');
    r.appendChild(el('td', null, k));
    const td = el('td');
    if (v === null) td.appendChild(el('span', 'nd', 'N/D'));
    else td.textContent = v;
    r.appendChild(td);
    t.appendChild(r);
  });
  p.appendChild(t);

  // LA CINTA DE COBERTURA SE DIBUJA DESDE LOS BUCKETS, NO DESDE UN PORCENTAJE REDONDEADO.
  // Es el hallazgo 6 del operador: un 99 % pintado como cinta llena esconde el bucket que falta.
  const cob = d.coverage || {};
  const claves = Object.keys(cob);
  if (claves.length) {
    const t2 = el('table', 'rejilla');
    const tr = el('tr');
    ['ventana', 'observados', 'esperados', 'completa'].forEach((h) => tr.appendChild(el('th', null, h)));
    t2.appendChild(tr);
    claves.forEach((k) => {
      const c = cob[k] || {};
      const r = el('tr');
      r.appendChild(el('td', null, k));
      r.appendChild(el('td', null, esNada(c.observed_buckets) ? 'N/D' : String(c.observed_buckets)));
      r.appendChild(el('td', null, esNada(c.expected_buckets) ? 'N/D' : String(c.expected_buckets)));
      const td = el('td');
      if (esNada(c.complete)) td.appendChild(el('span', 'nd', 'N/D'));
      else {
        td.textContent = c.complete ? 'COMPLETA' : 'INCOMPLETA';
        td.classList.add(c.complete ? 'pos' : 'neg');
      }
      r.appendChild(td);
      t2.appendChild(r);
    });
    p.appendChild(t2);
    pie(p, 'la cobertura se lee de `observed_buckets`/`expected_buckets`, no de un % redondeado');
  }
  return p;
}

function panelEstructura(sobre) {
  const p = panel('ChoCh / BOS por horizonte', 'binance (OHLC real)');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const hz = (sobre.datos && sobre.datos.horizons) || {};
  const claves = Object.keys(hz);
  if (!claves.length) return hueco(p, 'estructura', 'el backend no trae horizontes');
  const t = el('table', 'rejilla');
  const tr = el('tr');
  ['horizonte', 'estado', 'BOS', 'ChoCh', 'invalidación', 'swings'].forEach((h) =>
    tr.appendChild(el('th', null, h))
  );
  t.appendChild(tr);
  claves.forEach((k) => {
    const h = hz[k] || {};
    const r = el('tr');
    r.appendChild(el('td', null, k));
    r.appendChild(el('td', null, h.state || 'N/D'));
    [h.bos_level, h.choch_level, h.invalidation_level].forEach((v) => {
      const td = el('td');
      if (esNada(v)) td.appendChild(el('span', 'nd', 'N/D'));
      else td.textContent = num(v, 1);
      r.appendChild(td);
    });
    // TRAMPA 4 del operador: `swing_count` es {highs, lows}. Pintarlo a pelo da NaN.
    const sc = h.swing_count || {};
    const td = el('td');
    if (esNada(sc.highs) && esNada(sc.lows)) td.appendChild(el('span', 'nd', 'N/D'));
    else td.textContent = (sc.highs || 0) + 'H / ' + (sc.lows || 0) + 'L';
    r.appendChild(td);
    t.appendChild(r);
  });
  p.appendChild(t);
  pie(
    p,
    'el placeholder de pivotes del handoff no se usa: estos seis horizontes los publica ' +
      '/api/structure-detail con `bos_level`, `choch_level` e `invalidation_level`. Donde el ' +
      'backend no tiene, se ve N/D.'
  );
  return p;
}

function panelBasis(sobre) {
  const p = panel('Perp vs Spot · basis', 'binance + bybit');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const d = sobre.datos;
  const t = el('table', 'rejilla');
  [
    ['futuro', num(d.fut_price, 1)],
    ['spot', num(d.spot_price, 1)],
    ['basis', esNada(d.basis_bps) ? null : num(d.basis_bps, 2) + ' bps'],
    ['estado', d.basis_status || null],
  ].forEach(([k, v]) => {
    const r = el('tr');
    r.appendChild(el('td', null, k));
    const td = el('td');
    if (v === null) td.appendChild(el('span', 'nd', 'N/D'));
    else td.textContent = v;
    r.appendChild(td);
    t.appendChild(r);
  });
  p.appendChild(t);
  // PENDIENTE 7 del operador, con su coste medido por el: el bundle de los tres en serie
  // tardaba ~13 s. Meterlo en la carga inicial se come el objetivo de velocidad.
  hueco(
    p,
    'los otros dos activos',
    'la tabla de los tres activos exige el bundle de los tres, que el operador midio en ' +
      '~13 s en serie. No se carga sola: se declara, para no pagar 13 s en cada apertura.'
  );
  return p;
}

/* --------------------------------------------------------------- RESEARCH */
function pintarResearch(marco, datos, nodo) {
  const caja = vaciar(nodo);
  caja.className = 'grid-2';
  if (marco === 'largo') {
    caja.appendChild(panelMacro(datos.macro));
    caja.appendChild(
      (function () {
        const p = panel('Ventana insuficiente', null);
        hueco(
          p,
          'derivados sobre 2 años de precio',
          'no se superponen: la ventana de derivados no alcanza el arco del precio largo. ' +
            'Dibujarlos juntos sugeriria una relacion que el dato no sostiene.'
        );
        return p;
      })()
    );
    return caja;
  }
  caja.appendChild(panelLiquidaciones(datos.liq));
  caja.appendChild(panelPerfil(datos.perfil));
  return caja;
}

function panelLiquidaciones(sobre) {
  const p = panel('Liquidaciones · densidad por precio', 'binance + bybit');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const d = sobre.datos;
  const niveles = d.levels || d.rows || [];
  if (!niveles.length) return hueco(p, 'liquidaciones', 'la ruta contesto sin niveles');
  const t = el('table', 'rejilla');
  const tr = el('tr');
  ['precio', 'largos', 'cortos'].forEach((h) => tr.appendChild(el('th', null, h)));
  t.appendChild(tr);
  niveles.slice(0, 12).forEach((n) => {
    const r = el('tr');
    r.appendChild(el('td', null, num(n.price ?? n.level ?? n.bucket, 1) || 'N/D'));
    [n.long_usd ?? n.longs, n.short_usd ?? n.shorts].forEach((v, i) => {
      const td = el('td');
      const s = usd(v);
      if (s === null) td.appendChild(el('span', 'nd', 'N/D'));
      else {
        td.textContent = s;
        td.classList.add(i === 0 ? 'neg' : 'pos');
      }
      r.appendChild(td);
    });
    t.appendChild(r);
  });
  p.appendChild(t);
  pie(
    p,
    'densidad de liquidaciones REALIZADAS (histórico), NO un modelo predictivo: dice dónde ya ' +
      'se ejecutaron forzados, no dónde reventarían posiciones abiertas.'
  );
  // PENDIENTE 3 del operador.
  hueco(
    p,
    'eje de TIEMPO del mapa',
    '/api/liquidation-map sirve niveles de PRECIO en una ventana; el eje de tiempo no existe ' +
      'como dato servido. El heatmap precio × tiempo del prototipo solo se puede DERIVAR ' +
      'restando ventanas acumuladas (8 peticiones), y eso no se hace en la carga inicial.'
  );
  return p;
}

function panelPerfil(sobre) {
  const p = panel('Perfil de volumen · niveles', 'binance');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const d = sobre.datos;
  const t = el('table', 'rejilla');
  [
    ['POC', num(d.poc, 1)],
    ['VAH', num(d.vah, 1)],
    ['VAL', num(d.val, 1)],
  ].forEach(([k, v]) => {
    const r = el('tr');
    r.appendChild(el('td', null, k));
    const td = el('td');
    if (v === null) td.appendChild(el('span', 'nd', 'N/D'));
    else td.textContent = v;
    r.appendChild(td);
    t.appendChild(r);
  });
  p.appendChild(t);
  // PENDIENTE 2 del operador.
  hueco(
    p,
    'histograma por bins',
    'el backend publica POC, VAH, VAL, HVN, LVN y bandas de VWAP, pero NO el histograma bin a ' +
      'bin. Se marcan los niveles servidos; no se dibujan barras que nadie sirve.'
  );
  return p;
}

function panelMacro(sobre) {
  const p = panel('Calendario macro', 'externo');
  if (!sobre || !sobre.ok) return fallo(p, sobre || { http: 0, motivo: 'no pedido' });
  const d = sobre.datos;
  // TRAMPA 5 del operador: las claves son title/event_at/importance/source.
  const up = ((d.event_risk || {}).upcoming) || d.upcoming || [];
  if (!up.length) return hueco(p, 'calendario', 'la ruta contesto sin eventos proximos');
  const t = el('table', 'rejilla');
  const tr = el('tr');
  ['fecha', 'evento', 'importancia', 'fuente'].forEach((h) => tr.appendChild(el('th', null, h)));
  t.appendChild(tr);
  up.slice(0, 8).forEach((e) => {
    const r = el('tr');
    r.appendChild(el('td', null, String(e.event_at || '').slice(0, 10) || 'N/D'));
    r.appendChild(el('td', null, e.title || 'N/D'));
    r.appendChild(el('td', null, e.importance || 'N/D'));
    r.appendChild(el('td', null, e.source || 'N/D'));
    t.appendChild(r);
  });
  p.appendChild(t);
  if (d.etf_note || (d.notes && d.notes.length)) {
    pie(p, d.etf_note || d.notes.join(' · '));
  }
  return p;
}

/* ----------------------------------------------------------------- FOLLOW */
function pintarFollow(sobre, nodo) {
  const caja = vaciar(nodo);
  if (!sobre.ok) return fallo(caja, sobre);
  const setups = (sobre.datos && sobre.datos.setups) || [];
  if (!setups.length) return hueco(caja, 'follow', 'la ruta contesto sin setups');
  const t = el('table', 'rejilla');
  const tr = el('tr');
  ['setup', 'sesgo', 'horizonte', 'confianza', 'evidencia', 'estado'].forEach((h) =>
    tr.appendChild(el('th', null, h))
  );
  t.appendChild(tr);
  setups.forEach((s) => {
    const r = el('tr');
    r.appendChild(el('td', null, s.name || s.id || 'N/D'));
    r.appendChild(el('td', null, s.bias || 'N/D'));
    r.appendChild(el('td', null, s.horizon || 'N/D'));
    const tdc = el('td');
    if (esNada(s.confidence)) tdc.appendChild(el('span', 'nd', 'N/D'));
    else tdc.textContent = num(s.confidence, 0);
    r.appendChild(tdc);
    const tde = el('td');
    const m = (s.matched || []).length;
    const f = (s.missing || []).length;
    tde.textContent = m + ' de ' + (m + f);
    r.appendChild(tde);
    const td = el('td');
    const est = String(s.state || '').toLowerCase();
    const ev = el(
      'span',
      'ev ' + (est === 'activo' ? 'ev-vivo' : est === 'vigilando' ? 'ev-backtest' : 'ev-noeval'),
      (s.state || 'N/D').toUpperCase()
    );
    td.appendChild(ev);
    r.appendChild(td);
    t.appendChild(r);
  });
  caja.appendChild(t);
  pie(caja, 'el `missing` de cada setup se cuenta: «' + setups.length + ' setups servidos por /api/setup»');
  return caja;
}

/* ------------------------------------------------------------------ LEARN */
function pintarLearn(sobre, nodo) {
  const caja = vaciar(nodo);
  if (!sobre.ok) return fallo(caja, sobre);
  const filas = (sobre.datos && (sobre.datos.rows || sobre.datos.observations)) || [];
  if (!filas.length) {
    return hueco(
      caja,
      'learn',
      'la ruta de replay contesto sin observaciones en la ventana pedida'
    );
  }
  const t = el('table', 'rejilla');
  const tr = el('tr');
  ['fecha', 'sabido en t0', 'resultado posterior', 'evidencia'].forEach((h) =>
    tr.appendChild(el('th', null, h))
  );
  t.appendChild(tr);
  filas.slice(0, 12).forEach((f) => {
    const r = el('tr');
    r.appendChild(el('td', null, String(f.ts || f.observed_at || '').slice(0, 19).replace('T', ' ')));
    r.appendChild(el('td', null, f.state || f.context_state || 'N/D'));
    const td = el('td');
    // LO SABIDO EN T0 NUNCA SE MEZCLA CON EL RESULTADO. Sin outcome -> «sin outcome», no 0.
    const out = f.outcome || f.result;
    if (esNada(out)) td.appendChild(noSe('ausente', 'sin outcome: aún no finalizado'));
    else td.textContent = String(out);
    r.appendChild(td);
    r.appendChild(el('td', null, 'HISTÓRICO'));
    t.appendChild(r);
  });
  caja.appendChild(t);
  pie(
    caja,
    'el marco guarda su contexto con `context_hash` y `logic_version`; el outcome se finaliza ' +
      'despues (`finalized_at`) y NUNCA entra en el marco. Una observacion sin resultado se ve ' +
      'como «sin outcome», no como un cero.'
  );
  return caja;
}

/* ------------------------------------------------------- pie de servicios */
function pintarServicios(sobre, nodo) {
  const caja = vaciar(nodo);
  if (!sobre.ok) return fallo(caja, sobre);
  const col = (sobre.datos && sobre.datos.collectors) || {};
  const claves = Object.keys(col);
  if (!claves.length) return hueco(caja, 'servicios', 'la ruta no trae colectores');
  claves.forEach((k) => {
    const c = col[k] || {};
    const d = el('div', 'fuente');
    const est = String(c.status || '').toUpperCase();
    d.appendChild(el('span', 'punto ' + (est === 'OK' ? 'ok' : est ? 'rancio' : 'mal')));
    d.appendChild(el('span', null, k));
    d.appendChild(el('span', 'venue', c.status || 'N/D'));
    if (!esNada(c.age_seconds)) d.appendChild(el('span', 'venue', num(c.age_seconds, 0) + ' s'));
    caja.appendChild(d);
  });
  return caja;
}
