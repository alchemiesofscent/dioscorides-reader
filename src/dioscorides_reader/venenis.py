"""The pseudo-Dioscorides treatises on poisons (tlg1118.tlg001 De venenis, tlg1118.tlg002 De venenatis animalibus,
Sprengel 1830) beside Mattioli's Book 6 (Sean, 2026-10-11).

Their Greek is a TLG text (Diogenes' XML in the corpora repository): it may be shown in a private build (D43) and
never in a public one (D42). It is not in the corpus bundle nor in this repository; a build reads it from a local
corpora checkout only when given one (--local-text tlg1118=CHECKOUT), and only files whose sha256 is the one
pinned in local_texts.lock.json. The two files become one TEI in the shape the reader reads (an edition stream,
book 1 and book 2, a chapter per numbered section, the title "t" and proem "Pr" as sections), written outside
the build output and read from there.
"""
from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "local_texts.lock.json"
KEY = "tlg1118"
TEI = "{http://www.tei-c.org/ns/1.0}"
XML = "{http://www.w3.org/XML/1998/namespace}"
BOOKS = ("De venenis", "De venenatis animalibus")


def pinned(checkout: Path, lock_path: Path = LOCK) -> tuple[dict, list[Path]]:
    """The lock entry and the treatises' files in a corpora checkout, each checked against its pinned sha256."""
    entry = json.loads(lock_path.read_text(encoding="utf-8"))[KEY]
    paths = []
    for item in entry["files"]:
        path = checkout / item["path"]
        if not path.is_file():
            raise ValueError(f"{KEY}: {item['path']} is not in {checkout}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"{KEY}: {item['path']} differs from local_texts.lock.json")
        paths.append(path)
    return entry, paths


def words(el: ET.Element, skip: tuple[str, ...] = ()) -> str:
    """The text of an element, without its page breaks or the elements named in skip, on one line."""
    out: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.tag in skip:
            out.append(node.tail or "")
            return
        out.append(node.text or "")
        for child in node:
            walk(child)
        if node is not el:
            out.append(node.tail or "")
    walk(el)
    return " ".join("".join(out).split())


def convert(paths: list[Path], entry: dict) -> ET.Element:
    """One TEI of the two treatises: books 1 and 2."""
    ET.register_namespace("", TEI[1:-1])
    sources = [ET.parse(path).getroot() for path in paths]
    root = ET.Element(f"{TEI}TEI")
    header = copy.deepcopy(sources[0].find(f"{TEI}teiHeader"))
    title = header.find(f"{TEI}fileDesc/{TEI}titleStmt/{TEI}title")
    for other in sources[1:]:
        title.text = f"{title.text}; {other.find(f'{TEI}teiHeader/{TEI}fileDesc/{TEI}titleStmt/{TEI}title').text}"
    encoding = ET.SubElement(header, f"{TEI}encodingDesc")
    ET.SubElement(ET.SubElement(encoding, f"{TEI}editorialDecl"), f"{TEI}p").text = (
        f"Read from {entry['repository']} at {entry['commit'][:12]} ({', '.join(i['path'] for i in entry['files'])}), "
        "a TLG text: shown in private builds only. The two treatises are books 1 and 2; their unnumbered page "
        "breaks are left out.")
    root.append(header)
    stream = ET.SubElement(ET.SubElement(ET.SubElement(root, f"{TEI}text"), f"{TEI}body"), f"{TEI}div",
                           {"type": "edition", f"{XML}lang": "grc"})
    for number, source in enumerate(sources, 1):
        book = ET.SubElement(stream, f"{TEI}div", {"type": "textpart", "subtype": "book", "n": str(number)})
        for section in source.find(f"{TEI}text/{TEI}body").findall(f"{TEI}div"):
            n = section.get("n", "")
            div = ET.SubElement(book, f"{TEI}div", {"type": "textpart", "n": n,
                                                    "subtype": "chapter" if n.isdigit() else "section"})
            heads = [words(label) for label in section.iter(f"{TEI}label") if label.get("type") == "head"]
            if heads:
                ET.SubElement(div, f"{TEI}head").text = " ".join(heads)
            for paragraph in section.findall(f"{TEI}p"):
                text = words(paragraph, skip=(f"{TEI}label", f"{TEI}pb"))
                if text:
                    ET.SubElement(div, f"{TEI}p").text = text
    return root


def prepare(checkout: Path, into: Path, lock_path: Path = LOCK) -> tuple[Path, dict]:
    """Write the treatises' TEI into `into` (outside the build output): (its path, the lock entry)."""
    entry, paths = pinned(checkout, lock_path)
    path = into / f"{KEY}.xml"
    ET.ElementTree(convert(paths, entry)).write(path, encoding="utf-8", xml_declaration=True)
    return path, entry
