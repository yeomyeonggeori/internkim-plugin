from __future__ import annotations

import html
import json
from pathlib import Path
from string import Template

import pypdfium2

from core.office_result import Issue
from core.page_sizes import DEFAULT_PAPER
from core.units import millimetres_to_pixels
from doc.blocks.writers import file_data_uri
from doc.blocks.pdf import DocumentFonts, covering_fonts, draw
from paperwork.paperwork_design import COLOR_BORDER, COLOR_HEADER_FILL, COLOR_INK, COLOR_MUTED, COLOR_RULE, PDF_PAGE_MARGIN_MILLIMETERS, SIZE_BODY, SIZE_FOOTER, SIZE_LETTERHEAD_DETAIL, SIZE_LETTERHEAD_NAME, SIZE_TITLE
from paperwork.jurisdictions import Jurisdiction, Labels
from render.renderer import DocumentPdfRequest, FontFile, render_document_pdf as render_pdf
from core.skill_paths import ASSETS_PATH


CSS_TEMPLATE_PATH = ASSETS_PATH / "paperwork" / "paperwork.css"
BOTTOM_MARGIN_MILLIMETERS = 20.0
ALIGNMENTS = {"L": "align-left", "C": "align-center", "R": "align-right"}


def render_paperwork_pdf(document: dict, jurisdiction: Jurisdiction, output_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    font_path = str(document.get("fontPath", "")).strip()
    fonts = covering_fonts(DocumentFonts(Path(font_path) if font_path else None), json.dumps(document, ensure_ascii=False), issues)
    footer_text = text_of(document.get("footer"))
    draw(output_path, lambda drawn_path: render_numbering_only_when_paged(paperwork_html(document, jurisdiction), drawn_path, text_of(document["title"]), fonts, footer_text))
    return issues


def render_numbering_only_when_paged(body: str, output_path: Path, title: str, fonts: list[FontFile], footer_text: str) -> None:
    render_pdf(pdf_request(body, output_path, title, fonts, footer_html(footer_text, is_numbered=False)))
    if page_count(output_path) > 1:
        render_pdf(pdf_request(body, output_path, title, fonts, footer_html(footer_text, is_numbered=True)))


def pdf_request(body: str, output_path: Path, title: str, fonts: list[FontFile], footer: str | None) -> DocumentPdfRequest:
    side = millimetres_to_pixels(PDF_PAGE_MARGIN_MILLIMETERS)
    return DocumentPdfRequest(
        html=body,
        css=paperwork_css(),
        output_path=output_path,
        title=title,
        fonts=tuple(fonts),
        size=DEFAULT_PAPER.exact_pixels,
        margin={"top": side, "left": side, "right": side, "bottom": millimetres_to_pixels(BOTTOM_MARGIN_MILLIMETERS)},
        footer=footer,
    )


def page_count(pdf_path: Path) -> int:
    document = pypdfium2.PdfDocument(str(pdf_path))
    try:
        return len(document)
    finally:
        document.close()


def footer_html(footer_text: str, is_numbered: bool) -> str | None:
    lines = [f"<span>{html.escape(footer_text)}</span>"] if footer_text else []
    if is_numbered:
        lines.append('<span>- <span class="pageNumber"></span> -</span>')
    if not lines:
        return None
    return f'<div style="display:flex;flex-direction:column;align-items:center;width:100%;font-size:{SIZE_FOOTER}pt;line-height:1.5;color:{hex_color(COLOR_MUTED)}">{"".join(lines)}</div>'


def paperwork_css() -> str:
    return Template(CSS_TEMPLATE_PATH.read_text(encoding="utf-8")).substitute(
        ink=hex_color(COLOR_INK),
        muted=hex_color(COLOR_MUTED),
        rule=hex_color(COLOR_RULE),
        border=hex_color(COLOR_BORDER),
        header_fill=hex_color(COLOR_HEADER_FILL),
        title=f"{SIZE_TITLE + 3}pt",
        body=f"{SIZE_BODY}pt",
        letterhead_name=f"{SIZE_LETTERHEAD_NAME}pt",
        letterhead_detail=f"{SIZE_LETTERHEAD_DETAIL}pt",
    )


def hex_color(color: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in color)


def paperwork_html(document: dict, jurisdiction: Jurisdiction) -> str:
    profile = document.get("profile", {})
    labels = jurisdiction.labels
    heading = [
        letterhead_html(profile, labels),
        approval_html(document.get("approvalLine") or []),
        title_html(document, labels),
        recipient_html(document.get("recipient"), labels),
        meta_html(document.get("meta") or []),
    ]
    body = [part for part in (*items_html(document.get("items")), *(section_html(section) for section in document.get("sections") or [])) if part]
    sign_off = [notes_html(document.get("notes") or []), signature_html(document.get("signature"), profile, labels)]
    parts = [*heading, *body[:-1], closing_html(body[-1:], sign_off)]
    return f'<div class="page" lang="{jurisdiction.language}">' + "\n".join(part for part in parts if part) + "</div>"


def closing_html(closed: list[str], sign_off: list[str]) -> str:
    signed = "".join(sign_off)
    if not signed:
        return "".join(closed)
    return f'<div class="closing">{"".join(closed)}<div class="sign-off">{signed}</div></div>'


def text_of(value: object) -> str:
    return "" if value is None else str(value).strip()


def escaped(value: object) -> str:
    return html.escape(text_of(value))


def image_html(path_value: object, css_class: str) -> str:
    path = Path(text_of(path_value))
    if not text_of(path_value) or not path.is_file():
        return ""
    return f'<img class="{css_class}" src="{file_data_uri(path.read_bytes(), path.name)}">'


def company_display_name(profile: dict) -> str:
    return text_of(profile.get("name") or profile.get("companyName")) if isinstance(profile, dict) else ""


def letterhead_html(profile: dict, labels: Labels) -> str:
    details = "".join(f'<p class="detail">{html.escape(line)}</p>' for line in letterhead_detail_lines(profile, labels))
    company = f'<div class="company"><p class="name">{html.escape(company_display_name(profile))}</p>{details}</div>'
    return f'<header class="letterhead">{image_html(profile.get("logoPath"), "logo")}{company}</header>'


def letterhead_detail_lines(profile: dict, labels: Labels) -> list[str]:
    identity = [*legal_identity(profile, labels), *representative_identity(profile, labels)]
    contact = "  ".join(part for part in (text_of(profile.get(field)) for field in ("phone", "email", "website")) if part)
    return [line for line in ("  ".join(identity), text_of(profile.get("address")), contact) if line]


def legal_identity(profile: dict, labels: Labels) -> list[str]:
    attributes = profile.get("legalAttributes")
    pairs = [(text_of(attribute.get("label")), text_of(attribute.get("value"))) for attribute in (attributes if isinstance(attributes, list) else [])[:2] if isinstance(attribute, dict)]
    labeled = [f"{label} {value}" for label, value in pairs if label and value]
    registration = text_of(profile.get("registrationNumber"))
    return labeled or ([f"{labels.registration_number} {registration}"] if registration else [])


def representative_identity(profile: dict, labels: Labels) -> list[str]:
    representative = text_of(profile.get("representative"))
    if not representative:
        return []
    return [f"{text_of(profile.get('representativeTitle')) or labels.representative_title} {representative}"]


def approval_html(approvers: list) -> str:
    if not approvers:
        return ""
    entries = [approver if isinstance(approver, dict) else {"role": approver} for approver in approvers]
    headers = "".join(f"<th>{escaped(entry.get('role'))}</th>" for entry in entries)
    boxes = "".join(approver_box(entry.get("name")) for entry in entries)
    return f'<div class="approval"><table><tr>{headers}</tr><tr>{boxes}</tr></table></div>'


def approver_box(name: object) -> str:
    return f'<td><span class="approver">{escaped(name)}</span></td>' if text_of(name) else "<td></td>"


def title_html(document: dict, labels: Labels) -> str:
    number = text_of(document.get("documentNumber"))
    number_line = f'<p class="document-number">{html.escape(labels.document_number)} {html.escape(number)}</p>' if number else ""
    return f'<div class="title-block"><h1>{escaped(document["title"])}</h1>{number_line}</div>'


def recipient_html(recipient: object, labels: Labels) -> str:
    if not isinstance(recipient, dict) or not recipient.get("lines"):
        return ""
    lines = "".join(f'<p class="line">{escaped(line)}</p>' for line in recipient["lines"])
    return f'<div class="recipient"><p class="label">{escaped(recipient.get("label")) or html.escape(labels.recipient)}</p>{lines}</div>'


def meta_html(rows: list) -> str:
    if not rows:
        return ""
    cells = "".join(f'<div class="meta-row"><div class="meta-label">{escaped(row.get("label"))}</div><div class="meta-value">{multiline(row.get("value"))}</div></div>' for row in rows)
    return f'<div class="meta">{cells}</div>'


def multiline(value: object) -> str:
    return "<br>".join(html.escape(line) for line in text_of(value).split("\n"))


def items_html(items: dict | None) -> tuple[str, str]:
    if items is None:
        return ("", "")
    headers = items["headers"]
    alignments = column_alignments(items.get("aligns"), len(headers))
    head = "".join(f"<th>{escaped(header)}</th>" for header in headers)
    body = "".join(item_row_html(row, alignments) for row in items.get("rows") or [])
    return (f'<table class="items"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>', totals_html(items.get("totals") or []))


def column_alignments(aligns: object, column_count: int) -> list[str]:
    given = aligns if isinstance(aligns, list) else []
    return [ALIGNMENTS.get(text_of(given[index]).upper() if index < len(given) else "L", ALIGNMENTS["L"]) for index in range(column_count)]


def item_row_html(row: object, alignments: list[str]) -> str:
    values = row if isinstance(row, list) else []
    cells = "".join(f'<td class="{alignment}">{multiline(values[index] if index < len(values) else "")}</td>' for index, alignment in enumerate(alignments))
    return f"<tr>{cells}</tr>"


def totals_html(totals: list) -> str:
    if not totals:
        return ""
    lines = "".join(f'<p class="{"final" if index == len(totals) - 1 else ""}">{escaped(total.get("label"))}<span class="value">{escaped(total.get("value"))}</span></p>' for index, total in enumerate(totals))
    return f'<div class="totals">{lines}</div>'


def section_html(section: dict) -> str:
    title = text_of(section.get("title"))
    heading = f"<h2>{html.escape(title)}</h2>" if title else ""
    paragraphs = "".join(f"<p>{multiline(paragraph)}</p>" for paragraph in section.get("paragraphs") or [])
    bullets = "".join(f'<p class="bullet">• {escaped(bullet)}</p>' for bullet in section.get("bullets") or [])
    return f'<div class="section">{heading}{paragraphs}{bullets}</div>'


def notes_html(notes: list) -> str:
    return f'<div class="notes">{"".join(f"<p>{escaped(note)}</p>" for note in notes)}</div>' if notes else ""


def signature_html(signature: object, profile: dict, labels: Labels) -> str:
    if not isinstance(signature, dict):
        return ""
    date = text_of(signature.get("date"))
    date_line = f'<p class="date">{html.escape(date)}</p>' if date else ""
    line = text_of(signature.get("line"))
    stamp = image_html(profile.get("stampPath"), "stamp") if signature.get("stamp") and isinstance(profile, dict) else ""
    seal = f'<span class="seal">{html.escape(labels.seal_mark)}{stamp}</span>' if labels.seal_mark or stamp else ""
    signer = f'<div class="signer"><span>{html.escape(line)}</span>{seal}</div>' if line else ""
    return f'<div class="signature">{date_line}{signer}</div>'
