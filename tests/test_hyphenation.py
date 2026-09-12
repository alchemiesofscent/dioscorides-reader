from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from dioscorides_reader.render import (
    ChapterRenderer,
    Report,
    TEI,
    element_reading_text,
    normalize_reading_label,
)


ROOT = Path(__file__).resolve().parents[1]


class ViewerHyphenationTest(unittest.TestCase):
    def renderer(self) -> ChapterRenderer:
        return ChapterRenderer(
            {
                "key": "sprengel1829-lat",
                "facs": "sprengel1829",
                "anchored_notes": False,
            },
            ROOT / "editions" / "sprengel" / "tei" / "sprengel1829_epidoc.xml",
            {},
            Report(),
        )

    def render_paragraph(self, inner_xml: str) -> str:
        paragraph = ET.fromstring(f'<p xmlns="{TEI.strip("{}")}">{inner_xml}</p>')
        output: list[str] = []
        self.renderer().el_p(paragraph, output)
        return "".join(output)

    def test_plain_midword_hyphen_is_hidden_and_fragments_join(self) -> None:
        html = self.render_paragraph('ἀνε-<lb n="8" break="no"/>μώνῃ')
        self.assertIn('ἀνε<span class="eol-hyphen">-</span>', html)
        self.assertIn('<span class="lb nobreak" data-n="8"></span>μώνῃ', html)
        self.assertNotIn('</span> μώνῃ', html)

    def test_italic_midword_hyphen_is_wrapped_inside_emphasis(self) -> None:
        html = self.render_paragraph(
            '<hi rend="italic">De Artemisia tenuifo-</hi>'
            '<lb n="13" break="no"/><hi rend="italic">lia.</hi>'
        )
        self.assertIn(
            '<em>De Artemisia tenuifo<span class="eol-hyphen">-</span></em>',
            html,
        )
        self.assertIn('<span class="lb nobreak" data-n="13"></span><em>lia.</em>', html)

    def test_ordinary_hyphen_and_break_remain_reading_text(self) -> None:
        html = self.render_paragraph('well-known<lb n="2"/>next')
        self.assertIn('well-known<span class="lb" data-n="2"></span> next', html)
        self.assertNotIn('eol-hyphen', html)

    def test_foreign_fragments_join_across_explicit_no_break(self) -> None:
        inner_xml = (
            '<foreign xml:lang="grc">μεταπο</foreign>'
            '<lb n="2" break="no"/>'
            '<foreign xml:lang="grc">ροποιούσῃ</foreign>'
        )
        html = self.render_paragraph(inner_xml)
        paragraph = ET.fromstring(f'<p xmlns="{TEI.strip("{}")}">{inner_xml}</p>')

        self.assertIn(
            '<span class="foreign grc" lang="grc">μεταπο</span>'
            '<span class="lb nobreak" data-n="2"></span>'
            '<span class="foreign grc" lang="grc">ροποιούσῃ</span>',
            html,
        )
        self.assertEqual(element_reading_text(paragraph), "μεταποροποιούσῃ")

    def test_no_break_discards_pretty_printed_leading_tail_whitespace(self) -> None:
        inner_xml = (
            '<foreign xml:lang="grc">μεταπο</foreign>'
            '<lb n="2" break="no"/>\n    '
            '<foreign xml:lang="grc">ροποιούσῃ</foreign>'
        )
        html = self.render_paragraph(inner_xml)
        paragraph = ET.fromstring(f'<p xmlns="{TEI.strip("{}")}">{inner_xml}</p>')

        self.assertNotIn('</span> <span class="foreign grc"', html)
        self.assertEqual(element_reading_text(paragraph), "μεταποροποιούσῃ")

    def test_ordinary_break_preserves_space_between_foreign_fragments(self) -> None:
        inner_xml = (
            '<foreign xml:lang="grc">ἐνι</foreign>'
            '<lb n="2"/>\n    '
            '<foreign xml:lang="grc">στρογγύλον</foreign>'
        )
        html = self.render_paragraph(inner_xml)
        paragraph = ET.fromstring(f'<p xmlns="{TEI.strip("{}")}">{inner_xml}</p>')

        self.assertRegex(
            html,
            r'<span class="lb" data-n="2"></span>\s+'
            r'<span class="foreign grc" lang="grc">στρογγύλον</span>',
        )
        self.assertEqual(element_reading_text(paragraph), "ἐνι στρογγύλον")

    def test_cross_page_hyphen_ignores_furniture_and_paragraph_boundaries(self) -> None:
        chapter = ET.fromstring(
            f'<div xmlns="{TEI.strip("{}")}" n="3.121">'
            '<p part="I">κε-</p>'
            '<pb n="467"/>'
            '<fw type="header">ΠΕΡΙ ΥΛΗΣ</fw>'
            '<fw type="pageNum">467</fw>'
            '<p part="F"><lb n="1" break="no"/>φαλὰς</p>'
            '</div>'
        )
        html = self.renderer().render_chapter(chapter)["html"]
        self.assertIn('κε<span class="eol-hyphen">-</span></p>', html)
        self.assertIn('<span class="fw fw-header">ΠΕΡΙ ΥΛΗΣ</span>', html)
        self.assertIn('<span class="lb nobreak" data-n="1"></span>φαλὰς', html)

    def test_cross_page_no_break_hides_only_its_marker_in_reading_mode(self) -> None:
        chapter = ET.fromstring(
            f'<div xmlns="{TEI.strip("{}")}" n="1.praef">'
            '<p>sae-<pb n="341"/><fw type="running">IN DIOSCORIDIS</fw>'
            '<lb n="1" break="no"/>pius in opere</p>'
            '</div>'
        )
        html = self.renderer().render_chapter(chapter)["html"]
        css = (ROOT / "web" / "reader.css").read_text(encoding="utf-8")

        self.assertIn(
            'sae<span class="eol-hyphen">-</span>'
            '<a class="pb nobreak-bridge"',
            html,
        )
        self.assertIn(
            '</a><span class="fw fw-running">IN DIOSCORIDIS</span>'
            '<span class="lb nobreak" data-n="1"></span>pius',
            html,
        )
        self.assertEqual(element_reading_text(chapter.find(f"{TEI}p")), "saepius in opere")
        self.assertIn("a.pb.nobreak-bridge { display: none; }", css)
        self.assertIn("body.show-fw a.pb.nobreak-bridge", css)
        self.assertIn("body.show-lineation a.pb.nobreak-bridge", css)

    def test_page_marker_without_following_no_break_stays_visible(self) -> None:
        chapter = ET.fromstring(
            f'<div xmlns="{TEI.strip("{}")}" n="1.praef">'
            '<p>sae<pb n="341"/><fw type="running">IN DIOSCORIDIS</fw>'
            '<lb n="1"/>pius</p>'
            '</div>'
        )
        html = self.renderer().render_chapter(chapter)["html"]

        self.assertIn('<a class="pb" href="#"', html)
        self.assertNotIn("nobreak-bridge", html)

    def test_cross_page_foreign_fragments_use_the_same_explicit_bridge(self) -> None:
        chapter = ET.fromstring(
            f'<div xmlns="{TEI.strip("{}")}" n="3.95">'
            '<p><foreign xml:lang="grc">λύσ</foreign>-<pb n="536"/>'
            '<fw type="running">COMMENTARIUS</fw><lb n="1" break="no"/>'
            '<foreign xml:lang="grc">σαν</foreign> '
            '<foreign xml:lang="grc">κυνὸς</foreign></p>'
            '</div>'
        )
        paragraph = chapter.find(f"{TEI}p")
        html = self.renderer().render_chapter(chapter)["html"]

        self.assertIn(
            '<span class="foreign grc" lang="grc">λύσ</span>'
            '<span class="eol-hyphen">-</span>'
            '<a class="pb nobreak-bridge"',
            html,
        )
        self.assertEqual(element_reading_text(paragraph), "λύσσαν κυνὸς")

    def test_cross_page_note_hyphen_uses_its_own_text_layer(self) -> None:
        note = ET.fromstring(
            f'<note xmlns="{TEI.strip("{}")}" type="footnote" n="67">'
            'Le-<milestone unit="page-continuation" n="0056"/>'
            '<lb n="1" break="no"/>pidio</note>'
        )
        _, html = self.renderer()._footnote(note)
        self.assertIn('Le<span class="eol-hyphen">-</span>', html)
        self.assertIn('<span class="lb nobreak" data-n="1"></span>pidio', html)

    def test_navigation_labels_drop_only_printed_split_hyphens(self) -> None:
        self.assertEqual(
            normalize_reading_label("De Artemisia tenuifo- lia"),
            "De Artemisia tenuifolia",
        )
        self.assertEqual(normalize_reading_label("subrotundo-oblonga"), "subrotundo-oblonga")
        head = ET.fromstring(
            f'<head xmlns="{TEI.strip("{}")}"><hi rend="italic">tenuifo-</hi>'
            '<lb break="no"/><hi rend="italic">lia</hi></head>'
        )
        self.assertEqual(element_reading_text(head), "tenuifolia")


if __name__ == "__main__":
    unittest.main()
