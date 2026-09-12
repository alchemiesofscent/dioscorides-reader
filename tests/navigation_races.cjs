/* Run the actual asynchronous UI functions without a browser or external packages. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function node() {
  let content = "";
  const children = new Map();
  return {
    hidden: true, dataset: {}, classList: { add() {}, remove() {}, toggle() {} },
    set textContent(value) { content = value; }, get textContent() { return content; },
    set innerHTML(value) { content = value; }, get innerHTML() { return content; },
    querySelector(selector) {
      if (!children.has(selector)) children.set(selector, node());
      return children.get(selector);
    },
    querySelectorAll() { return []; },
    setAttribute() {}, replaceChildren(...values) { content = values.map(value => value.textContent).join(""); },
  };
}

function harness(filename, hook) {
  const nodes = new Map();
  const context = vm.createContext({
    document: {
      querySelector(selector) {
        if (!nodes.has(selector)) nodes.set(selector, node());
        return nodes.get(selector);
      },
      createElement() { return node(); },
    },
    window: { setTimeout, clearTimeout },
    finishes: [],
  });
  const source = fs.readFileSync(path.join(__dirname, "../web", filename), "utf8");
  const beforeBoot = filename === "reader.js"
    ? source.slice(0, source.indexOf("  // ---------- boot ----------"))
    : source.slice(0, source.indexOf("  async function boot()"));
  vm.runInContext(beforeBoot + hook + "\n})();", context);
  return { context, nodes, api: context.harness };
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

for (const failure of [false, true]) {
  test(`chapter reader discards stale ${failure ? "failure" : "success"} and final navigation update`, async () => {
    const { context, nodes, api } = harness("reader.js", `
      globalThis.harness = {
        render,
        setup(loader) {
          manifest = { editions: { test: {label: "Test", lang: "eng", status: "accepted"} } };
          loadChunk = loader;
          buildToc = () => {};
          currentIndex = () => ({flat: [{}], i: 0});
          updateDiplomaticLink = () => globalThis.finishes.push(state.book);
        },
        route(route) { Object.assign(state, route); }
      };
    `);
    const old = deferred();
    const chapter = html => ({ html, pages: [], noteIds: [] });
    api.setup((_edition, book) => book === "1" ? old.promise : Promise.resolve({
      chapters: { "2": chapter("BOOK TWO CHAPTER TWO") }, notes: {}, apps: {},
    }));
    api.route({ edL: "test", edR: "-", book: "1", ch: "1" });
    const pending = api.render();
    api.route({ book: "2", ch: "2" });
    await api.render();
    const pane = nodes.get("#paneL");
    assert.equal(pane.querySelector(".pane-body").innerHTML, "BOOK TWO CHAPTER TWO");
    if (failure) old.reject(new Error("old fetch failed"));
    else old.resolve({ chapters: { "1": chapter("OLD ONE"), "2": chapter("OLD TWO") }, notes: {}, apps: {} });
    await pending;
    assert.equal(pane.querySelector(".pane-head").textContent, "Test · 2.2 · accepted");
    assert.equal(pane.querySelector(".pane-body").innerHTML, "BOOK TWO CHAPTER TWO");
    assert.equal(pane._chapter.html, "BOOK TWO CHAPTER TWO");
    assert.equal(context.finishes.length, 1);
  });

  test(`diplomatic reader discards stale ${failure ? "failure" : "success"}`, async () => {
    const { context, nodes, api } = harness("diplomatic.js", `
      globalThis.harness = {
        render,
        setup(loader) {
          pageIndex = new Map([["0033", {}], ["0034", {}]]);
          loadPage = loader;
          renderPaper = page => { paper.textContent = page.text; };
          updateNavigation = meta => globalThis.finishes.push(meta.leaf);
          prefetchNeighbor = () => {};
          showMessage = message => globalThis.finishes.push(message);
        },
        route(leaf) { state.leaf = leaf; }
      };
    `);
    const old = deferred();
    api.setup(leaf => leaf === "0033" ? old.promise : Promise.resolve({
      meta: { leaf: "0034" }, page: { text: "NEW PAGE" },
    }));
    api.route("0033");
    const pending = api.render();
    api.route("0034");
    await api.render();
    if (failure) old.reject(new Error("old page failure"));
    else old.resolve({ meta: { leaf: "0033" }, page: { text: "OLD PAGE" } });
    await pending;
    assert.equal(nodes.get("#paper").textContent, "NEW PAGE");
    assert.equal(context.finishes.length, 1);
  });
}
