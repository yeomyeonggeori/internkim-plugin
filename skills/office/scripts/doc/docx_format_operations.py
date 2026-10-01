from __future__ import annotations

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
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
TEXT_PROPERTIES = ("bold", "italic", "underline", "strike", "color", "highlight", "size", "font", "baseline")
PARAGRAPH_PROPERTIES = ("align", "spaceBeforePoints", "spaceAfterPoints", "lineSpacing", "indentLeftInches", "indentRightInches", "firstLineIndentInches", "keepWithNext", "pageBreakBefore", "shadingFill", "borders", "borderColor")
STYLE_TYPES = {"paragraph": WD_STYLE_TYPE.PARAGRAPH, "character": WD_STYLE_TYPE.CHARACTER}
# Element order of CT_PPrBase after w:pBdr, ECMA-376 Part 1, 17.3.1.26
PARAGRAPH_PROPERTIES_AFTER_BORDERS = (
    "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN",
    "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
    "w:textDirection", "w:textAlignment", "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
)
BORDER_EIGHTHS_OF_A_POINT = "4"
DEFAULT_BORDER_COLOR = "000000"


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
    if operation.get("baseline"):
        set_baseline(font, operation["baseline"])
    if old_properties is not None:
        record_run_property_change(run_element, old_properties, tracking)


def set_baseline(font, baseline: str) -> None:
    if baseline == "superscript":
        font.superscript = True
    elif baseline == "subscript":
        font.subscript = True
    else:
        font.superscript = None


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
    if operation.get("indentRightInches") is not None:
        paragraph_format.right_indent = Inches(operation["indentRightInches"])
    if operation.get("firstLineIndentInches") is not None:
        paragraph_format.first_line_indent = Inches(operation["firstLineIndentInches"])
    if operation.get("keepWithNext") is not None:
        paragraph_format.keep_with_next = operation["keepWithNext"]
    if operation.get("pageBreakBefore") is not None:
        paragraph_format.page_break_before = operation["pageBreakBefore"]
    decorate_paragraph(paragraph_format._element.get_or_add_pPr(), operation)


def decorate_paragraph(paragraph_properties, operation: dict) -> None:
    if operation.get("shadingFill"):
        replace_property(paragraph_properties, "w:shd", shading(operation["shadingFill"]), PARAGRAPH_PROPERTIES_AFTER_BORDERS[1:])
    if operation.get("borders") is not None:
        replace_property(paragraph_properties, "w:pBdr", paragraph_borders(operation["borders"], operation.get("borderColor")), PARAGRAPH_PROPERTIES_AFTER_BORDERS)
    elif operation.get("borderColor"):
        recolor_borders(paragraph_properties, operation["borderColor"])


def replace_property(paragraph_properties, tag: str, element, successors: tuple[str, ...]) -> None:
    existing = paragraph_properties.find(qn(tag))
    if existing is not None:
        paragraph_properties.remove(existing)
    if element is not None:
        paragraph_properties.insert_element_before(element, *successors)


def shading(color: str):
    if color == "none":
        return None
    element = OxmlElement("w:shd")
    for name, value in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", color.lstrip("#").upper())):
        element.set(qn(name), value)
    return element


def paragraph_borders(sides: list[str], color: str | None):
    if not sides:
        return None
    borders = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        if side in sides:
            borders.append(border_line(side, color or DEFAULT_BORDER_COLOR))
    return borders


def border_line(side: str, color: str):
    line = OxmlElement(f"w:{side}")
    for name, value in (("w:val", "single"), ("w:sz", BORDER_EIGHTHS_OF_A_POINT), ("w:space", "1"), ("w:color", color.lstrip("#").upper())):
        line.set(qn(name), value)
    return line


def recolor_borders(paragraph_properties, color: str) -> None:
    borders = paragraph_properties.find(qn("w:pBdr"))
    for line in borders if borders is not None else ():
        line.set(qn("w:color"), color.lstrip("#").upper())


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
    if operation.get("baseline"):
        set_baseline(font, operation["baseline"])
    if style.type == WD_STYLE_TYPE.PARAGRAPH:
        format_paragraph(style.paragraph_format, operation)

