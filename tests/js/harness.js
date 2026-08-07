'use strict';
// Arnes minimo para ejecutar static/app.js dentro de Node.
//
// app.js es un script de navegador sin exports: se evalua en un contexto `vm` con un DOM
// suficiente para que el fichero cargue (su unica llamada al DOM en el nivel superior es
// `document.addEventListener('DOMContentLoaded', boot)`), y a partir de ahi las funciones
// quedan disponibles como propiedades del global del contexto.
//
// Deliberadamente NO se comprueban cadenas dentro del fichero: se llaman las funciones de
// verdad y se comprueba lo que devuelven.

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const RAIZ = path.join(__dirname, '..', '..');
const APP_JS = path.join(RAIZ, 'static', 'app.js');
const INDEX_HTML = path.join(RAIZ, 'static', 'index.html');

class ClassList {
  constructor(node) { this.node = node; this.set = new Set(); }
  add(...names) { names.forEach(n => this.set.add(n)); }
  remove(...names) { names.forEach(n => this.set.delete(n)); }
  contains(name) { return this.set.has(name); }
  toggle(name, force) {
    const on = force === undefined ? !this.set.has(name) : Boolean(force);
    if (on) this.set.add(name); else this.set.delete(name);
    return on;
  }
  get value() { return [...this.set].join(' '); }
}

class Node {
  constructor(tag) {
    this.tagName = String(tag || 'div').toUpperCase();
    this.children = [];
    this.attributes = {};
    this.classList = new ClassList(this);
    this.style = {};
    this.dataset = {};
    this.hidden = false;
    this.id = '';
    this._text = '';
    this.listeners = {};
  }
  get className() { return this.classList.value; }
  set className(value) {
    this.classList.set = new Set(String(value || '').split(/\s+/).filter(Boolean));
  }
  get textContent() {
    return this.children.length ? this.children.map(c => c.textContent).join('') : this._text;
  }
  set textContent(value) { this._text = String(value === undefined ? '' : value); this.children = []; }
  append(...nodes) {
    for (const n of nodes) this.children.push(typeof n === 'string' ? Object.assign(new Node('span'), { _text: n }) : n);
  }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === 'class') this.className = value;
    if (name === 'id') this.id = String(value);
  }
  getAttribute(name) { return Object.hasOwn(this.attributes, name) ? this.attributes[name] : null; }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  dispatch(type, event) { for (const fn of this.listeners[type] || []) fn(event); }
  closest() { return null; }
  /** Todos los descendientes, incluido este nodo. */
  walk(out = []) { out.push(this); for (const c of this.children) if (c.walk) c.walk(out); return out; }
}

/** Lee del HTML real la navegacion y las secciones conmutables.
 *
 * Las "secciones" del dashboard son EXACTAMENTE los destinos de `.section-links`: eso es lo
 * que `initSectionNav()` conmuta. El documento tiene otros `<section id=...>` anidados
 * (summary, analyzer-*) que no son pestanas; contarlos daria una lista que no corresponde a
 * la navegacion.
 */
function leerIndexHtml() {
  const html = fs.readFileSync(INDEX_HTML, 'utf8');
  const bloque = html.match(/<nav[^>]*class="[^"]*section-links[^"]*"[\s\S]*?<\/nav>/);
  const navLinks = bloque
    ? [...bloque[0].matchAll(/href="#([^"]+)"/g)].map(m => `#${m[1]}`)
    : [];
  const sectionIds = navLinks.map(hash => hash.slice(1));
  const todosLosIds = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]));
  return { html, sectionIds, navLinks, todosLosIds };
}

/** Documento de mentira poblado con las secciones y enlaces del index.html real. */
function crearDocumento() {
  const { sectionIds, navLinks } = leerIndexHtml();
  const porId = new Map();
  const secciones = sectionIds.map((id) => {
    const node = new Node('section');
    node.id = id;
    porId.set(id, node);
    return node;
  });
  const enlaces = navLinks.map((hash) => {
    const node = new Node('a');
    node.hash = hash;
    node.href = hash;
    node.className = 'section-link';
    return node;
  });
  const document = {
    listeners: {},
    getElementById: (id) => porId.get(id) || null,
    querySelector: () => null,
    querySelectorAll: (selector) => (selector === '.section-links a' ? enlaces : []),
    createElement: (tag) => new Node(tag),
    createElementNS: (_ns, tag) => new Node(tag),
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    body: new Node('body'),
  };
  return { document, secciones, enlaces, porId, sectionIds, navLinks };
}

/** Evalua static/app.js en un contexto aislado y devuelve ese contexto. */
function cargarApp(extras = {}) {
  const dom = crearDocumento();
  const contexto = {
    console,
    document: dom.document,
    location: { hash: '', pathname: '/' },
    history: { pushState() {}, replaceState() {} },
    navigator: { userAgent: 'node' },
    fetch: async () => { throw new Error('sin red en las pruebas'); },
    setTimeout, clearTimeout, setInterval, clearInterval,
    requestAnimationFrame: (fn) => fn(),
    EventSource: function EventSource() { this.close = () => {}; this.addEventListener = () => {}; },
    LightweightCharts: { createChart: () => ({}) },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    ...extras,
  };
  contexto.window = contexto;
  contexto.__hook = {};
  contexto.window.addEventListener = (type, fn) => {
    (contexto.__winListeners[type] = contexto.__winListeners[type] || []).push(fn);
  };
  contexto.__winListeners = {};
  contexto.window.scrollTo = () => {};
  vm.createContext(contexto);
  // Las declaraciones `function` de nivel superior si quedan como propiedades del global,
  // pero `const`/`let` viven en el ambito lexico del script y no serian accesibles desde
  // fuera. El epilogo se evalua DENTRO de ese mismo ambito y las publica.
  const fuente = fs.readFileSync(APP_JS, 'utf8');
  const epilogo = '\n;__hook.state = state; __hook.COLORS = COLORS;'
    + ' __hook.FALLBACK_SECTION = FALLBACK_SECTION; __hook.MAX_SEGMENTS = MAX_SEGMENTS;'
    + ' __hook.EXEC_CLASS = EXEC_CLASS; __hook.FLOW_QUADRANTS = FLOW_QUADRANTS;\n';
  vm.runInContext(fuente + epilogo, contexto, { filename: 'app.js' });
  Object.assign(contexto, contexto.__hook);
  contexto.__dom = dom;
  return contexto;
}

module.exports = { cargarApp, crearDocumento, leerIndexHtml, Node, APP_JS, INDEX_HTML, RAIZ };
