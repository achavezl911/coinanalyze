'use strict';
// A4 (DATOS A, F3-F6): «Dónde reventó ya» decía «Sin liquidaciones ... no es un hueco» con la
// ventana vacía aunque el colector estuviera caído. La ruta sirve ahora feed_alive y su motivo:
// sin feed vivo, una ventana vacía es SIN DATO, y con niveles es lo oído, un mínimo.

const test = require('node:test');
const assert = require('node:assert/strict');
const { cargarApp, Node } = require('./harness');

function monta() {
  const app = cargarApp();
  for (const id of ['heat-liq', 'heat-liq-sub', 'heat-liq-note']) {
    const n = new Node(id === 'heat-liq' ? 'div' : 'p');
    n.id = id;
    app.__dom.porId.set(id, n);
  }
  const nota = () => app.__dom.porId.get('heat-liq-note').textContent;
  return { app, nota };
}

const BASE = { available: true, window_minutes: 180, current_price: 80000, buckets_total: 0, levels: [] };

test('ventana vacia con el feed caido: SIN DATO con su motivo, no «sin liquidaciones»', () => {
  const { app, nota } = monta();
  app.renderLiqPrecio({ ...BASE, feed_alive: false, feed_reason: 'bybit_liquidations_disconnected' });
  assert.match(nota(), /SIN DATO/);
  assert.match(nota(), /bybit_liquidations_disconnected/);
  assert.doesNotMatch(nota(), /Sin liquidaciones/);
});

test('una respuesta sin feed_alive (ruta vieja) tampoco certifica el cero', () => {
  const { app, nota } = monta();
  app.renderLiqPrecio({ ...BASE });
  assert.match(nota(), /SIN DATO/);
});

test('ventana vacia con el feed vivo: sin liquidaciones, es una lectura', () => {
  const { app, nota } = monta();
  app.renderLiqPrecio({ ...BASE, feed_alive: true, feed_reason: null });
  assert.match(nota(), /^Sin liquidaciones en la ventana servida/);
});

test('con niveles y el feed caido: lo oido se pinta y se rotula INCOMPLETO', () => {
  const { app, nota } = monta();
  app.renderLiqPrecio({ ...BASE, buckets_total: 1, feed_alive: false, feed_reason: 'x',
                        levels: [{ price: 80000, long_liq: 10, short_liq: 0 }] });
  assert.match(nota(), /^1 de 1 niveles con liquidaciones\. INCOMPLETO/);
  assert.equal(app.__dom.porId.get('heat-liq').children.length, 1);
});
