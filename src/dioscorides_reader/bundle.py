"""Verify portable corpus exports before any rendering or filesystem changes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse, unquote
from lxml import etree

SCHEMA = "dioscorides-corpus-export/1"
XI = "{http://www.w3.org/2001/XInclude}include"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_id(manifest: dict) -> str:
    content = {key: value for key, value in manifest.items()
               if key not in {"bundle_id", "generated", "generated_at", "created_at", "timestamp", "timestamps"}}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"Invalid bundle path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value or ":" in value:
        raise ValueError(f"Unsafe bundle path: {value!r}")
    return path


class Bundle:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        manifest_path = self.root / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError("Bundle manifest must be a regular file")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if self.manifest.get("schema") != SCHEMA:
            raise ValueError("Unsupported corpus bundle schema")
        if self.manifest.get("bundle_id") != manifest_id(self.manifest):
            raise ValueError("Bundle manifest digest mismatch")
        if not re.fullmatch(r"[a-f0-9]{40,64}", self.manifest.get("producer_commit", "")):
            raise ValueError("Bundle must name its producer commit")
        self.files: dict[str, dict] = {}
        for record in self.manifest["files"]:
            key = relative_path(record["path"]).as_posix()
            if not key.startswith("payload/") or key in self.files:
                raise ValueError(f"Duplicate or non-payload bundle file: {key}")
            path = self.root / key
            if path.is_symlink() or path.resolve() != path or not path.is_file():
                raise ValueError(f"Bundle file is missing or linked outside its location: {key}")
            if path.stat().st_size != record["size"] or sha256(path) != record["sha256"]:
                raise ValueError(f"Bundle file digest/size mismatch: {key}")
            self.files[key] = record
        editions = self.manifest.get("editions", [])
        if not editions or len({entry["id"] for entry in editions}) != len(editions):
            raise ValueError("Bundle must contain uniquely identified display editions")
        self._checked: set[Path] = set()
        for edition in editions:
            tei = self.path(edition["tei_path"])
            if self.files[edition["tei_path"]]["sha256"] != edition["source_sha256"]:
                raise ValueError(f"Edition source digest mismatch: {edition['id']}")
            self._validate_xml(tei, set())

    def path(self, value: str) -> Path:
        key = relative_path(value).as_posix()
        if key not in self.files:
            raise ValueError(f"Dependency is absent from bundle manifest: {key}")
        return self.root / key

    def include_path(self, source: Path, href: str) -> Path:
        parsed = urlparse(href)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or Path(href).is_absolute():
            raise ValueError(f"Only bundled local XML inclusions are allowed: {href}")
        target = (source.parent / unquote(href)).resolve()
        try:
            key = target.relative_to(self.root).as_posix()
        except ValueError as error:
            raise ValueError(f"XML inclusion escapes bundle: {href}") from error
        return self.path(key)

    def _validate_xml(self, path: Path, visiting: set[Path]) -> None:
        if path in visiting:
            raise ValueError(f"Cyclic XML inclusion: {path.name}")
        if path in self._checked:
            return
        raw = path.read_bytes()
        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
        # Parsing determines the declared/BOM encoding before inspecting document
        # declarations; byte searches miss UTF-16 and other valid XML encodings.
        try:
            root = etree.fromstring(raw, parser)
        except etree.XMLSyntaxError as error:
            raise ValueError(f"Invalid bundled XML: {path.name}: {error}") from error
        if root.getroottree().docinfo.doctype:
            raise ValueError(f"DTD/entity declarations are not allowed: {path.name}")
        for node in root.iter():
            if node.get("{http://www.w3.org/XML/1998/namespace}base"):
                raise ValueError("xml:base is not supported in corpus bundles")
            if node.tag != XI:
                continue
            if node.get("parse", "xml") != "xml" or node.get("xpointer"):
                raise ValueError("Only complete local XML inclusions are supported")
            self._validate_xml(self.include_path(path, node.get("href", "")), visiting | {path})
        self._checked.add(path)

    def read_json(self, value: str) -> dict:
        return json.loads(self.path(value).read_text(encoding="utf-8"))
