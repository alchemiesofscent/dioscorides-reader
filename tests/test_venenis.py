"""The treatises on poisons beside Mattioli's Book 6: read only in a build given them, from pinned files.
The Greek here is made up (the real text is a TLG text and stays out of this repository)."""
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from dioscorides_reader import concordance, venenis

TEI = "{http://www.tei-c.org/ns/1.0}"
W = "urn:cts:greekLit:tlg0656.tlg001.wellmann1906:"
M = "urn:cts:greekLit:tlg0656.tlg001.mattioli1554:"
V2 = "urn:cts:greekLit:tlg1118.tlg002.sprengel1830:"
HEAD = "urn_a\trelation\turn_b\tstatus\tw_from\tw_to\ta_lead\tw_lead\n"
TREATISE = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>{title}</title></titleStmt>
<publicationStmt><p>made up</p></publicationStmt><sourceDesc><p>made up</p></sourceDesc></fileDesc></teiHeader>
<text><body>
<div type="Section" n="t"><p><label type="head"><hi>ΑΛΦΑ</hi></label></p></div>
<div type="Section" n="Pr"><p><label type="head">ΠΡΟΟΙΜΙΟΝ.</label> Ἄλφα βῆτα <pb/>
γάμμα.</p></div>
<div type="Section" n="1"><p>[Περὶ δέλτα.] Δέλτα ἔψιλον.</p><p>Ζῆτα.</p></div>
<div type="Section" n="2"><p>Ἦτα θῆτα.</p></div>
</body></text></TEI>
"""


def checkout(tmp_path):
    files = []
    for n, title in (("001", "Prima"), ("002", "Secunda")):
        path = tmp_path / "corpora" / "tlg" / f"tlg1118{n}.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TREATISE.format(title=title), encoding="utf-8")
        files.append({"path": f"tlg/tlg1118{n}.xml", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    lock = tmp_path / "local_texts.lock.json"
    lock.write_text(json.dumps({"schema_version": 1, "tlg1118": {
        "repository": "alchemiesofscent/corpora", "commit": "c" * 40, "files": files}}))
    return tmp_path / "corpora", lock


def test_the_two_treatises_become_two_books(tmp_path):
    corpora, lock = checkout(tmp_path)
    out = tmp_path / "scratch"
    out.mkdir()
    path, entry = venenis.prepare(corpora, out, lock)
    stream = ET.parse(path).getroot().find(f"{TEI}text/{TEI}body/{TEI}div")
    assert stream.get("type") == "edition"
    books = stream.findall(f"{TEI}div")
    assert [b.get("n") for b in books] == ["1", "2"]
    divs = books[0].findall(f"{TEI}div")
    assert [(d.get("n"), d.get("subtype")) for d in divs] == [
        ("t", "section"), ("Pr", "section"), ("1", "chapter"), ("2", "chapter")]
    assert divs[1].find(f"{TEI}head").text == "ΠΡΟΟΙΜΙΟΝ."
    assert divs[1].find(f"{TEI}p").text == "Ἄλφα βῆτα γάμμα."         # the head and the page break left out
    assert [p.text for p in divs[2].findall(f"{TEI}p")] == ["[Περὶ δέλτα.] Δέλτα ἔψιλον.", "Ζῆτα."]
    assert "Prima; Secunda" in ET.tostring(ET.parse(path).getroot(), encoding="unicode")


def test_a_file_not_as_pinned_is_refused(tmp_path):
    corpora, lock = checkout(tmp_path)
    (corpora / "tlg" / "tlg1118002.xml").write_text(TREATISE.format(title="Altera"), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from local_texts.lock.json"):
        venenis.pinned(corpora, lock)


def rows(tmp_path):
    wdata = (HEAD + f"{M}1.1\tedition_of\t{W}1.1\tproposed\t\t\t\t\n").encode()
    vdata = (HEAD + f"{M}6.37\tedition_of\t{V2}2@Ἦτα[1]-θῆτα[1]\tproposed\t0\t2\t\tἮτα θῆτα\n"
             + f"{M}6.42\tedition_of\t{V2}1\tproposed\t\t\t\t\n").encode()
    (tmp_path / "edition_of.tsv").write_bytes(wdata)
    (tmp_path / "edition_of_tlg1118.tsv").write_bytes(vdata)
    lock = {"repository": "alchemiesofscent/concordance", "commit": "abc", "vendored": "edition_of.tsv",
            "rows": 1, "edition_of_sha256": hashlib.sha256(wdata).hexdigest(),
            "tlg1118": {"vendored": "edition_of_tlg1118.tsv", "rows": 2, "sha256": hashlib.sha256(vdata).hexdigest()}}
    (tmp_path / "concordance.lock.json").write_text(json.dumps(lock))
    return tmp_path / "concordance.lock.json"


def test_book_6_pairs_with_the_treatises_only_in_a_build_given_them(tmp_path):
    lock = rows(tmp_path)
    public = concordance.load(lock)["mattioli1554"]
    assert public["to_wellmann"] == {"1.1": ["1.1"]}
    private = concordance.load(lock, venenis=True)["mattioli1554"]
    assert private["to_wellmann"]["6.37"] == ["V2.2"] and private["to_wellmann"]["6.42"] == ["V2.1"]
    assert private["spans"]["6.37"] == [["V2.2", 0, 2, "De venenatis animalibus 2 (part)",
                                         {"sub": "Ἦτα[1]-θῆτα[1]", "lead": ["Ἦτα", "θῆτα"]}]]


def test_changed_treatise_rows_are_refused(tmp_path):
    lock = rows(tmp_path)
    (tmp_path / "edition_of_tlg1118.tsv").write_bytes(HEAD.encode())
    concordance.load(lock)                                  # a public build does not read them
    with pytest.raises(ValueError, match="edition_of_tlg1118.tsv"):
        concordance.load(lock, venenis=True)


def test_the_treatises_pair_their_chapters_through_their_own_keys(tmp_path):
    pairings = concordance.load(rows(tmp_path), venenis=True)
    edition = {"books": [{"n": "1", "chapters": [{"n": "Pr"}, {"n": "1"}]}, {"n": "2", "chapters": [{"n": "2"}]}]}
    pairing = concordance.venenis_pairing(edition, pairings)
    assert pairing["to_wellmann"] == {"1.Pr": ["V1.Pr"], "1.1": ["V1.1"], "2.2": ["V2.2"]}
    assert pairing["target"] is True and pairing["status"] == "proposed"
