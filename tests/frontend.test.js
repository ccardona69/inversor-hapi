// Prueba de humo del frontend: ejecuta static/app.js con un DOM mínimo
// (sin dependencias) y comprueba que cada vista pinta su contenido.
// Corre con: node --test tests/frontend.test.js
"use strict";

const { test } = require("node:test");
const assert = require("node:assert");

class El {
  constructor(id = "") {
    this.id = id;
    this._html = "";
    this._text = "";
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.children = [];
    this.disabled = false;
    this.value = "";
    this.open = false;
    this.classList = {
      _set: new Set(),
      add: (...cs) => cs.forEach(c => this.classList._set.add(c)),
      remove: (...cs) => cs.forEach(c => this.classList._set.delete(c)),
      toggle: (c, force) => {
        const on = force === undefined ? !this.classList._set.has(c) : !!force;
        on ? this.classList._set.add(c) : this.classList._set.delete(c);
        return on;
      },
      contains: c => this.classList._set.has(c),
    };
  }
  set innerHTML(v) { this._html = String(v); }
  get innerHTML() { return this._html; }
  set textContent(v) { this._text = String(v); }
  get textContent() { return this._text; }
  querySelector() { return new El(); }
  querySelectorAll() { return []; }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k]; }
  removeAttribute(k) { delete this.attributes[k]; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren() { this.children = []; }
  contains() { return false; }
  closest() { return null; }
  focus() {}
  scrollTo() {}
  scrollIntoView() {}
  click() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
  addEventListener() {}
  getBoundingClientRect() { return { left: 0, right: 0, top: 0, bottom: 0 }; }
}

const elements = {};
const windowHandlers = {};

global.window = {
  addEventListener: (ev, fn) => { windowHandlers[ev] = fn; },
  scrollTo: () => {},
};
global.document = {
  getElementById: id => (elements[id] = elements[id] || new El(id)),
  querySelector: () => new El(),
  querySelectorAll: () => [],
  createElement: () => new El(),
  addEventListener: () => {},
  documentElement: new El("html"),
  body: new El("body"),
  activeElement: null,
  title: "",
};
global.location = { hash: "", search: "", protocol: "http:", href: "http://localhost/" };
global.matchMedia = () => ({ matches: false, addEventListener: () => {} });
global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
global.fetch = () => Promise.reject(new Error("offline"));

require("../static/app.js");

test("las ocho vistas pintan su contenido en modo demo", async () => {
  // Espera a que loadServerData() resuelva (fetch rechazado => modo demo).
  await new Promise(r => setTimeout(r, 25));
  const main = document.getElementById("main-content");

  const cases = [
    ["#resumen", "Tu marcador"],
    ["#cartera", "Sincronización"],
    ["#analisis", "Pongamos los números"],
    ["#explorar", "Busca por ticker"],
    ["#asistente", "Luna"],
    ["#movimientos", "Registrar un movimiento"],
    ["#diario", "Escribe antes de actuar"],
    ["#ajustes", "Perfil de inversión"],
  ];
  for (const [hash, marker] of cases) {
    location.hash = hash;
    windowHandlers.hashchange();
    assert.ok(
      main.innerHTML.includes(marker),
      `${hash} debería contener «${marker}»`,
    );
  }
});

test("el resumen muestra importes con formato de moneda", async () => {
  location.hash = "#resumen";
  windowHandlers.hashchange();
  const html = document.getElementById("main-content").innerHTML;
  assert.match(html, /\$\d/);
});
