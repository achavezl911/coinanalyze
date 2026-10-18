'use strict';
/* EL LIBRO · lo que se CALCULA (campana 145, OF-4b). Funciones puras: las prueba `node --test` y K111 las recalcula
 * por su cuenta. Nada de aqui toca el DOM ni pide nada.
 *
 * LAS FAMILIAS son las de OF-2: FAMILIAS de static/flujo/flujo-calculo.js, que esta pagina carga delante (y de ahi
 * tambien `cifra` e `isoZ`). Nunca se suman dos. Tambien se puede mirar UN VENUE SOLO.
 *
 * LO QUE CONOCE UN VENUE, de una foto o de un libro vivo al paso P: la compra, desde su nivel mas profundo hacia arriba
 * (por encima de la mejor compra no hay compras: es un cero CONOCIDO); la venta, desde abajo hasta su nivel mas
 * profundo. Su tramo conocido es [nivel mas profundo de la compra, nivel mas profundo de la venta]; fuera, no se sabe.
 * POR NIVEL, LA FAMILIA: la suma de los venues que lo CONOCEN y cuantos son (n de N). Si no lo conoce ninguno, el nivel
 * es DESCONOCIDO: nunca se suma ni se pinta como cero. Un venue sin foto en ese instante, o sin libro vivo, no conoce
 * nada. Los niveles van por su indice entero k (nivel = k * P): sin errores de coma flotante al comparar.
 */

const LIBRO_ACTIVOS = ['BTC', 'ETH', 'SOL'];
const LIBRO_VENUES = ['binance_usdm', 'binance_spot', 'bybit_linear', 'bybit_spot', 'okx_swap', 'okx_spot',
  'bitget_usdt', 'deribit_perp', 'coinbase_spot'];
// El paso al que se guardan las fotos (app/libro.py PASOS): el mapa no puede ir mas fino; los pasos validos son sus
// multiplos enteros.
const LIBRO_PASO = { BTC: '10', ETH: '0.5', SOL: '0.02' };
const LIBRO_VENTANAS = { '30m': 30, '1h': 60, '4h': 240, '12h': 720, '1d': 1440, '3d': 4320 };
const LIBRO_VENTANA_DEFECTO = '1h';
const LIBRO_TOPE_FOTOS = 2000; // app/libro_lectura.py TOPE_FOTOS
const LIBRO_FOTO_S = 5; // app/libro.py FOTO_S
// La base escribe cada minuto a los 2 s de cerrarse (app/libro.py CIERRE_S): un instante cuyo minuto no hace 62 s que
// cerro puede no estar escrito todavia. Eso no es un hueco: es «sin escribir aun».
const LIBRO_ESCRITO_S = 62;
const LIBRO_REGISTRO_MIN = 30; // mas atras, el mapa es un REGISTRO (el aviso de /api/libro/referencia)

function libroVenues(familia) {
  if (Object.prototype.hasOwnProperty.call(FAMILIAS, familia)) return FAMILIAS[familia].venues.slice();
  return LIBRO_VENUES.includes(familia) ? [familia] : null;
}

function rotuloFamilia(familia) {
  return Object.prototype.hasOwnProperty.call(FAMILIAS, familia) ? FAMILIAS[familia].rotulo : familia + ' (un venue)';
}

/* ¿`t` es un multiplo entero positivo de `base`? En aritmetica exacta (texto decimal escalado a BigInt). */
function esMultiplo(t, base) {
  if (!/^\d+(\.\d+)?$/.test(String(t || ''))) return false;
  const d = Math.max((String(t).split('.')[1] || '').length, (String(base).split('.')[1] || '').length);
  const n = BigInt(String(t).replace('.', '') + '0'.repeat(d - (String(t).split('.')[1] || '').length));
  const b = BigInt(String(base).replace('.', '') + '0'.repeat(d - (String(base).split('.')[1] || '').length));
  return n > 0n && n % b === 0n;
}

/* ------------------------------------------------------------------ el hash
 * `#<activo>/<familia|venue>[/<paso>][/<ventana>]` y detras, en cualquier orden, `unidad=usd`, `hasta=<ISO>` (una
 * ventana fija del pasado) y `ver=<n>` (cuantas columnas a la vista; por omision, todas). Una vista = una URL. Lo que no
 * se entiende cae al defecto y la pagina reescribe el hash. */
function leeHashLibro(hash) {
  const partes = String(hash || '').replace(/^#/, '').split('/').filter(Boolean);
  const e = { activo: 'BTC', familia: 'perp', paso: null, ventana: LIBRO_VENTANA_DEFECTO, unidad: 'base', hasta: null,
              ver: null };
  const a = String(partes[0] || '').toUpperCase();
  if (LIBRO_ACTIVOS.includes(a)) e.activo = a;
  if (partes[1] && libroVenues(partes[1])) e.familia = partes[1];
  partes.slice(2).forEach((p) => {
    const [k, v] = p.split('=');
    if (v === undefined && Object.prototype.hasOwnProperty.call(LIBRO_VENTANAS, k)) e.ventana = k;
    else if (v === undefined && esMultiplo(k, LIBRO_PASO[e.activo])) e.paso = k;
    else if (k === 'unidad' && (v === 'usd' || v === 'base')) e.unidad = v;
    else if (k === 'ver' && /^\d+$/.test(v || '') && Number(v) >= 10) e.ver = Number(v);
    else if (k === 'hasta' && v) {
      const t = Date.parse(v);
      if (!Number.isNaN(t) && t % 60000 === 0) e.hasta = isoZ(t);
    }
  });
  if (!e.paso) e.paso = LIBRO_PASO[e.activo];
  return e;
}

function escribeHashLibro(e) {
  let h = '#' + e.activo + '/' + e.familia;
  if (e.paso !== LIBRO_PASO[e.activo]) h += '/' + e.paso;
  if (e.ventana !== LIBRO_VENTANA_DEFECTO) h += '/' + e.ventana;
  if (e.unidad === 'usd') h += '/unidad=usd';
  if (e.hasta) h += '/hasta=' + e.hasta;
  if (e.ver) h += '/ver=' + e.ver;
  return h;
}

/* ------------------------------------------------------------------ la ventana del mapa
 * EL CADA: el menor multiplo de 5 s con el que la historia cabe en el tope de fotos de la ruta (venues x instantes). */
function cadaPara(nVenues, ventanaS) {
  let c = LIBRO_FOTO_S;
  while (nVenues * Math.ceil(ventanaS / c) > LIBRO_TOPE_FOTOS) c += LIBRO_FOTO_S;
  return c;
}

/* La historia: `ventana` que acaba en `hasta` (fija) o, sin el, en el instante en curso incluido. Las columnas son los
 * instantes multiplos de `cada` (los que la ruta devuelve: extract(epoch) % cada = 0). */
function ventanaLibro(e, ahoraMs) {
  const s = LIBRO_VENTANAS[e.ventana] * 60;
  const cada = cadaPara(libroVenues(e.familia).length, s);
  const c = cada * 1000;
  const hasta = e.hasta ? Date.parse(e.hasta) : (Math.floor(ahoraMs / c) + 1) * c;
  const desde = hasta - s * 1000;
  const columnas = [];
  for (let t = Math.ceil(desde / c) * c; t < hasta; t += c) columnas.push(t);
  return { desde: isoZ(desde), hasta: isoZ(hasta), cada, columnas };
}

/* ------------------------------------------------------------------ lo que conoce un venue */
function kDe(t, P) {
  return Math.round(Number(t) / P);
}

function nivelTexto(k, paso) {
  const d = (String(paso).split('.')[1] || '').length;
  const s = (k * Number(paso)).toFixed(d);
  return d ? s.replace(/0+$/, '').replace(/\.$/, '') : s;
}

/* Un libro (una foto servida o un aviso vivo) al paso P -> lo que conoce:
 *   { venue, compra, venta (texto exacto), kc (nivel de la mejor compra), qc (cantidades hacia abajo desde kc), kv, qv
 *     (hacia arriba desde kv), lo, hi (su tramo conocido) }
 * `compras`/`ventas` llegan como { desde, cantidades } (foto) o como [[nivel, cantidad], ...] (vivo); null o vacio si
 * ni el mejor nivel se conoce entero a ese paso: entonces se conoce desde el nivel siguiente. */
function libroDe(venue, compra, venta, compras, ventas, paso) {
  const P = Number(paso);
  const lado = (x) => {
    if (!x) return null;
    if (Array.isArray(x)) return x.length ? { k: kDe(x[0][0], P), q: x.map((p) => Number(p[1])) } : null;
    return x.cantidades && x.cantidades.length ? { k: kDe(x.desde, P), q: x.cantidades.map(Number) } : null;
  };
  const c = lado(compras);
  const v = lado(ventas);
  const kc = c ? c.k : Math.floor(Number(compra) / P + 1e-9);
  const kv = v ? v.k : Math.floor(Number(venta) / P + 1e-9);
  return { venue, compra: String(compra), venta: String(venta), kc, qc: c ? c.q : [], kv, qv: v ? v.q : [],
           lo: c ? kc - c.q.length + 1 : kc + 1, hi: v ? kv + v.q.length - 1 : kv - 1 };
}

/* La cantidad de un libro en el nivel k: [compra, venta], o null si no lo conoce. */
function enNivel(L, k) {
  if (k < L.lo || k > L.hi) return null;
  const c = k > L.kc ? 0 : L.qc[L.kc - k] || 0;
  const v = k < L.kv ? 0 : L.qv[k - L.kv] || 0;
  return [c, v];
}

/* LA FAMILIA en un instante: por nivel k de [lo, hi] (la union de lo que conocen), la suma de los que lo conocen y
 * cuantos son. `libros` = los de los venues con libro en ese instante; N = los venues de la familia. */
function sumaFamilia(libros, N) {
  if (!libros.length) return null;
  const lo = Math.min(...libros.map((L) => L.lo));
  const hi = Math.max(...libros.map((L) => L.hi));
  if (hi < lo) return null;
  const filas = hi - lo + 1;
  const c = new Float64Array(filas);
  const v = new Float64Array(filas);
  const n = new Uint8Array(filas);
  libros.forEach((L) => {
    for (let k = Math.max(lo, L.lo); k <= L.hi; k++) {
      const x = enNivel(L, k);
      c[k - lo] += x[0];
      v[k - lo] += x[1];
      n[k - lo] += 1;
    }
  });
  let mc = null;
  let mv = null;
  libros.forEach((L) => {
    if (mc === null || Number(L.compra) > Number(mc)) mc = L.compra;
    if (mv === null || Number(L.venta) < Number(mv)) mv = L.venta;
  });
  return { lo, hi, c, v, n, N, venues: libros.map((L) => L.venue), mejorCompra: mc, mejorVenta: mv };
}

/* ------------------------------------------------------------------ el mapa: la rejilla de columnas
 * Por instante de la ventana: `foto` (algun venue de la familia tiene foto), `hueco` (ninguno: nadie la escucho, o el
 * libro no era valido) o `pendiente` (la base aun no ha escrito su minuto). Nunca se rellena ni se estira una columna. */
function estadoColumna(t, hayFoto, asOfMs) {
  if (hayFoto) return 'foto';
  return Math.floor(t / 60000) * 60000 + 60000 + LIBRO_ESCRITO_S * 1000 > asOfMs ? 'pendiente' : 'hueco';
}

function columnasDeFotos(d, venues, instantes, asOfMs) {
  const porTs = new Map();
  (d.fotos || []).forEach((f) => {
    if (!venues.includes(f.venue)) return;
    const t = Date.parse(f.ts);
    if (!porTs.has(t)) porTs.set(t, []);
    porTs.get(t).push(f);
  });
  return instantes.map((t) => {
    const fotos = porTs.get(t) || [];
    const libros = fotos.map((f) => libroDe(f.venue, f.compra, f.venta, f.compras, f.ventas, d.paso));
    return { ts: t, estado: estadoColumna(t, fotos.length > 0, asOfMs), origen: 'historia', fotos,
             suma: sumaFamilia(libros, venues.length) };
  });
}

/* Una foto servida como si fuera un aviso del vivo (la escalera de una ventana FIJA es la de su ultima foto). */
function fotoComoAviso(f) {
  return { tipo: 'libro', venue: f.venue, compra: f.compra, venta: f.venta, compras: f.compras, ventas: f.ventas,
           ts_libro_ms: Date.parse(f.ts_libro), foto: f.ts };
}

/* ------------------------------------------------------------------ la escalera
 * Por nivel k, de la venta conocida mas alta a la compra conocida mas baja: compra, venta (null si DESCONOCIDO),
 * cuantos lo conocen, las mejores marcadas y la ACUMULADA desde el medio: la compra desde el nivel de la mejor compra
 * hacia abajo, la venta desde el de la mejor venta hacia arriba. Un nivel que no conocen todos la hace PARCIAL (es un
 * minimo); uno que no conoce ninguno la corta: mas alla no se sabe. En USD, cada nivel vale su cantidad por el precio
 * del CENTRO del nivel (la foto y el relevo no guardan los precios de dentro: el error es como mucho medio paso). */
function enUnidad(q, k, paso, unidad) {
  return unidad === 'usd' ? q * (k + 0.5) * Number(paso) : q;
}

/* ------------------------------------------------------------------ la escala de color del mapa
 * EL PERCENTIL DE LO VISIBLE (P2): el indice de color de una cantidad es su puesto entre las celdas CONOCIDAS con
 * cantidad de las columnas que se ven, floor(256 * (cuantas tienen menos) / cuantas), de 0 a 255; un cero conocido es
 * el fondo (-1). Medido sobre fotos reales de produccion (x1-tmp/c145/p2): ninguna escala fija sirve a la vez a los
 * perpetuos (colas estrechas: el p99 es ~3x la mediana) y a los libros profundos (spot, Coinbase, Deribit: de 29 a
 * 360x); el percentil es la unica que deja ver los muros en todas las ventanas medidas. Cambia al moverse: es de lo
 * que se ve. */
function escalaPercentil(columnas, j0, j1, paso, unidad) {
  const xs = [];
  for (let j = j0; j <= j1; j++) {
    const col = columnas[j];
    const s = col && col.estado === 'foto' ? col.suma : null;
    if (!s) continue;
    for (let i = 0; i < s.n.length; i++) {
      const q = s.n[i] ? enUnidad(s.c[i] + s.v[i], s.lo + i, paso, unidad) : 0;
      if (q > 0) xs.push(q);
    }
  }
  const ord = Float64Array.from(xs).sort();
  const n = ord.length;
  return {
    n,
    indice(q) {
      if (!(q > 0) || !n) return -1;
      let a = 0;
      let b = n;
      while (a < b) {
        const m = (a + b) >> 1;
        if (ord[m] < q) a = m + 1;
        else b = m;
      }
      return Math.min(255, Math.floor((256 * a) / n));
    },
  };
}

function escaleraFamilia(s, paso, unidad) {
  if (!s) return [];
  const P = Number(paso);
  const kb = Math.floor(Number(s.mejorCompra) / P + 1e-9);
  const ka = Math.floor(Number(s.mejorVenta) / P + 1e-9);
  const filas = [];
  for (let k = s.hi; k >= s.lo; k--) {
    const i = k - s.lo;
    filas.push({ k, nivel: nivelTexto(k, paso), compra: s.n[i] ? enUnidad(s.c[i], k, paso, unidad) : null,
                 venta: s.n[i] ? enUnidad(s.v[i], k, paso, unidad) : null, n: s.n[i], N: s.N, mejor_compra: k === kb,
                 mejor_venta: k === ka, acum_compra: null, acum_venta: null, acum_parcial_compra: false,
                 acum_parcial_venta: false });
  }
  const porK = new Map(filas.map((f) => [f.k, f]));
  [['compra', kb, -1], ['venta', ka, 1]].forEach(([lado, k0, dir]) => {
    let acc = 0;
    let parcial = false;
    for (let k = k0; k >= s.lo && k <= s.hi; k += dir) {
      const f = porK.get(k);
      if (!f || !f.n) break;
      acc += f[lado];
      parcial = parcial || f.n < s.N;
      f['acum_' + lado] = acc;
      f['acum_parcial_' + lado] = parcial;
    }
  });
  return filas;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    LIBRO_ACTIVOS, LIBRO_VENUES, LIBRO_PASO, LIBRO_VENTANAS, LIBRO_ESCRITO_S, libroVenues, rotuloFamilia, esMultiplo,
    leeHashLibro, escribeHashLibro, cadaPara, ventanaLibro, kDe, nivelTexto, libroDe, enNivel, sumaFamilia,
    estadoColumna, columnasDeFotos, fotoComoAviso, enUnidad, escalaPercentil, escaleraFamilia,
  };
}
