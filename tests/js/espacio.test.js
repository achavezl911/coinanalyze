'use strict';
/* Lo puro de /espacio (campana OF-6b, static/espacio/espacio.js): el hash de ida y vuelta y el que no se entiende.
 * Se llama a las funciones de verdad, como flujo_trazos.test.js. */
const test = require('node:test');
const assert = require('node:assert');
const S = require('../../static/espacio/espacio.js');

const DEF = { disp: '1', vistas: [''] };

test('hash: ida y vuelta en las cuatro disposiciones, con vistas de /flujo enteras', () => {
  const vistas = ['BTC/1m/perp', 'BTC/5m/perp/hasta=2026-11-15T10:00:00Z/capas=vwap,poc', 'ETH/5m/perp/min=2.5',
                  'BTC/1h/perp/modo=tpo'];
  for (const [disp, n] of [['1', 1], ['2h', 2], ['2v', 2], ['4', 4]]) {
    const e = { disp, vistas: vistas.slice(0, n) };
    const h = S.escribeHashEspacio(e);
    assert.deepStrictEqual(S.leeHashEspacio(h), e, h);
    assert.strictEqual(S.escribeHashEspacio(S.leeHashEspacio(h)), h);
  }
  // legible: las barras y los iguales de la vista no se codifican
  assert.strictEqual(S.escribeHashEspacio({ disp: '2h', vistas: ['BTC/1m/perp', '#ETH/5m/perp'] }),
                     '#d=2h&v=BTC/1m/perp&v=ETH/5m/perp');
});

test('hash: con menos vistas que marcos, las que faltan van a la vista por omision; de mas no se escriben', () => {
  assert.deepStrictEqual(S.leeHashEspacio('#d=4&v=BTC/1m/perp'), { disp: '4', vistas: ['BTC/1m/perp', '', '', ''] });
  assert.deepStrictEqual(S.leeHashEspacio('#d=2v'), { disp: '2v', vistas: ['', ''] });
  assert.strictEqual(S.escribeHashEspacio({ disp: '1', vistas: ['A', 'B', 'C'] }), '#d=1&v=A');
});

test('hash: lo que no se entiende cae al defecto (1 marco, vista por omision)', () => {
  for (const h of ['', '#', 'basura', '#d=3', '#d=4&d=4', '#v=BTC/1m/perp', '#d=1&v=A&v=B', '#d=1&x=1',
                   '#d=1&v=%E0%A4%A', '#d=1&v=BTC%231m', '#d=1&v=<script>', '#d=2h&v=BTC 1m', '#d=1&v']) {
    assert.deepStrictEqual(S.leeHashEspacio(h), DEF, h);
  }
  assert.strictEqual(S.escribeHashEspacio(S.leeHashEspacio('#d=9')), '#d=1&v=');
  assert.strictEqual(S.srcMarco(''), '/flujo');
  assert.strictEqual(S.srcMarco('ETH/5m/perp'), '/flujo#ETH/5m/perp');
});
