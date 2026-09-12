"""Small read-only TEI helpers; includes resolve only within the verified bundle."""
from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from .bundle import Bundle, XI

ACTIVE_BUNDLE: Bundle | None = None


def norm_space(value: str) -> str:
    return " ".join((value or "").split())


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def xml_id(element: ET.Element) -> str:
    return element.get("{http://www.w3.org/XML/1998/namespace}id") or element.get("xml:id") or element.get("id") or ""


def parse_tei(path: Path) -> ET.Element:
    if ACTIVE_BUNDLE is None:
        raise ValueError("TEI parsing requires a verified bundle")
    root = ET.parse(path).getroot()

    def expand(parent: ET.Element, source: Path) -> None:
        for index, child in enumerate(list(parent)):
            if child.tag == XI:
                target = ACTIVE_BUNDLE.include_path(source, child.get("href", ""))
                replacement = copy.deepcopy(parse_tei(target))
                replacement.tail = (replacement.tail or "") + (child.tail or "")
                parent.remove(child)
                parent.insert(index, replacement)
            else:
                expand(child, source)

    expand(root, path)
    return root
