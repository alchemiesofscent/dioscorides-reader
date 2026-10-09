# Changelog

Versions of the reader software. The corpus it displays is versioned separately:
each build records its pinned edition-workbench bundle in `corpus.lock.json` and
shows it beside the reader version under **Reading settings**. Release tags
`v<version>` are created automatically after deployment (see README, "Versions").

While the reader is in alpha, a minor version (0.x.0) adds or reorganises how people read;
a patch version (0.x.y) fixes behaviour without changing the layout.

## 0.10.2-alpha — 2026-10-09

- "Only the matching part" is now an on/off switch, above the part and in Reading settings. It is
  remembered for all panes and later chapters.
- A part shown alone keeps the punctuation after its last word (the final full stop was lost).
- Corpus 38085b0b: Sean's Gunther corrections (footnote Greek in 1.38; 5·76 pints in the 1.32 note;
  Gunther's comment after 1.51 as a note; Iasmelaion as chapter 1.76a; the section heading "Dakrua. Tears or
  gums of trees"), and the Sprengel 1830 commentary's restored chapter boundaries.

## 0.10.1-alpha — 2026-10-09

- A part of a chapter is found by its first words together, not by one word and its count. 0.10.0 could
  land on the wrong occurrence where the texts cut words differently: beside Wellmann 1.5, Gunther
  showed the whole of 1.4 instead of its last part. If a part's first words can't be found, the whole
  chapter is shown, never a wrong part. 1,130 of 1,165 partial links are now shown as parts.

## 0.10.0-alpha — 2026-10-09

- **Only the matching part is shown.** When the chapter on the left renders part of a chapter on the right,
  the right pane shows just that part, with "show the whole chapter" above it.
  - Gunther 1.52 is Wellmann 1.42.2, so Wellmann shows §2.
  - Beside Wellmann 1.5, Gunther, Berendes, Mattioli and Sprengel show only the end of their chapter 1.4.
  - Word spans inside a section work too: Sprengel 1.35 beside Wellmann 1.30.6.
  - The part is found by its first words in the page. Where they can't be found (about 3%, and in
    Sprengel's Latin stream, which has no word spans of its own), the whole chapter is shown, as before.

## 0.9.1-alpha — 2026-10-09

- **No Wellmann chapter is skipped where an edition joins two.** Wellmann 1.4 and 1.5 are one chapter in
  the other editions. Each Wellmann chapter is now linked to its part of that chapter, so Wellmann 1.5
  shows Gunther, Berendes, Mattioli and Sprengel 1.4 (concordance 185ebb4). The same holds across the
  work, with three passages found in other places: Wellmann 2.7 is in Sprengel 2.4, and 4.16 and 4.180
  are also printed in Sprengel 4.99 and 4.7.

## 0.9.0-alpha — 2026-10-09

- **Chapters pair by Wellmann's sections.** Where an edition divides a Wellmann chapter into several
  chapters, each part is now linked to the sections it renders, or to a span of words. It pairs
  only with the parts of other editions that render the same text. Example: Mattioli 1.40 =
  Wellmann 1.42.1 = Gunther 1.51 (mastic oil), and Mattioli 1.41 = Wellmann 1.42.2 = Gunther 1.52.
  Before, both were shown against both. The note above the pane names the section. 92 Wellmann
  chapters are affected (concordance d8c6767, which also corrects 18 links). The vendored rows
  carry each link's word range in Wellmann (`w_from`, `w_to`), and nothing else new.

## 0.8.1-alpha — 2026-10-09

- Corpus 91dd9bab (Gunther 1934 corrections). Every printed footnote mark in Gunther is a link
  to its note. The 396 woodcuts carry their printed captions. The garbled OCR (bookplate, stamps,
  the handwritten plate, noise) is gone. Daubeny's appendix and Saracen's index are re-read from
  the scans, with the Greek in Greek letters.

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
