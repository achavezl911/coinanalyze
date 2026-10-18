'use strict';
// LOS INDICADORES (campana 146, OF-5a) · lo que la pagina calcula para los paneles y la cinta: las claves nuevas del
// hash, el CVD EXACTO (y que tras un hueco vuelve a 0), el cambio de una serie de nivel, y el precio que escribe la
// cinta. Se llaman las funciones de verdad (static/flujo/flujo-calculo.js, flujo-indicadores.js, flujo-cinta.js).

const test = require('node:test');
const assert = require('node:assert');
const F = require('../../static/flujo/flujo-calculo.js');

Object.assign(globalThis, F); // flujo-indicadores.js usa decimales() y entero() de flujo-calculo.js, como en la pagina
const I = require('../../static/flujo/flujo-indicadores.js');
const C = require('../../static/flujo/flujo-cinta.js');

test('el hash de los indicadores: sin la clave, lo de por omision; ninguno; el orden es el de la pantalla', () => {
  const e = F.leeHash('#BTC/1m/perp');
  assert.deepStrictEqual([e.ind, e.cinta], [['delta', 'cvd', 'grandes', 'cinta'], null]);
  assert.strictEqual(F.escribeHash(e), '#BTC/1m/perp');
  const t = F.leeHash('#ETH/15m/perp/hasta=2026-10-18T13:00:00Z/ind=liq,oi,delta,nada/cinta=50000');
  assert.deepStrictEqual([t.ind, t.cinta], [['delta', 'oi', 'liq'], '50000']);
  assert.strictEqual(F.escribeHash(t), '#ETH/15m/perp/hasta=2026-10-18T13:00:00Z/ind=delta,oi,liq/cinta=50000');
  assert.deepStrictEqual(F.leeHash('#BTC/1m/perp/ind=ninguno').ind, []);
  assert.strictEqual(F.escribeHash(F.leeHash('#BTC/1m/perp/ind=ninguno')), '#BTC/1m/perp/ind=ninguno');
  // lo que no se entiende cae al defecto: una lista sin nada conocido, un filtro que no es un numero positivo
  const malo = F.leeHash('#BTC/1m/perp/ind=nada,otra/cinta=-5');
  assert.deepStrictEqual([malo.ind, malo.cinta], [F.INDICADORES_DEFECTO, null]);
  // las vistas de K109 (sin la clave) siguen siendo las mismas
  ['#BTC/1m/perp/5/hasta=2026-10-17T11:30:00Z/ver=20', '#BTC/5m/perp/hasta=2026-10-17T11:30:00Z/ver=60/capas=perfil,vwap']
    .forEach((h) => assert.strictEqual(F.escribeHash(F.leeHash(h)), h));
});

test('el CVD es exacto, empieza en la primera vela y tras un hueco vuelve a 0 (no se suma lo que no se escucho)', () => {
  const velas = [
    { ts: 'a', delta: '0.1', estado: 'completa' }, { ts: 'b', delta: '0.2', estado: 'incompleta' },
    { ts: 'c', delta: '0', estado: 'hueco' }, { ts: 'd', delta: '-1.25', estado: 'completa' },
    { ts: 'e', delta: '3', estado: 'abierta' }];
  assert.deepStrictEqual(I.cvdDe(velas), [
    { ts: 'a', valor: '0.1', origen: 'a' }, { ts: 'b', valor: '0.3', origen: 'a' }, // en float, 0.30000000000000004
    { ts: 'c', valor: null, origen: null }, { ts: 'd', valor: '-1.25', origen: 'd' }, { ts: 'e', valor: '1.75', origen: 'd' }]);
  assert.strictEqual(I.deEntero(-5n, 2), '-0.05');
  assert.strictEqual(I.deEntero(0n, 3), '0');
});

test('el cambio de una serie de nivel solo existe entre dos cubos con dato', () => {
  const cubos = [{ ts: 'a', valores: { oi: '100.5' } }, { ts: 'b', valores: { oi: '99.25' } }, { ts: 'c', valores: null },
                 { ts: 'd', valores: { oi: '101' } }];
  assert.deepStrictEqual(I.cambiosDe(cubos, 'oi').map((x) => x.valor), [null, '-1.25', null, null]);
});

test('la cinta: el filtro por omision de P2 por activo, y el precio hasta donde llego la orden', () => {
  assert.deepStrictEqual(['BTC', 'ETH', 'SOL'].map((a) => C.filtroCinta({ activo: a, cinta: null })),
    ['200000', '200000', '50000']);
  assert.strictEqual(C.filtroCinta({ activo: 'BTC', cinta: '50000' }), '50000');
  assert.strictEqual(C.precioCinta({ agresor: 'compra', precio_min: '100', precio_max: '102' }), '102↑');
  assert.strictEqual(C.precioCinta({ agresor: 'venta', precio_min: '100', precio_max: '102' }), '100↓');
  assert.strictEqual(C.precioCinta({ agresor: 'venta', precio_min: '100', precio_max: '100' }), '100');
});
