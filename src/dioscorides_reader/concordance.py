"""Chapter pairing through Wellmann, from the concordance's edition_of links.

The concordance (alchemiesofscent/concordance) links each chapter of an edition or
translation of Dioscorides to the Wellmann chapter(s) it renders: rows of links.tsv
with relation edition_of, urn_a in the edition (version = the edition's name), urn_b
in Wellmann (version wellmann1906). Those rows are vendored here as
concordance/edition_of.tsv and bound by concordance.lock.json (concordance commit,
sha256 of the vendored rows), because the Pages build has no access to that
repository. An edition without rows pairs by identical chapter key, as before.
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
        target, wkey = split(row["urn_b"])
        if target != WELLMANN:
            raise ValueError(f"edition_of must point into Wellmann: {row['urn_b']}")
        entry = out.setdefault(version, {"to_wellmann": {}, "statuses": set()})
        targets = entry["to_wellmann"].setdefault(key, [])
        if wkey not in targets:
            targets.append(wkey)
        entry["statuses"].add(row["status"])
    if len(rows) != lock["rows"]:
        raise ValueError("Vendored concordance row count differs from concordance.lock.json")
    for version, entry in out.items():
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
