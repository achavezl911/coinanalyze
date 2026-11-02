'use strict';
// REMATE 1 DE LA 148 · la fuente por vista (acercar el precio o ensanchar la vela no esconde una cifra) y la etiqueta
// del precio en vivo (adenda). Se llaman las funciones de verdad (static/flujo/flujo-dibujo.js).

const test = require('node:test');
const assert = require('node:assert');
const D = require('../../static/flujo/flujo-dibujo.js');

// un monoespaciado de 0.6 em: lo que mide fillText en Chromium para ui-monospace, redondeado
const ancho = (t, b, f) => t.length * f * 0.6 + (b ? 1 : 0);
const celda = (hueco, ...txt) => ({ hueco, piezas: txt.map((t) => [t, false]) });

test('la fuente sube hasta el techo cuando todo cabe', () => {
  assert.strictEqual(D.fuenteVista([celda(40, '1.2', '3.4')], 13, ancho), 13);
});

test('la fuente se queda en la mayor con la que cabe la cifra mas ancha (BTC 15m, 74 px por vela)', () => {
  // 37 px por mitad: '12.34' (5 car.) cabe a 10 (30 + 4) y no a 11 (33 + 4 = 37 si, a 12 no); la vista lleva 11
  const c = [celda(37, '12.34', '0.512'), celda(37, '1.2', '3')];
  assert.strictEqual(D.fuenteVista(c, 13, ancho), 11);
  const f = D.fuenteVista(c, 13, ancho);
  c.forEach((x) => x.piezas.forEach(([t, b]) => assert.ok(ancho(t, b, f) + 4 <= x.hueco)));
});

test('una cifra que no cabe ni a 9 px no baja la fuente de las demas', () => {
  const c = [celda(20, '1.2', '3'), celda(20, '123.456', '1')];
  assert.strictEqual(D.fuenteVista(c, 13, ancho), 13);
});

test('nunca por debajo de 9 px ni por encima del techo', () => {
  assert.strictEqual(D.fuenteVista([celda(32, '99999')], 13, ancho), 9); // cabe a 9 (31 px) y no a 10 (34)
  assert.strictEqual(D.fuenteVista([celda(5, '99999')], 13, ancho), 13); // no sale a ningun tamano: no cuenta
  assert.strictEqual(D.fuenteVista([], 10, ancho), 10);
  assert.strictEqual(D.fuenteVista([celda(1000, '1')], 9, ancho), 9);
});

test('LA MONOTONIA: con el mismo ancho, subir el techo (acercar el precio) no echa ninguna cifra', () => {
  const c = [celda(37, '12.34', '0.512'), celda(37, '81.2K', '7.77'), celda(37, '1', '2')];
  let antes = null;
  for (let tope = 9; tope <= 13; tope++) {
    const f = D.fuenteVista(c, tope, ancho);
    const salen = c.filter((x) => x.piezas.every(([t, b]) => ancho(t, b, f) + 4 <= x.hueco)).length;
    if (antes !== null) assert.ok(salen >= antes, 'tope ' + tope + ': ' + salen + ' < ' + antes);
    antes = salen;
  }
  assert.strictEqual(antes, 3);
});

test('LA MONOTONIA: con el mismo techo, ensanchar la vela no echa ninguna cifra', () => {
  let antes = null;
  for (let h = 20; h <= 60; h += 2) {
    const c = [celda(h, '12.34', '0.512'), celda(h, '81.2K', '7.77'), celda(h, '1', '2')];
    const f = D.fuenteVista(c, 12, ancho);
    const salen = c.filter((x) => x.piezas.every(([t, b]) => ancho(t, b, f) + 4 <= x.hueco)).length;
    if (antes !== null) assert.ok(salen >= antes, 'hueco ' + h);
    antes = salen;
  }
});

const T0 = Date.parse('2026-11-02T22:00:00Z');
const dato = (o) => ({ venue: 'binance_usdm', precio: '81361.4', tsMs: T0 - 500, asOfMs: T0, recibidoMs: T0, ok: true, ...o });

test('la etiqueta en vivo: el precio con los decimales del activo, el venue y la edad', () => {
  const e = D.etiquetaVivo(dato(), 3, T0 + 1000);
  assert.strictEqual(e.texto, '81361.400');
  assert.strictEqual(e.venue, 'binance_usdm');
  assert.strictEqual(e.estado, 'vivo');
  assert.strictEqual(e.edad_s, 1.5);
  assert.strictEqual(e.aviso, 'vivo 1s');
  assert.strictEqual(D.etiquetaVivo(dato({ precio: 2510.456 }), 2, T0).texto, '2510.46');
});

test('mas de 10 s sin operacion, o sin respuesta: «sin vivo» con su edad', () => {
  const e = D.etiquetaVivo(dato(), 3, T0 + 12000);
  assert.strictEqual(e.estado, 'sin vivo');
  assert.strictEqual(e.aviso, 'sin vivo 12s');
  assert.strictEqual(D.etiquetaVivo(dato({ ok: false }), 3, T0 + 1000).estado, 'sin vivo');
  assert.strictEqual(D.etiquetaVivo(dato(), 3, T0 + 600000).aviso, 'sin vivo 10m');
  assert.strictEqual(D.etiquetaVivo(dato(), 3, T0 + 9000).estado, 'vivo');
});

test('sin ninguna operacion conocida, ningun precio (lo ausente no es cero)', () => {
  assert.strictEqual(D.etiquetaVivo(null, 3, T0), null);
  assert.strictEqual(D.etiquetaVivo(dato({ precio: null }), 3, T0), null);
  assert.strictEqual(D.etiquetaVivo(dato({ precio: 'x' }), 3, T0), null);
});
