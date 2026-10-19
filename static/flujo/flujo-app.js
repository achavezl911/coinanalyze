'use strict';
/* EL FOOTPRINT · el estado, la capa de datos y el latido (campana 142, OF-2).
 * ---------------------------------------------------------------------------
 * EL ESTADO VIVE EN EL HASH, como en la mesa: `#<activo>/<marco>/<familia>[/<paso>][/clave=valor...]` (ver
 * flujo-calculo.js). Una vista = una URL: headless no pulsa nada, y K109 abre una ventana fija del pasado con `hasta=`.
 *
 * UNA SOLA CAPA DE DATOS: `pedir()` de static/mesa/mesa-datos.js, la de la mesa. Ninguna URL se construye en otro sitio.
 *
 * LOS CUATRO ESTADOS, y ninguno es cero:
 *   ERROR    la ruta contesto mal o no contesto: se dice con su codigo; si ya habia velas se quedan, dichas viejas
 *   RANCIO   el latido lleva mas de RANCIO_S sin una respuesta buena: lo que hay deja de llamarse vivo
 *   AUSENTE  una vela cerrada que nadie escucho (ni una fila de cobertura): se pinta HUECO, nunca como una vela
 *   NULO     una respuesta buena sin una sola celda en toda la ventana: se dice arriba
 *
 * EL LATIDO: cada VIVO_S pide SOLO las velas que todavia pueden cambiar (desde la primera ABIERTA hasta la en curso),
 * con el paso que eligio la historia. La historia se pide una vez por vista; nunca la ventana entera en cada latido.
 */

const VIVO_S = 5;
const RANCIO_S = 30;
const RUTA = '/api/orderflow/footprint';
// Lo que la pantalla DECLARA que marca, y con que regla (K109 lo compara con la suya).
const UMBRALES = { razon: '3', minimo: 'la media de volumen por nivel de su vela', apilado: 3, cierre_s: CIERRE_S };

let VISTA = leeHash(window.location.hash);
let LIENZO = null;
let MODELO = null;
let ULTIMA = null; // la ultima respuesta BUENA: { asOfMs, t }
let FALLO = null; // el ultimo intento que no trajo dato
let LATIDO = null;
let TIC = null;
let PIDIENDO = false;
let CARGA = 0;
// LO QUE SE LEE DESDE FUERA (K109, por CDP): `listo` cuando la vista pedida ya esta pintada, la vista, las peticiones,
// y `repinta()`, que vuelve a pintar AHORA (sincrono): asi FLUJO_PINTADO y lo que el lienzo escribio son del mismo fotograma.
window.FLUJO_HITOS = { listo: false, vista: null, peticiones: [], repinta: () => LIENZO && LIENZO.pinta() };

/* OF-3 (campana 143) · LAS CAPAS Y EL TPO. Cada capa es una peticion propia, servida y pintada tal cual
 * (flujo-capas.js, flujo-tpo.js), y ninguna cambia lo que el footprint pide ni pinta. Se piden cuando el footprint ya
 * esta pintado (el dinamico necesita saber que se ve) y otra vez con cada vela NUEVA del latido, nunca en cada latido:
 * el compuesto, como mucho cada REFRESCO_COMPUESTO_S (su ventana es de dias). `capas` dice a K109 cuando han llegado
 * todas; en el modo TPO, `repinta()` pinta el lienzo del TPO. */
const RUTA_SESIONES = '/api/orderflow/sesiones';
const RUTA_VWAP = '/api/orderflow/vwap';
const RUTA_PERFIL = '/api/orderflow/perfil';
const RUTA_TPO = '/api/orderflow/tpo';
const TPO_VIVO_S = 30;
const REFRESCO_COMPUESTO_S = 300;
let LIENZO_TPO = null;
let MODELO_TPO = null;
let FALLO_TPO = null;
let LATIDO_TPO = null;
let CAPAS_FALLOS = [];
let PENDIENTES = 0;
const SEQ = {};
const VISIBLE = { vista: null, pedida: null };
let COMPUESTO_MS = 0;
Object.assign(window.FLUJO_HITOS, {
  capas: false,
  repinta: () => (VISTA.modo === 'tpo' ? LIENZO_TPO && LIENZO_TPO.pinta() : LIENZO && LIENZO.pinta()),
});

/* OF-5a (campana 146) · LOS INDICADORES Y LA CINTA (flujo-indicadores.js, flujo-cinta.js). Se piden cuando el footprint
 * ya esta pintado y, en vivo, otra vez con cada vela NUEVA (las series de 5 min y las grandes de la ventana del
 * footprint); la cinta lleva su propio latido, que pide solo lo nuevo. `indicadores` dice a K112 cuando han llegado;
 * `aplicadas`, que respuestas del footprint aplico la pantalla, en orden; y `congela()` para todos los latidos y deja
 * sin efecto lo que estuviera en vuelo (como una vista nueva: CARGA + 1), para que lo pintado y lo recibido sean lo
 * mismo cuando K112 los compara. */
Object.assign(window.FLUJO_HITOS, {
  indicadores: false,
  aplicadas: [],
  congela: () => {
    CARGA += 1;
    IND.pide += 1;
    CINTA.pide += 1;
    pararLatido();
  },
});

function apunta(sobre) {
  if (sobre.ok) window.FLUJO_HITOS.aplicadas.push({ ruta: sobre.ruta, as_of: sobre.datos.as_of });
}

/* La ventana de los indicadores es la del footprint que se pinta: de su primera vela al final de la ultima. */
async function cargaVistaIndicadores(mia) {
  if (!MODELO || mia !== CARGA) return;
  window.FLUJO_HITOS.indicadores = false;
  const m = FLUJO_MARCOS[VISTA.marco] * 60000;
  const w = { desde: MODELO.velas[0].ts, hasta: isoZ(Date.parse(MODELO.velas[MODELO.velas.length - 1].ts) + m) };
  await cargaIndicadores(VISTA, w, (s) => {
    apuntar(s);
    apunta(s); // solo llega aqui lo que se aplica (la ultima peticion de cada vista)
  });
  if (mia !== CARGA) return;
  LIENZO.pide();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (mia === CARGA) window.FLUJO_HITOS.indicadores = true;
  }));
}

function cargaVistaCinta() {
  cargaCinta(VISTA, apuntar);
}

/* OF-6a (campana 148) · F-10, EL CVD DE SESION: si la sesion de la primera vela empezo antes que ella, su delta hasta
 * ahi, de /api/orderflow/sesiones cortada en la primera vela y con un paso de PASO_ARRANQUE veces el base (una fila o
 * dos: solo hace falta el delta). Sin la fila del CVD encendida no se pide. `arranques` dice a K113 cuando esta. */
const PASO_ARRANQUE = 100000;
window.FLUJO_HITOS.of6a = true;
window.FLUJO_HITOS.arranques = false;

async function cargaArranques(mia) {
  window.FLUJO_HITOS.arranques = false;
  if (!MODELO || mia !== CARGA) return;
  MODELO.arranques = {};
  const v0 = MODELO.velas[0];
  const ses = leeSesion(VISTA.sesion);
  const ini = v0 && ses ? sesionDe(v0.ts, ses) : null;
  if (!VISTA.filas.includes('cvd') || ini === null || ini >= Date.parse(v0.ts)) {
    LIENZO.pide();
    window.FLUJO_HITOS.arranques = true;
    return;
  }
  const t0 = Date.parse(v0.ts);
  const sobre = await pedir(RUTA_SESIONES, {
    symbol: VISTA.activo, desde: isoZ(t0 - 60000), hasta: isoZ(t0), sesion: VISTA.sesion,
    paso: String(Number((Number(MODELO.paso_base) * PASO_ARRANQUE).toPrecision(12))),
    venues: FAMILIAS[VISTA.familia].venues.join(','), unidad: VISTA.unidad });
  apuntar(sobre);
  if (mia !== CARGA || !MODELO) return;
  const s = sobre.ok ? (sobre.datos.sesiones || []).find((x) => Date.parse(x.inicio) === ini) : null;
  MODELO.arranques[ini] = s ? { delta: s.delta, estado: estadoSesion(s).estado, corte: s.corte }
    : { delta: null, estado: sobre.ok ? 'hueco' : 'error', http: sobre.http };
  LIENZO.pide();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (mia === CARGA) window.FLUJO_HITOS.arranques = true;
  }));
}

/* Lo que el raton o el teclado dejaron en los dos ejes va al hash (sin pedir nada ni volver a cargar). */
function vistaCambiada(est) {
  Object.assign(VISTA, est);
  const h = escribeHash(VISTA);
  if (window.location.hash !== h) window.history.replaceState(null, '', h);
  window.FLUJO_HITOS.vista = h;
  pintaSelectores();
}

/* I-07: el menu del eje de precio, junto al clic; Esc o un clic fuera lo cierran (y los menus de la barra). */
function abreMenu(x, y) {
  const m = document.getElementById('menu-eje');
  pintaSelectores();
  m.hidden = false;
  m.style.left = Math.max(0, Math.min(x, window.innerWidth - m.offsetWidth - 8)) + 'px';
  m.style.top = Math.max(0, Math.min(y, window.innerHeight - m.offsetHeight - 8)) + 'px';
}

function cierraMenus(salvo) {
  document.getElementById('menu-eje').hidden = true;
  document.querySelectorAll('details.menu[open]').forEach((d) => {
    if (d !== salvo) d.open = false;
  });
}

/* I-06: el teclado. Las flechas, una vela; Re Pag / Av Pag, una pantalla; Inicio, lo primero cargado; Fin, la ultima
 * vela (y seguirla); Esc cierra menus, la ayuda y la regla. Con el foco en un mando, el teclado es suyo. */
function teclado(ev) {
  if (ev.key === 'Escape') {
    cierraMenus();
    LIENZO.borraRegla();
    return;
  }
  if (VISTA.modo === 'tpo' || ev.ctrlKey || ev.altKey || ev.metaKey) return;
  if (ev.target && ev.target.closest && ev.target.closest('input, select, textarea, dialog')) return;
  const accion = { ArrowLeft: () => LIENZO.mueve(-1), ArrowRight: () => LIENZO.mueve(1),
                   PageUp: () => LIENZO.pagina(-1), PageDown: () => LIENZO.pagina(1),
                   Home: () => LIENZO.inicio(), End: () => LIENZO.presente() }[ev.key];
  if (!accion) return;
  ev.preventDefault();
  accion();
}

/* E-05: la cruz sigue al raton tambien sobre los paneles (su vertical es la de la vela; su valor, el del panel). */
function cruzDeLosPaneles() {
  const ind = document.getElementById('lienzo-ind');
  ind.addEventListener('mousemove', (ev) => {
    const r = document.getElementById('lienzo').getBoundingClientRect();
    const g = LIENZO.geo();
    const x = ev.clientX - r.left;
    LIENZO.cruzEn({ x, y: ev.clientY - r.top, zona: x >= g.ancho ? 'precio' : 'grafico', sobre: 'panel',
                    panelY: ev.clientY - ind.getBoundingClientRect().top });
  });
  ind.addEventListener('mouseleave', () => LIENZO.cruzEn(null));
}

function reloj() {
  return (window.performance || Date).now();
}

function ahora() {
  return ULTIMA ? ULTIMA.asOfMs + (reloj() - ULTIMA.t) : Date.now();
}

function apuntar(sobre) {
  window.FLUJO_HITOS.peticiones.push({ ruta: sobre.ruta, ms: Math.round(sobre.ms), http: sobre.http, ok: sobre.ok });
}

function parametros(e, desde, hasta, paso) {
  return { symbol: e.activo, marco: e.marco, desde, hasta, paso, venues: FAMILIAS[e.familia].venues.join(','),
           unidad: e.unidad };
}

/* Una vela servida, con lo que la pantalla le calcula: su estado contra el reloj y sus desequilibrios. */
function prepara(v, paso, asOfMs) {
  return Object.assign({}, v, estadoVela(v, asOfMs, VISTA.marco), { des: desequilibrios(v.niveles, paso) });
}

function modelo(d) {
  const asOfMs = Date.parse(d.as_of);
  return {
    activo: d.symbol, marco: d.marco, familia: VISTA.familia, venues: d.venues, paso: d.paso, paso_base: d.paso_base,
    paso_auto: d.paso_auto || null, unidad: d.unidad, umbrales: UMBRALES,
    filtro: { min: VISTA.min, esconde: VISTA.esconde, grande: VISTA.grande },
    velas: d.velas.map((v) => prepara(v, d.paso, asOfMs)),
  };
}

/* ------------------------------------------------------------------ pedir */
async function carga() {
  const mia = ++CARGA;
  pararLatido();
  MODELO = null;
  ULTIMA = null;
  FALLO = null;
  window.FLUJO_HITOS.listo = false;
  // OF-3: el footprint a la vista y el TPO no; las capas de la vista anterior, fuera
  window.FLUJO_HITOS.capas = false;
  document.getElementById('grafico').hidden = false;
  document.getElementById('grafico-tpo').hidden = true;
  MODELO_TPO = null;
  FALLO_TPO = null;
  CAPAS_FALLOS = [];
  VISIBLE.vista = VISIBLE.pedida = null;
  window.FLUJO_HITOS.vista = escribeHash(VISTA);
  pintaSelectores();
  midePaneles(VISTA); // OF-5a: el alto de los paneles lo fija la VISTA, no el dato
  pintaEstado('pidiendo la historia…');
  const w = ventana(VISTA, Date.now());
  const sobre = await pedir(RUTA, parametros(VISTA, w.desde, w.hasta, VISTA.paso));
  apuntar(sobre);
  if (mia !== CARGA) return;
  apunta(sobre); // OF-5a: lo que la pantalla APLICA (K112 lo compara con lo que llego)
  if (!sobre.ok) {
    FALLO = sobre;
    LIENZO.pon({ velas: [] }, VISTA);
  } else {
    ULTIMA = { asOfMs: Date.parse(sobre.datos.as_of), t: reloj() };
    MODELO = modelo(sobre.datos);
    LIENZO.pon(MODELO, VISTA);
    if (!VISTA.hasta) arrancaLatido();
    cargaArranques(mia); // OF-6a: el CVD de sesion de la primera vela
  }
  pintaSelectores();
  pintaEstado();
  // listo cuando el lienzo ya pinto ESTA vista (dos fotogramas: el que la pide y el que la dibuja)
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (mia === CARGA) window.FLUJO_HITOS.listo = true;
  }));
  // OF-3: las capas, cuando el footprint ya esta pintado
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (mia === CARGA && MODELO) cargaCapas();
    else if (mia === CARGA) window.FLUJO_HITOS.capas = true;
  }));
  // OF-5a: los indicadores de la ventana del footprint y la cinta
  if (MODELO) cargaVistaIndicadores(mia);
  else window.FLUJO_HITOS.indicadores = true;
  cargaVistaCinta();
}

async function late() {
  if (!MODELO || PIDIENDO || document.hidden) return;
  PIDIENDO = true;
  const mia = CARGA;
  const viva = ventanaViva(VISTA.marco, ahora());
  const abierta = MODELO.velas.find((v) => v.estado === 'abierta');
  const desde = abierta && Date.parse(abierta.ts) < Date.parse(viva.desde) ? isoZ(Date.parse(abierta.ts)) : viva.desde;
  // si la pestana estuvo dormida mas que la historia entera, se vuelve a pedir la vista
  if ((Date.parse(viva.hasta) - Date.parse(desde)) / 60000 / FLUJO_MARCOS[VISTA.marco] > FLUJO_HISTORIA[VISTA.marco]) {
    PIDIENDO = false;
    carga();
    return;
  }
  const sobre = await pedir(RUTA, parametros(VISTA, desde, viva.hasta, MODELO.paso));
  PIDIENDO = false;
  apuntar(sobre);
  if (mia !== CARGA) return;
  if (!sobre.ok) {
    FALLO = sobre;
    pintaEstado();
    return;
  }
  FALLO = null;
  apunta(sobre);
  ULTIMA = { asOfMs: Date.parse(sobre.datos.as_of), t: reloj() };
  const porTs = new Map(MODELO.velas.map((v, i) => [Date.parse(v.ts), i]));
  const antes = MODELO.velas.length; // OF-3: con una vela NUEVA, las capas vivas se vuelven a pedir
  sobre.datos.velas.forEach((v) => {
    const nueva = prepara(v, MODELO.paso, ULTIMA.asOfMs);
    const t = Date.parse(v.ts);
    if (porTs.has(t)) MODELO.velas[porTs.get(t)] = nueva;
    else if (t > Date.parse(MODELO.velas[MODELO.velas.length - 1].ts)) MODELO.velas.push(nueva);
  });
  MODELO.velas.forEach((v, i) => {
    if (v.estado === 'abierta') MODELO.velas[i] = Object.assign(v, estadoVela(v, ULTIMA.asOfMs, VISTA.marco));
  });
  LIENZO.actualiza();
  pintaEstado();
  if (MODELO.velas.length > antes) refrescaCapas();
  if (MODELO.velas.length > antes) cargaVistaIndicadores(mia); // OF-5a
}

function arrancaLatido() {
  pararLatido();
  LATIDO = setInterval(late, VIVO_S * 1000);
  TIC = setInterval(pintaEstado, 1000);
}

function pararLatido() {
  if (LATIDO !== null) clearInterval(LATIDO);
  if (TIC !== null) clearInterval(TIC);
  LATIDO = TIC = null;
  if (LATIDO_TPO !== null) clearInterval(LATIDO_TPO);
  LATIDO_TPO = null;
  paraCinta(); // OF-5a
}

/* ------------------------------------------------------------------ decir
 * OF-6a (campana 148): UNA linea, corta. Lo que importa de cada vela (incompleta, hueco, en curso) lo dice la vela y
 * la ficha; la fuente de cada panel, su cabecera; lo largo (los venues, la regla del paso, las capas), el `title`. */
function pintaEstado(pidiendo) {
  const caja = vaciar(document.getElementById('estado'));
  const grafico = document.getElementById('grafico');
  if (pidiendo) {
    caja.appendChild(el('span', 'cargando', pidiendo));
    return;
  }
  const p = el('p', 'estado-linea');
  caja.appendChild(p);
  const pon = (t) => p.appendChild(typeof t === 'string' ? document.createTextNode(t) : t);
  const titulo = [];
  let rancio = false;
  const marca = (n, clase, texto) => {
    const s = noSe(clase, texto);
    s.setAttribute('data-estado', clase);
    pon(s);
    pon(' ');
    return n;
  };
  if (FALLO) marca(0, 'error', 'HTTP ' + FALLO.http + ' · ' + (FALLO.motivo || '') + (MODELO ? ' · se enseña lo último que llegó' : ''));
  CAPAS_FALLOS.forEach(([nombre, s]) => marca(0, 'error', 'capa ' + nombre + ': HTTP ' + s.http + ' · ' + (s.motivo || '')));
  if (MODELO && !VISTA.hasta && ULTIMA) {
    const edadS = (reloj() - ULTIMA.t) / 1000;
    rancio = edadS > RANCIO_S;
    if (rancio) {
      marca(0, 'rancio', 'la última respuesta buena es de hace ' + Math.round(edadS) + ' s (el latido pide cada '
        + VIVO_S + ' s)');
    }
  }
  if (MODELO && !MODELO.velas.some((v) => v.niveles.length)) {
    marca(0, 'nulo', 'la ruta contestó sin una sola celda en toda la ventana: no hay operaciones que pintar');
  }
  if (VISTA.modo === 'tpo') {
    estadoTPO(pon, titulo);
  } else if (MODELO) {
    const huecos = MODELO.velas.filter((v) => v.estado === 'hueco').length;
    const inc = MODELO.velas.filter((v) => v.estado === 'incompleta').length;
    const fam = FAMILIAS[VISTA.familia];
    pon(el('b', null, VISTA.activo + ' · ' + VISTA.marco + ' · ' + fam.rotulo));
    pon(' · paso ' + MODELO.paso + (MODELO.paso_auto ? ' auto' : ' fijado') + ' · '
      + (MODELO.unidad === 'usd' ? 'USD' : VISTA.activo) + ' · '
      + (VISTA.hasta ? 'hasta ' + VISTA.hasta.slice(5, 16).replace('T', ' ') + 'Z' : rancio ? 'RANCIO' : 'vivo')
      + ' · ' + MODELO.velas.length + ' velas'
      + (inc ? ' · ' + inc + ' incompleta' + (inc > 1 ? 's' : '') : '')
      + (huecos ? ' · ' + huecos + ' hueco' + (huecos > 1 ? 's' : '') + ' sin dato' : ''));
    titulo.push('venues: ' + MODELO.venues.join(', '));
    if (MODELO.paso_auto) titulo.push('paso automático: la vela mediana toca ' + MODELO.paso_auto.niveles_vela_mediana
      + ' niveles · ' + MODELO.paso_auto.regla);
    if (!VISTA.hasta) titulo.push('vivo: la vela en curso se pide cada ' + VIVO_S + ' s');
    if (VISTA.capas.length || VISTA.compuesto || VISTA.fijo) {
      pon(' · capas');
      titulo.push(textoCapas());
    }
  }
  caja.title = titulo.join('\n');
  grafico.classList.toggle('rancio', rancio || (!!FALLO && !!MODELO));
}

function rotuloSesion() {
  const s = leeSesion(VISTA.sesion);
  return (s.rotulo === 'propia' ? 'propia' : s.rotulo) + ' ' + s.inicio + '–' + s.fin + 'Z'
    + (s.cruza ? ' (cruza la medianoche: es una sola)' : '');
}

function textoCapas() {
  const partes = [];
  if (VISTA.capas.includes('perfil')) partes.push('perfil de cada sesión');
  if (VISTA.compuesto) partes.push('compuesto de ' + VISTA.compuesto + ' sesiones (se rehace cada ' + REFRESCO_COMPUESTO_S / 60 + ' min)');
  if (VISTA.capas.includes('vwap')) partes.push('VWAP de la sesión ±1·2·3σ');
  if (VISTA.capas.includes('dinamico')) partes.push('dinámico (lo visible)');
  if (VISTA.fijo) partes.push('fijo ' + VISTA.fijo[0].slice(5, 16).replace('T', ' ') + '–' + VISTA.fijo[1].slice(5, 16).replace('T', ' ') + 'Z');
  const w = ventanaCapas(ventana(VISTA, ahora()), leeSesion(VISTA.sesion), VISTA.marco);
  return 'capas · sesión ' + rotuloSesion() + ' · ' + partes.join(' · ')
    + (w.recortada && (VISTA.capas.includes('perfil') || VISTA.capas.includes('vwap'))
      ? ' · perfil y VWAP solo de las ' + SESIONES_MAXIMO + ' últimas sesiones (desde ' + w.desde.slice(5, 16).replace('T', ' ')
        + 'Z: el tope de la ruta)' : '');
}

function estadoTPO(pon, titulo) {
  if (FALLO_TPO) {
    const n = noSe('error', 'HTTP ' + FALLO_TPO.http + ' · ' + (FALLO_TPO.motivo || ''));
    n.setAttribute('data-estado', 'error');
    pon(n);
    pon(' ');
  }
  if (!MODELO_TPO) return;
  const p = MODELO_TPO.paso_auto;
  pon(el('b', null, VISTA.activo + ' · TPO · ' + FAMILIAS[VISTA.familia].rotulo));
  pon(' · sesión ' + rotuloSesion() + ' · paso ' + MODELO_TPO.paso + (p ? ' auto' : '') + ' · '
    + MODELO_TPO.sesiones.length + ' sesión(es) · '
    + (VISTA.hasta ? 'hasta ' + VISTA.hasta.slice(5, 16).replace('T', ' ') + 'Z' : 'vivo'));
  titulo.push('venues: ' + MODELO_TPO.venues.join(', '));
  if (p) titulo.push('paso automático: el periodo de 30 min mediano toca ' + p.niveles_periodo_mediano + ' niveles');
  titulo.push('una letra por media hora (A = la primera de la sesión)'
    + (VISTA.hasta ? '' : ' · vivo: se pide cada ' + TPO_VIVO_S + ' s'));
}

/* F-16: lo que dice la ficha junto al cursor, en una linea para el lector de pantalla (#lectura, aria-live). */
function lectura(texto) {
  document.getElementById('lectura').textContent = texto || '';
}

/* ------------------------------------------------------------- los mandos */
function pintaSelectores() {
  [['sel-activo', 'activo'], ['sel-marco', 'marco'], ['sel-familia', 'familia'], ['sel-unidad', 'unidad'],
    ['sel-celda', 'celda']]
    .forEach(([id, k]) => {
      document.querySelectorAll('#' + id + ' button').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.valor === VISTA[k]));
      });
    });
  // OF-6a: el color, su referencia, los numeros, las filas de resumen, la rueda y si se sigue la ultima vela
  document.querySelectorAll('#m-color input[name=color]').forEach((r) => { r.checked = r.value === VISTA.color; });
  document.querySelectorAll('#m-color input[name=ref]').forEach((r) => { r.checked = r.value === VISTA.ref; });
  document.getElementById('sel-numeros').checked = VISTA.numeros !== false;
  document.querySelectorAll('#menu-eje input[data-fila]').forEach((c) => { c.checked = VISTA.filas.includes(c.dataset.fila); });
  document.querySelectorAll('#menu-eje input[name=rueda]').forEach((r) => { r.checked = r.value === VISTA.rueda; });
  document.querySelectorAll('#menu-escala button').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.valor === (VISTA.y ? 'manual' : 'auto')));
  });
  document.getElementById('b-presente').classList.toggle('parado', VISTA.x !== null && VISTA.x !== undefined);
  const sel = document.getElementById('sel-paso');
  vaciar(sel);
  const base = MODELO ? MODELO.paso_base : null;
  const opciones = ['auto'];
  if (base) {
    for (let e = 0; e < 5; e++) [1, 2, 5].forEach((m) => opciones.push(String(Number((Number(base) * m * Math.pow(10, e)).toPrecision(12)))));
  }
  if (VISTA.paso !== 'auto' && !opciones.includes(VISTA.paso)) opciones.push(VISTA.paso);
  opciones.forEach((o) => {
    const op = el('option', null, o === 'auto' ? 'auto' : o);
    op.value = o;
    op.selected = o === VISTA.paso;
    sel.appendChild(op);
  });
  document.getElementById('sel-min').value = VISTA.min || '';
  document.getElementById('sel-esconde').checked = VISTA.esconde;
  document.getElementById('sel-grande').value = VISTA.grande || '';
  document.getElementById('ir-mesa').setAttribute('href', '/#scalp/' + VISTA.activo);
  // OF-3: el gestor de sesiones, las capas y el modo
  const ses = leeSesion(VISTA.sesion);
  const propia = !tiene(SESIONES, VISTA.sesion);
  document.getElementById('sel-sesion').value = propia ? 'propia' : VISTA.sesion;
  document.getElementById('sesion-propia').hidden = !propia;
  document.getElementById('ses-ini').value = ses.inicio;
  document.getElementById('ses-fin').value = ses.fin === '24:00' ? '00:00' : ses.fin;
  [['capa-perfil', 'perfil'], ['capa-vwap', 'vwap'], ['capa-dinamico', 'dinamico']].forEach(([id, c]) => {
    document.getElementById(id).checked = VISTA.capas.includes(c);
  });
  document.getElementById('capa-compuesto').checked = !!VISTA.compuesto;
  document.getElementById('sel-compuesto').value = VISTA.compuesto || COMPUESTO_DEFECTO;
  document.getElementById('capa-fijo').checked = !!VISTA.fijo;
  document.getElementById('fijo-rango').textContent = VISTA.fijo
    ? VISTA.fijo[0].slice(5, 16).replace('T', ' ') + '–' + VISTA.fijo[1].slice(5, 16).replace('T', ' ') + 'Z'
    : '(mayús + arrastre sobre el gráfico)';
  document.querySelectorAll('#sel-modo button').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.valor === VISTA.modo));
  });
  document.getElementById('sel-sesiones').value = VISTA.sesiones;
  pintaMandosIndicadores(); // OF-5a
}

/* ------------------------------------------------------------------ OF-3 · las capas */
/* Lo que se ve: de la primera vela visible al final de la ultima, segun lo que el lienzo acaba de pintar. */
function rangoVisible() {
  const reg = window.FLUJO_PINTADO;
  if (!MODELO || !reg || !reg.velas || !reg.velas.length || reg.activo !== MODELO.activo || reg.marco !== MODELO.marco) {
    return null;
  }
  const m = FLUJO_MARCOS[MODELO.marco] * 60000;
  return { desde: isoZ(Date.parse(reg.velas[0].ts)), hasta: isoZ(Date.parse(reg.velas[reg.velas.length - 1].ts) + m) };
}

/* [nombre, ruta, parametros] de cada capa que la vista pide: las sesiones de la ventana del footprint, el compuesto de
 * las N ultimas, el VWAP de la ventana, el fijo de su rango y el dinamico de lo visible. Paso y unidad, los del
 * footprint: las filas de las capas son las suyas. */
function peticionesCapas() {
  const e = VISTA;
  const w = ventanaCapas(ventana(e, ahora()), leeSesion(e.sesion), e.marco);
  const base = { symbol: e.activo, venues: FAMILIAS[e.familia].venues.join(',') };
  const perfil = Object.assign({ paso: MODELO.paso, unidad: e.unidad }, base);
  const out = [];
  if (e.capas.includes('perfil')) out.push(['sesiones', RUTA_SESIONES, Object.assign({ desde: w.desde, hasta: w.hasta, sesion: e.sesion }, perfil)]);
  if (e.compuesto) {
    const wc = ventanaSesiones(Date.parse(w.hasta), leeSesion(e.sesion), e.compuesto);
    out.push(['compuesto', RUTA_SESIONES, Object.assign({ desde: wc.desde, hasta: wc.hasta, sesion: e.sesion }, perfil)]);
  }
  if (e.capas.includes('vwap')) out.push(['vwap', RUTA_VWAP, Object.assign({ desde: w.desde, hasta: w.hasta, marco: e.marco, sesion: e.sesion }, base)]);
  if (e.fijo) out.push(['fijo', RUTA_PERFIL, Object.assign({ desde: e.fijo[0], hasta: e.fijo[1] }, perfil)]);
  const vis = e.capas.includes('dinamico') ? rangoVisible() : null;
  if (vis) out.push(['dinamico', RUTA_PERFIL, Object.assign({}, vis, perfil)]);
  return out;
}

/* Pide las capas (todas, o solo las nombradas) y las deja en el modelo; la ultima peticion de cada capa manda. */
async function cargaCapas(nombres) {
  if (!MODELO || VISTA.modo === 'tpo') return;
  const carga = CARGA;
  const todas = peticionesCapas();
  const vivas = new Set(todas.map(([n]) => n));
  MODELO.capas = Object.fromEntries(Object.entries(MODELO.capas || {}).filter(([n]) => vivas.has(n)));
  CAPAS_FALLOS = CAPAS_FALLOS.filter(([n]) => vivas.has(n));
  const pide = nombres ? todas.filter(([n]) => nombres.includes(n)) : todas;
  if (pide.some(([n]) => n === 'compuesto')) COMPUESTO_MS = Date.now();
  const din = pide.find(([n]) => n === 'dinamico');
  if (din) VISIBLE.pedida = VISIBLE.vista = din[2].desde + '/' + din[2].hasta;
  window.FLUJO_HITOS.capas = false;
  PENDIENTES += pide.length;
  await Promise.all(pide.map(async ([nombre, ruta, q]) => {
    SEQ[nombre] = (SEQ[nombre] || 0) + 1;
    const n = SEQ[nombre];
    const sobre = await pedir(ruta, q);
    PENDIENTES -= 1;
    apuntar(sobre);
    if (carga !== CARGA || !MODELO || n !== SEQ[nombre]) return;
    if (!peticionesCapas().some(([x]) => x === nombre)) return;
    CAPAS_FALLOS = CAPAS_FALLOS.filter(([x]) => x !== nombre);
    if (!sobre.ok) {
      delete MODELO.capas[nombre];
      CAPAS_FALLOS.push([nombre, sobre]);
      return;
    }
    const capa = { datos: sobre.datos, asOfMs: Date.parse(sobre.datos.as_of) };
    if (nombre === 'dinamico' || nombre === 'fijo') {
      capa.estado = estadoRango(Date.parse(sobre.datos.desde), Date.parse(sobre.datos.hasta), sobre.datos.cobertura,
                                capa.asOfMs);
    }
    MODELO.capas[nombre] = capa;
  }));
  if (carga !== CARGA || !MODELO) return;
  LIENZO.pide();
  pintaEstado();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (!PENDIENTES && carga === CARGA) window.FLUJO_HITOS.capas = true;
  }));
}

/* Una vela NUEVA: las capas que llegan al presente se vuelven a pedir (el compuesto, como mucho cada 5 min). */
function refrescaCapas() {
  const vivas = ['sesiones', 'vwap', 'dinamico'];
  if (VISTA.fijo && Date.parse(VISTA.fijo[1]) > ahora() - CIERRE_S * 1000) vivas.push('fijo');
  if (Date.now() - COMPUESTO_MS >= REFRESCO_COMPUESTO_S * 1000) vivas.push('compuesto');
  cargaCapas(vivas);
}

/* El dinamico sigue a lo que se ve: cuando lo visible cambia y se queda quieto un tic, se pide otra vez. */
function vigilaVisible() {
  if (!MODELO || VISTA.modo === 'tpo' || !VISTA.capas.includes('dinamico')) return;
  const r = rangoVisible();
  if (!r) return;
  const clave = r.desde + '/' + r.hasta;
  if (clave === VISIBLE.pedida) return;
  if (clave !== VISIBLE.vista) {
    VISIBLE.vista = clave;
    return;
  }
  cargaCapas(['dinamico']);
}

/* El fijo se elige con MAYUS + arrastre sobre el grafico: de la vela donde empieza a la vela donde acaba. */
function seleccionFija() {
  const g = document.getElementById('grafico');
  let ini = null;
  const vela = (x) => {
    const reg = window.FLUJO_PINTADO;
    if (!reg || !reg.velas || !reg.velas.length) return null;
    const xx = x - g.querySelector('canvas').getBoundingClientRect().left;
    let mejor = null;
    reg.velas.forEach((v) => {
      const d = Math.abs(v.x0 + v.ancho / 2 - xx);
      if (!mejor || d < mejor.d) mejor = { d, t: Date.parse(v.ts) };
    });
    return mejor.t;
  };
  g.addEventListener('mousedown', (ev) => {
    if (!ev.shiftKey) return;
    ev.stopPropagation();
    ini = vela(ev.clientX);
  }, true);
  window.addEventListener('mouseup', (ev) => {
    if (ini === null) return;
    const fin = vela(ev.clientX);
    const m = FLUJO_MARCOS[VISTA.marco] * 60000;
    if (fin !== null) cambia({ fijo: [isoZ(Math.min(ini, fin)), isoZ(Math.max(ini, fin) + m)] });
    ini = null;
  });
}

/* ------------------------------------------------------------------ OF-3 · el modo TPO */
function peticionTPO() {
  const hasta = VISTA.hasta ? Date.parse(VISTA.hasta) : (Math.floor(ahora() / 60000) + 1) * 60000;
  return Object.assign(ventanaSesiones(hasta, leeSesion(VISTA.sesion), VISTA.sesiones),
                       { symbol: VISTA.activo, sesion: VISTA.sesion, paso: 'auto',
                         venues: FAMILIAS[VISTA.familia].venues.join(',') });
}

function modeloTPO(d) {
  return { clave: [d.symbol, VISTA.familia, VISTA.sesion, VISTA.hasta, VISTA.sesiones].join('|'), activo: d.symbol,
           familia: VISTA.familia, venues: d.venues, paso: d.paso, sesion: d.sesion, paso_auto: d.paso_auto || null,
           letras: d.letras, sesiones: d.sesiones };
}

async function cargaTPO() {
  const mia = ++CARGA;
  pararLatido();
  MODELO = null;
  ULTIMA = null;
  FALLO = null;
  FALLO_TPO = null;
  MODELO_TPO = null;
  window.FLUJO_HITOS.listo = false;
  window.FLUJO_HITOS.capas = true;
  window.FLUJO_HITOS.arranques = true; // OF-6a: el TPO no lleva filas de resumen: no hay arranque que esperar
  window.FLUJO_HITOS.vista = escribeHash(VISTA);
  document.getElementById('grafico').hidden = true;
  document.getElementById('grafico-tpo').hidden = false;
  midePaneles(VISTA); // OF-5a: sin paneles ni cinta en el TPO
  cargaVistaCinta();
  pintaSelectores();
  pintaEstado('pidiendo el TPO…');
  const sobre = await pedir(RUTA_TPO, peticionTPO());
  apuntar(sobre);
  if (mia !== CARGA) return;
  if (!sobre.ok) {
    FALLO_TPO = sobre;
    LIENZO_TPO.pon({ clave: 'vacio', sesiones: [] });
  } else {
    ULTIMA = { asOfMs: Date.parse(sobre.datos.as_of), t: reloj() };
    MODELO_TPO = modeloTPO(sobre.datos);
    LIENZO_TPO.pon(MODELO_TPO);
    if (!VISTA.hasta) LATIDO_TPO = setInterval(lateTPO, TPO_VIVO_S * 1000);
  }
  pintaEstado();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (mia === CARGA) window.FLUJO_HITOS.listo = true;
  }));
}

async function lateTPO() {
  if (!MODELO_TPO || PIDIENDO || document.hidden) return;
  PIDIENDO = true;
  const mia = CARGA;
  const sobre = await pedir(RUTA_TPO, peticionTPO());
  PIDIENDO = false;
  apuntar(sobre);
  if (mia !== CARGA) return;
  FALLO_TPO = sobre.ok ? null : sobre;
  if (sobre.ok) {
    ULTIMA = { asOfMs: Date.parse(sobre.datos.as_of), t: reloj() };
    MODELO_TPO = modeloTPO(sobre.datos);
    LIENZO_TPO.pon(MODELO_TPO);
  }
  pintaEstado();
}

function cambia(cambios) {
  window.location.hash = escribeHash(Object.assign({}, VISTA, cambios));
}

function aplicaHash() {
  const nueva = leeHash(window.location.hash);
  const hash = escribeHash(nueva);
  if (window.location.hash !== hash) {
    // lo que no se entendio se reescribe: la URL y la pantalla no dicen cosas distintas
    window.history.replaceState(null, '', hash);
  }
  // OF-3: el MODO TPO es otra vista (cualquier cambio en el la vuelve a pedir); en el footprint, cambiar de capa o de
  // sesion pide las capas y no el footprint
  if (nueva.modo === 'tpo' || VISTA.modo === 'tpo') {
    VISTA = nueva;
    if (nueva.modo === 'tpo') cargaTPO();
    else carga();
    return;
  }
  const capasCambian = ['sesion', 'capas', 'compuesto', 'fijo'].some((k) => String(nueva[k]) !== String(VISTA[k]));
  const indCambia = String(nueva.ind) !== String(VISTA.ind) || nueva.cinta !== VISTA.cinta; // OF-5a
  const soloFiltro = MODELO && ['activo', 'marco', 'familia', 'paso', 'unidad', 'hasta']
    .every((k) => nueva[k] === VISTA[k]);
  const sesionCambia = nueva.sesion !== VISTA.sesion || String(nueva.filas) !== String(VISTA.filas);
  VISTA = nueva;
  if (soloFiltro) {
    MODELO.filtro = { min: VISTA.min, esconde: VISTA.esconde, grande: VISTA.grande };
    window.FLUJO_HITOS.vista = hash;
    pintaSelectores();
    LIENZO.vista(VISTA); // OF-6a: el modo de la celda, el color y los dos ejes: se repinta, no se pide
    if (sesionCambia) cargaArranques(CARGA);
    if (capasCambian) cargaCapas();
    if (indCambia) {
      midePaneles(VISTA);
      cargaVistaIndicadores(CARGA);
      cargaVistaCinta();
    }
    LIENZO.pide();
    return;
  }
  carga();
}

function arranca() {
  LIENZO = creaLienzo(document.getElementById('lienzo'), {
    alLeer: lectura, alCambiar: vistaCambiada, alMenu: abreMenu, cruz: document.getElementById('cruz'),
    ficha: document.getElementById('ficha') });
  // OF-6a: los modos de la celda, el color, los numeros, el menu del eje, el presente, la ayuda y el teclado
  document.getElementById('sel-celda').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-valor]');
    if (b) cambia({ celda: b.dataset.valor });
  });
  document.querySelectorAll('#m-color input[name=color]').forEach((r) => r.addEventListener('change', () => cambia({ color: r.value })));
  document.querySelectorAll('#m-color input[name=ref]').forEach((r) => r.addEventListener('change', () => cambia({ ref: r.value })));
  document.getElementById('sel-numeros').addEventListener('change', (ev) => cambia({ numeros: ev.target.checked }));
  document.getElementById('menu-escala').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-valor]');
    if (b && b.dataset.valor === 'auto') LIENZO.auto();
    else if (b) LIENZO.manual();
  });
  document.querySelectorAll('#menu-eje input[data-fila]').forEach((c) => c.addEventListener('change', () => {
    const marcadas = [...document.querySelectorAll('#menu-eje input[data-fila]')].filter((x) => x.checked)
      .map((x) => x.dataset.fila);
    cambia({ filas: FILAS_RESUMEN.filter((f) => marcadas.includes(f)) });
  }));
  document.querySelectorAll('#menu-eje input[name=rueda]').forEach((r) => r.addEventListener('change', () => cambia({ rueda: r.value })));
  document.addEventListener('mousedown', (ev) => {
    if (!ev.target.closest('#menu-eje')) document.getElementById('menu-eje').hidden = true;
    document.querySelectorAll('details.menu[open]').forEach((d) => {
      if (!d.contains(ev.target)) d.open = false;
    });
  });
  document.getElementById('b-presente').addEventListener('click', () => LIENZO.presente());
  document.getElementById('b-ayuda').addEventListener('click', () => document.getElementById('ayuda').showModal());
  document.addEventListener('keydown', teclado);
  cruzDeLosPaneles();
  creaIndicadores(document.getElementById('lienzo-ind')); // OF-5a
  atiendeMandosIndicadores();
  [['sel-activo', 'activo'], ['sel-marco', 'marco'], ['sel-familia', 'familia'], ['sel-unidad', 'unidad']]
    .forEach(([id, k]) => {
      document.getElementById(id).addEventListener('click', (ev) => {
        const b = ev.target.closest('button[data-valor]');
        // OF-6a: otro activo, marco, familia o unidad es otra vista: los ejes vuelven a lo de por omision
        if (b) cambia({ [k]: b.dataset.valor, paso: k === 'activo' ? 'auto' : VISTA.paso, x: null, y: null, fila: null });
      });
    });
  document.getElementById('sel-paso').addEventListener('change', (ev) => cambia({ paso: ev.target.value }));
  const numero = (v) => (/^\d+(\.\d+)?$/.test(v) && Number(v) > 0 ? v : null);
  document.getElementById('sel-min').addEventListener('change', (ev) => cambia({ min: numero(ev.target.value) }));
  document.getElementById('sel-grande').addEventListener('change', (ev) => cambia({ grande: numero(ev.target.value) }));
  document.getElementById('sel-esconde').addEventListener('change', (ev) => cambia({ esconde: ev.target.checked }));
  window.addEventListener('hashchange', aplicaHash);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && LATIDO !== null) late();
  });
  // OF-3: el gestor de sesiones (con su hora escrita), las capas, el modo TPO y el lienzo del TPO
  LIENZO_TPO = creaLienzoTPO(document.getElementById('lienzo-tpo'));
  document.getElementById('sel-sesion').addEventListener('change', (ev) => {
    if (ev.target.value !== 'propia') cambia({ sesion: ev.target.value });
    else document.getElementById('sesion-propia').hidden = false;
  });
  const propia = () => {
    const s = document.getElementById('ses-ini').value + '-' + document.getElementById('ses-fin').value;
    if (leeSesion(s)) cambia({ sesion: s });
  };
  document.getElementById('ses-ini').addEventListener('change', propia);
  document.getElementById('ses-fin').addEventListener('change', propia);
  [['capa-perfil', 'perfil'], ['capa-vwap', 'vwap'], ['capa-dinamico', 'dinamico']].forEach(([id, c]) => {
    document.getElementById(id).addEventListener('change', (ev) => {
      cambia({ capas: CAPAS.filter((x) => (x === c ? ev.target.checked : VISTA.capas.includes(x))) });
    });
  });
  const compuesto = () => {
    const n = Math.round(Number(document.getElementById('sel-compuesto').value)) || COMPUESTO_DEFECTO;
    cambia({ compuesto: document.getElementById('capa-compuesto').checked ? Math.min(COMPUESTO_MAXIMO, Math.max(2, n)) : null });
  };
  document.getElementById('capa-compuesto').addEventListener('change', compuesto);
  document.getElementById('sel-compuesto').addEventListener('change', compuesto);
  document.getElementById('capa-fijo').addEventListener('change', (ev) => {
    if (!ev.target.checked) cambia({ fijo: null });
    else if (!VISTA.fijo) pintaSelectores(); // el fijo nace de un MAYUS + arrastre sobre el grafico
  });
  document.getElementById('sel-modo').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-valor]');
    if (b) cambia({ modo: b.dataset.valor });
  });
  document.getElementById('sel-sesiones').addEventListener('change', (ev) => {
    cambia({ sesiones: Math.min(TPO_MAXIMO, Math.max(1, Math.round(Number(ev.target.value)) || TPO_SESIONES)) });
  });
  seleccionFija();
  setInterval(vigilaVisible, 400);
  aplicaHash();
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('DOMContentLoaded', arranca);
}
