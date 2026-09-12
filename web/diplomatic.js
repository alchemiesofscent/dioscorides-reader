/* Sprengel 1829 page-level diplomatic reader.
   Data is generated from the canonical page files by
   python -m dioscorides_reader build. */

(function () {
  "use strict";

  const DATA = "data/sprengel1829-diplomatic";
  const DEFAULT_LEAF = "0033";
  const state = { leaf: null, view: "both" };
  let renderGeneration = 0;
  let index = null;
  let pageIndex = new Map();
  const chunkCache = new Map();

  const $ = (selector) => document.querySelector(selector);
  const paper = $("#paper");
  const facsPane = $("#facs");

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  }

  function showMessage(message) {
    const box = $("#message");
    box.textContent = message;
    box.hidden = false;
    window.clearTimeout(showMessage.timer);
    showMessage.timer = window.setTimeout(() => { box.hidden = true; }, 5000);
  }

  async function loadIndex() {
    const response = await fetch(`${DATA}/index.json`);
    if (!response.ok) throw new Error(`diplomatic index: HTTP ${response.status}`);
    index = await response.json();
    pageIndex = new Map(index.pages.map((page, ordinal) => [page.leaf, { ...page, ordinal }]));
  }

  function loadChunk(chunk) {
    if (!chunkCache.has(chunk)) {
      chunkCache.set(chunk, fetch(`${DATA}/pages-${chunk}.json`).then((response) => {
        if (!response.ok) throw new Error(`page chunk ${chunk}: HTTP ${response.status}`);
        return response.json();
      }));
    }
    return chunkCache.get(chunk);
  }

  async function loadPage(leaf) {
    const meta = pageIndex.get(leaf);
    if (!meta) throw new Error(`scan leaf ${leaf} is not in the retained edition`);
    const chunk = await loadChunk(meta.chunk);
    const page = chunk.pages[leaf];
    if (!page) throw new Error(`scan leaf ${leaf} is absent from chunk ${meta.chunk}`);
    return { page, meta };
  }

  function parseHash() {
    const match = location.hash.match(/^#\/(?:sprengel1829\/)?(\d{4})$/);
    return match && pageIndex.has(match[1]) ? match[1] : null;
  }

  function writeHash(leaf) {
    const hash = `#/sprengel1829/${leaf}`;
    if (location.hash !== hash) location.hash = hash;
    else render();
  }

  function selectedStreams(page) {
    if (state.view === "both") return ["grc", "lat"].filter((key) => page.streams[key]);
    return page.streams[state.view] ? [state.view] : [];
  }

  function furnitureFor(page, streams, bottom) {
    const bottomKinds = new Set(["sig", "catchword"]);
    const rows = [];
    for (const stream of streams) {
      for (const item of page.streams[stream].furniture) {
        if (bottomKinds.has(item.kind) === bottom) rows.push(item);
      }
    }
    return rows;
  }

  function appendFurniture(parent, furniture, position) {
    if (!furniture.length) return;
    const wrapper = node("div", `furniture-${position}`);
    for (const item of furniture) {
      const known = ["header", "pageNum", "sig", "catchword"].includes(item.kind);
      wrapper.appendChild(node("div", `fw fw-${known ? item.kind : "other"}`, item.text || "\u00a0"));
    }
    parent.appendChild(wrapper);
  }

  function appendNotes(block, notes) {
    if (!notes.length) return;
    const section = node("div", "notes-block");
    for (const note of notes) {
      const lines = note.lines.length ? note.lines : [""];
      lines.forEach((line, ordinal) => {
        const row = node("div", "note-row");
        let label = "";
        let labelClass = "note-n";
        if (ordinal === 0 && note.n !== "cont") label = note.n;
        if (ordinal === 0 && (note.n === "cont" || note.continues)) {
          label = "continued";
          labelClass += " note-continued";
        }
        row.appendChild(node("span", labelClass, label));
        row.appendChild(node("span", "note-line", line || "\u00a0"));
        section.appendChild(row);
      });
    }
    block.appendChild(section);
  }

  function appendStream(parent, page, stream) {
    const data = page.streams[stream];
    const block = node("section", `stream-block stream-${stream}`);
    block.lang = stream === "grc" ? "grc" : "la";
    let label = stream === "grc" ? "Greek" : "Latin";
    if (page.region === "front" && stream === "lat") label = "Front matter";
    block.appendChild(node("h2", "stream-label", label));
    if (data.continues) {
      block.appendChild(node("div", "page-continues", "continues from preceding scan leaf"));
    }
    const lines = node("div", "stream-lines");
    data.lines.forEach((line, ordinal) => {
      const encoded = data.lineation
        ? data.lineation[ordinal]
        : `${stream === "grc" ? "G" : "L"}${String(ordinal + 1).padStart(2, "0")}`;
      const row = node("div", "diplomatic-line");
      if (encoded) {
        row.id = `line-${page.leaf}-${encoded}`;
        row.dataset.lineId = encoded;
      } else {
        row.classList.add("blank-line");
      }
      const chapterStart = data.chapter_starts && data.chapter_starts[encoded];
      if (chapterStart) {
        row.classList.add(chapterStart.indent === false ? "chapter-praef" : "chapter-start");
        row.dataset.chapter = chapterStart.chapter;
        row.title = `Chapter ${chapterStart.chapter}`;
      }
      row.appendChild(node("span", "line-number", encoded ? String(Number(encoded.slice(1))) : ""));
      row.lastChild.setAttribute("aria-hidden", "true");
      row.appendChild(node("span", "line-text", line || "\u00a0"));
      lines.appendChild(row);
    });
    block.appendChild(lines);
    appendNotes(block, data.notes);
    parent.appendChild(block);
  }

  function renderPaper(page) {
    paper.replaceChildren();
    paper.setAttribute("aria-busy", "false");
    paper.classList.toggle("page-left", page.side === "left");
    paper.classList.toggle("page-right", page.side === "right");
    const streams = selectedStreams(page);
    appendFurniture(paper, furnitureFor(page, streams, false), "top");
    if (!streams.length) {
      const language = state.view === "grc" ? "Greek" : "Latin";
      paper.appendChild(node("p", "paper-empty", `No ${language} stream is present on this leaf.`));
    } else {
      for (const stream of streams) appendStream(paper, page, stream);
    }
    appendFurniture(paper, furnitureFor(page, streams, true), "bottom");
  }

  function updateNavigation(meta) {
    const previous = index.pages[meta.ordinal - 1];
    const next = index.pages[meta.ordinal + 1];
    $("#prev").disabled = !previous;
    $("#next").disabled = !next;
    $("#where").textContent = `printed p. ${meta.printed} · scan leaf ${meta.leaf}`;
    $("#pageTitle").textContent = meta.region === "front"
      ? `Front matter · ${meta.printed}`
      : `Printed page ${meta.printed}`;
    const sideLabel = meta.side === "left" ? "left page · verso" : "right page · recto";
    $("#pageProvenance").textContent = `scan leaf ${meta.leaf} · ${sideLabel} · ${meta.streams.length === 2 ? "Greek and Latin" : "front matter"}`;
    document.title = `Sprengel 1829 · p. ${meta.printed} · leaf ${meta.leaf}`;
  }

  function prefetchNeighbor(meta, delta) {
    const neighbor = index.pages[meta.ordinal + delta];
    if (neighbor) loadChunk(neighbor.chunk).catch(() => {});
  }

  async function render() {
    const generation = ++renderGeneration;
    const leaf = state.leaf;
    const meta = pageIndex.get(leaf);
    if (!meta) return;
    paper.setAttribute("aria-busy", "true");
    try {
      const loaded = await loadPage(leaf);
      if (generation !== renderGeneration || state.leaf !== loaded.meta.leaf) return;
      renderPaper(loaded.page);
      const transcription = $("#transcription");
      transcription.scrollTop = 0;
      transcription.scrollLeft = 0;
      updateNavigation(loaded.meta);
      if (!facsPane.hidden) openFacsimile(loaded.page);
      prefetchNeighbor(loaded.meta, -1);
      prefetchNeighbor(loaded.meta, 1);
    } catch (error) {
      if (generation !== renderGeneration) return;
      paper.setAttribute("aria-busy", "false");
      paper.replaceChildren(node("p", "paper-empty", error.message));
      showMessage(error.message);
    }
  }

  function step(delta) {
    const meta = pageIndex.get(state.leaf);
    if (!meta) return;
    const target = index.pages[meta.ordinal + delta];
    if (target) writeHash(target.leaf);
  }

  function normalizePrinted(value) {
    return value.trim().replace(/^p(?:age)?\.?\s*/i, "").replace(/^\[|\]$/g, "").toLowerCase();
  }

  function resolveJump(value) {
    const query = value.trim();
    if (/^\d{4}$/.test(query) && pageIndex.has(query)) return query;
    const normalized = normalizePrinted(query);
    const matches = index.pages.filter((page) => normalizePrinted(page.printed) === normalized);
    if (matches.length === 1) return matches[0].leaf;
    if (matches.length > 1) {
      showMessage(`Printed page ${query} occurs more than once; enter its four-digit scan leaf.`);
    } else if (/^\d{4}$/.test(query)) {
      showMessage(`Scan leaf ${query} is not retained. Leaves 0630–0631 are excluded duplicate scans.`);
    } else {
      showMessage(`Printed page ${query || "(blank)"} was not found.`);
    }
    return null;
  }

  // ---------- facsimile ----------

  let osd = null;
  let currentFacs = null;
  let currentFacsLeaf = null;
  let facsRetried = false;

  function ensureOsd() {
    if (osd) return osd;
    osd = OpenSeadragon({
      id: "osd",
      prefixUrl: "vendor/openseadragon/images/",
      showNavigator: false,
      maxZoomPixelRatio: 2.5,
      crossOriginPolicy: false,
    });
    osd.addHandler("open-failed", () => {
      if (!facsRetried && currentFacs) {
        facsRetried = true;
        window.setTimeout(() => osd.open(currentFacs.info), 400);
        return;
      }
      $("#facsLabel").textContent = "Scan unavailable; use ‘open image’.";
    });
    return osd;
  }

  function openFacsimile(page) {
    currentFacs = page.facs;
    $("#facsLabel").textContent = `Original scan · leaf ${page.leaf} · printed p. ${page.printed}`;
    $("#facsDirect").href = page.facs.direct;
    if (currentFacsLeaf === page.leaf && osd) return;
    currentFacsLeaf = page.leaf;
    facsRetried = false;
    ensureOsd().open(page.facs.info);
  }

  // ---------- wiring and boot ----------

  function bind() {
    window.addEventListener("hashchange", () => {
      const leaf = parseHash();
      if (!leaf) {
        showMessage("That page address is not in the retained Sprengel edition.");
        writeHash(state.leaf || DEFAULT_LEAF);
        return;
      }
      state.leaf = leaf;
      render();
    });
    $("#prev").addEventListener("click", () => step(-1));
    $("#next").addEventListener("click", () => step(1));
    $("#jumpForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const leaf = resolveJump($("#jump").value);
      if (leaf) {
        $("#jump").value = "";
        writeHash(leaf);
      }
    });
    $("#streamView").addEventListener("change", (event) => {
      state.view = event.target.value;
      try { localStorage.setItem("sprengel-diplomatic-stream", state.view); } catch (_error) {}
      render();
    });
    $("#toggleFacs").addEventListener("click", (event) => {
      facsPane.hidden = !facsPane.hidden;
      event.currentTarget.classList.toggle("active", !facsPane.hidden);
      if (!facsPane.hidden) render();
    });
    document.addEventListener("keydown", (event) => {
      if (event.target.matches("input, select, textarea")) return;
      if (event.key === "ArrowLeft") step(-1);
      if (event.key === "ArrowRight") step(1);
    });
  }

  async function boot() {
    try {
      await loadIndex();
    } catch (error) {
      document.body.innerHTML = `<div class="boot-error"><h2>Diplomatic pages are not reachable</h2><p>Open the completed reader preview. If the problem persists, rebuild the preview from its selected corpus export using the project README.</p></div>`;
      return;
    }
    try {
      const saved = localStorage.getItem("sprengel-diplomatic-stream");
      if (["both", "grc", "lat"].includes(saved)) state.view = saved;
    } catch (_error) {}
    $("#streamView").value = state.view;
    const chapter = new URLSearchParams(location.search).get("chapter");
    if (/^\d+\.[^/]+$/.test(chapter || "")) {
      $("#chapterLink").href = `reader.html#/sprengel1829-grc/sprengel1829-lat/${chapter}`;
    }
    bind();
    const routedLeaf = parseHash();
    state.leaf = routedLeaf || DEFAULT_LEAF;
    if (routedLeaf && location.hash === `#/sprengel1829/${routedLeaf}`) render();
    else writeHash(state.leaf);
  }

  boot();
})();
