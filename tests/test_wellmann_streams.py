"""Small physical-page fixture: semantic owners, continuations and leak failures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
from lxml import html
from dioscorides_reader import render

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check_wellmann_streams.py'
spec = importlib.util.spec_from_file_location('wellmann_checker', SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def built(tmp_path):
    source = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div subtype="book" n="3">
      <pb n="75"/><div subtype="chapter" n="64" xml:id="wellmann1906-3-64"><p>κύριον</p></div>
      <div subtype="chapter" n="65" xml:id="wellmann1906-3-65"><p>ἕτερον</p><pb n="76"/>
      <ab type="recension" subtype="RV" n="64" corresp="#wellmann1906-3-64"><lb n="20"/>σέλινον συνώνυμα</ab></div>
      <div subtype="chapter" n="64RV" rend="bracketed" xml:id="wellmann1906-3-64RV"><head>Caput 64RV</head><p>παρέμβλητον</p></div>
      <div subtype="chapter" n="73a" rend="bracketed" xml:id="wellmann1906-3-73a"><p>κανονικόν</p></div>
      </div><div subtype="book" n="4"><div subtype="chapter" n="127" xml:id="wellmann1906-4-127">
      <p>κυρίως</p><pb n="273"/><ab type="recension" subtype="RV" n="127" part="I" corresp="#wellmann1906-4-127"><lb n="20"/>δι-</ab>
      <pb n="274"/><ab type="recension" subtype="RV" part="F" corresp="#wellmann1906-4-127"><lb n="18" break="no"/>πλοῦν</ab></div>
      <div subtype="chapter" n="164" xml:id="wellmann1906-4-164"><p>ῥίζα</p><pb n="311"/>
      <ab type="recension" subtype="RV" n="164" corresp="#wellmann1906-4-164"><ptr type="rv-line-key" n="18" target="#line"/><lb n="18"/>παραλλαγή</ab></div>
      <div subtype="chapter" n="58RV" xml:id="wellmann1906-4-58RVRV"><head>Caput 58RV</head>
      <ab type="recension" subtype="RV" n="58RV" rend="bracketed" corresp="#wellmann1906-4-58RVRV"><lb n="11"/>χρυσάνθεμον</ab></div>
      </div></body></text></TEI>'''
    bundle = tmp_path / 'bundle'
    tei = bundle / 'payload/Wellmann_Dioscorides/tei/wellmann1906.xml'
    tei.parent.mkdir(parents=True)
    tei.write_text(source)
    root = ET.fromstring(source)
    cfg = {'key': 'wellmann1906', 'facs': 'none', 'anchored_notes': False, 'label_source': 'head'}
    renderer = render.ChapterRenderer(cfg, tei, {}, render.Report())
    renderer.recensions = render.recension_groups(root)
    entry_pages = render.chapter_entry_page_breaks(root)
    dist = tmp_path / 'dist'
    output = dist / 'data/wellmann1906'
    output.mkdir(parents=True)
    chapters = {}
    projection = []
    for book in root.findall('.//' + render.TEI + 'div[@subtype="book"]'):
        data = {}
        for ch in book.findall(render.TEI + 'div'):
            n = ch.get('n')
            result = renderer.render_chapter(ch, entry_pages.get(ch))
            data[n] = result
            chapters[(book.get('n'), n)] = result
            if not render.is_bracketed_rv(ch):
                projection.append({'id': render.xml_id(ch), 'text': ch.find(render.TEI + 'p').text})
        (output / f'book-{book.get("n")}.json').write_text(json.dumps({'chapters': data}))
    Path(str(tei) + '.main-stream.json').write_text(json.dumps({'chapters': projection}))
    return dist, bundle, chapters, cfg, root


def test_recension_placement_labels_and_page_join(built):
    dist, bundle, chapters, cfg, root = built
    ch64 = html.fromstring(chapters['3', '64']['html'])
    assert 'σέλινον' in ch64.text_content()
    assert 'σέλινον' not in chapters['3', '65']['html']
    assert 'σέλινον' not in checker.html_text(ch64, main=True)
    joined = html.fromstring(chapters['4', '127']['html'])
    groups = joined.xpath('.//*[@class="tei-recension"]')
    assert len(groups) == 1
    assert checker.tokens(checker.html_text(groups[0])) == ['διπλοῦν']
    assert [p['n'] for p in chapters['4', '127']['pages']][-2:] == ['273', '274']
    assert joined.xpath('.//*[@class="rv-label"]/text()') == ['127 RV']
    assert '18 RV' in chapters['4', '164']['html']
    bracketed = chapters['3', '64RV']
    assert '[64 RV]' in bracketed['html'] and 'Caput 64RV' not in bracketed['html']
    assert bracketed['id'] == 'wellmann1906-3-64RV'
    ch = root.find('.//' + render.TEI + 'div[@n="64RV"]')
    assert render.chapter_label(cfg, '3', '64RV', ch, {}, render.Report()) == '[64 RV]'
    assert 'tei-rv-bracketed' not in chapters['3', '73a']['html']
    inner_brackets = chapters['4', '58RV']['html']
    assert '[58 RV]' in inner_brackets and '58RV RV' not in inner_brackets
    assert 'Caput 58RV' not in inner_brackets
    assert 'χρυσάνθεμον' in inner_brackets
    result = subprocess.run([sys.executable, str(SCRIPT), str(dist), str(bundle)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'RV/C segments: 5; RV/C blocks: 4' in result.stdout
    assert 'Mismatches: 0' in result.stdout


@pytest.mark.parametrize('damage', ['main-leak', 'lost-segment', 'wrong-owner', 'changed-rv'])
def test_checker_rejects_corruption(built, damage):
    dist, bundle, *_ = built
    path = dist / 'data/wellmann1906/book-3.json'
    book = json.loads(path.read_text())
    ch = book['chapters']['64']
    if damage == 'main-leak':
        ch['html'] = ch['html'].replace('κύριον', 'κύριον σέλινον')
    elif damage == 'lost-segment':
        ch['html'] = ch['html'].replace('data-rv-segment="0"', 'data-lost="0"')
    elif damage == 'wrong-owner':
        book['chapters']['65']['html'] += ch['html']
        ch['html'] = '<div>κύριον</div>'
    else:
        ch['html'] = ch['html'].replace('συνώνυμα', 'ἀλλαγή')
    path.write_text(json.dumps(book))
    assert checker.check(dist, bundle) > 0
