from __future__ import annotations

import io
import copy
import json
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from dioscorides_reader.bundle import Bundle, manifest_id, sha256
from dioscorides_reader.compiler import compile_bundle, fetch_bundle, unpack_archive

TEI = """<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude">
<teiHeader><fileDesc><titleStmt><title>Test</title></titleStmt>
<publicationStmt><p>Private fixture</p></publicationStmt><sourceDesc>
<xi:include href="../listWit.xml"/></sourceDesc></fileDesc></teiHeader>
<text><body><div type="translation" xml:lang="eng"><div subtype="book" n="1">
<div subtype="chapter" n="1" xml:id="ch-1"><head>Test chapter</head><p>
<app><lem>reading</lem><rdg wit="#A">variant</rdg></app>
<anchor xml:id="s1"/>another<anchor xml:id="e1"/> reading.
<ref type="footnote-ref" target="#note-1">1</ref></p><note type="footnote" xml:id="note-1">A note.</note>
</div></div></div></body></text><standOff><listApp>
<app xml:id="app-extra" from="#s1" to="#e1"><lem>another</lem><rdg wit="#A">other</rdg></app>
</listApp></standOff></TEI>"""
TEI_PATH = "payload/editions/beck/tei/beck2020_fresh_diplomatic_epidoc.xml"


def make_bundle(path: Path, tei: str | bytes = TEI) -> Path:
    values = {
        TEI_PATH: tei,
        "payload/editions/beck/listWit.xml": '<listWit xmlns="http://www.tei-c.org/ns/1.0"><witness xml:id="A">Codex A</witness></listWit>',
        "payload/editions/sprengel/sprengel_chapter_table.tsv": "n\tlabel_grc\tlabel_la\n",
        "payload/facsimiles.json": json.dumps({"schema": "facsimiles/1", "resources": []}),
    }
    files = []
    for key, value in values.items():
        target = path / key
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            target.write_bytes(value)
        else:
            target.write_text(value, encoding="utf-8")
        files.append({"path": key, "sha256": sha256(target), "size": target.stat().st_size})
    manifest = {"schema": "dioscorides-corpus-export/1", "producer_commit": "a" * 40,
                "editions": [{"id": "beck2020", "edition_id": "beck2020", "label": "Beck 2020",
                              "status": "review_pending", "tei_path": TEI_PATH,
                              "legacy_tei_path": TEI_PATH.removeprefix("payload/"),
                              "source_sha256": sha256(path / TEI_PATH)}], "files": files}
    manifest["bundle_id"] = manifest_id(manifest)
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def rewrite_manifest(path: Path, change) -> None:
    manifest = json.loads((path / "manifest.json").read_text())
    change(manifest)
    manifest["bundle_id"] = manifest_id(manifest)
    (path / "manifest.json").write_text(json.dumps(manifest))


def snapshot(path: Path) -> dict:
    return {file.relative_to(path).as_posix(): sha256(file) for file in path.rglob("*") if file.is_file()}


def test_isolated_build_preserves_routes_notes_and_apparatus(tmp_path):
    bundle = make_bundle(tmp_path / "input")
    output = tmp_path / "dist"
    result = compile_bundle(bundle, output)
    assert result["editions"]["beck2020"]["status"] == "review_pending"
    assert result["editions"]["beck2020"]["books"][0]["chapters"][0]["n"] == "1"
    book = json.loads((output / "data/beck2020/book-1.json").read_text())
    html = book["chapters"]["1"]["html"]
    assert html.count("another") == 1
    assert "app-standoff" in html
    assert "Codex A" in " ".join(book["apps"].values())
    assert "A note." in book["notes"]["note-1"]
    assert (output / "vendor/openseadragon/openseadragon.min.js").is_file()
    assert "../editions/" not in (output / "data/beck2020/book-1.json").read_text()
    before = snapshot(output)
    compile_bundle(bundle, output)
    assert snapshot(output) == before


def test_corrupt_payload_does_not_replace_completed_output(tmp_path):
    bundle = make_bundle(tmp_path / "input")
    output = tmp_path / "dist"
    compile_bundle(bundle, output)
    before = snapshot(output)
    (bundle / TEI_PATH).write_text("tampered")
    with pytest.raises(ValueError, match="digest/size mismatch"):
        compile_bundle(bundle, output)
    assert snapshot(output) == before


def test_header_credits_change_without_chapter_or_apparatus_changes(tmp_path):
    before = make_bundle(tmp_path / "before")
    revised = TEI.replace('</titleStmt>', '''<respStmt>
      <resp>Source correction, editorial review and AI-assisted encoding</resp>
      <persName>Test editor</persName><note type="affiliation">Institute</note>
      </respStmt></titleStmt>''').replace('</fileDesc>', '''</fileDesc><encodingDesc>
      <projectDesc><p>Corrected against the printed source.</p></projectDesc></encodingDesc>''')
    after = make_bundle(tmp_path / "after", revised)
    first = compile_bundle(before, tmp_path / "first")
    second = compile_bundle(after, tmp_path / "second")
    assert first['bundle_id'] != second['bundle_id']
    assert first['editions']['beck2020']['source_sha256'] != second['editions']['beck2020']['source_sha256']
    assert first['editions']['beck2020']['books'] == second['editions']['beck2020']['books']
    assert (tmp_path / 'first/data/beck2020/book-1.json').read_bytes() == (tmp_path / 'second/data/beck2020/book-1.json').read_bytes()
    credits = second['editions']['beck2020']['credits']
    assert 'Test editor — Source correction, editorial review and AI-assisted encoding' in json.dumps(credits, ensure_ascii=False)
    assert 'Corrected against the printed source.' in json.dumps(credits)
    assert 'Codex A' not in json.dumps(credits), 'included witnesses are not edition credits'


@pytest.mark.parametrize("href", ["../../../../../../etc/passwd", "https://example.org/witness.xml", "/etc/passwd", "absent.xml"])
def test_missing_or_external_include_is_rejected(tmp_path, href):
    bundle = make_bundle(tmp_path / "input", TEI.replace("../listWit.xml", href))
    with pytest.raises(ValueError, match="bundle|bundled|inclusion"):
        Bundle(bundle)


def test_unrelated_output_is_never_replaced(tmp_path):
    bundle = make_bundle(tmp_path / "input")
    output = tmp_path / "research"
    output.mkdir()
    (output / "notes.txt").write_text("preserve")
    with pytest.raises(ValueError, match="Refusing to replace"):
        compile_bundle(bundle, output)
    assert (output / "notes.txt").read_text() == "preserve"


def test_lock_and_manifest_schema_validation(tmp_path):
    bundle = make_bundle(tmp_path / "input")
    lock = tmp_path / "corpus.lock.json"
    lock.write_text(json.dumps({"bundle_id": "0" * 64, "producer_commit": "a" * 40}))
    with pytest.raises(ValueError, match="lock"):
        compile_bundle(bundle, tmp_path / "dist", lock)
    rewrite_manifest(bundle, lambda manifest: manifest.update(schema="future/100"))
    with pytest.raises(ValueError, match="schema"):
        Bundle(bundle)


def test_fetch_copies_only_manifested_sources_and_is_idempotent(tmp_path):
    source = make_bundle(tmp_path / "source")
    (source / "private-scratch.txt").write_text("do not copy")
    target = fetch_bundle(source, tmp_path / "cache")
    assert not (target / "private-scratch.txt").exists()
    assert Bundle(target).manifest == Bundle(source).manifest
    before = snapshot(target)
    assert fetch_bundle(source, tmp_path / "cache") == target
    assert snapshot(target) == before


@pytest.mark.parametrize("name,kind", [("../escape", "file"), ("bundle/link", "symlink"), ("bundle/hard", "hardlink")])
def test_archive_rejects_path_escape_and_links(tmp_path, name, kind):
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo(name)
        if kind == "symlink":
            info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
        elif kind == "hardlink":
            info.type, info.linkname = tarfile.LNKTYPE, "/etc/passwd"
        else:
            info.size = 4
        handle.addfile(info, io.BytesIO(b"test") if kind == "file" else None)
    with pytest.raises(ValueError):
        unpack_archive(archive, tmp_path / "extracted")
    assert not (tmp_path / "escape").exists()


def test_safe_release_archive(tmp_path):
    source = make_bundle(tmp_path / "input")
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(source, arcname="corpus")
    root = unpack_archive(archive, tmp_path / "extracted")
    assert Bundle(root).manifest["bundle_id"] == Bundle(source).manifest["bundle_id"]


def corrupted_structure(scenario: str) -> str:
    root = ET.fromstring(TEI)
    ns = {"t": "http://www.tei-c.org/ns/1.0"}
    stream = root.find(".//t:div[@type='translation']", ns)
    book = stream.find("t:div", ns)
    app = root.find("t:standOff/t:listApp/t:app", ns)
    if scenario == "duplicate_chapter":
        chapter = copy.deepcopy(book[0])
        chapter.set("{http://www.w3.org/XML/1998/namespace}id", "different-chapter")
        # Keep XML IDs unique so the route check is the condition under test.
        for element in chapter.iter():
            key = "{http://www.w3.org/XML/1998/namespace}id"
            if key in element.attrib:
                element.set(key, "duplicate-" + element.get(key))
        book.append(chapter)
    elif scenario == "duplicate_book":
        duplicate = copy.deepcopy(book)
        for element in duplicate.iter():
            key = "{http://www.w3.org/XML/1998/namespace}id"
            if key in element.attrib:
                element.set(key, "duplicate-" + element.get(key))
        stream.append(duplicate)
    elif scenario == "missing_end":
        app.set("to", "#missing")
    elif scenario == "incomplete_range":
        del app.attrib["to"]
    elif scenario == "empty_target":
        del app.attrib["from"]
        del app.attrib["to"]
    elif scenario in {"missing_ptr_end", "odd_ptr", "empty_ptr"}:
        del app.attrib["from"]
        del app.attrib["to"]
        targets = {"missing_ptr_end": "#s1 #missing", "odd_ptr": "#s1 #e1 #s1", "empty_ptr": ""}
        ET.SubElement(app, "{http://www.tei-c.org/ns/1.0}ptr", {"target": targets[scenario]})
    return ET.tostring(root, encoding="unicode")


@pytest.mark.parametrize("scenario", ["duplicate_chapter", "duplicate_book", "missing_end",
                                       "incomplete_range", "empty_target", "missing_ptr_end",
                                       "odd_ptr", "empty_ptr"])
def test_route_and_apparatus_failures_preserve_completed_output(tmp_path, scenario):
    source = make_bundle(tmp_path / "source")
    output = tmp_path / "dist"
    compile_bundle(source, output)
    before = snapshot(output)
    make_bundle(source, corrupted_structure(scenario))
    with pytest.raises(ValueError, match="Duplicate|stand-off apparatus"):
        compile_bundle(source, output)
    assert snapshot(output) == before


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-le", "utf-16-be"])
def test_dtd_is_rejected_in_all_xml_encodings_and_preserves_output(tmp_path, encoding):
    source = make_bundle(tmp_path / "source")
    output = tmp_path / "dist"
    compile_bundle(source, output)
    before = snapshot(output)
    declared = "UTF-8" if encoding == "utf-8" else "UTF-16"
    text = (f'<?xml version="1.0" encoding="{declared}"?>'
            '<!DOCTYPE TEI [<!ENTITY hidden "expanded entity">]>'
            + TEI.replace("Test chapter", "&hidden;"))
    make_bundle(source, text.encode(encoding))
    with pytest.raises(ValueError, match="DTD/entity"):
        compile_bundle(source, output)
    assert snapshot(output) == before
