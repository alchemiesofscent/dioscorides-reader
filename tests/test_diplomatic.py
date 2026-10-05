from pathlib import Path

import pytest
from dioscorides_reader.diplomatic import tei_chapter_starts


def write_chapter(tmp_path: Path, n: str, content: str) -> Path:
    path = tmp_path / "chapter.xml"
    path.write_text(f'''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
    <div type="edition"><div type="textpart" subtype="book" n="2">
    <pb facs="https://archive.org/download/item/scan_0199.jp2"/>
    <head><lb n="1"/>BOOK II</head>
    <div type="textpart" subtype="chapter" n="{n}" xml:id="spr-ch-2.{n}-grc">
    {content}</div></div></div></body></text></TEI>''')
    return path


def test_unheaded_preface_starts_at_body_line_and_skips_notes_and_furniture(tmp_path):
    path = write_chapter(tmp_path, "praef", '''<note><lb n="20"/>A note.</note>
        <fw><lb n="1"/>A header.</fw><milestone unit="proemium"/>
        <p><lb n="2"/>Dear Areios,</p>''')
    starts = tei_chapter_starts(path)
    assert list(starts["0199"]["grc"]) == ["G02"]
    assert starts["0199"]["grc"]["G02"] == {
        "chapter": "2.praef", "book": "2", "n": "praef",
        "xml_id": "spr-ch-2.praef-grc", "line_n": 2, "indent": False,
    }


@pytest.mark.parametrize(("n", "content", "message"), [
    ("1", "<p><lb n='2'/>Text.</p>", "has no head"),
    ("praef", "<note><lb n='20'/>A note.</note><p>Text.</p>", "has no line start"),
])
def test_unheaded_numbered_chapter_and_preface_without_body_line_are_refused(
        tmp_path, n, content, message):
    with pytest.raises(ValueError, match=message):
        tei_chapter_starts(write_chapter(tmp_path, n, content))
