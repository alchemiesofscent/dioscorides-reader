# Experiment: aligning Dioscorides editions automatically

**Date:** 2026-09-12. **Status:** experiment, not wired into the reader.

## Question

The reader pairs editions by equal chapter number, which is wrong wherever the
editions chapter the text differently (Wellmann 1.52 sousinon is Sprengel 1.62 and
Berendes Cap. 62). Can the concordance be derived automatically, so that no one
checks 900 chapter rows by hand?

## Method

Editions of the same Greek text align like sequences with mutations, so the
concordance is read off a sequence alignment rather than authored.

1. **Greek against Greek (Wellmann against Sprengel 1829).** Each book becomes a
   stream of accent-stripped tokens, apparatus, notes and headings excluded. The
   two streams are globally aligned (`difflib`, no junk heuristic). Every Wellmann
   chapter's tokens are looked up in the alignment; the Sprengel chapters they land
   in, with mutual coverage, give the relation: `same`, `contains`, `contained-in`,
   `overlaps`, `absent`. Short chapters the global alignment skipped are recovered
   by local vocabulary overlap inside the window between their neighbours.
   Because the alignment is token-level, any smaller unit (a section, a quotation)
   maps to a token span in the other edition.
2. **Translations (Beck 2020, Berendes 1902).** Token identity does not cross
   languages, but both translations print the Greek chapter heading. The chapter
   sequences are aligned (Needleman-Wunsch) on heading stems against their base
   edition: Beck against Wellmann's chapter openings, Berendes against Sprengel's
   chapter table, then chained through step 1.

Run from a workbench checkout (all five books take about fifteen seconds):

```bash
cd /path/to/edition-workbench
ALIGN_OUT=build/alignment/ python3 /path/to/dioscorides-reader/experiments/edition-alignment/run_all_books.py
python3 /path/to/dioscorides-reader/experiments/edition-alignment/align_translation_headings.py
```

## Result, workbench commit 07ace103

| Wellmann to Sprengel | chapters |
|---|---|
| same | 597 |
| contains | 168 |
| contained-in | 148 |
| overlaps | 29 |
| absent after fallback | 9 |

Pilot chapters 1.43, 1.52 and 1.56 are one-to-one with Sprengel 53, 62 and 66,
and their sections map to token spans inside those chapters. Where Sprengel
splits a Wellmann chapter, the splits fall where the perfume corpus split its
recipe units (Wellmann 1.30 contains Sprengel 29 to 36; 1.58 contains 68 to 70).

Translations: 1,648 chapters placed by heading, 91 by position only, 55 unplaced.
The unplaced ones are real features: Wellmann's argumenta, RV-recension chapters,
and the extra chapter blocks Berendes carries in Books 2 and 5.

## Conclusion

- The concordance is generated output, rebuilt from the pinned bundle, with a
  relation, score and evidence on every row. Nobody edits it.
- The test of the alignment is a viewer that shows the two texts side by side
  along the alignment, not a table. Reviewing thousands of rows is not a task
  for a person. When the reader adopts this, it replaces provisional
  chapter-key pairing and the parallel view itself exposes any misalignment.
- Exceptions (about 150) mostly need a label, not a decision: "argumentum, no
  counterpart", "RV recension", "extra chapter in this translation".

Deferred until the perfume corpus pilot has its first recipe page.
