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
const RUTA_CINTA = '/api/orderflow/cinta';
const RUTA_PERFIL = '/api/orderflow/perfil';
const RUTA_HONDA = '/api/libro/honda';
const RUTA_HUELLA = '/api/orderflow/footprint';
const HUELLA_RETRASO_S = 10; // cuanto despues del borde de minuto se vuelve a pedir el footprint en vivo
// LA CAPA HONDA EN VIVO (149 B r1): cada HONDA_CADA_S (en su rejilla, HONDA_RETRASO_S despues) se pide lo nuevo
const HONDA_EN_VIVO = true;
const HONDA_CADA_S = 30;
const HONDA_RETRASO_S = 5;
const CINTA_S = 1; // la cinta de la vista, una pagina por segundo (minutos=1, limit=1000), sin solapar
const PERFIL_S = 60; // el maximo y minimo de la sesion UTC, del perfil desde las 00:00Z
const TIEMPOS_MAX = 2000;
const NIVELES_VIVO = 100; // lo maximo que trae el relevo al paso base: cuanto mas pide, mas conoce la escalera

let VISTA = leeHashLibro(window.location.hash);
let EL_MAPA = null;
let LA_ESCALERA = null;
let MODELO = null;
let FALLO = null;
let CARGA = 0;
let DESFASE = 0; // la hora del servidor menos la de esta pagina (de as_of)
const VIVO = { canal: 'ninguno', ws: null, motivoWs: null, sondeo: null, pidiendo: false, reintento: null,
               columna: null, huella: null, honda: null, pidiendoHonda: false, tic: null, libros: {}, fallo: null, relevo: null, pendiente: false };
// EL VOLUMEN RECIENTE (L-07): lo que la cinta ya conto (sumaReciente), si contesta, y el perfil de la sesion UTC
const CINTA = { rec: recienteVacio(), estado: 'pendiente', fallo: null, pidiendo: false, latido: null,
                perfil: null, perfilFallo: null, pidiendoPerfil: false, latidoPerfil: null };
// LO QUE SE LEE DESDE FUERA (K111, por CDP): `listo` cuando la vista pedida ya esta pintada, `vivo_listo` cuando cada
// venue de la familia ya dijo algo por el vivo, las peticiones, y `repinta()`, que vuelve a pintar AHORA el mapa y la
// escalera (sincrono): asi LIBRO_PINTADO y lo pintado son del mismo fotograma.
window.LIBRO_HITOS = { listo: false, vivo_listo: false, vista: null, peticiones: [], repinta: () => repinta() };
// `congela()` (para K111): el vivo deja de tocar la pantalla -ni mensajes, ni sondeo, ni columnas- y se repinta; asi lo
// pintado es lo de los mensajes ya procesados, que se cuentan por canal en `recibidos` (los primeros N marcos del
// websocket, o las primeras N respuestas del sondeo, son exactamente los que la pantalla uso).
Object.assign(window.LIBRO_HITOS, { recibidos: { websocket: 0, sondeo: 0, cinta: 0, perfil: 0, huella: 0, honda: 0 },
                                    congelado: false, tiempos: [],
                                    congela: () => congela() });
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
  // la historia, la capa honda (desde 75 s antes: la primera columna puede usar una foto de antes de la ventana) y el
  // footprint 1m de la ventana, a la vez. EL FOOTPRINT (149 B r1) con el contrato de la ruta real: desde y hasta en
  // borde de minuto, SIEMPRE los dos (fuera de borde, o sin hasta, contesta 422): desde al borde por debajo, hasta al
  // de por encima; lo que cae fuera de la ventana del mapa no se pinta
  const q = { symbol: VISTA.activo, venues: venues.join(','), hasta: w.hasta };
  const hDesde = isoZ(Math.floor(Date.parse(w.desde) / 60000) * 60000);
  const hHasta = isoZ(Math.ceil(Date.parse(w.hasta) / 60000) * 60000);
  const [sobre, honda, huella] = await Promise.all([
    pedir(RUTA_FOTOS, Object.assign({ desde: w.desde, paso: VISTA.paso, cada: w.cada }, q)),
    pedir(RUTA_HONDA, Object.assign({ desde: isoZ(Date.parse(w.desde) - HONDA_RANCIA_S * 1000) }, q)),
    pedir(RUTA_HUELLA, Object.assign({}, q, { desde: hDesde, hasta: hHasta, marco: '1m', paso: VISTA.paso, unidad: 'base' })),
  ]);
  [sobre, honda, huella].forEach(apuntar);
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
               columnas: columnasDeFotos(sobre.datos, venues, w.columnas, asOf), ahora,
               huella: huella.ok ? { desde: hDesde, hasta: hHasta, velas: huella.datos.velas || [] } : null,
               huellaUltimo: Date.parse(hHasta) - 60000,
               huellaFallo: huella.ok ? null : 'el footprint respondió ' + (huella.http || 'nada') };
    // la capa honda, junta a las columnas de la historia y, en vivo, a las nuevas (anadeHonda): al paso guardado
    MODELO.hondaFotos = new Map();
    MODELO.hondaUltima = null;
    if (honda.ok) anadeHonda(honda.datos);
    MODELO.honda = honda.ok ? rejuntaHonda()
      : { pinta: false, motivo: 'la capa honda respondió ' + (honda.http || 'nada'), columnas: 0 };
    EL_MAPA.pon(MODELO, VISTA.ver);
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
    if (HONDA_EN_VIVO && MODELO.honda && MODELO.honda.pinta) MODELO.honda = rejuntaHonda(desde);
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
    if (window.LIBRO_HITOS.congelado) return;
    window.LIBRO_HITOS.recibidos.websocket += 1;
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
  if (window.LIBRO_HITOS.congelado) return;
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
  if (mia !== CARGA || VIVO.sondeo === null || window.LIBRO_HITOS.congelado) return;
  window.LIBRO_HITOS.recibidos.sondeo += 1;
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
      MODELO.columnas.push({ ts: t, estado: suma ? 'foto' : 'hueco', origen: 'vivo', suma, libros: vivos });
      const sobra = MODELO.columnas.length - 2 * Math.ceil((LIBRO_VENTANAS[VISTA.ventana] * 60) / MODELO.cada);
      if (sobra > 0) MODELO.columnas.splice(0, sobra);
      if (HONDA_EN_VIVO && MODELO.honda && MODELO.honda.pinta) MODELO.honda = rejuntaHonda(t);
      EL_MAPA.actualiza();
    }
    programaColumna();
  }, Math.max(0, t - ahora()));
}

/* EL FOOTPRINT EN VIVO (149 B r1): cada minuto CERRADO se vuelve a pedir, desde el ultimo minuto pedido (el que estaba
 * en curso, o el primero que fallo) hasta el borde de minuto siguiente; sus velas sustituyen a las que tenia de ese
 * desde en adelante, y las de antes de la primera columna del mapa se tiran: el volumen de debajo y el perfil de lo
 * negociado siguen al mapa. Cada respuesta procesada se cuenta en `recibidos.huella`. */
function programaHuella() {
  const t = Math.floor(ahora() / 60000) * 60000 + 60000;
  VIVO.huella = setTimeout(() => {
    lateHuella(CARGA, t);
    programaHuella();
  }, Math.max(0, t - ahora()) + HUELLA_RETRASO_S * 1000);
}

async function lateHuella(mia, t) {
  if (!MODELO || MODELO.fijo || window.LIBRO_HITOS.congelado) return;
  const desde = Math.min(MODELO.huellaUltimo, t - 60000);
  const hasta = t + 60000;
  const sobre = await pedir(RUTA_HUELLA, { symbol: MODELO.activo, venues: MODELO.venues.join(','), desde: isoZ(desde),
                                          hasta: isoZ(hasta), marco: '1m', paso: MODELO.paso, unidad: 'base' });
  apuntar(sobre);
  if (mia !== CARGA || !MODELO || window.LIBRO_HITOS.congelado) return;
  window.LIBRO_HITOS.recibidos.huella += 1;
  if (!sobre.ok) {
    MODELO.huellaFallo = 'el footprint respondió ' + (sobre.http || 'nada');
    return;
  }
  const primera = MODELO.columnas.length ? Math.floor(MODELO.columnas[0].ts / 60000) * 60000 : desde;
  const viejas = MODELO.huella ? MODELO.huella.velas.filter((v) => {
    const ts = Date.parse(v.ts);
    return ts < desde && ts >= primera;
  }) : [];
  MODELO.huella = { desde: isoZ(Math.max(primera, MODELO.huella ? Date.parse(MODELO.huella.desde) : desde)),
                    hasta: isoZ(hasta), velas: viejas.concat(sobre.datos.velas || []) };
  MODELO.huellaUltimo = t;
  MODELO.huellaFallo = null;
  EL_MAPA.actualiza();
}

/* LA CAPA HONDA EN VIVO (149 B r1). Las fotos recibidas se guardan por venue|ts (la ultima respuesta manda); al llegar
 * una nueva se vuelven a juntar las columnas desde su ts (una foto de ts x solo cambia columnas de ts >= x: las de los
 * ultimos 75 s, o menos). Cada HONDA_CADA_S se pide desde la ultima foto recibida menos 75 s (lo que una foto
 * escrita tarde puede cambiar) hasta el siguiente borde de la rejilla. Cada respuesta procesada se cuenta en
 * `recibidos.honda` (K111 rehace la junta con las primeras N). La misma regla que la historia: juntaHonda. */
function anadeHonda(d) {
  let min = null;
  ((d && d.fotos) || []).forEach((f) => {
    MODELO.hondaFotos.set(f.venue + '|' + f.ts, f);
    const t = Date.parse(f.ts);
    if (min === null || t < min) min = t;
    if (MODELO.hondaUltima === null || t > MODELO.hondaUltima) MODELO.hondaUltima = t;
  });
  const primera = MODELO.columnas.length ? MODELO.columnas[0].ts - HONDA_RANCIA_S * 1000 : null;
  if (primera !== null) {
    MODELO.hondaFotos.forEach((f, k) => { if (Date.parse(f.ts) < primera) MODELO.hondaFotos.delete(k); });
  }
  return min;
}

function rejuntaHonda(desdeMs) {
  return juntaHonda(MODELO.columnas, { fotos: [...MODELO.hondaFotos.values()] }, MODELO.venues, MODELO.paso,
                    LIBRO_PASO[MODELO.activo], desdeMs);
}

function programaHonda() {
  const c = HONDA_CADA_S * 1000;
  const t = Math.floor(ahora() / c) * c + c;
  VIVO.honda = setTimeout(() => {
    lateHonda(CARGA, t);
    programaHonda();
  }, Math.max(0, t - ahora()) + HONDA_RETRASO_S * 1000);
}

async function lateHonda(mia, t) {
  if (!MODELO || MODELO.fijo || !MODELO.honda || !MODELO.honda.pinta || VIVO.pidiendoHonda
      || window.LIBRO_HITOS.congelado) return;
  const desde = Math.max(MODELO.hondaUltima === null ? Date.parse(MODELO.desde) : MODELO.hondaUltima,
                         MODELO.columnas.length ? MODELO.columnas[0].ts : 0) - HONDA_RANCIA_S * 1000;
  VIVO.pidiendoHonda = true;
  const sobre = await pedir(RUTA_HONDA, { symbol: MODELO.activo, venues: MODELO.venues.join(','), desde: isoZ(desde),
                                         hasta: isoZ(t + HONDA_CADA_S * 1000) });
  VIVO.pidiendoHonda = false;
  apuntar(sobre);
  if (mia !== CARGA || !MODELO || window.LIBRO_HITOS.congelado) return;
  window.LIBRO_HITOS.recibidos.honda += 1;
  if (!sobre.ok) return; // la junta de antes sigue: se dice en el canal de la capa por la linea de debajo
  const min = anadeHonda(sobre.datos);
  if (min === null) return;
  MODELO.honda = rejuntaHonda(min);
  EL_MAPA.actualiza();
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
  programaHuella();
  if (HONDA_EN_VIVO) programaHonda();
  CINTA.latido = setInterval(() => lateCinta(CARGA), CINTA_S * 1000);
  CINTA.latidoPerfil = setInterval(() => lateSesion(CARGA), PERFIL_S * 1000);
  lateCinta(CARGA);
  lateSesion(CARGA);
}

function paraCinta() {
  [CINTA.latido, CINTA.latidoPerfil].forEach((t) => { if (t !== null) clearInterval(t); });
  CINTA.latido = CINTA.latidoPerfil = null;
}

/* Una pagina de la cinta: la escalera cuenta lo que trae de nuevo. Una caida se dice (columnas vacias), nunca ceros.
 * Cada respuesta, buena o mala, se cuenta en `recibidos.cinta` (K111 rehace la cuenta con las primeras N). */
async function lateCinta(mia) {
  if (CINTA.pidiendo || document.hidden || VISTA.hasta || window.LIBRO_HITOS.congelado) return;
  CINTA.pidiendo = true;
  const sobre = await pedir(RUTA_CINTA, { symbol: VISTA.activo, venues: venuesVista().join(','), minutos: 1,
                                         limit: 1000 });
  CINTA.pidiendo = false;
  if (mia !== CARGA || window.LIBRO_HITOS.congelado) return;
  window.LIBRO_HITOS.recibidos.cinta += 1;
  if (sobre.ok) {
    CINTA.rec = sumaReciente(CINTA.rec, sobre.datos, VISTA.paso);
    CINTA.estado = 'ok';
    CINTA.fallo = null;
  } else {
    CINTA.estado = 'caida';
    CINTA.fallo = 'HTTP ' + sobre.http + (sobre.motivo ? ': ' + sobre.motivo : '');
  }
  pideEscalera();
}

async function lateSesion(mia) {
  if (CINTA.pidiendoPerfil || document.hidden || VISTA.hasta || window.LIBRO_HITOS.congelado) return;
  CINTA.pidiendoPerfil = true;
  const t = ahora();
  const dia = isoZ(t).slice(0, 10);
  const sobre = await pedir(RUTA_PERFIL, { symbol: VISTA.activo, desde: dia + 'T00:00:00Z', hasta: isoZ(t),
                                          paso: VISTA.paso, venues: venuesVista().join(','), unidad: 'base' });
  CINTA.pidiendoPerfil = false;
  if (mia !== CARGA || window.LIBRO_HITOS.congelado) return;
  window.LIBRO_HITOS.recibidos.perfil += 1;
  if (sobre.ok) {
    CINTA.perfil = { dia, niveles: sobre.datos.niveles || [] };
    CINTA.perfilFallo = null;
  } else {
    CINTA.perfilFallo = 'HTTP ' + sobre.http;
  }
  pideEscalera();
}

function limpiaCinta() {
  CINTA.rec = limpiaReciente(CINTA.rec);
}

function paraVivo() {
  paraCinta();
  Object.assign(CINTA, { rec: recienteVacio(), estado: 'pendiente', fallo: null, perfil: null, perfilFallo: null });
  paraSondeo();
  [VIVO.reintento, VIVO.columna, VIVO.huella, VIVO.honda].forEach((t) => { if (t !== null) clearTimeout(t); });
  if (VIVO.tic !== null) clearInterval(VIVO.tic);
  VIVO.reintento = VIVO.columna = VIVO.huella = VIVO.honda = VIVO.tic = null;
  VIVO.pidiendoHonda = false;
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
    apuntaPinta(LA_ESCALERA.pinta(VISTA, venuesVista(), ultimaFotoComoVivo(), 'ninguno', ahora(),
                                  { rec: null, cinta: 'fija', perfil: null }));
    return;
  }
  apuntaPinta(LA_ESCALERA.pinta(VISTA, venuesVista(), VIVO.libros, VIVO.canal, ahora(),
                                { rec: CINTA.rec, cinta: CINTA.estado, motivo: CINTA.fallo, perfil: CINTA.perfil }));
}

/* lo pintado, para K111, y lo que tardo cada pinta() (P1 de la campana 149) */
function apuntaPinta(reg) {
  window.LIBRO_PINTADO.escalera = reg;
  const ts = window.LIBRO_HITOS.tiempos;
  ts.push(reg.ms);
  const pz = window.LIBRO_HITOS.piezas || (window.LIBRO_HITOS.piezas = []);
  pz.push(reg.piezas);
  if (pz.length > TIEMPOS_MAX) pz.splice(0, pz.length - TIEMPOS_MAX);
  if (ts.length > TIEMPOS_MAX) ts.splice(0, ts.length - TIEMPOS_MAX);
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

function congela() {
  window.LIBRO_HITOS.congelado = true;
  paraSondeo();
  [VIVO.reintento, VIVO.columna, VIVO.huella, VIVO.honda].forEach((t) => { if (t !== null) clearTimeout(t); });
  if (VIVO.tic !== null) clearInterval(VIVO.tic);
  VIVO.reintento = VIVO.columna = VIVO.huella = VIVO.honda = VIVO.tic = null;
  VIVO.pidiendoHonda = false;
  paraCinta();
  repinta();
}

function repinta() {
  if (EL_MAPA) EL_MAPA.pinta(true);
  if (LA_ESCALERA) pintaEscaleraYa();
  pintaEstado();
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

/* (149 rC, H-09) lo que hay bajo el raton: la ficha junto al cursor y #lectura en una linea, con las MISMAS palabras
 * (fichaDe de libro-mapa.js); la escalera resalta la fila de ese precio si la tiene a la vista (H-01). */
function lectura(f, pos) {
  const caja = document.getElementById('lectura');
  const ficha = document.getElementById('ficha');
  const esc = LA_ESCALERA ? LA_ESCALERA.resalta(f ? f.nivel : null) : null;
  if (window.LIBRO_CRUZ) window.LIBRO_CRUZ.escalera = esc;
  if (!f) {
    caja.textContent = '';
    ficha.hidden = true;
    return;
  }
  caja.textContent = f.texto;
  while (ficha.firstChild) ficha.removeChild(ficha.firstChild);
  f.lineas.forEach(([campo, t]) => {
    const d = document.createElement('div');
    d.dataset.campo = campo;
    d.textContent = t;
    if (campo === 'cab') d.className = 'ficha-cab';
    else if (campo === f.lado) d.className = 'domina';
    ficha.appendChild(d);
  });
  ficha.hidden = false;
  const g = ficha.parentElement.getBoundingClientRect();
  const w = ficha.offsetWidth;
  const h = ficha.offsetHeight;
  let x = pos.x + 16;
  if (x + w > g.width) x = Math.max(0, pos.x - 16 - w);
  ficha.style.left = x + 'px';
  ficha.style.top = Math.max(0, Math.min(g.height - h, pos.y + 16)) + 'px';
}

/* ------------------------------------------------------------------ el mando de intensidad y la leyenda
 * Dos asas en percentiles (los cortes de lo visible); se recuerdan en localStorage si el navegador deja. */
const INTENSIDAD_CLAVE = 'libro.intensidad';

function montaIntensidad() {
  const a = document.getElementById('int-bajo');
  const b = document.getElementById('int-alto');
  if (!a || !b) return;
  try {
    const x = JSON.parse(window.localStorage.getItem(INTENSIDAD_CLAVE) || 'null');
    if (Array.isArray(x) && x.length === 2 && x[0] >= 0 && x[1] <= 100 && x[0] < x[1]) [a.value, b.value] = x;
  } catch (e) {
    // sin localStorage (o con basura): los de omision
  }
  const mueve = (ev) => {
    let lo = Number(a.value);
    let hi = Number(b.value);
    if (lo >= hi) {
      if (ev && ev.target === a) lo = hi - 1;
      else hi = lo + 1;
      a.value = lo;
      b.value = hi;
    }
    try {
      window.localStorage.setItem(INTENSIDAD_CLAVE, JSON.stringify([lo, hi]));
    } catch (e) {
      // no se recuerda: no pasa nada
    }
    EL_MAPA.percentiles([lo, hi]);
  };
  a.addEventListener('input', mueve);
  b.addEventListener('input', mueve);
  if (Number(a.value) !== MAPA_PERCENTILES[0] || Number(b.value) !== MAPA_PERCENTILES[1]) mueve();
}

/* ------------------------------------------------------------------ (149 rC) los gestos que tienen DOM
 * H-08/I-07: el menu del eje de precio (clic derecho) con el modo de recentrado, recordado como la intensidad; Esc o un
 * clic fuera lo cierran. I-05: «PRESENTE» enciende seguir el presente (encendido: apagado el boton; parado: en acento). */
const RECENTRA_CLAVE = 'libro.recentrado';

function cierraMenuEje() {
  document.getElementById('menu-eje').hidden = true;
}

function montaGestos() {
  const menu = document.getElementById('menu-eje');
  const cv = document.getElementById('mapa');
  let modo = 'ultimo';
  try {
    const x = window.localStorage.getItem(RECENTRA_CLAVE);
    if (RECENTRA[x]) modo = x;
  } catch (e) {
    // sin localStorage: el de omision
  }
  EL_MAPA.recentra(modo, false);
  const marca = (m) => menu.querySelectorAll('input[name=recentra]').forEach((r) => { r.checked = r.value === m; });
  marca(modo);
  menu.querySelectorAll('input[name=recentra]').forEach((r) => r.addEventListener('change', () => {
    try {
      window.localStorage.setItem(RECENTRA_CLAVE, r.value);
    } catch (e) {
      // no se recuerda: no pasa nada
    }
    EL_MAPA.recentra(r.value, true);
    marca(r.value);
    cierraMenuEje();
  }));
  cv.addEventListener('contextmenu', (ev) => {
    const b = cv.getBoundingClientRect();
    if (EL_MAPA.zonaDe(ev.clientX - b.left, ev.clientY - b.top) !== 'precio') return;
    ev.preventDefault();
    marca(EL_MAPA.estado().vertical.recentra);
    menu.hidden = false;
    menu.style.left = Math.max(0, Math.min(ev.clientX, window.innerWidth - menu.offsetWidth - 8)) + 'px';
    menu.style.top = Math.max(0, Math.min(ev.clientY, window.innerHeight - menu.offsetHeight - 8)) + 'px';
  });
  document.addEventListener('mousedown', (ev) => {
    if (!menu.hidden && !ev.target.closest('#menu-eje')) cierraMenuEje();
  });
  // la ayuda (la pantalla no es un manual): «?» la abre y la cierra, Esc la cierra (el dialogo modal lo hace solo)
  const ayuda = document.getElementById('ayuda');
  const alterna = () => (ayuda.open ? ayuda.close() : ayuda.showModal());
  document.getElementById('b-ayuda').addEventListener('click', alterna);
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') cierraMenuEje();
    if (ev.key !== '?' || ev.ctrlKey || ev.altKey || ev.metaKey) return;
    const t = ev.target && ev.target.tagName;
    if (t === 'INPUT' || t === 'SELECT' || t === 'TEXTAREA') return;
    ev.preventDefault();
    cierraMenuEje();
    alterna();
  });
  document.getElementById('b-presente').addEventListener('click', () => EL_MAPA.presente());
}

function pintaVista(v) {
  const b = document.getElementById('b-presente');
  if (b) b.classList.toggle('parado', !v.sigue);
}

/* La leyenda: los dos degradados con sus cortes en la unidad de la vista, el desconocido y el «sin datos». */
function pintaLeyenda(esc, m) {
  const cv = document.getElementById('mapa-leyenda');
  const tx = document.getElementById('mapa-cortes');
  if (!cv || !tx) return;
  const g = cv.getContext('2d');
  const w = cv.width - 40;
  [[MAPA_LUT_COMPRA, 0], [MAPA_LUT_VENTA, 7]].forEach(([lut, y]) => {
    for (let x = 0; x < w; x++) {
      const c = lut[Math.floor((255 * x) / (w - 1))];
      g.fillStyle = 'rgb(' + c.join(',') + ')';
      g.fillRect(x, y, 1, 6);
    }
  });
  g.fillStyle = 'rgb(' + MAPA_COLOR.desconocido.join(',') + ')';
  g.fillRect(w + 4, 0, 14, 13);
  for (let x = 0; x < 14; x++) {
    for (let y = 0; y < 13; y++) {
      g.fillStyle = 'rgb(' + colorHueco(x, y).join(',') + ')';
      g.fillRect(w + 22 + x, y, 1, 1);
    }
  }
  const u = m.unidad === 'usd' ? ' USD' : ' ' + m.activo;
  tx.textContent = esc.corte[0] === null ? 'sin cantidades a la vista'
    : 'p' + esc.percentiles[0] + ' ' + cifra(esc.corte[0]) + u + ' → p' + esc.percentiles[1] + ' ' + cifra(esc.corte[1])
      + u + ' (de ' + esc.n + ' celdas a la vista) · gris: desconocido · rayado: sin datos · un nivel que conocen menos'
      + ' venues que la familia no se atenúa (lo dice «n de N» al leerlo): en perp solo okx_swap y bitget guardan la'
      + ' capa honda, así que n de N mide lo que guardamos, no la liquidez del mercado';
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
  EL_MAPA = creaMapa(document.getElementById('mapa'), lectura, document.getElementById('encaje'), pintaLeyenda,
                     pintaVista);
  montaIntensidad();
  montaGestos();
  LA_ESCALERA = creaEscalera(document.getElementById('escalera'), { pide: pideEscalera, limpia: limpiaCinta });
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
