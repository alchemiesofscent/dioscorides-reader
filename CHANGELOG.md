# Changelog

Versions of the reader software. The corpus it displays is versioned separately:
each build records its pinned edition-workbench bundle in `corpus.lock.json` and
shows it beside the reader version under **Reading settings**. Release tags
`v<version>` are created automatically after deployment (see README, "Versions").

While the reader is in alpha, a minor version (0.x.0) adds or reorganises how people read;
a patch version (0.x.y) fixes behaviour without changing the layout.

## 0.8.0-alpha — 2026-10-09

- **Wellmann shows its printed structure.** Editorial additions appear in angle brackets
  ⟨ ⟩ and deletions in square brackets [ ], as Wellmann prints them; the printed chapter
  numerals stand on their line; the printed marginal section numbers sit in the margin
  beside their line.
- A **Chapter numerals** switch in the toolbar and mobile menu hides or shows the printed
  chapter numerals in the running text; they are shown by default. Numbers that belong to
  a chapter heading (Sprengel, Mattioli, Gunther) always stay.
- Corpus corpus-0a3620f2bc9b715b (edition-workbench 86256ba0). Paul of Aegina VII is in
  the corpus but not yet in the public build (no reader adapter yet).

## 0.7.0-alpha — 2026-10-09

- **Gunther 1934 has its facsimile.** Every chapter opens on its printed page, and the
  arrows turn the 728 pages of the scan. The images are published with the site, pinned in
  `facsimiles.lock.json` (a release asset of this repository, checked against its sha256 when
  the site is built). They are a second input beside `corpus.lock.json`, because no public image
  service holds this scan. Copyright: see README, "Facsimiles".

## 0.6.0-alpha — 2026-10-08

- New edition: **Gunther 1934 (Goodyer's English, 1655)**, *The Greek Herbal of Dioscorides*.
  It has John Goodyer's English with Gunther's identifications in the chapter heads and his
  footnotes. The front matter, each book's preface, Daubeny's appendix and the two indexes are
  sections. It is paired with every other edition through Wellmann. The text is read from the
  scans and is not yet reviewed; there is no facsimile.
- Sections after the last book (the back matter) get routes of their own, as the front matter
  already does.
- The Mattioli corpus update gives each chapter one commentary section (no split commentary).

## 0.5.1-alpha — 2026-10-08

- If a section exists in only one of the two editions (Mattioli's dedication, Berendes' index,
  a book preface the Sprengel commentary lacks), the other pane now says there is no
  counterpart instead of "not in this edition".

## 0.5.0-alpha — 2026-10-08

- **Chapters pair through Wellmann.** Before this, the second pane showed whatever chapter had
  the same number. Now each edition maps its chapters to Wellmann's, using the concordance's
  `edition_of` links: Mattioli, Sprengel 1829 (Greek and Latin), the Sprengel 1830 commentary
  and Berendes (German and English). The other pane shows the chapter or chapters that render
  the same Dioscorides text. For example:
  - Wellmann 1.43 (ῥόδινον) is Berendes 1.53 and Mattioli 1.42.
  - Wellmann 1.68 (λίβανος) is Mattioli 1.70–1.73.

  A line above the paired text says which chapters are shown, or that there is no
  counterpart. The pairing is proposed, not yet checked.
- **Wellmann's table of contents has the right titles.** It used to take Sprengel's chapter
  titles by number. Now each Wellmann chapter takes the title of the Sprengel chapter that
  corresponds to it.
- **Where the rows come from.** `concordance/edition_of.tsv`, pinned by `concordance.lock.json`,
  holds only chapter keys and status, without evidence or notes, and leaves out Beck, which is in
  copyright. Beck pairs by its own numbering, which is Wellmann's.

## 0.4.0-alpha — 2026-10-08

- New edition: **Mattioli 1554 (English, machine translation)**. It is an English translation of
  the whole Latin text except the Index and Errata, built block for block on the Latin, with
  the same chapters, prefaces and front-matter sections. It can be read side by side with
  the Latin. Its blocks are labelled **Dioscorides** and **Commentary**, and its sections are
  named in English: Preface, Title page, Dedication, Privileges, The printer to the reader.
  The page links are approximate. The translation is unreviewed and not accepted.

## 0.3.1-alpha — 2026-10-08

- Mattioli's commentary is set upright. It is still marked off by its **Commentarius** label,
  smaller size and side rule.
- Mattioli's sections carry the usual names: each book opens with its **Praefatio**, and the
  front matter lists Titulus, Dedicatio, Praefatio, Privilegia, Typographus lectori, Errata and
  Index.

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
