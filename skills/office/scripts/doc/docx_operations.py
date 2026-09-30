import copy
from dataclasses import dataclass, field

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from doc_definitions import OPERATIONS
from docx_blocks import PARAGRAPH_TAG, TABLE_TAG, body_block_elements, paragraph_runs
from office_operations import OPERATION_NOT_APPLICABLE, TARGET_NOT_FOUND, Change, OperationSet
from office_result import INVALID_VALUE, OfficeFailure


SETTINGS_AFTER_UPDATE_FIELDS = (
    "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr", "attachedSchema",
    "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats", "doNotAutoCompressPictures", "forceUpgrade",
    "captions", "readModeInkLockDown", "smartTagType", "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags",
    "decimalSymbol", "listSeparator",
)


@dataclass
class DocxEditing:
    document: Document
    elements: list
    cursors: dict = field(default_factory=dict)
    deleted: set = field(default_factory=set)
    touched: set = field(default_factory=set)


def load_editing(path: str) -> DocxEditing:
    document = Document(path)
    return DocxEditing(document, body_block_elements(document))


def save_editing(editing: DocxEditing, path: str) -> None:
    editing.document.save(path)


def resolve_block(editing: DocxEditing, index: int, location: str):
    if index >= len(editing.elements):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: block {index} does not exist; the document has {len(editing.elements)} blocks", location))
    element = editing.elements[index]
    if id(element) in editing.deleted:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {index} is deleted by another operation in this batch", location))
    editing.touched.add(id(element))
    return element


def resolve_paragraph(editing: DocxEditing, index: int, location: str) -> Paragraph:
    element = resolve_block(editing, index, location)
    if element.tag != PARAGRAPH_TAG:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {index} is not a paragraph", location))
    return Paragraph(element, editing.document._body)


def resolve_table(editing: DocxEditing, index: int, location: str) -> Table:
    element = resolve_block(editing, index, location)
    if element.tag != TABLE_TAG:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {index} is not a table", location))
    return Table(element, editing.document._body)


def require_style(editing: DocxEditing, style_name: str, style_types: tuple, location: str) -> None:
    style = next((style for style in editing.document.styles if style.name == style_name), None)
    if style is None:
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: the document defines no style named {style_name!r}", location))
    if style.type not in style_types:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: style {style_name!r} cannot apply here", location))


def placement(editing: DocxEditing, operation: dict, location: str):
    after, before = operation.get("after"), operation.get("before")
    if (after is None) == (before is None):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: give exactly one of after and before", location))
    if before is not None:
        anchor = resolve_block(editing, before, f"{location}.before")
        return lambda element: anchor.addprevious(element)
    if after == -1:
        return start_placement(editing)
    anchor = resolve_block(editing, after, f"{location}.after")
    return cursor_placement(editing, anchor)


def start_placement(editing: DocxEditing):
    def place(element):
        cursor = editing.cursors.get("start")
        if cursor is not None:
            cursor.addnext(element)
        elif editing.elements:
            editing.elements[0].addprevious(element)
        editing.cursors["start"] = element
    return place


def cursor_placement(editing: DocxEditing, anchor):
    def place(element):
        editing.cursors.get(id(anchor), anchor).addnext(element)
        editing.cursors[id(anchor)] = element
    return place


def plan_replace_text(editing: DocxEditing, operation: dict, location: str) -> Change:
    paragraphs = scoped_paragraphs(editing, operation, location)
    occurrences = sum(joined_run_text(paragraph).count(operation["find"]) for paragraph in paragraphs)
    if occurrences == 0:
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: {operation['find']!r} does not occur", location))

    def change() -> str:
        replaced = sum(replace_in_paragraph(paragraph, operation["find"], operation["replace"]) for paragraph in paragraphs)
        return f"replaced {replaced} occurrences of {operation['find']!r}"
    return change


def scoped_paragraphs(editing: DocxEditing, operation: dict, location: str) -> list[Paragraph]:
    elements = [resolve_block(editing, operation["block"], f"{location}.block")] if operation.get("block") is not None else editing.elements
    return [Paragraph(paragraph_element, editing.document._body) for element in elements for paragraph_element in paragraph_elements_within(element)]


def paragraph_elements_within(element) -> list:
    if element.tag == PARAGRAPH_TAG:
        return [element]
    return list(element.iter(PARAGRAPH_TAG))


def joined_run_text(paragraph: Paragraph) -> str:
    return "".join(run.text for run in paragraph_runs(paragraph))


def replace_in_paragraph(paragraph: Paragraph, find: str, replace: str) -> int:
    count = 0
    search_start = 0
    while True:
        runs = paragraph_runs(paragraph)
        joined = "".join(run.text for run in runs)
        position = joined.find(find, search_start)
        if position < 0:
            return count
        replace_span(runs, position, position + len(find), replace)
        search_start = position + len(replace)
        count += 1


def replace_span(runs: list, start: int, end: int, replace: str) -> None:
    offset = 0
    replacement_written = False
    for run in runs:
        text = run.text
        run_start, run_end = offset, offset + len(text)
        offset = run_end
        if run_end <= start or run_start >= end:
            continue
        keep_before = text[:max(0, start - run_start)]
        keep_after = text[max(0, end - run_start):] if end < run_end else ""
        run.text = keep_before + ("" if replacement_written else replace) + keep_after
        replacement_written = True


def plan_set_text(editing: DocxEditing, operation: dict, location: str) -> Change:
    paragraph = resolve_paragraph(editing, operation["block"], f"{location}.block")

    def change() -> str:
        set_paragraph_text(paragraph, operation["text"])
        return f"set the text of block {operation['block']}"
    return change


def set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    runs = paragraph_runs(paragraph)
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for run in runs[1:]:
        run._r.getparent().remove(run._r)
    for hyperlink in paragraph._p.findall(qn("w:hyperlink")):
        if hyperlink.find(qn("w:r")) is None:
            paragraph._p.remove(hyperlink)


def plan_insert_paragraph(editing: DocxEditing, operation: dict, location: str) -> Change:
    style = operation.get("style") or "Normal"
    require_style(editing, style, (WD_STYLE_TYPE.PARAGRAPH,), f"{location}.style")
    place = placement(editing, operation, location)

    def change() -> str:
        place(editing.document.add_paragraph(operation["text"], style=style)._p)
        return f"inserted a {style} paragraph"
    return change


def plan_insert_heading(editing: DocxEditing, operation: dict, location: str) -> Change:
    level = operation.get("level") or 1
    require_style(editing, f"Heading {level}", (WD_STYLE_TYPE.PARAGRAPH,), f"{location}.level")
    place = placement(editing, operation, location)

    def change() -> str:
        place(editing.document.add_heading(operation["text"], level=level)._p)
        return f"inserted a level {level} heading"
    return change


def plan_insert_list(editing: DocxEditing, operation: dict, location: str) -> Change:
    style = "List Number" if operation.get("numbered") else "List Bullet"
    require_style(editing, style, (WD_STYLE_TYPE.PARAGRAPH,), location)
    place = placement(editing, operation, location)

    def change() -> str:
        for item in operation["items"]:
            place(editing.document.add_paragraph(item, style=style)._p)
        return f"inserted {len(operation['items'])} list items"
    return change


def plan_insert_table(editing: DocxEditing, operation: dict, location: str) -> Change:
    rows = operation["rows"]
    width = len(rows[0])
    ragged = [index for index, row in enumerate(rows) if len(row) != width]
    if width == 0 or ragged:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.rows: every row needs the header row's {width} cells", f"{location}.rows"))
    style = operation.get("style") or "Table Grid"
    require_style(editing, style, (WD_STYLE_TYPE.TABLE,), f"{location}.style")
    place = placement(editing, operation, location)

    def change() -> str:
        table = editing.document.add_table(rows=len(rows), cols=width)
        table.style = style
        for row_cells, values in zip(table.rows, rows):
            for cell, value in zip(row_cells.cells, values):
                cell.text = "" if value is None else str(value)
        place(table._tbl)
        return f"inserted a {len(rows)}x{width} table"
    return change


def plan_insert_page_break(editing: DocxEditing, operation: dict, location: str) -> Change:
    place = placement(editing, operation, location)

    def change() -> str:
        paragraph = editing.document.add_paragraph()
        paragraph.add_run().add_break(WD_BREAK.PAGE)
        place(paragraph._p)
        return "inserted a page break"
    return change


def plan_delete_block(editing: DocxEditing, operation: dict, location: str) -> Change:
    element = editing.elements[operation["block"]] if operation["block"] < len(editing.elements) else None
    if element is not None and id(element) in editing.touched:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {operation['block']} is used by another operation in this batch", location))
    element = resolve_block(editing, operation["block"], f"{location}.block")
    editing.deleted.add(id(element))

    def change() -> str:
        element.getparent().remove(element)
        return f"deleted block {operation['block']}"
    return change


def plan_set_style(editing: DocxEditing, operation: dict, location: str) -> Change:
    element = resolve_block(editing, operation["block"], f"{location}.block")
    is_table = element.tag == TABLE_TAG
    require_style(editing, operation["style"], (WD_STYLE_TYPE.TABLE,) if is_table else (WD_STYLE_TYPE.PARAGRAPH,), f"{location}.style")
    target = Table(element, editing.document._body) if is_table else Paragraph(element, editing.document._body)

    def change() -> str:
        target.style = operation["style"]
        return f"set block {operation['block']} to style {operation['style']!r}"
    return change


def plan_set_cell(editing: DocxEditing, operation: dict, location: str) -> Change:
    table = resolve_table(editing, operation["block"], f"{location}.block")
    cell = table_cell(table, operation["row"], operation["column"], location)

    def change() -> str:
        replace_cell_text(cell, operation["text"])
        return f"set cell ({operation['row']}, {operation['column']}) of block {operation['block']}"
    return change


def table_cell(table: Table, row: int, column: int, location: str):
    if row >= len(table.rows):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.row: the table has {len(table.rows)} rows", f"{location}.row"))
    cells = table.rows[row].cells
    if column >= len(cells):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.column: row {row} has {len(cells)} cells", f"{location}.column"))
    return cells[column]


def replace_cell_text(cell, text: str) -> None:
    paragraphs = cell.paragraphs
    set_paragraph_text(paragraphs[0], text)
    for paragraph in paragraphs[1:]:
        paragraph._p.getparent().remove(paragraph._p)


def plan_insert_table_row(editing: DocxEditing, operation: dict, location: str) -> Change:
    table = resolve_table(editing, operation["block"], f"{location}.block")
    if operation["after"] >= len(table.rows):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.after: the table has {len(table.rows)} rows", f"{location}.after"))
    template_row = table.rows[operation["after"]]
    if len(operation["cells"]) > len(template_row.cells):
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.cells: the row has {len(template_row.cells)} cells", f"{location}.cells"))

    def change() -> str:
        new_row_element = copy.deepcopy(template_row._tr)
        template_row._tr.addnext(new_row_element)
        new_row = table.rows[operation["after"] + 1]
        for index, cell in enumerate(new_row.cells):
            value = operation["cells"][index] if index < len(operation["cells"]) else ""
            replace_cell_text(cell, "" if value is None else str(value))
        return f"inserted a row after row {operation['after']} of block {operation['block']}"
    return change


def plan_delete_table_row(editing: DocxEditing, operation: dict, location: str) -> Change:
    table = resolve_table(editing, operation["block"], f"{location}.block")
    if operation["row"] >= len(table.rows):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.row: the table has {len(table.rows)} rows", f"{location}.row"))
    if len(table.rows) == 1:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: the table's only row cannot be deleted; delete the block instead", location))
    row_element = table.rows[operation["row"]]._tr

    def change() -> str:
        row_element.getparent().remove(row_element)
        return f"deleted row {operation['row']} of block {operation['block']}"
    return change


def plan_set_header(editing: DocxEditing, operation: dict, location: str) -> Change:
    return plan_header_or_footer(editing, operation, location, "header")


def plan_set_footer(editing: DocxEditing, operation: dict, location: str) -> Change:
    return plan_header_or_footer(editing, operation, location, "footer")


def plan_header_or_footer(editing: DocxEditing, operation: dict, location: str, part_name: str) -> Change:
    section_index = operation.get("section") or 0
    sections = editing.document.sections
    if section_index >= len(sections):
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.section: the document has {len(sections)} sections", f"{location}.section"))
    part = getattr(sections[section_index], part_name)

    def change() -> str:
        part.is_linked_to_previous = False
        paragraphs = part.paragraphs
        if not paragraphs:
            part.add_paragraph(operation["text"])
        else:
            set_paragraph_text(paragraphs[0], operation["text"])
            for paragraph in paragraphs[1:]:
                paragraph._p.getparent().remove(paragraph._p)
        return f"set the {part_name} of section {section_index}"
    return change


def plan_add_comment(editing: DocxEditing, operation: dict, location: str) -> Change:
    paragraph = resolve_paragraph(editing, operation["block"], f"{location}.block")
    if not paragraph_runs(paragraph):
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}: block {operation['block']} has no text to comment on", location))

    def change() -> str:
        editing.document.add_comment(paragraph_runs(paragraph), text=operation["text"], author=operation.get("author") or "")
        return f"commented on block {operation['block']}"
    return change


def plan_set_east_asia_font(editing: DocxEditing, operation: dict, location: str) -> Change:
    def change() -> str:
        run_fonts = default_run_fonts(editing.document)
        run_fonts.set(qn("w:eastAsia"), operation["font"])
        run_fonts.attrib.pop(qn("w:eastAsiaTheme"), None)
        return f"set the default East Asian font to {operation['font']!r}"
    return change


def default_run_fonts(document):
    styles = document.styles.element
    defaults = child_or_create(styles, "w:docDefaults", first=True)
    run_properties_default = child_or_create(defaults, "w:rPrDefault", first=True)
    run_properties = child_or_create(run_properties_default, "w:rPr", first=True)
    return child_or_create(run_properties, "w:rFonts", first=True)


def child_or_create(parent, tag: str, first: bool):
    child = parent.find(qn(tag))
    if child is not None:
        return child
    child = OxmlElement(tag)
    if first:
        parent.insert(0, child)
    else:
        parent.append(child)
    return child


def plan_update_fields_on_open(editing: DocxEditing, operation: dict, location: str) -> Change:
    def change() -> str:
        settings = editing.document.settings.element
        update_fields = settings.find(qn("w:updateFields"))
        if update_fields is None:
            update_fields = OxmlElement("w:updateFields")
            insert_before_successor(settings, update_fields)
        update_fields.set(qn("w:val"), "true")
        return "asked Word to update fields when the file opens"
    return change


def insert_before_successor(settings, element) -> None:
    successor_tags = {qn(f"w:{name}") for name in SETTINGS_AFTER_UPDATE_FIELDS}
    successor = next((child for child in settings if child.tag in successor_tags), None)
    if successor is None:
        settings.append(element)
    else:
        successor.addprevious(element)


DOCX_OPERATIONS = OperationSet(OPERATIONS, {
    "replace_text": plan_replace_text,
    "set_text": plan_set_text,
    "insert_paragraph": plan_insert_paragraph,
    "insert_heading": plan_insert_heading,
    "insert_list": plan_insert_list,
    "insert_table": plan_insert_table,
    "insert_page_break": plan_insert_page_break,
    "delete_block": plan_delete_block,
    "set_style": plan_set_style,
    "set_cell": plan_set_cell,
    "insert_table_row": plan_insert_table_row,
    "delete_table_row": plan_delete_table_row,
    "set_header": plan_set_header,
    "set_footer": plan_set_footer,
    "add_comment": plan_add_comment,
    "set_east_asia_font": plan_set_east_asia_font,
    "update_fields_on_open": plan_update_fields_on_open,
})
