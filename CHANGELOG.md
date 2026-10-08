# Changelog

Versions of the reader software. The corpus it displays is versioned separately:
each build records its pinned edition-workbench bundle in `corpus.lock.json` and
shows it beside the reader version under **Reading settings**. Release tags
`v<version>` are created automatically after deployment (see README, "Versions").

While the reader is in alpha, a minor version (0.x.0) adds or reorganises how people read;
a patch version (0.x.y) fixes behaviour without changing the layout.

## 0.3.0-alpha — 2026-10-08

Mattioli 1554 (Latin, with commentary), review pending, not accepted.

- Each chapter shows Dioscorides' text and Mattioli's commentary as two labelled blocks:
  **Dioscorides** in upright type, then **Commentarius** in italic as printed, with a rule
  beside it. Words printed upright inside the commentary stay upright.
- The leaves before Book 1 (title page, dedication, preface, privileges, index) are listed as
  **Front matter**. Each book's prefaces and closing lines are entries in the contents, in
  reading order.
- Expansions show the supplied letters dimmed. Marginal notes appear in small brackets where
  they stand, woodcuts as ❦ with their caption, and illegible letters as […].
- Facsimiles open the Wellcome Collection page images.
- Side-by-side pairing goes by chapter number. Mattioli's numbering is his own, so his
  chapters do not line up with Wellmann's or Sprengel's.

## 0.2.1-alpha — 2026-10-07

- A chapter that opens with its own page break no longer also lists the page before it, so
  the facsimile opens on the right page. Affected: the Sprengel 1829 praefatio (Greek and
  Latin; it opened one leaf early), Berendes English 1.46, 5.5, 5.28, 5.41, 5.64 and 5.80,
  and the Berendes Sachregister. Text is unchanged.

## 0.2.0-alpha — 2026-10-07

Reading on phones and small tablets (up to 900px wide).

- One edition at a time, with a **1/2** button in the bottom bar to swap between the left
  (primary) and right (comparison) edition. Routes are unchanged, so a link opens the same
  pair on any device.
- Bottom navigation bar: menu, previous chapter, current chapter (tap for contents), next
  chapter, facsimile. While the facsimile is open, the arrows turn its pages instead.
- Menu drawer with both edition pickers, Pages, Lineation, Page furniture and reading settings.
- Contents drawer with a filter that matches chapter numbers and titles, ignoring accents.
- Notes and apparatus open as a sheet above the bottom bar; focus returns to the note mark
  when it closes.
- Facsimile fills the screen, with pinch, double-tap and drag gestures.
- 44px touch targets, a skip link to the text, and focus kept inside open drawers.

Every width:

- **Reading settings**: text size and a night theme. These and the last reading position
  (route and scroll) are kept in the browser on this device only.
- The settings panel shows the reader version and the pinned corpus bundle.
- Clicking outside a note closes it; Escape closes a note before anything else.

Desktop keeps facing pages, the contents rail and the facsimile side pane. The controls
are the same as before, now in one top bar that wraps on narrower screens.

## 0.1.0-alpha — 2026-10-07

The first public reader, at <https://alchemiesofscent.github.io/dioscorides-reader/>.
Tagged retrospectively at the state deployed before the phone layout.

- Parallel reading of Wellmann 1906, Sprengel 1829 (Greek and Latin), Sprengel's 1830
  commentary (Latin, with a draft English translation) and Berendes 1902 (German, with
  English), built from one pinned edition-workbench corpus release.
- Notes, critical apparatus and commentary in popovers; a chapter's Notes section lists the
  notes its own marks cite; printer's errors shown as printed, with the correction on hover;
  Sperrdruck shown.
- Lineation and page-furniture views; page breaks linked to facsimiles from Archive.org,
  Heidelberg and the BBAW.
- Sprengel 1829 page view preserving physical lines, linked to chapter routes, with note
  markers linked to their notes.
- Berendes front matter, errata and Sachregister (German and English), with a filter.
- Source and credits from the verified TEI headers.
- Public build without Beck 2020 (in copyright), deployed to GitHub Pages from `main`.
- Chapters are paired by equal chapter number: provisional, not a scholarly concordance.
