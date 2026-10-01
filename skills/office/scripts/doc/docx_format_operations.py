from __future__ import annotations

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.text.run import Run

from doc.docx_editing import DocxEditing, require_style, resolve_block, resolve_paragraph
from doc.docx_text import PARAGRAPH_TAG, live_runs, run_text
from doc.docx_tracking import record_paragraph_property_change, record_run_property_change, runs_between, snapshot_paragraph_properties, snapshot_run_properties, split_runs_at
from core.office_operations import TARGET_NOT_FOUND, Change
from core.office_result import INVALID_VALUE, MISSING_FIELD, OfficeFailure


ALIGNMENTS = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}
HIGHLIGHTS = {
    "yellow": WD_COLOR_INDEX.YELLOW, "green": WD_COLOR_INDEX.BRIGHT_GREEN, "cyan": WD_COLOR_INDEX.TURQUOISE,
    "pink": WD_COLOR_INDEX.PINK, "blue": WD_COLOR_INDEX.BLUE, "red": WD_COLOR_INDEX.RED, "gray": WD_COLOR_INDEX.GRAY_25, "none": None,
}
TEXT_PROPERTIES = ("bold", "italic", "underline", "strike", "color", "highlight", "size", "font")
PARAGRAPH_PROPERTIES = ("align", "spaceBeforePoints", "spaceAfterPoints", "lineSpacing", "indentLeftInches", "firstLineIndentInches", "keepWithNext", "pageBreakBefore")
STYLE_TYPES = {"paragraph": WD_STYLE_TYPE.PARAGRAPH, "character": WD_STYLE_TYPE.CHARACTER}


def require_any(operation: dict, names: tuple[str, ...], location: str) -> None:
    if all(operation.get(name) is None for name in names):
        raise OfficeFailure(MISSING_FIELD.issue(f"{location}: give at least one of {', '.join(names)}", location))


def plan_format_text(editing: DocxEditing, operation: dict, location: str) -> Change:
    require_any(operation, TEXT_PROPERTIES, location)
    if operation.get("block") is None and not operation.get("find"):
        raise OfficeFailure(MISSING_FIELD.issue(f"{location}: give block, find, or both", location))
    paragraphs = scoped_paragraph_elements(editing, operation, location)
    runs = [run for paragraph in paragraphs for run in matching_runs(paragraph, operation.get("find"))]
    if not runs:
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.find: {operation.get('find')!r} does not occur", f"{location}.find"))

    def change() -> str:
        for run in runs:
            format_run(run, operation, editing.tracking)
        tracked = " as tracked changes" if editing.tracking is not None else ""
        return f"formatted {len(runs)} runs{tracked}"
    return change


def scoped_paragraph_elements(editing: DocxEditing, operation: dict, location: str) -> list:
    if operation.get("block") is None:
        return [paragraph for element in editing.elements for paragraph in paragraphs_within(element)]
    return paragraphs_within(resolve_block(editing, operation["block"], f"{location}.block"))


def paragraphs_within(element) -> list:
    return [element] if element.tag == PARAGRAPH_TAG else list(element.iter(PARAGRAPH_TAG))


def matching_runs(paragraph, find: str | None) -> list:
    if not find:
        return [run for run in live_runs(paragraph) if run_text(run)]
    text = "".join(run_text(run) for run in live_runs(paragraph))
    spans = []
    position = text.find(find)
    while position >= 0:
        spans.append((position, position + len(find)))
        position = text.find(find, position + len(find))
    for start, end in spans:
        split_runs_at(paragraph, (start, end))
    return [run for start, end in spans for run in runs_between(paragraph, start, end)]


def format_run(run_element, operation: dict, tracking) -> None:
    old_properties = snapshot_run_properties(run_element) if tracking is not None else None
    font = Run(run_element, None).font
    for name in ("bold", "italic", "underline", "strike"):
        if operation.get(name) is not None:
            setattr(font, name, operation[name])
    if operation.get("color"):
        font.color.rgb = RGBColor.from_string(operation["color"].lstrip("#").upper())
    if operation.get("highlight"):
        font.highlight_color = HIGHLIGHTS[operation["highlight"]]
    if operation.get("size") is not None:
        font.size = Pt(operation["size"])
    if operation.get("font"):
        set_run_font_name(font, operation["font"])
    if old_properties is not None:
        record_run_property_change(run_element, old_properties, tracking)


def set_run_font_name(font, name: str) -> None:
    font.name = name
    run_fonts = font._element.rPr.rFonts
    run_fonts.set(qn("w:eastAsia"), name)


def plan_set_paragraph_format(editing: DocxEditing, operation: dict, location: str) -> Change:
    require_any(operation, PARAGRAPH_PROPERTIES, location)
    paragraph = resolve_paragraph(editing, operation["block"], f"{location}.block")

    def change() -> str:
        old_properties = snapshot_paragraph_properties(paragraph._p) if editing.tracking is not None else None
        format_paragraph(paragraph.paragraph_format, operation)
        if old_properties is not None:
            record_paragraph_property_change(paragraph._p, old_properties, editing.tracking)
            return f"formatted block {operation['block']} as a tracked change"
        return f"formatted block {operation['block']}"
    return change


def format_paragraph(paragraph_format, operation: dict) -> None:
    if operation.get("align"):
        paragraph_format.alignment = ALIGNMENTS[operation["align"]]
    if operation.get("spaceBeforePoints") is not None:
        paragraph_format.space_before = Pt(operation["spaceBeforePoints"])
    if operation.get("spaceAfterPoints") is not None:
        paragraph_format.space_after = Pt(operation["spaceAfterPoints"])
    if operation.get("lineSpacing") is not None:
        paragraph_format.line_spacing = operation["lineSpacing"]
    if operation.get("indentLeftInches") is not None:
        paragraph_format.left_indent = Inches(operation["indentLeftInches"])
    if operation.get("firstLineIndentInches") is not None:
        paragraph_format.first_line_indent = Inches(operation["firstLineIndentInches"])
    if operation.get("keepWithNext") is not None:
        paragraph_format.keep_with_next = operation["keepWithNext"]
    if operation.get("pageBreakBefore") is not None:
        paragraph_format.page_break_before = operation["pageBreakBefore"]


def plan_define_style(editing: DocxEditing, operation: dict, location: str) -> Change:
    style_type = STYLE_TYPES[operation.get("type") or "paragraph"]
    if operation.get("basedOn"):
        require_style(editing, operation["basedOn"], (style_type,), f"{location}.basedOn")
    existing = next((style for style in editing.document.styles if style.name == operation["name"]), None)
    if existing is not None and existing.type != style_type:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.type: style {operation['name']!r} exists as another type", f"{location}.type"))

    style = existing or editing.document.styles.add_style(operation["name"], style_type)
    if operation.get("basedOn"):
        style.base_style = editing.document.styles[operation["basedOn"]]
    apply_style_properties(style, operation)

    def change() -> str:
        verb = "updated" if existing is not None else "defined"
        return f"{verb} style {operation['name']!r}"
    return change


def apply_style_properties(style, operation: dict) -> None:
    font = style.font
    for name in ("bold", "italic", "underline"):
        if operation.get(name) is not None:
            setattr(font, name, operation[name])
    if operation.get("size") is not None:
        font.size = Pt(operation["size"])
    if operation.get("color"):
        font.color.rgb = RGBColor.from_string(operation["color"].lstrip("#").upper())
    if operation.get("font"):
        font.name = operation["font"]
        style.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), operation["font"])
    if style.type == WD_STYLE_TYPE.PARAGRAPH:
        format_paragraph(style.paragraph_format, operation)

