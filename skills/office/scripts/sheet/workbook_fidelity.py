from __future__ import annotations

from dataclasses import dataclass, field
import copy
import posixpath

from lxml import etree

from sheet.formula_references import REFERENCE_ERROR, ROW_AXIS, Shift, deleted_sheet_reference, rename_sheet_reference, rewrite_formula, shift_reference, shift_single
from sheet.workbook_package import (
    CONTENT_TYPES_NAMESPACE,
    CONTENT_TYPES_PART,
    RELATIONSHIP_NAMESPACE,
    Package,
    add_content_type_override,
    add_relationship,
    main_tag,
    relationships,
    worksheet_parts,
)


EXCEL_MAIN_NAMESPACE = "http://schemas.microsoft.com/office/excel/2006/main"
DRAWING_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
CHART_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"
DRAWING_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/drawing"
DRAWING_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.drawing+xml"
OFFICE_DOCUMENT_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/officeDocument"
MANAGED_CONTENT_TYPE_ENDINGS = (
    "sheet.main+xml", "template.main+xml", "macroEnabled.main+xml", "worksheet+xml", "chartsheet+xml", "styles+xml",
    "sharedStrings+xml", "theme+xml", "drawing+xml", "drawingml.chart+xml", "comments+xml", "vmlDrawing", "table+xml",
    "pivotTable+xml", "pivotCacheDefinition+xml", "pivotCacheRecords+xml", "externalLink+xml", "core-properties+xml",
    "extended-properties+xml", "custom-properties+xml", "vbaProject", "calcChain+xml", "printerSettings",
    "sheetMetadata+xml", "relationships+xml", "chartstyle+xml", "chartcolorstyle+xml",
)
MANAGED_SHEET_ELEMENTS = frozenset((
    "sheetPr", "dimension", "sheetViews", "sheetFormatPr", "cols", "sheetData", "sheetProtection", "autoFilter",
    "mergeCells", "conditionalFormatting", "dataValidations", "hyperlinks", "printOptions", "pageMargins", "pageSetup",
    "headerFooter", "rowBreaks", "colBreaks", "drawing", "legacyDrawing", "tableParts", "extLst",
))
MANAGED_WORKBOOK_ELEMENTS = frozenset((
    "fileVersion", "workbookPr", "workbookProtection", "bookViews", "sheets", "definedNames", "calcPr",
    "externalReferences", "pivotCaches", "extLst",
))
CARRIED_SHEET_ELEMENTS = frozenset((
    "sheetCalcPr", "protectedRanges", "scenarios", "sortState", "dataConsolidate", "customSheetViews", "phoneticPr",
    "cellWatches", "ignoredErrors", "smartTags", "webPublishItems",
))
CARRIED_WORKBOOK_ELEMENTS = frozenset((
    "fileSharing", "functionGroups", "oleSize", "customWorkbookViews", "smartTagPr", "smartTagTypes", "webPublishing",
    "fileRecoveryPr", "webPublishObjects",
))
IGNORED_WORKBOOK_ELEMENTS = frozenset(("AlternateContent", "revisionPtr"))
WORKBOOK_ORDER = (
    "fileVersion", "fileSharing", "workbookPr", "workbookProtection", "bookViews", "sheets", "functionGroups",
    "externalReferences", "definedNames", "calcPr", "oleSize", "customWorkbookViews", "pivotCaches", "smartTagPr",
    "smartTagTypes", "webPublishing", "fileRecoveryPr", "webPublishObjects", "extLst",
)
RANGE_ATTRIBUTES = ("sqref", "ref")
WORKSHEET_ORDER = (
    "sheetPr", "dimension", "sheetViews", "sheetFormatPr", "cols", "sheetData", "sheetCalcPr", "sheetProtection",
    "protectedRanges", "scenarios", "autoFilter", "sortState", "dataConsolidate", "customSheetViews", "mergeCells",
    "phoneticPr", "conditionalFormatting", "dataValidations", "hyperlinks", "printOptions", "pageMargins", "pageSetup",
    "headerFooter", "rowBreaks", "colBreaks", "customProperties", "cellWatches", "ignoredErrors", "smartTags", "drawing",
    "legacyDrawing", "legacyDrawingHF", "drawingHF", "picture", "oleObjects", "controls", "webPublishItems", "tableParts",
    "extLst",
)
REFERENCE_ATTRIBUTES = ("id", "embed", "link", "pict")
SPREADSHEET_DRAWING_ROOT = f'<xdr:wsDr xmlns:xdr="{DRAWING_NAMESPACE}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'.encode()


@dataclass
class EditRecord:
    steps: list = field(default_factory=list)

    def shifted(self, shift: Shift) -> None:
        self.steps.append(("shift", shift))

    def renamed(self, old_name: str, new_name: str) -> None:
        self.steps.append(("rename", old_name, new_name))

    def deleted(self, title: str) -> None:
        self.steps.append(("delete", title))

    def current_title(self, title: str) -> str | None:
        for step in self.steps:
            if step[0] == "rename" and step[1].casefold() == title.casefold():
                title = step[2]
            elif step[0] == "delete" and step[1].casefold() == title.casefold():
                return None
        return title

    def rewrite_reference(self, reference: str, host: str) -> str:
        for step in self.steps:
            if step[0] == "rename":
                reference = rename_sheet_reference(reference, step[1], step[2])
                host = step[2] if host.casefold() == step[1].casefold() else host
            elif step[0] == "delete":
                reference = deleted_sheet_reference(reference, step[1])
            else:
                reference = shift_reference(reference, host, step[1])
        return reference

    def rewrite_formula_text(self, text: str, host: str) -> str:
        return rewrite_formula("=" + text, lambda reference: self.rewrite_reference(reference, host))[1:]

    def shifts_for(self, title: str) -> list[Shift]:
        shifts = []
        for step in self.steps:
            if step[0] == "rename" and step[1].casefold() == title.casefold():
                title = step[2]
            elif step[0] == "shift" and step[1].sheet.casefold() == title.casefold():
                shifts.append(step[1])
        return shifts


@dataclass
class Graft:
    source: Package
    output: Package
    record: EditRecord
    identifier_maps: dict = field(default_factory=dict)
    copied: dict = field(default_factory=dict)
    unattached_rules: dict = field(default_factory=dict)


def local_name(element) -> str:
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


def content_type(package: Package, part: str) -> str:
    root = package.xml(CONTENT_TYPES_PART)
    for override in root.iter(f"{{{CONTENT_TYPES_NAMESPACE}}}Override"):
        if override.get("PartName") == "/" + part:
            return override.get("ContentType")
    extension = posixpath.splitext(part)[1].lstrip(".").lower()
    for default in root.iter(f"{{{CONTENT_TYPES_NAMESPACE}}}Default"):
        if default.get("Extension", "").lower() == extension:
            return default.get("ContentType")
    return ""


def is_managed(package: Package, part: str) -> bool:
    kind = content_type(package, part)
    return kind.startswith("image/") or kind.endswith(MANAGED_CONTENT_TYPE_ENDINGS)


def main_part(package: Package) -> str:
    return next(relationship["part"] for relationship in relationships(package, "") if relationship["type"] == OFFICE_DOCUMENT_RELATIONSHIP)


def preserve_source_content(source: Package, output: Package, record: EditRecord) -> list[str]:
    graft = Graft(source, output, record)
    owners = owner_pairs(graft)
    for source_owner, output_owner in owners:
        graft_related_parts(graft, source_owner, output_owner)
    graft_orphan_parts(graft)
    sheets = sheet_pairs(graft)
    for pair in sheets:
        graft_elements(graft, pair.source_part, pair.output_part, CARRIED_SHEET_ELEMENTS, WORKSHEET_ORDER, pair.original_title)
        graft_rule_extensions(graft, pair)
        graft_extensions(graft, pair.source_part, pair.output_part, pair.original_title)
        graft_drawing_anchors(graft, pair)
    graft_elements(graft, main_part(source), main_part(output), CARRIED_WORKBOOK_ELEMENTS, WORKBOOK_ORDER, None)
    graft_extensions(graft, main_part(source), main_part(output), None)
    return lost_content(graft, sheets)


@dataclass(frozen=True)
class SheetPair:
    source_part: str
    output_part: str
    original_title: str
    title: str


def sheet_pairs(graft: Graft) -> list[SheetPair]:
    output_parts = {title.casefold(): part for part, title in worksheet_parts(graft.output).items()}
    pairs = []
    for part, title in worksheet_parts(graft.source).items():
        current = graft.record.current_title(title)
        if current is not None and current.casefold() in output_parts:
            pairs.append(SheetPair(part, output_parts[current.casefold()], title, current))
    return pairs


def owner_pairs(graft: Graft) -> list[tuple[str, str]]:
    pairs = [("", ""), (main_part(graft.source), main_part(graft.output))]
    return pairs + [(pair.source_part, pair.output_part) for pair in sheet_pairs(graft)]


def graft_related_parts(graft: Graft, source_owner: str, output_owner: str) -> None:
    for relationship in relationships(graft.source, source_owner):
        part = relationship["part"]
        if part is None or part not in graft.source.entries or is_managed(graft.source, part):
            continue
        if part in graft.output.entries and part not in graft.copied:
            continue
        connect(graft, source_owner, output_owner, relationship)


def connect(graft: Graft, source_owner: str, output_owner: str, relationship: dict) -> str:
    copied = copy_part(graft, relationship["part"])
    target = posixpath.relpath(copied, posixpath.dirname(output_owner) or ".") if output_owner else copied
    identifier = add_relationship(graft.output, output_owner, relationship["type"], target)
    graft.identifier_maps.setdefault(source_owner, {})[relationship["id"]] = identifier
    return identifier


def copy_part(graft: Graft, part: str) -> str:
    if part in graft.copied:
        return graft.copied[part]
    name = free_part_name(graft.output, part)
    graft.copied[part] = name
    graft.output.add(name, graft.source.entries[part])
    if content_type(graft.output, name) != content_type(graft.source, part):
        add_content_type_override(graft.output, name, content_type(graft.source, part))
    for relationship in relationships(graft.source, part):
        if relationship["part"] is None:
            add_relationship(graft.output, name, relationship["type"], relationship["target"])
            continue
        if relationship["part"] in graft.source.entries:
            connect(graft, part, name, relationship)
    return name


def free_part_name(package: Package, part: str) -> str:
    if part not in package.entries:
        return part
    stem, extension = posixpath.splitext(part)
    return next(f"{stem}_{number}{extension}" for number in range(2, 10000) if f"{stem}_{number}{extension}" not in package.entries)


def graft_orphan_parts(graft: Graft) -> None:
    related = {relationship["part"] for owner in [""] + list(graft.source.entries) if owner.endswith(".xml") or owner == "" for relationship in relationships(graft.source, owner)}
    for part in list(graft.source.entries):
        if part.endswith(".rels") or part == CONTENT_TYPES_PART or part in related or part in graft.output.entries or is_managed(graft.source, part):
            continue
        copy_part(graft, part)


def graft_elements(graft: Graft, source_part: str, output_part: str, carried: frozenset, order: tuple, title: str | None) -> None:
    root = graft.output.xml(output_part)
    present = {local_name(child) for child in root}
    elements = [child for child in graft.source.xml(source_part) if local_name(child) in carried and local_name(child) not in present]
    if not elements:
        return
    for element in elements:
        grafted = copy.deepcopy(element)
        if title is not None:
            rewrite_range_attributes(grafted, title, graft.record)
        insert_in_order(root, grafted, order)
    graft.output.set_xml(output_part, root)


def rewrite_range_attributes(element, original: str, record: EditRecord) -> None:
    if not record.steps:
        return
    for node in element.iter():
        for attribute in RANGE_ATTRIBUTES:
            if node.get(attribute):
                ranges = [record.rewrite_reference(reference, original) for reference in node.get(attribute).split()]
                node.set(attribute, " ".join(reference for reference in ranges if REFERENCE_ERROR not in reference) or node.get(attribute))


def rule_key(formatting, rule, title: str, record: EditRecord) -> tuple:
    ranges = " ".join(record.rewrite_reference(reference, title) for reference in (formatting.get("sqref") or "").split())
    return ranges, rule.get("type"), rule.get("priority")


def graft_rule_extensions(graft: Graft, pair: SheetPair) -> None:
    source_rules = {
        rule_key(formatting, rule, pair.original_title, graft.record): rule.find(main_tag("extLst"))
        for formatting in graft.source.xml(pair.source_part).iter(main_tag("conditionalFormatting"))
        for rule in formatting.iter(main_tag("cfRule"))
        if rule.find(main_tag("extLst")) is not None
    }
    if not source_rules:
        return
    root = graft.output.xml(pair.output_part)
    attached = set()
    for formatting in root.iter(main_tag("conditionalFormatting")):
        for rule in formatting.iter(main_tag("cfRule")):
            key = rule_key(formatting, rule, pair.original_title, EditRecord())
            if key in source_rules and rule.find(main_tag("extLst")) is None:
                rule.append(copy.deepcopy(source_rules[key]))
                attached.add(key)
    graft.output.set_xml(pair.output_part, root)
    graft.unattached_rules[pair.title] = sum(1 for key in source_rules if key not in attached and key[0] and REFERENCE_ERROR not in key[0])


def graft_extensions(graft: Graft, source_part: str, output_part: str, title: str | None) -> None:
    source_extensions = graft.source.xml(source_part).find(main_tag("extLst"))
    if source_extensions is None:
        return
    root = graft.output.xml(output_part)
    target = root.find(main_tag("extLst"))
    if target is None:
        target = etree.SubElement(root, main_tag("extLst"))
    existing = {extension.get("uri"): extension for extension in target}
    for extension in source_extensions:
        grafted = copy.deepcopy(extension)
        remap_identifiers(grafted, graft.identifier_maps.get(source_part, {}))
        if title is not None:
            rewrite_extension_references(grafted, title, graft.record)
        merge_extension(target, existing.get(grafted.get("uri")), grafted)
    graft.output.set_xml(output_part, root)


def merge_extension(target, existing, grafted) -> None:
    if existing is None or len(existing) == 0 or len(grafted) == 0:
        target.append(grafted)
        return
    for child in grafted[0]:
        existing[0].append(child)


def remap_identifiers(element, identifiers: dict) -> None:
    for node in element.iter():
        for attribute in list(node.attrib):
            qualified = etree.QName(attribute)
            if qualified.namespace == RELATIONSHIP_NAMESPACE and qualified.localname in REFERENCE_ATTRIBUTES and node.get(attribute) in identifiers:
                node.set(attribute, identifiers[node.get(attribute)])


def rewrite_extension_references(element, original: str, record: EditRecord) -> None:
    if not record.steps:
        return
    for node in list(element.iter(f"{{{EXCEL_MAIN_NAMESPACE}}}f")):
        node.text = record.rewrite_formula_text(node.text or "", original)
    for node in list(element.iter(f"{{{EXCEL_MAIN_NAMESPACE}}}sqref")):
        ranges = [record.rewrite_reference(reference, original) for reference in (node.text or "").split()]
        kept = [reference for reference in ranges if REFERENCE_ERROR not in reference]
        if kept:
            node.text = " ".join(kept)
        elif node.getparent() is not None and node.getparent().getparent() is not None:
            node.getparent().getparent().remove(node.getparent())


def drawing_part(package: Package, sheet_part: str) -> str | None:
    return next((relationship["part"] for relationship in relationships(package, sheet_part) if relationship["type"] == DRAWING_RELATIONSHIP), None)


def is_carried_anchor(anchor) -> bool:
    if local_name(anchor) == "AlternateContent":
        return False
    content = [child for child in anchor if local_name(child) not in ("from", "to", "pos", "ext", "clientData")]
    if not content:
        return True
    kind = local_name(content[0])
    if kind == "pic":
        return True
    if kind == "graphicFrame":
        data = next(content[0].iter("{http://schemas.openxmlformats.org/drawingml/2006/main}graphicData"), None)
        return data is not None and data.get("uri") == CHART_URI
    return False


def graft_drawing_anchors(graft: Graft, pair: SheetPair) -> None:
    source_drawing = drawing_part(graft.source, pair.source_part)
    if source_drawing is None or source_drawing not in graft.source.entries:
        return
    anchors = [anchor for anchor in graft.source.xml(source_drawing) if not is_carried_anchor(anchor)]
    if not anchors:
        return
    output_drawing = drawing_part(graft.output, pair.output_part) or create_drawing(graft.output, pair.output_part)
    shifts = graft.record.shifts_for(pair.original_title)
    root = graft.output.xml(output_drawing)
    for anchor in anchors:
        grafted = copy.deepcopy(anchor)
        remap_identifiers(grafted, anchor_identifiers(graft, source_drawing, output_drawing, grafted))
        for shift in shifts:
            shift_anchor(grafted, shift)
        root.append(grafted)
    graft.output.set_xml(output_drawing, root)


def anchor_identifiers(graft: Graft, source_drawing: str, output_drawing: str, anchor) -> dict:
    wanted = {node.get(attribute) for node in anchor.iter() for attribute in node.attrib if etree.QName(attribute).namespace == RELATIONSHIP_NAMESPACE}
    identifiers = {}
    for relationship in relationships(graft.source, source_drawing):
        if relationship["id"] not in wanted:
            continue
        if relationship["part"] is None:
            identifiers[relationship["id"]] = add_relationship(graft.output, output_drawing, relationship["type"], relationship["target"])
        elif relationship["part"] in graft.source.entries:
            identifiers[relationship["id"]] = connect(graft, source_drawing, output_drawing, relationship)
    return identifiers


def create_drawing(package: Package, sheet_part: str) -> str:
    name = free_part_name(package, "xl/drawings/drawing1.xml")
    package.add(name, SPREADSHEET_DRAWING_ROOT)
    add_content_type_override(package, name, DRAWING_CONTENT_TYPE)
    identifier = add_relationship(package, sheet_part, DRAWING_RELATIONSHIP, posixpath.relpath(name, posixpath.dirname(sheet_part)))
    root = package.xml(sheet_part)
    element = etree.Element(main_tag("drawing"))
    element.set(f"{{{RELATIONSHIP_NAMESPACE}}}id", identifier)
    insert_in_order(root, element, WORKSHEET_ORDER)
    package.set_xml(sheet_part, root)
    return name


def insert_in_order(root, element, order: tuple) -> None:
    position = order.index(local_name(element))
    later = next((child for child in root if local_name(child) in order and order.index(local_name(child)) > position), None)
    if later is None:
        root.append(element)
    else:
        later.addprevious(element)


def shift_anchor(anchor, shift: Shift) -> None:
    tag = "row" if shift.axis == ROW_AXIS else "col"
    for marker in ("from", "to"):
        node = anchor.find(f"{{{DRAWING_NAMESPACE}}}{marker}/{{{DRAWING_NAMESPACE}}}{tag}")
        if node is None:
            continue
        moved = shift_single(int(node.text) + 1, shift)
        node.text = str((moved if moved is not None else shift.at) - 1)


def element_names(package: Package, part: str) -> set:
    return {local_name(child) for child in package.xml(part)}


def extension_uris(package: Package, part: str) -> set:
    extensions = package.xml(part).find(main_tag("extLst"))
    return set() if extensions is None else {extension.get("uri") for extension in extensions}


def uncarried_anchor_count(package: Package, sheet_part: str) -> int:
    part = drawing_part(package, sheet_part)
    if part is None or part not in package.entries:
        return 0
    return sum(1 for anchor in package.xml(part) if not is_carried_anchor(anchor))


def lost_content(graft: Graft, sheets: list[SheetPair]) -> list[str]:
    source, output = graft.source, graft.output
    lost = []
    for pair in sheets:
        for name in sorted(element_names(source, pair.source_part) - MANAGED_SHEET_ELEMENTS - element_names(output, pair.output_part)):
            lost.append(f"{pair.title}: <{name}>")
        if extension_uris(source, pair.source_part) - extension_uris(output, pair.output_part):
            lost.append(f"{pair.title}: worksheet extensions")
        if uncarried_anchor_count(output, pair.output_part) < uncarried_anchor_count(source, pair.source_part):
            lost.append(f"{pair.title}: drawing shapes")
        if graft.unattached_rules.get(pair.title):
            lost.append(f"{pair.title}: conditional format extensions")
    workbook_source, workbook_output = main_part(source), main_part(output)
    for name in sorted(element_names(source, workbook_source) - MANAGED_WORKBOOK_ELEMENTS - IGNORED_WORKBOOK_ELEMENTS - element_names(output, workbook_output)):
        lost.append(f"workbook: <{name}>")
    discarded = deleted_sheet_parts(graft)
    for part in sorted(source.entries):
        if part.endswith(".rels") or part == CONTENT_TYPES_PART or is_managed(source, part) or part in graft.copied or part in discarded:
            continue
        lost.append(f"part {part}")
    return lost


def deleted_sheet_parts(graft: Graft) -> set[str]:
    pending = [part for part, title in worksheet_parts(graft.source).items() if graft.record.current_title(title) is None]
    reached = set()
    while pending:
        part = pending.pop()
        if part in reached:
            continue
        reached.add(part)
        pending.extend(relationship["part"] for relationship in relationships(graft.source, part) if relationship["part"] in graft.source.entries)
    return reached
