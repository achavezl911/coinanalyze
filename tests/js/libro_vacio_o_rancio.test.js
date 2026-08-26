'use strict';
// K13 — vacio y rancio no se pueden ver igual.
//
// /api/scalp/orderbook filtra ts >= now()-30s: un libro viejo llega como CERO filas y la
// tabla queda vacia, exactamente igual que cuando no hay libro. La distincion viene fuera
// de rows y el panel tiene que pintarla; si el servidor lo declara y el panel lo calla, no
// llega a quien decide.

const test = require('node:test');
const assert = require('node:assert/strict');
const { cargarApp, leerIndexHtml, Node } = require('./harness');

function panel() {
  const app = cargarApp();
  const body = Object.assign(new Node('tbody'), { id: 'orderbook-body' });
  const nota = Object.assign(new Node('p'), { id: 'orderbook-note' });
  app.__dom.porId.set(body.id, body);
  app.__dom.porId.set(nota.id, nota);
  return { app, body, nota };
}

test('el hueco donde va la nota existe en el documento real', () => {
  assert.ok(leerIndexHtml().todosLosIds.has('orderbook-note'));
});

test('libro rancio: cero filas, pero el panel dice que es viejo y cuanto', () => {
  const { app, body, nota } = panel();
  app.renderOrderbook({
    rows: [],
    freshness: { status: 'stale', age_seconds: 412.5, max_age_seconds: 30, as_of: '2026-08-26T01:00:00+00:00' },
  });
  assert.equal(body.children.length, 0);
  assert.match(nota.textContent, /RANCIO/);
  assert.match(nota.textContent, /412\.5 s/);
  assert.match(nota.textContent, /corte 30 s/);
  assert.ok(nota.className.includes('has-gaps'));
});

test('sin libro: cero filas y el panel NO dice que sea viejo', () => {
  const { app, nota } = panel();
  app.renderOrderbook({
    rows: [],
    freshness: { status: 'empty', age_seconds: null, max_age_seconds: 30, as_of: null },
  });
  assert.match(nota.textContent, /Sin libro/);
  assert.doesNotMatch(nota.textContent, /RANCIO/);
  assert.ok(nota.className.includes('has-gaps'));
});

test('los dos casos vacios NO dicen lo mismo, que es el punto de la unidad', () => {
  const { app } = panel();
  const rancio = app.orderbookNote({ status: 'stale', age_seconds: 60, max_age_seconds: 30 }, 0);
  const vacio = app.orderbookNote({ status: 'empty', age_seconds: null, max_age_seconds: 30 }, 0);
  assert.notEqual(rancio, vacio);
});

test('libro fresco: pinta las filas, dice la edad y no se marca en ambar', () => {
  const { app, body, nota } = panel();
  app.renderOrderbook({
    rows: [
      { exchange: 'binance', spread_bps: 1.2, imbalance_l1: 0.51 },
      { exchange: 'bybit', spread_bps: 1.5, imbalance_l1: 0.49 },
    ],
    freshness: { status: 'fresh', age_seconds: 2.4, max_age_seconds: 30, as_of: '2026-08-26T01:00:00+00:00' },
  });
  assert.equal(body.children.length, 2);
  assert.match(nota.textContent, /2 venues/);
  assert.match(nota.textContent, /2\.4 s/);
  assert.ok(!nota.className.includes('has-gaps'));
});

test('sin respuesta no se afirma ni que falte el libro ni que sea viejo', () => {
  const { app, nota } = panel();
  // Es el respaldo de maybe() cuando la peticion falla: no trae freshness.
  app.renderOrderbook({ rows: [] });
  assert.doesNotMatch(nota.textContent, /RANCIO/);
  assert.doesNotMatch(nota.textContent, /Sin libro/);
  assert.match(nota.textContent, /no respondio|no declara/);
  assert.ok(nota.className.includes('has-gaps'));
});

test('una edad ilegible no se convierte en un numero inventado', () => {
  const { app } = panel();
  const texto = app.orderbookNote({ status: 'stale', age_seconds: 'hace mucho', max_age_seconds: 30 }, 0);
  assert.match(texto, /sin decir de cuando/);
});
