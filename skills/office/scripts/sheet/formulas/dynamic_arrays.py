from __future__ import annotations

from lxml import etree
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string

from sheet.workbook.package import MAIN_NAMESPACE, WORKBOOK_PART, Package, add_content_type_override, add_relationship, main_tag, relationships


METADATA_PART = "xl/metadata.xml"
METADATA_RELATIONSHIP = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sheetMetadata"
METADATA_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml"
DYNAMIC_ARRAY_NAMESPACE = "http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray"
DYNAMIC_ARRAY_EXTENSION = "{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}"
DYNAMIC_ARRAY_TYPE = "XLDAPR"
DYNAMIC_ARRAY_METADATA = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<metadata xmlns="{MAIN_NAMESPACE}" xmlns:xda="{DYNAMIC_ARRAY_NAMESPACE}">'
    f'<metadataTypes count="1"><metadataType name="{DYNAMIC_ARRAY_TYPE}" minSupportedVersion="120000" copy="1" pasteAll="1" pasteValues="1" merge="1" splitFirst="1" rowColShift="1" clearFormats="1" clearComments="1" assign="1" coerce="1" cellMeta="1"/></metadataTypes>'
    f'<futureMetadata name="{DYNAMIC_ARRAY_TYPE}" count="1"><bk><extLst><ext uri="{DYNAMIC_ARRAY_EXTENSION}"><xda:dynamicArrayProperties fDynamic="1" fCollapsed="0"/></ext></extLst></bk></futureMetadata>'
    f'<cellMetadata count="1"><bk><rc t="1" v="0"/></bk></cellMetadata></metadata>'
).encode("utf-8")


def metadata_part(package: Package) -> str | None:
    return next((relationship["part"] for relationship in relationships(package, WORKBOOK_PART) if relationship["type"] == METADATA_RELATIONSHIP), None)


def dynamic_array_cell_metadata(package: Package) -> str:
    part = metadata_part(package)
    if part is None or part not in package.entries:
        package.add(METADATA_PART, DYNAMIC_ARRAY_METADATA)
        add_relationship(package, WORKBOOK_PART, METADATA_RELATIONSHIP, "metadata.xml")
        add_content_type_override(package, METADATA_PART, METADATA_CONTENT_TYPE)
        return "1"
    return existing_dynamic_array_index(package, part)


def existing_dynamic_array_index(package: Package, part: str) -> str:
    root = package.xml(part)
    types = [element.get("name") for element in root.iter(main_tag("metadataType"))]
    if DYNAMIC_ARRAY_TYPE in types:
        type_index = types.index(DYNAMIC_ARRAY_TYPE) + 1
        cell_metadata = root.find(main_tag("cellMetadata"))
        blocks = [] if cell_metadata is None else cell_metadata.findall(main_tag("bk"))
        for position, block in enumerate(blocks, 1):
            record = block.find(main_tag("rc"))
            if record is not None and record.get("t") == str(type_index):
                return str(position)
    package.add(part, DYNAMIC_ARRAY_METADATA)
    return "1"


def row_element(sheet_data, row_number: int):
    rows = sheet_data.findall(main_tag("row"))
    for row in rows:
        number = int(row.get("r"))
        if number == row_number:
            return row
        if number > row_number:
            created = etree.Element(main_tag("row"), r=str(row_number))
            row.addprevious(created)
            return created
    return etree.SubElement(sheet_data, main_tag("row"), r=str(row_number))


def cell_element(sheet_root, coordinate: str):
    column_letters, row_number = coordinate_from_string(coordinate)
    column = column_index_from_string(column_letters)
    row = row_element(sheet_root.find(main_tag("sheetData")), row_number)
    for cell in row.findall(main_tag("c")):
        existing_letters, _ = coordinate_from_string(cell.get("r"))
        existing = column_index_from_string(existing_letters)
        if existing == column:
            return cell
        if existing > column:
            created = etree.Element(main_tag("c"), r=coordinate)
            cell.addprevious(created)
            return created
    return etree.SubElement(row, main_tag("c"), r=coordinate)


def mark_array_formula(cell, reference: str, cell_metadata: str | None) -> None:
    formula = cell.find(main_tag("f"))
    formula.set("t", "array")
    formula.set("ref", reference)
    for attribute in ("si", "aca", "ca"):
        formula.attrib.pop(attribute, None)
    if cell_metadata is not None:
        cell.set("cm", cell_metadata)
