/* Run the actual asynchronous UI functions without a browser or external packages. */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function node() {
  let content = "";
  const selectors = new Map();
  return {
    children: [], attributes: {},
    hidden: true, dataset: {}, classList: { add() {}, remove() {}, toggle() {} },
    set textContent(value) { content = value; this.children = []; },
    get textContent() { return content + this.children.map(child => child.textContent).join(""); },
    set innerHTML(value) { this.htmlAssigned = true; content = value; this.children = []; },
    get innerHTML() { return content; },
    querySelector(selector) {
      if (!selectors.has(selector)) selectors.set(selector, node());
      return selectors.get(selector);
    },
    querySelectorAll() { return []; },
    setAttribute(name, value) { this.attributes[name] = value; },
    appendChild(child) { this.children.push(child); return child; },
    replaceChildren(...values) { content = ""; this.children = values; },
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
    window: { setTimeout, clearTimeout, matchMedia: () => ({ matches: false, addEventListener() {} }) }, URL,
    finishes: [],
  });
  const source = fs.readFileSync(path.join(__dirname, "../web", filename), "utf8");
  const beforeBoot = filename === "reader.js"
    ? source.slice(0, source.indexOf("  // ---------- boot ----------"))
    : source.slice(0, source.indexOf("  async function boot()"));
  vm.runInContext(beforeBoot + hook + "\n})();", context);
  return { context, nodes, api: context.harness };
}

test("credits stay with the selected edition through delayed navigation", async () => {
  const { nodes, api } = harness("reader.js", `
    globalThis.harness = {
      render, renderCredits,
      setup(loader) {
        manifest = { editions: Object.fromEntries(["first", "second"].map(id => [id, {
          label: id, lang: "grc", credits: { sections: [{ title: "Project", entries: [
            {label: "Responsibility", text: id + " editor", links: []}
          ] }] }
        }])) };
        loadChunk = loader;
        buildToc = () => {};
        currentIndex = () => ({flat: [{}], i: 0});
        updateDiplomaticLink = () => {};
      },
      route(route) { Object.assign(state, route); }
    };
  `);
  const old = deferred();
  const chunk = { chapters: { "1": {html: "Greek", pages: [], noteIds: []} }, notes: {}, apps: {} };
  api.setup(edition => edition === "first" ? old.promise : Promise.resolve(chunk));
  api.route({ edL: "first", edR: "-", book: "1", ch: "1" });
  const pending = api.render();
  const details = nodes.get("#paneL").querySelector(".edition-credits");
  details.open = true;
  api.route({ edL: "second" });
  await api.render();
  assert.equal(details.open, false);
  assert.equal(details.dataset.edition, "second");
  assert.match(details.querySelector(".credits-content").textContent, /second editor/);
  assert.equal(details.querySelector("summary").attributes["aria-label"], "Source and credits for second");
  details.open = true;
  await api.render();
  assert.equal(details.open, true, "chapter rerender keeps the disclosure open");
  old.resolve(chunk);
  await pending;
  assert.equal(details.dataset.edition, "second");
  assert.doesNotMatch(details.querySelector(".credits-content").textContent, /first editor/);
});

test("credit text stays literal and only ordinary web links become anchors", () => {
  const { nodes, api } = harness("reader.js", `globalThis.harness = { renderCredits };`);
  const pane = nodes.get("#paneL");
  api.renderCredits(pane, "test", {label: "Test", credits: {sections: [{
    title: "<img onerror=bad>", entries: [{label: "Author", text: "<script>bad()</script>", links: [
      {text: "<img>", href: "https://example.org/source"},
      {text: "bad", href: "javascript:alert(1)"}, {text: "bad", href: "//example.org"},
      {text: "bad", href: "https://user:password@example.org"}
    ]}]
  }]}});
  const content = pane.querySelector(".edition-credits").querySelector(".credits-content");
  const walk = item => [item, ...item.children.flatMap(walk)];
  const all = walk(content);
  assert.equal(all.some(item => item.htmlAssigned), false);
  assert.match(content.textContent, /<script>bad\(\)<\/script>/);
  const anchors = all.filter(item => item.href);
  assert.equal(anchors.length, 1);
  assert.equal(anchors[0].href, "https://example.org/source");
  assert.equal(anchors[0].rel, "noopener noreferrer");
  api.renderCredits(pane, "missing", {label: "Missing"});
  assert.match(content.textContent, /not recorded/);
});

test("keyboard input within credits never turns the chapter", () => {
  const { context, api } = harness("reader.js", `
    step = direction => globalThis.finishes.push(direction);
    globalThis.harness = { handleKeydown };
  `);
  const inside = { closest: () => ({}), matches: () => false };
  for (const key of ["ArrowLeft", "ArrowRight", "Enter", " ", "Tab"]) {
    api.handleKeydown({key, target: inside});
  }
  assert.equal(context.finishes.length, 0);
  api.handleKeydown({key: "ArrowRight", target: {closest: () => null, matches: () => false}});
  assert.equal(context.finishes[0], 1);
});

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

for (const scenario of [
  { name: "chapter commentary takes precedence", direct: 2, nested: 1, notes: true, sigla: true },
  { name: "nested section commentary is the fallback", direct: 0, nested: 2, notes: true },
  { name: "sigla alone precede commentary", direct: 1, nested: 0, sigla: true },
  { name: "editions without commentary keep notes at the end", direct: 0, nested: 0, notes: true },
  { name: "commentary without notes still gets its rule", direct: 1, nested: 0 },
]) {
  test(`Notes placement: ${scenario.name}`, async () => {
    const { nodes, api } = harness("reader.js", `
      globalThis.harness = {
        renderPane,
        setup(chunk) {
          manifest = { editions: { test: {label: "Test", lang: "deu"} } };
          loadChunk = () => Promise.resolve(chunk);
        }
      };
    `);
    const pane = nodes.get("#paneL"), body = pane.querySelector(".pane-body");
    const endnotes = node(), moves = [], marked = [];
    const commentary = () => ({
      before(value) { moves.push([this, value]); },
      classList: { add(value) { marked.push([this, value]); } },
    });
    const direct = Array.from({ length: scenario.direct }, commentary);
    const nested = Array.from({ length: scenario.nested }, commentary);
    body.querySelectorAll = selector => ({
      ".chapter > .commentary": direct,
      ".chapter .section > .commentary": nested,
    })[selector] || [];
    body.querySelector = selector => selector === ".endnotes" && (scenario.notes || scenario.sigla)
      ? endnotes : null;
    const chapter = {
      html: '<div class="chapter"><p>Translation</p></div>',
      noteIds: scenario.notes ? ["n1"] : [],
      sigla: scenario.sigla ? ['<div class="siglorum">Sigla</div>'] : [],
    };
    api.setup({ chapters: { "5": chapter }, notes: { n1: "Footnote" } });
    await api.renderPane(pane, "test", { book: "1", ch: "5" }, 0);
    const first = direct[0] || nested[0];
    assert.deepEqual(marked, first ? [[first.classList, "commentary-first"]] : []);
    assert.deepEqual(moves, first && (scenario.notes || scenario.sigla) ? [[first, endnotes]] : []);
    const items = scenario.notes ? '<ol><li id="en-n1">Footnote</li></ol>' : "";
    const notesHTML = scenario.notes || scenario.sigla
      ? `<section class="endnotes"><h4>Notes</h4>${chapter.sigla.join("")}${items}</section>` : "";
    assert.equal(body.innerHTML, chapter.html + notesHTML, "note content and IDs are unchanged before the DOM move");
  });
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

test("matter links keep either language and the active pairing", () => {
  const { api } = harness("reader.js", `globalThis.harness = { configureMatter };`);
  const targets = [{route: "1.48", target: "berendes-erratum-target-1"}];
  const link = {dataset: {targets: JSON.stringify(targets)}};
  const body = {querySelectorAll: () => [link]};
  for (const [edL, edR] of [["berendes1902", "berendes1902-eng"], ["berendes1902-eng", "berendes1902"], ["berendes1902-eng", "-"]]) {
    api.configureMatter(body, {}, {edL, edR});
    assert.equal(link.href, `#/${edL}/${edR}/1.48`);
  }
});

test("index filter searches printed and expanded headwords and English, in its own pane", () => {
  const entries = [
    {dataset: {headword: "Bartgras Bartgras beard grass"}},
    {dataset: {headword: "— öl Mandelöl almond oil"}},
    {dataset: {headword: "ἀβρότονον ἀβρότονον"}},
  ];
  let label;
  const body = {
    querySelectorAll(selector) { return selector === "a.matter-link" ? [] : entries; },
    prepend(value) { label = value; },
  };
  // Only the input needs event behavior in this minimal DOM harness.
  let listener;
  const h = harness("reader.js", `globalThis.harness = { configureMatter };`);
  h.context.document.createElement = () => {
    const el = node();
    el.addEventListener = (event, fn) => { listener = fn; };
    return el;
  };
  h.api.configureMatter(body, {kind: "index"}, {edL: "berendes1902-eng", edR: "-"});
  const input = label.children[0];
  input.value = " BEARD GRASS "; listener();
  assert.deepEqual(entries.map(e => e.hidden), [false, true, true]);
  input.value = "Mandelöl"; listener();
  assert.deepEqual(entries.map(e => e.hidden), [true, false, true]);
  input.value = "ἀβρότονον"; listener();
  assert.deepEqual(entries.map(e => e.hidden), [true, true, false]);
  input.value = ""; listener();
  assert.deepEqual(entries.map(e => e.hidden), [false, false, false]);
});

test("front and back section routes round trip through the existing URL parser", () => {
  const { context, api } = harness("reader.js", `
    manifest = {editions: {berendes1902: {}, "berendes1902-eng": {}}};
    globalThis.harness = { parseHash };
  `);
  for (const section of ["front.matter", "back.errata", "back.index"]) {
    context.location = {hash: `#/berendes1902-eng/berendes1902/${section}`};
    const route = api.parseHash();
    assert.equal(route.edL, "berendes1902-eng");
    assert.equal(route.edR, "berendes1902");
    assert.equal(`${route.book}.${route.ch}`, section);
  }
});

test("a page resolved to multiple chapters offers every target in the active pairing", () => {
  const h = harness("reader.js", `
    let menu = "";
    showPopover = (_link, html) => { menu = html; };
    globalThis.harness = { configureMatter, menu: () => menu };
  `);
  h.context.document.createElement = () => {
    const el = node();
    Object.defineProperty(el, "innerHTML", {get() {
      return this.href || this.children.map(child => child.innerHTML).join("\n");
    }});
    return el;
  };
  let click;
  const link = {
    dataset: {targets: JSON.stringify([
      {route: "4.23", target: "berendes-ch-4.23"},
      {route: "4.24", target: "berendes-ch-4.24"},
    ])},
    addEventListener: (_event, fn) => { click = fn; },
  };
  h.api.configureMatter({querySelectorAll: () => [link]}, {},
    {edL: "berendes1902-eng", edR: "berendes1902"});
  let prevented = false;
  let stopped = false;
  click({preventDefault() { prevented = true; }, stopPropagation() { stopped = true; }});
  assert.equal(stopped, true, "the document click handler must not close the target menu");
  assert.equal(prevented, true);
  assert.equal(h.api.menu(), "#/berendes1902-eng/berendes1902/4.23\n#/berendes1902-eng/berendes1902/4.24");
});

test("chapters pair through Wellmann where an edition has concordance rows", () => {
  const { api } = harness("reader.js", `
    globalThis.harness = {
      pairedTargets,
      setup(m) { manifest = m; }
    };
  `);
  const books = (keys) => [{ n: "1", chapters: keys.map(n => ({ n, label: n })) }];
  api.setup({ editions: {
    wellmann1906: { label: "Wellmann", books: [...books(["praef", "42", "43", "68"]), { n: "2", chapters: [{ n: "arg", label: "arg" }] }] },
    berendes1902: { label: "Berendes", books: books(["praef", "42", "43", "68"]) },
    mattioli1554: { label: "Mattioli", books: [...books(["praef", "41", "42", "70", "71"]),
      { n: "2", chapters: [{ n: "praef", label: "praef" }] }], pairing: {
      status: "proposed", to_wellmann: { "1.42": ["1.43"], "1.70": ["1.68"], "1.71": ["1.68"], "2.praef": ["2.arg"] } } },
  } });
  const keys = r => Array.from(r.targets, t => `${t.book}.${t.ch}`).join(" ");
  // Mattioli 1.42 (Rosaceum) is Wellmann 1.43
  assert.equal(keys(api.pairedTargets("wellmann1906", "mattioli1554", { book: "1", ch: "43" })), "1.42");
  assert.equal(keys(api.pairedTargets("mattioli1554", "wellmann1906", { book: "1", ch: "42" })), "1.43");
  // two Mattioli chapters in one Wellmann chapter, also through an edition without rows
  assert.equal(keys(api.pairedTargets("berendes1902", "mattioli1554", { book: "1", ch: "68" })), "1.70 1.71");
  const none = api.pairedTargets("mattioli1554", "wellmann1906", { book: "1", ch: "41" });
  assert.equal(keys(none), "");
  assert.match(none.note, /no Wellmann counterpart/);
  // sections (praef) and editions without rows pair by key; the note says the pairing is proposed
  assert.equal(keys(api.pairedTargets("mattioli1554", "wellmann1906", { book: "1", ch: "praef" })), "1.praef");
  assert.equal(keys(api.pairedTargets("wellmann1906", "berendes1902", { book: "1", ch: "42" })), "1.42");
  assert.match(api.pairedTargets("wellmann1906", "mattioli1554", { book: "1", ch: "68" }).note, /proposed concordance/);
  // a book preface linked to Wellmann's argumentum, both ways
  assert.equal(keys(api.pairedTargets("mattioli1554", "wellmann1906", { book: "2", ch: "praef" })), "2.arg");
  assert.equal(keys(api.pairedTargets("wellmann1906", "mattioli1554", { book: "2", ch: "arg" })), "2.praef");
  // a section the other edition lacks is no counterpart, not a missing chapter
  const front = api.pairedTargets("mattioli1554", "berendes1902", { book: "2", ch: "praef" });
  assert.equal(keys(front), "");
  assert.match(front.note, /\(none\)/);
});
