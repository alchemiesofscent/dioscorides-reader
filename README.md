# Dioscorides reader

Read parallel Dioscorides editions, notes, critical apparatus and source facsimiles.
The Sprengel page view preserves physical lines and connects them to chapter routes.
This repository owns presentation. Edition Workbench owns the maintained corpus and
scholarly corrections; the reader consumes immutable exports and never edits them.

## Run locally

Use Python 3.12 or newer and an authenticated GitHub CLI (`gh`) with access to the private corpus. From this repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m dioscorides_reader fetch --repository alchemiesofscent/edition-workbench --tag corpus-5b2356c89644b0a7 --lock corpus.lock.json
.venv/bin/python -m dioscorides_reader build --bundle .cache/corpus/5b2356c89644b0a721d9811b6192608591b260c21241024d3acf34875728e1d8 --lock corpus.lock.json --output dist
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
.venv/bin/python -m dioscorides_reader fetch --repository alchemiesofscent/edition-workbench --tag corpus-5b2356c89644b0a7 --asset dioscorides-corpus.tar.gz --cache .cache/corpus --lock corpus.lock.json
```

Private release retrieval uses the authenticated `gh` CLI. The exact release and bundle are recorded in `corpus.lock.json`. It downloads no scan images. Release
archives must contain one bundle directory and regular files; links and escaping paths
are rejected before extraction. Reader builds reject corrupt or unsupported bundles and
replace previous completed output only after all generation succeeds.

## Public site

`.github/workflows/pages.yml` publishes the reader to
<https://alchemiesofscent.github.io/dioscorides-reader/> on every push to `main` (or by hand
from the Actions tab). It fetches the pinned release and builds with `--exclude beck2020`:
Beck 2020 is in copyright and never appears in the public site, and the workflow refuses to
deploy if any Beck text or facsimile record reaches the output. The same public build locally:

```bash
.venv/bin/python -m dioscorides_reader build --bundle <bundle> --lock corpus.lock.json --output dist --exclude beck2020
```

The workflow needs two repository settings: Pages with source "GitHub Actions", and an Actions
secret `CORPUS_TOKEN`, a fine-grained token with read-only Contents access to
`alchemiesofscent/edition-workbench` so it can download the private corpus release.

## Phones and small screens

Up to 900px wide the reader switches to a compact layout. The routes, the data and the
text are the same; only the arrangement changes.

- **One edition at a time.** The **1/2** button in the bottom bar swaps between the left
  (primary) and right (comparison) edition of the current route; the menu has the same choice
  as **Primary edition** / **Comparison edition**.
- **Bottom bar.** ☰ opens the menu; ← and → step chapters; the chapter number opens the
  contents; **Facsimile** lays the page image over the text, and the arrows then turn its
  pages instead.
- **Menu.** Both edition pickers, Pages (Sprengel page view), Lineation, Page furniture and
  Reading settings.
- **Contents.** A drawer with a filter for chapter numbers and titles (accents ignored).
- **Notes and apparatus** open as a sheet above the bottom bar.

**Reading settings** (text size, night theme) exist at every width. They and the last
position (route and scroll) are saved in the browser's local storage on that device only,
under `dioscorides-mobile-v1`; nothing is sent anywhere. Without a chosen size, the text is
16px on desktop and 21px in the compact layout. The panel also shows the reader version and
the corpus bundle the site was built from, which is what to quote when reporting a problem.

`web/mobile.css` holds the compact layout and the desktop arrangement of the shared top-bar
markup; `web/mobile.js` runs before `web/reader.js` and handles preferences, drawers and the
edition toggle. The browser smoke runner checks the compact shell at 390px.

## Versions

There is no release schedule: every push to `main` deploys, and a change people will notice
ships as a new version as soon as it is ready.

- A fix that does not change the layout is a patch version (0.2.1 → 0.2.2); a new way of
  reading is a minor version (0.2 → 0.3). Several fixes made in one sitting can share one.
- Refactors, tests and documentation need no version. A new corpus pin is not a reader
  version either: the bundle identifier is shown beside the version.

To release, in the commit that makes the change: set the version in `pyproject.toml`,
`src/dioscorides_reader/__init__.py` and the `?v=` asset queries in `web/reader.html` (which
stop browsers serving a cached script or stylesheet), and add a `CHANGELOG.md` entry headed
`## <version> — <date>`. `tests/test_version.py` fails if these disagree. Versions use the
`-alpha` suffix while the reader is in alpha; Python reads `0.2.1-alpha` as `0.2.1a0`.

After a successful deployment, the Pages workflow's `tag` job runs `.github/release_tags.py`.
It tags every version that has a changelog entry as `v<version>`, on the commit that first
set that version in `pyproject.toml`, with the changelog entry as the tag message. Existing
tags are never moved. `python .github/release_tags.py --dry-run` shows what it would do.

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

## Source and credits

Open **Source and credits** beneath either edition heading to see the source edition,
recorded contributors and responsibilities, project methods, funding and licence. The
content comes from the pinned TEI headers; it is not inferred from author names or witnesses.
The Wellmann headers now credit Sean Coughlin and Alchemies of Scent for documented
transcription corrections, editorial review, TEI/apparatus work and quality checks, while
retaining the original First1K contributors and distinguishing the printed editor.
Automated/AI-assisted methods and review limits remain explicit.

The September 2026 Wellmann attribution correction preserves every non-header XML byte.
The reader still displays the same chapter text and apparatus, and inherited full-document
EpiDoc limitations remain recorded by the producer.
