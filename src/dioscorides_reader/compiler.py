"""Compile verified corpus inputs into a self-contained static reading surface."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import subprocess
import tarfile
from pathlib import Path

from . import diplomatic, render, xml_utils
from .bundle import Bundle, relative_path

MARKER = ".dioscorides-reader-output"


def verify_lock(bundle: Bundle, lock: Path | None) -> None:
    if lock is None:
        return
    expected = json.loads(lock.read_text(encoding="utf-8"))
    for field in ("bundle_id", "producer_commit"):
        if expected.get(field) != bundle.manifest[field]:
            raise ValueError(f"Corpus lock {field} does not match bundle")


def web_directory() -> Path:
    source = Path(__file__).resolve().parents[2] / "web"
    installed = Path(sys.prefix) / "share" / "dioscorides-reader" / "web"
    for location in (source, installed):
        if (location / "reader.html").is_file():
            return location
    raise ValueError("Reader web assets are missing; reinstall dioscorides-reader")


def compile_bundle(bundle_path: Path, output: Path, lock: Path | None = None) -> dict:
    bundle = Bundle(bundle_path)
    verify_lock(bundle, lock)
    if output.is_symlink():
        raise ValueError("Output must not be a symbolic link")
    output = output.resolve()
    if output == bundle.root or output in bundle.root.parents or bundle.root in output.parents:
        raise ValueError("Build output must be separate from the immutable bundle")
    if output.exists() and (not output.is_dir() or
                            (any(output.iterdir()) and not (output / MARKER).is_file())):
        raise ValueError("Refusing to replace a directory not created by dioscorides-reader")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-build-", dir=output.parent))
    old_root, old_table, old_facs = render.ROOT, render.CHAPTER_TABLE, render.FACSIMILES
    old_bundle = xml_utils.ACTIVE_BUNDLE
    try:
        shutil.copytree(web_directory(), staging, dirs_exist_ok=True)
        data = staging / "data"
        data.mkdir()
        render.ROOT = bundle.root
        render.CHAPTER_TABLE = bundle.path("payload/editions/sprengel/sprengel_chapter_table.tsv")
        xml_utils.ACTIVE_BUNDLE = bundle
        facsimiles = bundle.read_json("payload/facsimiles.json")
        if facsimiles.get("schema") != "facsimiles/1":
            raise ValueError("Unsupported facsimile export schema")
        render.FACSIMILES = {
            (bundle.path(item["tei_path"]).as_posix(), item["facs"]): item
            for item in facsimiles["resources"]
        }
        table = render.load_chapter_table()
        report = render.Report()
        configs = {entry["key"]: entry for entry in render.EDITIONS}
        editions = {}
        for selection in bundle.manifest["editions"]:
            key = selection["id"]
            if key not in configs:
                raise ValueError(f"No reader adapter for exported stream: {key}")
            config = {**configs[key], "tei_path": selection["tei_path"]}
            edition = render.build_edition(config, table, report, data)
            if not edition or not edition["books"] or any(not book["chapters"] for book in edition["books"]):
                raise ValueError(f"Selected edition did not produce complete readable books: {key}")
            edition.update(status=selection["status"], source_sha256=selection["source_sha256"],
                           edition_id=selection.get("edition_id", key))
            editions[key] = edition
        if any(key.startswith("sprengel1829-") for key in editions):
            selection = next(item for item in bundle.manifest["editions"]
                             if item["id"].startswith("sprengel1829-"))
            diplomatic.build(bundle.read_json("payload/diplomatic/sprengel1829.json"),
                             bundle.path(selection["tei_path"]), data / "sprengel1829-diplomatic")
        # Broken textual links/structure must not silently become a completed build.
        fatal = [item for item in report.items if item[1] in {
            "structure", "footnote ref target missing", "stand-off apparatus",
        }]
        if fatal:
            raise ValueError(f"Reader build has unresolved structural references: {fatal[:5]}")
        manifest = {"schema": "dioscorides-reader-data/1", "bundle_id": bundle.manifest["bundle_id"],
                    "producer_commit": bundle.manifest["producer_commit"], "editions": editions,
                    "pairing": "provisional chapter-key pairing"}
        (data / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
        report.write(data / "REPORT.md")
        # Retain retrieval guidance even when optional facsimile images are unavailable.
        shutil.copyfile(bundle.path("payload/facsimiles.json"), data / "facsimiles.json")
        (staging / MARKER).write_text(bundle.manifest["bundle_id"] + "\n", encoding="ascii")
        (staging / "index.html").write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8"><title>Dioscorides reader</title>'
            '<meta http-equiv="refresh" content="0;url=reader.html"><a href="reader.html">Open reader</a></html>\n',
            encoding="utf-8")
        backup = None
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{output.name}-previous-", dir=output.parent))
            backup.rmdir()
            output.rename(backup)
        try:
            staging.rename(output)
        except BaseException:
            if backup is not None:
                backup.rename(output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return manifest
    finally:
        render.ROOT, render.CHAPTER_TABLE, render.FACSIMILES = old_root, old_table, old_facs
        xml_utils.ACTIVE_BUNDLE = old_bundle
        if staging.exists():
            shutil.rmtree(staging)


def fetch_bundle(source: Path, cache: Path, lock: Path | None = None) -> Path:
    bundle = Bundle(source)
    verify_lock(bundle, lock)
    cache = cache.resolve()
    target = cache / bundle.manifest["bundle_id"]
    if cache == bundle.root or bundle.root in cache.parents:
        raise ValueError("Cache must be outside the immutable export")
    if target.exists():
        if target.is_symlink():
            raise ValueError("Bundle cache entries must not be symbolic links")
        existing = Bundle(target)
        if existing.manifest["bundle_id"] != bundle.manifest["bundle_id"]:
            raise ValueError("Existing bundle cache entry has the wrong identity")
        return target
    cache.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".fetch-", dir=cache))
    try:
        shutil.copyfile(bundle.root / "manifest.json", staging / "manifest.json")
        for key in bundle.files:
            path = staging / key
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle.path(key), path)
        Bundle(staging)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target


def unpack_archive(archive: Path, destination: Path) -> Path:
    """Extract only regular files/directories underneath one top-level directory."""
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        roots = set()
        seen = set()
        for member in members:
            name = member.name.rstrip("/")
            path = relative_path(name)
            if not (member.isfile() or member.isdir()) or name in seen:
                raise ValueError(f"Unsafe or duplicate archive member: {member.name}")
            roots.add(path.parts[0])
            seen.add(name)
        if len(roots) != 1:
            raise ValueError("Corpus archive must contain exactly one bundle root")
        for member in members:
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with handle.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    root = destination / roots.pop()
    Bundle(root)
    return root


def fetch_release(repository: str, tag: str, asset: str, cache: Path, lock: Path) -> Path:
    if not repository or repository.startswith("-") or not tag or tag.startswith("-"):
        raise ValueError("Release repository and tag must be explicit values")
    if relative_path(asset).name != asset or not asset.endswith(".tar.gz"):
        raise ValueError("Release asset must be a plain .tar.gz filename")
    with tempfile.TemporaryDirectory(prefix="dioscorides-release-") as temporary:
        directory = Path(temporary)
        command = ["gh", "release", "download", tag, "--repo", repository,
                   "--pattern", asset, "--dir", str(directory)]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode:
            raise ValueError("Private release download failed; verify gh authentication and the pinned release")
        root = unpack_archive(directory / asset, directory / "extracted")
        return fetch_bundle(root, cache, lock)
