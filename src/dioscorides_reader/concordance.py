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

Mattioli's Book 6 renders the pseudo-Dioscorides treatises on poisons (tlg1118.tlg001, De venenis; tlg1118.tlg002,
De venenatis animalibus), not Wellmann. Those rows are vendored apart (concordance/edition_of_tlg1118.tsv) and read
only when the build includes the treatises' Greek (a TLG text: private builds only). They pair through keys of
their own, V1.n and V2.n, which no Wellmann chapter has; the treatises' stream maps its chapters 1.n and 2.n to them
(venenis_pairing).
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
VENENIS = {"urn:cts:greekLit:tlg1118.tlg001.": ("V1", "De venenis"),
           "urn:cts:greekLit:tlg1118.tlg002.": ("V2", "De venenatis animalibus")}


def split(urn: str) -> tuple[str, str]:
    """(version, passage) of a Dioscorides URN."""
    if not urn.startswith(PREFIX) or ":" not in urn[len(PREFIX):]:
        raise ValueError(f"Not a Dioscorides passage URN: {urn}")
    version, passage = urn[len(PREFIX):].split(":", 1)
    return version, passage


def venenis_target(urn: str) -> tuple[str, str, str]:
    """(pivot key, passage, label) of a passage of the treatises on poisons: tlg1118.tlg002.sprengel1830:2@a[1]-b[1]
    is V2.2, 2@a[1]-b[1], "De venenatis animalibus 2 (part)"."""
    for prefix, (book, title) in VENENIS.items():
        if urn.startswith(prefix) and ":" in urn[len(prefix):]:
            passage = urn[len(prefix):].split(":", 1)[1]
            head, at, _ = passage.partition("@")
            return f"{book}.{head}", passage, f"{title} {head}" + (" (part)" if at else "")
    raise ValueError(f"Not a passage of the treatises on poisons: {urn}")


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


def selector(passage: str, chapter: str, lead: str = "") -> dict | None:
    """What part of a chapter a passage names, for the reader to show only that part: {"from", "to"} section
    labels (1.42.2, 1.105.1-1.105.5), {"section", "sub"} (1.30.6@a[2]-b[2]), {"sub"} (1.30@a[1]-b[1]), or
    {"unit", "sub"} for a named block of an edition's chapter (Mattioli's 1.4.translation@...); None: whole."""
    head, _, sub = passage.partition("@")
    if sub:
        found = {"sub": sub, "lead": lead.split()} if lead else {"sub": sub}
        if head == chapter:
            return found
        rest = head[len(chapter) + 1:]
        return {"unit": rest, **found} if not rest[:1].isdigit() else {"section": rest, **found}
    if head == chapter:
        return None
    a, _, b = head.partition("-")
    return {"from": a[len(chapter) + 1:], "to": (b or a)[len(chapter) + 1:]}


def vendored(lock_path: Path, path: str, sha256: str, count: int) -> list[dict]:
    """The rows of one vendored file, checked against its lock entry."""
    data = (lock_path.parent / path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"Vendored concordance rows differ from concordance.lock.json: {path}")
    rows = list(csv.DictReader(data.decode("utf-8").splitlines(), delimiter="\t"))
    if len(rows) != count:
        raise ValueError(f"Vendored concordance row count differs from concordance.lock.json: {path}")
    return rows


def load(lock_path: Path = LOCK, venenis: bool = False) -> dict | None:
    """{version: {"to_wellmann": {key: [wellmann keys]}, "status": ...}} from the pinned rows;
    None when no concordance is pinned (every edition then pairs by identical key). venenis: also the
    rows to the treatises on poisons, for a build that includes their Greek."""
    if not lock_path.exists():
        return None
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    rows = vendored(lock_path, lock["vendored"], lock["edition_of_sha256"], lock["rows"])
    extra = lock.get("tlg1118")
    if venenis:
        if not extra:
            raise ValueError("The build includes the treatises on poisons but no rows to them are vendored")
        rows += vendored(lock_path, extra["vendored"], extra["sha256"], extra["rows"])
    out: dict[str, dict] = {}
    for row in rows:
        if row["relation"] != "edition_of":
            raise ValueError(f"Unexpected relation in vendored concordance rows: {row['relation']}")
        version, key = split(row["urn_a"])
        part = None
        if "@" in key:          # part of the edition's chapter (Mattioli's 1.4.translation@...): the chapter pairs
            part, key = key, wellmann_chapter(key)
        if row["urn_b"].startswith(PREFIX):
            target, passage = split(row["urn_b"])
            if target != WELLMANN:
                raise ValueError(f"edition_of must point into Wellmann: {row['urn_b']}")
            wkey, label = wellmann_chapter(passage), wellmann_label(passage)
        else:
            wkey, passage, label = venenis_target(row["urn_b"])
            passage = wkey + passage[len(wkey.split(".", 1)[1]):]      # 2@a[1]-b[1] -> V2.2@a[1]-b[1]
        entry = out.setdefault(version, {"to_wellmann": {}, "spans": {}, "parts": {}, "statuses": set()})
        if part:
            entry["parts"].setdefault(key, {})[wkey] = selector(part, key, row.get("a_lead") or "")
        targets = entry["to_wellmann"].setdefault(key, [])
        if wkey not in targets:
            targets.append(wkey)
        start, end = row.get("w_from") or None, row.get("w_to") or None
        entry["spans"].setdefault(key, []).append(
            [wkey, int(start) if start else None, int(end) if end else None, label,
             selector(passage, wkey, row.get("w_lead") or "")])
        entry["statuses"].add(row["status"])
    for version, entry in out.items():
        # only chapters linked to part of a Wellmann chapter need their spans (a whole chapter overlaps all)
        entry["spans"] = {k: v for k, v in entry["spans"].items() if any(x[1] is not None for x in v)}
        if not entry["parts"]:
            del entry["parts"]
        statuses = entry.pop("statuses")
        entry["status"] = "checked" if statuses == {"checked"} else "proposed"
        entry["source"] = {"repository": lock["repository"], "commit": lock["commit"]}
    return out


def venenis_pairing(edition: dict, pairings: dict | None) -> dict:
    """The treatises' stream pairs its chapter n of treatise 1 or 2 (book 1, 2) through V1.n, V2.n; "target": it is
    shown, as Wellmann is, in the part that the other edition's chapter renders."""
    statuses = {pairings[v]["status"] for v in pairings or {} if any(
        w.startswith("V") for ws in pairings[v]["to_wellmann"].values() for w in ws)}
    return {"to_wellmann": {f"{book['n']}.{c['n']}": [f"V{book['n']}.{c['n']}"]
                            for book in edition["books"] for c in book["chapters"]},
            "target": True, "status": "checked" if statuses == {"checked"} else "proposed"}


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
