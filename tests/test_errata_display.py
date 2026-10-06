from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from dioscorides_reader.render import ChapterRenderer, Report, TEI

ROOT = Path(__file__).resolve().parents[1]


class ErrataDisplayTest(unittest.TestCase):
    def render(self, inner_xml: str) -> str:
        renderer = ChapterRenderer({"key": "berendes1902", "facs": "berendes1902", "anchored_notes": False},
                                   ROOT / "x.xml", {}, Report())
        paragraph = ET.fromstring(f'<p xmlns="{TEI.strip("{}")}">{inner_xml}</p>')
        out: list[str] = []
        renderer.el_p(paragraph, out)
        return "".join(out)

    def test_errata_correction_keeps_print_and_names_the_author(self) -> None:
        html = self.render('<choice><sic>Geschmack</sic><corr source="#berendes-erratum-4">Geruch</corr></choice>')
        self.assertIn('class="sic sic-errata"', html)
        self.assertIn("author&#x27;s errata: Geruch", html.replace("&#39;", "&#x27;"))
        self.assertIn(">Geschmack<", html)

    def test_errata_addition_is_visible_and_marked(self) -> None:
        html = self.render('(Burseraceae),<choice><sic/><corr source="#berendes-erratum-5"> besonders von '
                           '<hi rend="italic">Commiphora abysiniaca</hi>,</corr></choice> einem')
        self.assertIn('class="sic-add"', html)
        self.assertIn("besonders von", html)
        self.assertIn("Commiphora abysiniaca", html)

    def test_plain_misprint_unchanged(self) -> None:
        html = self.render('<choice><sic>Mitel</sic><corr>Mittel</corr></choice>')
        self.assertIn('class="sic"', html)
        self.assertIn("recte: Mittel", html)


if __name__ == "__main__":
    unittest.main()
