#!/usr/bin/env python3
"""Check built Wellmann main text and every separately rendered recension.

Usage: python scripts/check_wellmann_streams.py DIST BUNDLE
Only the pinned bundle is read; no producer checkout is required.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata
from lxml import etree, html

NS = {'t': 'http://www.tei-c.org/ns/1.0'}
XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
SKIP = {'pb', 'fw', 'chapter-head', 'rv-label', 'rv-bracket', 'note-inline',
        'note-block', 'fnref', 'tr-note', 'app-standoff', 'app-empty',
        'gap', 'eol-hyphen'}


def tokens(text):
    text = re.sub(r'[-‐‑]?\s*\ue000\s*', '', text)
    return unicodedata.normalize('NFC', text).split()


def html_text(node, *, main=False):
    classes = set(node.get('class', '').split())
    if classes & SKIP or (main and classes & {'tei-recension', 'tei-rv-bracketed'}):
        return ''
    if 'lb' in classes:
        return '\ue000' if 'nobreak' in classes else ' '
    value = (node.text or '') + ''.join(html_text(c, main=main) + (c.tail or '') for c in node)
    if 'tei-supplied' in classes:
        value = value.removeprefix('⟨').removesuffix('⟩')
    if 'tei-surplus' in classes or 'tei-del-brackets' in classes:
        value = value.removeprefix('[').removesuffix(']')
    return ' ' + value + ' ' if node.tag in {'p', 'div', 'section'} else value


def tei_text(node):
    """Independent running-lemma projection of a recension, with break semantics."""
    tag = etree.QName(node).localname
    if tag in {'note', 'rdg', 'head', 'fw', 'ptr'}:
        return ''
    if tag == 'lb':
        return '\ue000' if node.get('break') == 'no' else ' '
    if tag == 'pb':
        return ' '
    if tag == 'app':
        lemma = node.find('t:lem', NS)
        return tei_text(lemma) if lemma is not None else ''
    value = (node.text or '') + ''.join(tei_text(c) + (c.tail or '') for c in node)
    return ' ' + value + ' ' if tag in {'p', 'div'} else value


def check(dist: Path, bundle: Path):
    tei = next(bundle.glob('payload/**/wellmann1906.xml'))
    tree = etree.parse(str(tei))
    projection = json.loads(Path(str(tei) + '.main-stream.json').read_text())
    expected = {c['id']: c['text'] for c in projection['chapters']}
    chapters = {}
    for path in sorted((dist / 'data/wellmann1906').glob('book-*.json')):
        book = json.loads(path.read_text())
        for ch in book['chapters'].values():
            chapters[ch['id']] = html.fromstring(ch['html'])
    errors = []
    def compare(label, actual, wanted):
        a, b = tokens(actual), tokens(wanted)
        if a != b:
            i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            errors.append(f'{label}: {len(a)} != {len(b)} tokens; at {i}: {a[max(0,i-3):i+5]!r} != {b[max(0,i-3):i+5]!r}')
    for ident, wanted in expected.items():
        if ident not in chapters:
            errors.append(f'Missing chapter {ident}')
        else:
            compare(ident, html_text(chapters[ident], main=True), wanted)
    bracketed_nodes = {n.get(XML_ID): n for n in tree.xpath('//t:div[@subtype="chapter"]', namespaces=NS)
                       if 'RV' in n.get('n', '') and (n.get('rend') == 'bracketed' or
                           n.find('t:ab[@type="recension"][@rend="bracketed"]', NS) is not None)}
    bracketed = set(bracketed_nodes)
    for ident, source in bracketed_nodes.items():
        if ident not in chapters:
            errors.append(f'Missing bracketed RV chapter {ident}')
        elif source.get('rend') == 'bracketed':
            compare(f'{ident} bracketed text', html_text(chapters[ident]), tei_text(source))
    manifest_path = dist / 'data/manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        # Routes can differ from xml:id (58RV/190RV retain IDs ending in RVRV).
        rv_keys = {f'{n.getparent().get("n")}.{n.get("n")}' for n in bracketed_nodes.values()}
        for name, edition in manifest['editions'].items():
            pairing = edition.get('pairing', {})
            for key, targets in pairing.get('to_wellmann', {}).items():
                if rv_keys.intersection(targets):
                    errors.append(f'{name} {key}: bracketed RV in translation pairs')
    for ident, node in chapters.items():
        if ident not in expected and ident not in bracketed:
            errors.append(f'Unexpected chapter {ident}')
        if ident in bracketed and node.find('.//*[@class="tei-rv-bracketed"]') is None:
            errors.append(f'Missing bracket wrapper {ident}')
    segments = tree.xpath('//t:ab[@type="recension"]', namespaces=NS)
    seen = Counter()
    group_count = 0
    for ident, chapter in chapters.items():
        for group in chapter.xpath('.//*[contains(concat(" ", @class, " "), " tei-recension ")]'):
            group_count += 1
            indexes = []
            for node in group.xpath('.//*[@data-rv-segment]'):
                index = int(node.get('data-rv-segment'))
                seen[index] += 1
                if index >= len(segments):
                    errors.append(f'Unknown RV segment {index}')
                    continue
                source = segments[index]
                if source.get('corresp') != '#' + ident:
                    errors.append(f'RV segment {index} under wrong owner {ident}')
                indexes.append(index)
            wanted = ' '.join(tei_text(segments[i]) for i in indexes)
            compare(f'{ident} RV group {group_count}', html_text(group), wanted)
        for node in chapter.xpath('.//*[@data-rv-segment]'):
            if not any('tei-recension' in p.get('class', '').split() for p in node.iterancestors()):
                errors.append(f'RV segment outside RV block: {node.get("data-rv-segment")}')
    for i in range(len(segments)):
        if seen[i] != 1:
            errors.append(f'RV segment {i}: rendered {seen[i]} times, expected once')
    print(f'Main chapters: {len(expected)}; bracketed RV chapters: {len(bracketed)}; '
          f'RV/C segments: {len(segments)}; RV/C blocks: {group_count}')
    for error in errors:
        print(error)
    print(f'Mismatches: {len(errors)}')
    return len(errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dist', type=Path)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    return int(bool(check(args.dist, args.bundle)))


if __name__ == '__main__':
    raise SystemExit(main())
