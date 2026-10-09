/* Optional real-browser integration check: node tests/browser_smoke.cjs DIST CHROME OUTPUT */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { spawn } = require("node:child_process");

async function main() {
  const [distValue, chrome, outputValue] = process.argv.slice(2);
  if (!distValue || !chrome || !outputValue) throw new Error("Usage: node tests/browser_smoke.cjs DIST CHROME OUTPUT");
  const dist = path.resolve(distValue), output = path.resolve(outputValue);
  fs.mkdirSync(output, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "dioscorides-browser-"));
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const server = http.createServer((request, response) => {
    const file = path.resolve(dist, "." + decodeURIComponent(new URL(request.url, "http://local").pathname));
    if (!file.startsWith(dist + path.sep)) { response.writeHead(403).end(); return; }
    fs.readFile(file, (error, bytes) => {
      if (error) { response.writeHead(404).end(); return; }
      const type = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" }[path.extname(file)];
      response.writeHead(200, { "Content-Type": type || "application/octet-stream" }).end(bytes);
    });
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const address = `http://127.0.0.1:${server.address().port}`;
  const browser = spawn(chrome, ["--headless", "--no-sandbox", "--disable-dev-shm-usage", "--no-first-run",
    "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
  let diagnostics = "";
  browser.stderr.on("data", bytes => { diagnostics = (diagnostics + bytes.toString()).slice(-4000); });
  let socket;
  try {
    const activePort = path.join(profile, "DevToolsActivePort");
    let port;
    for (let attempt = 0; !port; attempt++) {
      if (attempt > 150 || browser.exitCode !== null) throw new Error("Chromium did not start: " + diagnostics);
      if (fs.existsSync(activePort)) {
        const value = fs.readFileSync(activePort, "utf8").split("\n")[0];
        if (/^[0-9]+$/.test(value) && Number(value) > 0) port = value;
      }
      if (!port) await sleep(100);
    }
    const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
    socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.addEventListener("open", resolve); socket.addEventListener("error", reject); });
    let nextID = 0;
    const pending = new Map(), exceptions = [];
    socket.addEventListener("message", event => {
      const message = JSON.parse(event.data);
      if (message.method === "Runtime.exceptionThrown") exceptions.push(message.params.exceptionDetails.text);
      if (pending.has(message.id)) {
        const [resolve, reject] = pending.get(message.id);
        pending.delete(message.id);
        message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
      }
    });
    const rpc = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++nextID;
      pending.set(id, [resolve, reject]);
      socket.send(JSON.stringify({ id, method, params }));
    });
    const evaluate = async expression => {
      const result = await rpc("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text + ": " + expression);
      return result.result.value;
    };
    const waitFor = async expression => {
      for (let attempt = 0; attempt < 150; attempt++) {
        if (await evaluate(expression)) return;
        await sleep(100);
      }
      throw new Error("Timed out: " + expression);
    };
    const navigate = async route => {
      await rpc("Page.navigate", { url: address + route });
      await waitFor("document.readyState === 'complete'");
    };
    const key = async (name, code, keyCode) => {
      const text = name === "Enter" ? "\r" : name === " " ? " " : undefined;
      await rpc("Input.dispatchKeyEvent", {type: "keyDown", key: name, code, windowsVirtualKeyCode: keyCode, text});
      await rpc("Input.dispatchKeyEvent", {type: "keyUp", key: name, code, windowsVirtualKeyCode: keyCode});
    };
    await rpc("Page.enable");
    await rpc("Runtime.enable");
    await rpc("Network.enable");
    // Verify text remains usable when optional remote image services are unavailable.
    await rpc("Network.setBlockedURLs", { urls: ["*://iiif.archive.org/*", "*://digilib.bbaw.de/*", "*://digi.ub.uni-heidelberg.de/*"] });
    await rpc("Emulation.setDeviceMetricsOverride", { width: 1280, height: 850, deviceScaleFactor: 1, mobile: false });
    await navigate("/reader.html#/wellmann1906/sprengel1829-grc/1.1");
    await waitFor("document.querySelectorAll('.pane-body .chapter').length === 2");
    assert.equal(await evaluate("document.querySelector('#paneL .edition-credits').open"), false);
    await evaluate("document.querySelector('#paneL .edition-credits summary').focus()");
    assert.equal(await evaluate("document.activeElement.matches('#paneL .edition-credits summary')"), true);
    await key("Enter", "Enter", 13);
    await waitFor("document.querySelector('#paneL .edition-credits').open");
    assert.equal(await evaluate(`(async () => {
      const manifest = await (await fetch('data/manifest.json')).json();
      return ['L', 'R'].every(side => {
        const pane = document.querySelector('#pane' + side);
        const details = pane.querySelector('.edition-credits');
        const edition = manifest.editions[details.dataset.edition];
        return edition.credits.sections.every(section => section.entries.every(entry =>
          details.querySelector('.credits-content').textContent.includes(entry.text)));
      });
    })()`), true);
    assert.match(await evaluate("document.querySelector('#paneL .edition-credits summary').getAttribute('aria-label')"), /Wellmann/);
    assert.match(await evaluate("document.querySelector('#paneR .edition-credits summary').getAttribute('aria-label')"), /Sprengel/);
    const beforeCreditsKey = await evaluate("location.hash");
    await key("ArrowRight", "ArrowRight", 39);
    assert.equal(await evaluate("location.hash"), beforeCreditsKey, "credits keyboard navigation must not turn the chapter");
    await key("Tab", "Tab", 9);
    assert.equal(await evaluate("document.activeElement.tagName === 'A' && !!document.activeElement.closest('.edition-credits')"), true);
    await evaluate("document.querySelector('#paneL .edition-credits summary').focus()");
    await key(" ", "Space", 32);
    await waitFor("!document.querySelector('#paneL .edition-credits').open");
    await evaluate("document.querySelector('#paneL .app').click()");
    await waitFor("!document.querySelector('#popover').hidden && document.querySelector('#popover').textContent.length > 5");
    await evaluate("document.querySelector('.pop-close').click()");
    await navigate("/reader.html#/sprengel1830-comm-eng/sprengel1830-comm/1.praef");
    await waitFor("document.querySelectorAll('.pane-body .chapter').length === 2");
    assert.match(await evaluate("document.querySelector('#paneL .pane-head').textContent"), /English draft/);
    await evaluate("document.querySelector('#paneL .fnref').click()");
    await waitFor("!document.querySelector('#popover').hidden");
    await navigate("/reader.html#/sprengel1829-grc/sprengel1829-lat/3.122");
    await waitFor("!document.querySelector('#pageView').hidden");
    assert.match(await evaluate("document.querySelector('#pageView').href"), /0499$/);
    await evaluate("document.querySelector('#toggleLineation').click()");
    assert.equal(await evaluate("document.body.classList.contains('show-lineation')"), true);
    // Synthetic numerals exercise the switch even with an older pinned corpus.
    await evaluate(`document.querySelector('#paneL .chapter').insertAdjacentHTML('beforeend',
      '<p id="numeralSmoke"><span class="tei-num tei-num-chapter">4</span> <span class="tei-num tei-num-section">2</span></p>')`);
    assert.equal(await evaluate("document.querySelector('#toggleChapterNumerals').getAttribute('aria-pressed')"), "true");
    assert.notEqual(await evaluate("getComputedStyle(document.querySelector('#numeralSmoke .tei-num-chapter')).display"), "none");
    await evaluate("document.querySelector('#toggleChapterNumerals').click()");
    assert.equal(await evaluate("document.body.classList.contains('hide-chapter-numerals')"), true);
    assert.equal(await evaluate("document.querySelector('#toggleChapterNumerals').getAttribute('aria-pressed')"), "false");
    assert.equal(await evaluate("getComputedStyle(document.querySelector('#numeralSmoke .tei-num-chapter')).display"), "none");
    assert.notEqual(await evaluate("getComputedStyle(document.querySelector('#numeralSmoke .tei-num-section')).display"), "none");
    await rpc("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: false });
    await evaluate("if (!document.querySelector('#toc').classList.contains('hidden')) document.querySelector('#toggleToc').click()");
    await evaluate("document.querySelector('#paneL .edition-credits').open = true");
    await sleep(100);
    assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth"), true);
    assert.equal(await evaluate(`(() => {
      const credits = document.querySelector('#paneL .edition-credits');
      const bounds = credits.getBoundingClientRect();
      return bounds.width > 250 && bounds.right <= innerWidth && credits.scrollWidth <= credits.clientWidth;
    })()`), true);
    const screenshot = await rpc("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(output, "reader-mobile.png"), Buffer.from(screenshot.data, "base64"));
    // Compact shell: one pane, menu and contents drawers, comparison toggle.
    assert.equal(await evaluate("getComputedStyle(document.querySelector('#paneR')).display"), "none");
    await evaluate("document.querySelector('#toggleMenu').click()");
    assert.equal(await evaluate("!document.querySelector('#readerMenu').hidden && !document.querySelector('#drawerBackdrop').hidden"), true);
    assert.equal(await evaluate("document.querySelector('#toggleChapterNumerals').getBoundingClientRect().width > 0"), true);
    await evaluate("document.querySelector('#toggleChapterNumerals').click()");
    assert.equal(await evaluate("document.querySelector('#toggleChapterNumerals').getAttribute('aria-pressed')"), "true");
    assert.notEqual(await evaluate("getComputedStyle(document.querySelector('#numeralSmoke .tei-num-chapter')).display"), "none");
    await evaluate("document.querySelector('#numeralSmoke').remove()");
    await evaluate("document.querySelector('#closeMenu').click()");
    await evaluate("document.querySelector('#where').click()");
    assert.equal(await evaluate("!document.querySelector('#toc').classList.contains('hidden') && !!document.querySelector('.contents-search input')"), true);
    await evaluate("document.querySelector('#drawerBackdrop').click()");
    await evaluate("document.querySelector('#toggleComparison').click()");
    assert.equal(await evaluate("getComputedStyle(document.querySelector('#paneL')).display === 'none' && getComputedStyle(document.querySelector('#paneR')).display !== 'none'"), true);
    await evaluate("document.querySelector('#toggleComparison').click()");
    const hasMatter = await evaluate(`(async () => {
      const m = await (await fetch('data/manifest.json')).json();
      return m.editions.berendes1902?.books.some(book => book.n === 'front');
    })()`);
    if (hasMatter) {
      await rpc("Emulation.setDeviceMetricsOverride", { width: 1280, height: 850, deviceScaleFactor: 1, mobile: false });
      await navigate("/reader.html#/berendes1902/berendes1902-eng/front.matter");
      await waitFor("document.querySelectorAll('.pane-body .chapter').length === 2");
      assert.match(await evaluate("document.querySelector('#paneL .pane-body').textContent"), /Vorwort/);
      assert.match(await evaluate("document.querySelector('#paneR .pane-body').textContent"), /PREFACE|Preface/);
      assert.equal(await evaluate("document.querySelectorAll('#paneL .fnref').length"), 2);
      await evaluate("document.querySelector('#paneR .fnref').click()");
      await waitFor("!document.querySelector('#popover').hidden");
      await evaluate("document.querySelector('#paneL .pb').click()");
      assert.equal(await evaluate("document.querySelector('#facs').hidden"), false);
      await evaluate("document.querySelector('#toggleFacs').click()");
      const frontShot = await rpc("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(output, "berendes-front.png"), Buffer.from(frontShot.data, "base64"));
      await navigate("/reader.html#/berendes1902/berendes1902-eng/back.errata");
      await waitFor("document.querySelectorAll('.errata .matter-link').length === 10");
      assert.match(await evaluate("document.querySelector('#paneR .errata').textContent"), /read beard grass/);
      assert.match(await evaluate("document.querySelector('#paneR .matter-link').hash"), /berendes1902\/berendes1902-eng\/1\.48$/);
      await evaluate("document.querySelector('#paneR .matter-link').click()");
      await waitFor("document.querySelector('#where').textContent === '1.48' && document.querySelectorAll('.pane-body .chapter').length === 2");
      await navigate("/reader.html#/berendes1902-eng/berendes1902/back.index");
      await waitFor("document.querySelectorAll('.index-entry').length === 4422");
      assert.match(await evaluate("document.querySelector('#paneL .sachregister').textContent"), /beard grass/i);
      await evaluate(`(() => {
        const input = document.querySelector('#paneL .index-filter input');
        input.value = 'beard grass'; input.dispatchEvent(new Event('input'));
      })()`);
      const filtered = await evaluate("[...document.querySelectorAll('#paneL .index-entry')].filter(e => !e.hidden).length");
      assert.ok(filtered > 0 && filtered < 2211);
      assert.equal(await evaluate("document.querySelectorAll('#paneR .index-entry[hidden]').length"), 0);
      await evaluate("document.querySelector('#paneL .index-entry:not([hidden]) .matter-link').click()");
      await waitFor("!document.querySelector('#popover').hidden || !location.hash.endsWith('back.index')");
      if (await evaluate("!document.querySelector('#popover').hidden")) {
        assert.ok(await evaluate("document.querySelectorAll('#popover a').length > 1"));
        await evaluate("document.querySelector('#popover a').click()");
      }
      await waitFor("!location.hash.endsWith('back.index') && document.querySelectorAll('.pane-body .chapter').length === 2");
      assert.match(await evaluate("location.hash"), /^#\/berendes1902-eng\/berendes1902\/[1-5]\./);
      await navigate("/reader.html#/berendes1902-eng/-/back.index");
      await waitFor("document.querySelectorAll('.index-entry').length === 2211");
      assert.equal(await evaluate("document.querySelector('#paneR').classList.contains('hidden')"), true);
      const indexShot = await rpc("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(path.join(output, "berendes-index.png"), Buffer.from(indexShot.data, "base64"));
    }
    await navigate("/diplomatic.html?chapter=3.122#/sprengel1829/0499");
    await waitFor("document.querySelectorAll('.stream-block').length === 2");
    assert.equal(await evaluate("document.querySelector('#line-0499-G03').dataset.chapter"), "3.122");
    await evaluate("document.querySelector('#streamView').value = 'grc'; document.querySelector('#streamView').dispatchEvent(new Event('change'))");
    await waitFor("document.querySelectorAll('.stream-block').length === 1");
    assert.equal(await evaluate("!!document.querySelector('.stream-grc')"), true);
    assert.ok((await evaluate("document.querySelector('#paper').textContent")).length > 100);
    const pagesScreenshot = await rpc("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(output, "diplomatic-mobile.png"), Buffer.from(pagesScreenshot.data, "base64"));
    assert.deepEqual(exceptions, []);
    const result = { passed: true, checks: ["parallel routes", "source-bound credits", "credits keyboard and link access", "credits mobile layout", "apparatus popover", "draft label", "footnote popover",
      "lineation", "chapter-page bridge", "390px layout", "compact reading shell", "physical line identity", "stream switching",
      "reading with unavailable remote facsimiles"], javascript_exceptions: exceptions, matter_checked: hasMatter };
    fs.writeFileSync(path.join(output, "browser-smoke.json"), JSON.stringify(result, null, 2) + "\n");
    console.log(JSON.stringify(result));
  } finally {
    if (socket) socket.close();
    browser.kill();
    await new Promise(resolve => server.close(resolve));
    await sleep(200);
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
