'use strict';
// LA MESA · la vista ENTRADAS (campana 137). Lo que aqui se prueba es lo que decide EL RELOJ DEL
// NAVEGADOR -lo unico que el cliente calcula-: una cuenta atras que llega a cero, un refresco que
// falla, un generador que deja de latir y una palabra de DECIDE que pasa de su tope. Lo que la
// pantalla PINTA se mira con un Chromium de verdad en K106; aqui no se comprueban cadenas.
//
// La respuesta NO se escribe a mano: la compone el backend (tests/entradas_vista_banco.py llama a
// app/entradas/vista.py), asi este test pinta la forma que la ruta sirve de verdad.

const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { cargaMesa } = require('./harness-mesa.js');

const RAIZ = path.join(__dirname, '..', '..');
function respuesta(...args) {
  const py = process.env.VENV_PY || path.join(RAIZ, '.venv', 'bin', 'python');
  return JSON.parse(execFileSync(py, [path.join(RAIZ, 'tests', 'entradas_vista_banco.py'), ...args],
                                 { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }));
}

// Una mesa con SU reloj: `pasa(s)` adelanta el `performance.now()` que la vista lee.
function mesa() {
  const m = cargaMesa();
  let ahora = 0;
  m.ventana.performance.now = () => ahora;
  m.evalua("ESTADO.vista = 'entradas'; ESTADO.activo = 'BTC';");
  const pinta = (sobre) => m.ctx.pintarEntradas({ tLlegada: ahora, ...sobre });
  const pasa = (s) => { ahora += s * 1000; m.ctx.entTicTac(); };
  const id = (x) => m.documento.getElementById(x);
  const vivos = () => id('ent-vivo').querySelectorAll('[data-plan]').map((n) => ({
    plan: n.getAttribute('data-plan'), tipo: n.getAttribute('data-tipo'), vivo: n.getAttribute('data-vivo'),
    chip: n.querySelector('[data-chip]').textContent,
  }));
  const avisos = () => id('ent-aviso').querySelectorAll('[data-aviso]').map((n) => n.getAttribute('data-aviso'));
  return { ...m, pinta, pasa, id, vivos, avisos };
}

test('el hash de la vista de entradas se lee, se escribe y no se confunde con las otras', () => {
  const { ctx, aqui } = cargaMesa();
  assert.deepStrictEqual(aqui(ctx.leerHash('#scalp/SOL/entradas')), { marco: 'scalp', activo: 'SOL', vista: 'entradas' });
  assert.deepStrictEqual(aqui(ctx.leerHash('#largo/eth/entradas')), { marco: 'largo', activo: 'ETH', vista: 'entradas' });
  assert.strictEqual(ctx.leerHash('#scalp/BTC/status').vista, 'estado');
  assert.strictEqual(ctx.leerHash('#scalp/BTC/entrada').vista, 'mesa');
  // una clave heredada de Object no es una vista
  assert.strictEqual(ctx.leerHash('#scalp/BTC/constructor').vista, 'mesa');
});

test('las dos unicas cuentas del cliente: una duracion y una hora cortada del instante servido', () => {
  const { ctx } = cargaMesa();
  assert.strictEqual(ctx.entDura(45.9), '45 s');
  assert.strictEqual(ctx.entDura(75), '1 min 15 s');
  assert.strictEqual(ctx.entDura(8040), '2 h 14 min');
  assert.strictEqual(ctx.entDura(190000), '2 d 4 h');
  assert.strictEqual(ctx.entDura(-3), '0 s');
  // la cuenta atras, siempre con sus segundos
  assert.strictEqual(ctx.entCuenta(13867), '3 h 51 min 7 s');
  assert.strictEqual(ctx.entCuenta(59), '59 s');
  assert.strictEqual(ctx.entCuenta(3600), '1 h 0 min 0 s');
  assert.strictEqual(ctx.entHora('2026-10-13T16:00:00+00:00'), '10-13 16:00Z');
  assert.strictEqual(ctx.entHora('2026-10-13T16:00:09Z', true), '10-13 16:00:09Z');
  assert.strictEqual(ctx.entHora(null), null);
});

test('un DISPARADO vivo se ve vivo, y al llegar su cuenta atras a cero deja de verse vivo SIN recargar', () => {
  const m = mesa();
  m.pinta({ ok: true, datos: respuesta('LONG', '30') });
  assert.deepStrictEqual(m.avisos(), []);
  assert.strictEqual(m.id('ent-aviso').hidden, true);
  const antes = m.vivos();
  assert.deepStrictEqual(antes.find((p) => p.tipo === 'disparado'), { plan: '7', tipo: 'disparado', vivo: 'si', chip: 'DISPARADO · VIVO' });
  assert.ok(antes.filter((p) => p.tipo === 'vigilando').every((p) => p.vivo === 'si' && p.chip === 'VIGILANDO'));
  m.pasa(29);
  assert.strictEqual(m.vivos().find((p) => p.tipo === 'disparado').vivo, 'si');
  m.pasa(2);
  assert.deepStrictEqual(m.vivos().find((p) => p.tipo === 'disparado'), { plan: '7', tipo: 'disparado', vivo: 'no', chip: 'DISPARADO · CADUCADO' });
});

test('si el refresco falla se dice ARRIBA en el acto y nada queda en pantalla como vivo; al volver, vuelve', () => {
  const m = mesa();
  const buena = respuesta('LONG');
  m.pinta({ ok: true, datos: buena });
  assert.ok(m.vivos().length >= 3 && m.vivos().every((p) => p.vivo === 'si'));
  m.pasa(45);
  m.pinta({ ok: false, http: 503, motivo: 'banco' });
  assert.deepStrictEqual(m.avisos(), ['sin-dato']);
  assert.match(m.id('ent-aviso').textContent, /la ruta de entradas no contesta/);
  assert.strictEqual(m.id('ent-aviso').hidden, false);
  assert.ok(m.vivos().length >= 3, 'lo ultimo que se supo sigue en pantalla');
  assert.ok(m.vivos().every((p) => p.vivo === 'no-se-sabe' && p.chip === 'YA NO SE SABE'));
  m.pinta({ ok: true, datos: buena });
  assert.deepStrictEqual(m.avisos(), []);
  assert.ok(m.vivos().every((p) => p.vivo === 'si'));
});

test('la ruta que contesta «no disponible» pinta su motivo servido arriba, y en la primera carga no inventa nada', () => {
  const m = mesa();
  m.pinta({ ok: true, datos: { disponible: false, motivo: 'esta base no tiene las tablas del registro' } });
  assert.deepStrictEqual(m.avisos(), ['no-disponible']);
  assert.match(m.id('ent-aviso').textContent, /esta base no tiene las tablas del registro/);
  assert.deepStrictEqual(m.vivos(), []);
  const n = mesa();
  n.pinta({ ok: false, http: 0, motivo: 'transporte: se cayo' });
  assert.deepStrictEqual(n.avisos(), ['sin-dato']);
  assert.match(n.id('ent-aviso').textContent, /transporte: se cayo/);
});

test('una respuesta que no llega NI falla tambien acaba diciendolo: la edad corre sola', () => {
  const m = mesa();
  const d = respuesta('LONG');
  m.pinta({ ok: true, datos: d });
  m.pasa(d.frescura.sin_dato_s - 1);
  assert.deepStrictEqual(m.avisos(), []);
  m.pasa(2);
  assert.deepStrictEqual(m.avisos(), ['sin-dato']);
  assert.ok(m.vivos().every((p) => p.vivo === 'no-se-sabe'));
  // y NO dice que la ruta no contesta: nadie le ha preguntado. Dice lo que sabe, la edad.
  assert.match(m.id('ent-aviso').textContent, /la ultima respuesta buena tiene mas de 120 s/);
  assert.doesNotMatch(m.id('ent-aviso').textContent, /no contesta/);
});

test('el generador que deja de latir se dice arriba aunque la ruta conteste, y sin latido ninguno tambien', () => {
  const m = mesa();
  const d = respuesta('LONG', '3600', '1700');
  m.pinta({ ok: true, datos: d });
  assert.deepStrictEqual(m.avisos(), [], 'a 1700 s del ultimo latido todavia late');
  m.pasa(101);
  assert.deepStrictEqual(m.avisos(), ['generador-parado'], 'el tope servido son 1800 s: lo cruza SIN recargar');
  assert.ok(m.vivos().every((p) => p.vivo === 'no-se-sabe'));
  const n = mesa();
  n.pinta({ ok: true, datos: respuesta('LONG', '3600', '5000') });
  assert.deepStrictEqual(n.avisos(), ['generador-parado']);
  assert.ok(n.vivos().every((p) => p.vivo === 'no-se-sabe'));
});

test('la palabra de DECIDE sale RANCIA sola al pasar de su tope, y la relacion de cada celda con ella tambien', () => {
  const m = mesa();
  const d = respuesta('SHORT');
  m.pinta({ ok: true, datos: d });
  const visibles = (clase) => m.documento.querySelectorAll('.' + clase).filter((n) => !n.hidden);
  assert.strictEqual(visibles('ent-dec-rancia').length, 0);
  // un plan largo con DECIDE en SHORT: va en contra, y se dice
  const relaciones = visibles('ent-rel').map((n) => n.getAttribute('data-relacion'));
  assert.deepStrictEqual(relaciones, ['en_contra', 'mismo_lado', 'no_dice', 'no_dice']);
  m.pasa(d.decide.max_age_s - d.decide.edad_s + 1);
  assert.strictEqual(visibles('ent-dec-viva').length, 0);
  assert.strictEqual(visibles('ent-dec-rancia').length, 2);
  assert.ok(visibles('ent-rel').every((n) => n.classList.contains('rel-rancio')));
});

test('sin respuesta de DECIDE la vista pinta lo que se le sirve y no una palabra', () => {
  const m = mesa();
  m.pinta({ ok: true, datos: respuesta('SIN') });
  const palabras = m.id('ent-decide').querySelectorAll('.ent-palabra').map((n) => [n.textContent, n.getAttribute('data-palabra')]);
  assert.deepStrictEqual(palabras, [['SIN RESPUESTA', ''], ['SIN RESPUESTA', '']]);
});
