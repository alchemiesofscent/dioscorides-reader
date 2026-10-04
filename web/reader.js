/* Dioscorides parallel reader.
   Data: data/manifest.json + data/{edition}/book-{n}.json
   (built by python -m dioscorides_reader build). Serve the repo root with
   `python -m dioscorides_reader serve --directory dist`; open /reader.html. */

(function () {
  "use strict";

  const DATA = "data";
  const NONE = "-";
  const state = { edL: null, edR: null, book: null, ch: null };
  let renderGeneration = 0;
  let manifest = null;
  const chunkCache = new Map(); // "edition/book" -> Promise<chunk>

  const $ = (sel) => document.querySelector(sel);
  const paneL = $("#paneL"), paneR = $("#paneR");
  const pickL = $("#pickL"), pickR = $("#pickR");
  const toc = $("#toc"), popover = $("#popover");

  // ---------- data ----------

  async function loadManifest() {
    const res = await fetch(`${DATA}/manifest.json`);
    if (!res.ok) throw new Error(`manifest.json: HTTP ${res.status}`);
    manifest = await res.json();
  }

  function loadChunk(edition, book) {
    const key = `${edition}/${book}`;
    if (!chunkCache.has(key)) {
      chunkCache.set(key, fetch(`${DATA}/${edition}/book-${book}.json`).then((r) => {
        if (!r.ok) throw new Error(`book-${book}.json: HTTP ${r.status}`);
        return r.json();
      }));
    }
    return chunkCache.get(key);
  }

  // ---------- routing ----------

  function parseHash() {
    const m = location.hash.match(/^#\/([^/]+)\/([^/]+)\/([^.]+)\.(.+)$/);
    if (!m) return null;
    const [, edL, edR, book, ch] = m;
    if (!manifest.editions[edL]) return null;
    if (edR !== NONE && !manifest.editions[edR]) return null;
    return { edL, edR, book, ch };
  }

  function writeHash() {
    const h = `#/${state.edL}/${state.edR}/${state.book}.${state.ch}`;
    if (location.hash !== h) location.hash = h; // triggers render via hashchange
    else render();
  }

  function defaultRoute() {
    const keys = Object.keys(manifest.editions);
    const edL = keys.includes("sprengel1829-grc") ? "sprengel1829-grc" : keys[0];
    // Builds may omit streams (a public build has no Beck), so never pair a stream with itself.
    const edR = ["beck2020", "sprengel1829-lat"].find((key) => keys.includes(key))
      || keys.find((key) => key !== edL) || NONE;
    const book = manifest.editions[edL].books[0];
    const ch = book.chapters[0];
    return { edL, edR, book: book.n, ch: ch.n };
  }

  // ---------- chapter list helpers ----------

  function flatChapters(edition) {
    const out = [];
    for (const book of manifest.editions[edition].books) {
      for (const ch of book.chapters) out.push({ book: book.n, ch: ch.n, label: ch.label });
    }
    return out;
  }

  function currentIndex() {
    const flat = flatChapters(state.edL);
    return { flat, i: flat.findIndex((c) => c.book === state.book && c.ch === state.ch) };
  }

  function step(delta) {
    const { flat, i } = currentIndex();
    const next = flat[i + delta];
    if (!next) return;
    state.book = next.book;
    state.ch = next.ch;
    writeHash();
  }

  // ---------- rendering ----------

  function editionOptions(select, value, allowNone) {
    select.innerHTML = "";
    if (allowNone) {
      const opt = document.createElement("option");
      opt.value = NONE;
      opt.textContent = "— single pane —";
      select.appendChild(opt);
    }
    for (const [key, ed] of Object.entries(manifest.editions)) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = ed.label;
      select.appendChild(opt);
    }
    select.value = value;
  }

  function buildToc() {
    toc.innerHTML = "";
    const ed = manifest.editions[state.edL];
    for (const book of ed.books) {
      const det = document.createElement("details");
      det.className = "book";
      det.open = book.n === state.book;
      const sum = document.createElement("summary");
      sum.textContent = `Book ${book.n}`;
      det.appendChild(sum);
      for (const ch of book.chapters) {
        const a = document.createElement("a");
        a.href = `#/${state.edL}/${state.edR}/${book.n}.${ch.n}`;
        a.innerHTML = `<span class="n">${ch.n}</span><span class="t"></span>`;
        a.querySelector(".t").textContent = ch.label || "";
        if (book.n === state.book && ch.n === state.ch) {
          a.className = "current";
        }
        det.appendChild(a);
      }
      toc.appendChild(det);
    }
    const cur = toc.querySelector("a.current");
    if (cur) cur.scrollIntoView({ block: "center" });
  }

  function renderCredits(pane, edition, metadata) {
    const details = pane.querySelector(".edition-credits");
    if (details.dataset.edition === edition) return;
    details.dataset.edition = edition;
    details.open = false;
    details.querySelector("summary").setAttribute("aria-label", `Source and credits for ${metadata.label}`);
    const content = details.querySelector(".credits-content");
    content.replaceChildren();
    const sections = metadata.credits?.sections || [];
    if (!sections.length) {
      const empty = document.createElement("p");
      empty.textContent = "Source and credit details are not recorded in this edition’s metadata.";
      content.appendChild(empty);
      return;
    }
    for (const section of sections) {
      const heading = document.createElement("h3");
      heading.textContent = section.title;
      content.appendChild(heading);
      const list = document.createElement("dl");
      for (const entry of section.entries) {
        const label = document.createElement("dt");
        label.textContent = entry.label;
        const description = document.createElement("dd");
        const text = document.createElement("span");
        text.textContent = entry.text;
        description.appendChild(text);
        const links = document.createElement("ul");
        links.className = "credits-links";
        for (const link of entry.links || []) {
          // Defence in depth for generated metadata: no HTML, relative URLs or
          // executable URL schemes are inserted into the reading surface.
          let url;
          try { url = new URL(link.href); } catch (_error) { continue; }
          if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) continue;
          const item = document.createElement("li");
          const anchor = document.createElement("a");
          anchor.textContent = link.text === entry.text ? "Open reference" : link.text;
          anchor.href = url.href;
          anchor.target = "_blank";
          anchor.rel = "noopener noreferrer";
          item.appendChild(anchor);
          links.appendChild(item);
        }
        if (links.children.length) description.appendChild(links);
        list.appendChild(label);
        list.appendChild(description);
      }
      content.appendChild(list);
    }
  }

  async function renderPane(pane, edition, route, generation) {
    const head = pane.querySelector(".pane-head");
    const body = pane.querySelector(".pane-body");
    pane._chapter = null;
    pane._chunk = null;
    if (edition === NONE) {
      pane.classList.add("hidden");
      return;
    }
    pane.classList.remove("hidden");
    const ed = manifest.editions[edition];
    renderCredits(pane, edition, ed);
    pane.dataset.lang = ed.lang;
    const status = typeof ed.status === "string" ? ed.status.replaceAll("_", " ") : "";
    head.textContent = `${ed.label} · ${route.book}.${route.ch}${status ? ` · ${status}` : ""}`;
    body.textContent = "Loading…";
    let chunk;
    try {
      chunk = await loadChunk(edition, route.book);
    } catch (err) {
      if (generation !== renderGeneration) return;
      body.textContent = `Book ${route.book} is not available in this edition (${err.message}).`;
      pane._chunk = null;
      return;
    }
    if (generation !== renderGeneration) return;
    pane._chunk = chunk;
    const chapter = chunk.chapters[route.ch];
    if (!chapter) {
      body.textContent = `Chapter ${route.book}.${route.ch} is not in ${ed.label}.`;
      return;
    }
    let html = chapter.html;
    const sigla = (chapter.sigla || []).join("");
    const noteIds = chapter.noteIds || [];
    if (sigla || noteIds.length) {
      const items = noteIds
        .map((id) => `<li id="en-${id}">${chunk.notes[id] || ""}</li>`)
        .join("");
      html += `<section class="endnotes"><h4>Notes</h4>${sigla}${items ? `<ol>${items}</ol>` : ""}</section>`;
    }
    body.innerHTML = html;
    const firstCommentary = body.querySelectorAll(".chapter > .commentary")[0]
      || body.querySelectorAll(".chapter .section > .commentary")[0];
    if (firstCommentary) {
      // Move the existing Notes section so its content and note IDs stay intact.
      const endnotes = body.querySelector(".endnotes");
      if (endnotes) firstCommentary.before(endnotes);
      firstCommentary.classList.add("commentary-first");
    }
    body.scrollTop = 0;
    pane.scrollTop = 0;
    pane._chapter = chapter;
  }

  async function render() {
    const generation = ++renderGeneration;
    const route = { ...state };
    hidePopover();
    $("#where").textContent = `${route.book}.${route.ch}`;
    pickL.value = route.edL;
    pickR.value = route.edR;
    buildToc();
    await Promise.all([renderPane(paneL, route.edL, route, generation), renderPane(paneR, route.edR, route, generation)]);
    if (generation !== renderGeneration) return;
    updateDiplomaticLink();
    const { flat, i } = currentIndex();
    $("#prev").disabled = i <= 0;
    $("#next").disabled = i < 0 || i >= flat.length - 1;
    if (!$("#facs").hidden && paneL._chapter && paneL._chapter.pages.length) {
      openFacs(paneL._chapter.pages[0], route.edL);
    }
  }

  function facsimileLeaf(page) {
    if (!page || !page.facs) return null;
    const source = page.facs.info || page.facs.direct || page.facs.url || "";
    let decoded = source;
    try { decoded = decodeURIComponent(source); } catch (_error) {}
    const match = decoded.match(/_(\d{4})\.jp2(?:\/|$)/);
    return match ? match[1] : null;
  }

  function updateDiplomaticLink() {
    const link = $("#pageView");
    const candidates = [
      { edition: state.edL, pane: paneL },
      { edition: state.edR, pane: paneR },
    ];
    const match = candidates.find(({ edition, pane }) =>
      (edition === "sprengel1829-grc" || edition === "sprengel1829-lat") &&
      pane._chapter && pane._chapter.pages && pane._chapter.pages.length
    );
    const leaf = match ? facsimileLeaf(match.pane._chapter.pages[0]) : null;
    link.hidden = !leaf;
    if (leaf) {
      const chapter = encodeURIComponent(`${state.book}.${state.ch}`);
      link.href = `diplomatic.html?chapter=${chapter}#/sprengel1829/${leaf}`;
      link.title = `Open this chapter at scan leaf ${leaf}`;
    }
  }

  // ---------- popover ----------

  function showPopover(target, html) {
    popover.innerHTML = `<button class="pop-close" aria-label="Close">×</button>${html}`;
    popover.hidden = false;
    const rect = target.getBoundingClientRect();
    const pw = Math.min(420, window.innerWidth - 24);
    let left = Math.min(rect.left, window.innerWidth - pw - 12);
    let top = rect.bottom + 6;
    popover.style.left = `${Math.max(8, left)}px`;
    popover.style.top = `${top}px`;
    const ph = popover.getBoundingClientRect().height;
    if (top + ph > window.innerHeight - 8) {
      popover.style.top = `${Math.max(8, rect.top - ph - 6)}px`;
    }
    popover.querySelector(".pop-close").addEventListener("click", hidePopover);
  }

  function hidePopover() {
    popover.hidden = true;
  }

  function highlightNote(pane, elements) {
    document.querySelectorAll(".note-hl").forEach((el) => el.classList.remove("note-hl"));
    elements.forEach((el) => el.classList.add("note-hl"));
  }

  function handleTextClick(event) {
    const fnref = event.target.closest("a.fnref");
    const app = event.target.closest("span.app");
    const pb = event.target.closest("a.pb");
    const pane = event.target.closest(".pane");
    const endnote = event.target.closest(".endnotes li[id^='en-']");
    if (endnote && pane && !event.target.closest("a")) {
      // a note clicked: highlight it and its marks, bring the first mark into view
      const id = endnote.id.slice(3);
      const refs = [...pane.querySelectorAll(`a.fnref[data-note="${CSS.escape(id)}"]`)];
      highlightNote(pane, [endnote, ...refs]);
      if (refs.length) refs[0].scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }
    if (fnref && pane && pane._chunk) {
      event.preventDefault();
      const id = fnref.dataset.note;
      const target = pane.querySelector(`#en-${CSS.escape(id)}`);
      highlightNote(pane, [fnref, ...(target ? [target] : [])]);
      const note = pane._chunk.notes[id];
      if (note) {
        const endnote = pane.querySelector(`#en-${CSS.escape(id)}`);
        showPopover(fnref, note + (endnote ? "" : ""));
      } else {
        showPopover(fnref, `<em>Note ${id} is not in this book’s data (see build REPORT.md).</em>`);
      }
      return;
    }
    if (app && pane && pane._chunk) {
      event.preventDefault();
      const entry = pane._chunk.apps[app.dataset.app];
      showPopover(app, entry || "<em>No apparatus entry.</em>");
      return;
    }
    if (pb && pane && pane._chapter) {
      event.preventDefault();
      const page = pane._chapter.pages[Number(pb.dataset.page)];
      if (page) {
        $("#facs").hidden = false;
        $("#toggleFacs").classList.add("active");
        openFacs(page, pane === paneL ? state.edL : state.edR);
      }
      return;
    }
    if (!event.target.closest("#popover")) hidePopover();
  }

  // ---------- facsimile ----------

  let osd = null;
  let facsRetried = false;
  let currentFacs = null;

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
        setTimeout(() => openSource(currentFacs), 400);
        return;
      }
      const direct = currentFacs && (currentFacs.direct || currentFacs.url);
      $("#facsLabel").textContent = "Facsimile unavailable.";
      if (direct) {
        const a = $("#facsDirect");
        a.href = direct;
        a.hidden = false;
      }
    });
    return osd;
  }

  function openSource(facs) {
    const viewer = ensureOsd();
    if (facs.kind === "iiif") viewer.open(facs.info);
    else viewer.open({ type: "image", url: facs.url });
  }

  function openFacs(page, edition) {
    if (!page.facs) {
      $("#facsLabel").textContent = `p. ${page.n} — no facsimile for this page.`;
      $("#facsDirect").hidden = true;
      return;
    }
    facsRetried = false;
    currentFacs = page.facs;
    const ed = manifest.editions[edition];
    $("#facsLabel").textContent = `${ed.label} — printed p. ${page.n}`;
    const a = $("#facsDirect");
    const direct = page.facs.direct || page.facs.url;
    a.href = direct || "#";
    a.hidden = !direct;
    openSource(page.facs);
  }

  // ---------- wiring ----------

  function handleKeydown(event) {
    if (event.target.closest(".edition-credits")) return;
    if (event.target.matches("input, select, textarea")) return;
    if (event.key === "ArrowLeft") step(-1);
    if (event.key === "ArrowRight") step(1);
    if (event.key === "Escape") hidePopover();
  }

  function bind() {
    window.addEventListener("hashchange", () => {
      const route = parseHash();
      if (route) {
        Object.assign(state, route);
        render();
      }
    });
    pickL.addEventListener("change", () => {
      state.edL = pickL.value;
      const flat = flatChapters(state.edL);
      if (!flat.some((c) => c.book === state.book && c.ch === state.ch)) {
        state.book = flat[0].book;
        state.ch = flat[0].ch;
      }
      writeHash();
    });
    pickR.addEventListener("change", () => {
      state.edR = pickR.value;
      writeHash();
    });
    $("#prev").addEventListener("click", () => step(-1));
    $("#next").addEventListener("click", () => step(1));
    document.addEventListener("keydown", handleKeydown);
    $("#toggleToc").addEventListener("click", (e) => {
      toc.classList.toggle("hidden");
      e.currentTarget.classList.toggle("active", !toc.classList.contains("hidden"));
    });
    $("#toggleLineation").addEventListener("click", (e) => {
      const active = document.body.classList.toggle("show-lineation");
      e.currentTarget.classList.toggle("active", active);
      e.currentTarget.setAttribute("aria-pressed", String(active));
    });
    $("#toggleFw").addEventListener("click", (e) => {
      document.body.classList.toggle("show-fw");
      e.currentTarget.classList.toggle("active");
    });
    $("#toggleFacs").addEventListener("click", (e) => {
      const facs = $("#facs");
      facs.hidden = !facs.hidden;
      e.currentTarget.classList.toggle("active", !facs.hidden);
      if (!facs.hidden && paneL._chapter && paneL._chapter.pages.length) {
        openFacs(paneL._chapter.pages[0], state.edL);
      }
    });
    document.addEventListener("click", handleTextClick);
  }

  // ---------- boot ----------

  (async function boot() {
    try {
      await loadManifest();
    } catch (err) {
      document.body.innerHTML =
        `<div style="padding:40px;font-family:sans-serif;max-width:44em">
         <h2>Reader data not reachable</h2>
         <p>Open the completed reader preview. If the problem persists, rebuild the
         preview from its selected corpus export using the project README.</p></div>`;
      return;
    }
    const route = parseHash() || defaultRoute();
    Object.assign(state, route);
    editionOptions(pickL, state.edL, false);
    editionOptions(pickR, state.edR, true);
    bind();
    $("#toggleToc").classList.add("active");
    writeHash();
    render();
  })();
})();
