"""Synthetic wording only: no restricted translation fixtures belong in Git."""
import json
from pathlib import Path

import pytest

from dioscorides_reader.__main__ import main
from dioscorides_reader.bundle import Bundle, sha256
from dioscorides_reader.compiler import compile_bundle
from dioscorides_reader.private_streams import KEY, LABEL, check_public_output
from test_bundle import make_bundle, rewrite_manifest, TEI, snapshot

TEXT = 'Synthetic fixture words for testing private reader isolation without using any actual translation.'


@pytest.fixture
def private_bundle(tmp_path):
    bundle = make_bundle(tmp_path / 'bundle')
    path = 'payload/editions/dioscorides-inhouse/tei/dioscorides-inhouse.xml'
    target = bundle / path
    target.parent.mkdir(parents=True)
    target.write_text(TEI.replace('xml:lang="eng"', 'xml:lang="en"')
                      .replace('reading</lem>', TEXT + '</lem>')
                      .replace('../listWit.xml', '../../beck/listWit.xml')
                      .replace('xml:id="ch-1"', 'xml:id="DSC_DMM-1.1" corresp="wellmann1906.xml#n:1.1"')
                      .replace("<p>\n<app>", "<ab>\n<app>").replace("</ref></p>", "</ref></ab>"))
    def add(manifest):
        manifest['files'].append({'path': path, 'sha256': sha256(target), 'size': target.stat().st_size})
        manifest['editions'].append({'id': KEY, 'edition_id': KEY, 'label': LABEL,
            'status': 'draft', 'restricted': True, 'ruling': 'D42', 'tei_path': path,
            'source_sha256': sha256(target)})
    rewrite_manifest(bundle, add)
    return bundle


def test_cli_private_build_has_stream_and_draft_metadata(private_bundle, tmp_path):
    output = tmp_path / 'private'
    assert main(['build', '--bundle', str(private_bundle), '--output', str(output),
                 '--private-include', KEY]) == 0
    edition = json.loads((output / 'data/manifest.json').read_text())['editions'][KEY]
    assert (edition['label'], edition['restricted'], edition['ruling']) == (LABEL, True, 'D42')
    book = json.loads((output / f'data/{KEY}/book-1.json').read_text())
    assert TEXT in book['chapters']['1']['html']
    assert edition['pairing']['to_wellmann']['1.1'] == ['1.1']


def test_unflagged_build_omits_private_stream(private_bundle, tmp_path):
    output = tmp_path / 'public'
    result = compile_bundle(private_bundle, output)
    assert KEY not in result['editions']
    assert not (output / 'data' / KEY).exists()
    assert check_public_output(output, Bundle(private_bundle)) == []


@pytest.mark.parametrize('leak', ['id', 'text', 'escaped-text', 'filename'])
def test_guard_rejects_private_leaks_with_no_stream_metadata(private_bundle, tmp_path, leak):
    output = tmp_path / 'bad'
    output.mkdir()
    target = output / ('dioscorides-inhouse.bin' if leak == 'filename' else 'stray.json')
    value = KEY if leak == 'id' else TEXT
    content = json.dumps({'html': '<p>' + value + '</p>'})
    if leak == 'escaped-text':
        content = content.replace('Synthetic', r'\u0053ynthetic')
    target.write_text(content)
    assert check_public_output(output, Bundle(private_bundle))


def test_guard_runs_before_replacing_completed_output(private_bundle, tmp_path, monkeypatch):
    from dioscorides_reader import compiler
    output = tmp_path / 'public'
    compile_bundle(private_bundle, output)
    before = snapshot(output)
    original = compiler.render.build_edition
    def corrupted(config, table, report, data):
        result = original(config, table, report, data)
        (data / 'stray.json').write_text(json.dumps({'text': TEXT}))
        return result
    monkeypatch.setattr(compiler.render, 'build_edition', corrupted)
    with pytest.raises(ValueError, match='restricted material'):
        compile_bundle(private_bundle, output)
    assert snapshot(output) == before


def test_private_restriction_metadata_is_required(private_bundle, tmp_path):
    rewrite_manifest(private_bundle, lambda m: m['editions'][-1].pop('restricted'))
    with pytest.raises(ValueError, match='D42 restriction'):
        compile_bundle(private_bundle, tmp_path / 'bad', private_include=(KEY,))


def test_workflows_never_enable_private_flag():
    root = Path(__file__).resolve().parents[1]
    for path in (root / '.github/workflows').iterdir():
        assert '--private-include' not in path.read_text()
    pages = (root / '.github/workflows/pages.yml').read_text()
    assert '--exclude beck2020 --exclude paul-heiberg-vii' in pages


def test_preface_pairs_by_explicit_source_target(private_bundle, tmp_path):
    path = private_bundle / 'manifest.json'
    manifest = json.loads(path.read_text())
    entry = manifest['editions'][-1]
    tei = private_bundle / entry['tei_path']
    tei.write_text(tei.read_text().replace('subtype="chapter" n="1"', 'subtype="chapter" n="preface"')
                   .replace('wellmann1906.xml#n:1.1', 'wellmann1906.xml#n:1.praef'))
    def update(m):
        m['editions'][-1]['source_sha256'] = sha256(tei)
        record = next(f for f in m['files'] if f['path'] == entry['tei_path'])
        record.update(sha256=sha256(tei), size=tei.stat().st_size)
    rewrite_manifest(private_bundle, update)
    result = compile_bundle(private_bundle, tmp_path / 'private', private_include=(KEY,))
    assert result['editions'][KEY]['pairing']['to_wellmann']['1.preface'] == ['1.praef']


@pytest.mark.parametrize('content', [r'{"edition":"\u0064ioscorides-inhouse"}',
                                     '{"edition":"&#100;ioscorides-inhouse"}',
                                     r'{"\u0064ioscorides-inhouse":true}'])
def test_guard_rejects_encoded_identifiers(private_bundle, tmp_path, content):
    output = tmp_path / 'encoded'
    output.mkdir()
    (output / 'data.json').write_text(content)
    assert check_public_output(output, Bundle(private_bundle))


def test_guard_fails_closed_without_text_coverage(private_bundle, tmp_path, monkeypatch):
    from dioscorides_reader import private_streams
    output = tmp_path / 'empty'
    output.mkdir()
    monkeypatch.setattr(private_streams, 'words', lambda value: [])
    assert 'no running-text fingerprints' in check_public_output(output, Bundle(private_bundle))[0]


def test_shared_source_phrase_allowed_only_in_its_own_book(private_bundle, tmp_path):
    from test_bundle import TEI_PATH
    source = private_bundle / TEI_PATH
    source.write_text(source.read_text().replace('reading</lem>', TEXT + '</lem>'))
    def update(m):
        m['editions'][0]['source_sha256'] = sha256(source)
        record = next(f for f in m['files'] if f['path'] == TEI_PATH)
        record.update(sha256=sha256(source), size=source.stat().st_size)
    rewrite_manifest(private_bundle, update)
    output = tmp_path / 'shared'
    compile_bundle(private_bundle, output)
    assert not check_public_output(output, Bundle(private_bundle))
    (output / 'stray.json').write_text(json.dumps({'text': TEXT}))
    assert check_public_output(output, Bundle(private_bundle))
