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
  // ---- MODO MAPA · RESIDUO R-a DE COLA 122 -----------------------------------------------
  // La version anterior mutaba `prim(mapa)` -LA PRIMERA CLAVE- y con eso daba por bueno que
  // «la correlacion por ventana llega». Una tarjeta que pintara SOLO la primera ventana pasaba
  // en VERDE, y la linea afirmaba las tres. Un campo se juzga en TODAS las claves que su
  // tarjeta pinta, o su linea no puede nombrarlo.
  //
  // Se mutan TODAS de una vez y se juzga FILA A FILA: por cada clave tiene que existir una
  // fila que la NOMBRE y esa fila tiene que haberse movido. Cuesta lo mismo que antes -una
  // renderizacion por campo- en vez de una por clave.
  ['cross_asset.correlation', SOBRE, 'Relativo entre activos: el NUMERO de la correlacion, en cada ventana',
    o => mutaMapa(o, ['cross_asset'], 'correlation'), true, 'cross-asset-body',
    o => clavesDe(o, ['cross_asset'], 'correlation')],
  ['cross_asset.beta_vs_base', SOBRE, 'Relativo entre activos: el NUMERO de la beta, en cada ventana',
    o => mutaMapa(o, ['cross_asset'], 'beta_vs_base'), true, 'cross-asset-body',
    o => clavesDe(o, ['cross_asset'], 'beta_vs_base')],
  ['cross_asset.relative_strength_vs_base_pct', SOBRE, 'Relativo entre activos: el NUMERO de la fuerza relativa, en cada ventana',
    // hoy llega {1h:null,4h:null,24h:null}: NO hay numero que mover, asi que no se juzga.
    o => mutaMapa(o, ['cross_asset'], 'relative_strength_vs_base_pct'), true, 'cross-asset-body',
    o => clavesDe(o, ['cross_asset'], 'relative_strength_vs_base_pct')],
  ['volatility.realized_vol_annualized_pct', SOBRE, 'Volatilidad: el NUMERO de la vol. realizada, en cada ventana',
    o => mutaMapa(o, ['volatility'], 'realized_vol_annualized_pct'), true, 'volatilidad-body',
    o => clavesDe(o, ['volatility'], 'realized_vol_annualized_pct')],
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
  ['volatility.atr.*.atr', SOBRE, 'Volatilidad: el ATR en precio, en cada marco',
    o => mutaAnidado(o, ['volatility', 'atr'], 'atr'), true, 'volatilidad-body',
    o => clavesAnidadas(o, ['volatility', 'atr'], 'atr')],
  ['volatility.atr.*.atr_pct', SOBRE, 'Volatilidad: el ATR en % del cierre, en cada marco',
    o => mutaAnidado(o, ['volatility', 'atr'], 'atr_pct'), true, 'volatilidad-body',
    o => clavesAnidadas(o, ['volatility', 'atr'], 'atr_pct')],
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
// --- MAPAS: todas las claves a la vez -------------------------------------------------------
// `num` muta recursivamente cualquier numero que cuelgue del valor: `correlation` es
// {ventana: {activo: numero}} y la beta es {ventana: numero}, y las dos tienen que moverse.
function num(v) {
  if (typeof v === 'number') return otro(v);
  if (Array.isArray(v)) return v.map(num);
  if (v && typeof v === 'object') { const r = {}; for (const k of Object.keys(v)) r[k] = num(v[k]); return r; }
  return v;
}
function tieneNumero(v) {
  if (typeof v === 'number') return true;
  if (Array.isArray(v)) return v.some(tieneNumero);
  if (v && typeof v === 'object') return Object.values(v).some(tieneNumero);
  return false;
}
function clavesDe(o, camino, clave) {
  const p = baja(o, camino), m = p && p[clave];
  if (!m || typeof m !== 'object' || Array.isArray(m)) return [];
  return Object.keys(m).filter(k => tieneNumero(m[k]));
}
function mutaMapa(o, camino, clave) {
  const ks = clavesDe(o, camino, clave);
  if (!ks.length) return false;
  const m = baja(o, camino)[clave];
  for (const k of ks) m[k] = num(m[k]);
  return true;
}
// `volatility.atr` es {marco: {atr, atr_pct}}: la clave de la FILA es el marco y el campo que
// se juzga es una hoja DENTRO de cada marco. Se muta esa hoja en todos los marcos.
function clavesAnidadas(o, camino, hoja) {
  const m = baja(o, camino);
  if (!m) return [];
  return Object.keys(m).filter(k => m[k] && typeof m[k][hoja] === 'number');
}
function mutaAnidado(o, camino, hoja) {
  const ks = clavesAnidadas(o, camino, hoja);
  if (!ks.length) return false;
  const m = baja(o, camino);
  for (const k of ks) m[k][hoja] = otro(m[k][hoja]);
  return true;
}

const limpia = s => (s || '').replace(/\s+/g, ' ').trim();

async function foto(transform) {
  const r = await render({ mode: 'replay', fixtures: FIX, settleMs: 400, frozenAt: 1756300000000, transform });
  for (const l of [...r.document.querySelectorAll('.section-links a')]) {
    l.dispatchEvent(new r.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise(res => setTimeout(res, 400));
  }
  // De cada contenedor se guarda su texto Y EL DE CADA UNA DE SUS FILAS. Las filas son lo que
  // permite juzgar un mapa EN TODAS SUS CLAVES con UNA sola renderizacion: se mutan todas de
  // golpe y despues se pregunta, clave a clave, si hay una fila que la nombre y si esa fila se
  // movio. Sin las filas habria que renderizar una vez por clave -25 renderizaciones mas- y el
  // check pasaria de dos minutos y medio a mas de seis.
  const cont = new Map();
  for (const [, , , , , id] of CAMPOS) {
    if (!id || cont.has(id)) continue;
    const el = r.document.getElementById(id);
    // LAS CELDAS SE UNEN CON SEPARADOR. `textContent` de un <tr> las pega sin nada en medio y
    // la ventana `1h` sale como `1heth 0.76...`: entonces el limite de palabra no casa y el
    // check decia «ninguna fila NOMBRA 1h» con las tres ventanas escritas en la pantalla.
    cont.set(id, el === null ? null : {
      texto: limpia(el.textContent),
      filas: [...el.children].map(c => c.children.length
        ? [...c.children].map(x => limpia(x.textContent)).join(' | ')
        : limpia(c.textContent)),
    });
  }
  const todo = r.document.body.textContent.replace(/\s+/g, ' ').trim();
  try { r.window.close(); } catch (_) {}
  return { todo, cont };
}

// ¿hay alguna fila que NOMBRE esta clave, y se movio esa fila?
// Se exige que la fila la NOMBRE a proposito: un numero que llega sin decir de que ventana o
// de que marco es TAMPOCO LLEGA -residuo R-b de COLA 122-. La tarjeta escribe «ATR · 5m» y
// «Vol. realizada anualizada · 1h»: si dejara de escribir el rotulo, aqui no habria fila que
// mencione la clave y el campo condena, aunque el numero siguiera en pantalla.
function filaDeClave(base, mut, clave) {
  const re = new RegExp('(^|[^0-9a-z])' + clave.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^0-9a-z]|$)', 'i');
  const idx = base.filas.map((t, i) => [t, i]).filter(([t]) => re.test(t)).map(([, i]) => i);
  if (!idx.length) return { nombrada: false, movida: false };
  return { nombrada: true, movida: idx.some(i => (mut.filas[i] === undefined) || (mut.filas[i] !== base.filas[i])) };
}

(async () => {
  let base;
  try { base = await foto(null); }
  catch (e) { console.log('NO MEDIDO: el panel no arranca: ' + String(e && e.message || e).split('\n')[0]); process.exit(2); }
  if (base.todo.includes(MARCA)) { console.log('NO MEDIDO: la marca ya esta en el DOM sin mutar nada'); process.exit(2); }
  if (base.todo.length < 1000) { console.log(`NO MEDIDO: el DOM son ${base.todo.length} B; no hay pantalla que medir`); process.exit(2); }
  // RESIDUO R-c DE COLA 122. Un contenedor que NO EXISTE no puede juzgarse -seria un ROJO por
  // un id mal escrito aqui-, pero ANTES esto APAGABA EL CHECK ENTERO: `exit 2` antes de juzgar
  // a nadie, asi que quitar una tarjeta dejaba sin vigilancia a las otras cuatro y la linea no
  // nombraba ni una. Ahora los demas se juzgan igual y los campos del ausente salen NOMBRADOS
  // con su razon. Nunca callados: un campo que no se juzga y no se dice es un campo sin red.
  const ausentes = new Set([...base.cont].filter(([, v]) => v === null).map(([id]) => id));

  // UN PLANTADO QUE NO OCURRE NO ES UN ROJO, y esto lo cazo la auditoria del operador. Si el
  // backend NO SIRVE el campo, no hay nada que marcar: la ausencia de la marca en el DOM no
  // dice «la tarjeta dejo de pintarlo», dice «no habia que pintar». Tres cubos:
  //     servido y pintado      -> bien
  //     servido y NO pintado   -> ROJO, con su nombre
  //     NO servido             -> no se juzga, y se DICE en la linea de veredicto
  const perdidos = [], control = [], noServidos = [], juzgadosQue = [], sinTarjeta = [];
  for (const [campo, ruta, que, planta, esperado, contenedor, claves] of CAMPOS) {
    if (contenedor && ausentes.has(contenedor)) {
      sinTarjeta.push(`${campo} (su tarjeta \`#${contenedor}\` no existe en el DOM)`);
      continue;
    }
    let planto = false, ks = null;
    const t = (url, body) => {
      if (url.split('?')[0] !== ruta) return body;
      const o = JSON.parse(body);
      if (claves) ks = claves(o);            // las claves SE LEEN DEL PAYLOAD, no se suponen
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
    let llega, detalle = '';
    if (contenedor && claves) {                                  // modo MAPA
      const b = base.cont.get(contenedor), m = f.cont.get(contenedor);
      const mudas = [], sinRotulo = [];
      for (const k of (ks || [])) {
        const v = filaDeClave(b, m, k);
        if (!v.nombrada) sinRotulo.push(k);
        else if (!v.movida) mudas.push(k);
      }
      llega = (ks || []).length > 0 && !mudas.length && !sinRotulo.length;
      if (sinRotulo.length) detalle += `; ninguna fila NOMBRA ${sinRotulo.join(' ')} -un numero sin decir de que ventana o marco es tampoco llega-`;
      if (mudas.length) detalle += `; la fila de ${mudas.join(' ')} no se movio`;
      if (llega) juzgadosQue.push(`${que} [${ks.length}: ${ks.join(' ')}]`);
    } else if (contenedor) {                                     // modo NUMERO
      llega = f.cont.get(contenedor).texto !== base.cont.get(contenedor).texto;
      if (esperado) juzgadosQue.push(que);
    } else {                                                     // modo MARCA
      llega = f.todo.includes(MARCA);
      if (esperado) juzgadosQue.push(que);
    }
    if (esperado && !llega) {
      if (contenedor && claves) juzgadosQue.push(`${que} [${(ks || []).length} claves]`);
      perdidos.push(`${campo} (${que}, de ${ruta}${detalle})`);
    }
    if (!esperado && llega) control.push(campo);
  }

  if (control.length) {
    console.log('NO MEDIDO: el control se colo -%s llega a la pantalla y no deberia-, asi que '
      .replace('%s', control.join(' ')) +
      'este check no distingue «se pinta» de «no se pinta» y su verde no valdria nada.');
    process.exit(2);
  }
  let cola = noServidos.length
    ? ` · ${noServidos.length} NO SE JUZGA(N) porque el backend no los sirvio hoy: ` +
      `${noServidos.join(' ')} -un plantado que no ocurre no es una perdida-`
    : '';
  // Los campos cuya tarjeta no existe SE NOMBRAN. Antes apagaban el check entero (R-c).
  if (sinTarjeta.length) {
    cola += ` · ${sinTarjeta.length} NO SE JUZGA(N) porque SU TARJETA NO ESTA EN LA PAGINA: ` +
      `${sinTarjeta.join(' · ')} -los demas campos si se han juzgado; una tarjeta que falta no ` +
      `deja sin red a las otras, pero SUS campos se quedan sin vigilar y por eso van nombrados-`;
  }
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
    'uno supondria-: los textos por marca en el DOM; las CIFRAS sueltas exigiendo que cambie ' +
    'el texto de su fila o de su tarjeta; y los MAPAS mutando TODAS sus claves y exigiendo, ' +
    'clave a clave, que exista una fila que la NOMBRE y que esa fila se mueva -entre corchetes ' +
    'van las claves de cada uno, que salen del payload y no de una lista escrita a mano-. ' +
    `Dos controles en la misma pasada, uno por modo${cola}`);
  process.exit(0);
})();
