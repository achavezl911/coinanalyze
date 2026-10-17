'use strict';
// LOS PERFILES (campana 143, OF-3) · lo que la pagina calcula para las capas y el TPO (static/flujo/flujo-calculo.js):
// las claves nuevas del hash, donde empiezan las sesiones (una que cruza la medianoche es UNA) y el estado que se
// escribe sobre cada capa. Se llaman las funciones de verdad.

const test = require('node:test');
const assert = require('node:assert');
const F = require('../../static/flujo/flujo-calculo.js');

test('el hash de las capas: sin claves nuevas es el footprint de la 142, y va y vuelve', () => {
  const e = F.leeHash('#BTC/5m/perp/sesion=22:00-06:00/capas=vwap,perfil,nada/compuesto=7/' +
    'fijo=2026-10-17T10:00:00Z,2026-10-17T11:00:00Z/hasta=2026-10-17T12:00:00Z');
  assert.deepStrictEqual([e.sesion, e.capas, e.compuesto, e.fijo, e.modo, e.paso],
    ['22:00-06:00', ['perfil', 'vwap'], 7, ['2026-10-17T10:00:00Z', '2026-10-17T11:00:00Z'], 'footprint', 'auto']);
  assert.strictEqual(F.escribeHash(e), '#BTC/5m/perp/hasta=2026-10-17T12:00:00Z/sesion=22:00-06:00/' +
    'capas=perfil,vwap/compuesto=7/fijo=2026-10-17T10:00:00Z,2026-10-17T11:00:00Z');
  ['#BTC/1m/perp', '#ETH/1m/perp/modo=tpo/sesiones=5', '#SOL/5m/spot/sesion=eeuu/capas=dinamico']
    .forEach((h) => assert.strictEqual(F.escribeHash(F.leeHash(h)), h));
  // lo que no se entiende cae al defecto: una sesion imposible, un compuesto de una, un fijo al reves, otro modo
  const malo = F.leeHash('#BTC/1m/perp/sesion=25:00-01:00/compuesto=1/fijo=2026-10-17T11:00:00Z,2026-10-17T10:00:00Z/' +
    'modo=libro/sesiones=0');
  assert.deepStrictEqual([malo.sesion, malo.compuesto, malo.fijo, malo.modo, malo.sesiones],
    ['dia', null, null, 'footprint', F.TPO_SESIONES]);
  assert.strictEqual(F.leeHash('#BTC/1m/perp/compuesto=99').compuesto, F.SESIONES_MAXIMO);
});

test('las capas de sesion no piden mas de las 7 ultimas sesiones (el tope de la ruta) y lo dicen', () => {
  const dia = F.leeSesion('dia');
  const w4h = F.ventana(F.leeHash('#BTC/4h/perp/hasta=2026-10-17T12:00Z'), 0);
  assert.deepStrictEqual(F.ventanaCapas(w4h, dia, '4h'),
    { desde: '2026-10-11T00:00:00Z', hasta: '2026-10-17T12:00:00Z', recortada: true });
  // eeuu empieza a las 13:30: el desde se adelanta al primer borde de vela de 1h que no pasa del tope
  const w1h = F.ventana(F.leeHash('#BTC/1h/perp/hasta=2026-10-17T12:00Z'), 0);
  assert.strictEqual(F.ventanaCapas(w1h, F.leeSesion('eeuu'), '1h').desde, '2026-10-10T14:00:00Z');
  const w5m = F.ventana(F.leeHash('#BTC/5m/perp/hasta=2026-10-17T12:00Z'), 0);
  assert.deepStrictEqual(F.ventanaCapas(w5m, dia, '5m'), Object.assign({}, w5m, { recortada: false }));
});

test('una sesion que cruza la medianoche es UNA: sus N ultimas, desde su inicio', () => {
  const noche = F.leeSesion('22:00-06:00');
  assert.deepStrictEqual([noche.ini, noche.minutos, noche.cruza], [1320, 480, true]);
  assert.deepStrictEqual([F.leeSesion('dia').minutos, F.leeSesion('dia').cruza], [1440, false]);
  assert.deepStrictEqual([F.leeSesion('eeuu').ini, F.leeSesion('eeuu').minutos], [810, 390]);
  assert.strictEqual(F.leeSesion('06:00-06:00').minutos, 1440);
  assert.strictEqual(F.leeSesion('24:00-01:00'), null);
  // a las 03:00 del 17 la ultima sesion de noche empezo el 16 a las 22:00 (no a medianoche)
  const t = Date.parse('2026-10-17T03:00:00Z');
  assert.strictEqual(new Date(F.inicioSesion(t, noche)).toISOString(), '2026-10-16T22:00:00.000Z');
  assert.deepStrictEqual(F.ventanaSesiones(t, noche, 2), { desde: '2026-10-15T22:00:00Z', hasta: '2026-10-17T03:00:00Z' });
  // a las 22:00 justas, la que empieza a las 22:00 aun no ha empezado ANTES de ese instante
  assert.strictEqual(new Date(F.inicioSesion(Date.parse('2026-10-17T22:00:00Z'), noche)).toISOString(),
    '2026-10-16T22:00:00.000Z');
  assert.deepStrictEqual(F.ventanaSesiones(Date.parse('2026-10-17T11:30:00Z'), F.leeSesion('dia'), 1),
    { desde: '2026-10-17T00:00:00Z', hasta: '2026-10-17T11:30:00Z' });
});

test('el estado de una capa: en curso, hueco o cuantos minutos-venue faltan; nunca un cero inventado', () => {
  const cob = (esp, fila, comp, completa) => ({ minutos_esperados: esp, minutos_con_fila: fila,
                                                minutos_completos: comp, completa });
  assert.deepStrictEqual(F.estadoSesion({ en_curso: true, cobertura: cob(2088, 1600, 1466, false) }),
    { estado: 'incompleta', en_curso: true, faltan: 622, esperados: 2088 });
  assert.strictEqual(F.marcaCapa(F.estadoSesion({ en_curso: true, cobertura: cob(2088, 1600, 1466, false) })),
    'en curso · faltan 622/2088');
  assert.strictEqual(F.marcaCapa(F.estadoSesion({ en_curso: false, cobertura: cob(120, 0, 0, false) })), 'hueco');
  assert.strictEqual(F.marcaCapa(F.estadoSesion({ en_curso: false, cobertura: cob(120, 120, 120, true) })), null);
  // una sesion que acaba de empezar no echa nada en falta
  assert.strictEqual(F.marcaCapa(F.estadoSesion({ en_curso: true, cobertura: cob(0, 0, 0, false) })), 'en curso');
  const asOf = Date.parse('2026-10-17T12:00:00Z');
  assert.strictEqual(F.estadoRango(0, Date.parse('2026-10-17T11:59:00Z'), cob(60, 60, 60, true), asOf).estado,
    'abierta');
  assert.deepStrictEqual(F.estadoRango(0, Date.parse('2026-10-17T11:58:00Z'), cob(60, 50, 45, false), asOf),
    { estado: 'incompleta', en_curso: false, faltan: 15, esperados: 60 });
});
