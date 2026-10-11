"""Vendor the concordance's edition_of rows at one commit, with their lock.

    python scripts/vendor_concordance.py CONCORDANCE_CHECKOUT COMMIT

Reads links.tsv at COMMIT (git show) and keeps the rows with relation edition_of, in the columns
urn_a, relation, urn_b, status only: this repository is public and the concordance is private, so
its evidence and notes stay there, and the rows of in-copyright editions (PRIVATE) are left out, as are
rows whose other end is neither Wellmann's Dioscorides (the reader pairs through Wellmann) nor the
pseudo-Dioscorides treatises on poisons (tlg1118.tlg001-002, which Mattioli's Book 6 renders: Sean, 2026-10-11).
Those go to their own file, concordance/edition_of_tlg1118.tsv: the reader reads them only in a build given the
treatises' Greek (a TLG text, never in a public build), and their offsets count the words of the treatise's
chapter as w_from and w_to count Wellmann's.
A link to part of a Wellmann chapter (a section, a run of sections, a span of words: Sean,
2026-10-09) also gets w_from and w_to, the words of the chapter it covers, and a span (on either side) its
first three words (a_lead, w_lead), by which the reader finds it on the page (0-based, end exclusive,
as the concordance's tools/tokens.py cuts the pinned text; empty for a whole chapter), so that the
reader pairs two parts only where they overlap. These are computed with the concordance's own
tools/editions/sections.py, so the checkout must be at COMMIT with its local sources configured.
Writes concordance/edition_of.tsv, concordance/edition_of_tlg1118.tsv and concordance.lock.json
(repository, commit, sha256 of links.tsv and of the vendored rows of each file).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ("beck2020",)
WELLMANN = "urn:cts:greekLit:tlg0656.tlg001.wellmann1906:"
VENENIS = ("urn:cts:greekLit:tlg1118.tlg001.", "urn:cts:greekLit:tlg1118.tlg002.")
COLUMNS = ("urn_a", "relation", "urn_b", "status")
SPAN = ("w_from", "w_to", "a_lead", "w_lead")
LEAD = 3


def text_id(S, urn):
    """The manifest id of the text a URN names, by work and version (sprengel1830 names the commentary
    on Dioscorides and the treatises on poisons alike)."""
    work, version = urn.split(":")[3].rsplit(".", 1)
    work = "urn:cts:greekLit:" + work
    return next(m["id"] for m in S.U.manifest() if m["work"] == work and m["version"] == version)


def unit_offsets(S, T, urn):
    """(from, to) words of a treatise's chapter that a span of it covers; ("", "") for the whole chapter."""
    head, _, sub = urn.rsplit(":", 1)[1].partition("@")
    if not sub:
        return "", ""
    i, j = T.span(T.tokens(S.U.reading(S.index(text_id(S, urn))[head])), sub)
    return str(i), str(j + 1)


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


def lead(S, T, urn):
    """The first words of a subreference's span (the reader finds a part by them), or ""."""
    head, _, sub = urn.rsplit(":", 1)[1].partition("@")
    if not sub:
        return ""
    words = T.tokens(S.U.reading(S.index(text_id(S, urn))[head]))
    i, _ = T.span(words, sub)
    return " ".join(f for _, _, f in words[i:i + LEAD])


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
    rows, venenis = [], []
    for line in lines[1:]:
        cells = line.split("\t")
        if cells[1] != "edition_of" or any(f".{v}:" in cells[0] for v in PRIVATE):
            continue
        target = cells[idx[2]]
        if target.startswith(VENENIS):        # Mattioli's Book 6 -> the treatises on poisons
            span = unit_offsets(S, T, target)
            into = venenis
        elif WELLMANN in target:
            span = offsets(S, T, target.rsplit(":", 1)[1])
            into = rows
        else:
            continue
        leads = (lead(S, T, cells[idx[0]]), lead(S, T, target))
        into.append("\t".join([*(cells[i] for i in idx), *span, *leads]) + "\n")
    out = ROOT / "concordance"
    out.mkdir(exist_ok=True)
    data = ("\t".join(COLUMNS + SPAN) + "\n" + "".join(rows)).encode("utf-8")
    (out / "edition_of.tsv").write_bytes(data)
    vdata = ("\t".join(COLUMNS + SPAN) + "\n" + "".join(venenis)).encode("utf-8")
    (out / "edition_of_tlg1118.tsv").write_bytes(vdata)
    lock = {"schema_version": 1, "repository": "alchemiesofscent/concordance", "commit": full,
            "links_sha256": hashlib.sha256(links).hexdigest(), "vendored": "concordance/edition_of.tsv",
            "rows": len(rows), "columns": list(COLUMNS + SPAN), "excluded_versions": list(PRIVATE),
            "edition_of_sha256": hashlib.sha256(data).hexdigest(),
            "tlg1118": {"vendored": "concordance/edition_of_tlg1118.tsv", "rows": len(venenis),
                        "sha256": hashlib.sha256(vdata).hexdigest()}}
    (ROOT / "concordance.lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} edition_of rows and {len(venenis)} to the treatises on poisons from {full[:12]}")


if __name__ == "__main__":
    main(*sys.argv[1:])
