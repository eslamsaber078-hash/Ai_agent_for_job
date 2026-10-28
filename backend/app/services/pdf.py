"""Render a prepared document into a sendable PDF.

The tracker shows him the whole truth, including the "what this ad asks for that your
CV does not show" section that must never reach an employer. The PDF is therefore
always rendered from the sendable text (assistant.cv_for_pdf), never from the stored
copy.

Additions the assistant suggested for one ad arrive wrapped in [[double brackets]].
They are drawn red and underlined in the review copy so nothing unconfirmed can be
skimmed past, and the caller strips them before producing the copy that goes out.
"""
from __future__ import annotations

import re
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate

_MARGIN = 18 * mm
_SUGGEST_COLOR = "#B42318"
_SUGGESTED_RE = re.compile(r"\[\[([^\[\]\n]{1,80})\]\]")

_STYLES = {
    "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=17,
                           leading=21, spaceAfter=3),
    "heading": ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=11.5,
                              leading=14, spaceBefore=10, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10,
                           leading=13.5, spaceAfter=2),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10, leading=13.5,
                             leftIndent=12, bulletIndent=0, spaceAfter=1.5),
    "indent": ParagraphStyle("indent", fontName="Helvetica", fontSize=10, leading=13.5,
                             leftIndent=16, spaceAfter=1.5),
    "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=8.5, leading=11,
                           textColor=_SUGGEST_COLOR, spaceBefore=8),
}


def _markup(escaped: str) -> str:
    """Turn [[suggestions]] into red underlined text; the line is already XML-escaped."""
    return _SUGGESTED_RE.sub(
        lambda m: f'<u><font color="{_SUGGEST_COLOR}">{m.group(1)}</font></u>', escaped
    )


def has_suggestions(content: str) -> bool:
    return bool(_SUGGESTED_RE.search(content or ""))


def render_text_pdf(content: str, name_line: bool = False, title: str = "Application document") -> bytes:
    """Lay a plain-text document out on A4 pages: one line = one paragraph.

    ALL-CAPS lines become bold headings, "- " lines get a bullet, indented lines are
    sub-bullets. When ``name_line`` is set, the first line is the document's big bold
    name (the CV header) instead of body text.
    """
    lines = [line.rstrip() for line in (content or "").split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    story = []
    first = name_line
    for line in lines:
        text = line.strip()
        if not text:
            continue
        if first:
            first = False
            story.append(Paragraph(_markup(escape(text)), _STYLES["name"]))
        elif text.startswith("RED ITEMS ARE SUGGESTIONS"):
            story.append(Paragraph(_markup(escape(text)), _STYLES["note"]))
        elif text.isupper() and len(text) > 2:
            story.append(Paragraph(_markup(escape(text)), _STYLES["heading"]))
        elif line.startswith("- "):
            story.append(Paragraph(_markup(escape(text[2:])), _STYLES["bullet"],
                                   bulletText="\u2022"))
        elif line.startswith("    "):
            story.append(Paragraph(_markup(escape(text)), _STYLES["indent"]))
        else:
            story.append(Paragraph(_markup(escape(text)), _STYLES["body"]))
    if not story:
        story.append(Paragraph("", _STYLES["body"]))
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=_MARGIN, rightMargin=_MARGIN,
                            topMargin=_MARGIN, bottomMargin=_MARGIN, title=title)
    doc.build(story)
    return buf.getvalue()
