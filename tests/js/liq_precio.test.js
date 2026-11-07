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
  assert.strictEqual(l[0], 'liq 10:00:00Z · binance · largo liquidado (venta forzada) · 100 · 10.0 k USD');
  assert.strictEqual(l[1], 'liq 10:00:01Z · binance · corto liquidado (compra forzada) · 101 · 10.0 k USD');
  assert.strictEqual(l[4], 'liq: y 2 más');
  assert.deepStrictEqual(Q.fichaLiq(e, [], t + 60000, t + 120000), ['liq 10:01:00Z · bybit · largo liquidado (venta forzada) · 90 · 50.0 k USD']);
  assert.deepStrictEqual(Q.fichaLiq(e, [], t + 120000, t + 180000), ['liq ≥ 10.0 k USD: ninguna']);
  const sin = [{ desde: t + 120000, hasta: t + 240000, motivo: 'hueco de bybit (unrecoverable): sin dato' }];
  assert.deepStrictEqual(Q.fichaLiq(e, sin, t + 120000, t + 180000), ['liq SIN DATO: hueco de bybit (unrecoverable): sin dato']);
});
