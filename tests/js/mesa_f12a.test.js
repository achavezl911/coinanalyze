'use strict';
// LA MESA · los 12 casos de fable-f12a (U-01, U-02, F1, G1, E1-E4, E6, D1, H1), traidos de
// entregas/fable/fable-f12a/scripts/fable_f12a_pantalla.py SIN cambiar su juicio: cada caso
// REPRODUCE con la mesa de main@7cb8abe y deja de reproducir con el remate MESA R1.
//
// POR QUE UN MUNDO PROPIO Y NO `harness-mesa.js`: estos casos necesitan un `fetch` que suelta
// las respuestas en el orden que la carrera pide (la de BTC, TARDE) y un reloj que mueve los
// dos intervalos de la mesa. Las respuestas tienen la FORMA medida en el release de 140
// (2026-11-19 y brazo B de fable_dz3_sonda.py, 11-22); el doble de DECIDE vive en
// mesa_f12a_decide.json. Ojo: `getElementById` CREA el nodo que no existe, asi que estos
// casos no prueban que mesa.html tenga un nodo: eso lo mira el test de `edad-` de abajo.

const test = require('node:test');
const assert = require('node:assert');
const path = require('path');
const fs = require('fs');
const vm = require('vm');

const DIR = path.join(__dirname, '..', '..', 'static', 'mesa');
const DECIDE = require('./mesa_f12a_decide.json');
const FICHEROS = ['mesa-datos.js', 'mesa-decide.js', 'mesa-paneles.js', 'mesa-entradas.js', 'mesa-app.js'];
const T0 = Date.parse('2026-11-19T19:00:50Z');
const NIVEL = {
  BTC: { center: 62491.22, low: 61667.11, high: 63280.5, inval: 62360.0, liq: 61380.5 },
  ETH: { center: 1850.5, low: 1832.0, high: 1869.0, inval: 1841.3, liq: 1811.7 },
  // SOL: las cifras que servia 140 el 2026-11-19 19:01Z (zona, invalidacion 1h, basis).
  SOL: { center: 74.834, low: 73.7, high: 75.951, inval: 74.08, liq: 72.68 },
};
const iso = (ms) => new Date(ms).toISOString();

class Nodo {
  constructor(tag, texto) {
    this.tag = tag;
    this.hijos = [];
    this._t = texto || '';
    this.attrs = {};
    this.className = '';
    this.hidden = false;
    this.dataset = {};
    this.style = {};
    this.parentNode = null;
    const yo = this;
    const clases = () => new Set(yo.className.split(/\s+/).filter(Boolean));
    const pon = (s) => { yo.className = Array.from(s).join(' '); };
    this.classList = {
      add: (...c) => { const s = clases(); c.forEach((x) => s.add(x)); pon(s); },
      remove: (...c) => { const s = clases(); c.forEach((x) => s.delete(x)); pon(s); },
      toggle: (c, on) => {
        const s = clases();
        const q = on === undefined ? !s.has(c) : Boolean(on);
        if (q) s.add(c); else s.delete(c);
        pon(s);
        return q;
      },
      contains: (c) => clases().has(c),
    };
  }
  appendChild(n) { n.parentNode = this; this.hijos.push(n); return n; }
  removeChild(n) { this.hijos = this.hijos.filter((x) => x !== n); return n; }
  get firstChild() { return this.hijos[0] || null; }
  get children() { return this.hijos.filter((h) => h.tag !== '#text'); }
  get textContent() {
    return this.tag === '#text' ? this._t : this.hijos.map((h) => h.textContent).join('');
  }
  set textContent(v) {
    this.hijos = [];
    if (v !== null && v !== undefined && String(v) !== '') this.appendChild(new Nodo('#text', String(v)));
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener() {}
  querySelectorAll() { return []; }
  querySelector() { return null; }
  closest() { return null; }
}

function plano(n) {
  if (n.tag === '#text') return n._t;
  return n.hijos.map(plano).filter((x) => x !== '').join(' ');
}
function todos(n, acc) {
  const a = acc || [];
  a.push(n);
  n.hijos.forEach((h) => todos(h, a));
  return a;
}

/* Las respuestas de la API, con la FORMA de 140. `ahora` es el reloj del banco. */
function doble(u, ahora) {
  const sim = u.searchParams.get('symbol') || 'BTCUSDT_PERP.A';
  const act = sim.slice(0, 3);
  const n = NIVEL[act];
  const r = u.pathname;
  if (r === '/api/mesa/decide') {
    const d = JSON.parse(JSON.stringify(DECIDE));
    d.symbol = sim;
    d.asset = act;
    d.frame = u.searchParams.get('frame');
    d.generated_at = iso(ahora);
    d.envelope_cut.as_of = iso(ahora - 1000);
    d.age.snapshot_lag_seconds.value = 5.0;
    d.decide.zone.center.value = n.center;
    d.decide.zone.low.value = n.low;
    d.decide.zone.high.value = n.high;
    d.decide.structural_invalidation.value = n.inval;
    return d;
  }
  if (r === '/api/quality/feeds') {
    return {
      symbol: sim, generated_at: iso(ahora), window_seconds: 900,
      feeds: [{ feed: 'ohlcv_1min', exchange: 'binance', status: 'OK', last_ts: iso(ahora - 12000),
        latency_seconds: 12.3, coverage_pct: 93.3, collector: 'ingest' }],
      collectors: { ingest: { status: 'OK', age_seconds: 3 } },
    };
  }
  if (r === '/api/scalp/signals') {
    const fila = (seg, state, confidence) => ({ ts: iso(ahora - seg * 1000), symbol: sim, state, confidence });
    return { limit: 200, count: 200, truncated: true, as_of: iso(ahora), rows: [
      fila(4, 'Short Rejection', 'media'), fila(23, 'No Trade', 'baja'),
      fila(41, 'Short Rejection', 'media'), fila(59, 'No Trade', 'baja'), fila(77, 'No Trade', 'baja'),
    ] };
  }
  if (r === '/api/scalp/delta-matrix') {
    const base = { as_of: iso(ahora), windows_are_nested: true, spot_imbalance: -0.12, fut_imbalance: -0.31,
      fut_volume: 3.1e7, oi_change_pct: null };
    return [
      { ...base, window: '1m', spot_delta: -642750.9, fut_delta: -9238338.2, coverage_status: 'complete',
        spot_coverage_status: 'complete', futures_coverage_status: 'complete',
        fut_delta_context: { band: 'extremo', robust_z: 4.2, status: 'ok' } },
      { ...base, window: '8h', spot_delta: null, fut_delta: -78132370.9, coverage_status: 'partial',
        spot_coverage_status: 'partial', futures_coverage_status: 'complete',
        spot_coverage_reason: 'agg_minutes_short', fut_delta_context: { band: 'alto', robust_z: 2.9, status: 'ok' } },
    ];
  }
  if (r === '/api/setup') return { symbol: sim, snapshot_ts: iso(ahora), setups: [] };
  if (r === '/api/signals/replay') return { rows: [] };
  if (r === '/api/scalp/orderbook') {
    const venue = (exchange, vc, b5, a5) => ({ exchange, venue_count: vc, ts: iso(ahora - 2200), mid_px: n.center,
      spread_bps: 0.016, bid_notional_l1: 5e5, ask_notional_l1: 4e5, bid_notional_l5: b5, ask_notional_l5: a5,
      imbalance_l5: b5 / (b5 + a5) });
    return { symbol: sim, rows: [venue('binance', 1, 1097130.35, 8976.43), venue('bybit', 1, 237766.24, 132253.45),
      venue('combined', 2, 1334896.58, 141229.87)],
      freshness: { status: 'fresh', as_of: iso(ahora - 2200), age_seconds: 2.2, max_age_seconds: 30 } };
  }
  if (r === '/api/liquidation-map') {
    return { type: 'historical_realized_density_3h', current_price: n.center, as_of: iso(ahora), window_minutes: 180,
      levels: [
        { price: n.liq, long_liq: 466952.53, short_liq: 0.0, total_notional: 466952.53, distance_pct: -1.6 },
        { price: n.high, long_liq: 0.0, short_liq: 170027.94, total_notional: 170027.94, distance_pct: 1.3 },
      ] };
  }
  if (r === '/api/volume-profile') {
    return { symbol: sim, as_of: iso(ahora), available: true,
      session: { poc: n.center + 111.1, vah: n.high, val: n.low, hvn: [], lvn: [] }, vwap: {} };
  }
  if (r === '/api/scalp/basis') {
    return { fut_ts: iso(ahora), spot_ts: iso(ahora), fut_price: 73.86, spot_price: 73.9, basis_bps: -5.4127,
      fut_age_seconds: 1.2, spot_age_seconds: 0.8, skew_ms: 400, stale_after_seconds: 30.0, status: 'VALID' };
  }
  if (r === '/api/structure-detail') {
    return { symbol: sim, as_of: iso(ahora), horizons: { '1h': { state: 'HH_HL', bos_level: 75.63, choch_level: 74.08,
      invalidation_level: 74.08, distance_to_invalidation_pct: -0.067, close: 74.03, swing_count: { highs: 3, lows: 3 } } } };
  }
  if (r === '/api/oi-context') {
    return { symbol: sim, available: true, oi_total_usd: 5991411852.35, percentile_1y: 11.3, coverage: {},
      by_venue: { binance_oi_usd: 5991411852.35, bybit_oi_usd: 4468899882.58, two_venue_total_usd: 10460311734.93,
        bybit_share_of_two_venues_pct: 42.7, note: 'open_interest viene del simbolo .A, que es BINANCE' } };
  }
  if (r === '/api/wyckoff') {
    return { symbol: sim, available: true, range: { available: true, low: 60968.3, high: 84937.46, bars: 270 },
      phase: { code: 'B', state: 'construccion_de_causa' }, bias: { bias: 'neutral', reading: 'equilibrio_sin_ventaja' } };
  }
  if (r === '/api/external-macro') return { available: true, regime: 'restrictivo', event_risk: { upcoming: [] } };
  return {};
}

const esperaReal = (ms) => new Promise((r) => setTimeout(r, ms));
async function respira() { await esperaReal(1); await esperaReal(1); }

function mundo() {
  const reloj = { ms: 0 };
  const ids = {};
  const pend = [];
  const pedidas = [];
  let timers = [];
  let nTimer = 0;
  const document = {
    hidden: false,
    getElementById(id) { if (!ids[id]) ids[id] = new Nodo('div'); return ids[id]; },
    createElement(t) { return new Nodo(t); },
    createTextNode(t) { return new Nodo('#text', String(t)); },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    addEventListener() {},
  };
  class Fecha extends Date {
    constructor(...a) { if (a.length) super(...a); else super(T0 + reloj.ms); }
    static now() { return T0 + reloj.ms; }
  }
  const ctx = {
    document, console, URL, URLSearchParams,
    Date: Fecha,
    performance: { now: () => reloj.ms, mark() {}, measure() {} },
    location: { origin: 'http://banco', hash: '' },
    addEventListener() {},
    fetch(url) {
      const u = new URL(url);
      pedidas.push({ ruta: u.pathname, activo: (u.searchParams.get('symbol') || '').slice(0, 3), ms: reloj.ms });
      return new Promise((res) => pend.push({ u, res }));
    },
    setInterval(fn, ms) { nTimer += 1; timers.push({ id: nTimer, fn, ms, prox: reloj.ms + ms }); return nTimer; },
    clearInterval(id) { timers = timers.filter((t) => t.id !== id); },
    setTimeout: (fn, ms) => setTimeout(fn, ms),
    clearTimeout: (id) => clearTimeout(id),
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  FICHEROS.forEach((f) => vm.runInContext(fs.readFileSync(path.join(DIR, f), 'utf8'), ctx, { filename: f }));

  const suelta = (filtro) => {
    const van = pend.filter(filtro || (() => true));
    van.forEach((p) => {
      pend.splice(pend.indexOf(p), 1);
      const cuerpo = doble(p.u, T0 + reloj.ms);
      p.res({ ok: true, status: 200, json: async () => cuerpo });
    });
    return van.length;
  };
  const es = (activo, soloDecide) => (p) =>
    p.u.searchParams.get('symbol').slice(0, 3) === activo &&
    (soloDecide === undefined || (p.u.pathname === '/api/mesa/decide') === soloDecide);
  const todo = async () => { for (let i = 0; i < 6; i += 1) { await respira(); suelta(); } await respira(); };
  /* Avanza el reloj del banco de segundo en segundo: dispara latido y refresco, y contesta. */
  const avanza = async (seg, hasta) => {
    for (let i = 1; i <= seg; i += 1) {
      reloj.ms += 1000;
      timers.slice().forEach((t) => { if (reloj.ms >= t.prox) { t.prox += t.ms; t.fn(); } });
      await respira();
      suelta();
      await respira();
      if (hasta && hasta()) return i;
    }
    return null;
  };
  const pon = (marco, activo) => vm.runInContext(
    "ESTADO.marco='" + marco + "'; ESTADO.activo='" + activo + "'; ESTADO.vista='mesa'; pintar()", ctx);
  const t = (id) => plano(document.getElementById(id));
  const decide = () => ['decide-sesgo', 'decide-motivo', 'decide-campos'].map(t).join(' ¦ ');
  return { ctx, reloj, ids, pend, pedidas, document, suelta, es, todo, avanza, pon, t, decide,
    js: (codigo) => vm.runInContext(codigo, ctx) };
}

const resultado = {};
function caso(id, reproduce, texto) {
  resultado[id.split(' ')[0]] = { reproduce, texto };
}
const corta = (s, n) => (s.length > n ? s.slice(0, n) + '…' : s);

async function carreraOla1() {
  const m = mundo();
  const f = (a) => m.ctx.num(NIVEL[a].center, 1);
  m.pon('scalp', 'BTC');
  await respira();
  m.pon('scalp', 'ETH');
  await respira();
  m.suelta(m.es('ETH', true));
  await respira();
  m.suelta(m.es('ETH', false));
  await respira();
  const antes = m.decide().includes(f('ETH'));
  m.suelta(m.es('BTC', true)); // la respuesta LENTA del activo que el operador ya dejo
  await respira();
  const cruzado = m.decide().includes(f('BTC')) && !m.decide().includes(f('ETH'));
  const ultimo = m.js('_ultimoDecide && _ultimoDecide.datos.asset');
  const seg = await m.avanza(40, () => m.decide().includes(f('ETH')));
  caso('A1 ola 1', antes && cruzado && m.js('ESTADO.activo') === 'ETH',
    'selector=' + m.js('ESTADO.activo') + ', DECIDE pinta la zona de ' + ultimo + ' (' + f('BTC') +
    '), _ultimoDecide.asset=' + ultimo + '; el latido le da edad viva; se corrige a los ' + seg + ' s (refresco)');
}

async function carreraOla2() {
  const m = mundo();
  const f = (a) => m.ctx.num(NIVEL[a].liq, 1);
  m.pon('scalp', 'BTC');
  await respira();
  m.suelta(m.es('BTC', true));
  await respira(); // la ola 2 de BTC queda pedida y SIN contestar
  const colgadas = m.pend.length;
  m.pon('scalp', 'ETH');
  await respira();
  m.suelta(m.es('ETH', true));
  await respira();
  m.suelta(m.es('ETH', false));
  await respira();
  const antes = m.t('research').includes(f('ETH'));
  m.suelta(m.es('BTC', false)); // llega tarde la ola 2 del activo anterior
  await respira();
  const n0 = m.pedidas.length;
  await m.avanza(600);
  const despues = m.pedidas.slice(n0);
  const cruzado = m.t('research').includes(f('BTC')) && !m.t('research').includes(f('ETH'));
  caso('A2 ola 2', antes && cruzado,
    colgadas + ' rutas de BTC contestan tarde: selector=' + m.js('ESTADO.activo') + ' y DECIDE de ' +
    m.js('_ultimoDecide.datos.asset') + ', pero liquidaciones pinta ' + f('BTC') + ' (BTC) y scan/matriz/libro son de BTC; ' +
    '600 s despues sigue igual: ' + despues.length + ' peticiones, ' +
    despues.filter((p) => p.ruta !== '/api/mesa/decide').length + ' fuera de /api/mesa/decide');
}

async function edadesYFormas() {
  const m = mundo();
  m.pon('scalp', 'BTC');
  await m.todo();
  const tile = (rot) => todos(m.document.getElementById('inspect'))
    .filter((n) => n.className === 'tile' && plano(n).startsWith(rot)).map(plano).join('');
  const pieLibro = () => todos(m.document.getElementById('inspect'))
    .filter((n) => n.className === 'pie' && plano(n).startsWith('frescura')).map(plano).join('');
  const foto = () => ({ tile: tile('edad del snapshot'), scan: m.t('scan'), libro: pieLibro(),
    tira: m.t('tira'), edad: m.t('decide-edad') });
  const a = foto();
  const n0 = m.pedidas.length;
  await m.avanza(300);
  const b = foto();
  const fuera = m.pedidas.slice(n0).filter((p) => p.ruta !== '/api/mesa/decide').length;
  const refrescos = m.pedidas.length - n0 - fuera;
  caso('B1 edad fija', a.tile === b.tile && a.scan === b.scan && a.libro === b.libro && a.tira === b.tira && refrescos > 0,
    '300 s despues (' + fuera + ' peticiones de ola 2, ' + refrescos + ' refrescos de DECIDE): cinta «' + corta(b.tile, 60) +
    '» · scan «' + corta(b.scan, 62) + '» · libro «' + corta(b.libro, 58) + '» · tira «' + corta(b.tira, 40) + '»');
  caso('B1b etiqueta de edad', !/^leído hace \d+ s$/.test(m.t('edad-scan')),
    'la etiqueta edad-scan dice «' + m.t('edad-scan') + '» tras ' + fuera + ' peticiones de ola 2');
  const vivos = (m.t('scan').match(/VIVO/g) || []).length;
  caso('F1 scan VIVO', vivos === 4 && /VIVO No Trade/.test(m.t('scan')),
    vivos + ' chips VIVO sobre las 4 ultimas EVALUACIONES de 200 (truncated=true), «No Trade» incluido, y 300 s despues');

  const research = m.t('research');
  const poc = m.ctx.num(NIVEL.BTC.center + 111.1, 1);
  caso('E1 perfil', !research.includes(poc),
    'servido session.poc=' + poc + ' y la pantalla: «' + corta(research.slice(research.indexOf('POC')), 34) + '»');
  caso('E2 liquidaciones', !research.includes(m.ctx.usd(466952.53)),
    'servido long_liq=466952.53 (' + m.ctx.usd(466952.53) + ') y la pantalla: «' +
    corta(research.slice(research.indexOf('precio')), 70) + '»');
  caso('E3 imbalance L5', /AUSENTE/.test(tile('imbalance L5')),
    'servida la fila combined (imbalance_l5=0.904) y la cinta: «' + corta(tile('imbalance L5'), 40) + '»');
  const bandas = todos(m.document.getElementById('matriz')).filter((n) => /banda-(violeta|azul)/.test(n.className)).length;
  caso('E4 banda matriz', bandas === 0,
    'servido fut_delta_context.band=extremo y alto: ' + bandas + ' celdas con acento (el JS espera extreme/high/elevated)');
  m.pon('largo', 'SOL');
  await m.todo();
  const largo = m.t('inspect');
  caso('E6 estado basis', !largo.includes('VALID'),
    'servido status=VALID y el panel: «' + corta(largo.slice(largo.indexOf('futuro')), 60) + '»');
  caso('D1 un decimal (SOL)', largo.includes('futuro 73,9 spot 73,9'),
    'futuro 73.86 y spot 73.9 se pintan «73,9» los dos con basis -5,41 bps; BOS/ChoCh/invalidacion 74.08 -> «' +
    m.ctx.num(74.08, 1) + '» con cierre 74.03; DECIDE zona 74.834/75.951 -> «' +
    (m.decide().match(/7[3-6],\d/g) || []).join(' ') + '»');
  caso('H1 invalidacion sin lado', !/0,067|0,07|cruzad/.test(largo + m.decide()),
    'servido 1h invalidation_level=74.08 con distance_to_invalidation_pct=-0.067 (cierre 74.03) y el panel: «' +
    corta(largo.slice(largo.indexOf('1h')), 40) + '»: ni signo ni distancia, tampoco en DECIDE');

  m.pon('swing', 'BTC');
  await m.todo();
  const swing = m.t('inspect');
  caso('G1 OI total', swing.includes('OI total $5.99B') && !swing.includes('$10.46B'),
    'servido two_venue_total_usd=10460311734.93 y el panel «binance + bybit»: «' +
    corta(swing.slice(swing.indexOf('OI total')), 62) + '»');
}

let _corrida = null;
const corrida = () => {
  if (!_corrida) {
    _corrida = (async () => {
      await carreraOla1();
      await carreraOla2();
      await edadesYFormas();
      return resultado;
    })();
  }
  return _corrida;
};

['A1', 'A2', 'B1', 'B1b', 'F1', 'E1', 'E2', 'E3', 'E4', 'E6', 'D1', 'H1', 'G1'].forEach((id) => {
  test('f12a ' + id + ' no reproduce', async () => {
    const r = (await corrida())[id];
    assert.ok(r, 'el caso ' + id + ' no llego a correr');
    assert.ok(!r.reproduce, id + ' REPRODUCE: ' + r.texto);
  });
});
