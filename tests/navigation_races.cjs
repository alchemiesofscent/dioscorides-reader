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
    window: { setTimeout, clearTimeout }, URL,
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
