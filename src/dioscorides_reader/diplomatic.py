"""Physical-page presentation from exported diplomatic records."""
from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from lxml import etree
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI_NS}
FACS_LEAF_RE = re.compile(r"_(?P<leaf>\d{4})\.jp2$")
def archive_iiif(facs: str) -> dict[str, str]:
    parsed = urlparse(facs)
    if parsed.netloc != "archive.org" or not parsed.path.startswith("/download/"):
        raise ValueError(f"unsupported Sprengel facsimile URL: {facs}")
    path_after_download = unquote(parsed.path[len("/download/"):])
    encoded = quote(path_after_download, safe="")
    base = f"https://iiif.archive.org/image/iiif/3/{encoded}"
    return {
        "kind": "iiif",
        "info": f"{base}/info.json",
        "direct": f"{base}/full/max/0/default.jpg",
        "source": facs,
    }


def tei_facsimiles(path: Path) -> dict[str, str]:
    """Return one verified source facsimile URL per physical scan leaf."""
    values: dict[str, str] = {}
    for _event, element in ET.iterparse(path, events=("start",)):
        if not element.tag.endswith("}pb"):
            continue
        facs = element.get("facs")
        if not facs:
            continue
        decoded = unquote(facs)
        match = FACS_LEAF_RE.search(decoded)
        if not match:
            continue
        leaf = match.group("leaf")
        previous = values.setdefault(leaf, facs)
        if previous != facs:
            raise ValueError(f"TEI leaf {leaf} has conflicting facsimile URLs")
    return values


def tei_chapter_starts(path: Path) -> dict[str, dict[str, dict[str, dict[str, object]]]]:
    """Map every chapter head to its exact physical page and printed line."""
    tree = etree.parse(str(path), etree.XMLParser(resolve_entities=False, no_network=True))
    starts: dict[str, dict[str, dict[str, dict[str, object]]]] = {}
    chapters = tree.xpath("//tei:div[@subtype='chapter']", namespaces=NS)
    for chapter in chapters:
        heads = chapter.xpath("./tei:head[1]", namespaces=NS)
        if not heads:
            raise ValueError(f"chapter {chapter.get('n')!r} has no head")
        line_breaks = heads[0].xpath("(.//tei:lb)[1]", namespaces=NS)
        if not line_breaks:
            raise ValueError(f"chapter {chapter.get('n')!r} head has no line start")
        line_break = line_breaks[0]
        page_breaks = line_break.xpath("preceding::tei:pb[1]", namespaces=NS)
        if not page_breaks:
            raise ValueError(f"chapter {chapter.get('n')!r} has no preceding page")
        facs = unquote(page_breaks[0].get("facs") or "")
        leaf_match = FACS_LEAF_RE.search(facs)
        if not leaf_match:
            raise ValueError(f"chapter {chapter.get('n')!r} has unrecognized facsimile {facs!r}")
        line_n = line_break.get("n") or ""
        if not line_n.isdigit():
            raise ValueError(f"chapter {chapter.get('n')!r} has invalid line number {line_n!r}")
        stream_nodes = chapter.xpath(
            "ancestor::tei:div[@type='edition' or @type='translation'][1]",
            namespaces=NS,
        )
        book_nodes = chapter.xpath(
            "ancestor::tei:div[@subtype='book'][1]", namespaces=NS
        )
        if len(stream_nodes) != 1 or len(book_nodes) != 1:
            raise ValueError(f"chapter {chapter.get('n')!r} lacks stream/book context")
        stream = "grc" if stream_nodes[0].get("type") == "edition" else "lat"
        line_id = f"{'G' if stream == 'grc' else 'L'}{int(line_n):02d}"
        book_n = book_nodes[0].get("n") or ""
        local_chapter_n = chapter.get("n") or ""
        chapter_n = f"{book_n}.{local_chapter_n}"
        leaf = leaf_match.group("leaf")
        stream_starts = starts.setdefault(leaf, {}).setdefault(stream, {})
        if line_id in stream_starts:
            previous = stream_starts[line_id]["chapter"]
            raise ValueError(
                f"chapter-start collision at {leaf}.{stream}.{line_id}: "
                f"{previous}, {chapter_n}"
            )
        stream_starts[line_id] = {
            "chapter": chapter_n,
            "book": book_n,
            "n": local_chapter_n,
            "xml_id": chapter.get(f"{{{XML_NS}}}id") or "",
            "line_n": int(line_n),
            "indent": local_chapter_n != "praef",
        }
    return starts


def build(records: dict, tei_path: Path, output: Path) -> dict:
    if records.get("schema") != "diplomatic-pages/1" or records.get("edition") != "sprengel1829":
        raise ValueError("Unsupported diplomatic page export")
    facsimiles = tei_facsimiles(tei_path)
    starts = tei_chapter_starts(tei_path)
    pages = {}
    for original in records["pages"]:
        page = json.loads(json.dumps(original, ensure_ascii=False))
        leaf = page["leaf"]
        if not re.fullmatch(r"\d{4}", leaf) or leaf in pages:
            raise ValueError(f"Invalid or duplicate diplomatic leaf: {leaf}")
        for stream, data in page["streams"].items():
            if stream not in {"grc", "lat"}:
                raise ValueError(f"Unknown diplomatic stream: {stream}")
            prefix = "G" if stream == "grc" else "L"
            count = 0
            lineation = []
            for line in data["lines"]:
                if line.strip():
                    count += 1
                    lineation.append(f"{prefix}{count:02d}")
                else:
                    lineation.append("")
            data["lang"] = stream
            data["lineation"] = lineation
            data["chapter_starts"] = {}
            for line_id, metadata in starts.get(leaf, {}).get(stream, {}).items():
                if line_id not in lineation:
                    raise ValueError(f"Chapter start missing from diplomatic lines: {leaf}/{line_id}")
                data["chapter_starts"][line_id] = {**metadata, "line_index": lineation.index(line_id)}
        page["region"] = "text" if "grc" in page["streams"] else "front"
        numeric = re.fullmatch(r"\[?(\d+)\]?", page["printed"])
        parity = int(numeric.group(1)) if numeric else int(leaf)
        page["side"] = "left" if parity % 2 == 0 else "right"
        if leaf not in facsimiles:
            raise ValueError(f"Diplomatic leaf has no TEI facsimile: {leaf}")
        page["facs"] = archive_iiif(facsimiles[leaf])
        pages[leaf] = page
    expected = {f"{number:04d}" for number in range(6, 863)} - {"0630", "0631"}
    if set(pages) != expected or set(facsimiles) != expected:
        raise ValueError("Sprengel diplomatic/TEI 855-leaf inventory mismatch")
    counts = {
        "leaves": len(pages),
        "front": sum(page["region"] == "front" for page in pages.values()),
        "greek": sum("grc" in page["streams"] for page in pages.values()),
        "latin": sum("lat" in page["streams"] for page in pages.values()),
    }
    if counts != {"leaves": 855, "front": 27, "greek": 828, "latin": 855}:
        raise ValueError(f"Sprengel diplomatic stream inventory mismatch: {counts}")
    chapter_counts = {stream: sum(len(streams.get(stream, {})) for streams in starts.values())
                      for stream in ("grc", "lat")}
    if chapter_counts != {"grc": 921, "lat": 921}:
        raise ValueError(f"Sprengel diplomatic chapter-start inventory mismatch: {chapter_counts}")
    output.mkdir(parents=True, exist_ok=True)
    index_pages = []
    chunks = {}
    for leaf, page in sorted(pages.items()):
        chunk = f"{int(leaf) // 100:02d}"
        chunks.setdefault(chunk, {})[leaf] = page
        index_pages.append({"leaf": leaf, "printed": page["printed"], "region": page["region"],
                            "side": page["side"], "streams": list(page["streams"]), "chunk": chunk})
    for chunk, chunk_pages in chunks.items():
        (output / f"pages-{chunk}.json").write_text(json.dumps({
            "schema": "sprengel-diplomatic-pages-v2", "pages": chunk_pages,
        }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    index = {"schema": "sprengel-diplomatic-index-v2", "edition": "sprengel1829",
             "label": "Sprengel 1829 · line-preserving diplomatic pages", "counts": counts,
             "pages": index_pages}
    (output / "index.json").write_text(json.dumps(index, ensure_ascii=False,
                                                separators=(",", ":")) + "\n", encoding="utf-8")
    return index
