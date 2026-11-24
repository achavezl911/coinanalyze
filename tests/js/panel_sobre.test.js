'use strict';
// PANEL R1 · los 9 casos de fable-f12b que cierra el remate P16 (U-03 + S1c, S2, T1, S17, S4, S5).
// El sobre lleva su activo, una vuelta lenta no se pierde ni pisa a una mas nueva, la hora es UTC,
// la portada se vacia al cambiar de activo, la pastilla de directo dice su edad y una fila que
// FALTA abre hueco. Cada caso CAE con main@1296998 y pasa con el remate.

// El navegador no esta en UTC (el caso T1 es justo eso): se fija ANTES de crear ninguna fecha.
process.env.TZ = 'America/Mexico_City';

const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { cargarApp, Node } = require('./harness');

const BTC = 'BTCUSDT_PERP.A';
const ETH = 'ETHUSDT_PERP.A';
const q = s => encodeURIComponent(s);

function puerta() {
  let abre;
  const p = new Promise(r => { abre = r; });
  return { p, abre };
}
const vuelta = () => new Promise(r => setImmediate(r));
async function asienta() { for (let i = 0; i < 20; i++) await vuelta(); }

// Panel con cada id del DOM resuelto a un nodo (memoizado) y el reloj del panel en la mano.
function panel() {
  const app = cargarApp();
  const nodos = new Map();
  app.document.getElementById = id => {
    if (!nodos.has(id)) { const n = new Node('div'); n.id = id; nodos.set(id, n); }
    return nodos.get(id);
  };
  app.__reloj = { t: Date.parse('2026-11-20T01:00:00Z') };
  vm.runInContext('Date.now = () => __reloj.t;', app);
  return app;
}

// ---------------- U-03 (S1a, S1b, S1d) y S1c: el sobre es de UN activo ----------------

test('S1a/S1d · con el sobre de BTC en cache, pedir el de ETH va a la red y no devuelve el de BTC', async () => {
  const app = panel();
  const pedidas = [];
  app.maybe = async path => { pedidas.push(path); return { de: path.includes(q(ETH)) ? 'ETH' : 'BTC' }; };
  assert.equal((await app.pedirSobre(q(BTC))).de, 'BTC');
  const eth = await app.pedirSobre(q(ETH));
  assert.equal(eth.de, 'ETH', 'el sobre de BTC (de hace < 15 s) se sirvio bajo ETH');
  assert.equal(pedidas.length, 2);
});

test('S1d · la peticion en vuelo de BTC no se reparte a quien pide ETH', async () => {
  const app = panel();
  const pBtc = puerta();
  app.maybe = path => (path.includes(q(BTC)) ? pBtc.p : Promise.resolve({ de: 'ETH' }));
  app.pedirSobre(q(BTC));
  const eth = app.pedirSobre(q(ETH));
  pBtc.abre({ de: 'BTC' });
  assert.equal((await eth).de, 'ETH');
});

test('S1b · delSobre no lee el sobre de otro activo: devuelve su relleno', async () => {
  const app = panel();
  app.maybe = async () => ({ trend_matrix: { de: 'BTC' } });
  await app.pedirSobre(q(BTC));
  app.state.symbol = ETH;
  assert.deepEqual(JSON.parse(JSON.stringify(app.delSobre('trend_matrix', { de: 'relleno' }))), { de: 'relleno' });
});

test('S1c · el sobre de BTC que llega tarde, ya en ETH, no se guarda como el sobre', async () => {
  const app = panel();
  const pBtc = puerta();
  const pEth = puerta();
  app.maybe = path => (path.includes(q(BTC)) ? pBtc.p : pEth.p);
  app.pedirSobre(q(BTC));
  app.state.symbol = ETH;
  const eth = app.pedirSobre(q(ETH));
  pBtc.abre({ de: 'BTC' });
  await asienta();
  assert.notEqual(app.state.sobre && app.state.sobre.de, 'BTC', 'el sobre tardio de BTC quedo en state.sobre bajo ETH');
  pEth.abre({ de: 'ETH' });
  assert.equal((await eth).de, 'ETH');
  assert.equal(app.state.sobre.de, 'ETH');
});

// ---------------- S2: la vuelta lenta se pinta si no hay otra MAS NUEVA pintada ----------------

// refreshOverview con el tramo lento fresco (sin contextRequest) y la red por puertas: el sobre
// responde al momento y el resto de rutas de cada vuelta espera a SU puerta (por eso cada vuelta
// se asienta antes de lanzar la siguiente). El primer efecto tras la guarda es renderCarry: se
// registra y se corta ahi (el resto del pintado no es de este caso).
function refrescos() {
  const app = panel();
  app.state.lastContextAt = app.__reloj.t;
  let actual = puerta();
  app.maybe = path => (path.startsWith('/api/ai/context') ? Promise.resolve({}) : actual.p);
  const pintadas = [];
  app.renderCarry = () => { pintadas.push(app.state.symbol); throw new Error('PINTA'); };
  const lanza = async () => {
    const p = puerta();
    actual = p;
    const r = app.refreshOverview().catch(e => { if (e.message !== 'PINTA') throw e; });
    await asienta();
    return { p, r };
  };
  return { app, lanza, pintadas };
}

test('S2 · una vuelta que acaba mientras otra mas nueva sigue en vuelo SE PINTA', async () => {
  const { lanza, pintadas } = refrescos();
  const v1 = await lanza();
  const v2 = await lanza();
  v1.p.abre({ rows: [] });
  await asienta();
  assert.equal(pintadas.length, 1, 'la vuelta 1 llego y no pinto: el panel espera a la 2, que puede no llegar');
  v2.p.abre({ rows: [] });
  await Promise.all([v1.r, v2.r]);
  assert.equal(pintadas.length, 2);
});

test('S2 · la respuesta vieja que llega DESPUES de pintar una mas nueva se rechaza', async () => {
  const { lanza, pintadas } = refrescos();
  const v1 = await lanza();
  const v2 = await lanza();
  v2.p.abre({ rows: [] });
  await asienta();
  v1.p.abre({ rows: [] });
  await Promise.all([v1.r, v2.r]);
  assert.equal(pintadas.length, 1);
});

// ---------------- T1: la hora del tramo es UTC ----------------

test('T1 · tramoISO lee una hora sin zona como UTC, no como la hora del navegador', () => {
  const app = panel();
  assert.equal(app.tramoISO('2026-11-20T01:00:00'), '2026-11-20T01:00:00.000Z');
  assert.equal(app.tramoISO('2026-11-20T01:00:00Z'), '2026-11-20T01:00:00.000Z');
  assert.equal(app.tramoISO('2026-11-20T01:00:00+00:00'), '2026-11-20T01:00:00.000Z');
  assert.equal(app.tramoISO(null), null);
});

// ---------------- S17: la portada es de UN activo ----------------

test('S17 · al cambiar de activo la portada se vacia: sus 11 nodos dicen «—»', () => {
  const app = panel();
  const ids = ['veredicto', 'ventana', 'porque', 'precio', 'precio-pie', 'oi', 'oi-pie', 'carry',
    'carry-pie', 'liq', 'liq-pie'].map(id => 'portada-' + id);
  for (const id of ids) app.document.getElementById(id).textContent = 'de BTC';
  app.clearSnapshotView = () => {};
  app.renderDataConfidence = () => {};
  app.resetPriceScales = () => {};
  app.clearSymbolView();
  assert.deepEqual(ids.filter(id => app.document.getElementById(id).textContent !== '—'), []);
});

// ---------------- S4: la pastilla de directo dice su edad ----------------

test('S4 · tras mas de 30 s sin fila del activo, la pastilla escribe su edad y se apaga', () => {
  const fuentes = [];
  const app = panel();
  app.EventSource = function EventSource() { this.close = () => {}; fuentes.push(this); };
  app.state.symbol = BTC;
  app.connectStream();
  const msg = d => fuentes[0].onmessage({ data: JSON.stringify(d) });
  msg({ rows: [{ symbol: 'BTC', last_px: 100, delta_5s: 1 }], scalp: [],
    books: [{ symbol: BTC, imbalance_l5: 0.6, spread_bps: 1 }] });
  const precio = app.document.getElementById('live-price');
  assert.match(precio.textContent, /^Px /);
  app.__reloj.t += 10000;
  msg({ rows: [], scalp: [], books: [] });
  assert.doesNotMatch(precio.textContent, /hace/, 'a los 10 s todavia no es rancio');
  app.__reloj.t += 30000;
  msg({ rows: [], scalp: [], books: [] });
  assert.match(precio.textContent, /^Px .* · hace 40 s$/);
  assert.equal(precio.className, 'live-pill neutral');
  app.__reloj.t += 5000;
  msg({ rows: [], scalp: [], books: [] });
  assert.match(precio.textContent, /^Px [^·]* · hace 45 s$/, 'la edad se reescribe, no se acumula');
  msg({ rows: [{ symbol: 'BTC', last_px: 101, delta_5s: 1 }], scalp: [], books: [] });
  assert.doesNotMatch(precio.textContent, /hace/);
});

// ---------------- S5: la fila que FALTA abre hueco ----------------

test('S5 · un salto de tiempo sin filas parte la serie igual que una fila nula', () => {
  const app = panel();
  const T = i => 1700000000 + i * 300;
  const filas = [0, 1, 2, 3, 9, 10, 11].map(i => ({ t: T(i), v: 100 + i }));
  const info = app.seriesSegments(filas, r => r.t, r => r.v);
  assert.deepEqual(JSON.parse(JSON.stringify(info.segments.map(s => s.map(p => p.time)))),
    [[T(0), T(1), T(2), T(3)], [T(9), T(10), T(11)]], 'la linea une T3 con T9 como si fuera dato');
  // sin salto, una sola linea
  const seguidas = [0, 1, 2, 3, 4].map(i => ({ t: T(i), v: 100 + i }));
  assert.equal(app.seriesSegments(seguidas, r => r.t, r => r.v).segments.length, 1);
});
