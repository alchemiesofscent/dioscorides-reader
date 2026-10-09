import hashlib
import json

import pytest

from dioscorides_reader import concordance

W = "urn:cts:greekLit:tlg0656.tlg001.wellmann1906:"
M = "urn:cts:greekLit:tlg0656.tlg001.mattioli1554:"
HEAD = "urn_a\trelation\turn_b\tstatus\tcoarse\tevidence\tsource\tby\tdate\tnote\n"


def write(tmp_path, rows, **change):
    data = (HEAD + "".join("\t".join(r) + "\n" for r in rows)).encode()
    (tmp_path / "edition_of.tsv").write_bytes(data)
    lock = {"repository": "alchemiesofscent/concordance", "commit": "abc", "vendored": "edition_of.tsv",
            "rows": len(rows), "edition_of_sha256": hashlib.sha256(data).hexdigest(), **change}
    (tmp_path / "concordance.lock.json").write_text(json.dumps(lock))
    return tmp_path / "concordance.lock.json"


def row(a, b, status="proposed"):
    return [M + a, "edition_of", W + b, status, "no", "lemma", "test", "", "", ""]


def test_rows_become_a_map_to_wellmann(tmp_path):
    lock = write(tmp_path, [row("1.42", "1.43"), row("1.70", "1.68"), row("1.71", "1.68"), row("5.42", "5.44"),
                            row("5.42", "5.45")])
    table = concordance.load(lock)
    entry = table["mattioli1554"]
    assert entry["to_wellmann"]["1.42"] == ["1.43"] and entry["to_wellmann"]["5.42"] == ["5.44", "5.45"]
    assert entry["status"] == "proposed" and entry["source"]["commit"] == "abc"
    assert concordance.pairing_for({"key": "mattioli1554-eng", "concordance": "mattioli1554"}, table) is entry
    assert concordance.pairing_for({"key": "berendes1902"}, table) is None


def test_changed_rows_or_wrong_targets_are_refused(tmp_path):
    lock = write(tmp_path, [row("1.42", "1.43")], edition_of_sha256="0" * 64)
    with pytest.raises(ValueError, match="differ"):
        concordance.load(lock)
    bad = [M + "1.42", "edition_of", "urn:cts:greekLit:tlg0656.tlg001.sprengel1829:1.43", "proposed", "", "", "", "", "", ""]
    with pytest.raises(ValueError, match="Wellmann"):
        concordance.load(write(tmp_path, [bad]))


def test_without_a_pinned_concordance_keys_pair_as_before(tmp_path):
    table = concordance.load(tmp_path / "concordance.lock.json")
    assert table is None
    assert concordance.pairing_for({"key": "mattioli1554", "concordance": "mattioli1554"}, table) is None


def test_wellmann_takes_the_title_of_its_sprengel_chapter():
    table = {"1.52": {"label_grc": "Περὶ συνθέσεως μύρων"}, "1.53": {"label_grc": "Περὶ ῥοδίνου σκευασίας"}}
    pairings = {"sprengel1829": {"to_wellmann": {"1.52": ["1.42"], "1.53": ["1.43"]}}}
    labels = concordance.relabel(table, pairings, "sprengel1829")
    assert labels["1.43"]["label_grc"] == "Περὶ ῥοδίνου σκευασίας" and "1.53" not in labels
    assert concordance.relabel(table, None, "sprengel1829") is table


def test_links_to_part_of_a_wellmann_chapter_keep_their_span(tmp_path):
    head = "urn_a\trelation\turn_b\tstatus\tw_from\tw_to\n"
    rows = [[M + "1.40", "edition_of", W + "1.42.1", "proposed", "0", "48"],
            [M + "1.41", "edition_of", W + "1.42.2", "proposed", "48", "122"],
            [M + "1.30", "edition_of", W + "1.30.6@ὁ[2]-ἐπιτιθέμενος[2]", "proposed", "475", "501"],
            [M + "1.43", "edition_of", W + "1.44", "proposed", "", ""]]
    data = (head + "".join("\t".join(r) + "\n" for r in rows)).encode()
    (tmp_path / "edition_of.tsv").write_bytes(data)
    lock = {"repository": "alchemiesofscent/concordance", "commit": "abc", "vendored": "edition_of.tsv",
            "rows": len(rows), "edition_of_sha256": hashlib.sha256(data).hexdigest()}
    (tmp_path / "concordance.lock.json").write_text(json.dumps(lock))
    entry = concordance.load(tmp_path / "concordance.lock.json")["mattioli1554"]
    assert entry["to_wellmann"] == {"1.40": ["1.42"], "1.41": ["1.42"], "1.30": ["1.30"], "1.43": ["1.44"]}
    assert entry["spans"] == {"1.40": [["1.42", 0, 48, "1.42.1"]], "1.41": [["1.42", 48, 122, "1.42.2"]],
                              "1.30": [["1.30", 475, 501, "1.30.6 (part)"]]}
    assert concordance.wellmann_label("1.105.1-1.105.5") == "1.105.1-5"
