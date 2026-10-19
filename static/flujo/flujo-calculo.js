'use strict';
/* EL FOOTPRINT · lo que se CALCULA (campana 142, OF-2). Funciones puras: las prueba `node --test` y K109 las
 * recalcula por su cuenta. Nada de aqui toca el DOM ni pide nada.
 *
 * LO QUE SE CALCULA AQUI Y NO EN EL SERVIDOR: los desequilibrios (por nivel; servidos, la respuesta engordaria) y el
 * estado de cada vela contra el reloj. Lo demas -niveles, compra, venta, delta, POC, value area, paso automatico y
 * cobertura- llega servido por /api/orderflow/footprint y se pinta TAL CUAL.
 *
 * EL DESEQUILIBRIO (P2 de la campana), DIAGONAL, en aritmetica EXACTA: BigInt sobre el texto decimal servido (en float,
 * 0.3 >= 3 * 0.1 es falso y en decimal es verdad):
 *   COMPRADOR en P  si compra(P) >= 3 x venta(P - paso)   y  compra(P) >= la media por nivel de su vela
 *   VENDEDOR  en P  si venta(P)  >= 3 x compra(P + paso)  y  venta(P)  >= la media por nivel de su vela
 * La media por nivel es (compra + venta de todos los niveles de la vela) / cuantos niveles. El vecino solo se mira
 * DENTRO de la vela (de su nivel mas bajo al mas alto). APILADO: 3 o mas niveles seguidos del mismo lado. Medido sobre
 * celdas reales de produccion (x1-tmp/c142/p2.py): sin el minimo, el 89 % de los niveles de BTC 1m salian
 * desequilibrio; con el, del 13 al 25 % segun activo y marco.
 * OF-6a (campana 148, F-05 de la investigacion de plataformas): un lado contrario a CERO no da desequilibrio (antes un
 * nivel sin celda valia 0 y cualquier compra lo «triplicaba»). El x3 y el minimo de arriba se quedan.
 */

const FLUJO_ACTIVOS = ['BTC', 'ETH', 'SOL'];
const FLUJO_MARCOS = { '1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440 };
// Las velas que se piden de historia: 240, salvo donde no caben en los 30 dias que se guardan las celdas.
const FLUJO_HISTORIA = { '1m': 240, '5m': 240, '15m': 240, '1h': 240, '4h': 180, '1d': 30 };
// LAS FAMILIAS (decision del encargo, por la dispersion medida entre venues): nunca se suman dos.
const FAMILIAS = {
  perp: { rotulo: 'perpetuos USDT', venues: ['binance_usdm', 'bybit_linear', 'okx_swap', 'bitget_usdt'] },
  spot: { rotulo: 'spot USDT', venues: ['binance_spot', 'bybit_spot', 'okx_spot'] },
  coinbase: { rotulo: 'Coinbase spot (USD)', venues: ['coinbase_spot'] },
  deribit: { rotulo: 'Deribit perpetuo (USD; SOL en USDC)', venues: ['deribit_perp'] },
};
const DESEQ_RAZON = 3n;
const DESEQ_APILADO = 3;
// Una vela se juzga CERRADA 90 s despues de su ultimo minuto: el colector escribe un minuto a los 10 s de cerrarse y
// lo reescribe, definitivo, a los 70 s (app/orderflow.py). Antes de eso, sin filas no es un hueco: es que no ha llegado.
const CIERRE_S = 90;
// OF-6a (campana 148): sin `ver=` en el hash, las velas a la vista salen del ESPACIADO por omision (flujo-dibujo.js):
// la vista se mide en pixeles por vela, no en velas, para que la cifra quepa en cualquier pantalla (P2).
const VER_DEFECTO = null;
const VER_MAXIMO = 120; // el tope del lienzo (P1 de la 148: con 400 velas no aguanta)

function tiene(obj, k) {
  return Object.prototype.hasOwnProperty.call(obj, k);
}

function isoZ(ms) {
  return new Date(ms).toISOString().replace('.000Z', 'Z');
}

/* ------------------------------------------------------------------ el hash
 * `#<activo>/<marco>/<familia>[/<paso>][/clave=valor...]`: una vista = una URL (headless no pulsa). El paso es `auto`
 * (por omision) o un numero; detras, en cualquier orden: unidad=usd, min=<x>, esconde, grande=<x>, hasta=<ISO>, ver=<n>.
 * Lo que no se entiende NO se adivina: se cae al defecto y la pagina reescribe el hash. */
function leeHash(hash) {
  const partes = String(hash || '').replace(/^#/, '').split('/').filter(Boolean);
  const e = { activo: 'BTC', marco: '1m', familia: 'perp', paso: 'auto', unidad: 'base', min: null, esconde: false,
              grande: null, hasta: null, ver: VER_DEFECTO };
  // OF-3 (campana 143): las capas, la sesion y el modo TPO; sin sus claves, la vista es la del footprint de la 142
  Object.assign(e, { sesion: 'dia', capas: [], compuesto: null, fijo: null, modo: 'footprint', sesiones: TPO_SESIONES });
  // OF-5a (campana 146): los indicadores (paneles, marcas de grandes y la cinta) y el filtro de la cinta
  Object.assign(e, { ind: INDICADORES_DEFECTO.slice(), cinta: null });
  // OF-6a (campana 148): lo que se ve y como (el modo de la celda, el color, los numeros, las filas de resumen) y el
  // estado de los DOS ejes: `x` velas desde el final (sin ella, sigue a la ultima), `y` el precio del centro (sin ella,
  // la escala vertical es AUTO) y `fila` los px de una fila
  Object.assign(e, { celda: 'bidask', color: 'delta', ref: 'vela', numeros: true, filas: FILAS_RESUMEN.slice(),
                     rueda: 'zoom', x: null, y: null, fila: null });
  const a = String(partes[0] || '').toUpperCase();
  if (FLUJO_ACTIVOS.includes(a)) e.activo = a;
  if (partes[1] && tiene(FLUJO_MARCOS, partes[1])) e.marco = partes[1];
  if (partes[2] && tiene(FAMILIAS, partes[2])) e.familia = partes[2];
  let resto = partes.slice(3);
  if (resto.length && !resto[0].includes('=') && resto[0] !== 'esconde') {
    if (resto[0] === 'auto' || (/^\d+(\.\d+)?$/.test(resto[0]) && Number(resto[0]) > 0)) e.paso = resto[0];
    resto = resto.slice(1);
  }
  const positivo = (v) => /^\d+(\.\d+)?$/.test(v || '') && Number(v) > 0;
  resto.forEach((p) => {
    const [k, v] = p.split('=');
    if (k === 'unidad' && (v === 'usd' || v === 'base')) e.unidad = v;
    else if (k === 'min' && positivo(v)) e.min = v;
    else if (k === 'grande' && positivo(v)) e.grande = v;
    else if (k === 'esconde' && v === undefined) e.esconde = true;
    else if (k === 'ver' && /^\d+$/.test(v || '') && Number(v) >= 5) e.ver = Math.min(VER_MAXIMO, Number(v));
    else if (k === 'hasta' && v) {
      const t = Date.parse(v);
      if (!Number.isNaN(t) && t % (FLUJO_MARCOS[e.marco] * 60000) === 0) e.hasta = isoZ(t);
    }
    else if (k === 'sesion' && leeSesion(v)) e.sesion = v;
    else if (k === 'capas' && v) e.capas = CAPAS.filter((c) => v.split(',').includes(c));
    else if (k === 'compuesto' && /^\d+$/.test(v || '') && Number(v) >= 2) e.compuesto = Math.min(COMPUESTO_MAXIMO, Number(v));
    else if (k === 'fijo' && v) {
      const [a, b] = v.split(',').map((x) => Date.parse(x));
      if (a < b && a % 60000 === 0 && b % 60000 === 0 && b - a <= 31 * DIA_MS) e.fijo = [isoZ(a), isoZ(b)];
    }
    else if (k === 'modo' && v === 'tpo') e.modo = 'tpo';
    else if (k === 'sesiones' && /^\d+$/.test(v || '') && Number(v) >= 1) e.sesiones = Math.min(TPO_MAXIMO, Number(v));
    else if (k === 'ind' && v) e.ind = leeIndicadores(v);
    else if (k === 'cinta' && positivo(v)) e.cinta = v;
    else if (k === 'celda' && CELDAS.includes(v)) e.celda = v;
    else if (k === 'color' && v === 'volumen') e.color = v;
    else if (k === 'ref' && (v === 'visible' || v === 'sesion')) e.ref = v;
    else if (k === 'numeros' && v === 'no') e.numeros = false;
    else if (k === 'filas' && v) e.filas = v === 'ninguna' ? [] : FILAS_RESUMEN.filter((f) => v.split(',').includes(f));
    else if (k === 'rueda' && v === 'desplaza') e.rueda = v;
    else if (k === 'x' && /^\d+(\.\d)?$/.test(v || '')) e.x = Number(v);
    else if (k === 'y' && positivo(v)) e.y = v;
    else if (k === 'fila' && /^\d+$/.test(v || '') && Number(v) >= FILA_MIN && Number(v) <= FILA_MAX) e.fila = Number(v);
  });
  return e;
}

function escribeHash(e) {
  let h = '#' + e.activo + '/' + e.marco + '/' + e.familia;
  if (e.paso !== 'auto') h += '/' + e.paso;
  if (e.unidad === 'usd') h += '/unidad=usd';
  if (e.min) h += '/min=' + e.min;
  if (e.esconde) h += '/esconde';
  if (e.grande) h += '/grande=' + e.grande;
  if (e.hasta) h += '/hasta=' + e.hasta;
  if (e.ver !== VER_DEFECTO && e.ver !== undefined) h += '/ver=' + e.ver;
  if (e.sesion && e.sesion !== 'dia') h += '/sesion=' + e.sesion;
  if (e.capas && e.capas.length) h += '/capas=' + e.capas.join(',');
  if (e.compuesto) h += '/compuesto=' + e.compuesto;
  if (e.fijo) h += '/fijo=' + e.fijo.join(',');
  if (e.modo === 'tpo') h += '/modo=tpo';
  if (e.sesiones && e.sesiones !== TPO_SESIONES) h += '/sesiones=' + e.sesiones;
  if (e.ind && e.ind.join(',') !== INDICADORES_DEFECTO.join(',')) h += '/ind=' + (e.ind.join(',') || 'ninguno');
  if (e.cinta) h += '/cinta=' + e.cinta;
  if (e.celda && e.celda !== 'bidask') h += '/celda=' + e.celda;
  if (e.color === 'volumen') h += '/color=volumen';
  if (e.ref && e.ref !== 'vela') h += '/ref=' + e.ref;
  if (e.numeros === false) h += '/numeros=no';
  if (e.filas && e.filas.join(',') !== FILAS_RESUMEN.join(',')) h += '/filas=' + (e.filas.join(',') || 'ninguna');
  if (e.rueda === 'desplaza') h += '/rueda=desplaza';
  if (e.x !== null && e.x !== undefined) h += '/x=' + e.x;
  if (e.y) h += '/y=' + e.y;
  if (e.fila) h += '/fila=' + e.fila;
  return h;
}

/* La historia: FLUJO_HISTORIA velas que acaban en `hasta` (una ventana fija del pasado) o, sin `hasta`, en la vela en
 * curso incluida. Las velas empiezan en multiplos del marco desde las 00:00 UTC, como date_bin en el servidor. */
function ventana(e, ahoraMs) {
  const m = FLUJO_MARCOS[e.marco] * 60000;
  const fin = e.hasta ? Date.parse(e.hasta) : (Math.floor(ahoraMs / m) + 1) * m;
  return { desde: isoZ(fin - FLUJO_HISTORIA[e.marco] * m), hasta: isoZ(fin) };
}

/* El latido pide SOLO las velas que todavia pueden cambiar: de la que contiene «ahora - CIERRE_S» a la en curso. */
function ventanaViva(marco, ahoraMs) {
  const m = FLUJO_MARCOS[marco] * 60000;
  return { desde: isoZ(Math.floor((ahoraMs - CIERRE_S * 1000) / m) * m), hasta: isoZ((Math.floor(ahoraMs / m) + 1) * m) };
}

/* ------------------------------------------------------- el estado de una vela
 *   abierta     no ha cerrado (o no hace CIERRE_S): lo que falte todavia puede llegar
 *   hueco       cerrada y SIN una sola fila de cobertura: nadie la escucho. Se dice AUSENTE; no es cero
 *   incompleta  cerrada y con minutos-venue que no se escucharon enteros: `faltan` de `esperados`
 *   vacia       cerrada, escuchada entera y sin operaciones: ese cero si es un dato
 *   completa    cerrada, escuchada entera y con operaciones */
function estadoVela(v, asOfMs, marco) {
  const fin = Date.parse(v.ts) + FLUJO_MARCOS[marco] * 60000;
  const c = v.cobertura || {};
  const esperados = c.minutos_esperados === undefined ? null : c.minutos_esperados;
  if (fin + CIERRE_S * 1000 > asOfMs) return { estado: 'abierta', faltan: null, esperados };
  if (!c.minutos_con_fila) return { estado: 'hueco', faltan: esperados, esperados };
  if (!c.completa) return { estado: 'incompleta', faltan: esperados - c.minutos_completos, esperados };
  if (!(v.niveles || []).length) return { estado: 'vacia', faltan: 0, esperados };
  return { estado: 'completa', faltan: 0, esperados };
}

/* ------------------------------------------------------- aritmetica exacta */
function decimales(t) {
  const i = String(t).indexOf('.');
  return i < 0 ? 0 : String(t).length - i - 1;
}

function entero(t, e) {
  const s = String(t);
  const neg = s.startsWith('-');
  const [ent, fr = ''] = (neg ? s.slice(1) : s).split('.');
  const n = BigInt(ent + fr.padEnd(e, '0'));
  return neg ? -n : n;
}

/* Por nivel (en el orden servido, ascendente): {dc, dv, ac, av} = desequilibrio comprador / vendedor y si es parte de
 * un apilado de ese lado. `niveles` = [{nivel, compra, venta}] en texto decimal; `paso` en texto. */
function desequilibrios(niveles, paso) {
  const out = niveles.map(() => ({ dc: false, dv: false, ac: false, av: false }));
  const n = niveles.length;
  if (!n) return out;
  let e = decimales(paso);
  niveles.forEach((l) => { e = Math.max(e, decimales(l.nivel), decimales(l.compra), decimales(l.venta)); });
  const P = niveles.map((l) => entero(l.nivel, e));
  const C = niveles.map((l) => entero(l.compra, e));
  const V = niveles.map((l) => entero(l.venta, e));
  const s = entero(paso, e);
  const indice = new Map(P.map((p, i) => [p.toString(), i]));
  let suma = 0n;
  for (let i = 0; i < n; i++) suma += C[i] + V[i];
  const N = BigInt(n);
  const lo = P[0];
  const hi = P[n - 1];
  for (let i = 0; i < n; i++) {
    if (P[i] - s >= lo) {
      const j = indice.get((P[i] - s).toString());
      const abajo = j === undefined ? 0n : V[j];
      out[i].dc = abajo > 0n && C[i] * N >= suma && C[i] >= DESEQ_RAZON * abajo;
    }
    if (P[i] + s <= hi) {
      const j = indice.get((P[i] + s).toString());
      const arriba = j === undefined ? 0n : C[j];
      out[i].dv = arriba > 0n && V[i] * N >= suma && V[i] >= DESEQ_RAZON * arriba;
    }
  }
  ['dc', 'dv'].forEach((lado) => {
    const marca = lado === 'dc' ? 'ac' : 'av';
    let ini = 0;
    for (let i = 1; i <= n; i++) {
      const sigue = i < n && out[i][lado] && out[i - 1][lado] && P[i] - P[i - 1] === s;
      if (sigue) continue;
      if (out[i - 1][lado] && i - ini >= DESEQ_APILADO) for (let k = ini; k < i; k++) out[k][marca] = true;
      ini = i;
    }
  });
  return out;
}

/* ------------------------------------------------------- como se escribe una cifra
 * Compacta y SIN redondear a cero: lo que no es cero nunca se escribe «0». K109 relee el texto pintado y lo compara con
 * el valor servido a la precision con que se escribio. */
function cifra(t) {
  const x = Number(t);
  const a = Math.abs(x);
  if (x === 0) return '0';
  if (a >= 1e6) return (x / 1e6).toFixed(2) + 'M';
  if (a >= 1e4) return (x / 1e3).toFixed(1) + 'K';
  if (a >= 1e3) return (x / 1e3).toFixed(2) + 'K';
  if (a >= 100) return x.toFixed(0);
  if (a >= 10) return x.toFixed(1);
  if (a >= 1) return x.toFixed(2);
  return x.toPrecision(2);
}

/* El filtro por tamano: el total de la celda contra `min` (atenua, o esconde) y contra `grande` (resalta). */
function filtro(total, e) {
  if (e.min && Number(total) < Number(e.min)) return e.esconde ? 'escondida' : 'atenuada';
  if (e.grande && Number(total) >= Number(e.grande)) return 'grande';
  return 'normal';
}

/* ================================================================= OF-3 · LOS PERFILES (campana 143)
 * LAS SESIONES: la misma plantilla que el servidor (app/orderflow_lectura.py, SESIONES). Por omision el DIA UTC; si el
 * fin no es posterior al inicio, la sesion CRUZA la medianoche y es UNA (de un dia al siguiente). Lo que se pinta de
 * cada sesion (su perfil, su VWAP, su TPO) lo calcula y lo sirve el servidor; aqui solo se sabe DONDE empiezan, para
 * pedir el compuesto y el TPO de las N ultimas. */
const SESIONES = {
  dia: { rotulo: 'Día UTC', inicio: '00:00', fin: '24:00' },
  asia: { rotulo: 'Asia', inicio: '00:00', fin: '08:00' },
  europa: { rotulo: 'Europa', inicio: '07:00', fin: '16:00' },
  eeuu: { rotulo: 'EE.UU.', inicio: '13:30', fin: '20:00' },
};
const CAPAS = ['perfil', 'vwap', 'dinamico'];
// El tope de la ruta (app/orderflow_lectura.py RANGO_SESIONES, medido en P1): de la primera sesion a `hasta`, 7 dias.
const SESIONES_MAXIMO = 7;
const COMPUESTO_DEFECTO = 5;
const COMPUESTO_MAXIMO = SESIONES_MAXIMO;
const TPO_SESIONES = 3;
const TPO_MAXIMO = SESIONES_MAXIMO;
const DIA_MS = 86400000;

function minutoDelDia(t) {
  if (!/^\d\d:\d\d$/.test(t || '')) return null;
  const m = Number(t.slice(0, 2)) * 60 + Number(t.slice(3));
  return Number(t.slice(3)) < 60 && m <= 1440 ? m : null;
}

/* `dia`, `asia`, `europa`, `eeuu` o `HH:MM-HH:MM` -> { nombre, rotulo, inicio, fin, ini (minuto del dia), minutos,
 * cruza } o null si no se entiende (y entonces el hash cae al dia). */
function leeSesion(v) {
  const plantilla = tiene(SESIONES, v || '') ? SESIONES[v] : null;
  const partes = plantilla ? [plantilla.inicio, plantilla.fin] : String(v || '').split('-');
  if (partes.length !== 2) return null;
  const ini = minutoDelDia(partes[0]);
  const fin = minutoDelDia(partes[1]);
  if (ini === null || fin === null || ini === 1440) return null;
  const minutos = (((fin - ini) % 1440) + 1440) % 1440 || 1440;
  return { nombre: v, rotulo: plantilla ? plantilla.rotulo : 'propia', inicio: partes[0], fin: partes[1], ini, minutos,
           cruza: ini + minutos > 1440 };
}

/* El inicio de la ULTIMA sesion que empieza antes de `ms`. */
function inicioSesion(ms, ses) {
  const o = ses.ini * 60000;
  return Math.floor((ms - 1 - o) / DIA_MS) * DIA_MS + o;
}

/* Las N ultimas sesiones que empiezan antes de `hastaMs`: [desde, hasta) toca exactamente esas N. */
function ventanaSesiones(hastaMs, ses, n) {
  return { desde: isoZ(inicioSesion(hastaMs, ses) - (n - 1) * DIA_MS), hasta: isoZ(hastaMs) };
}

/* La ventana de las capas de sesion (perfil y VWAP): la del footprint, sin pasar de las SESIONES_MAXIMO ultimas (el
 * tope de la ruta). Con 1h, 4h o 1d la historia es mas larga: el desde se adelanta al primer borde de vela que lo
 * cumple, y la pantalla lo dice (`recortada`). */
function ventanaCapas(w, ses, marco) {
  const m = FLUJO_MARCOS[marco] * 60000;
  const tope = Math.ceil((inicioSesion(Date.parse(w.hasta), ses) - (SESIONES_MAXIMO - 1) * DIA_MS) / m) * m;
  return Date.parse(w.desde) >= tope ? { desde: w.desde, hasta: w.hasta, recortada: false }
    : { desde: isoZ(tope), hasta: w.hasta, recortada: true };
}

/* El estado de un RANGO de minutos [desde, hasta) servido por /perfil (el dinamico y el fijo): como una vela de
 * cualquier largo. Si no ha cerrado (hasta + CIERRE_S despues de as_of), «en curso»: lo que falta aun puede llegar. */
function estadoRango(desdeMs, hastaMs, c, asOfMs) {
  const cob = c || {};
  const esperados = cob.minutos_esperados === undefined ? null : cob.minutos_esperados;
  if (hastaMs + CIERRE_S * 1000 > asOfMs) return { estado: 'abierta', en_curso: true, faltan: null, esperados };
  if (!cob.minutos_con_fila) return { estado: 'hueco', en_curso: false, faltan: esperados, esperados };
  if (!cob.completa) {
    return { estado: 'incompleta', en_curso: false, faltan: esperados - cob.minutos_completos, esperados };
  }
  return { estado: 'completa', en_curso: false, faltan: 0, esperados };
}

/* El estado de una SESION servida (sesiones, vwap, tpo): el servidor dice si sigue en curso y su cobertura hasta su
 * corte; lo que falta se dice aunque siga en curso, y una sesion que acaba de empezar no echa nada en falta. */
function estadoSesion(s) {
  const c = s.cobertura || {};
  const esperados = c.minutos_esperados === undefined ? null : c.minutos_esperados;
  let estado = 'completa';
  if (esperados !== 0 && !c.minutos_con_fila) estado = 'hueco';
  else if (esperados !== 0 && !c.completa) estado = 'incompleta';
  return { estado, en_curso: !!s.en_curso, faltan: estado === 'completa' ? 0 : esperados - (c.minutos_completos || 0),
           esperados };
}

/* La marca que se escribe sobre una capa: en curso, hueco o cuantos minutos-venue faltan (nada si no hay nada que
 * decir). */
function marcaCapa(st) {
  const partes = [];
  if (st.en_curso) partes.push('en curso');
  if (st.estado === 'hueco') partes.push('hueco');
  else if (st.faltan) partes.push('faltan ' + st.faltan + '/' + st.esperados);
  return partes.join(' · ') || null;
}

/* ================================================================= OF-5a · LOS INDICADORES (campana 146)
 * En el hash, `ind=` dice que se enciende, en su orden (los paneles bajo el footprint, las marcas de las grandes y la
 * cinta); sin la clave, lo de por omision; `ind=ninguno`, nada. Lo que no se entiende cae al defecto. */
const INDICADORES = ['delta', 'cvd', 'oi', 'oib', 'funding', 'ls', 'liq', 'grandes', 'cinta'];
const INDICADORES_DEFECTO = ['delta', 'cvd', 'grandes', 'cinta'];

function leeIndicadores(v) {
  if (v === 'ninguno') return [];
  const pedidos = String(v).split(',');
  const lista = INDICADORES.filter((c) => pedidos.includes(c));
  return lista.length ? lista : INDICADORES_DEFECTO.slice();
}

/* ================================================================= OF-6a · EL FOOTPRINT PROFESIONAL (campana 148)
 * Lo que la pantalla escribe y como lo colorea, segun la especificacion de entregas/20261018-2130-INVESTIGACION-
 * plataformas.md (los E-xx y F-xx citados), sin cambiar nada de lo que se sirve. */
const CELDAS = ['bidask', 'delta', 'volumen', 'trades', 'perfil']; // F-01: los modos de la celda
const FILAS_RESUMEN = ['vol', 'delta', 'deltap', 'cvd', 'ops']; // F-10 (delta min/max no salen de lo servido)
const FILA_MIN = 4;
const FILA_MAX = 60;
const PASOS_COLOR = 20; // F-04: la intensidad en 20 pasos discretos
const CORTE_COLOR = 0.98; // F-04: el corte superior, p98 de la referencia
// E-04: por debajo de 1 000, los decimales del activo en su unidad base (en USD y en conteos, ninguno)
const DECIMALES = { BTC: 3, ETH: 2, SOL: 1 };

/* E-04: >= 1 000 -> «1.2K», >= 1 000 000 -> «1.2M», con un decimal; por debajo, `dec` decimales, uno menos por cada
 * cifra entera de mas (cinco caracteres como mucho: lo que midio P2 de la 148 sobre velas reales: con los decimales
 * fijos la p90 de BTC pedia 7). Lo que no es cero nunca se escribe «0»: si redondea a cero, una cifra significativa. */
function cifraE04(t, dec) {
  const x = Number(t);
  const a = Math.abs(x);
  if (x === 0) return '0';
  const mil = (v, d, suf) => {
    const s = (x / d).toFixed(1);
    return Math.abs(Number(s)) >= 1000 && suf === 'K' ? mil(v, 1e6, 'M') : s + suf;
  };
  if (a >= 1e6) return mil(x, 1e6, 'M');
  if (a >= 1e3) return mil(x, 1e3, 'K');
  const s = x.toFixed(Math.max(0, dec - (a < 10 ? 0 : a < 100 ? 1 : 2)));
  if (Math.abs(Number(s)) >= 1000) return mil(x, 1e3, 'K');
  return Number(s) !== 0 ? s : x.toPrecision(1);
}

/* Los decimales con que se escribe una cantidad de la vista (E-04). */
function decimalesDe(activo, unidad) {
  return unidad === 'usd' ? 0 : DECIMALES[activo] === undefined ? 2 : DECIMALES[activo];
}

/* F-07: el POC de la vela es el nivel de mas volumen y, si hay EMPATE, todos (comparados en exacto). */
function pocsDe(niveles) {
  let e = 0;
  niveles.forEach((l) => { e = Math.max(e, decimales(l.total)); });
  const T = niveles.map((l) => entero(l.total, e));
  const m = T.reduce((a, t) => (t > a ? t : a), -1n);
  return niveles.filter((_, i) => T[i] === m).map((l) => l.nivel);
}

/* F-04: la referencia del 100 %: el p98 (rango mas cercano) de los valores absolutos NO nulos del conjunto. */
function referencia(valores) {
  const xs = valores.map((v) => Math.abs(v)).filter((v) => v > 0).sort((a, b) => a - b);
  return xs.length ? xs[Math.ceil(CORTE_COLOR * xs.length) - 1] : 0;
}

/* F-04: el paso de color (0..19) de un valor contra su referencia; lo que pasa del corte satura; -1 = nada que pintar. */
function pasoColor(v, ref) {
  const a = Math.abs(v);
  if (!(ref > 0) || !(a > 0)) return -1;
  return Math.min(PASOS_COLOR - 1, Math.floor(PASOS_COLOR * Math.min(1, a / ref)));
}

/* La sesion a la que pertenece una vela (el inicio de la ultima que empezo en o antes de ella), o null si la vela cae
 * fuera de su tramo (una plantilla de menos de 24 h). */
function sesionDe(ts, ses) {
  const t = Date.parse(ts);
  const ini = inicioSesion(t + 1, ses);
  return t < ini + ses.minutos * 60000 ? ini : null;
}

/* F-10: el CVD DE SESION por vela, EXACTO (BigInt sobre el texto servido): por cada sesion, desde su inicio. Si la
 * sesion empezo antes de la primera vela, su arranque es el delta de la sesion hasta ahi (`arranques[inicio]`, de
 * /api/orderflow/sesiones cortada en la primera vela: {delta, estado}); si esa peticion fallo, no se sabe y no se
 * escribe. Lo que no se escucho no se suma ni se supone: una vela HUECO no lleva CVD, y desde ella (o desde un arranque
 * con minutos sin escuchar, o una vela incompleta) el CVD de la sesion es `incompleta`: le falta lo que no se escucho,
 * como a una vela incompleta, y se dice. -> [{valor (texto) | null, estado, sesion}] */
function cvdSesion(velas, ses, arranques) {
  let e = 0;
  velas.forEach((v) => { e = Math.max(e, decimales(v.delta)); });
  Object.values(arranques || {}).forEach((a) => { if (a && a.delta !== null) e = Math.max(e, decimales(a.delta)); });
  const t0 = velas.length ? Date.parse(velas[0].ts) : 0;
  let actual = null;
  let acum = null;
  let estado = null;
  return velas.map((v) => {
    const s = sesionDe(v.ts, ses);
    if (s !== actual) {
      actual = s;
      acum = null;
      estado = 'completa';
      if (s !== null && s >= t0) acum = 0n;
      else if (s !== null) {
        const a = (arranques || {})[s];
        if (a && a.delta !== null && a.delta !== undefined) {
          acum = entero(a.delta, e);
          if (a.estado !== 'completa') estado = 'incompleta';
        } else if (a && a.estado === 'hueco') {
          acum = 0n;
          estado = 'incompleta';
        }
      }
    }
    if (s === null || acum === null) return { valor: null, estado: null, sesion: s };
    if (v.estado === 'hueco') {
      estado = 'incompleta';
      return { valor: null, estado: null, sesion: s };
    }
    if (v.estado === 'incompleta') estado = 'incompleta';
    acum += entero(v.delta, e);
    return { valor: deEntero(acum, e), estado, sesion: s };
  });
}

/* Un BigInt con `e` decimales, de vuelta a texto decimal sin ceros de mas (lo usan el CVD de los paneles y el de
 * sesion). */
function deEntero(n, e) {
  const neg = n < 0n;
  const s = (neg ? -n : n).toString().padStart(e + 1, '0');
  let r = e ? s.slice(0, s.length - e) + '.' + s.slice(s.length - e) : s;
  if (e) r = r.replace(/0+$/, '').replace(/\.$/, '');
  return (neg && r !== '0' ? '-' : '') + r;
}

/* F-10: las filas de resumen de una vela, en texto: lo servido tal cual (volumen, delta, operaciones), el delta % y
 * el CVD de sesion; null = no hay dato (una vela HUECO no tiene ninguna). */
function resumenVela(v, cvd) {
  if (v.estado === 'hueco') return { vol: null, delta: null, deltap: null, cvd: null, ops: null };
  const tot = Number(v.total);
  return { vol: v.total, delta: v.delta, deltap: tot ? String((Number(v.delta) / tot) * 100) : null,
           cvd: cvd ? cvd.valor : null, ops: String(v.operaciones) };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    FLUJO_MARCOS, FLUJO_HISTORIA, FAMILIAS, CIERRE_S, VER_DEFECTO, leeHash, escribeHash, ventana, ventanaViva,
    estadoVela, desequilibrios, cifra, filtro, isoZ,
  };
  Object.assign(module.exports, { SESIONES, CAPAS, SESIONES_MAXIMO, COMPUESTO_DEFECTO, TPO_SESIONES, leeSesion,
                                  inicioSesion, ventanaSesiones, ventanaCapas, estadoRango, estadoSesion, marcaCapa });
  Object.assign(module.exports, { INDICADORES, INDICADORES_DEFECTO, leeIndicadores, decimales, entero });
  Object.assign(module.exports, { CELDAS, FILAS_RESUMEN, PASOS_COLOR, DECIMALES, cifraE04, decimalesDe, pocsDe,
                                  deEntero, referencia, pasoColor, sesionDe, cvdSesion, resumenVela });
}
