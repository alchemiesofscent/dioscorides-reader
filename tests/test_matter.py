"""Matter rendering uses source text and only the exported target resolutions."""
import json
import xml.etree.ElementTree as ET

import pytest

from dioscorides_reader import render
from dioscorides_reader.matter import MatterRenderer, target_routes, errata_lines

NS = render.TEI.strip('{}')


def element(xml):
    return ET.fromstring(f'<div xmlns="{NS}">{xml}</div>')


def renderer(tmp_path, **kwargs):
    report = render.Report()
    cfg = {'key': 'berendes1902', 'lang': 'deu', 'facs': 'none', 'anchored_notes': True}
    return MatterRenderer(cfg, tmp_path / 'text.xml', {}, report, **kwargs), report


def index_payload():
    return {'registers': [{'entries': [{
        'id': 'idx-1', 'index_page': '559', 'index_line': '4',
        'headword': 'Bartgras', 'resolved_headword': 'Bartgras',
        'references': [
            {'page': '63', 'page_kind': 'printed', 'chapter_keys': ['target', 'nested']},
            {'page': '99', 'page_kind': 'printed', 'chapter_keys': []},
        ], 'english_renderings': [{'form': 'beard grass', 'unit_count': 1}],
    }]}]}


def test_front_matter_pages_lines_and_notes(tmp_path):
    r, report = renderer(tmp_path)
    div = element('<pb n="V"/><head>Vorwort</head><p><lb n="1"/>Prose '
                  '<ref type="footnote-ref" target="#fn">1</ref></p>'
                  '<note type="footnote" xml:id="fn" corresp="#mark">Footnote</note>')
    div.set('type', 'front_matter')
    result = r.render_chapter(div)
    assert 'Vorwort' in result['html'] and 'data-n="1"' in result['html']
    assert result['pages'] == [{'n': 'V', 'facs': None}]
    assert result['refNoteIds'] == ['fn']
    assert 'Footnote' in r.notes['fn']
    assert report.items == []


def test_errata_german_refs_and_translated_segments(tmp_path):
    routes = {'correction': '1.2'}
    german = element('<p><lb n="9"/><ref target="#correction">lies Bartgras</ref></p>')
    german.set('type', 'errata')
    english = element('<p><seg><lb n="9"/>read beard grass</seg></p>')
    english.set('type', 'errata')
    for div, text in [(german, 'lies Bartgras'), (english, 'read beard grass')]:
        r, report = renderer(tmp_path, routes=routes, errata={'9': 'correction'})
        html = r.render_chapter(div)['html']
        assert 'class="matter-link"' in html and '/1.2"' in html and text in html
        assert report.items == []


def test_index_preserves_print_multi_targets_plain_unresolved_and_english(tmp_path):
    r, report = renderer(tmp_path, index=index_payload(), routes={'target': '1.2', 'nested': '4.152'})
    div = element('<pb n="559"/><head>Sachregister</head><head>A.</head>'
                  '<p part="I"><lb n="4"/>Bartgras<lb n="5"/>63f. 99.</p>')
    div.set('type', 'index')
    result = r.render_chapter(div)
    html = result['html']
    assert result['kind'] == 'index'
    assert 'Sachregister' in html and 'A.' in html and 'part-I' in html
    assert html.count('class="matter-link"') == 1
    assert '>63</a>f. 99.' in html
    assert '4.152' in html and 'nested' in html
    assert 'beard grass' in html and 'data-headword="Bartgras Bartgras beard grass"' in html
    assert report.items == []


def test_index_rejects_missing_targets_and_print_mismatch(tmp_path):
    div = element('<pb n="559"/><p><lb n="4"/>Bartgras 64. 99.</p>')
    div.set('type', 'index')
    r, _ = renderer(tmp_path, index=index_payload())
    with pytest.raises(ValueError, match='differs from payload'):
        r.render_chapter(div)
    r, _ = renderer(tmp_path)
    with pytest.raises(ValueError, match='no chapter route'):
        r.link(['missing'], '63')


def test_route_mapping_keeps_nested_identity(tmp_path):
    stream = element('<div subtype="book" n="4"><div subtype="chapter" n="152" xml:id="ch">'
                     '<div subtype="section" xml:id="nested"><choice xml:id="correction"/></div>'
                     '</div></div>')
    assert target_routes(stream) == {'ch': '4.152', 'nested': '4.152', 'correction': '4.152'}


def test_build_matter_routes_and_cross_section_notes(tmp_path, monkeypatch):
    source = tmp_path / 'input.xml'
    source.write_text(f'''<TEI xmlns="{NS}"><text><front><div type="front_matter">
      <head>Vorwort</head><p><ref type="footnote-ref" target="#fn">1</ref></p>
      <note type="footnote" xml:id="fn" corresp="#mark">Front note</note></div></front>
      <body><div type="translation"><div subtype="book" n="1">
      <div subtype="chapter" n="1"><head>Chapter</head></div></div></div></body>
      <back><div type="errata"><head>Verbesserungen</head><p><ref target="#correction">Correction</ref>
      <ref type="footnote-ref" target="#fn">1</ref></p></div>
      <div type="index"><head>Sachregister</head><p>Printed index</p></div></back></text></TEI>''')
    monkeypatch.setattr(render, 'ROOT', tmp_path)
    monkeypatch.setattr(render, 'parse_tei', lambda path: ET.parse(path).getroot())
    cfg = {'key': 'berendes1902', 'tei_path': 'input.xml', 'label': 'Berendes', 'lang': 'deu',
           'stream': {'type': 'translation'}, 'facs': 'none', 'label_source': 'head',
           'anchored_notes': True, 'include_matter': True, 'matter_routes': {'correction': '1.1'}}
    report = render.Report()
    edition = render.build_edition(cfg, {}, report, tmp_path / 'data')
    assert [book['n'] for book in edition['books']] == ['front', '1', 'back']
    assert [c['n'] for c in edition['books'][-1]['chapters']] == ['errata', 'index']
    back = json.loads((tmp_path / 'data/berendes1902/book-back.json').read_text())
    assert back['chapters']['errata']['noteIds'] == ['fn']
    assert 'Front note' in back['notes']['fn']
    assert report.items == []


def test_compiler_reads_shared_verified_auxiliary_for_both_languages(tmp_path):
    from dioscorides_reader.bundle import manifest_id, sha256
    from dioscorides_reader.compiler import compile_bundle

    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    german = f'''<TEI xmlns="{NS}"><text><front><div type="front_matter"><head>Vorwort</head></div></front>
    <body><div type="translation"><div subtype="book" n="1"><div subtype="chapter" n="2" xml:id="target">
    <head>Bartgras</head><p><choice xml:id="correction"><sic>Strandbinse</sic><corr>Bartgras</corr></choice></p>
    <div subtype="section" xml:id="nested"/></div></div></div></body><back>
    <div type="errata"><p><lb n="9"/><ref target="#correction">lies Bartgras</ref></p></div>
    <div type="index"><pb n="559" facs="https://digi.ub.uni-heidelberg.de/diglitData/image/berendes1902/3/0_559.jpg"/><head>Sachregister</head><p><lb n="4"/>Bartgras 63f. 99.</p></div>
    </back></text></TEI>'''
    english = german.replace('<div type="translation">', '<div type="translation" xml:lang="eng">')
    english = english.replace('Vorwort', 'Preface').replace(
        '<lb n="9"/><ref target="#correction">lies Bartgras</ref>',
        '<seg><lb n="9"/>read beard grass</seg>')
    values = {'payload/de.xml': german, 'payload/en.xml': english,
              'payload/editions/sprengel/sprengel_chapter_table.tsv': 'n\tlabel_grc\tlabel_la\n',
              'payload/facsimiles.json': json.dumps({'schema': 'facsimiles/1', 'resources': []}),
              'payload/index.json': json.dumps({**index_payload(), 'schema': 'berendes-reader-index/1',
                                                'edition': 'berendes1902'})}
    files = []
    for key, value in values.items():
        path = bundle / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        files.append({'path': key, 'sha256': sha256(path), 'size': path.stat().st_size})
    editions = [{'id': key, 'tei_path': path, 'source_sha256': sha256(bundle / path), 'status': 'draft'}
                for key, path in [('berendes1902', 'payload/de.xml'), ('berendes1902-eng', 'payload/en.xml')]]
    editions[0]['auxiliary'] = [{'id': 'sachregister', 'schema': 'berendes-reader-index/1',
                                'path': 'payload/index.json', 'sha256': sha256(bundle / 'payload/index.json')}]
    manifest = {'schema': 'dioscorides-corpus-export/1', 'producer_commit': 'a' * 40,
                'files': files, 'editions': editions}
    manifest['bundle_id'] = manifest_id(manifest)
    (bundle / 'manifest.json').write_text(json.dumps(manifest))
    output = tmp_path / 'output'
    result = compile_bundle(bundle, output)
    for key in ['berendes1902', 'berendes1902-eng']:
        assert [b['n'] for b in result['editions'][key]['books']] == ['front', '1', 'back']
        back = json.loads((output / f'data/{key}/book-back.json').read_text())
        assert 'beard grass' in back['chapters']['index']['html']
        assert 'matter-link' in back['chapters']['errata']['html']
    assert 'No undecidable items' in (output / 'data/REPORT.md').read_text()
    editions[0]['auxiliary'][0]['sha256'] = '0' * 64
    manifest['bundle_id'] = manifest_id(manifest)
    (bundle / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='auxiliary digest'):
        compile_bundle(bundle, output)
