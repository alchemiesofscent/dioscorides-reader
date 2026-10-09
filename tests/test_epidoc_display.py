from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from dioscorides_reader.render import ChapterRenderer, Report, TEI


@pytest.fixture(params=["wellmann1906", "sprengel1829-grc", "berendes1902"])
def renderer(request):
    report = Report()
    return ChapterRenderer({"key": request.param, "anchored_notes": False},
                           Path("synthetic.xml"), {}, report), report


def render(renderer, xml):
    element = ET.fromstring(f'<p xmlns="{TEI.strip("{}")}">{xml}</p>')
    out = []
    renderer.render_element(element, out)
    return "".join(out)


def test_editorial_brackets_and_nested_content(renderer):
    chapter, report = renderer
    html = render(chapter, '<supplied reason="omitted">added <hi rend="italic">letters</hi>'
                  '<lb n="10"/><app xml:id="addition"><lem>lemma</lem>'
                  '<rdg wit="#A">variant</rdg></app></supplied> '
                  '<surplus>deleted <hi rend="bold">word</hi></surplus>')
    assert '<span class="tei-supplied" title="supplied by the editor">⟨added <em>letters</em>' in html
    assert 'class="lb"' in html
    assert 'data-app="app-1">lemma</span>⟩</span>' in html
    assert "variant" in str(chapter.apps)
    assert '<span class="tei-surplus" title="deleted by the editor">[deleted <strong>word</strong>]</span>' in html
    assert not [item for item in report.items if item[1] == "unmapped element"]


def test_chapter_numeral_stays_inline(renderer):
    chapter, report = renderer
    html = render(chapter, '<lb n="10"/><num type="chapter" value="4">4</num> text'
                  '<num type="section">2</num>')
    assert '<span class="tei-num tei-num-chapter">4</span> text' in html
    assert '<span class="tei-num tei-num-section">2</span>' in html
    assert not report.items


def test_only_marginal_labels_get_margin_class(renderer):
    chapter, report = renderer
    html = render(chapter, '<lb n="15"/><label type="section" place="margin">2</label>'
                  '<label>Ordinary <hi rend="italic">label</hi></label>')
    assert '<span class="tei-label margin-label" data-place="margin">2</span>' in html
    assert '<span class="tei-label">Ordinary <em>label</em></span>' in html
    assert not report.items
