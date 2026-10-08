"""Vendor the concordance's edition_of rows at one commit, with their lock.

    python scripts/vendor_concordance.py CONCORDANCE_CHECKOUT COMMIT

Reads links.tsv at COMMIT (git show, so the checkout's working tree does not matter) and keeps
the rows with relation edition_of, in four columns only (urn_a, relation, urn_b, status): this
repository is public and the concordance is private, so its evidence and notes stay there, and
the rows of in-copyright editions (PRIVATE) are left out. Writes concordance/edition_of.tsv and
concordance.lock.json (repository, commit, sha256 of links.tsv and of the vendored rows).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ("beck2020",)
COLUMNS = ("urn_a", "relation", "urn_b", "status")


def main(checkout, commit):
    full = subprocess.run(["git", "-C", checkout, "rev-parse", commit], check=True, capture_output=True,
                          text=True).stdout.strip()
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
        rows.append("\t".join(cells[i] for i in idx) + "\n")
    data = ("\t".join(COLUMNS) + "\n" + "".join(rows)).encode("utf-8")
    out = ROOT / "concordance" / "edition_of.tsv"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(data)
    lock = {"schema_version": 1, "repository": "alchemiesofscent/concordance", "commit": full,
            "links_sha256": hashlib.sha256(links).hexdigest(), "vendored": "concordance/edition_of.tsv",
            "rows": len(rows), "columns": list(COLUMNS), "excluded_versions": list(PRIVATE),
            "edition_of_sha256": hashlib.sha256(data).hexdigest()}
    (ROOT / "concordance.lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} edition_of rows from {full[:12]}")


if __name__ == "__main__":
    main(*sys.argv[1:])
