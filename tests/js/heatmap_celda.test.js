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
  // 0.006742 % por 8 h -> «6.74». Ocho caracteres pasan a cuatro, que es lo que quita el
  // desplazamiento horizontal a 1366-1536 px.
  //
  // ESPERABA «6.7» HASTA EL 2026-09-09 Y SE ACTUALIZO CON SU RAZON, no se aflojo: con UN
  // decimal, dias que valen cosas distintas se pintaban con el mismo texto. Medido sobre el
  // payload real de /api/carry/matriz, 45 celdas por mapa: un decimal daba 6 pares
  // indistinguibles en funding y 10 en OI; dos decimales dan 0 y 2. El caracter extra salio
  // GRATIS, medido con chromium en 12 anchuras de 1024 a 2560: el desbordamiento horizontal de
  // la rejilla es identico al del formato viejo en las doce, porque el ancho de columna ya lo
  // fijaba la cabecera de fecha -«08-28», cinco caracteres-.
  const celda = app.celdaHeat({ pct_8h: 0.006742, muestras: 288, completo: true }, 0.01, ' % por 8 h', 1000);
  assert.equal(celda.textContent, '6.74');
  // EL DATO NO SE PIERDE: el crudo sigue entero en el titulo, con su unidad y su denominador.
  assert.ok(celda.title.includes('0.006742'), celda.title);
  assert.ok(celda.title.includes('% por 8 h'), celda.title);
  assert.ok(celda.title.includes('288 muestras'), celda.title);
});

test('sin factor no se escala nada', () => {
  // El heatmap de interes abierto no se toca: sus valores ya son cortos y estan en % de verdad.
  // Esperaba «-1.2» hasta el 2026-09-09; ahora «-1.24» por la misma razon que el de arriba, y
  // aqui importaba mas: el mapa de OI era el que MAS pares indistinguibles tenia, 10 de 45.
  const celda = app.celdaHeat({ chg_pct: -1.24, muestras: 288, completo: true }, 5, ' %', 1);
  assert.equal(celda.textContent, '-1.24');
});

// EL CASO QUE NINGUN TEST CUBRIA, y era el peor de los dos sintomas: un valor que NO es cero
// pintado como un cero. Con un decimal, este funding salia «-0.0» -medido en produccion el
// 2026-09-09, la celda del 2026-09-02 de SOL-. Un cero pintado donde no hay un cero es una
// afirmacion falsa sobre el mercado, no un redondeo.
test('un valor distinto de cero NUNCA se pinta como un cero', () => {
  // -0.000025 % por 8 h x 1000 = -0.025 -> con dos decimales ya no cae en cero.
  const c1 = app.celdaHeat({ pct_8h: -0.000025, muestras: 288, completo: true }, 0.01, ' % por 8 h', 1000);
  assert.equal(c1.textContent, '-0.03');
  // Y por debajo de eso, donde ni dos decimales llegan, se marca en vez de mentir. El signo lo
  // sigue diciendo el color de fondo, y el crudo entero sigue en el title.
  const c2 = app.celdaHeat({ pct_8h: -0.0000004, muestras: 288, completo: true }, 0.01, ' % por 8 h', 1000);
  assert.equal(c2.textContent, '\u22480');
  assert.ok(c2.title.includes('-4e-7') || c2.title.includes('0.0000004'), c2.title);
  // EL NEGATIVO, sin el cual lo de arriba seria una maquina de poner «aprox. cero»: un cero de
  // verdad se sigue pintando como un cero.
  const c3 = app.celdaHeat({ pct_8h: 0, muestras: 288, completo: true }, 0.01, ' % por 8 h', 1000);
  assert.equal(c3.textContent, '0');
});

// Y EL CRITERIO, no el ejemplo: dos valores distintos no pueden dar el mismo texto en el rango
// en el que estos mapas viven de verdad.
test('dos dias con valores distintos no se pintan igual', () => {
  const a = app.celdaHeat({ chg_pct: 0.208, muestras: 288, completo: true }, 5, ' %', 1);
  const b = app.celdaHeat({ chg_pct: 0.211, muestras: 288, completo: true }, 5, ' %', 1);
  // Estos dos SI sobreviven iguales y esta declarado: difieren en 0.003 puntos porcentuales, y
  // separarlos costaria un tercer decimal en TODAS las celdas para ganar dos pares de 45.
  assert.equal(a.textContent, b.textContent);
  const c = app.celdaHeat({ chg_pct: -2.12, muestras: 288, completo: true }, 5, ' %', 1);
  const d = app.celdaHeat({ chg_pct: -2.057, muestras: 288, completo: true }, 5, ' %', 1);
  // Estos dos se pintaban IGUALES con un decimal -los dos «-2.1»- y ahora se distinguen.
  assert.notEqual(c.textContent, d.textContent);
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
