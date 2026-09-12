# Dioscorides reader

Read parallel Dioscorides editions, notes, critical apparatus and source facsimiles.
The Sprengel page view preserves physical lines and connects them to chapter routes.
This repository owns presentation. Edition Workbench owns the maintained corpus and
scholarly corrections; the reader consumes immutable exports and never edits them.

## Run locally

Use Python 3.12 or newer. From this repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m dioscorides_reader build --bundle /absolute/path/to/corpus-export --output dist
.venv/bin/python -m dioscorides_reader serve --directory dist
```

Open `http://127.0.0.1:8000/reader.html`. The server binds to loopback by default.
`dist` is reproducible output and must not be edited as an edition source.
Builds require the exported text and metadata; the production checkout is unnecessary.

To select a pinned snapshot, use `--lock corpus.lock.json` with `build` or `fetch`.
The lock records `bundle_id` and `producer_commit`. Fetch verifies every file before
publishing an entry under the ignored cache and prints the resulting bundle directory:

```bash
.venv/bin/python -m dioscorides_reader fetch --source /absolute/path/to/corpus-export --cache .cache/corpus --lock corpus.lock.json
.venv/bin/python -m dioscorides_reader fetch --repository alchemiesofscent/edition-workbench --tag corpus-ID --asset dioscorides-corpus.tar.gz --cache .cache/corpus --lock corpus.lock.json
```

Private release retrieval uses the authenticated `gh` CLI. Replace `corpus-ID` with the
exact release recorded in the project handoff. It downloads no scan images. Release
archives must contain one bundle directory and regular files; links and escaping paths
are rejected before extraction. Reader builds reject corrupt or unsupported bundles and
replace previous completed output only after all generation succeeds.

## Corpus interface

`manifest.json` declares `dioscorides-corpus-export/1`, the production commit, the selected
display streams and their scholarly status, and every payload file's hash and byte size.
The bundle identifier is SHA-256 of sorted compact UTF-8 JSON with `bundle_id` and optional
top-level timestamps omitted. Included XML must resolve entirely within the verified files.

The payload carries selected TEI and XInclude dependencies, the chapter-label table,
`diplomatic-pages/1` parsed Sprengel page records, and `facsimiles/1` retrieval records.
Physical page records keep exact lines, blank lines, furniture and notes; the reader derives
line identifiers, chapter bridges and browser chunks. Shared diplomatic parsing belongs
to production. No source checkout paths, cross-repository imports, or scan binaries are needed.

The existing seven stream identifiers and hash URLs remain stable:

```text
reader.html#/wellmann1906/sprengel1829-grc/1.1
reader.html#/sprengel1830-comm-eng/sprengel1830-comm/1.praef
reader.html#/beck2020/-/1.1
diplomatic.html#/sprengel1829/0499
```

Equal chapter numbers provide provisional display pairing, not an assertion of scholarly
equivalence. The English translation retains its draft label. Candidate status is displayed
in the reading pane. Mattioli and Hájek can remain production work in progress until their
exports have supported reading structures; the reader never invents chapter alignment.

Remote facsimiles use the existing Archive.org, Heidelberg and BBAW adapters. Beck images
and two recovered Sprengel pages need their recorded optional image source. When an image
is unavailable, reading remains usable; its retrieval record remains in the built data.
No build fetches, retains or commits scans. Image restoration is a separate local operation.

## Development and verification

`src/dioscorides_reader` contains bundle validation and rendering; `web` contains the
maintained static application and vendored OpenSeadragon; `tests` contains synthetic
regressions. Historical implementations were selected from tei-maker commit
`ec8823eef290fe5bef51a4fa7afe0e7ffcceff83` and adapted for immutable input bundles.

```bash
.venv/bin/python -m pytest
```

Focused tests cover isolated deterministic builds, notes and inline/stand-off apparatus,
word joins across lines/pages, duplicate routes, complete apparatus targets, encoding-aware
DTD rejection, bundle integrity and includes, lock mismatch, safe archive extraction, and
preservation of previous output. When Node.js is available, pytest also runs delayed-fetch
regressions against the actual UI functions to ensure navigation cannot mix old text with a
new heading. Full-corpus integration additionally checks all route sets, note/apparatus
references, 855 Sprengel physical leaves, and browser behavior.
Human scholarly acceptance and deployment are separate from these engineering checks.

An optional browser smoke runner uses an existing Chromium executable through its debugging
protocol; it needs Node.js 22 or newer and no npm packages. It checks popovers, stable routes,
the physical-page bridge, mobile layout and continued reading with unavailable image services:

```bash
node tests/browser_smoke.cjs dist /absolute/path/to/chromium /tmp/dioscorides-browser-evidence
```
