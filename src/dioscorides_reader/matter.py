"""Presentation of TEI front/back sections and the bundled Berendes register."""
from __future__ import annotations

import copy
import json
import re
import xml.etree.ElementTree as ET

from .render import ChapterRenderer, TEI, esc
from .xml_utils import xml_id, norm_space


def target_routes(stream: ET.Element) -> dict[str, str]:
    """Retain source identities, locating each within its actual chapter."""
    routes = {}
    for book in stream.findall(f'{TEI}div'):
        for chapter in book.findall(f'{TEI}div'):
            if chapter.get('subtype') != 'chapter':
                continue
            route = f"{book.get('n')}.{chapter.get('n')}"
            for element in chapter.iter():
                if xml_id(element):
                    routes[xml_id(element)] = route
    return routes


def errata_lines(root: ET.Element) -> dict[str, str]:
    lines = {}
    section = root.find(f'{TEI}text/{TEI}back/{TEI}div[@type="errata"]')
    if section is not None:
        line = ''
        for element in section.iter():
            if element.tag == f'{TEI}lb':
                line = element.get('n', '')
            elif element.tag == f'{TEI}ref' and element.get('target', '').startswith('#'):
                lines[line] = element.get('target')[1:]
    return lines


class MatterRenderer(ChapterRenderer):
    def __init__(self, *args, routes=None, index=None, errata=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.routes = routes or {}
        self.entries = {(entry['index_page'], entry['index_line']): entry
                        for register in (index or {}).get('registers', [])
                        for entry in register['entries']}
        self.errata = errata or {}
        self.section_type = ''
        self.index_page = ''
        self.seen_entries = set()

    def link(self, targets: list[str], text: str) -> str:
        records = [{'route': self.routes[target], 'target': target}
                   for target in targets if target in self.routes]
        if len(records) != len(targets):
            raise ValueError(f'Matter reference has no chapter route: {targets}')
        if not records:
            return text
        href = f"#/{self.cfg['key']}/-/{records[0]['route']}"
        title = '; '.join(f"{record['route']} ({record['target']})" for record in records)
        return (f'<a class="matter-link" href="{esc(href)}" '
                f'data-targets="{esc(json.dumps(records))}" title="{esc(title)}">{text}</a>')

    def el_ref(self, el, out):
        target = el.get('target', '').removeprefix('#')
        if (self.section_type == 'errata' and el.get('type') != 'footnote-ref'
                and target in self.routes):
            inner = []
            self.render_children(el, inner)
            out.append(self.link([target], ''.join(inner)))
        else:
            super().el_ref(el, out)

    def el_seg(self, el, out):
        # Translation segments retain the printed line identity, but no ref.
        line = el.find(f'{TEI}lb')
        target = self.errata.get(line.get('n')) if line is not None else None
        if self.section_type == 'errata' and target:
            inner = []
            self.render_children(el, inner)
            out.append(self.link([target], ''.join(inner)))
        else:
            super().el_seg(el, out)

    def el_pb(self, el, out):
        self.index_page = el.get('n', '')
        super().el_pb(el, out)

    def index_line(self, line: ET.Element, number: str, out: list[str]) -> None:
        entry = self.entries.get((self.index_page, number))
        inner = []
        self.render_children(line, inner)
        text = ''.join(inner)
        if entry:
            self.seen_entries.add(entry['id'])
            # Replace only text-node number tokens, from the right: the printed
            # reference list follows the headword. Keep punctuation and suffixes.
            parts = re.split(r'(<[^>]*>)', text)
            positions = [(i, match) for i in range(0, len(parts), 2)
                         for match in re.finditer(r'(?<!\w)\d+(?!\d)', parts[i])]
            references = [ref for ref in entry['references'] if ref['page_kind'] == 'printed']
            cursor = len(positions)
            for ref in reversed(references):
                cursor -= 1
                if cursor < 0 or positions[cursor][1].group() != ref['page']:
                    raise ValueError(f"Printed index reference differs from payload: {entry['id']}")
                i, match = positions[cursor]
                parts[i] = (parts[i][:match.start()] + self.link(ref['chapter_keys'], match.group())
                            + parts[i][match.end():])
            text = ''.join(parts)
            renderings = []
            for rendering in entry['english_renderings']:      # "Beard grass" and "beard grass" are one
                form = rendering['form'].replace('_', '').strip()
                # a chapter head gives "German [English]": drop the repeated German headword
                for head in (entry['resolved_headword'], entry['headword']):
                    if head and form.casefold().startswith(head.casefold() + ' ') and form.casefold() != head.casefold():
                        form = form[len(head):].strip()
                        break
                if form and form.casefold() not in {r.casefold() for r in renderings}:
                    renderings.append(form)
            if renderings:
                text += f' <span class="index-english">— {esc("; ".join(renderings))}</span>'
            search = norm_space(' '.join([entry['headword'], entry['resolved_headword'], *renderings]))
            out.append(f'<span class="index-entry" data-headword="{esc(search)}" '
                       f'id="{esc(entry["id"])}">{text}</span>')
        else:
            out.append(f'<span class="index-line">{text}</span>')

    def el_p(self, el, out):
        if self.section_type != 'index' or not self.entries:
            return super().el_p(el, out)
        # Preserve paragraph parts and every printed line; TEI remains the text
        # source, while the auxiliary payload supplies reference resolution.
        part = el.get('part', '')
        out.append(f'<p class="index-paragraph part-{esc(part)}">')
        line = ET.Element(f'{TEI}p')
        line.text = el.text
        number = ''
        for child in el:
            if (child.tag == f'{TEI}lb' and number
                    and (self.index_page, number) in self.entries
                    and (self.index_page, child.get('n', '')) not in self.entries):
                line.append(copy.deepcopy(child))
                continue
            if child.tag in {f'{TEI}lb', f'{TEI}pb'}:
                if line.text or len(line):
                    self.index_line(line, number, out)
                line = ET.Element(f'{TEI}p')
                line.text = child.tail
                if child.tag == f'{TEI}pb':
                    self.el_pb(child, out)
                    number = ''
                else:
                    number = child.get('n', '')
                    marker = copy.deepcopy(child)
                    marker.tail = child.tail
                    line.text = None
                    line.insert(0, marker)
            else:
                line.append(copy.deepcopy(child))
        if line.text or len(line):
            self.index_line(line, number, out)
        out.append('</p>')

    def render_chapter(self, div, entry_pb=None):
        self.section_type = div.get('type', '')
        rendered = super().render_chapter(div, entry_pb)
        if self.section_type == 'index':
            if self.entries and len(self.seen_entries) != len(self.entries):
                raise ValueError('Index payload entries are missing from printed TEI lines')
            rendered['kind'] = 'index'
            rendered['html'] = '<div class="sachregister" lang="de">' + rendered['html'] + '</div>'
        elif self.section_type == 'errata':
            rendered['html'] = '<div class="errata">' + rendered['html'] + '</div>'
        return rendered
