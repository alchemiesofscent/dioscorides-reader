/* Reading preferences and the compact (≤900px) reader shell. Runs before
   reader.js; reader.js calls window.dioscoridesReaderRendered after each
   render. Drawers (menu, contents) exist only in the compact layout; on wider
   screens the contents rail and the facing panes behave as before. */
(function () {
  'use strict';
  const toolbar = document.querySelector('.reader-toolbar');
  const syncToolbarHeight = () => document.documentElement.style.setProperty('--reader-toolbar-height', toolbar.getBoundingClientRect().height + 'px');
  new ResizeObserver(syncToolbarHeight).observe(toolbar);
  syncToolbarHeight();
  const key = 'dioscorides-mobile-v1';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) {}
  const size = document.querySelector('#textSize');
  const theme = document.querySelector('#readerTheme');
  const toc = document.querySelector('#toc');
  const paneL = document.querySelector('#paneL');
  const paneR = document.querySelector('#paneR');
  const mobile = window.matchMedia('(max-width: 900px)');
  const compact = () => mobile.matches;
  if (!location.hash && /^#\/[^/]+\/[^/]+\/[^.]+\..+$/.test(saved.route || '')) {
    history.replaceState(null, '', saved.route);
  }
  theme.value = saved.theme === 'night' ? 'night' : 'paper';
  // Without a chosen size the layout default applies (16px wide, 21px compact).
  function showSize() {
    const chosen = Number(saved.size);
    if (chosen) document.documentElement.style.setProperty('--reader-size', Math.min(30, Math.max(14, chosen)) + 'px');
    else document.documentElement.style.removeProperty('--reader-size');
    size.value = chosen || (compact() ? 21 : 16);
  }
  function preferences() {
    document.body.classList.toggle('night', theme.value === 'night');
    saved.theme = theme.value; persist();
  }
  function persist() { try { localStorage.setItem(key, JSON.stringify(saved)); } catch (_) {} }
  showSize(); preferences();
  size.addEventListener('input', () => { saved.size = Number(size.value); showSize(); persist(); });
  theme.addEventListener('change', preferences);
  document.querySelector('#toggleSettings').addEventListener('click', e => {
    const settings = document.querySelector('#readerSettings');
    settings.hidden = !settings.hidden;
    e.currentTarget.setAttribute('aria-expanded', String(!settings.hidden));
  });
  const menu = document.querySelector('#readerMenu');
  const menuButton = document.querySelector('#toggleMenu');
  const backdrop = document.querySelector('#drawerBackdrop');
  function syncDrawers() {
    const open = compact() && (!menu.hidden || !toc.classList.contains('hidden'));
    backdrop.hidden = !open;
    document.querySelector('#where').setAttribute('aria-expanded', String(!toc.classList.contains('hidden')));
    document.querySelector('.frame .panes').inert = open;
    document.querySelector('#facs').inert = open;
  }
  function closeMenu() {
    const wasOpen = !menu.hidden;
    menu.hidden = true; menuButton.setAttribute('aria-expanded', 'false'); syncDrawers();
    if (wasOpen) menuButton.focus();
  }
  menuButton.addEventListener('click', () => {
    const opening = menu.hidden;
    contentsClosed(); menu.hidden = !opening;
    menuButton.setAttribute('aria-expanded', String(opening)); syncDrawers();
    if (opening) document.querySelector('#closeMenu').focus();
  });
  document.querySelector('#closeMenu').addEventListener('click', closeMenu);
  backdrop.addEventListener('click', () => { closeMenu(); contentsClosed(); });
  new MutationObserver(syncDrawers).observe(toc, { attributes: true, attributeFilter: ['class'] });
  document.querySelector('#toggleToc').addEventListener('click', closeMenu);
  document.querySelector('#where').addEventListener('click', () => document.querySelector('#toggleToc').click());
  document.addEventListener('keydown', e => {
    if (!compact()) return;
    const panel = !menu.hidden ? menu : !toc.classList.contains('hidden') ? toc : null;
    if (e.key !== 'Tab' || !panel) return;
    const items = [...panel.querySelectorAll('button,select,input,a,summary')].filter(el => el.getClientRects().length && !el.disabled);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
  });
  function contentsClosed() {
    toc.classList.add('hidden');
    const button = document.querySelector('#toggleToc');
    button.classList.remove('active'); button.setAttribute('aria-expanded', 'false');
    syncDrawers();
  }
  function contentsOpened() {
    toc.classList.remove('hidden');
    const button = document.querySelector('#toggleToc');
    button.classList.add('active'); button.setAttribute('aria-expanded', 'true');
    syncDrawers();
  }
  if (compact()) contentsClosed();
  // Crossing the breakpoint: drawers close on the way down, the rail returns on the way up.
  mobile.addEventListener('change', () => {
    menu.hidden = true; menuButton.setAttribute('aria-expanded', 'false');
    if (compact()) contentsClosed(); else contentsOpened();
    document.querySelector('#readerSettings').hidden = true;
    document.querySelector('#toggleSettings').setAttribute('aria-expanded', 'false');
    showSize();
  });
  const comparisonToggle = document.querySelector('#toggleComparison');
  comparisonToggle.addEventListener('click', () => selectSide(!document.body.classList.contains('mobile-comparison')));
  function selectSide(comparison) {
    const available = document.querySelector('#pickR').value !== '-';
    document.body.classList.toggle('mobile-comparison', comparison && available);
    comparisonToggle.textContent = comparison && available ? '2' : '1';
    const label = comparison && available ? 'Show primary text' : 'Show comparison text';
    comparisonToggle.setAttribute('aria-label', label);
    comparisonToggle.title = label;
    comparisonToggle.setAttribute('aria-pressed', String(comparison && available));
    comparisonToggle.disabled = !available;
    document.querySelector('#showPrimary').setAttribute('aria-pressed', String(!comparison || !available));
    document.querySelector('#showComparison').setAttribute('aria-pressed', String(comparison && available));
    document.querySelector('#showPrimary').classList.toggle('active', !comparison || !available);
    document.querySelector('#showComparison').classList.toggle('active', comparison && available);
  }
  document.querySelector('#showPrimary').addEventListener('click', () => selectSide(false));
  document.querySelector('#showComparison').addEventListener('click', () => selectSide(true));
  document.querySelector('#toggleToc').setAttribute('aria-controls', 'toc');
  document.querySelector('#toggleToc').addEventListener('click', () => {
    // Core reader's handler runs after this listener.
    queueMicrotask(() => document.querySelector('#toggleToc').setAttribute('aria-expanded', String(!toc.classList.contains('hidden'))));
  });
  toc.addEventListener('click', e => { if (compact() && e.target.closest('a')) contentsClosed(); });
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const settings = document.querySelector('#readerSettings');
    if (!settings.hidden && !compact()) {
      settings.hidden = true;
      document.querySelector('#toggleSettings').setAttribute('aria-expanded', 'false');
    }
    if (compact()) { contentsClosed(); closeMenu(); }
  });
  window.dioscoridesReaderRendered = () => {
    const sameRoute = saved.route === location.hash;
    if (sameRoute) {
      paneL.scrollTop = Number(saved.left) || 0;
      paneR.scrollTop = Number(saved.right) || 0;
    } else { saved.left = 0; saved.right = 0; }
    saved.route = location.hash; persist();
    const comparison = document.querySelector('#pickR').value !== '-';
    document.querySelector('#showComparison').disabled = !comparison;
    selectSide(document.body.classList.contains('mobile-comparison') && comparison);
    if (compact() && toc.classList.contains('hidden')) document.querySelector('#toggleToc').classList.remove('active');
    const search = document.createElement('div'); search.className = 'contents-search';
    const input = document.createElement('input'); input.type = 'search'; input.placeholder = 'Find a chapter…'; input.setAttribute('aria-label', 'Filter chapter titles or numbers');
    search.append(input); toc.prepend(search);
    const heading = document.createElement('div'); heading.className = 'drawer-heading';
    const title = document.createElement('strong'); title.textContent = 'Contents';
    const close = document.createElement('button'); close.className = 'btn'; close.textContent = '×'; close.setAttribute('aria-label', 'Close contents'); close.addEventListener('click', contentsClosed);
    heading.append(title, close); search.prepend(heading);
    input.addEventListener('input', () => {
      const normalize = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
      const q = normalize(input.value.trim());
      for (const book of toc.querySelectorAll('.book')) {
        let hits = 0;
        for (const a of book.querySelectorAll('a')) { a.hidden = !normalize(a.textContent).includes(q); if (!a.hidden) hits++; }
        book.hidden = !hits; if (q) book.open = !!hits;
      }
    });
  };
  let timer;
  for (const [pane, field] of [[paneL, 'left'], [paneR, 'right']]) {
    pane.addEventListener('scroll', () => {
      if (saved.route !== location.hash || pane.querySelector('.pane-body').textContent === 'Loading…') return;
      saved[field] = pane.scrollTop;
      clearTimeout(timer); timer = setTimeout(persist, 150);
    }, { passive: true });
  }
})();
