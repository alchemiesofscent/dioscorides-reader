import xml.etree.ElementTree as ET

from dioscorides_reader.credits import extract


def header(content):
    return ET.fromstring(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0" '
        'xmlns:xi="http://www.w3.org/2001/XInclude"><teiHeader>'
        + content + '</teiHeader><text><body><p>ἀπὸ τῶν φύλλων</p></body></text></TEI>'
    )


def test_records_exact_responsibilities_methods_and_primary_source():
    result = extract(header('''<fileDesc><titleStmt>
      <title>De materia medica</title><author>Dioscurides</author>
      <editor role="editor-princeps">Max Wellmann</editor>
      <principal>Sean Coughlin</principal>
      <funder>Project <ref target="https://example.org/grant">funding</ref>.</funder>
      <respStmt><resp>Critical correction and editorial adjudication.</resp>
        <persName>Sean Coughlin</persName><note type="affiliation">Research institute</note></respStmt>
      <respStmt><resp>AI-assisted draft transcription; manually corrected</resp>
        <name>Recorded tools</name><affiliation>Project</affiliation></respStmt>
      <respStmt><resp>Earlier scaffold, subsequently corrected against print</resp>
        <orgName>Upstream corpus</orgName></respStmt>
      </titleStmt><sourceDesc><listBibl><biblStruct><monogr>
        <title>Printed source</title><editor>Max Wellmann</editor><imprint>
        <publisher>Weidmann</publisher><date>1906–1914</date></imprint>
        </monogr></biblStruct></listBibl><xi:include href="../listWit.xml"/>
        <xi:include href="../listBibl.xml"/></sourceDesc>
      <publicationStmt><authority>Research project</authority>
        <availability><licence target="https://example.org/licence">Project-created materials only.</licence></availability>
      </publicationStmt></fileDesc><encodingDesc>
        <projectDesc><p>The digital edition corrects the inherited source.</p>
          <p>AI-assisted work remains subject to editorial review.</p></projectDesc>
        <editorialDecl><correction><p>Printed readings govern corrections.</p></correction></editorialDecl>
      </encodingDesc>'''))
    sections = {section['title']: section['entries'] for section in result['sections']}
    responsibilities = [row['text'] for row in sections['Digital edition and responsibilities'] if row['label'] == 'Responsibility']
    assert responsibilities == [
        'Sean Coughlin — Critical correction and editorial adjudication. Affiliation: Research institute',
        'Recorded tools — AI-assisted draft transcription; manually corrected. Affiliation: Project',
        'Upstream corpus — Earlier scaffold, subsequently corrected against print',
    ]
    assert len(sections['Source edition']) == 1
    assert sections['Source edition'][0]['text'] == 'Printed source Max Wellmann Weidmann 1906–1914'
    assert [row['text'] for row in sections['Project and methods'] if row['label'] in {'Project description', 'Editorial methods'}] == [
        'The digital edition corrects the inherited source.',
        'AI-assisted work remains subject to editorial review.',
        'Printed readings govern corrections.',
    ]
    rights = sections['Publication and rights'][-1]
    assert rights['text'] == 'Project-created materials only.'
    assert rights['links'] == [{'text': 'Project-created materials only.', 'href': 'https://example.org/licence'}]


def test_partial_metadata_does_not_invent_people_methods_or_rights():
    assert extract(ET.fromstring('<TEI/>')) == {'sections': []}
    result = extract(header('<fileDesc><titleStmt><title>Διοϲκουρίδου</title></titleStmt></fileDesc>'))
    assert result == {'sections': [{'title': 'Digital edition and responsibilities', 'entries': [
        {'label': 'Title', 'text': 'Διοϲκουρίδου', 'links': []}
    ]}]}


def test_metadata_markup_is_plain_text_and_links_are_restricted():
    result = extract(header('''<fileDesc><titleStmt>
      <title>&lt;script&gt;alert(1)&lt;/script&gt;</title><funder>See
      <ref target="javascript:alert(1)">bad</ref><ref target="//example.org">relative</ref>
      <ref target="file:///tmp/private">local</ref><ref target="https://user:pass@example.org">credentials</ref>
      <ref target="https://example.org/unsafe&#10;path">whitespace</ref>
      <ref target="https://example.org/good">reference</ref></funder>
      </titleStmt></fileDesc>'''))
    assert result['sections'][0]['entries'][0]['text'] == '<script>alert(1)</script>'
    assert result['sections'][1]['entries'][0]['links'] == [{'text': 'reference', 'href': 'https://example.org/good'}]
