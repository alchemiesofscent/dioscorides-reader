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
    for (let attempt = 0; !fs.existsSync(activePort); attempt++) {
      if (attempt > 150 || browser.exitCode !== null) throw new Error("Chromium did not start: " + diagnostics);
      await sleep(100);
    }
    const port = fs.readFileSync(activePort, "utf8").split("\n")[0];
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
    await rpc("Page.enable");
    await rpc("Runtime.enable");
    await rpc("Network.enable");
    // Verify text remains usable when optional remote image services are unavailable.
    await rpc("Network.setBlockedURLs", { urls: ["*://iiif.archive.org/*", "*://digilib.bbaw.de/*", "*://digi.ub.uni-heidelberg.de/*"] });
    await rpc("Emulation.setDeviceMetricsOverride", { width: 1280, height: 850, deviceScaleFactor: 1, mobile: false });
    await navigate("/reader.html#/wellmann1906/sprengel1829-grc/1.1");
    await waitFor("document.querySelectorAll('.pane-body .chapter').length === 2");
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
    await rpc("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: false });
    await sleep(100);
    assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth"), true);
    const screenshot = await rpc("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(output, "reader-mobile.png"), Buffer.from(screenshot.data, "base64"));
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
    const result = { passed: true, checks: ["parallel routes", "apparatus popover", "draft label", "footnote popover",
      "lineation", "chapter-page bridge", "390px layout", "physical line identity", "stream switching",
      "reading with unavailable remote facsimiles"], javascript_exceptions: exceptions };
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
