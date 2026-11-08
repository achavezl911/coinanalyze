'use strict';
// LAS LIQUIDACIONES SOBRE EL PRECIO (campana 150) · lo puro de static/flujo/flujo-liq.js: la regla del radio (el AREA
// proporcional a los USD), el umbral, lo que la ruta no cubre (se dice, no es «ninguna») y las lineas de la ficha.

const test = require('node:test');
const assert = require('node:assert');
const Q = require('../../static/flujo/flujo-liq.js');

const ev = (ts, lado, usd, precio, exchange) => ({ ts, exchange: exchange || 'binance', lado, usd: String(usd),
                                                   precio: String(precio), cantidad: '1' });

test('el radio: el AREA es proporcional a los USD entre el minimo y el maximo', () => {
  assert.strictEqual(Q.radioLiq(10000), 3);
  assert.strictEqual(Q.radioLiq(40000), 6); // 4 veces los USD, 4 veces el area, 2 veces el radio
  assert.ok(Math.abs(Q.radioLiq(90000) - 9) < 1e-12);
  assert.strictEqual(Q.radioLiq(100), 3); // el minimo visible
  assert.strictEqual(Q.radioLiq(5e6), 18); // el maximo
  const a = (u) => Q.radioLiq(u) ** 2;
  assert.ok(Math.abs(a(250000) / a(50000) - 5) < 1e-9);
});

test('el umbral: por omision 10 mil, y >= (no >)', () => {
  const s = { eventos: [ev('2026-11-07T10:00:00.000Z', 'long', 9999.99, 100), ev('2026-11-07T10:00:01.000Z', 'short', 10000, 101),
                        ev('2026-11-07T10:00:02.000Z', 'long', 250000, 99)] };
  const e = Q.sobreUmbralLiq(Q.eventosLiq(s));
  assert.deepStrictEqual(e.map((x) => [x.lado, x.usd, x.precio]), [['short', 10000, 101], ['long', 250000, 99]]);
  assert.strictEqual(Q.sobreUmbralLiq(Q.eventosLiq(s), 1000).length, 3);
});

test('lo que la ruta no cubre se dice: retencion, corte y hueco (no el recuperado)', () => {
  const A = Date.parse('2026-11-07T10:00:00Z');
  const B = Date.parse('2026-11-07T12:00:00Z');
  const s = { retencion_h: 720, desde_dato: '2026-11-07T10:30:00.000Z', truncada: true,
              eventos: [ev('2026-11-07T11:00:00.000Z', 'long', 20000, 100)],
              huecos: [{ exchange: 'bybit', desde: '2026-11-07T11:10:00.000Z', hasta: '2026-11-07T11:20:00.000Z', estado: 'unrecoverable' },
                       { exchange: 'binance', desde: '2026-11-07T11:30:00.000Z', hasta: '2026-11-07T11:40:00.000Z', estado: 'recovered' }] };
  const sin = Q.sinDatoLiq(s, A, B);
  assert.deepStrictEqual(sin.map((x) => [new Date(x.desde).toISOString().slice(11, 16), new Date(x.hasta).toISOString().slice(11, 16)]),
                         [['10:00', '10:30'], ['11:00', '12:00'], ['11:10', '11:20']]);
  assert.deepStrictEqual(Q.sinDatoLiq(null, A, B).length, 1);
  assert.deepStrictEqual(Q.sinDatoLiq({ desde_dato: '2026-11-07T10:00:00.000Z', eventos: [], huecos: [] }, A, B), []);
});

test('la ficha: las de su tramo, cuantas mas si no caben, «ninguna» solo con dato, y SIN DATO en un hueco', () => {
  const s = { eventos: [0, 1, 2, 3, 4, 5].map((k) => ev('2026-11-07T10:00:0' + k + '.000Z', k % 2 ? 'short' : 'long', 10000 + k, 100 + k))
    .concat([ev('2026-11-07T10:01:00.000Z', 'long', 50000, 90, 'bybit')]), huecos: [] };
  const e = Q.sobreUmbralLiq(Q.eventosLiq(s));
  const t = Date.parse('2026-11-07T10:00:00Z');
  const l = Q.fichaLiq(e, [], t, t + 60000);
  assert.strictEqual(l.length, 5);
  assert.strictEqual(l[0], 'liq 10:00:00Z · binance · largo liquidado (venta forzada) · ejecución: sin dato · orden a 100 · 10.0 k USD');
  assert.strictEqual(l[1], 'liq 10:00:01Z · binance · corto liquidado (compra forzada) · ejecución: sin dato · orden a 101 · 10.0 k USD');
  assert.strictEqual(l[4], 'liq: y 2 más');
  assert.deepStrictEqual(Q.fichaLiq(e, [], t + 60000, t + 120000), ['liq 10:01:00Z · bybit · largo liquidado (venta forzada) · ejecución: sin dato · orden a 90 · 50.0 k USD']);
  assert.deepStrictEqual(Q.fichaLiq(e, [], t + 120000, t + 180000), ['liq ≥ 10.0 k USD: ninguna']);
  const sin = [{ desde: t + 120000, hasta: t + 240000, motivo: 'hueco de bybit (unrecoverable): sin dato' }];
  assert.deepStrictEqual(Q.fichaLiq(e, sin, t + 120000, t + 180000), ['liq SIN DATO: hueco de bybit (unrecoverable): sin dato']);
});

test('la cascada: >= n del mismo lado en s segundos, episodios unidos si comparten eventos, null sin regla', () => {
  const R = { n: 5, s: 60 };
  const t = (seg) => new Date(Date.parse('2026-11-07T10:00:00Z') + seg * 1000).toISOString();
  const s = { eventos: [0, 10, 20, 30].map((k) => ev(t(k), 'long', 100, 100)) // 4: no
    .concat([0, 15, 30, 45, 60, 100].map((k) => ev(t(200 + k), 'short', 1000, 100))) // 5 en 60 s justos, y una mas
    .concat([0, 1, 2, 3, 4, 70, 71, 72, 73, 74].map((k) => ev(t(400 + k), 'long', 10, 100))) }; // dos rachas
  const c = Q.cascadasLiq(Q.eventosLiq(s), R);
  const t0 = Date.parse(t(0));
  assert.deepStrictEqual(c.map((x) => [x.lado, (x.desde - t0) / 1000, (x.hasta - t0) / 1000, x.n, x.usd]),
                         [['short', 200, 260, 5, 5000], ['long', 400, 404, 5, 50], ['long', 470, 474, 5, 50]]);
  assert.strictEqual(Q.cascadasLiq(Q.eventosLiq(s), null), null);
  assert.strictEqual(Q.cascadasLiq(Q.eventosLiq(s), { n: 4, s: 60 }).filter((x) => x.lado === 'long').length, 3);
  assert.strictEqual(Q.textoCascada(c[0]), 'cascada de cortos (compra forzada) · 10:03:20–10:04:20Z · 5 liq · 5.0 k USD');
});

// remate 1 (campana 150): `precio` es la p de la orden forzada; el circulo va en `ejecucion` y sin ella no se pinta
const ex = (ts, lado, usd, p, ej, fuente, venue, exchange) => Object.assign(ev(ts, lado, usd, p, exchange),
  { ejecucion: ej, ejecucion_fuente: fuente }, venue ? { ejecucion_impresion: { ts, venue, compra: lado === 'short', usd: '1' } } : {});

test('la ejecucion: ap o cinta con su fuente, sin dato aparte, y la ficha da las dos con la p de la orden', () => {
  const s = { eventos: [ex('2026-11-07T20:47:18.056Z', 'long', 298600, '75368.4', '75661.5', 'ap'),
                        ex('2026-11-07T20:48:48.931Z', 'long', 49600, '75385.1', '75629.1', 'cinta', 'bybit_linear', 'bybit'),
                        ex('2026-11-07T20:49:00.000Z', 'short', 20000, '75800', null, 'sin_dato'),
                        ex('2026-11-07T20:49:01.000Z', 'short', 20000, '75800', 'NaN', 'cinta', 'binance_usdm')] };
  const e = Q.eventosLiq(s);
  assert.deepStrictEqual(e.map((x) => [x.precio, x.ejecucion, x.fuente, x.venue]),
    [[75368.4, 75661.5, 'ap', null], [75385.1, 75629.1, 'cinta', 'bybit_linear'], [75800, null, 'sin_dato', null],
     [75800, null, 'sin_dato', null]]);
  const [con, sin] = Q.parteLiq(e);
  assert.deepStrictEqual([con.length, sin.length], [2, 2]);
  const t = Date.parse('2026-11-07T20:47:00Z');
  assert.deepStrictEqual(Q.fichaLiq(con, [], t, t + 180000, undefined, undefined, sin), [
    'liq 20:47:18Z · binance · largo liquidado (venta forzada) · ejecución 75661.5 (ap de binance) · orden a 75368.4 · 298.6 k USD',
    'liq 20:48:48Z · bybit · largo liquidado (venta forzada) · ejecución 75629.1 (cinta de bybit_linear) · orden a 75385.1 · 49.6 k USD',
    'liq 20:49:00Z · binance · corto liquidado (compra forzada) · ejecución: sin dato · orden a 75800 · 20.0 k USD',
    'liq 20:49:01Z · binance · corto liquidado (compra forzada) · ejecución: sin dato · orden a 75800 · 20.0 k USD']);
  assert.strictEqual(Q.fichaLiq(con, [], t, t + 180000, undefined, 3, sin)[3], 'liq: y 1 más');
});

test('la ficha de /libro: las liquidaciones y cascadas de la COLUMNA [ts_j, ts_j + cada), no las de su minuto', () => {
  Object.assign(global, require('../../static/flujo/flujo-calculo.js'), require('../../static/libro/libro-calculo.js'), Q);
  const Mp = require('../../static/libro/libro-mapa.js');
  const t = Date.parse('2026-11-07T20:47:00Z');
  const s = { eventos: [ex('2026-11-07T20:47:10.000Z', 'long', 20000, '100', '101', 'ap'),
                        ex('2026-11-07T20:47:40.000Z', 'short', 30000, '102', null, 'sin_dato')], huecos: [] };
  const [eventos, sinPrecio] = Q.parteLiq(Q.sobreUmbralLiq(Q.eventosLiq(s)));
  const cas = (d, h) => ({ lado: 'long', desde: Date.parse(d), hasta: Date.parse(h), n: 5, usd: 1 });
  const m = { paso: '10', unidad: 'base', N: 2, cada: 30, columnas: [{ ts: t, estado: 'hueco', suma: null },
    { ts: t + 30000, estado: 'hueco', suma: null }],
              liq: { eventos, sinPrecio, sinDato: [], cascadas: [cas('2026-11-07T20:46:00Z', '2026-11-07T20:47:05Z'),
                                                               cas('2026-11-07T20:47:31Z', '2026-11-07T20:47:50Z')] } };
  const liq = (j) => Mp.fichaDe(m, j, 10, null).lineas.filter((x) => x[0] === 'liq').map((x) => x[1]);
  const a = liq(0);
  const b = liq(1);
  assert.strictEqual(a.length, 2, a.join('\n'));
  assert.match(a[0], /^liq 20:47:10Z .* ejecución 101 \(ap de binance\) · orden a 100 /);
  assert.match(a[1], /^cascada de largos .* 20:46:00–20:47:05Z/);
  assert.strictEqual(b.length, 2, b.join('\n'));
  assert.match(b[0], /^liq 20:47:40Z .* ejecución: sin dato · orden a 102 /);
  assert.match(b[1], /20:47:31–20:47:50Z/);
  assert.deepStrictEqual(Mp.fichaDe(m, 1, 10, null).liq, { desde: '2026-11-07T20:47:30Z', hasta: '2026-11-07T20:48:00Z' });
});
