'use strict';
// LA CELDA DEL HEATMAP: que no se corte, que diga su unidad, y que un hueco no sea un cero.
//
// QUE PASO. Medido con el navegador en 14 anchos de 1366 a 2560 px (`scrollWidth > clientWidth`):
// en 8 de los 14 se cortaban celdas, y el PEOR era 1920 —el monitor mas comun— con 50 de 84
// celdas y las 28 etiquetas de fecha recortadas. Cuando se cortan, celdas que valen cosas
// distintas se ven iguales y el heatmap deja de poder leerse como lo que es.
//
// Dos causas: `minmax(0, 1fr)` deja que la columna encoja por debajo de su contenido, y el
// escalon ancho de 1900 px estrechaba el panel de 806 a 556 px justo al ganar pantalla.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { cargarApp, APP_JS } = require('./harness');

const app = cargarApp();

test('el funding se pinta en milesimas y el valor crudo no se pierde', () => {
  // 0.006742 % por 8 h -> «6.7». Seis caracteres pasan a tres, que es lo que quita el
  // desplazamiento horizontal a 1366-1536 px.
  const celda = app.celdaHeat({ pct_8h: 0.006742, muestras: 288, completo: true }, 0.01, ' % por 8 h', 1000);
  assert.equal(celda.textContent, '6.7');
  // EL DATO NO SE PIERDE: el crudo sigue entero en el titulo, con su unidad y su denominador.
  assert.ok(celda.title.includes('0.006742'), celda.title);
  assert.ok(celda.title.includes('% por 8 h'), celda.title);
  assert.ok(celda.title.includes('288 muestras'), celda.title);
});

test('sin factor no se escala nada', () => {
  // El heatmap de interes abierto no se toca: sus valores ya son cortos y estan en % de verdad.
  const celda = app.celdaHeat({ chg_pct: -1.24, muestras: 288, completo: true }, 5, ' %', 1);
  assert.equal(celda.textContent, '-1.2');
});

test('una celda sin dato va VACIA y marcada, nunca a cero', () => {
  // Un cero ahi se leeria como «ese dia no se pago funding», que es falso: no se midio.
  const celda = app.celdaHeat(null, 0.01, ' % por 8 h', 1000);
  assert.equal(celda.textContent, '');
  assert.ok(celda.className.includes('heat-vacia'));
  assert.ok(/no es un cero/.test(celda.title), celda.title);
});

test('un dia incompleto se marca en vez de pasar por completo', () => {
  const celda = app.celdaHeat({ pct_8h: 0.005, muestras: 219, completo: false }, 0.01, ' % por 8 h', 1000);
  assert.ok(celda.className.includes('heat-parcial'));
  assert.ok(celda.title.includes('DIA INCOMPLETO'));
});

// ESTE ES DEBIL Y LO DIGO: comprueba TEXTO del fuente, no comportamiento. Un `minmax(0, ...)`
// que volviera por otra via no lo cazaria. El check de verdad es el barrido con el navegador
// —`scrollWidth > clientWidth` en la banda 1366-2560—, que no corre en CI porque necesita
// chromium y una replica con payloads. Esto solo evita la recaida literal.
test('la rejilla no vuelve a permitir columnas mas estrechas que su contenido (DEBIL)', () => {
  const fuente = fs.readFileSync(APP_JS, 'utf8');
  const m = fuente.match(/gridTemplateColumns\s*=\s*`72px repeat\(\$\{[^}]+\}, minmax\(([^,]+),/);
  assert.ok(m, 'no se encontro la plantilla de columnas del heatmap');
  assert.equal(m[1].trim(), 'min-content');
});
