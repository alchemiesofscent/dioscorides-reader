"""An edition whose chapters hold the author's text and a commentary on it (Mattioli 1554)."""
from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from dioscorides_reader.render import (
    ChapterRenderer, Report, TEI, element_reading_text, resolve_facs, section_label,
)

NS = TEI.strip("{}")
CFG = {"key": "mattioli1554", "facs": "iiif-image", "anchored_notes": True,
       "label_source": "head", "lang": "lat", "text_and_commentary": True}
CHAPTER = f"""<div xmlns="{NS}" type="textpart" subtype="chapter" n="43" xml:id="mat-1.43">
  <head><figure><head><lb/>ELATINVM</head></figure><note type="lemma" place="margin"><foreign xml:lang="grc">Ἐλάτινον</foreign>.</note><lb/>ELATINVM. <num type="chapter" value="43">CAP. XLIII.</num></head>
  <div type="textpart" subtype="section" n="translation"><ab><lb/>FRACTA elate, <expan>tu<ex>n</ex>sa</expan> <gap reason="illegible"/></ab></div>
  <div type="textpart" subtype="section" n="commentary" rend="italic"><ab><lb/><note type="marginal" place="margin"><lb/>Elatini consideratio.</note>ELATINVM, quod ex <hi rend="roman">Dactylorum</hi> <unclear>inuolucris</unclear></ab></div>
</div>"""


class TextAndCommentaryTest(unittest.TestCase):
    def render(self) -> str:
        renderer = ChapterRenderer(CFG, Path("mattioli1554.xml"), {}, Report())
        return renderer.render_chapter(ET.fromstring(CHAPTER))["html"]

    def test_text_and_commentary_are_distinct_labelled_blocks(self) -> None:
        html = self.render()
        self.assertIn('<section class="dioscorides-text"><span class="block-label">Dioscorides</span>', html)
        self.assertIn('<section class="commentary author-commentary">'
                      '<span class="block-label">Commentarius</span>', html)
        self.assertLess(html.index("dioscorides-text"), html.index("author-commentary"))
        self.assertNotIn('data-n="translation"', html)

    def test_transcription_elements_have_handlers(self) -> None:
        html = self.render()
        self.assertIn('<span class="expan">tu<span class="ex">n</span>sa</span>', html)
        self.assertIn('class="gap"', html)
        self.assertIn('<span class="unclear" title="uncertain reading">inuolucris</span>', html)
        self.assertIn('<span class="note-marginal">', html)
        self.assertIn('<span class="note-lemma">', html)
        self.assertIn('❦ ELATINVM', html)
        self.assertNotIn("tei-unknown", html)

    def test_heading_label_skips_the_woodcut_caption(self) -> None:
        head = ET.fromstring(CHAPTER).find(f"{TEI}head")
        self.assertEqual(element_reading_text(head), "Ἐλάτινον. ELATINVM. CAP. XLIII.")

    def test_named_sections_take_their_conventional_labels(self) -> None:
        div = ET.fromstring(f'<div xmlns="{NS}" n="praef"><div n="translation"><ab><lb/>QVANQVAM</ab></div></div>')
        self.assertEqual(section_label(CFG, "1", "praef", div, {}, Report()), "Praefatio")
        self.assertEqual(section_label(CFG, "front", "privilegia", div, {}, Report()), "Privilegia")

    def test_iiif_image_requests_resolve_to_their_service(self) -> None:
        facs = "https://iiif.wellcomecollection.org/image/b33551200_0002_0117.jp2/full/max/0/default.jpg"
        self.assertEqual(resolve_facs(CFG, facs, Path("x.xml"), Report()), {
            "kind": "iiif", "direct": facs,
            "info": "https://iiif.wellcomecollection.org/image/b33551200_0002_0117.jp2/info.json"})
        report = Report()
        self.assertIsNone(resolve_facs(CFG, "https://example.org/page.png", Path("x.xml"), report))



class EnglishMattioliTest(unittest.TestCase):
    def test_english_stream_labels_its_blocks_in_english(self) -> None:
        cfg = {**CFG, "key": "mattioli1554-eng", "lang": "eng"}
        html = ChapterRenderer(cfg, Path("mattioli1554-eng.xml"), {}, Report()).render_chapter(
            ET.fromstring(CHAPTER))["html"]
        self.assertIn('<span class="block-label">Commentary</span>', html)
        div = ET.fromstring(f'<div xmlns="{NS}" n="praef"/>')
        self.assertEqual(section_label(cfg, "1", "praef", div, {}, Report()), "Preface")
        self.assertEqual(section_label(cfg, "front", "typographus", div, {}, Report()), "The printer to the reader")


if __name__ == "__main__":
    unittest.main()
