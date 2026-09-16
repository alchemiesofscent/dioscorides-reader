#!/usr/bin/env python3
"""Preserved edition-aware TEI rendering for verified corpus export bundles.

The compiler supplies immutable source paths and display output locations.
HTML and JSON here are derived presentation, never maintained scholarly text.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
import xml.etree.ElementTree as ET

from .xml_utils import local_name, norm_space, parse_tei, xml_id
from .credits import extract as extract_credits

# Configured by the bundle compiler; never points to another checkout.
ROOT = Path(".")
FACSIMILES = {}

TEI = "{http://www.tei-c.org/ns/1.0}"
XML = "{http://www.w3.org/XML/1998/namespace}"
OUT_DIR = ROOT / "reader" / "data"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


CHAPTER_TABLE = ROOT / "editions" / "sprengel" / "sprengel_chapter_table.tsv"

# ---------------------------------------------------------------------------
# Existing display adapters preserve route and rendering behavior. The compiler
# selects streams and replaces historical TEI paths from the verified manifest.
# Sprengel 1829 exposes Greek and Latin streams from one scholarly edition.
# ---------------------------------------------------------------------------
EDITIONS = [
    {
        "key": "sprengel1829-grc",
        "label": "Sprengel 1829 (Greek)",
        "lang": "grc",
        "tei_path": "editions/sprengel/tei/sprengel1829_epidoc.xml",
        "stream": {"type": "edition", "lang": "grc"},
        "facs": "sprengel1829",
        "label_source": "table:grc",
        "anchored_notes": "auto",
    },
    {
        "key": "sprengel1829-lat",
        "label": "Sprengel 1829 (Latin)",
        "lang": "lat",
        "tei_path": "editions/sprengel/tei/sprengel1829_epidoc.xml",
        "stream": {"type": "translation", "lang": "lat"},
        "facs": "sprengel1829",
        "label_source": "table:la",
        "anchored_notes": True,
    },
    {
        "key": "sprengel1830-comm",
        "label": "Sprengel 1830 Commentarius (Latin)",
        "lang": "lat",
        "tei_path": "editions/sprengel/tei/sprengel1830_comm_epidoc.xml",
        "stream": {"type": "commentary"},
        "facs": "archive-download",
        "label_source": "table:la",
        "anchored_notes": True,
    },
    {
        "key": "sprengel1830-comm-eng",
        "label": "Sprengel 1830 Commentarius (English draft)",
        "lang": "eng",
        "tei_path": "editions/sprengel/tei/sprengel1830_comm_eng_epidoc.xml",
        "stream": {"type": "translation", "lang": "eng"},
        "facs": "none",
        "label_source": "head",
        "anchored_notes": True,
    },
    {
        "key": "berendes1902",
        "label": "Berendes 1902 (German)",
        "lang": "deu",
        "tei_path": "editions/berendes/tei/berendes1902_epidoc.xml",
        "stream": {"type": "translation"},
        "facs": "heidelberg",
        "label_source": "table:grc",
        "anchored_notes": True,
        # Keep note bodies where the TEI places them.  They are also retained
        # in the book-level side table so inline refs can open popovers.
        "footnote_display": "tei-order",
    },
    {
        "key": "beck2020",
        "label": "Beck 2020 (English)",
        "lang": "eng",
        "tei_path": "editions/beck/tei/beck2020_fresh_diplomatic_epidoc.xml",
        "stream": {"type": "translation"},
        "facs": "local",
        "label_source": "head",
        "anchored_notes": True,
    },
    {
        "key": "wellmann1906",
        "label": "Wellmann 1906 (Greek, critical)",
        "lang": "grc",
        "tei_path": "Wellmann_Dioscorides/tei/wellmann1906.xml",
        "stream": {"type": "edition"},
        "facs": "bbaw",
        "label_source": "table:grc",
        "anchored_notes": True,
    },
]

BBAW_VOLUMES = {
    "Vol1_Lib_I_II": "Ped_Diosc_De_mat_med_Wellmann_Lib_I_II",
    "Vol2_Lib_III_IV": "Ped_Diosc_De_mat_med_Wellmann_Lib_III_IV",
    "Vol3_Lib_V": "Ped_Diosc_De_mat_med_Wellmann_Lib_V",
}

HYPHENS = ("-", "‐", "⸗")


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def squash(value: str) -> str:
    return re.sub(r"\s+", " ", value or "")


def normalize_reading_label(value: str) -> str:
    """Remove a printed line-end split from a compact navigation label."""
    label = norm_space(value)
    hyphens = "".join(re.escape(char) for char in HYPHENS)
    return re.sub(rf"(?<=\w)[{hyphens}]\s+(?=\w)", "", label)


def element_reading_text(el: ET.Element) -> str:
    """Extract reading text while respecting TEI ``lb/@break`` semantics."""
    parts: list[str] = []
    trailing_hyphen = re.compile(
        rf"[{''.join(re.escape(char) for char in HYPHENS)}]\s*$"
    )

    def walk(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            if child.tag == f"{TEI}lb":
                if child.get("break") == "no":
                    joined = "".join(parts)
                    parts[:] = [trailing_hyphen.sub("", joined)]
                else:
                    parts.append(" ")
            elif child.tag == f"{TEI}fw":
                # Running heads and printed page numbers are not reading text.
                # Their tails are still handled below so ordinary word spacing
                # survives when no explicit no-break milestone follows.
                pass
            else:
                walk(child)
            if child.tail:
                tail = child.tail
                if child.tag == f"{TEI}lb" and child.get("break") == "no":
                    tail = tail.lstrip()
                if tail:
                    parts.append(tail)

    walk(el)
    return norm_space("".join(parts))


def now_utc() -> str:
    return "content-addressed"


class Report:
    """Collects everything the build could not decide deterministically."""

    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def add(self, edition: str, category: str, detail: str) -> None:
        self.items.append((edition, category, detail))

    def write(self, path: Path) -> None:
        lines = [
            "> **Doc:** Reader build QA report · **Version:** (generated) · "
            f"**Updated:** {now_utc()} · **Status:** generated",
            "> **Context:** Emitted by `dioscorides_reader`. Items the "
            "build could not decide deterministically. Regenerated on every build — "
            "do not edit by hand.",
            "",
            "# Reader build report",
            "",
        ]
        if not self.items:
            lines.append("No undecidable items in this build.")
        by_cat: dict[str, list[tuple[str, str]]] = {}
        for edition, category, detail in self.items:
            by_cat.setdefault(category, []).append((edition, detail))
        for category in sorted(by_cat):
            lines.append(f"## {category} ({len(by_cat[category])})")
            lines.append("")
            for edition, detail in by_cat[category]:
                lines.append(f"- `{edition}`: {detail}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Facsimile resolution (no network at build time; endpoints documented in
# reader/TODO.md and verified out-of-band).
# ---------------------------------------------------------------------------

def iiif3_archive(path_after_download: str) -> dict:
    enc = quote(path_after_download, safe="")
    base = f"https://iiif.archive.org/image/iiif/3/{enc}"
    return {"kind": "iiif", "info": f"{base}/info.json",
            "direct": f"{base}/full/max/0/default.jpg"}


def resolve_local_facs(facs: str, tei_path: Path, report: Report, edition_key: str) -> dict | None:
    """Resolve one repository-local facsimile without allowing path escape."""
    record = FACSIMILES.get((tei_path.resolve().as_posix(), facs), {})
    url = record.get("url")
    if url and url.startswith(("https://", "http://", "facsimiles/")):
        return {"kind": "image", "url": url}
    report.add(edition_key, "facsimile unavailable", facs)
    return None


def resolve_facs(cfg: dict, facs: str, tei_path: Path, report: Report) -> dict | None:
    mode = cfg["facs"]
    if mode == "none":
        return None
    if not facs:
        report.add(cfg["key"], "pb without @facs", "page break missing @facs")
        return None
    if mode == "sprengel1829":
        parsed = urlparse(facs)
        if parsed.netloc == "archive.org" and parsed.path.startswith("/download/"):
            return iiif3_archive(unquote(parsed.path[len("/download/"):]))
        m = re.search(r"page-(\d+)\.png$", facs)
        if not m:
            report.add(cfg["key"], "unrecognized facs", facs)
            return None
        leaf = m.group(1).zfill(4)
        return iiif3_archive(
            f"b23982500_0001/b23982500_0001_jp2.zip/b23982500_0001_jp2/b23982500_0001_{leaf}.jp2"
        )
    if mode == "archive-download":
        parsed = urlparse(facs)
        if not parsed.scheme and not parsed.netloc:
            return resolve_local_facs(facs, tei_path, report, cfg["key"])
        if parsed.netloc != "archive.org" or not parsed.path.startswith("/download/"):
            report.add(cfg["key"], "unrecognized facs", facs)
            return None
        path = unquote(parsed.path[len("/download/"):])
        return iiif3_archive(path)
    if mode == "heidelberg":
        basename = unquote(urlparse(facs).path).rsplit("/", 1)[-1]
        ident = quote(f"berendes1902:{basename}", safe="")
        base = f"https://digi.ub.uni-heidelberg.de/iiif/2/{ident}"
        return {"kind": "iiif", "info": f"{base}/info.json", "direct": facs}
    if mode == "bbaw":
        m = re.search(r"(Vol\d_Lib_[IV_]+)/png/Vol\d_p(\d+)\.png$", facs)
        if not m or m.group(1) not in BBAW_VOLUMES:
            report.add(cfg["key"], "unrecognized facs", facs)
            return None
        fn = f"/silo10/cmg/{BBAW_VOLUMES[m.group(1)]}/"
        pn = int(m.group(2))
        return {"kind": "image",
                "url": f"https://digilib.bbaw.de/digilib/Scaler?fn={fn}&pn={pn}&dw=1800"}
    if mode == "local":
        return resolve_local_facs(facs, tei_path, report, cfg["key"])
    report.add(cfg["key"], "unknown facs mode", mode)
    return None


# ---------------------------------------------------------------------------
# TEI -> HTML
# ---------------------------------------------------------------------------

class ChapterRenderer:
    """Renders one chapter div to HTML, accumulating book-level side tables
    (lifted footnotes, apparatus entries) and the chapter's page list."""

    def __init__(self, cfg: dict, tei_path: Path, witnesses: dict[str, str],
                 report: Report,
                 stand_off_apps: dict[str, list[ET.Element]] | None = None) -> None:
        self.cfg = cfg
        self.tei_path = tei_path
        self.witnesses = witnesses
        self.report = report
        self.notes: dict[str, str] = {}
        self.apps: dict[str, str] = {}
        self.app_counter = 0
        self.stand_off_apps = stand_off_apps or {}
        self._page_records: dict[ET.Element, dict] = {}
        # per-chapter state
        self.pages: list[dict] = []
        self.note_ids: list[str] = []
        self.ref_note_ids: list[str] = []
        self._track_running_text = True
        self._last_running_text: tuple[list[str], int] | None = None
        self._pending_page_break: (
            tuple[list[str], int, tuple[list[str], int] | None] | None
        ) = None

    # -- helpers ------------------------------------------------------------

    def _wit_html(self, tokens: str) -> str:
        parts = []
        for token in (tokens or "").split():
            ident = token.lstrip("#")
            desc = self.witnesses.get(ident)
            if desc:
                parts.append(f'<abbr title="{esc(desc)}">{esc(ident)}</abbr>')
            else:
                parts.append(esc(ident))
                self.report.add(self.cfg["key"], "unresolved siglum", token)
        return " ".join(parts)

    def _rstrip_out(self, out: list[str]) -> None:
        while out and not out[-1]:
            out.pop()
        if out:
            out[-1] = out[-1].rstrip()
            if not out[-1]:
                self._rstrip_out(out)

    def _append_text(self, out: list[str], value: str) -> None:
        """Append escaped TEI text and remember its position in the reading text.

        The remembered position deliberately survives intervening page furniture.
        A ``break="no"`` line can therefore mark the printed hyphen at the end of
        the preceding page even when ``pb``, ``fw``, and paragraph tags separate
        the two word fragments in the generated HTML.
        """
        rendered = esc(squash(value))
        out.append(rendered)
        if self._track_running_text and rendered.strip():
            self._last_running_text = (out, len(out) - 1)
            # Any real reading text after a page marker means that marker is
            # not the bridge to a later ``lb[@break='no']``.
            if (
                self._pending_page_break is not None
                and self._pending_page_break[0] is out
            ):
                self._pending_page_break = None

    def _mark_no_break_page_bridge(self, out: list[str]) -> bool:
        """Mark a ``pb`` crossed by the current explicit no-break milestone.

        Page furniture is rendered without changing ``_last_running_text``.
        Consequently the saved positions prove that no intervening reading
        text occurred; no lexical join is guessed here.  Whitespace emitted
        around the hidden furniture is removed so the two word fragments are
        adjacent in default reading mode.
        """
        pending = self._pending_page_break
        current = self._last_running_text
        self._pending_page_break = None
        if pending is None or current is None:
            return False
        pending_out, page_index, preceding = pending
        if (
            pending_out is not out
            or preceding is None
            or preceding[0] is not out
            or current[0] is not out
            or preceding[1] != current[1]
        ):
            return False
        marker = out[page_index]
        if 'class="pb"' not in marker:
            return False
        out[page_index] = marker.strip().replace(
            'class="pb"', 'class="pb nobreak-bridge"', 1
        )
        for index in range(current[1] + 1, len(out)):
            if index != page_index and not out[index].strip():
                out[index] = ""
        return True

    def _render_children_untracked(self, el: ET.Element, out: list[str]) -> None:
        """Render non-reading material without displacing the last text token."""
        previous_tracking = self._track_running_text
        previous_text = self._last_running_text
        self._track_running_text = False
        try:
            self.render_children(el, out)
        finally:
            self._track_running_text = previous_tracking
            self._last_running_text = previous_text

    def _render_children_isolated(self, el: ET.Element, out: list[str]) -> None:
        """Render a separate reading-text layer, then restore the outer layer."""
        previous_tracking = self._track_running_text
        previous_text = self._last_running_text
        self._track_running_text = True
        self._last_running_text = None
        try:
            self.render_children(el, out)
        finally:
            self._track_running_text = previous_tracking
            self._last_running_text = previous_text

    def _mark_token_hyphen(self, out: list[str], index: int) -> bool:
        if 'class="eol-hyphen"' in out[index]:
            return False
        trailing_hyphen = re.compile(
            rf"([{''.join(re.escape(value) for value in HYPHENS)}])"
            r"((?:</[^>]+>\s*)*)$"
        )
        value = out[index]
        match = trailing_hyphen.search(value)
        if not match:
            return False
        out[index] = (
            value[:match.start()]
            + f'<span class="eol-hyphen">{match.group(1)}</span>'
            + match.group(2)
        )
        return True

    def _mark_trailing_line_hyphen(self, out: list[str]) -> bool:
        """Wrap the last visible hyphen, looking through inline closing tags.

        A printed split can end inside ``hi`` (for example italic
        ``tenuifo-``), so the immediately preceding HTML token may be
        ``</em>`` rather than the text token itself.
        """
        closing_tag = re.compile(r"^</[^>]+>$")
        for index in range(len(out) - 1, -1, -1):
            value = out[index]
            if not value:
                continue
            if self._mark_token_hyphen(out, index):
                return True
            if closing_tag.fullmatch(value.strip()):
                continue
            break
        if self._last_running_text is not None:
            text_out, index = self._last_running_text
            if text_out is out and 0 <= index < len(out):
                return self._mark_token_hyphen(out, index)
        return False

    def _page_record(self, el: ET.Element) -> dict:
        if el not in self._page_records:
            self._page_records[el] = {
                "n": el.get("n", ""),
                "facs": resolve_facs(
                    self.cfg, el.get("facs", ""), self.tei_path, self.report
                ),
            }
        return dict(self._page_records[el])

    # -- element dispatch ---------------------------------------------------

    def render_children(self, el: ET.Element, out: list[str]) -> None:
        if el.text:
            self._append_text(out, el.text)
        children = list(el)
        i = 0
        while i < len(children):
            child = children[i]
            if (
                self.cfg.get("footnote_display") == "tei-order"
                and local_name(child.tag) == "note"
                and child.get("type") == "footnote"
            ):
                run: list[ET.Element] = []
                while i < len(children):
                    candidate = children[i]
                    if not (
                        local_name(candidate.tag) == "note"
                        and candidate.get("type") == "footnote"
                    ):
                        break
                    run.append(candidate)
                    i += 1
                out.append('<section class="endnotes tei-order"><ol>')
                for note in run:
                    key, body = self._footnote(note)
                    out.append(f'<li id="en-{esc(key)}">{body}</li>')
                out.append("</ol></section>")
                for note in run:
                    if note.tail:
                        self._append_text(out, note.tail)
                continue
            self.render_element(child, out)
            if child.tail:
                tail = child.tail
                if local_name(child.tag) == "lb" and child.get("break") == "no":
                    tail = tail.lstrip()
                if tail:
                    self._append_text(out, tail)
            i += 1

    def render_element(self, el: ET.Element, out: list[str]) -> None:
        name = local_name(el.tag)
        handler = getattr(self, f"el_{name}", None)
        if handler is not None:
            handler(el, out)
            return
        tag_info = name + "".join(f"[@{k}={v}]" for k, v in el.attrib.items())
        self.report.add(self.cfg["key"], "unmapped element", tag_info)
        out.append(f'<span class="tei-unknown" data-tag="{esc(name)}">')
        self.render_children(el, out)
        out.append("</span>")

    def el_div(self, el: ET.Element, out: list[str]) -> None:
        if el.get("type") == "commentary":
            out.append('<section class="commentary">')
            self.render_children(el, out)
            out.append("</section>")
        elif el.get("subtype") == "section":
            n = el.get("n", "")
            out.append(f'<section class="section" data-n="{esc(n)}">')
            self.render_children(el, out)
            out.append("</section>")
        else:
            out.append('<div class="tei-div">')
            self.render_children(el, out)
            out.append("</div>")

    def el_p(self, el: ET.Element, out: list[str]) -> None:
        cls = "commentary" if el.get("rend") == "commentary" else ""
        out.append(f'<p class="{cls}">' if cls else "<p>")
        self.render_children(el, out)
        out.append("</p>")

    def el_ab(self, el: ET.Element, out: list[str]) -> None:
        ab_type = el.get("subtype") or el.get("type") or "ab"
        out.append(f'<div class="tei-ab tei-ab-{esc(ab_type)}">')
        self.render_children(el, out)
        out.append("</div>")

    def el_head(self, el: ET.Element, out: list[str]) -> None:
        out.append('<h3 class="chapter-head">')
        self.render_children(el, out)
        out.append("</h3>")

    def el_seg(self, el: ET.Element, out: list[str]) -> None:
        seg_type = el.get("type", "seg")
        out.append(f'<span class="seg-{esc(seg_type)}">')
        self.render_children(el, out)
        out.append("</span>")

    def el_foreign(self, el: ET.Element, out: list[str]) -> None:
        lang = el.get(f"{XML}lang", "")
        cls = "foreign grc" if lang == "grc" else "foreign"
        out.append(f'<span class="{cls}" lang="{esc(lang)}">')
        self.render_children(el, out)
        out.append("</span>")

    def el_del(self, el: ET.Element, out: list[str]) -> None:
        if el.get("rend") == "brackets":
            out.append('<span class="tei-del-brackets">[')
            self.render_children(el, out)
            out.append("]</span>")
            return
        out.append("<del>")
        self.render_children(el, out)
        out.append("</del>")

    def el_hi(self, el: ET.Element, out: list[str]) -> None:
        rend = el.get("rend", "")
        tag = {"italic": "em", "bold": "strong"}.get(rend)
        out.append(f"<{tag}>" if tag else f'<span class="hi" data-rend="{esc(rend)}">')
        self.render_children(el, out)
        out.append(f"</{tag}>" if tag else "</span>")

    def el_label(self, el: ET.Element, out: list[str]) -> None:
        out.append('<span class="tei-label">')
        self.render_children(el, out)
        out.append("</span>")

    def el_num(self, el: ET.Element, out: list[str]) -> None:
        num_type = el.get("type", "num")
        out.append(f'<span class="tei-num tei-num-{esc(num_type)}">')
        self.render_children(el, out)
        out.append("</span>")

    def el_lb(self, el: ET.Element, out: list[str]) -> None:
        n = el.get("n", "")
        broken = el.get("break") == "no"
        if broken:
            self._mark_no_break_page_bridge(out)
        else:
            self._pending_page_break = None
        self._rstrip_out(out)
        if broken:
            self._mark_trailing_line_hyphen(out)
        self._last_running_text = None
        show = ""
        try:
            if n and int(n) % 5 == 0:
                show = ' data-show="1"'
        except ValueError:
            pass
        cls = "lb nobreak" if broken else "lb"
        out.append(f'<span class="{cls}" data-n="{esc(n)}"{show}></span>')
        if not broken:
            out.append(" ")

    def el_pb(self, el: ET.Element, out: list[str]) -> None:
        idx = len(self.pages)
        page = self._page_record(el)
        self.pages.append(page)
        marker_index = len(out)
        out.append(
            f' <a class="pb" href="#" data-page="{idx}" '
            f'title="printed page {esc(page["n"])}">p.&nbsp;{esc(page["n"])}</a> '
        )
        self._pending_page_break = (
            out,
            marker_index,
            self._last_running_text,
        )

    def el_fw(self, el: ET.Element, out: list[str]) -> None:
        fw_type = el.get("type", "")
        out.append(f'<span class="fw fw-{esc(fw_type)}">')
        self._render_children_untracked(el, out)
        out.append("</span>")

    def el_ref(self, el: ET.Element, out: list[str]) -> None:
        if el.get("type") == "footnote-ref":
            target = (el.get("target") or "").lstrip("#")
            if target:
                self.ref_note_ids.append(target)
            rid = xml_id(el)
            text = norm_space("".join(el.itertext()))
            out.append(
                f'<a class="fnref" href="#" id="{esc(rid)}" data-note="{esc(target)}">'
                f"<sup>{esc(text)}</sup></a>"
            )
        else:
            out.append('<span class="tei-ref">')
            self.render_children(el, out)
            out.append("</span>")

    def el_note(self, el: ET.Element, out: list[str]) -> None:
        note_type = el.get("type", "")
        nid = xml_id(el)
        if note_type == "footnote":
            key, body = self._footnote(el)
            if not self.cfg["anchored_notes"]:
                out.append(f'<span class="note-block" id="{esc(nid)}">{body}</span>')
        elif note_type == "siglorum":
            out.append(f'<div class="siglorum" id="{esc(nid)}">')
            self.render_children(el, out)
            out.append("</div>")
        else:
            out.append('<span class="note-inline">')
            self.render_children(el, out)
            out.append("</span>")

    def _footnote(self, el: ET.Element) -> tuple[str, str]:
        """Register one footnote and return its side-table key and rendered body."""
        inner: list[str] = []
        self._render_children_isolated(el, inner)
        n = el.get("n", "")
        body = f'<span class="note-n">{esc(n)}</span> ' if n else ""
        body += "".join(inner).strip()
        nid = xml_id(el)
        key = nid or f"note-{self.cfg['key']}-{len(self.notes)}"
        if self.cfg["anchored_notes"]:
            if not nid:
                self.report.add(
                    self.cfg["key"],
                    "footnote without xml:id",
                    norm_space("".join(el.itertext()))[:80],
                )
            self.notes[key] = body
            self.note_ids.append(key)
            if not el.get("corresp"):
                self.report.add(
                    self.cfg["key"], "footnote without corresp anchor", key
                )
        return key, body

    def _register_app(self, el: ET.Element) -> tuple[str, str, str]:
        """Add an apparatus popover entry and return its id, register, and lemma."""
        self.app_counter += 1
        app_id = f"app-{self.app_counter}"
        register = "testimonia" if el.get("type") == "testimonia" else "crit"
        lem = el.find(f"{TEI}lem")
        lem_out: list[str] = []
        if lem is not None:
            self._render_children_isolated(lem, lem_out)
        lem_html = "".join(lem_out).strip()
        entry: list[str] = []
        if register == "testimonia":
            entry.append('<div class="app-register-label">Testimonia</div>')
        if lem is not None:
            wit = self._wit_html(" ".join(filter(None, [lem.get("wit"), lem.get("source")])))
            entry.append(
                '<div class="app-reading app-lem-line">'
                f'<span class="app-lem-text">{lem_html or "&nbsp;"}</span>'
                + (f' <span class="app-wit">{wit}</span>' if wit else "")
                + "</div>"
            )
        for child in el:
            cname = local_name(child.tag)
            if cname == "rdg":
                rdg_out: list[str] = []
                self._render_children_isolated(child, rdg_out)
                rdg_html = "".join(rdg_out).strip() or "<em>om.</em>"
                wit = self._wit_html(" ".join(filter(None, [child.get("wit"), child.get("source")])))
                entry.append(
                    f'<div class="app-reading"><span class="app-rdg">{rdg_html}</span>'
                    + (f' <span class="app-wit">{wit}</span>' if wit else "")
                    + "</div>"
                )
            elif cname == "note":
                note_out: list[str] = []
                self._render_children_isolated(child, note_out)
                entry.append(f'<div class="app-note">{"".join(note_out).strip()}</div>')
            elif cname == "lem":
                for sub in child:
                    if local_name(sub.tag) == "note":
                        note_out = []
                        self._render_children_isolated(sub, note_out)
                        entry.append(
                            f'<div class="app-note">{"".join(note_out).strip()}</div>'
                        )
        self.apps[app_id] = "".join(entry)
        return app_id, register, lem_html

    def el_app(self, el: ET.Element, out: list[str]) -> None:
        app_id, register, lem_html = self._register_app(el)
        display = lem_html if lem_html else '<span class="app-empty">†</span>'
        out.append(
            f'<span class="app app-{register}" data-app="{app_id}">{display}</span>'
        )
        if self._track_running_text:
            self._last_running_text = (out, len(out) - 1)

    def el_anchor(self, el: ET.Element, out: list[str]) -> None:
        for app in self.stand_off_apps.get(xml_id(el), []):
            app_id, register, _lem_html = self._register_app(app)
            out.append(
                f'<span class="app app-{register} app-standoff" '
                f'data-app="{app_id}">†</span>'
            )

    def el_lem(self, el: ET.Element, out: list[str]) -> None:  # only via el_app
        self.render_children(el, out)

    def el_rdg(self, el: ET.Element, out: list[str]) -> None:  # only via el_app
        self.render_children(el, out)

    def el_milestone(self, el: ET.Element, out: list[str]) -> None:
        unit = el.get("unit", "")
        out.append(f'<span class="milestone" data-unit="{esc(unit)}"></span>')

    # -- entry point ----------------------------------------------------------

    def render_chapter(self, div: ET.Element,
                       entry_pb: ET.Element | None = None) -> dict:
        self._track_running_text = True
        self._last_running_text = None
        self._pending_page_break = None
        self.pages = []
        if entry_pb is not None:
            inherited = self._page_record(entry_pb)
            inherited["inherited"] = True
            self.pages.append(inherited)
        self.note_ids = []
        self.ref_note_ids = []
        out: list[str] = []
        n = div.get("n", "")
        cid = xml_id(div)
        out.append(f'<div class="chapter" data-n="{esc(n)}" id="{esc(cid)}">')
        self.render_children(div, out)
        out.append("</div>")
        return {
            "id": cid,
            "html": "".join(out),
            "pages": self.pages,
            "noteIds": self.note_ids,
            "refNoteIds": self.ref_note_ids,
        }


# ---------------------------------------------------------------------------
# Per-edition build
# ---------------------------------------------------------------------------

def load_chapter_table() -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = {}
    with CHAPTER_TABLE.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            table[row["n"]] = row
    return table


def load_witnesses(root: ET.Element) -> dict[str, str]:
    witnesses: dict[str, str] = {}
    for el in root.iter():
        if local_name(el.tag) in {"witness", "bibl"}:
            ident = xml_id(el)
            if ident:
                text = norm_space("".join(el.itertext()))
                witnesses.setdefault(ident, text)
    return witnesses


def collect_stand_off_apps(root: ET.Element, stream: ET.Element,
                           cfg: dict, report: Report) -> dict[str, list[ET.Element]]:
    """Index stand-off apparatus entries by each body start anchor they target."""
    body_anchors = {
        xml_id(anchor)
        for anchor in stream.iter(f"{TEI}anchor")
        if xml_id(anchor)
    }
    by_anchor: dict[str, list[ET.Element]] = {}
    for stand_off in root.findall(f"{TEI}standOff"):
        for list_app in stand_off.iter(f"{TEI}listApp"):
            for app in list_app.findall(f"{TEI}app"):
                label = xml_id(app) or "unidentified app"
                pointers = app.findall(f"{TEI}ptr")
                has_range = "from" in app.attrib or "to" in app.attrib
                if has_range:
                    if pointers or not app.get("from") or not app.get("to"):
                        report.add(cfg["key"], "stand-off apparatus", f"incomplete or mixed range on {label}")
                        continue
                    tokens = [app.get("from"), app.get("to")]
                else:
                    if len(pointers) != 1:
                        report.add(cfg["key"], "stand-off apparatus", f"expected one nonempty ptr on {label}")
                        continue
                    tokens = (pointers[0].get("target") or "").split()
                    if not tokens or len(tokens) % 2:
                        report.add(cfg["key"], "stand-off apparatus", f"incomplete ptr target pairs on {label}")
                        continue
                invalid = False
                for target in tokens:
                    anchor_id = target[1:] if target.startswith("#") else ""
                    if not anchor_id or anchor_id not in body_anchors:
                        report.add(
                            cfg["key"], "stand-off apparatus",
                            f"range endpoint is not a body anchor on {label}: {target or '(missing)'}",
                        )
                        invalid = True
                if not invalid:
                    for target in tokens[::2]:
                        by_anchor.setdefault(target[1:], []).append(app)
    return by_anchor


def find_stream(root: ET.Element, cfg: dict, report: Report) -> ET.Element | None:
    body = root.find(f"{TEI}text/{TEI}body")
    if body is None:
        report.add(cfg["key"], "structure", "no text/body found")
        return None
    want = cfg["stream"]
    for div in body.findall(f"{TEI}div"):
        if div.get("type") != want["type"]:
            continue
        if "lang" in want and div.get(f"{XML}lang") != want["lang"]:
            continue
        return div
    report.add(cfg["key"], "structure", f"stream {want} not found")
    return None


def chapter_entry_page_breaks(root: ET.Element) -> dict[ET.Element, ET.Element]:
    """Map each chapter to the page milestone active at chapter entry."""
    current_pb: ET.Element | None = None
    entry_pages: dict[ET.Element, ET.Element] = {}
    for el in root.iter():
        if el.tag == f"{TEI}pb":
            current_pb = el
        elif el.tag == f"{TEI}div" and el.get("subtype") == "chapter":
            if current_pb is not None:
                entry_pages[el] = current_pb
    return entry_pages


def chapter_label(cfg: dict, book_n: str, ch_n: str, div: ET.Element,
                  table: dict, report: Report) -> str | None:
    if ch_n == "praef":
        if book_n != "1":
            head = div.find(f"{TEI}head")
            if head is not None:
                label = norm_space("".join(head.itertext()))
                if label:
                    return label
        return "Praefatio"
    source = cfg["label_source"]
    if source.startswith("table:"):
        row = table.get(f"{book_n}.{ch_n}")
        if row:
            label = row.get(f"label_{source.split(':')[1]}", "").strip()
            if label:
                return normalize_reading_label(label)
    if source == "head" or source.startswith("table:"):
        head = div.find(f"{TEI}head")
        if head is not None:
            label = element_reading_text(head)
            if label:
                return label
    # deterministic fallback: first words of the chapter body (notes excluded)
    words: list[str] = []
    for el in div.iter():
        if local_name(el.tag) in {"note", "fw", "head"}:
            continue
        if el.text:
            words.append(el.text)
        if len(" ".join(words)) > 120:
            break
    text = norm_space(" ".join(words))
    if not text:
        report.add(cfg["key"], "empty chapter label", f"{book_n}.{ch_n}")
        return None
    if len(text) > 60:
        text = text[:60].rsplit(" ", 1)[0] + "…"
    return text


def global_footnote_bodies(root: ET.Element, renderer: ChapterRenderer) -> dict[str, str]:
    """Render every addressable footnote once for cross-book ref resolution."""
    notes: dict[str, str] = {}
    for note in root.iter(f"{TEI}note"):
        if note.get("type") != "footnote":
            continue
        note_id = xml_id(note)
        if not note_id:
            continue
        inner: list[str] = []
        renderer.render_children(note, inner)
        n = note.get("n", "")
        body = f'<span class="note-n">{esc(n)}</span> ' if n else ""
        notes[note_id] = body + "".join(inner).strip()
    return notes


def build_edition(cfg: dict, table: dict, report: Report,
                  out_dir: Path = OUT_DIR) -> dict | None:
    tei_path = ROOT / cfg["tei_path"]
    # Bundle verification already checked this XML. Attribution is read before
    # includes expand the separate witness/reference libraries into the header.
    credits = extract_credits(ET.parse(tei_path).getroot())
    root = parse_tei(tei_path)
    if root is None:
        report.add(cfg["key"], "structure", f"cannot parse {cfg['tei_path']}")
        return None
    stream = find_stream(root, cfg, report)
    if stream is None:
        return None
    witnesses = load_witnesses(root)
    renderer_cfg = cfg
    if cfg["anchored_notes"] == "auto":
        renderer_cfg = {
            **cfg,
            "anchored_notes": any(
                ref.get("type") == "footnote-ref" for ref in stream.iter(f"{TEI}ref")
            ),
        }
    stand_off_apps = collect_stand_off_apps(root, stream, cfg, report)
    renderer = ChapterRenderer(
        renderer_cfg, tei_path, witnesses, report, stand_off_apps
    )
    global_notes = global_footnote_bodies(root, renderer)
    # Born-digital translations deliberately have no physical-page model.  Other
    # editions retain root-level inheritance because some TEIs place the active
    # page milestone immediately outside their selected text stream.
    entry_pages = {} if cfg["facs"] == "none" else chapter_entry_page_breaks(root)

    edition_out_dir = out_dir / cfg["key"]
    edition_out_dir.mkdir(parents=True, exist_ok=True)
    books_manifest: list[dict] = []
    chunks: list[tuple[Path, dict]] = []
    book_numbers: set[str] = set()

    for book in stream.findall(f"{TEI}div"):
        if book.get("subtype") != "book":
            report.add(cfg["key"], "structure",
                       f"non-book div under stream: {book.attrib}")
            continue
        book_n = book.get("n", "")
        if not re.fullmatch(r"[1-9][0-9]*", book_n):
            raise ValueError(f"Invalid book identifier for reader output: {book_n!r}")
        if book_n in book_numbers:
            raise ValueError(f"Duplicate book route in {cfg['key']}: {book_n}")
        book_numbers.add(book_n)
        chapters: dict[str, dict] = {}
        chapter_list: list[dict] = []
        for chapter in book.findall(f"{TEI}div"):
            if chapter.get("subtype") != "chapter":
                report.add(cfg["key"], "structure",
                           f"non-chapter div under book {book_n}: {chapter.attrib}")
                continue
            ch_n = chapter.get("n", "")
            if ch_n in chapters:
                raise ValueError(f"Duplicate chapter route in {cfg['key']}: {book_n}.{ch_n}")
            if not ch_n or "/" in ch_n or any(character.isspace() for character in ch_n):
                raise ValueError(f"Invalid chapter route in {cfg['key']}: {book_n}.{ch_n}")
            rendered = renderer.render_chapter(chapter, entry_pages.get(chapter))
            label = chapter_label(cfg, book_n, ch_n, chapter, table, report)
            rendered["label"] = label
            chapters[ch_n] = rendered
            chapter_list.append({"n": ch_n, "label": label})
        chunk = {
            "edition": cfg["key"],
            "book": book_n,
            "chapters": chapters,
            "notes": dict(renderer.notes),
            "apps": dict(renderer.apps),
        }
        renderer.notes.clear()
        renderer.apps.clear()
        chunk_path = edition_out_dir / f"book-{book_n}.json"
        chunks.append((chunk_path, chunk))
        books_manifest.append({"n": book_n, "chapters": chapter_list})

    for chunk_path, chunk in chunks:
        referenced = {
            note_id
            for chapter in chunk["chapters"].values()
            for note_id in chapter.pop("refNoteIds")
        }
        for note_id in sorted(referenced):
            body = global_notes.get(note_id)
            if body is None:
                report.add(cfg["key"], "footnote ref target missing", note_id)
            else:
                chunk["notes"].setdefault(note_id, body)
        chunk_path.write_text(
            json.dumps(chunk, ensure_ascii=False), encoding="utf-8", newline="\n"
        )

    return {
        "label": cfg["label"],
        "lang": cfg["lang"],
        "tei_path": cfg["tei_path"],
        "facs_mode": cfg["facs"],
        "footnote_display": cfg.get("footnote_display", "chapter-end"),
        "credits": credits,
        "books": books_manifest,
    }
