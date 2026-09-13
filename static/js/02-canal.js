'use strict';
// como se piden los datos: api/maybe/pedir y el SOBRE
// Trozo 2 de 11 del panel. Sale de static/app.js SIN TOCAR UNA LINEA DE LOGICA
// (FASE 2, 2026-09-13): lineas 161-235 del fichero original.
// El orden de los <script defer> de index.html ES el orden de este fichero: no se
// reordena nada, porque en scripts clasicos un `const` de primer nivel solo existe a
// partir del script que lo declara.
async function api(path) {
  const response = await fetch(path, { headers: { Accept: 'application/json' }, cache: 'no-store' });
  if (!response.ok) { const text = await response.text(); console.error('API_ERROR', path, response.status, text.slice(0, 500)); throw new Error(`${response.status} ${path}`); }
  return response.json();
}
// Un endpoint caido y un endpoint sin datos NO son lo mismo. Antes ambos devolvian el
// fallback vacio y el operador leia "sin datos" ante un 500 de la API o un Postgres caido.
// Ahora el error se conserva en state.errors y la barra global lo muestra.
async function maybe(path, fallback) {
  try {
    const result = await api(path);
    if (state.errors) delete state.errors[path];
    return result;
  } catch (error) {
    if (state.errors) {
      state.errors[path] = { message: String(error && error.message || error), at: Date.now() };
    }
    console.error('endpoint fallo', path, error);
    return fallback;
  }
}
// EL SOBRE, UNA VEZ POR REFRESCO. Se comparte entre refreshOverview y loadView: si dos
// pestanas lo piden a la vez, la segunda espera a la promesa de la primera en vez de abrir
// otra peticion. Sin esto, "una vez por refresco" seria "una vez por pestana".
async function pedirSobre(q, force = false) {
  if (!force && state.sobre && Date.now() - state.sobreAt < 15000) return state.sobre;
  if (state.sobrePendiente) return state.sobrePendiente;
  state.sobrePendiente = maybe(`/api/ai/context?symbol=${q}`, null).then(res => {
    if (res) { state.sobre = res; state.sobreAt = Date.now(); }
    state.sobrePendiente = null;
    pintarEdadFoto();
    return state.sobre;
  });
  return state.sobrePendiente;
}
// LA EDAD, UNA. Las tarjetas FOTO no publican una edad cada una: publican la del sobre,
// que es el unico instante que comparten. Si no hay sobre, lo dice en vez de callar.
function pintarEdadFoto() {
  const pill = $('foto-edad');
  if (!pill) return;
  const gen = state.sobre && state.sobre.generated_at;
  if (!gen) { pill.textContent = 'Foto —'; pill.className = 'live-pill'; pill.title = 'No se pudo leer /api/ai/context'; return; }
  const seg = Math.max(0, Math.round((Date.now() - Date.parse(gen)) / 1000));
  pill.textContent = `Foto ${seg < 90 ? `${seg}s` : `${Math.round(seg / 60)}min`}`;
  pill.className = `live-pill ${seg <= 90 ? 'positive' : seg <= 300 ? 'neutral' : 'negative'}`;
  pill.title = `Edad de /api/ai/context (generated_at ${gen}). UNA para todas las tarjetas FOTO.`;
}
// Lee una seccion del sobre. `fallback` es el MISMO que usaba la llamada suelta que
// sustituye, para que la tarjeta no distinga entre "no hubo sobre" y "no hubo ruta".
function delSobre(clave, fallback) {
  const s = state.sobre;
  if (!s || s[clave] === undefined || s[clave] === null) return fallback;
  return s[clave];
}
// LOS DOS ADAPTADORES, y solo dos. El sobre trae el MISMO dato con otro envase; el envase
// se traduce aqui y NINGUNA funcion de pintado cambia, que es lo que garantiza que no se
// pierde un campo. Medido campo a campo el 2026-09-11 contra las rutas servidas.
function sobreConfianza(fallback) {
  const d = delSobre('data_confidence', null);
  return d ? { rows: [d] } : fallback;   // la ruta envuelve en rows[]; el sobre da la fila
}
function sobreOrderbook(fallback) {
  const ob = delSobre('orderbook', null);
  if (!ob) return fallback;
  // la ruta da rows[] por exchange; el sobre da una clave por exchange + freshness
  const rows = Object.keys(ob).filter(k => k !== 'freshness').map(k => ob[k]);
  return { rows, freshness: ob.freshness, symbol: state.symbol };
}
function lastEndpointError() {
  const entries = Object.entries(state.errors || {});
  if (!entries.length) return null;
  entries.sort((a, b) => b[1].at - a[1].at);
  return { path: entries[0][0], ...entries[0][1], count: entries.length };
}

