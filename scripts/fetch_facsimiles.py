"""Fetch the page images pinned in facsimiles.lock.json into a built site.

    python scripts/fetch_facsimiles.py SITE [--cache DIR]

Facsimiles that no public image service holds are published with the site. Each set is one tar
of JPEG pages, a release asset of this repository; the lock pins its tag, asset and sha256. The
archive is downloaded with `gh release download` (cached in DIR), checked against the pin, and its
pages (flat NNNN.jpg members only) are written to SITE/<directory>. Run after the build: the build
replaces SITE.
"""
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMBER = re.compile(r"\d{4}\.jpg")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(item, cache):
    archive = cache / item["tag"] / item["asset"]
    if not archive.is_file() or sha256(archive) != item["sha256"]:
        archive.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["gh", "release", "download", item["tag"], "--repo", item["repository"],
                        "--pattern", item["asset"], "--dir", str(archive.parent), "--clobber"], check=True)
    if sha256(archive) != item["sha256"]:
        raise SystemExit(f"{item['asset']}: sha256 differs from facsimiles.lock.json")
    return archive


def extract(archive, target, pages):
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(archive) as tar:
        for member in tar:
            if not member.isfile() or not MEMBER.fullmatch(member.name):
                raise SystemExit(f"{archive.name}: unexpected member {member.name!r}")
            (target / member.name).write_bytes(tar.extractfile(member).read())
            count += 1
    if count != pages:
        raise SystemExit(f"{archive.name}: {count} pages, the lock says {pages}")


def main(argv):
    site = Path(argv[0])
    cache = Path(argv[argv.index("--cache") + 1]) if "--cache" in argv else ROOT / ".cache/facsimiles"
    lock = json.loads((ROOT / "facsimiles.lock.json").read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise SystemExit("Unsupported facsimiles.lock.json schema")
    for item in lock["sets"]:
        target = (site / item["directory"]).resolve()
        if site.resolve() not in target.parents:
            raise SystemExit(f"{item['directory']}: outside the site")
        extract(fetch(item, cache), target, item["pages"])
        print(f"{item['edition']}: {item['pages']} pages → {item['directory']}")


if __name__ == "__main__":
    main(sys.argv[1:])
