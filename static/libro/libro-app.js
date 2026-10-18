'use strict';
/* EL LIBRO · el estado, la capa de datos y el vivo (campana 145, OF-4b).
 * ---------------------------------------------------------------------------
 * EL ESTADO VIVE EN EL HASH (libro-calculo.js): una vista = una URL; K111 abre una ventana fija del pasado con `hasta=`.
 *
 * UNA SOLA CAPA DE DATOS: lo que va por HTTP, por `pedir()` de static/mesa/mesa-datos.js (la de la mesa y /flujo); el
 * websocket, por `abreVivo()` de aqui. Ninguna URL se construye en otro sitio.
 *
 * LOS CUATRO ESTADOS, y ninguno es cero:
 *   ERROR    la ruta contesto mal o no contesto: se dice con su codigo; lo que habia se queda, dicho
 *   RANCIO   un venue cuyo ultimo aviso tiene mas de ESC_RANCIO_S: no suma en la escalera y se dice
 *   AUSENTE  un instante que nadie escucho (HUECO) o un nivel que nadie conoce (DESCONOCIDO): nunca se rellena
 *   NULO     la ventana entera sin una sola foto: se dice arriba
 *
 * EL VIVO: el websocket /api/libro/vivo si abre; mientras no abre, o si se cae, /api/libro/ultimo cada SONDEO_S (la
 * misma capa de datos), y el websocket se vuelve a intentar cada REINTENTO_WS_S. El cambio es automatico y sin
 * recargar, y la pantalla dice SIEMPRE por cual va y la hora del ultimo libro. La historia del mapa se pide UNA vez
 * (con el `cada` que cabe en el tope); el vivo le AÑADE una columna cada `cada` segundos con los libros vivos.
 */

const RUTA_FOTOS = '/api/libro/fotos';
const RUTA_ULTIMO = '/api/libro/ultimo';
const RUTA_VIVO = '/api/libro/vivo';
const SONDEO_S = 1;
const REINTENTO_WS_S = 30;
const NIVELES_VIVO = 100; // lo maximo que trae el relevo al paso base: cuanto mas pide, mas conoce la escalera

let VISTA = leeHashLibro(window.location.hash);
let EL_MAPA = null;
let LA_ESCALERA = null;
let MODELO = null;
let FALLO = null;
let CARGA = 0;
let DESFASE = 0; // la hora del servidor menos la de esta pagina (de as_of)
const VIVO = { canal: 'ninguno', ws: null, motivoWs: null, sondeo: null, pidiendo: false, reintento: null,
               columna: null, tic: null, libros: {}, fallo: null, relevo: null, pendiente: false };
// LO QUE SE LEE DESDE FUERA (K111, por CDP): `listo` cuando la vista pedida ya esta pintada, `vivo_listo` cuando cada
// venue de la familia ya dijo algo por el vivo, las peticiones, y `repinta()`, que vuelve a pintar AHORA el mapa y la
// escalera (sincrono): asi LIBRO_PINTADO y lo pintado son del mismo fotograma.
window.LIBRO_HITOS = { listo: false, vivo_listo: false, vista: null, peticiones: [], repinta: () => repinta() };
window.LIBRO_PINTADO = { mapa: null, escalera: null };

function ahora() {
  return Date.now() + DESFASE;
}

function apuntar(sobre) {
  window.LIBRO_HITOS.peticiones.push({ ruta: sobre.ruta, ms: Math.round(sobre.ms), http: sobre.http, ok: sobre.ok });
  if (window.LIBRO_HITOS.peticiones.length > 400) window.LIBRO_HITOS.peticiones.splice(0, 200);
}

function venuesVista() {
  return libroVenues(VISTA.familia);
}

/* ------------------------------------------------------------------ la historia */
async function carga() {
  const mia = ++CARGA;
  paraVivo();
  MODELO = null;
  FALLO = null;
  Object.assign(window.LIBRO_HITOS, { listo: false, vivo_listo: false, vista: escribeHashLibro(VISTA) });
  pintaSelectores();
  pintaEstado('pidiendo la historia…');
  const venues = venuesVista();
  const w = ventanaLibro(VISTA, ahora());
  const sobre = await pedir(RUTA_FOTOS, { symbol: VISTA.activo, venues: venues.join(','), desde: w.desde,
                                          hasta: w.hasta, paso: VISTA.paso, cada: w.cada });
  apuntar(sobre);
  if (mia !== CARGA) return;
  if (!sobre.ok) {
    FALLO = sobre;
    EL_MAPA.pon(null);
  } else {
    const asOf = Date.parse(sobre.datos.as_of);
    DESFASE = asOf - Date.now();
    MODELO = { activo: VISTA.activo, familia: VISTA.familia, venues, N: venues.length, paso: sobre.datos.paso,
               cada: w.cada, unidad: VISTA.unidad, desde: w.desde, hasta: w.hasta, asOfMs: asOf,
               fijo: !!VISTA.hasta, aviso: sobre.datos.aviso,
               columnas: columnasDeFotos(sobre.datos, venues, w.columnas, asOf) };
    EL_MAPA.pon(MODELO);
    pideEscalera();
    if (!VISTA.hasta) {
      arrancaVivo();
      recuperaPendientes(mia);
    }
  }
  pintaEstado();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (mia === CARGA) window.LIBRO_HITOS.listo = true;
  }));
}

/* Lo que la base no habia escrito al pedir la historia (su ultimo minuto, «sin escribir aun»): se pide UNA vez mas
 * cuando ya tiene que estar escrito, y sus columnas se sustituyen por las de la base. */
function recuperaPendientes(mia) {
  const pend = MODELO.columnas.filter((c) => c.estado === 'pendiente');
  if (!pend.length) return;
  const desde = pend[0].ts;
  const hasta = pend[pend.length - 1].ts + MODELO.cada * 1000;
  const espera = Math.floor((hasta - 1) / 60000) * 60000 + 60000 + (LIBRO_ESCRITO_S + 3) * 1000 - ahora();
  setTimeout(async () => {
    if (mia !== CARGA || !MODELO) return;
    const sobre = await pedir(RUTA_FOTOS, { symbol: MODELO.activo, venues: MODELO.venues.join(','), desde: isoZ(desde),
                                            hasta: isoZ(hasta), paso: MODELO.paso, cada: MODELO.cada });
    apuntar(sobre);
    if (mia !== CARGA || !MODELO || !sobre.ok) return;
    const inst = pend.map((c) => c.ts);
    const nuevas = new Map(columnasDeFotos(sobre.datos, MODELO.venues, inst, Date.parse(sobre.datos.as_of))
      .map((c) => [c.ts, c]));
    MODELO.columnas = MODELO.columnas.map((c) => nuevas.get(c.ts) || c);
    EL_MAPA.actualiza();
  }, Math.max(1000, espera));
}

/* ------------------------------------------------------------------ el vivo */
function parametrosVivo() {
  return { symbol: VISTA.activo, venues: venuesVista().join(','), paso: VISTA.paso, niveles: NIVELES_VIVO };
}

function abreVivo() {
  const url = new URL(RUTA_VIVO, window.location.href);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  Object.entries(parametrosVivo()).forEach(([k, v]) => url.searchParams.set(k, v));
  let ws;
  try {
    ws = new WebSocket(url.toString());
  } catch (e) {
    VIVO.motivoWs = 'no se pudo abrir: ' + (e && e.message ? e.message : e);
    return;
  }
  VIVO.ws = ws;
  ws.onopen = () => {
    if (VIVO.ws !== ws) return;
    VIVO.canal = 'websocket';
    VIVO.motivoWs = null;
    paraSondeo();
    pintaEstado();
  };
  ws.onmessage = (ev) => {
    if (VIVO.ws !== ws) return;
    let m;
    try {
      m = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    if (m.tipo === 'inicio' || m.tipo === 'latido') VIVO.relevo = m.relevo;
    else recibe(m, 0);
  };
  ws.onclose = (ev) => {
    if (VIVO.ws !== ws) return;
    VIVO.ws = null;
    VIVO.motivoWs = VIVO.canal === 'websocket' ? 'se cerró (código ' + ev.code + ')'
      : 'no abre (código ' + ev.code + '): la red no lo deja pasar';
    arrancaSondeo();
    VIVO.reintento = setTimeout(() => { if (VIVO.tic !== null) abreVivo(); }, REINTENTO_WS_S * 1000);
    pintaEstado();
  };
}

function recibe(m, edadMs) {
  if (!m || !m.venue || !['libro', 'sin_libro', 'sin_dato'].includes(m.tipo)) return;
  VIVO.libros[m.venue] = { m, llegadaMs: ahora() - (edadMs || 0) };
  if (!window.LIBRO_HITOS.vivo_listo && venuesVista().every((v) => VIVO.libros[v] && VIVO.libros[v].m.tipo !== 'sin_dato')) {
    window.LIBRO_HITOS.vivo_listo = true;
  }
  pideEscalera();
}

async function sondea() {
  if (VIVO.pidiendo || document.hidden) return;
  VIVO.pidiendo = true;
  const mia = CARGA;
  const sobre = await pedir(RUTA_ULTIMO, parametrosVivo());
  VIVO.pidiendo = false;
  apuntar(sobre);
  if (mia !== CARGA || VIVO.sondeo === null) return;
  if (!sobre.ok) {
    VIVO.fallo = sobre;
  } else {
    VIVO.fallo = null;
    VIVO.relevo = sobre.datos.relevo;
    if (VIVO.canal !== 'websocket') VIVO.canal = 'sondeo';
    DESFASE = Date.parse(sobre.datos.as_of) - Date.now();
    sobre.datos.libros.forEach((m) => recibe(m, m.edad_ms));
  }
  pintaEstado();
}

function arrancaSondeo() {
  if (VIVO.sondeo !== null) return;
  VIVO.sondeo = setInterval(sondea, SONDEO_S * 1000);
  sondea();
}

function paraSondeo() {
  if (VIVO.sondeo !== null) clearInterval(VIVO.sondeo);
  VIVO.sondeo = null;
}

/* Cada `cada` segundos (en la rejilla), una columna del mapa con los libros VIVOS de ese momento. */
function programaColumna() {
  const c = MODELO.cada * 1000;
  const t = Math.floor(ahora() / c) * c + c;
  VIVO.columna = setTimeout(() => {
    if (!MODELO || MODELO.fijo) return;
    const vivos = MODELO.venues
      .filter((v) => estadoVenue(VIVO.libros[v], ahora()).estado === 'vivo')
      .map((v) => {
        const m = VIVO.libros[v].m;
        return libroDe(v, m.compra, m.venta, m.compras, m.ventas, MODELO.paso);
      });
    const suma = sumaFamilia(vivos, MODELO.N);
    const ultima = MODELO.columnas[MODELO.columnas.length - 1];
    if (!ultima || t > ultima.ts) {
      MODELO.columnas.push({ ts: t, estado: suma ? 'foto' : 'hueco', origen: 'vivo', suma });
      const sobra = MODELO.columnas.length - 2 * Math.ceil((LIBRO_VENTANAS[VISTA.ventana] * 60) / MODELO.cada);
      if (sobra > 0) MODELO.columnas.splice(0, sobra);
      EL_MAPA.actualiza();
    }
    programaColumna();
  }, Math.max(0, t - ahora()));
}

function arrancaVivo() {
  VIVO.libros = {};
  VIVO.canal = 'ninguno';
  VIVO.fallo = null;
  VIVO.motivoWs = null;
  abreVivo();
  arrancaSondeo(); // hasta que el websocket abra: la escalera no espera al apreton
  VIVO.tic = setInterval(() => {
    pideEscalera();
    pintaEstado();
  }, 1000);
  programaColumna();
}

function paraVivo() {
  paraSondeo();
  [VIVO.reintento, VIVO.columna].forEach((t) => { if (t !== null) clearTimeout(t); });
  if (VIVO.tic !== null) clearInterval(VIVO.tic);
  VIVO.reintento = VIVO.columna = VIVO.tic = null;
  if (VIVO.ws) {
    const ws = VIVO.ws;
    VIVO.ws = null;
    ws.close();
  }
  VIVO.canal = 'ninguno';
  VIVO.libros = {};
  window.LIBRO_PINTADO.escalera = null;
}

/* ------------------------------------------------------------------ pintar */
function pintaEscaleraYa() {
  VIVO.pendiente = false;
  if (VISTA.hasta) {
    window.LIBRO_PINTADO.escalera = LA_ESCALERA.pinta(VISTA, venuesVista(), ultimaFotoComoVivo(), 'ninguno', ahora());
    return;
  }
  window.LIBRO_PINTADO.escalera = LA_ESCALERA.pinta(VISTA, venuesVista(), VIVO.libros, VIVO.canal, ahora());
}

function pideEscalera() {
  if (VIVO.pendiente) return;
  VIVO.pendiente = true;
  requestAnimationFrame(pintaEscaleraYa);
}

/* En una ventana FIJA del pasado no hay vivo: la escalera es la de la ULTIMA columna con foto de la ventana (un
 * registro, y lo dice), con la foto de cada venue en ese instante; un venue sin foto en el no conoce nada. */
function ultimaFotoComoVivo() {
  const col = MODELO && MODELO.columnas.slice().reverse().find((c) => c.estado === 'foto');
  const out = {};
  if (!col) return out;
  col.fotos.forEach((f) => { out[f.venue] = { m: fotoComoAviso(f), llegadaMs: ahora() }; });
  MODELO.venues.filter((v) => !out[v]).forEach((v) => {
    out[v] = { m: { tipo: 'sin_dato', venue: v, motivo: 'sin foto en ' + isoZ(col.ts) }, llegadaMs: ahora() };
  });
  return out;
}

function repinta() {
  if (EL_MAPA) EL_MAPA.pinta();
  if (LA_ESCALERA) pintaEscaleraYa();
}

function textoCanal() {
  const ult = Object.values(VIVO.libros).filter((x) => x.m.tipo === 'libro')
    .sort((a, b) => b.m.ts_libro_ms - a.m.ts_libro_ms)[0];
  const hora = ult ? ' · último libro ' + new Date(ult.m.ts_libro_ms).toISOString().slice(11, 23) + 'Z (' + ult.m.venue
    + ', hora del venue)' : ' · todavía sin ningún libro';
  if (VIVO.canal === 'websocket') return 'vivo por WEBSOCKET' + hora;
  if (VIVO.canal === 'sondeo') {
    return 'vivo por SONDEO cada ' + SONDEO_S + ' s de ' + RUTA_ULTIMO + ' (el websocket ' + (VIVO.motivoWs || 'aún no ha abierto')
      + '; se reintenta cada ' + REINTENTO_WS_S + ' s)' + hora;
  }
  return 'vivo: conectando…';
}

function pintaEstado(pidiendo) {
  const caja = vaciar(document.getElementById('estado'));
  if (pidiendo) {
    caja.appendChild(el('span', 'cargando', pidiendo));
    return;
  }
  const linea = (...trozos) => {
    const p = el('p', 'estado-linea');
    trozos.forEach((t) => p.appendChild(typeof t === 'string' ? document.createTextNode(t) : t));
    caja.appendChild(p);
    return p;
  };
  if (FALLO) {
    linea(noSe('error', 'historia: HTTP ' + FALLO.http + ' · ' + (FALLO.motivo || ''))).setAttribute('data-estado', 'error');
  }
  if (VIVO.fallo && !VISTA.hasta) {
    linea(noSe('error', 'vivo: HTTP ' + VIVO.fallo.http + ' · ' + (VIVO.fallo.motivo || '')))
      .setAttribute('data-estado', 'error');
  }
  if (MODELO && !MODELO.columnas.some((c) => c.estado === 'foto')) {
    linea(noSe('nulo', 'la ventana no tiene ni una foto de esta familia: no hay libro que pintar'))
      .setAttribute('data-estado', 'nulo');
  }
  if (MODELO) {
    const huecos = MODELO.columnas.filter((c) => c.estado === 'hueco').length;
    const pend = MODELO.columnas.filter((c) => c.estado === 'pendiente').length;
    linea(el('b', null, VISTA.activo + ' · ' + rotuloFamilia(VISTA.familia)),
      ' (' + MODELO.venues.join(', ') + ') · paso ' + MODELO.paso + ' · ' + VISTA.ventana + ' a una foto cada '
        + MODELO.cada + ' s · ' + (VISTA.unidad === 'usd' ? 'en USD' : 'en ' + VISTA.activo) + ' · '
        + (VISTA.hasta ? 'ventana FIJA hasta ' + VISTA.hasta.slice(0, 16).replace('T', ' ') + 'Z (un registro: sin vivo)'
          : 'el vivo añade una columna cada ' + MODELO.cada + ' s')
        + (huecos ? ' · ' + huecos + ' instante(s) HUECO' : '') + (pend ? ' · ' + pend + ' sin escribir aún' : ''));
    linea(MODELO.aviso).setAttribute('data-estado', 'aviso');
  }
  if (MODELO && !VISTA.hasta) {
    const p = linea(textoCanal());
    p.setAttribute('data-estado', 'canal');
    p.setAttribute('data-canal', VIVO.canal);
  }
}

/* ------------------------------------------------------------------ los mandos */
function pasosDe(activo) {
  return [1, 2, 5, 10, 20, 50].map((m) => nivelTexto(m, LIBRO_PASO[activo]));
}

function pintaSelectores() {
  [['sel-activo', 'activo'], ['sel-familia', 'familia'], ['sel-ventana', 'ventana'], ['sel-unidad', 'unidad']]
    .forEach(([id, k]) => {
      document.querySelectorAll('#' + id + ' button').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.valor === VISTA[k]));
      });
    });
  const sv = vaciar(document.getElementById('sel-venue'));
  ['', ...LIBRO_VENUES].forEach((v) => {
    const op = el('option', null, v || '—');
    op.value = v;
    op.selected = v === VISTA.familia;
    sv.appendChild(op);
  });
  const sp = vaciar(document.getElementById('sel-paso'));
  pasosDe(VISTA.activo).forEach((p) => {
    const op = el('option', null, p);
    op.value = p;
    op.selected = p === VISTA.paso;
    sp.appendChild(op);
  });
  document.getElementById('ir-mesa').setAttribute('href', '/#scalp/' + VISTA.activo);
}

function lectura(col, k) {
  const caja = document.getElementById('lectura');
  if (!col) {
    caja.textContent = '';
    return;
  }
  const t = new Date(col.ts).toISOString().slice(5, 19).replace('T', ' ') + 'Z';
  const est = { hueco: 'HUECO: ningún venue de la familia tenía libro válido', pendiente: 'sin escribir aún' };
  if (col.estado !== 'foto') {
    caja.textContent = t + ' · ' + est[col.estado];
    return;
  }
  const s = col.suma;
  const x = k === null || k < s.lo || k > s.hi ? null : k - s.lo;
  const nivel = k === null ? '' : ' · nivel ' + nivelTexto(k, MODELO.paso);
  if (x === null || !s.n[x]) {
    caja.textContent = t + nivel + ' · DESCONOCIDO: ningún venue de la familia conoce este nivel en este instante';
    return;
  }
  const u = (q) => cifra(enUnidad(q, k, MODELO.paso, VISTA.unidad));
  caja.textContent = t + nivel + ' · compra ' + u(s.c[x]) + ' · venta ' + u(s.v[x]) + ' · lo conocen ' + s.n[x] + ' de '
    + s.N + ' venues' + (s.n[x] < s.N ? ' (la suma es de esos)' : '') + ' · mejor compra ' + s.mejorCompra
    + ' · mejor venta ' + s.mejorVenta + (col.origen === 'vivo' ? ' · columna del vivo' : '');
}

function cambia(cambios) {
  window.location.hash = escribeHashLibro(Object.assign({}, VISTA, cambios));
}

function aplicaHash() {
  const nueva = leeHashLibro(window.location.hash);
  const hash = escribeHashLibro(nueva);
  if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
  VISTA = nueva;
  carga();
}

function arranca() {
  EL_MAPA = creaMapa(document.getElementById('mapa'), lectura);
  LA_ESCALERA = creaEscalera(document.getElementById('escalera'));
  [['sel-activo', 'activo'], ['sel-familia', 'familia'], ['sel-ventana', 'ventana'], ['sel-unidad', 'unidad']]
    .forEach(([id, k]) => {
      document.getElementById(id).addEventListener('click', (ev) => {
        const b = ev.target.closest('button[data-valor]');
        if (!b) return;
        const c = { [k]: b.dataset.valor };
        if (k === 'activo') c.paso = LIBRO_PASO[b.dataset.valor];
        cambia(c);
      });
    });
  document.getElementById('sel-venue').addEventListener('change', (ev) => {
    if (ev.target.value) cambia({ familia: ev.target.value });
  });
  document.getElementById('sel-paso').addEventListener('change', (ev) => cambia({ paso: ev.target.value }));
  window.addEventListener('hashchange', aplicaHash);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && VIVO.sondeo !== null) sondea();
  });
  aplicaHash();
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('DOMContentLoaded', arranca);
}
