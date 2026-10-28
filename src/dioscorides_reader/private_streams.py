"""D42 private inclusion and public-output guard, independent of UI selection."""
from html import unescape
import json
from pathlib import Path
import re
import unicodedata
from lxml import etree

KEY = 'dioscorides-inhouse'
LABEL = 'In-house draft, not yet reviewed'


def words(value):
    return re.findall(r'\w+', unicodedata.normalize('NFC', unescape(re.sub(r'<[^>]*>', ' ', value))))


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def check_public_output(dist: Path, bundle) -> list[str]:
    """Reject IDs anywhere and copied running text even if its edition ID was removed.

    Text fingerprints cover each 12-word source window, plus complete shorter
    text blocks of at least four words. Diagnostics never include source wording.
    """
    ids = {KEY, 'DSC_DMM-'}
    fingerprints = {}
    for entry in bundle.manifest['editions']:
        if entry['id'] != KEY:
            continue
        tree = etree.parse(str(bundle.path(entry['tei_path'])),
                           etree.XMLParser(resolve_entities=False, no_network=True))
        for node in tree.xpath('//*[local-name()="p" or local-name()="ab"][ancestor::*[local-name()="body"]]'):
            tokens = words(' '.join(node.itertext()))
            size = min(12, len(tokens))
            if size >= 4:
                fingerprints.setdefault(size, set()).update(
                    tuple(tokens[i:i+size]) for i in range(len(tokens)-size+1))
    # Shared wording is permitted only in book output of the edition whose
    # verified source attests it. A stray file has no such source authority.
    manifest_path = dist / 'data/manifest.json'
    included = (json.loads(manifest_path.read_text())['editions']
                if manifest_path.is_file() else {})
    sources = {e['id']: e for e in bundle.manifest['editions']
               if e['id'] != KEY and e['id'] in included}
    attested = {}
    def source_windows(edition, size):
        cache_key = (edition, size)
        if cache_key not in attested:
            tree = etree.parse(str(bundle.path(sources[edition]['tei_path'])),
                               etree.XMLParser(resolve_entities=False, no_network=True))
            body = tree.xpath('//*[local-name()="body"]')
            tokens = words(' '.join(' '.join(node.itertext()) for node in body))
            attested[cache_key] = {tuple(tokens[i:i+size]) for i in range(len(tokens)-size+1)
                                   if tuple(tokens[i:i+size]) in fingerprints[size]}
        return attested[cache_key]
    errors = []
    if any(e['id'] == KEY for e in bundle.manifest['editions']) and not fingerprints:
        errors.append('Restricted in-house source has no running-text fingerprints')
    for path in sorted(dist.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(dist).as_posix()
        raw = path.read_bytes()
        if any(ident in relative or ident.encode() in raw for ident in ids):
            errors.append(f'Restricted in-house identifier in {relative}')
            continue
        if path.suffix not in {'.json', '.html', '.js', '.md', '.txt', '.xml'}:
            continue
        value = raw.decode('utf-8', errors='replace')
        if path.suffix == '.json':
            value = ' '.join(strings(json.loads(value)))
        if any(ident in unescape(value) for ident in ids):
            errors.append(f'Restricted in-house identifier in {relative}')
            continue
        tokens = words(value)
        own = re.fullmatch(r'data/([^/]+)/book-[^/]+\.json', relative)
        for size, samples in fingerprints.items():
            matches = {tuple(tokens[i:i+size]) for i in range(len(tokens)-size+1)
                       if tuple(tokens[i:i+size]) in samples}
            if matches and own and own.group(1) in sources:
                matches -= source_windows(own.group(1), size)
            if matches:
                errors.append(f'Restricted in-house text in {relative}')
                break
    return errors


def chapter_pairing(bundle, entry):
    """Use the source's explicit chapter targets, including prefaces/arguments."""
    ns = {"t": "http://www.tei-c.org/ns/1.0"}
    tree = etree.parse(str(bundle.path(entry['tei_path'])),
                       etree.XMLParser(resolve_entities=False, no_network=True))
    targets = {}
    reverse = {}
    for chapter in tree.xpath('//t:div[@subtype="book"]/t:div[@subtype="chapter"]', namespaces=ns):
        key = chapter.getparent().get('n') + '.' + chapter.get('n')
        correspondences = chapter.get('corresp', '').split()
        mapped = []
        for correspondence in correspondences:
            match = re.fullmatch(r'wellmann1906\.xml#n:([1-5]\.[^\s.]+)', correspondence)
            if not match:
                raise ValueError("Private chapter requires an explicit Wellmann chapter target")
            mapped.append(match.group(1))
        if not mapped:
            raise ValueError("Private chapter lacks a Wellmann chapter target")
        targets[key] = mapped
        for target in mapped:
            reverse.setdefault(target, []).append(key)
    return {"to_wellmann": targets, "from_wellmann": reverse}
