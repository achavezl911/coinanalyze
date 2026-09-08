'use strict';
// EL LECTOR DE SECCIONES, PROBADO CONTRA HTML SINTETICO.
//
// POR QUE EXISTE ESTE FICHERO. El 2026-09-08 el CI del PR #167 dio ROJO diciendo
// «#liquidez no corresponde a ninguna seccion». La seccion EXISTIA: se pintaba y se navegaba.
// Lo que fallaba era el lector del propio test, que hacia
//     html.match(/<nav ... class="section-links" ...>/)
// sin `/g`, o sea que cogia SOLO EL PRIMER <nav>. Mientras hubo una lista funciono; cuando la
// reorganizacion partio el menu en dos, se quedo con ocho destinos y ACUSO AL DOCUMENTO.
//
// Un instrumento que mide una FORMA del documento en vez de la cosa deja de medir en cuanto la
// forma cambia, y no avisa de eso: avisa de otra cosa. Estas pruebas son el control que hacia
// falta para que no se repita, y se corren contra HTML de mentira: un instrumento que solo se
// puede comprobar estropeando el sujeto no se comprueba nunca.

const test = require('node:test');
const assert = require('node:assert/strict');
const { leerSecciones } = require('./harness');

function doc({ secciones, navs }) {
  const s = secciones.map(id => `<section id="${id}" class="market-section" hidden></section>`).join('\n');
  const n = navs.map(lista =>
    `<nav class="section-links">` +
    lista.map(id => `<a href="#${id}" data-tab="${id}">${id}</a>`).join('') +
    `</nav>`).join('\n');
  return `<html><body>${n}\n${s}</body></html>`;
}

test('con UNA lista de navegacion, las lee todas', () => {
  const { sectionIds, navLinks } = leerSecciones(doc({
    secciones: ['mesa', 'coste'], navs: [['mesa', 'coste']],
  }));
  assert.deepEqual(sectionIds, ['mesa', 'coste']);
  assert.deepEqual(navLinks, ['#mesa', '#coste']);
});

test('CONTROL · con DOS listas, no se pierde la segunda', () => {
  // Este es el caso exacto que rompio el CI. Con el lector viejo, `navLinks` habria valido
  // ['#mesa'] y `liquidez` habria salido «inexistente».
  const { sectionIds, navLinks } = leerSecciones(doc({
    secciones: ['mesa', 'liquidez'], navs: [['mesa'], ['liquidez']],
  }));
  assert.deepEqual(sectionIds, ['mesa', 'liquidez']);
  assert.deepEqual(navLinks, ['#mesa', '#liquidez']);
});

test('CONTROL QUE SE MUEVE · una TERCERA lista entra sola en el censo', () => {
  // Si mañana alguien parte el menu otra vez, el lector no tiene que tocarse.
  const { navLinks } = leerSecciones(doc({
    secciones: ['mesa', 'liquidez', 'archivo'],
    navs: [['mesa'], ['liquidez'], ['archivo']],
  }));
  assert.deepEqual(navLinks, ['#mesa', '#liquidez', '#archivo']);
});

test('CONTROL QUE SE MUEVE · un enlace a una seccion que no existe se ve', () => {
  // El operador que lo pulsa se queda en blanco, asi que tiene que poder acusarse.
  const { sectionIds, navLinks } = leerSecciones(doc({
    secciones: ['mesa'], navs: [['mesa', 'fantasma']],
  }));
  const enDoc = new Set(sectionIds);
  const colgados = navLinks.map(h => h.slice(1)).filter(id => !enDoc.has(id));
  assert.deepEqual(colgados, ['fantasma']);
});

test('CONTROL QUE SE MUEVE · una seccion sin enlace en NINGUNA lista se ve', () => {
  // Existe y es inalcanzable: el caso que el lector viejo no podia ver ni queriendo, porque
  // sacaba la lista de secciones del propio nav.
  const { sectionIds, navLinks } = leerSecciones(doc({
    secciones: ['mesa', 'huerfana'], navs: [['mesa']],
  }));
  const enNav = new Set(navLinks.map(h => h.slice(1)));
  const inalcanzables = sectionIds.filter(id => !enNav.has(id));
  assert.deepEqual(inalcanzables, ['huerfana']);
});

test('las secciones anidadas que NO son pestañas siguen fuera del censo', () => {
  // El aviso del harness viejo era correcto y se conserva: el documento tiene <section> de
  // resumen y de analizador que no son pestañas. Solo cuentan las `market-section`.
  const html = doc({ secciones: ['mesa'], navs: [['mesa']] })
    .replace('</body>', '<section id="analyzer-zone" class="analyzer-pane"></section></body>');
  assert.deepEqual(leerSecciones(html).sectionIds, ['mesa']);
});
