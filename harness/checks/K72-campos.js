'use strict';
// La sonda de K72. Vease la cabecera de K72-el-campo-que-no-llega.sh para el criterio.
//
// LA TABLA DE CAMPOS VIVE AQUI Y SE LEE ENTERA: cada fila dice DE QUE RUTA sale el campo y EN
// QUE TARJETA se mira. La ruta no se supone: sale del censo por dato de la FASE 3a -la tarjeta
// de setups se alimenta de /api/dashboard/state aunque el sobre tambien traiga `setup`-.
//
// DOS MODOS DE MEDIR, y el segundo existe por un defecto que tuvo esta sonda:
//
//   MARCA     se sustituye el valor por una cadena reconocible y se busca ESA cadena en el
//             DOM. Vale para textos y listas de textos.
//   NUMERO    se MUTA el valor y se exige que cambie el TEXTO DEL CONTENEDOR de la tarjeta.
//             No se busca ningun valor, asi que no hay coincidencia posible.
//
// POR QUE HIZO FALTA EL SEGUNDO. La primera version marcaba `cross_asset.correlation` y
// `volatility.realized_vol_annualized_pct` anadiendo una CLAVE nueva al objeto de ventanas.
// Eso prueba que la tarjeta ENUMERA las ventanas, NO que escriba sus numeros: con la celda del
// numero borrada, o con la vol. escrita como un «—» fijo, el check seguia diciendo VERDE y su
// linea seguia afirmando que «la correlacion por ventana» llegaba ESCRITA. Era la figura del
// residuo R1 por otra puerta: afirmar una cobertura que no se habia medido.
//
// EN MODO NUMERO EL PLANTADO TIENE QUE MOVER EL NUMERO, no su etiqueta. Por eso se compara el
// contenedor entero: si la tarjeta deja de escribir la cifra y conserva el rotulo, el texto del
// contenedor deja de moverse y el check condena.
const path = require('path');

const REPO = process.env.REPO || '/srv/coinanalyze/repo';
const FIX = process.env.K72_FIXTURES || '/srv/coinanalyze/harness/estado/k31-fixtures';
process.env.REPO = REPO;
const { render } = require(path.join(REPO, 'harness/panel/render.js'));

const MARCA = 'ZZK72ZZ';
const SOBRE = '/api/ai/context';

// muta un numero lo bastante para que cualquier redondeo lo separe del original
const otro = v => (typeof v === 'number' ? v * 3 + 7.77 : v);
// primera clave de un objeto de ventanas, sin suponer cual es
const prim = o => (o && typeof o === 'object' ? Object.keys(o)[0] : undefined);

// [campo, ruta, que, planta, esperado, contenedor]
// `contenedor` presente -> modo NUMERO. Ausente -> modo MARCA.
// Cada `planta` devuelve `false` SI EL CAMPO NO VIENE en el payload. Eso no es un fallo de la
// tarjeta: es que no habia nada que pintar, y se cuenta aparte.
const CAMPOS = [
  // ---- FASE 3a · modo MARCA (textos) -----------------------------------------------------
  ['setup.missing', '/api/dashboard/state', 'la tarjeta de setups: lo que le falta a cada uno',
    o => {
      const con = ((o.setup && o.setup.setups) || []).filter(s => Array.isArray(s.missing) && s.missing.length);
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
  ['oi_context.by_venue.note', SOBRE, 'la tarjeta Open Interest: el alcance del reparto',
    o => {
      if (!o.oi_context || !o.oi_context.by_venue || !o.oi_context.by_venue.note) return false;
      o.oi_context.by_venue.note = MARCA;
      return true;
    }, true],
  ['operator_read.invalidates_long', SOBRE, 'Que invalida la lectura: las condiciones del largo',
    o => {
      const op = o.operator_read;
      if (!op || !Array.isArray(op.invalidates_long) || !op.invalidates_long.length) return false;
      op.invalidates_long[0] = MARCA;
      return true;
    }, true],
  ['operator_read.invalidates_short', SOBRE, 'Que invalida la lectura: las condiciones del corto',
    o => {
      const op = o.operator_read;
      if (!op || !Array.isArray(op.invalidates_short) || !op.invalidates_short.length) return false;
      op.invalidates_short[0] = MARCA;
      return true;
    }, true],

  // ---- FASE 3b · modo NUMERO (cifras) ----------------------------------------------------
  ['cross_asset.correlation', SOBRE, 'Relativo entre activos: el NUMERO de la correlacion',
    o => {
      const c = o.cross_asset && o.cross_asset.correlation, w = prim(c);
      if (!w || !c[w] || typeof c[w] !== 'object') return false;
      const a = prim(c[w]);
      if (a === undefined || typeof c[w][a] !== 'number') return false;
      c[w][a] = otro(c[w][a]);
      return true;
    }, true, 'cross-asset-body'],
  ['cross_asset.beta_vs_base', SOBRE, 'Relativo entre activos: el NUMERO de la beta',
    o => {
      const b = o.cross_asset && o.cross_asset.beta_vs_base, w = prim(b);
      if (w === undefined || typeof b[w] !== 'number') return false;
      b[w] = otro(b[w]);
      return true;
    }, true, 'cross-asset-body'],
  ['cross_asset.relative_strength_vs_base_pct', SOBRE, 'Relativo entre activos: el NUMERO de la fuerza relativa',
    o => {
      const r = o.cross_asset && o.cross_asset.relative_strength_vs_base_pct, w = prim(r);
      // hoy llega {1h:null,4h:null,24h:null}: NO hay numero que mover, asi que no se juzga.
      if (w === undefined || typeof r[w] !== 'number') return false;
      r[w] = otro(r[w]);
      return true;
    }, true, 'cross-asset-body'],
  ['volatility.realized_vol_annualized_pct', SOBRE, 'Volatilidad: el NUMERO de la vol. realizada',
    o => {
      const v = o.volatility && o.volatility.realized_vol_annualized_pct, w = prim(v);
      if (w === undefined || typeof v[w] !== 'number') return false;
      v[w] = otro(v[w]);
      return true;
    }, true, 'volatilidad-body'],
  ['volatility.daily_range_percentile_1y', SOBRE, 'Volatilidad: el percentil de rango diario',
    o => {
      if (!o.volatility || typeof o.volatility.daily_range_percentile_1y !== 'number') return false;
      o.volatility.daily_range_percentile_1y = otro(o.volatility.daily_range_percentile_1y);
      return true;
    }, true, 'volatilidad-body'],
  ['volatility.compression_score', SOBRE, 'Volatilidad: la compresion',
    o => {
      if (!o.volatility || typeof o.volatility.compression_score !== 'number') return false;
      o.volatility.compression_score = otro(o.volatility.compression_score);
      return true;
    }, true, 'volatilidad-body'],
  ['volatility.range_expansion', SOBRE, 'Volatilidad: la expansion de rango',
    o => {
      if (!o.volatility || typeof o.volatility.range_expansion !== 'boolean') return false;
      o.volatility.range_expansion = !o.volatility.range_expansion;
      return true;
    }, true, 'volatilidad-body'],
  ['volatility.atr.*.atr', SOBRE, 'Volatilidad: el ATR en precio',
    o => {
      const a = o.volatility && o.volatility.atr, tf = prim(a);
      if (tf === undefined || !a[tf] || typeof a[tf].atr !== 'number') return false;
      a[tf].atr = otro(a[tf].atr);
      return true;
    }, true, 'volatilidad-body'],
  ['volatility.atr.*.atr_pct', SOBRE, 'Volatilidad: el ATR en % del cierre',
    o => {
      const a = o.volatility && o.volatility.atr, tf = prim(a);
      if (tf === undefined || !a[tf] || typeof a[tf].atr_pct !== 'number') return false;
      a[tf].atr_pct = otro(a[tf].atr_pct);
      return true;
    }, true, 'volatilidad-body'],
  ['volume_profile.session.poc', SOBRE, 'Perfil de volumen: el POC',
    o => plantaNum(o, ['volume_profile', 'session'], 'poc'), true, 'perfil-vol-body'],
  ['volume_profile.session.vah', SOBRE, 'Perfil de volumen: el VAH',
    o => plantaNum(o, ['volume_profile', 'session'], 'vah'), true, 'perfil-vol-body'],
  ['volume_profile.session.val', SOBRE, 'Perfil de volumen: el VAL',
    o => plantaNum(o, ['volume_profile', 'session'], 'val'), true, 'perfil-vol-body'],
  ['volume_profile.session.hvn', SOBRE, 'Perfil de volumen: los nodos de alto volumen',
    o => plantaLista(o, ['volume_profile', 'session'], 'hvn'), true, 'perfil-vol-body'],
  ['volume_profile.session.lvn', SOBRE, 'Perfil de volumen: los nodos de bajo volumen',
    o => plantaLista(o, ['volume_profile', 'session'], 'lvn'), true, 'perfil-vol-body'],
  ['volume_profile.vwap.utc_day', SOBRE, 'Perfil de volumen: el VWAP del dia',
    o => plantaNum(o, ['volume_profile', 'vwap'], 'utc_day'), true, 'perfil-vol-body'],
  ['volume_profile.vwap.weekly', SOBRE, 'Perfil de volumen: el VWAP de la semana',
    o => plantaNum(o, ['volume_profile', 'vwap'], 'weekly'), true, 'perfil-vol-body'],
  ['volume_profile.vwap.bands.plus_1sigma', SOBRE, 'Perfil de volumen: la banda +1 sigma',
    o => plantaNum(o, ['volume_profile', 'vwap', 'bands'], 'plus_1sigma'), true, 'perfil-vol-body'],
  ['volume_profile.vwap.bands.minus_1sigma', SOBRE, 'Perfil de volumen: la banda -1 sigma',
    o => plantaNum(o, ['volume_profile', 'vwap', 'bands'], 'minus_1sigma'), true, 'perfil-vol-body'],
  ['volume_profile.vwap.bands.plus_2sigma', SOBRE, 'Perfil de volumen: la banda +2 sigma',
    o => plantaNum(o, ['volume_profile', 'vwap', 'bands'], 'plus_2sigma'), true, 'perfil-vol-body'],
  ['volume_profile.vwap.bands.minus_2sigma', SOBRE, 'Perfil de volumen: la banda -2 sigma',
    o => plantaNum(o, ['volume_profile', 'vwap', 'bands'], 'minus_2sigma'), true, 'perfil-vol-body'],
  // LA RAFAGA SE VIGILA POR FILA Y NO POR TARJETA. Su ultima fila es DERIVADA de `total` y
  // `baseline_5m`, asi que mutar `total` movia el texto de la tarjeta AUNQUE la fila del Total
  // hubiera perdido su cifra: el check decia VERDE. Lo encontro un plantado mio -C7-, no un
  // razonamiento. Apuntando a la fila, «llega» vuelve a significar «esta escrito AHI».
  ['liq_burst.long_liq', SOBRE, 'Rafaga de liquidaciones: los largos liquidados',
    o => plantaNum(o, ['liq_burst'], 'long_liq'), true, 'fila-liq-largos'],
  ['liq_burst.short_liq', SOBRE, 'Rafaga de liquidaciones: los cortos liquidados',
    o => plantaNum(o, ['liq_burst'], 'short_liq'), true, 'fila-liq-cortos'],
  ['liq_burst.total', SOBRE, 'Rafaga de liquidaciones: el total',
    o => plantaNum(o, ['liq_burst'], 'total'), true, 'fila-liq-total'],
  ['liq_burst.events', SOBRE, 'Rafaga de liquidaciones: el numero de eventos',
    o => plantaNum(o, ['liq_burst'], 'events'), true, 'fila-liq-eventos'],
  ['liq_burst.baseline_5m', SOBRE, 'Rafaga de liquidaciones: la mediana por 5 min en 3 h',
    o => plantaNum(o, ['liq_burst'], 'baseline_5m'), true, 'fila-liq-mediana'],

  // ---- LOS DOS CONTROLES, en la misma pasada ---------------------------------------------
  // Uno por modo. Si cualquiera de los dos llegara, este check estaria diciendo que si a
  // cualquier cosa y su VERDE no valdria nada.
  ['setup.daily_flow_source', '/api/dashboard/state', 'CONTROL(marca): campo que la tarjeta NO pinta',
    o => {
      if (!o.setup || o.setup.daily_flow_source === undefined) return false;
      o.setup.daily_flow_source = MARCA;
      return true;
    }, false],
  ['operator_read.edge', SOBRE, 'CONTROL(numero): campo servido que NINGUNA tarjeta pinta',
    o => plantaNum(o, ['operator_read'], 'edge'), false, 'invalida-body'],
];

function baja(o, camino) {
  let x = o;
  for (const k of camino) { if (!x || typeof x !== 'object') return null; x = x[k]; }
  return (x && typeof x === 'object') ? x : null;
}
function plantaNum(o, camino, clave) {
  const p = baja(o, camino);
  if (!p || typeof p[clave] !== 'number') return false;
  p[clave] = otro(p[clave]);
  return true;
}
function plantaLista(o, camino, clave) {
  const p = baja(o, camino);
  if (!p || !Array.isArray(p[clave]) || !p[clave].length) return false;
  p[clave] = p[clave].map(otro);
  return true;
}

async function foto(transform) {
  const r = await render({ mode: 'replay', fixtures: FIX, settleMs: 400, frozenAt: 1756300000000, transform });
  for (const l of [...r.document.querySelectorAll('.section-links a')]) {
    l.dispatchEvent(new r.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise(res => setTimeout(res, 400));
  }
  const cont = new Map();
  for (const [, , , , , id] of CAMPOS) {
    if (!id || cont.has(id)) continue;
    const el = r.document.getElementById(id);
    cont.set(id, el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : null);
  }
  const todo = r.document.body.textContent.replace(/\s+/g, ' ').trim();
  try { r.window.close(); } catch (_) {}
  return { todo, cont };
}

(async () => {
  let base;
  try { base = await foto(null); }
  catch (e) { console.log('NO MEDIDO: el panel no arranca: ' + String(e && e.message || e).split('\n')[0]); process.exit(2); }
  if (base.todo.includes(MARCA)) { console.log('NO MEDIDO: la marca ya esta en el DOM sin mutar nada'); process.exit(2); }
  if (base.todo.length < 1000) { console.log(`NO MEDIDO: el DOM son ${base.todo.length} B; no hay pantalla que medir`); process.exit(2); }
  // Un contenedor que NO EXISTE no puede juzgarse: seria un ROJO por un id mal escrito aqui.
  const sinNodo = [...base.cont].filter(([, t]) => t === null).map(([id]) => id);
  if (sinNodo.length) {
    console.log(`NO MEDIDO: ${sinNodo.length} contenedor(es) no existen en el DOM: ${sinNodo.join(' ')}`);
    process.exit(2);
  }

  // UN PLANTADO QUE NO OCURRE NO ES UN ROJO, y esto lo cazo la auditoria del operador. Si el
  // backend NO SIRVE el campo, no hay nada que marcar: la ausencia de la marca en el DOM no
  // dice «la tarjeta dejo de pintarlo», dice «no habia que pintar». Tres cubos:
  //     servido y pintado      -> bien
  //     servido y NO pintado   -> ROJO, con su nombre
  //     NO servido             -> no se juzga, y se DICE en la linea de veredicto
  const perdidos = [], control = [], noServidos = [], juzgadosQue = [];
  for (const [campo, ruta, que, planta, esperado, contenedor] of CAMPOS) {
    let planto = false;
    const t = (url, body) => {
      if (url.split('?')[0] !== ruta) return body;
      const o = JSON.parse(body);
      planto = planta(o) !== false;
      return JSON.stringify(o);
    };
    let f;
    try { f = await foto(t); }
    catch (e) { console.log(`NO MEDIDO: el panel reventó midiendo ${campo}: ${String(e && e.message || e).split('\n')[0]}`); process.exit(2); }
    if (!planto) { noServidos.push(campo); continue; }
    // Si la mutacion tumba el panel, «cambio el contenedor» no significaria nada.
    if (contenedor && f.todo.length < base.todo.length * 0.8) {
      console.log(`NO MEDIDO: mutar ${campo} tumba el panel (DOM ${f.todo.length} de ${base.todo.length})`);
      process.exit(2);
    }
    const llega = contenedor
      ? (f.cont.get(contenedor) !== base.cont.get(contenedor))   // modo NUMERO
      : f.todo.includes(MARCA);                                  // modo MARCA
    if (esperado) juzgadosQue.push(que);
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
  const juzgados = juzgadosQue.length;

  if (perdidos.length) {
    console.log(`ROJO: ${perdidos.length} campo(s) que el backend SIRVE dejaron de llegar a su ` +
      `tarjeta: ${perdidos.join(' · ')} · de ${juzgados} juzgados, medido mutando el ` +
      `payload que la tarjeta LEE y exigiendo que se mueva el DOM${cola}`);
    process.exit(1);
  }
  if (!juzgados) {
    console.log('NO MEDIDO: el backend no sirvio hoy ninguno de los campos vigilados, asi que ' +
      `no hay nada que juzgar${cola}`);
    process.exit(2);
  }
  // RESIDUO R1 (COLA 121): esta linea ENUMERABA CINCO COSAS FIJAS pasara lo que pasara, asi que
  // se atribuia una cobertura que no habia medido. La lista se construye de los que de verdad
  // se juzgaron, y en modo NUMERO «llega» significa que se movio la CIFRA, no su etiqueta.
  console.log(`los ${juzgados} campos servidos hoy llegan ESCRITOS a su tarjeta: ` +
    `${juzgadosQue.join(' · ')}. Medido mutando el payload que la tarjeta lee -no el que ` +
    'uno supondria-: los textos por marca en el DOM, y las CIFRAS exigiendo que cambie el ' +
    'texto del contenedor de su tarjeta, que es lo unico que distingue escribir el numero de ' +
    `escribir solo su rotulo. Dos controles en la misma pasada, uno por modo${cola}`);
  process.exit(0);
})();
