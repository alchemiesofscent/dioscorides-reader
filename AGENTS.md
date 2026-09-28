# Working instructions — dioscorides-reader

This repository builds the static parallel reader of Dioscorides' *De materia
medica*: editions side by side, notes, apparatus, facsimiles and the Sprengel
page view. It builds only from the edition-workbench release bundle pinned in
`corpus.lock.json`, never from source files, and it never edits or accepts a
text. How to build and test is in `README.md`. In the project site it becomes
the Dioscorides editions part, with witness pages, in the September design
(checklist items 4.1, 4.2 and 7.7).

## Working rules (the same in every Alchemies of Scent repository)

- One person works here, Sean Coughlin. Scholarly decisions (readings,
  identifications, translations, what counts as an ingredient, accepting a
  text) are his; agents prepare the evidence and a concrete proposal.
- Work on `main`, one change per commit. Pull (with rebase) before starting and
  before pushing, and end every session committed and pushed. No branches,
  pull requests or worktrees: a session that starts on a branch brings its
  commits onto `main` and deletes the branch, or says so when it cannot.
- One writer per repository at a time.
- Run this repository's checks before every commit. The commit message says
  what changed, how it was checked and what comes next.
- Git is the history: no new version headers, archive copies, changelogs,
  status files or process documents unless Sean asks. Existing ones stay as
  they are.
- The project has one checklist: `HANDOFF.md` in
  [aos-perfume-corpus](https://github.com/alchemiesofscent/aos-perfume-corpus).
  This repository's items are listed there; tick them there when done.
- Nothing is published without Sean's decision.

## Rules of this repository

- Keep `corpus.lock.json` as the only input; a new bundle is a new pin.
- Beck 2020 is in copyright: it may appear in private builds only, and never
  in anything published.
- Deployment is Sean's decision.

## Checks (run before committing)

- `.venv/bin/python -m pytest` (it also runs the Node checks when Node.js is
  available).

## History

This repository used to defer to an orchestrator in edition-workbench, with
ownership claims and assigned paths. That process is retired. The branch
`experiment/edition-alignment` is an open question for Sean: bring it onto
`main` or drop it.
