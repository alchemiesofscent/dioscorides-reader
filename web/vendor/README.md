> **Doc:** Dioscorides reader vendored libraries · **Version:** 1.0 · **Updated:** 2026-09-12 · **Status:** active
> **Context:** Third-party code committed for offline use by the reader. No CDN dependencies.

# Vendored libraries

## openseadragon/

- **OpenSeadragon 5.0.1** — deep-zoom image viewer (IIIF Image API v2/v3 + plain images).
- Source: https://github.com/openseadragon/openseadragon/releases/download/v5.0.1/openseadragon-bin-5.0.1.zip
- License: BSD-3-Clause (see `openseadragon/LICENSE.txt`).
- Files kept: `openseadragon.min.js`, `images/` (navigation button sprites — the
  viewer's `prefixUrl` points here), `LICENSE.txt`.
- Update procedure: download a newer release zip, replace the same three items, bump
  this README's header.
