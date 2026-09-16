"""Small, literal presentation of the source TEI's attribution and methods.

Read the unexpanded header: included witness/bibliography libraries are apparatus
dependencies, not the edition's source citation or a list of its contributors.
This module reports recorded metadata; it does not infer roles or licence scope.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

TEI = "{http://www.tei-c.org/ns/1.0}"


def text(node: ET.Element | None) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def links(node: ET.Element) -> list[dict]:
    result = []
    for child in node.iter():
        if child.tag not in {TEI + "ref", TEI + "licence"}:
            continue
        target = child.get("target", "")
        if not target or any(character.isspace() or ord(character) < 32 for character in target):
            continue
        try:
            parsed = urlsplit(target)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
                continue
        except ValueError:
            continue
        value = {"text": text(child) or target, "href": target}
        if value not in result:
            result.append(value)
    return result


def extract(root: ET.Element) -> dict:
    """Return optional plain-text sections, in a stable order, without raw HTML."""
    header = root.find(TEI + "teiHeader")
    if header is None:
        return {"sections": []}
    sections = []

    def section(title, entries):
        if entries:
            sections.append({"title": title, "entries": entries})

    def entry(label, node, value=None):
        value = text(node) if value is None else value
        if not value:
            return []
        return [{"label": label, "text": value, "links": links(node)}]

    source = header.find(f"{TEI}fileDesc/{TEI}sourceDesc")
    sources = []
    if source is not None:
        for child in source:
            records = list(child) if child.tag == TEI + "listBibl" else [child]
            for record in records:
                if record.tag in {TEI + "biblStruct", TEI + "bibl", TEI + "p"}:
                    # Add spaces between structured bibliographic fields even when
                    # their XML was serialized without indentation or whitespace.
                    value = " ".join(" ".join(record.itertext()).split())
                    sources.extend(entry("Source", record, value))
    section("Source edition", sources)

    title = header.find(f"{TEI}fileDesc/{TEI}titleStmt")
    attribution, project = [], []
    if title is not None:
        labels = {"title": "Title", "author": "Author", "editor": "Editor"}
        for child in title:
            name = child.tag.removeprefix(TEI)
            if name in labels:
                label = labels[name]
                if child.get("role"):
                    label += " (" + child.get("role") + ")"
                attribution.extend(entry(label, child))
            elif name == "respStmt":
                roles, names, affiliations, notes = [], [], [], []
                for part in child:
                    part_name = part.tag.removeprefix(TEI)
                    value = text(part)
                    if not value:
                        continue
                    if part_name == "resp":
                        roles.append(value)
                    elif part_name in {"name", "persName", "orgName"}:
                        names.append(value)
                    elif part_name == "affiliation" or (part_name == "note" and part.get("type") == "affiliation"):
                        affiliations.append(value)
                    elif part_name == "note":
                        notes.append(value)
                value = " — ".join(part for part in ("; ".join(names), "; ".join(roles)) if part)
                if affiliations:
                    separator = (" " if value[-1:] in ".!?;:" else ". ") if value else ""
                    value += separator + "Affiliation: " + "; ".join(affiliations)
                if notes:
                    separator = (" " if value[-1:] in ".!?;:" else ". ") if value else ""
                    value += separator + "; ".join(notes)
                attribution.extend(entry("Responsibility", child, value))
            elif name in {"principal", "funder", "sponsor"}:
                project.extend(entry({"principal": "Project lead", "funder": "Funding", "sponsor": "Sponsor"}[name], child))
    section("Digital edition and responsibilities", attribution)

    encoding = header.find(TEI + "encodingDesc")
    if encoding is not None:
        for name, label in (("projectDesc", "Project description"), ("editorialDecl", "Editorial methods")):
            for description in encoding.findall(TEI + name):
                paragraphs = list(description) or [description]
                for paragraph in paragraphs:
                    project.extend(entry(label, paragraph))
    section("Project and methods", project)

    publication = header.find(f"{TEI}fileDesc/{TEI}publicationStmt")
    published = []
    if publication is not None:
        labels = {"authority": "Authority", "publisher": "Publisher", "pubPlace": "Place", "date": "Date", "p": "Publication statement"}
        for child in publication:
            name = child.tag.removeprefix(TEI)
            if name in labels:
                published.extend(entry(labels[name], child))
            elif name == "availability":
                for statement in list(child) or [child]:
                    published.extend(entry("Recorded rights statement", statement))
    section("Publication and rights", published)
    return {"sections": sections}
