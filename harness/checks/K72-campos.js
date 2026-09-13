'use strict';
// La sonda de K72. Vease la cabecera de K72-el-campo-que-no-llega.sh para el criterio.
//
// LA TABLA DE CAMPOS VIVE AQUI Y SE LEE ENTERA: son pocos y cada uno dice DE QUE RUTA sale.
// La ruta no se supone: sale del censo por dato de la FASE 3a -la tarjeta de setups se
// alimenta de /api/dashboard/state aunque el sobre tambien traiga `setup`-.
const path = require('path');

const REPO = process.env.REPO || '/srv/coinanalyze/repo';
const FIX = process.env.K72_FIXTURES || '/srv/coinanalyze/harness/estado/k31-fixtures';
process.env.REPO = REPO;
const { render } = require(path.join(REPO, 'harness/panel/render.js'));

const MARCA = 'ZZK72ZZ';
// Cada `planta` devuelve `false` SI EL CAMPO NO VIENE en el payload. Eso no es un fallo de la
// tarjeta: es que no habia nada que pintar, y se cuenta aparte.
const CAMPOS = [
  ['setup.missing', '/api/dashboard/state', 'la tarjeta de setups: lo que le falta a cada uno',
    o => {
      const ss = (o.setup && o.setup.setups) || [];
      const con = ss.filter(s => Array.isArray(s.missing) && s.missing.length);
      con.forEach(s => { s.missing[0] = MARCA; });
      return con.length > 0;
    }, true],
  ['setup.invalidation', '/api/dashboard/state', 'la tarjeta de setups: lo que lo invalida',
    o => {
      const con = ((o.setup && o.setup.setups) || []).filter(s => s.invalidation);
      con.forEach(s => { s.invalidation = MARCA; });
      return con.length > 0;
    }, true],
  ['setup.horizon', '/api/dashboard/state', 'la tarjeta de setups: su horizonte',
    o => {
      const con = ((o.setup && o.setup.setups) || []).filter(s => s.horizon);
      con.forEach(s => { s.horizon = MARCA; });
      return con.length > 0;
    }, true],
  ['oi data_gaps.exchanges', '/api/oi', 'la tarjeta Open Interest: de que venue es la serie',
    o => {
      if (!o.data_gaps || !Array.isArray(o.data_gaps.exchanges) || !o.data_gaps.exchanges.length) return false;
      o.data_gaps.exchanges = [MARCA];
      return true;
    }, true],
  ['oi_context.by_venue.note', '/api/ai/context', 'la tarjeta Open Interest: el alcance del reparto',
    o => {
      if (!o.oi_context || !o.oi_context.by_venue || !o.oi_context.by_venue.note) return false;
      o.oi_context.by_venue.note = MARCA;
      return true;
    }, true],
  // EL CONTROL, en la misma pasada. Un campo que la tarjeta NO pinta: si llegara, este check
  // diria que si a cualquier cosa y su VERDE no valdria nada.
  ['setup.daily_flow_source', '/api/dashboard/state', 'CONTROL: campo que la tarjeta NO pinta',
    o => {
      if (!o.setup || o.setup.daily_flow_source === undefined) return false;
      o.setup.daily_flow_source = MARCA;
      return true;
    }, false],
];

async function texto(transform) {
  const r = await render({ mode: 'replay', fixtures: FIX, settleMs: 400, frozenAt: 1756300000000, transform });
  for (const l of [...r.document.querySelectorAll('.section-links a')]) {
    l.dispatchEvent(new r.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise(res => setTimeout(res, 400));
  }
  return r.document.body.textContent.replace(/\s+/g, ' ').trim();
}

(async () => {
  let base;
  try { base = await texto(null); }
  catch (e) { console.log('NO MEDIDO: el panel no arranca: ' + String(e && e.message || e).split('\n')[0]); process.exit(2); }
  if (base.includes(MARCA)) { console.log('NO MEDIDO: la marca ya esta en el DOM sin mutar nada'); process.exit(2); }
  if (base.length < 1000) { console.log(`NO MEDIDO: el DOM son ${base.length} B; no hay pantalla que medir`); process.exit(2); }

  // UN PLANTADO QUE NO OCURRE NO ES UN ROJO, y esto lo cazo la auditoria del operador. Si el
  // backend NO SIRVE el campo, no hay nada que marcar: la ausencia de la marca en el DOM no
  // dice «la tarjeta dejo de pintarlo», dice «no habia que pintar». La primera version no
  // distinguia las dos cosas y condenaba a la tarjeta por hacer lo correcto: con un sobre sin
  // `oi_context.by_venue` la tarjeta escribe «Reparto por venue: no servido» -que es lo que
  // se le pidio- y el check decia ROJO «un campo que el backend SIRVE dejo de llegar», que
  // ademas es una frase FALSA porque no lo sirvio.
  //
  // Por eso cada `planta` devuelve AHORA si de verdad puso la marca, y hay tres cubos:
  //     servido y pintado      -> bien
  //     servido y NO pintado   -> ROJO, con su nombre
  //     NO servido             -> no se juzga, y se DICE en la linea de veredicto
  const perdidos = [], control = [], noServidos = [];
  for (const [campo, ruta, que, planta, esperado] of CAMPOS) {
    let planto = false;
    const t = (url, body) => {
      if (url.split('?')[0] !== ruta) return body;
      const o = JSON.parse(body);
      planto = planta(o) !== false;
      return JSON.stringify(o);
    };
    let llega;
    try { llega = (await texto(t)).includes(MARCA); }
    catch (e) { console.log(`NO MEDIDO: el panel reventó midiendo ${campo}: ${String(e && e.message || e).split('\n')[0]}`); process.exit(2); }
    if (!planto) { noServidos.push(campo); continue; }
    if (esperado && !llega) perdidos.push(`${campo} (${que}, de ${ruta})`);
    if (!esperado && llega) control.push(campo);
  }

  if (control.length) {
    console.log('NO MEDIDO: el control se colo -%s llega a la pantalla y no deberia-, asi que '
      .replace('%s', control.join(' ')) +
      'este check no distingue «se pinta» de «no se pinta» y su verde no valdria nada.');
    process.exit(2);
  }
  const cola = noServidos.length
    ? ` · ${noServidos.length} NO SE JUZGA(N) porque el backend no los sirvio hoy: ` +
      `${noServidos.join(' ')} -un plantado que no ocurre no es una perdida-`
    : '';
  const juzgados = CAMPOS.length - 1 - noServidos.filter(c => !c.startsWith('setup.daily_flow_source')).length;

  if (perdidos.length) {
    console.log(`ROJO: ${perdidos.length} campo(s) que el backend SIRVE dejaron de llegar a su ` +
      `tarjeta: ${perdidos.join(' · ')} · de ${juzgados} juzgados, medido mutando el ` +
      `payload que la tarjeta LEE y buscando la marca en el DOM${cola}`);
    process.exit(1);
  }
  if (!juzgados) {
    console.log('NO MEDIDO: el backend no sirvio hoy ninguno de los campos vigilados, asi que ' +
      `no hay nada que juzgar${cola}`);
    process.exit(2);
  }
  console.log(`los ${juzgados} campos servidos hoy llegan ESCRITOS a su tarjeta: lo que le ` +
    'falta a cada setup, lo que lo invalida, su horizonte, el venue de la serie de OI y el ' +
    'alcance del reparto por venue. Medido mutando el payload que la tarjeta lee -no el que ' +
    'uno supondria- y buscando la marca en el DOM, con el control de un campo NO pintado ' +
    `saliendo \`false\` en la misma pasada${cola}`);
  process.exit(0);
})();
