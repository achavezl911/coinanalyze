'use strict';
// La sonda de K46. Vease la cabecera de K46-el-campo-que-no-llega.sh para el criterio.
//
// LA TABLA DE CAMPOS VIVE AQUI Y SE LEE ENTERA: son pocos y cada uno dice DE QUE RUTA sale.
// La ruta no se supone: sale del censo por dato de la FASE 3a -la tarjeta de setups se
// alimenta de /api/dashboard/state aunque el sobre tambien traiga `setup`-.
const path = require('path');

const REPO = process.env.REPO || '/srv/coinanalyze/repo';
const FIX = process.env.K46_FIXTURES || '/srv/coinanalyze/harness/estado/k31-fixtures';
process.env.REPO = REPO;
const { render } = require(path.join(REPO, 'harness/panel/render.js'));

const MARCA = 'ZZK46ZZ';
const CAMPOS = [
  ['setup.missing', '/api/dashboard/state', 'la tarjeta de setups: lo que le falta a cada uno',
    o => (o.setup && o.setup.setups || []).forEach(s => {
      if (Array.isArray(s.missing) && s.missing.length) s.missing[0] = MARCA;
    }), true],
  ['setup.invalidation', '/api/dashboard/state', 'la tarjeta de setups: lo que lo invalida',
    o => (o.setup && o.setup.setups || []).forEach(s => { if (s.invalidation) s.invalidation = MARCA; }), true],
  ['setup.horizon', '/api/dashboard/state', 'la tarjeta de setups: su horizonte',
    o => (o.setup && o.setup.setups || []).forEach(s => { if (s.horizon) s.horizon = MARCA; }), true],
  ['oi data_gaps.exchanges', '/api/oi', 'la tarjeta Open Interest: de que venue es la serie',
    o => { if (o.data_gaps) o.data_gaps.exchanges = [MARCA]; }, true],
  ['oi_context.by_venue.note', '/api/ai/context', 'la tarjeta Open Interest: el alcance del reparto',
    o => { if (o.oi_context && o.oi_context.by_venue) o.oi_context.by_venue.note = MARCA; }, true],
  // EL CONTROL, en la misma pasada. Un campo que la tarjeta NO pinta: si llegara, este check
  // diria que si a cualquier cosa y su VERDE no valdria nada.
  ['setup.daily_flow_source', '/api/dashboard/state', 'CONTROL: campo que la tarjeta NO pinta',
    o => { if (o.setup) o.setup.daily_flow_source = MARCA; }, false],
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

  const perdidos = [], control = [];
  for (const [campo, ruta, que, planta, esperado] of CAMPOS) {
    const t = (url, body) => {
      if (url.split('?')[0] !== ruta) return body;
      const o = JSON.parse(body);
      planta(o);
      return JSON.stringify(o);
    };
    let llega;
    try { llega = (await texto(t)).includes(MARCA); }
    catch (e) { console.log(`NO MEDIDO: el panel reventó midiendo ${campo}: ${String(e && e.message || e).split('\n')[0]}`); process.exit(2); }
    if (esperado && !llega) perdidos.push(`${campo} (${que}, de ${ruta})`);
    if (!esperado && llega) control.push(campo);
  }

  if (control.length) {
    console.log('NO MEDIDO: el control se colo -%s llega a la pantalla y no deberia-, asi que '
      .replace('%s', control.join(' ')) +
      'este check no distingue «se pinta» de «no se pinta» y su verde no valdria nada.');
    process.exit(2);
  }
  if (perdidos.length) {
    console.log(`ROJO: ${perdidos.length} campo(s) que el backend SIRVE dejaron de llegar a su ` +
      `tarjeta: ${perdidos.join(' · ')} · de ${CAMPOS.length - 1} vigilados, medido mutando el ` +
      'payload que la tarjeta LEE y buscando la marca en el DOM');
    process.exit(1);
  }
  console.log(`los ${CAMPOS.length - 1} campos vigilados llegan ESCRITOS a su tarjeta: lo que le ` +
    'falta a cada setup, lo que lo invalida, su horizonte, el venue de la serie de OI y el ' +
    'alcance del reparto por venue. Medido mutando el payload que la tarjeta lee -no el que ' +
    'uno supondria- y buscando la marca en el DOM, con el control de un campo NO pintado ' +
    'saliendo `false` en la misma pasada');
  process.exit(0);
})();
