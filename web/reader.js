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
  // The compact layout (mobile.css) shows one pane and lays the facsimile over it.
  const compact = window.matchMedia("(max-width: 900px)");
  const facsCoversText = () => compact.matches && !$("#facs").hidden;
  const paneL = $("#paneL"), paneR = $("#paneR");
  const pickL = $("#pickL"), pickR = $("#pickR");
  const toc = $("#toc"), popover = $("#popover");

  // ---------- data ----------

  async function loadManifest() {
    const res = await fetch(`${DATA}/manifest.json`);
    if (!res.ok) throw new Error(`manifest.json: HTTP ${res.status}`);
    manifest = await res.json();
    const version = $("#readerVersion");
    if (version && manifest.reader_version) {
      version.textContent = `Reader ${manifest.reader_version} · corpus ${manifest.bundle_id.slice(0, 12)}`;
    }
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

  // ---------- pairing through Wellmann ----------
  // An edition with concordance rows (manifest pairing.to_wellmann) maps its chapters to
  // Wellmann's; the other pane shows the chapters of its own edition that render the same
  // Wellmann chapter(s). Editions without rows pair by identical key, as before.

  const CHAPTER_KEY = /^\d+[A-Za-z]*$/;
  const inverseCache = new Map();

  function toWellmann(edition, book, ch) {
    const pairing = manifest.editions[edition].pairing;
    const key = `${book}.${ch}`;
    if (!pairing) return [key];
    if (key in pairing.to_wellmann) return pairing.to_wellmann[key];
    return CHAPTER_KEY.test(ch) ? [] : [key];   // a chapter without rows has no counterpart; sections pair by key
  }

  function fromWellmann(edition, wkeys) {
    const pairing = manifest.editions[edition].pairing;
    if (!pairing) return wkeys;
    if (!inverseCache.has(edition)) {
      const inverse = new Map();
      for (const c of flatChapters(edition)) {
        for (const w of pairing.to_wellmann[`${c.book}.${c.ch}`] || []) {
          if (!inverse.has(w)) inverse.set(w, []);
          inverse.get(w).push(`${c.book}.${c.ch}`);
        }
      }
      inverseCache.set(edition, inverse);
    }
    const inverse = inverseCache.get(edition);
    const out = [];
    for (const w of wkeys) {
      const own = inverse.get(w) || (CHAPTER_KEY.test(w.slice(w.indexOf(".") + 1)) ? [] : [w]);
      for (const k of own) if (!out.includes(k)) out.push(k);
    }
    return out;
  }

  // The chapters of `edition` that answer the route's chapter in `from` (the left edition).
  function pairedTargets(from, edition, route) {
    const plain = [{ book: route.book, ch: route.ch }];
    if (from === edition) return { targets: plain, note: "" };
    const pf = manifest.editions[from].pairing, pe = manifest.editions[edition].pairing;
    if (!pf && !pe) return { targets: plain, note: "" };
    const wkeys = toWellmann(from, route.book, route.ch);
    const keys = fromWellmann(edition, wkeys);
    const targets = keys.map((k) => { const i = k.indexOf("."); return { book: k.slice(0, i), ch: k.slice(i + 1) }; });
    const status = [pf, pe].some((p) => p && p.status !== "checked") ? "proposed concordance" : "concordance";
    const same = targets.length === 1 && targets[0].book === route.book && targets[0].ch === route.ch;
    const via = pf && wkeys.length && !(wkeys.length === 1 && wkeys[0] === `${route.book}.${route.ch}`)
      ? ` = Wellmann ${wkeys.join(", ")}` : "";
    const note = same ? "" : `${manifest.editions[from].label} ${route.book}.${route.ch}`
      + (wkeys.length ? `${via} = ${manifest.editions[edition].label} ${keys.length ? keys.join(", ") : "(none)"}`
        : " has no Wellmann counterpart")
      + ` · ${status}`;
    return { targets, note };
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
      sum.textContent = book.label || `Book ${book.n}`;
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

  async function renderPane(pane, edition, route, generation, paired = null) {
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
    const targets = paired ? paired.targets : [{ book: route.book, ch: route.ch }];
    const shown = targets.map((t) => `${t.book}.${t.ch}`).join(", ") || "—";
    head.textContent = `${ed.label} · ${shown}${status ? ` · ${status}` : ""}`;
    body.textContent = "Loading…";
    const banner = paired && paired.note
      ? `<p class="pairing-note">${paired.note.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</p>` : "";
    if (!targets.length) {
      body.innerHTML = banner || `<p>No counterpart in ${ed.label}.</p>`;
      return;
    }
    const parts = [];
    let chunk = null, chapter = null;
    for (const target of targets) {
      let part;
      try {
        part = await loadChunk(edition, target.book);
      } catch (err) {
        if (generation !== renderGeneration) return;
        body.textContent = `Book ${target.book} is not available in this edition (${err.message}).`;
        pane._chunk = null;
        return;
      }
      if (generation !== renderGeneration) return;
      const found = part.chapters[target.ch];
      if (!found) {
        parts.push(`<p>Chapter ${target.book}.${target.ch} is not in ${ed.label}.</p>`);
        continue;
      }
      if (!chapter) { chunk = part; chapter = found; }
      let html = found.html;
      const sigla = (found.sigla || []).join("");
      const noteIds = found.noteIds || [];
      if (sigla || noteIds.length) {
        const items = noteIds
          .map((id) => `<li id="en-${id}">${part.notes[id] || ""}</li>`)
          .join("");
        html += `<section class="endnotes"><h4>Notes</h4>${sigla}${items ? `<ol>${items}</ol>` : ""}</section>`;
      }
      parts.push(html);
    }
    pane._chunk = chunk;
    if (!chapter) {
      body.innerHTML = banner + parts.join("");
      return;
    }
    body.innerHTML = banner + parts.join("");
    configureMatter(body, chapter, route);
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

  function matterHref(route, target) {
    return `#/${route.edL}/${route.edR}/${target.route}`;
  }

  function configureMatter(body, chapter, route) {
    for (const link of body.querySelectorAll("a.matter-link")) {
      const targets = JSON.parse(link.dataset.targets);
      link.href = matterHref(route, targets[0]);
      if (targets.length > 1) {
        link.addEventListener("click", event => {
          event.preventDefault();
          event.stopPropagation();
          const list = document.createElement("div");
          for (const target of targets) {
            const item = document.createElement("p");
            const anchor = document.createElement("a");
            anchor.href = matterHref(route, target);
            anchor.textContent = `Chapter ${target.route}`;
            anchor.title = target.target;
            item.appendChild(anchor);
            list.appendChild(item);
          }
          showPopover(link, list.innerHTML);
        });
      }
    }
    if (chapter.kind !== "index") return;
    const label = document.createElement("label");
    label.className = "index-filter";
    label.textContent = "Filter index by headword ";
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Headword or English rendering";
    label.appendChild(input);
    body.prepend(label);
    input.addEventListener("input", () => {
      const query = input.value.trim().toLocaleLowerCase();
      for (const entry of body.querySelectorAll(".index-entry")) {
        entry.hidden = !entry.dataset.headword.toLocaleLowerCase().includes(query);
      }
      // while filtering, hide register/letter headings, page markers and paragraphs left without a match
      const register = typeof body.querySelector === "function" ? body.querySelector(".sachregister") : null;
      const container = register && (register.querySelector(".chapter") || register);
      if (container) {
        for (const block of container.children) {
          block.hidden = Boolean(query) && !block.querySelector(".index-entry:not([hidden])");
        }
      }
    });
  }

  async function render() {
    const generation = ++renderGeneration;
    const route = { ...state };
    hidePopover();
    $("#where").textContent = `${route.book}.${route.ch}`;
    pickL.value = route.edL;
    pickR.value = route.edR;
    buildToc();
    const paired = route.edR === NONE ? null : pairedTargets(route.edL, route.edR, route);
    await Promise.all([renderPane(paneL, route.edL, route, generation),
      renderPane(paneR, route.edR, route, generation, paired)]);
    if (generation !== renderGeneration) return;
    const facsChunk = await loadChunk(route.edL, route.book);
    if (generation !== renderGeneration) return;
    const seenPages = new Set();
    facsPages = Object.values(facsChunk.chapters).flatMap(c => c.pages || []).filter(page => {
      const key = `${page.n}/${JSON.stringify(page.facs || {})}`;
      if (seenPages.has(key)) return false;
      seenPages.add(key); return true;
    });
    facsIndex = -1;
    syncFacsNavigation();
    window.dioscoridesReaderRendered?.();
    updateDiplomaticLink();
    syncFacsNavigation();
    if (!$("#facs").hidden && paneL._chapter && paneL._chapter.pages.length) {
      openFacs(paneL._chapter.pages[0], route.edL);
    } else if (!$("#facs").hidden) setFacsVisible(true);
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

  let noteTrigger = null;
  function showPopover(target, html) {
    noteTrigger = target;
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
    popover.querySelector(".pop-close").focus({ preventScroll: true });
  }

  function hidePopover(restoreFocus = true) {
    const open = !popover.hidden;
    popover.hidden = true;
    if (restoreFocus && open && noteTrigger && noteTrigger.isConnected) noteTrigger.focus({ preventScroll: true });
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
      showNavigationControl: false,
      gestureSettingsTouch: {
        clickToZoom: false,
        dblClickToZoom: true,
        dblClickDragToZoom: true,
        pinchToZoom: true,
        dragToPan: true,
      },
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

  let facsPages = [];
  let facsIndex = -1;
  function syncFacsNavigation() {
    const imageMode = facsCoversText();
    const { flat, i } = currentIndex();
    const index = imageMode ? facsIndex : i;
    const count = imageMode ? facsPages.length : flat.length;
    $("#prev").disabled = index <= 0;
    $("#next").disabled = index < 0 || index >= count - 1;
    for (const [id, direction] of [["prev", "Previous"], ["next", "Next"]]) {
      const label = `${direction} ${imageMode ? "facsimile page" : "chapter"}`;
      $("#" + id).setAttribute("aria-label", label);
      $("#" + id).title = label;
    }
  }
  function navigate(delta) {
    if (!facsCoversText()) step(delta);
    else {
      const page = facsPages[facsIndex + delta];
      if (page) openFacs(page, state.edL);
    }
  }

  function setFacsVisible(visible) {
    $("#facs").hidden = !visible;
    $("#toggleFacs").classList.toggle("active", visible);
    $("#toggleFacs").setAttribute("aria-pressed", String(visible));
    if (visible && paneL._chapter?.pages.length) openFacs(paneL._chapter.pages[0], state.edL);
    else if (visible) {
      osd?.close();
      $("#facsLabel").textContent = "No facsimile is recorded for this chapter.";
      $("#facsDirect").hidden = true;
      facsIndex = -1;
    }
    syncFacsNavigation();
  }
  function openFacs(page, edition) {
    facsIndex = facsPages.findIndex(p => p.n === page.n);
    syncFacsNavigation();
    if (!page.facs) {
      if (osd) osd.close();
      currentFacs = null;
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
    if (event.key === "Escape") hidePopover();
    if (!popover.hidden) return;
    // In the compact layout an open drawer keeps the arrows for itself.
    if (compact.matches && (!toc.classList.contains("hidden") || $("#readerMenu")?.hidden === false)) return;
    if (event.target.matches("input, select, textarea")) return;
    if (facsCoversText() && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
      event.preventDefault();
      const page = facsPages[facsIndex + (event.key === "ArrowLeft" ? -1 : 1)];
      if (page) openFacs(page, state.edL);
      return;
    }
    if (event.key === "ArrowLeft") step(-1);
    if (event.key === "ArrowRight") step(1);
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
    $("#prev").addEventListener("click", () => navigate(-1));
    $("#next").addEventListener("click", () => navigate(1));
    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("click", e => { if (!e.target.closest("#popover, a.fnref, span.app")) hidePopover(false); });
    compact.addEventListener("change", syncFacsNavigation);
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
    $("#toggleFacs").addEventListener("click", () => {
      setFacsVisible($("#facs").hidden);
      $("#closeMenu")?.click();
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
