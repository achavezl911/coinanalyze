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
window.FLUJO_HITOS = { listo: false, vista: null, peticiones: [] };

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
  window.FLUJO_HITOS.vista = escribeHash(VISTA);
  pintaSelectores();
  pintaEstado('pidiendo la historia…');
  const w = ventana(VISTA, Date.now());
  const sobre = await pedir(RUTA, parametros(VISTA, w.desde, w.hasta, VISTA.paso));
  apuntar(sobre);
  if (mia !== CARGA) return;
  if (!sobre.ok) {
    FALLO = sobre;
    LIENZO.pon({ velas: [] }, VISTA.ver);
  } else {
    ULTIMA = { asOfMs: Date.parse(sobre.datos.as_of), t: reloj() };
    MODELO = modelo(sobre.datos);
    LIENZO.pon(MODELO, VISTA.ver);
    if (!VISTA.hasta) arrancaLatido();
  }
  pintaSelectores();
  pintaEstado();
  // listo cuando el lienzo ya pinto ESTA vista (dos fotogramas: el que la pide y el que la dibuja)
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (mia === CARGA) window.FLUJO_HITOS.listo = true;
  }));
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
  ULTIMA = { asOfMs: Date.parse(sobre.datos.as_of), t: reloj() };
  const porTs = new Map(MODELO.velas.map((v, i) => [Date.parse(v.ts), i]));
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
}

/* ------------------------------------------------------------------ decir */
function pintaEstado(pidiendo) {
  const caja = vaciar(document.getElementById('estado'));
  const grafico = document.getElementById('grafico');
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
  let rancio = false;
  if (FALLO) {
    const p = linea(noSe('error', 'HTTP ' + FALLO.http + ' · ' + (FALLO.motivo || '')));
    p.setAttribute('data-estado', 'error');
    if (MODELO) p.appendChild(document.createTextNode(' · se enseña lo último que llegó'));
  }
  if (MODELO && !VISTA.hasta && ULTIMA) {
    const edadS = (reloj() - ULTIMA.t) / 1000;
    rancio = edadS > RANCIO_S;
    if (rancio) {
      linea(noSe('rancio', 'la última respuesta buena es de hace ' + Math.round(edadS) + ' s (el latido pide cada '
        + VIVO_S + ' s)')).setAttribute('data-estado', 'rancio');
    }
  }
  if (MODELO && !MODELO.velas.some((v) => v.niveles.length)) {
    linea(noSe('nulo', 'la ruta contestó sin una sola celda en toda la ventana: no hay operaciones que pintar'))
      .setAttribute('data-estado', 'nulo');
  }
  if (MODELO) {
    const huecos = MODELO.velas.filter((v) => v.estado === 'hueco').length;
    const inc = MODELO.velas.filter((v) => v.estado === 'incompleta').length;
    const fam = FAMILIAS[VISTA.familia];
    const p = linea(
      el('b', null, VISTA.activo + ' · ' + VISTA.marco + ' · ' + fam.rotulo),
      ' (' + MODELO.venues.join(', ') + ') · paso ' + MODELO.paso + (MODELO.paso_auto
        ? ' (automático: la vela mediana toca ' + MODELO.paso_auto.niveles_vela_mediana + ' niveles)' : ' (fijado)')
        + ' · ' + (MODELO.unidad === 'usd' ? 'en USD' : 'en ' + VISTA.activo)
        + ' · ' + (VISTA.hasta ? 'ventana fija hasta ' + VISTA.hasta.slice(0, 16).replace('T', ' ') + 'Z'
          : rancio ? 'RANCIO' : 'vivo: la vela en curso se pide cada ' + VIVO_S + ' s')
        + ' · ' + MODELO.velas.length + ' velas'
        + (inc ? ' · ' + inc + ' incompleta(s)' : '') + (huecos ? ' · ' + huecos + ' hueco(s) sin dato' : ''));
    if (MODELO.paso_auto) p.title = MODELO.paso_auto.regla;
  }
  grafico.classList.toggle('rancio', rancio || (!!FALLO && !!MODELO));
}

function lectura(v, fila) {
  const caja = document.getElementById('lectura');
  if (!v) {
    caja.textContent = '';
    return;
  }
  const t = v.ts.slice(5, 16).replace('T', ' ') + 'Z';
  const cob = { abierta: 'en curso', hueco: 'HUECO: nadie la escuchó', vacia: 'escuchada entera, sin operaciones',
                completa: 'completa', incompleta: 'INCOMPLETA: faltan ' + v.faltan + ' de ' + v.esperados + ' minutos-venue' };
  if (fila) {
    caja.textContent = t + ' · nivel ' + fila.nivel + ' · venta ' + fila.venta + ' · compra ' + fila.compra + ' · Δ '
      + fila.delta + (fila.dc ? ' · desequilibrio COMPRADOR' : '') + (fila.dv ? ' · desequilibrio VENDEDOR' : '')
      + (fila.ac || fila.av ? ' (apilado)' : '');
  } else {
    caja.textContent = t + ' · ' + cob[v.estado] + (v.niveles.length ? ' · compra ' + v.compra + ' · venta ' + v.venta
      + ' · Δ ' + v.delta + ' · ' + v.operaciones + ' operaciones · POC ' + v.poc
      + (v.value_area ? ' · value area ' + v.value_area.val + '–' + v.value_area.vah : '') : '');
  }
}

/* ------------------------------------------------------------- los mandos */
function pintaSelectores() {
  [['sel-activo', 'activo'], ['sel-marco', 'marco'], ['sel-familia', 'familia'], ['sel-unidad', 'unidad']]
    .forEach(([id, k]) => {
      document.querySelectorAll('#' + id + ' button').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.valor === VISTA[k]));
      });
    });
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
  const soloFiltro = MODELO && ['activo', 'marco', 'familia', 'paso', 'unidad', 'hasta']
    .every((k) => nueva[k] === VISTA[k]);
  VISTA = nueva;
  if (soloFiltro) {
    MODELO.filtro = { min: VISTA.min, esconde: VISTA.esconde, grande: VISTA.grande };
    window.FLUJO_HITOS.vista = hash;
    pintaSelectores();
    LIENZO.pide();
    return;
  }
  carga();
}

function arranca() {
  LIENZO = creaLienzo(document.getElementById('lienzo'), lectura);
  [['sel-activo', 'activo'], ['sel-marco', 'marco'], ['sel-familia', 'familia'], ['sel-unidad', 'unidad']]
    .forEach(([id, k]) => {
      document.getElementById(id).addEventListener('click', (ev) => {
        const b = ev.target.closest('button[data-valor]');
        if (b) cambia({ [k]: b.dataset.valor, paso: k === 'activo' ? 'auto' : VISTA.paso });
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
  aplicaHash();
}

if (typeof document !== 'undefined' && document.addEventListener) {
  document.addEventListener('DOMContentLoaded', arranca);
}
