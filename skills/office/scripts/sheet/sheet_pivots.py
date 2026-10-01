from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import re
from xml.sax.saxutils import quoteattr

from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from office_operations import OPERATION_NOT_APPLICABLE, Change
from office_result import INVALID_VALUE, OfficeFailure
from office_schema import closest_suggestion, did_you_mean
from workbook_access import parse_cell, parse_range, sheet_of
from workbook_package import (
    MAIN_NAMESPACE,
    RELATIONSHIP_NAMESPACE,
    WORKBOOK_PART,
    Package,
    add_content_type_override,
    add_relationship,
    main_tag,
    worksheet_parts,
)
from workbook_snapshot import cell_values


PIVOT_TABLE_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/pivotTable"
PIVOT_CACHE_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/pivotCacheDefinition"
PIVOT_RECORDS_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/pivotCacheRecords"
CONTENT_TYPE_PREFIX = "application/vnd.openxmlformats-officedocument.spreadsheetml."
FUNCTION_CAPTIONS = {"sum": "Sum", "count": "Count", "average": "Average", "max": "Max", "min": "Min"}
BUILT_IN_FORMATS = {"0": 1, "0.00": 2, "#,##0": 3, "#,##0.00": 4, "0%": 9, "0.00%": 10}
DEFAULT_NUMBER_FORMAT = "#,##0"
DEFAULT_TOTAL_LABEL = "Grand Total"
DEFAULT_TARGET_SHEET = "Pivot"
DEFAULT_TARGET_CELL = "A3"
HEADER_FILL = "DCEAF7"
RULE_COLOR = "94A3B8"
NATURAL_CHUNK = re.compile(r"(\d+)")


@dataclass
class PivotLayout:
    name: str
    source_sheet: str
    source_reference: str
    headers: list
    records: list
    row_field: int
    column_field: int | None
    value_fields: list
    function: str
    captions: list
    total_label: str
    number_format: str
    row_items: list = field(default_factory=list)
    column_items: list = field(default_factory=list)
    location: str = ""


def item_key(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()[:10] if not isinstance(value, datetime.datetime) or value.time() == datetime.time() else value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def natural_order(text: str) -> list:
    return [(0, int(chunk), "") if chunk.isdigit() else (1, 0, chunk.casefold()) for chunk in NATURAL_CHUNK.split(text) if chunk]


def distinct_items(records: list, index: int) -> list:
    return sorted({item_key(record[index]) for record in records}, key=natural_order)


def numbers(values: list) -> list:
    return [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]


def aggregate(values: list, function: str) -> float | None:
    if function == "count":
        return len([value for value in values if value is not None and value != ""])
    found = numbers(values)
    if not found:
        return None
    if function == "sum":
        return sum(found)
    if function == "average":
        return sum(found) / len(found)
    return max(found) if function == "max" else min(found)


def field_index(headers: list, name: str, location: str) -> int:
    texts = [str(header) for header in headers]
    if name in texts:
        return texts.index(name)
    raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {name!r} is not a header of the source{did_you_mean(name, texts)}; it has {', '.join(texts)}", location, closest_suggestion(name, texts)))


def pivot_names(workbook) -> set:
    return {pivot.name.casefold() for worksheet in workbook.worksheets for pivot in getattr(worksheet, "_pivots", [])}


def plan_add_pivot_table(editing, operation: dict, location: str) -> Change:
    workbook = editing.workbook
    worksheet = sheet_of(workbook, operation, location)
    bounds = parse_range(operation["range"], f"{location}.range")
    if bounds[2] <= bounds[0]:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.range: a pivot needs a header row and at least one data row", f"{location}.range"))
    headers = [cell.value for cell in next(worksheet.iter_rows(min_row=bounds[0], max_row=bounds[0], min_col=bounds[1], max_col=bounds[3]))]
    if any(header is None or str(header).strip() == "" for header in headers) or len({str(header) for header in headers}) != len(headers):
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.range: every header cell of the source needs its own name; row {bounds[0]} holds {headers}", f"{location}.range"))
    row_field = field_index(headers, operation["row"], f"{location}.row")
    column_field = field_index(headers, operation["column"], f"{location}.column") if operation.get("column") else None
    value_fields = [field_index(headers, name, f"{location}.values[{index}]") for index, name in enumerate(operation["values"])]
    if column_field is not None and len(value_fields) != 1:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.values: a pivot with a column field summarizes exactly one value", f"{location}.values"))
    captions = operation.get("valueLabels") or [f"{FUNCTION_CAPTIONS[operation.get('function', 'sum')]} of {headers[index]}" for index in value_fields]
    if len(captions) != len(value_fields):
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.valueLabels: give one caption per value, {len(value_fields)} in all", f"{location}.valueLabels"))
    target_row, target_column = parse_cell(operation.get("targetCell", DEFAULT_TARGET_CELL), f"{location}.targetCell")
    taken = pivot_names(workbook) | editing.reserved_names
    name = operation.get("name") or next(f"PivotTable{number}" for number in range(1, 10000) if f"pivottable{number}" not in taken)
    if name.casefold() in taken:
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}.name: the workbook already has a pivot table named {name!r}", f"{location}.name"))

    def change() -> str:
        records = cell_values(workbook, worksheet, (bounds[0] + 1, bounds[1], bounds[2], bounds[3]))
        layout = PivotLayout(name, worksheet.title, operation["range"].replace("$", "").upper(), [str(header) for header in headers], records, row_field, column_field, value_fields, operation.get("function", "sum"), captions, operation.get("totalLabel", DEFAULT_TOTAL_LABEL), operation.get("numberFormat", DEFAULT_NUMBER_FORMAT))
        layout.row_items = distinct_items(records, row_field)
        layout.column_items = distinct_items(records, column_field) if column_field is not None else []
        target = target_sheet(workbook, operation.get("targetSheet", DEFAULT_TARGET_SHEET))
        write_grid(target, layout, target_row, target_column, location)
        editing.reserved_names.add(name.casefold())
        editing.package_patches.append(lambda package: add_pivot_parts(package, target.title, layout))
        return f"added pivot table {name} of {worksheet.title}!{layout.source_reference} on {target.title}!{layout.location.split(':')[0]}"
    return change


def target_sheet(workbook, name: str):
    match = next((worksheet for worksheet in workbook.worksheets if worksheet.title == name), None)
    return match if match is not None else workbook.create_sheet(title=name)


def grid_rows(layout: PivotLayout) -> list[list]:
    if layout.column_field is None:
        return value_grid(layout)
    return crosstab_grid(layout)


def matching(layout: PivotLayout, record: list, row_item: str | None, column_item: str | None) -> bool:
    if row_item is not None and item_key(record[layout.row_field]) != row_item:
        return False
    return column_item is None or item_key(record[layout.column_field]) == column_item


def summary(layout: PivotLayout, value_field: int, row_item: str | None, column_item: str | None):
    return aggregate([record[value_field] for record in layout.records if matching(layout, record, row_item, column_item)], layout.function)


def value_grid(layout: PivotLayout) -> list[list]:
    rows = [[layout.headers[layout.row_field], *layout.captions]]
    for item in layout.row_items:
        rows.append([item or "(blank)", *[summary(layout, value_field, item, None) for value_field in layout.value_fields]])
    rows.append([layout.total_label, *[summary(layout, value_field, None, None) for value_field in layout.value_fields]])
    return rows


def crosstab_grid(layout: PivotLayout) -> list[list]:
    value_field = layout.value_fields[0]
    rows = [[layout.captions[0], layout.headers[layout.column_field]] + [None] * len(layout.column_items)]
    rows.append([layout.headers[layout.row_field], *[item or "(blank)" for item in layout.column_items], layout.total_label])
    for row_item in layout.row_items + [None]:
        cells = [summary(layout, value_field, row_item, column_item) for column_item in layout.column_items]
        label = layout.total_label if row_item is None else (row_item or "(blank)")
        rows.append([label, *cells, summary(layout, value_field, row_item, None)])
    return rows


def write_grid(worksheet, layout: PivotLayout, top: int, left: int, location: str) -> None:
    rows = grid_rows(layout)
    width = max(len(row) for row in rows)
    occupied = [cell.coordinate for row in worksheet.iter_rows(min_row=top, max_row=top + len(rows) - 1, min_col=left, max_col=left + width - 1) for cell in row if cell.value is not None]
    if occupied:
        raise OfficeFailure(OPERATION_NOT_APPLICABLE.issue(f"{location}.targetCell: the pivot needs {get_column_letter(left)}{top}:{get_column_letter(left + width - 1)}{top + len(rows) - 1} empty, but {worksheet.title} has values in {', '.join(occupied[:5])}", f"{location}.targetCell"))
    header_rows = 1 if layout.column_field is None else 2
    for offset, values in enumerate(rows):
        for column_offset, value in enumerate(values):
            cell = worksheet.cell(row=top + offset, column=left + column_offset, value=value)
            style_pivot_cell(cell, offset, column_offset, header_rows, len(rows), layout.number_format)
    layout.location = f"{get_column_letter(left)}{top}:{get_column_letter(left + width - 1)}{top + len(rows) - 1}"
    worksheet.column_dimensions[get_column_letter(left)].width = max(worksheet.column_dimensions[get_column_letter(left)].width or 0, 14)
    for column_offset in range(1, width):
        letter = get_column_letter(left + column_offset)
        worksheet.column_dimensions[letter].width = max(worksheet.column_dimensions[letter].width or 0, 14)


def style_pivot_cell(cell, row_offset: int, column_offset: int, header_rows: int, row_count: int, number_format: str) -> None:
    is_header = row_offset < header_rows
    is_total = row_offset == row_count - 1
    if is_header:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
    elif is_total:
        cell.font = Font(bold=True)
        cell.border = Border(top=Side(style="thin", color=RULE_COLOR))
    if not is_header and column_offset > 0:
        cell.number_format = number_format


def escaped(value: object) -> str:
    return quoteattr(str(value))


def add_pivot_parts(package: Package, target_title: str, layout: PivotLayout) -> None:
    sheet_part = next(part for part, title in worksheet_parts(package).items() if title == target_title)
    records_part = free_name(package, "xl/pivotCache/pivotCacheRecords", ".xml")
    package.add(records_part, records_xml(layout).encode("utf-8"))
    add_content_type_override(package, records_part, CONTENT_TYPE_PREFIX + "pivotCacheRecords+xml")
    cache_part = free_name(package, "xl/pivotCache/pivotCacheDefinition", ".xml")
    records_identifier = add_relationship(package, cache_part, PIVOT_RECORDS_RELATIONSHIP, records_part.rsplit("/", 1)[1])
    package.add(cache_part, cache_xml(layout, records_identifier).encode("utf-8"))
    add_content_type_override(package, cache_part, CONTENT_TYPE_PREFIX + "pivotCacheDefinition+xml")
    cache_identifier = add_relationship(package, WORKBOOK_PART, PIVOT_CACHE_RELATIONSHIP, cache_part.removeprefix("xl/"))
    cache_id = register_cache(package, cache_identifier)
    table_part = free_name(package, "xl/pivotTables/pivotTable", ".xml")
    add_relationship(package, table_part, PIVOT_CACHE_RELATIONSHIP, "../pivotCache/" + cache_part.rsplit("/", 1)[1])
    package.add(table_part, table_xml(layout, cache_id).encode("utf-8"))
    add_content_type_override(package, table_part, CONTENT_TYPE_PREFIX + "pivotTable+xml")
    add_relationship(package, sheet_part, PIVOT_TABLE_RELATIONSHIP, "../pivotTables/" + table_part.rsplit("/", 1)[1])


def free_name(package: Package, stem: str, extension: str) -> str:
    return next(f"{stem}{number}{extension}" for number in range(1, 10000) if f"{stem}{number}{extension}" not in package.entries)


def register_cache(package: Package, identifier: str) -> int:
    from lxml import etree

    root = package.xml(WORKBOOK_PART)
    caches = root.find(main_tag("pivotCaches"))
    if caches is None:
        caches = etree.Element(main_tag("pivotCaches"))
        following = next((child for child in root if etree.QName(child).localname in ("smartTagPr", "smartTagTypes", "webPublishing", "fileRecoveryPr", "webPublishObjects", "extLst")), None)
        if following is None:
            root.append(caches)
        else:
            following.addprevious(caches)
    cache_id = max([int(cache.get("cacheId")) for cache in caches] + [0]) + 1
    element = etree.SubElement(caches, main_tag("pivotCache"))
    element.set("cacheId", str(cache_id))
    element.set(f"{{{RELATIONSHIP_NAMESPACE}}}id", identifier)
    package.set_xml(WORKBOOK_PART, root)
    return cache_id


def dimension_fields(layout: PivotLayout) -> dict:
    fields = {layout.row_field: layout.row_items}
    if layout.column_field is not None:
        fields[layout.column_field] = layout.column_items
    return fields


def shared_items(values: list) -> str:
    present = [value for value in values if value is not None and value != ""]
    blank = ' containsBlank="1"' if len(present) < len(values) else ""
    found = numbers(present)
    if present and len(found) == len(present):
        integer = ' containsInteger="1"' if all(float(value).is_integer() for value in found) else ""
        return f'<sharedItems containsSemiMixedTypes="0" containsString="0" containsNumber="1"{integer}{blank} minValue="{min(found)}" maxValue="{max(found)}"/>'
    mixed = ' containsMixedTypes="1" containsNumber="1"' if found else ""
    return f"<sharedItems{mixed}{blank}/>"


def cache_xml(layout: PivotLayout, records_identifier: str) -> str:
    dimensions = dimension_fields(layout)
    fields = []
    for index, header in enumerate(layout.headers):
        if index in dimensions:
            items = "".join(f"<s v={escaped(item)}/>" if item else "<m/>" for item in dimensions[index])
            blank = ' containsBlank="1"' if "" in dimensions[index] else ""
            fields.append(f'<cacheField name={escaped(header)} numFmtId="0"><sharedItems{blank} count="{len(dimensions[index])}">{items}</sharedItems></cacheField>')
        else:
            fields.append(f'<cacheField name={escaped(header)} numFmtId="0">{shared_items([record[index] for record in layout.records])}</cacheField>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<pivotCacheDefinition xmlns="{MAIN_NAMESPACE}" xmlns:r="{RELATIONSHIP_NAMESPACE}" r:id="{records_identifier}" refreshOnLoad="1" '
        f'createdVersion="6" refreshedVersion="6" minRefreshableVersion="3" recordCount="{len(layout.records)}">'
        f'<cacheSource type="worksheet"><worksheetSource ref="{layout.source_reference}" sheet={escaped(layout.source_sheet)}/></cacheSource>'
        f'<cacheFields count="{len(fields)}">{"".join(fields)}</cacheFields></pivotCacheDefinition>'
    )


def record_value(value: object) -> str:
    if value is None or value == "":
        return "<m/>"
    if isinstance(value, bool):
        return f'<b v="{int(value)}"/>'
    if isinstance(value, (int, float)):
        return f'<n v="{value}"/>'
    return f"<s v={escaped(item_key(value))}/>"


def records_xml(layout: PivotLayout) -> str:
    dimensions = {index: {item: position for position, item in enumerate(items)} for index, items in dimension_fields(layout).items()}
    rows = []
    for record in layout.records:
        cells = [f'<x v="{dimensions[index][item_key(value)]}"/>' if index in dimensions else record_value(value) for index, value in enumerate(record)]
        rows.append(f"<r>{''.join(cells)}</r>")
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><pivotCacheRecords xmlns="{MAIN_NAMESPACE}" xmlns:r="{RELATIONSHIP_NAMESPACE}" count="{len(rows)}">{"".join(rows)}</pivotCacheRecords>'


def axis_field(axis: str, count: int) -> str:
    items = "".join(f'<item x="{index}"/>' for index in range(count))
    return f'<pivotField axis="{axis}" showAll="0"><items count="{count + 1}">{items}<item t="default"/></items></pivotField>'


def axis_items(tag: str, count: int) -> str:
    items = "".join("<i><x/></i>" if index == 0 else f'<i><x v="{index}"/></i>' for index in range(count))
    return f'<{tag} count="{count + 1}">{items}<i t="grand"><x/></i></{tag}>'


def table_xml(layout: PivotLayout, cache_id: int) -> str:
    fields = []
    for index in range(len(layout.headers)):
        if index == layout.row_field:
            fields.append(axis_field("axisRow", len(layout.row_items)))
        elif index == layout.column_field:
            fields.append(axis_field("axisCol", len(layout.column_items)))
        elif index in layout.value_fields:
            fields.append('<pivotField dataField="1" showAll="0"/>')
        else:
            fields.append('<pivotField showAll="0"/>')
    if layout.column_field is not None:
        columns = f'<colFields count="1"><field x="{layout.column_field}"/></colFields>{axis_items("colItems", len(layout.column_items))}'
        first_data_row = 2
    elif len(layout.value_fields) > 1:
        items = "".join("<i><x/></i>" if index == 0 else f'<i i="{index}"><x v="{index}"/></i>' for index in range(len(layout.value_fields)))
        columns = f'<colFields count="1"><field x="-2"/></colFields><colItems count="{len(layout.value_fields)}">{items}</colItems>'
        first_data_row = 1
    else:
        columns = '<colItems count="1"><i/></colItems>'
        first_data_row = 1
    subtotal = "" if layout.function == "sum" else f' subtotal="{layout.function}"'
    number_format = BUILT_IN_FORMATS.get(layout.number_format, 0)
    format_attribute = f' numFmtId="{number_format}"' if number_format else ""
    data_fields = "".join(f'<dataField name={escaped(caption)} fld="{index}"{subtotal} baseField="0" baseItem="0"{format_attribute}/>' for caption, index in zip(layout.captions, layout.value_fields))
    column_caption = f' colHeaderCaption={escaped(layout.headers[layout.column_field])}' if layout.column_field is not None else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<pivotTableDefinition xmlns="{MAIN_NAMESPACE}" name={escaped(layout.name)} cacheId="{cache_id}" applyNumberFormats="0" applyBorderFormats="0" '
        'applyFontFormats="0" applyPatternFormats="0" applyAlignmentFormats="0" applyWidthHeightFormats="1" dataCaption="Values" '
        f'grandTotalCaption={escaped(layout.total_label)} rowHeaderCaption={escaped(layout.headers[layout.row_field])}{column_caption} '
        'updatedVersion="6" minRefreshableVersion="3" useAutoFormatting="1" itemPrintTitles="1" createdVersion="6" indent="0" outline="1" outlineData="1" multipleFieldFilters="0">'
        f'<location ref="{layout.location}" firstHeaderRow="1" firstDataRow="{first_data_row}" firstDataCol="1"/>'
        f'<pivotFields count="{len(fields)}">{"".join(fields)}</pivotFields>'
        f'<rowFields count="1"><field x="{layout.row_field}"/></rowFields>{axis_items("rowItems", len(layout.row_items))}'
        f'{columns}<dataFields count="{len(layout.value_fields)}">{data_fields}</dataFields>'
        '<pivotTableStyleInfo name="PivotStyleLight16" showRowHeaders="1" showColHeaders="1" showRowStripes="0" showColStripes="0" showLastColumn="1"/>'
        '</pivotTableDefinition>'
    )
