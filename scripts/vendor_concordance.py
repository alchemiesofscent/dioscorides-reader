"""Vendor the concordance's edition_of rows at one commit, with their lock.

    python scripts/vendor_concordance.py CONCORDANCE_CHECKOUT COMMIT

Reads links.tsv at COMMIT (git show) and keeps the rows with relation edition_of, in the columns
urn_a, relation, urn_b, status only: this repository is public and the concordance is private, so
its evidence and notes stay there, and the rows of in-copyright editions (PRIVATE) are left out.
A link to part of a Wellmann chapter (a section, a run of sections, a span of words: Sean,
2026-10-09) also gets w_from and w_to, the words of the chapter it covers (0-based, end exclusive,
as the concordance's tools/tokens.py cuts the pinned text; empty for a whole chapter), so that the
reader pairs two parts only where they overlap. These are computed with the concordance's own
tools/editions/sections.py, so the checkout must be at COMMIT with its local sources configured.
Writes concordance/edition_of.tsv and concordance.lock.json (repository, commit, sha256 of
links.tsv and of the vendored rows).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ("beck2020",)
COLUMNS = ("urn_a", "relation", "urn_b", "status")
SPAN = ("w_from", "w_to")


def offsets(S, T, passage):
    """(from, to) words of the Wellmann chapter that a passage (chapter, section, range, span) covers."""
    head, _, sub = passage.partition("@")
    a, _, b = head.partition("-") if not sub else (head, "", "")
    chapter = ".".join(a.split(".")[:2])
    if a == chapter and not b and not sub:
        return "", ""
    toks, starts = S.wellmann(chapter)
    unit = {p: (s, s + len(st), st) for p, s, st in starts}
    if sub:
        base, words = (0, toks) if a == chapter else (unit[a][0], unit[a][2])
        i, j = T.span(words, sub)
        return str(base + i), str(base + j + 1)
    return str(unit[a][0]), str(unit[b or a][1])


def main(checkout, commit):
    full = subprocess.run(["git", "-C", checkout, "rev-parse", commit], check=True, capture_output=True,
                          text=True).stdout.strip()
    head_commit = subprocess.run(["git", "-C", checkout, "rev-parse", "HEAD"], check=True, capture_output=True,
                                 text=True).stdout.strip()
    if head_commit != full:
        sys.exit(f"the checkout is at {head_commit[:12]}, not {full[:12]}: its tools must be those of COMMIT")
    sys.path[:0] = [str(Path(checkout) / "tools"), str(Path(checkout) / "tools" / "editions")]
    import sections as S  # noqa: E402  (the concordance's)
    import tokens as T  # noqa: E402
    links = subprocess.run(["git", "-C", checkout, "show", f"{full}:links.tsv"], check=True,
                           capture_output=True).stdout
    lines = links.decode("utf-8").splitlines()
    head = lines[0].split("\t")
    idx = [head.index(c) for c in COLUMNS]
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        if cells[1] != "edition_of" or any(f".{v}:" in cells[0] for v in PRIVATE):
            continue
        span = offsets(S, T, cells[idx[2]].rsplit(":", 1)[1])
        rows.append("\t".join([*(cells[i] for i in idx), *span]) + "\n")
    data = ("\t".join(COLUMNS + SPAN) + "\n" + "".join(rows)).encode("utf-8")
    out = ROOT / "concordance" / "edition_of.tsv"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(data)
    lock = {"schema_version": 1, "repository": "alchemiesofscent/concordance", "commit": full,
            "links_sha256": hashlib.sha256(links).hexdigest(), "vendored": "concordance/edition_of.tsv",
            "rows": len(rows), "columns": list(COLUMNS + SPAN), "excluded_versions": list(PRIVATE),
            "edition_of_sha256": hashlib.sha256(data).hexdigest()}
    (ROOT / "concordance.lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} edition_of rows from {full[:12]}")


if __name__ == "__main__":
    main(*sys.argv[1:])
