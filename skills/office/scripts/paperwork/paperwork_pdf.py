from __future__ import annotations

import html
import json
from pathlib import Path
from string import Template

from core.office_result import Issue
from core.image_fit import sized_style
from core.page_sizes import DEFAULT_PAPER
from core.units import POINTS_PER_INCH, MILLIMETRES_PER_INCH, millimetres_to_pixels
from doc.blocks.writers import file_data_uri
from doc.blocks.pdf import DocumentFonts, covering_fonts, draw
from balance.fit import fit_rhythm
from balance.measure import Body, measure_pdf
from balance.rhythm import Rhythm
from balance.tokens import BODY_BOTTOM_MARGIN_MILLIMETERS
from paperwork.paperwork_design import COLOR_BORDER, COLOR_HEADER_FILL, COLOR_INK, COLOR_MUTED, COLOR_RULE, PDF_PAGE_MARGIN_MILLIMETERS, SIZE_BODY, SIZE_FOOTER, SIZE_LETTERHEAD_DETAIL, SIZE_LETTERHEAD_NAME, SIZE_TITLE
from paperwork.blanks import is_left_blank
from paperwork.jurisdictions import Jurisdiction, Labels
from render.renderer import DocumentPdfRequest, FontFile, render_document_pdf as render_pdf
from core.skill_paths import ASSETS_PATH


CSS_TEMPLATE_PATH = ASSETS_PATH / "paperwork" / "paperwork.css"
ALIGNMENTS = {"L": "align-left", "C": "align-center", "R": "align-right"}
UNBREAKABLE_KINDS = ("date", "amount", "quantity", "percent")
POINTS_PER_MILLIMETRE = POINTS_PER_INCH / MILLIMETRES_PER_INCH
IMAGE_BOXES_MILLIMETERS = {"logo": (40.0, 10.0), "stamp": (16.0, 16.0)}
BLANK = '<span class="blank"></span>'


def render_paperwork_pdf(document: dict, jurisdiction: Jurisdiction, output_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    font_path = str(document.get("fontPath", "")).strip()
    fonts = covering_fonts(DocumentFonts(Path(font_path) if font_path else None), json.dumps(document, ensure_ascii=False), issues)
    draw(output_path, lambda drawn_path: render_fitted(paperwork_html(document, jurisdiction), drawn_path, text_of(document["title"]), fonts))
    return issues


def render_fitted(body: str, output_path: Path, title: str, fonts: list[FontFile]) -> None:
    def draw_at(rhythm: Rhythm, is_numbered: bool = False):
        render_pdf(pdf_request(body, output_path, title, fonts, rhythm, footer_html(is_numbered)))
        return measure_pdf(output_path, page_body())

    rhythm = fit_rhythm(draw_at)
    if len(draw_at(rhythm)) > 1:
        draw_at(rhythm, is_numbered=True)


def page_body() -> Body:
    top = PDF_PAGE_MARGIN_MILLIMETERS * POINTS_PER_MILLIMETRE
    return Body(top, DEFAULT_PAPER.millimetres[1] * POINTS_PER_MILLIMETRE - BODY_BOTTOM_MARGIN_MILLIMETERS * POINTS_PER_MILLIMETRE)


def pdf_request(body: str, output_path: Path, title: str, fonts: list[FontFile], rhythm: Rhythm, footer: str | None) -> DocumentPdfRequest:
    side = millimetres_to_pixels(PDF_PAGE_MARGIN_MILLIMETERS)
    return DocumentPdfRequest(
        html=body,
        css=rhythm.css(paperwork_css()),
        output_path=output_path,
        title=title,
        fonts=tuple(fonts),
        size=DEFAULT_PAPER.exact_pixels,
        margin={"top": side, "left": side, "right": side, "bottom": millimetres_to_pixels(BODY_BOTTOM_MARGIN_MILLIMETERS)},
        footer=footer,
    )


def footer_html(is_numbered: bool) -> str | None:
    if not is_numbered:
        return None
    return f'<div style="display:flex;justify-content:center;width:100%;font-size:{SIZE_FOOTER}pt;line-height:1.5;color:{hex_color(COLOR_MUTED)}"><span>- <span class="pageNumber"></span> -</span></div>'


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
        lead_html(document.get("lead") or []),
    ]
    sections = document.get("sections") or []
    flow = [part for part in (*items_html(document.get("items")), *(section_html(section) for section in sections[:-1])) if part]
    last_head, last_tail = split_section(sections[-1]) if sections else ("", "")
    flow = [*flow, last_head] if last_head else flow
    closed = [last_tail] if last_tail else flow[-1:]
    flow = flow if last_tail else flow[:-1]
    sign_off = [notes_html(document.get("notes") or []), signature_html(document.get("signature"), profile, labels), colophon_html(document.get("footer"))]
    parts = [*heading, *flow, closing_html(closed, sign_off)]
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


def filled_or_blank(container: object, key: str | int) -> str:
    if is_left_blank(container, key):
        return BLANK
    return multiline(container[key] if isinstance(container, list) else container.get(key))


def image_html(path_value: object, css_class: str) -> str:
    path = Path(text_of(path_value))
    if not text_of(path_value) or not path.is_file():
        return ""
    box_width, box_height = IMAGE_BOXES_MILLIMETERS[css_class]
    return f'<img class="{css_class}" src="{file_data_uri(path.read_bytes(), path.name)}" style="{sized_style(path, box_width, box_height, "mm")}">'


def company_display_name(profile: dict) -> str:
    return text_of(profile.get("name") or profile.get("companyName")) if isinstance(profile, dict) else ""


def letterhead_html(profile: dict, labels: Labels) -> str:
    details = "".join(f'<p class="detail">{html.escape(line)}</p>' for line in letterhead_detail_lines(profile, labels))
    name = company_display_name(profile)
    company = f'<div class="company"><p class="name">{html.escape(name) if name else BLANK}</p>{details}</div>'
    return f'<header class="letterhead">{image_html(profile.get("logoPath"), "logo")}{company}</header>'


def letterhead_detail_lines(profile: dict, labels: Labels) -> list[str]:
    identity = [*legal_identity(profile, labels), *representative_identity(profile, labels)]
    numbers = [f"{label} {text_of(profile.get(field))}" for field, label in (("phone", labels.phone), ("fax", labels.fax)) if text_of(profile.get(field))]
    contact = "  ".join([*numbers, *(text_of(profile.get(field)) for field in ("email", "website") if text_of(profile.get(field)))])
    return [line for line in ("  ".join(identity), text_of(profile.get("address")), contact) if line]


def legal_identity(profile: dict, labels: Labels) -> list[str]:
    attributes = profile.get("legalAttributes")
    pairs = [(text_of(attribute.get("label")), text_of(attribute.get("value"))) for attribute in (attributes if isinstance(attributes, list) else []) if isinstance(attribute, dict)]
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
    lines = "".join(f'<p class="line">{filled_or_blank(recipient["lines"], index)}</p>' for index in range(len(recipient["lines"])))
    return f'<div class="recipient"><p class="label">{escaped(recipient.get("label")) or html.escape(labels.recipient)}</p>{lines}</div>'


def meta_html(rows: list) -> str:
    if not rows:
        return ""
    cells = "".join(f'<div class="meta-row"><div class="meta-label">{escaped(row.get("label"))}</div><div class="{unbreakable_class("meta-value", row.get("kind"))}">{filled_or_blank(row, "value")}</div></div>' for row in rows)
    return f'<div class="meta">{cells}</div>'


def unbreakable_class(base: str, kind: object) -> str:
    return f"{base} unbreakable" if text_of(kind) in UNBREAKABLE_KINDS else base


def column_kinds(kinds: object, column_count: int) -> list[str]:
    given = kinds if isinstance(kinds, list) else []
    return [text_of(given[index]) if index < len(given) else "" for index in range(column_count)]


def multiline(value: object) -> str:
    return "<br>".join(html.escape(line) for line in text_of(value).split("\n"))


def items_html(items: dict | None) -> tuple[str, str]:
    if items is None:
        return ("", "")
    headers = items["headers"]
    alignments = column_alignments(items.get("aligns"), len(headers))
    head = "".join(f"<th>{escaped(header)}</th>" for header in headers)
    kinds = column_kinds(items.get("kinds"), len(headers))
    body = "".join(item_row_html(row, alignments, kinds) for row in items.get("rows") or [])
    return (f'<table class="items"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>', totals_html(items.get("totals") or []))


def column_alignments(aligns: object, column_count: int) -> list[str]:
    given = aligns if isinstance(aligns, list) else []
    return [ALIGNMENTS.get(text_of(given[index]).upper() if index < len(given) else "L", ALIGNMENTS["L"]) for index in range(column_count)]


def item_row_html(row: object, alignments: list[str], kinds: list[str]) -> str:
    values = row if isinstance(row, list) else []
    cells = "".join(f'<td class="{unbreakable_class(alignment, kinds[index])}">{multiline(values[index] if index < len(values) else "")}</td>' for index, alignment in enumerate(alignments))
    return f"<tr>{cells}</tr>"


def totals_html(totals: list) -> str:
    if not totals:
        return ""
    lines = "".join(f'<p class="{"final" if index == len(totals) - 1 else ""}">{escaped(total.get("label"))}<span class="value">{filled_or_blank(total, "value")}</span></p>' for index, total in enumerate(totals))
    return f'<div class="totals">{lines}</div>'


def section_html(section: dict) -> str:
    title = text_of(section.get("title"))
    heading = f"<h2>{html.escape(title)}</h2>" if title else ""
    paragraph_lines = section.get("paragraphs") or []
    bullet_lines = section.get("bullets") or []
    paragraphs = "".join(f"<p>{filled_or_blank(paragraph_lines, index)}</p>" for index in range(len(paragraph_lines)))
    bullets = "".join(f'<p class="bullet">• {filled_or_blank(bullet_lines, index)}</p>' for index in range(len(bullet_lines)))
    return f'<div class="section">{heading}{paragraphs}{bullets}</div>'


def split_section(section: dict) -> tuple[str, str]:
    title = text_of(section.get("title"))
    heading = f"<h2>{html.escape(title)}</h2>" if title else ""
    paragraph_lines = section.get("paragraphs") or []
    bullet_lines = section.get("bullets") or []
    lines = [f"<p>{filled_or_blank(paragraph_lines, index)}</p>" for index in range(len(paragraph_lines))]
    lines += [f'<p class="bullet">• {filled_or_blank(bullet_lines, index)}</p>' for index in range(len(bullet_lines))]
    if len(lines) < 2:
        return "", section_html(section)
    return f'<div class="section">{heading}{"".join(lines[:-1])}</div>', f'<div class="section">{lines[-1]}</div>'


def colophon_html(footer: object) -> str:
    return f'<p class="colophon">{escaped(footer)}</p>' if text_of(footer) else ""


def lead_html(lead: list) -> str:
    return f'<div class="lead">{"".join(f"<p>{escaped(line)}</p>" for line in lead)}</div>' if lead else ""


def notes_html(notes: list) -> str:
    return f'<div class="notes">{"".join(f"<p>{escaped(note)}</p>" for note in notes)}</div>' if notes else ""


def signature_html(signature: object, profile: dict, labels: Labels) -> str:
    if not isinstance(signature, dict):
        return ""
    date_line = f'<p class="date">{filled_or_blank(signature, "date")}</p>' if text_of(signature.get("date")) or is_left_blank(signature, "date") else ""
    stamp = image_html(profile.get("stampPath"), "stamp") if signature.get("stamp") and isinstance(profile, dict) else ""
    seal = f'<span class="seal">{html.escape(labels.seal_mark)}{stamp}</span>' if labels.seal_mark or stamp else ""
    has_signer = text_of(signature.get("line")) or is_left_blank(signature, "line")
    signer = f'<div class="signer"><span>{filled_or_blank(signature, "line")}</span>{seal}</div>' if has_signer else ""
    return f'<div class="signature">{date_line}{signer}</div>'
