"""Chapter pairing through Wellmann, from the concordance's edition_of links.

The concordance (alchemiesofscent/concordance) links each chapter of an edition or
translation of Dioscorides to the Wellmann chapter(s) it renders: rows of links.tsv
with relation edition_of, urn_a in the edition (version = the edition's name), urn_b
in Wellmann (version wellmann1906). Those rows are vendored here as
concordance/edition_of.tsv and bound by concordance.lock.json (concordance commit,
sha256 of the vendored rows), because the Pages build has no access to that
repository. An edition without rows pairs by identical chapter key, as before.

A link may go to part of a Wellmann chapter (a section 1.42.1, a run 1.105.1-1.105.5, a span of
words 1.30.6@first[n]-last[n]: Sean, 2026-10-09); its row then carries w_from and w_to, the words
of the chapter it covers. An edition's chapter that renders several Wellmann chapters is linked to
each by a span of its own words (urn_a ...:1.4@first[n]-last[m]); it pairs as the chapter 1.4.
to_wellmann keeps the chapter keys; spans adds, per chapter of the
edition, [Wellmann chapter, from, to, label] (from and to None for a whole chapter), so that two
parts of one Wellmann chapter pair only where they overlap.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "concordance.lock.json"
WELLMANN = "wellmann1906"
PREFIX = "urn:cts:greekLit:tlg0656.tlg001."


def split(urn: str) -> tuple[str, str]:
    """(version, passage) of a Dioscorides URN."""
    if not urn.startswith(PREFIX) or ":" not in urn[len(PREFIX):]:
        raise ValueError(f"Not a Dioscorides passage URN: {urn}")
    version, passage = urn[len(PREFIX):].split(":", 1)
    return version, passage


def wellmann_chapter(passage: str) -> str:
    """The Wellmann chapter of a passage: 1.42.1, 1.105.1-1.105.5 and 1.30.6@a[1]-b[1] are in 1.42, 1.105, 1.30."""
    return ".".join(passage.split("@")[0].split("-")[0].split(".")[:2])


def wellmann_label(passage: str) -> str:
    """How a target is shown: 1.42.1, 1.105.1-5, 1.30.6 (part)."""
    head, at, _ = passage.partition("@")
    a, dash, b = head.partition("-")
    if dash and a.rsplit(".", 1)[0] == b.rsplit(".", 1)[0]:
        head = f"{a}-{b.rsplit('.', 1)[1]}"
    return head + (" (part)" if at else "")


def selector(passage: str, chapter: str) -> dict | None:
    """What part of a chapter a passage names, for the reader to show only that part: {"from", "to"} section
    labels (1.42.2, 1.105.1-1.105.5), {"section", "sub"} (1.30.6@a[2]-b[2]), {"sub"} (1.30@a[1]-b[1]), or
    {"unit", "sub"} for a named block of an edition's chapter (Mattioli's 1.4.translation@...); None: whole."""
    head, _, sub = passage.partition("@")
    if sub:
        if head == chapter:
            return {"sub": sub}
        rest = head[len(chapter) + 1:]
        return {"unit": rest, "sub": sub} if not rest[:1].isdigit() else {"section": rest, "sub": sub}
    if head == chapter:
        return None
    a, _, b = head.partition("-")
    return {"from": a[len(chapter) + 1:], "to": (b or a)[len(chapter) + 1:]}


def load(lock_path: Path = LOCK) -> dict | None:
    """{version: {"to_wellmann": {key: [wellmann keys]}, "status": ...}} from the pinned rows;
    None when no concordance is pinned (every edition then pairs by identical key)."""
    if not lock_path.exists():
        return None
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    path = lock_path.parent / lock["vendored"]
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != lock["edition_of_sha256"]:
        raise ValueError("Vendored concordance rows differ from concordance.lock.json")
    out: dict[str, dict] = {}
    rows = list(csv.DictReader(data.decode("utf-8").splitlines(), delimiter="\t"))
    for row in rows:
        if row["relation"] != "edition_of":
            raise ValueError(f"Unexpected relation in vendored concordance rows: {row['relation']}")
        version, key = split(row["urn_a"])
        part = None
        if "@" in key:          # part of the edition's chapter (Mattioli's 1.4.translation@...): the chapter pairs
            part, key = key, wellmann_chapter(key)
        target, passage = split(row["urn_b"])
        if target != WELLMANN:
            raise ValueError(f"edition_of must point into Wellmann: {row['urn_b']}")
        wkey = wellmann_chapter(passage)
        entry = out.setdefault(version, {"to_wellmann": {}, "spans": {}, "parts": {}, "statuses": set()})
        if part:
            entry["parts"].setdefault(key, {})[wkey] = selector(part, key)
        targets = entry["to_wellmann"].setdefault(key, [])
        if wkey not in targets:
            targets.append(wkey)
        start, end = row.get("w_from") or None, row.get("w_to") or None
        entry["spans"].setdefault(key, []).append(
            [wkey, int(start) if start else None, int(end) if end else None, wellmann_label(passage),
             selector(passage, wkey)])
        entry["statuses"].add(row["status"])
    if len(rows) != lock["rows"]:
        raise ValueError("Vendored concordance row count differs from concordance.lock.json")
    for version, entry in out.items():
        # only chapters linked to part of a Wellmann chapter need their spans (a whole chapter overlaps all)
        entry["spans"] = {k: v for k, v in entry["spans"].items() if any(x[1] is not None for x in v)}
        if not entry["parts"]:
            del entry["parts"]
        statuses = entry.pop("statuses")
        entry["status"] = "checked" if statuses == {"checked"} else "proposed"
        entry["source"] = {"repository": lock["repository"], "commit": lock["commit"]}
    return out


def pairing_for(config: dict, table: dict | None) -> dict | None:
    """The manifest's pairing record for one reader stream, or None (identical keys)."""
    version = config.get("concordance")
    if not version or table is None:
        return None
    if version not in table:
        raise ValueError(f"No concordance rows for {config['key']} (version {version})")
    return table[version]


def relabel(table: dict, pairings: dict | None, version: str) -> dict:
    """A chapter table keyed by Wellmann: each Wellmann chapter gets the row of the first chapter
    of `version` (whose numbering the table follows) paired with it. Without rows: the table."""
    if not pairings or version not in pairings:
        return table
    out: dict = {}
    for key, targets in pairings[version]["to_wellmann"].items():
        for w in targets:
            if w not in out and key in table:
                out[w] = table[key]
    return out
