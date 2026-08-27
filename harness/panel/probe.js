// SONDA DEL PANEL · el instrumento de K31.
//
// Contesta dos preguntas EJECUTANDO el panel, no leyendolo:
//   ESLABON 5  ¿que rutas pide el panel cuando un operador abre las ocho secciones?
//   ESLABON 6  ¿la cifra que trae esa ruta LLEGA A LA PANTALLA?
//
// El eslabon 6 se mide POR MUTACION: se cambia el valor en el payload y se vuelve a
// pintar. Si el DOM no se mueve, ese payload no llega a la pantalla. No se pregunta si
// app.js "menciona" el campo: eso es texto, y K44 enseño que un criterio de texto se
// cumple borrando un comentario.
//
// LO QUE ESTA SONDA NO PUEDE DECIR, y va declarado en la salida:
//   · jsdom no maqueta. Prueba que el valor se ESCRIBE en el DOM de su seccion, no que
//     el pixel sea visible. Un display:none se le escapa.
//   · lo que se dibuja en CANVAS (las series de lightweight-charts) queda fuera: el
//     motor de graficos se sustituye por un doble. Esas rutas se declaran aparte.
const fs = require('fs');
const path = require('path');
const { render, fixtureName } = require('./render');

const FIX = process.env.K31_FIXTURES || fs.mkdtempSync('/tmp/k31-');
const FROZEN = 1756300000000;   // reloj congelado: ver render.js
const norm = t => t.replace(/\s+/g, ' ').trim();
const SETTLE_CAPTURA = parseInt(process.env.K31_SETTLE || '6000', 10);

async function conducir(transform, mode, settle) {
  const r = await render({ mode, fixtures: FIX, settleMs: settle, frozenAt: FROZEN, transform });
  const enlaces = [...r.document.querySelectorAll('.section-links a')];
  for (const l of enlaces) {
    l.dispatchEvent(new r.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise(res => setTimeout(res, settle));
  }
  r.texto = norm(r.document.body.textContent);
  r.secciones = enlaces.length;
  return r;
}

// Mutacion que PRESERVA EL TIPO y RELLENA LOS NULOS.
//   preservar el tipo: si rompiera el JSON, la seccion fallaria entera y todos los
//   campos pareceria que llegan a la pantalla -la tautologia inversa-.
//   rellenar los nulos: un campo nulo no se puede "mover", y sin rellenarlo un payload
//   que el panel SI pinta -pero que hoy viene vacio- saldria como no cableado. Medido:
//   /api/structure-detail trae los horizontes 3d/1d en null, pinta "Sin nivel
//   estructural" y al rellenarlo pasa a "Tesis invalida al perder $4.24K en 3D". El
//   cable esta bien; lo que falta es el dato. Son cosas distintas y el check no puede
//   confundirlas.
function mutar(o, prof = 0) {
  if (prof > 7) return o;
  if (Array.isArray(o)) { o.forEach(x => mutar(x, prof + 1)); return o; }
  if (o && typeof o === 'object') {
    for (const k of Object.keys(o)) {
      const v = o[k];
      if (v === null) o[k] = /pct|ratio|level|price|close|high|low|score|count|delta|value|bps/i.test(k) ? 4242.42 : 'ZZMUTZZ';
      else if (typeof v === 'number') o[k] = v === 0 ? 12345.678 : (v > 0 ? v * 3 + 7.77 : v * 3 - 7.77);
      else if (typeof v === 'string') o[k] = v === '' ? 'ZZMUTZZ' : ('ZZ' + v).slice(0, 40);
      else if (typeof v === 'boolean') o[k] = !v;
      else mutar(v, prof + 1);
    }
  }
  return o;
}

// UNA EXCEPCION TIENE QUE SALIR COMO JSON, NO COMO STDOUT VACIO. Medido: leyendo un
// static/index.html sin permiso la sonda moria con EACCES, stdout quedaba vacio y el
// check publicaba "la sonda no devolvio nada", que no dice NADA de la causa. Un
// instrumento que no puede explicar por que no midio obliga a adivinar, y adivinar es
// lo que este proyecto no puede permitirse.
function morir(e) {
  const msg = e && e.message ? e.message : String(e);
  console.log(JSON.stringify({ error: msg.slice(0, 300) }, null, 1));
  process.exit(0);
}
process.on('uncaughtException', morir);
process.on('unhandledRejection', morir);

(async () => {
  const t0 = Date.now();
  fs.mkdirSync(FIX, { recursive: true });
  const yaHabia = fs.existsSync(path.join(FIX, '_urls.json'));

  // 1 · CAPTURA: el propio panel decide que pide; cada respuesta se guarda en disco.
  const cap = await conducir(null, yaHabia ? 'replay' : 'capture', yaHabia ? 400 : SETTLE_CAPTURA);
  const urls = [...new Set(cap.requested)];
  fs.writeFileSync(path.join(FIX, '_urls.json'), JSON.stringify(urls, null, 1));
  const noOk = urls.filter(u => cap.status[u] && cap.status[u] !== 200);
  const pedidas = [...new Set(urls.map(u => u.split('?')[0]))].sort();

  const salida = {
    fixtures: FIX,
    capturado_en: new Date().toISOString(),
    secciones: cap.secciones,
    fatal: cap.fatal,
    errores: cap.errores ? cap.errores.length : (cap.errors || []).length,
    urls: urls.length,
    rutas_pedidas: pedidas,
    no_200: noOk.map(u => ({ url: u, codigo: cap.status[u] })),
    texto_dom: cap.texto.length,
  };
  if (cap.fatal) { salida.error = 'el panel no arranca: ' + cap.fatal; console.log(JSON.stringify(salida, null, 1)); process.exit(0); }

  // SIN PAYLOADS NO HAY MEDICION, Y ESO ES NO MEDIDO, NO UN ROJO. Si no se pudo traer ni
  // uno -sin credenciales, sin red, o produccion caida- el panel NO se queda mudo: los
  // maybe() caen a sus fallbacks y las secciones siguen pidiendo. MEDIDO induciendolo
  // con un netrc inexistente: 29 rutas pedidas y CERO payloads con datos. O sea que sin
  // esta guardia el check publicaria "37 de 66 no llegan a la pantalla", un rojo
  // inventado a partir de un canal roto, que es la familia de K63: el estado del
  // INSTRUMENTO disfrazado de veredicto sobre el SUJETO.
  const conDatos = urls.filter(u => fs.existsSync(path.join(FIX, fixtureName(u)))).length;
  salida.payloads_con_datos = conDatos;
  if (conDatos === 0) {
    const codigos = [...new Set(noOk.map(u => cap.status[u]).filter(Boolean))];
    salida.error = 'no se pudo traer NI UN payload de produccion (' + urls.length +
      ' rutas pedidas): ' + (codigos.length ? 'codigos ' + codigos.join(',') : 'sin respuesta');
    console.log(JSON.stringify(salida, null, 1)); process.exit(0);
  }

  // 2 · CONTROL: dos renders sin mutar deben ser IDENTICOS. Si no lo son, el
  // instrumento es inestable y cualquier veredicto por mutacion seria ruido.
  const base = await conducir(null, 'replay', 300);
  const ctrl = await conducir(null, 'replay', 300);
  salida.control_determinista = base.texto === ctrl.texto;
  salida.texto_dom = base.texto.length;
  if (!salida.control_determinista) { console.log(JSON.stringify(salida, null, 1)); process.exit(0); }

  // 3 · ESLABON 6, por mutacion, payload a payload.
  const mudas = [], vivas = [];
  for (const u of urls) {
    const p = u.split('?')[0];
    const f = path.join(FIX, fixtureName(u));
    if (!fs.existsSync(f)) continue;
    let crudo; try { crudo = fs.readFileSync(f, 'utf8'); JSON.parse(crudo); } catch (e) { continue; }
    const t = (url, body) => (url.split('?')[0] === p ? JSON.stringify(mutar(JSON.parse(body))) : body);
    const r = await conducir(t, 'replay', 300);
    (r.texto !== base.texto ? vivas : mudas).push(p);
  }
  salida.payloads_probados = vivas.length + mudas.length;
  salida.llegan_a_la_pantalla = [...new Set(vivas)].sort();
  salida.no_llegan = [...new Set(mudas)].sort();
  salida.segundos = Math.round((Date.now() - t0) / 1000);
  console.log(JSON.stringify(salida, null, 1));
  process.exit(0);
})();
