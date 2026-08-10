'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { cargarApp, Node } = require('./harness');

function appConDailyBars() {
  const app = cargarApp();
  const body = new Node('div');
  body.id = 'dailybars-body';
  const sub = new Node('span');
  sub.id = 'dailybars-sub';
  app.__dom.porId.set(body.id, body);
  app.__dom.porId.set(sub.id, sub);
  return { app, body, sub };
}

function row(overrides = {}) {
  return {
    session_date: '2026-08-08',
    cvd_spot_usd: -100,
    cvd_fut_usd: -200,
    price_open: 100,
    price_high: 105,
    price_low: 95,
    price_close: 98,
    price_chg_pct: -2,
    price_response: 'venta_con_caida',
    ...overrides,
  };
}

test('sessionOhlc exige las cuatro patas y nunca convierte ausencia en cero', () => {
  const { app } = appConDailyBars();
  assert.equal(app.sessionOhlc(row({ price_high: null })), null);
  assert.equal(app.sessionOhlc(row({ price_open: '' })), null);
  assert.equal(app.sessionOhlc(row({ price_low: false })), null);
  assert.equal(app.sessionOhlc(row({ price_close: 0 })), null);

  const candle = app.sessionOhlc(row());
  assert.equal(candle.open, 100);
  assert.equal(candle.high, 105);
  assert.equal(candle.low, 95);
  assert.equal(candle.close, 98);
});

test('sessionOhlc rechaza OHLC geometricamente imposible', () => {
  const { app } = appConDailyBars();
  assert.equal(app.sessionOhlc(row({ price_high: 99 })), null);
  assert.equal(app.sessionOhlc(row({ price_low: 101 })), null);
  assert.equal(app.sessionOhlc(row({ price_high: 90, price_low: 110 })), null);
});

test('sessionPriceDomain usa solo velas completas y conserva el hueco', () => {
  const { app } = appConDailyBars();
  const domain = app.sessionPriceDomain([
    row({ price_low: 90, price_high: 110 }),
    row({ session_date: '2026-08-09', price_high: null }),
    row({ session_date: '2026-08-10', price_low: 80, price_high: 120 }),
  ]);
  assert.equal(domain.present, 2);
  assert.equal(domain.missing, 1);
  assert.equal(domain.observed_low, 80);
  assert.equal(domain.observed_high, 120);
  assert.ok(domain.min < 80);
  assert.ok(domain.max > 120);
});

test('renderDailyBars alinea vela y barra por la misma session_date', () => {
  const { app, body, sub } = appConDailyBars();
  app.renderDailyBars({
    rows: [
      row({ session_date: '2026-08-08' }),
      row({
        session_date: '2026-08-09',
        cvd_spot_usd: 150,
        cvd_fut_usd: 250,
        price_open: 98,
        price_high: 104,
        price_low: 97,
        price_close: 103,
        price_chg_pct: 5.102,
        price_response: 'compra_con_subida',
      }),
    ],
  });

  const nodes = body.walk();
  const candles = nodes.filter(node => node.classList.contains('session-price-candle'));
  const flows = nodes.filter(node => node.classList.contains('session-flow-bar'));
  const priceSvg = nodes.find(node => node.classList.contains('session-price-svg'));
  const flowSvg = nodes.find(node => node.classList.contains('session-flow-svg'));

  assert.ok(priceSvg, 'debe existir track OHLC');
  assert.ok(flowSvg, 'debe existir track de flujo');
  assert.equal(candles.length, 2);
  assert.equal(flows.length, 2);

  for (const iso of ['2026-08-08', '2026-08-09']) {
    assert.ok(candles.some(node => node.getAttribute('data-session-date') === iso));
    assert.ok(flows.some(node => node.getAttribute('data-session-date') === iso));
  }
  assert.match(sub.textContent, /OHLC 2\/2/);
});

test('una sesion sin OHLC deja hueco arriba pero conserva flujo medido abajo', () => {
  const { app, body, sub } = appConDailyBars();
  app.renderDailyBars({
    rows: [
      row({ session_date: '2026-08-08' }),
      row({
        session_date: '2026-08-09',
        price_high: null,
        cvd_spot_usd: -50,
        cvd_fut_usd: 80,
        price_response: 'flujo_dividido',
      }),
    ],
  });

  const nodes = body.walk();
  const candles = nodes.filter(node => node.classList.contains('session-price-candle'));
  const flows = nodes.filter(node => node.classList.contains('session-flow-bar'));

  assert.equal(candles.length, 1, 'no debe fabricar una vela para OHLC incompleto');
  assert.equal(flows.length, 2, 'el flujo medido no se pierde por faltar precio');
  assert.match(sub.textContent, /OHLC 1\/2/);
});

test('si no hay ninguna vela completa se declara N/D y no se fabrica precio', () => {
  const { app, body } = appConDailyBars();
  app.renderDailyBars({
    rows: [
      row({ price_open: null }),
      row({ session_date: '2026-08-09', price_low: null }),
    ],
  });

  const nodes = body.walk();
  assert.equal(nodes.filter(node => node.classList.contains('session-price-candle')).length, 0);
  const empty = nodes.find(node => node.classList.contains('session-map-empty'));
  assert.ok(empty);
  assert.match(empty.textContent, /no disponible/i);
  assert.equal(nodes.filter(node => node.classList.contains('session-flow-bar')).length, 2);
});
