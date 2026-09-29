'use strict';
// Arnes para ejecutar LA MESA dentro de Node. Hermano de `harness.js`, que hace lo mismo con
// el panel viejo.
//
// POR QUE UNO APARTE Y NO UN PARAMETRO DE `harness.js`: son dos pantallas distintas con dos
// DOM distintos, y lo que hace util a estos tests es que el sujeto este NOMBRADO. `harness.js`
// descubre `static/index.html`; este descubre `static/mesa.html`, y lo dice en su propio
// nombre. Un arnes que sirve para las dos y no dice cual cargo es la forma mas barata de
// medir el panel equivocado durante semanas.
//
// La lista de ficheros NO se escribe aqui: la descubre `harness/bin/panel-fuentes --html
// mesa.html` del <script> del HTML, igual que para el panel viejo. Si la mesa se parte en mas
// modulos manana, estos tests siguen midiendo la mesa entera sin tocar una linea.
//
// Deliberadamente NO se comprueban cadenas dentro de los ficheros: se llaman las funciones de
// verdad y se comprueba lo que devuelven.

const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');

const RAIZ = path.join(__dirname, '..', '..');

let _fuente = null;
function fuenteMesa() {
  if (_fuente !== null) return _fuente;
  const py = process.env.VENV_PY || path.join(RAIZ, '.venv', 'bin', 'python');
  try {
    _fuente = execFileSync(
      py,
      [path.join(RAIZ, 'harness', 'bin', 'panel-fuentes'), '--repo', RAIZ,
       '--html', 'mesa.html', '--cat'],
      { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }
    );
  } catch (e) {
    // SIN SUJETO NO SE INVENTA UNO: que reviente y que los tests fallen, no que pasen sobre
    // una mesa vacia.
    throw new Error(
      'no se pudieron descubrir las fuentes de la mesa: '
      + (e.stderr || e.message || '').toString().slice(0, 300)
    );
  }
  return _fuente;
}

// ------------------------------------------------------------------ DOM minimo
// Lo justo para que los ficheros carguen y para que las funciones que construyen nodos se
// puedan llamar de verdad. No pretende ser un navegador: lo que necesita maqueta -si DECIDE
// cabe en el pliegue- se mide con Chromium en K102, no aqui.

class ClassList {
  constructor() { this.set = new Set(); }
  add(...n) { n.forEach((x) => x && this.set.add(x)); }
  remove(...n) { n.forEach((x) => this.set.delete(x)); }
  contains(n) { return this.set.has(n); }
  toggle(n, force) {
    const on = force === undefined ? !this.set.has(n) : Boolean(force);
    if (on) this.set.add(n); else this.set.delete(n);
    return on;
  }
  get value() { return [...this.set].join(' '); }
}

class Node {
  constructor(tag) {
    this.tagName = String(tag || 'div').toUpperCase();
    this.children = [];
    this.attributes = {};
    this.style = {};
    this._texto = '';
    this.classList = new ClassList();
  }
  get className() { return this.classList.value; }
  set className(v) {
    this.classList = new ClassList();
    String(v || '').split(/\s+/).forEach((x) => x && this.classList.add(x));
  }
  appendChild(n) { this.children.push(n); n.parentNode = this; return n; }
  removeChild(n) {
    const i = this.children.indexOf(n);
    if (i >= 0) this.children.splice(i, 1);
    return n;
  }
  get firstChild() { return this.children[0] || null; }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null; }
  removeAttribute(k) { delete this.attributes[k]; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k); }
  get dataset() {
    const d = {};
    Object.keys(this.attributes).forEach((k) => {
      if (k.startsWith('data-')) {
        d[k.slice(5).replace(/-([a-z])/g, (m, c) => c.toUpperCase())] = this.attributes[k];
      }
    });
    return d;
  }
  set textContent(v) { this._texto = v === null || v === undefined ? '' : String(v); this.children = []; }
  get textContent() {
    return this._texto + this.children.map((c) => c.textContent).join('');
  }
  addEventListener() {}
  // Suficiente para los selectores que la mesa usa de verdad.
  matches(sel) {
    if (sel.startsWith('[') && sel.endsWith(']')) return this.hasAttribute(sel.slice(1, -1));
    return false;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  querySelectorAll(sel) {
    const soloHijos = sel.startsWith(':scope > ');
    const s = soloHijos ? sel.slice(':scope > '.length) : sel;
    const casa = (n) => {
      if (s.startsWith('[') && s.endsWith(']')) return n.hasAttribute(s.slice(1, -1));
      if (s.startsWith('.')) return n.classList.contains(s.slice(1));
      return n.tagName === s.toUpperCase();
    };
    const fuera = [];
    const anda = (n, prof) => {
      n.children.forEach((c) => {
        if (casa(c)) fuera.push(c);
        if (!soloHijos) anda(c, prof + 1);
      });
    };
    anda(this, 0);
    return fuera;
  }
}

function nuevoDocumento(ids) {
  const cuerpo = new Node('body');
  const porId = {};
  (ids || []).forEach((id) => {
    const n = new Node('div');
    n.setAttribute('id', id);
    porId[id] = n;
    cuerpo.appendChild(n);
  });
  return {
    body: cuerpo,
    createElement: (t) => new Node(t),
    createTextNode: (t) => {
      const n = new Node('#text');
      n.textContent = t;
      return n;
    },
    getElementById: (id) => porId[id] || null,
    querySelector: (s) => cuerpo.querySelector(s),
    querySelectorAll: (s) => cuerpo.querySelectorAll(s),
    addEventListener: () => {},
    _porId: porId,
  };
}

// Los ids que la mesa toca. Se declaran aqui para que un test que pida uno inexistente falle
// en vez de recibir null y pasar por casualidad.
const IDS = [
  'decide', 'decide-sesgo', 'decide-motivo', 'decide-campos', 'decide-edad',
  'conf-escalones', 'conf-palabra', 'conf-clave', 'dc-relleno', 'dc-valor', 'dc-clave',
  'reloj', 'tira', 'scan', 'matriz', 'matriz-pie', 'matriz-venue', 'inspect', 'research',
  'follow', 'learn', 'pie-servicios', 'sel-marco', 'sel-activo', 'ir-estado', 'volver',
  'vista-mesa', 'vista-estado', 'estado-resumen', 'estado-procesos', 'estado-feeds',
  'estado-declaraciones',
];

function cargaMesa() {
  const documento = nuevoDocumento(IDS);
  // los tres escalones de la barra de confianza
  for (let i = 0; i < 3; i += 1) {
    documento.getElementById('conf-escalones').appendChild(new Node('span'));
  }
  const ventana = {
    location: { hash: '', origin: 'http://mesa.local' },
    performance: { now: () => 0, mark: () => {} },
    addEventListener: () => {},
    setTimeout: (f) => f(),
    URL,
  };
  ventana.window = ventana;
  const ctx = {
    window: ventana,
    document: documento,
    URL,
    console,
    Date,
    Math,
    Number,
    JSON,
    Array,
    Object,
    String,
    isNaN,
    setTimeout: (f) => f(),
    fetch: () => Promise.reject(new Error('en los tests no se pide red')),
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(fuenteMesa(), ctx, { filename: 'mesa.concatenada.js' });

  // DOS TRAMPAS DEL ARNES QUE COSTARON SEIS TESTS EN ROJO, Y NINGUNA ERA DEL SUJETO:
  //
  // 1 · UN `const` DE PRIMER NIVEL NO ES UNA PROPIEDAD DEL GLOBAL. En un script de `vm`, solo
  //     `var` y las DECLARACIONES DE FUNCION acaban en el objeto global del contexto. Por eso
  //     `ctx.simbolo` existe y `ctx.MARCOS` sale `undefined` aunque las dos esten declaradas
  //     al mismo nivel. Leer una constante NO es `ctx.X`: es evaluarla en el contexto.
  //     Si un test hubiera escrito `assert.ok(!ctx.MARCOS_MALOS)` habria pasado por esto y
  //     no por el sujeto: un `undefined` que parece un aprobado.
  //
  // 2 · UN OBJETO CREADO DENTRO DEL `vm` NO CASA CON `deepStrictEqual` CONTRA UN LITERAL DE
  //     AQUI. Cada contexto tiene sus propias intrinsecas, asi que el `{}` de dentro lleva
  //     OTRO `Object.prototype` y `deepStrictEqual` -que compara prototipos- lo rechaza con
  //     los mismos valores delante. `aqui()` lo trae al realm de los tests.
  const evalua = (expr) => vm.runInContext(expr, ctx);
  const aqui = (v) => JSON.parse(JSON.stringify(v));

  return { ctx, documento, ventana, evalua, aqui };
}

module.exports = { cargaMesa, nuevoDocumento, Node, IDS };
