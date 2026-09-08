'use strict';
// P1 — la navegacion interna apunta a secciones que existen y nunca deja la pagina vacia.

const fs = require('node:fs');
const test = require('node:test');
const assert = require('node:assert/strict');
const { cargarApp, leerIndexHtml, APP_JS } = require('./harness');

const { sectionIds, navLinks } = leerIndexHtml();

const { todosLosIds } = leerIndexHtml();

// EL ORDEN ES EL DE «MESA DE POSICION», 2026-09-08, y cambio por una tesis y no por gusto:
// para dias-a-semanas en perpetuos el funding es el GASTO principal -se paga tres veces al dia
// se mire o no-, asi que `coste` va segundo, delante de la estructura. Y `liquidez` -libro,
// absorcion de 3 min, coste de ejecucion- baja al final, a una segunda lista rotulada «para
// ejecutar, no para decidir»: no se borra, deja de competir por la atencion.
const ORDEN_ESPERADO = [
  'mesa', 'coste', 'estructura', 'flujo', 'derivados', 'calidad', 'replay', 'contexto', 'liquidez',
];

test('el index.html declara las nueve secciones de la reorganizacion, en su orden', () => {
  assert.deepEqual([...sectionIds], ORDEN_ESPERADO);
});

// EL CHECK QUE FALTABA, y es el que hace que este fichero no vuelva a acusar al documento de un
// fallo del lector: la navegacion y las secciones tienen que ser EL MISMO CONJUNTO. Da igual en
// cuantas listas este repartido el menu.
test('la navegacion y las secciones son el mismo conjunto', () => {
  const enNav = new Set(navLinks.map(h => h.slice(1)));
  const enDoc = new Set(sectionIds);
  const soloNav = [...enNav].filter(id => !enDoc.has(id));
  const soloDoc = [...enDoc].filter(id => !enNav.has(id));
  assert.deepEqual(soloNav, [], `enlaces a secciones que no existen: ${soloNav}`);
  assert.deepEqual(soloDoc, [], `secciones sin enlace, inalcanzables: ${soloDoc}`);
});

test('el coste va antes que la estructura', () => {
  // No es cosmetica: si vuelve a quedar detras, el dashboard ha vuelto a tener la señal como eje.
  assert.ok(sectionIds.indexOf('coste') < sectionIds.indexOf('estructura'));
  assert.equal(sectionIds.indexOf('coste'), 1);
});

test('cada enlace de la navegacion superior apunta a un elemento existente', () => {
  assert.ok(navLinks.length >= 8, 'la barra de navegacion no trae enlaces');
  for (const hash of navLinks) {
    assert.ok(todosLosIds.has(hash.slice(1)), `${hash} no existe en el documento`);
  }
});

test('cada destino de .horizon-link apunta a una seccion existente', () => {
  // Los enlaces de las tarjetas de horizonte se generan en JS (`link: '#...'`), asi que el
  // destino se lee del propio codigo: es exactamente el que acabara en el href.
  const fuente = fs.readFileSync(APP_JS, 'utf8');
  const destinos = [...fuente.matchAll(/link:\s*'#([a-z0-9_-]+)'/gi)].map(m => m[1]);
  assert.ok(destinos.length >= 3, 'no se encontro ningun destino de horizon-link');
  for (const destino of destinos) {
    assert.ok(sectionIds.includes(destino), `#${destino} no corresponde a ninguna seccion`);
  }
});

test('un hash invalido abre mesa y no oculta todas las secciones', async () => {
  const app = cargarApp();
  app.location.hash = '#no-existe';
  app.loadSection = async () => {};
  app.initSectionNav();

  const visibles = app.__dom.secciones.filter(s => !s.hidden);
  assert.equal(app.state.activeSection, 'mesa');
  assert.deepEqual(visibles.map(s => s.id), ['mesa']);
});

test('un hash vacio tambien abre mesa', async () => {
  const app = cargarApp();
  app.location.hash = '';
  app.loadSection = async () => {};
  app.initSectionNav();
  assert.equal(app.state.activeSection, 'mesa');
});

test('un hash valido abre esa seccion y solo esa', async () => {
  for (const id of sectionIds) {
    const app = cargarApp();
    app.location.hash = `#${id}`;
    app.loadSection = async () => {};
    app.initSectionNav();
    const visibles = app.__dom.secciones.filter(s => !s.hidden).map(s => s.id);
    assert.deepEqual(visibles, [id], `hash #${id}`);
  }
});

test('navegar a un destino invalido en caliente devuelve a mesa, no a la nada', async () => {
  const app = cargarApp();
  app.location.hash = '#flujo';
  app.loadSection = async () => {};
  app.initSectionNav();
  assert.equal(app.state.activeSection, 'flujo');

  // popstate con un hash que no existe: el fallback tiene que ser una seccion REAL.
  app.location.hash = '#overview';
  for (const fn of app.__winListeners.popstate || []) await fn();
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(app.state.activeSection, 'mesa');
  const visibles = app.__dom.secciones.filter(s => !s.hidden).map(s => s.id);
  assert.deepEqual(visibles, ['mesa']);
});

test('la constante de fallback es una seccion del documento', () => {
  const app = cargarApp();
  assert.ok(sectionIds.includes(app.FALLBACK_SECTION));
});
