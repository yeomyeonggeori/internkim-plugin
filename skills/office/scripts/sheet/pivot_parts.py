from __future__ import annotations

from dataclasses import dataclass
import datetime
from xml.sax.saxutils import quoteattr

from lxml import etree
from openpyxl.styles.numbers import BUILTIN_FORMATS_REVERSE

from sheet.pivot_layout import DATE_UNITS, DateGroup, PivotAxis, PivotField, PivotModel, as_datetime, item_key, numbers, shown_number
from sheet.workbook_package import (
    MAIN_NAMESPACE,
    RELATIONSHIP_NAMESPACE,
    WORKBOOK_PART,
    Package,
    add_content_type_override,
    add_relationship,
    main_tag,
    worksheet_parts,
)


PIVOT_TABLE_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/pivotTable"
PIVOT_CACHE_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/pivotCacheDefinition"
PIVOT_RECORDS_RELATIONSHIP = f"{RELATIONSHIP_NAMESPACE}/pivotCacheRecords"
CONTENT_TYPE_PREFIX = "application/vnd.openxmlformats-officedocument.spreadsheetml."
SHOW_DATA_AS = {"percent_of_total": "percentOfTotal", "percent_of_row": "percentOfRow", "percent_of_column": "percentOfCol"}
SHORT_DATE_FORMAT_ID = 14
VALUES_FIELD = -2
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


@dataclass
class PivotPlacement:
    name: str
    source_sheet: str
    source_reference: str
    location: str
    first_data_row: int


def escaped(value: object) -> str:
    return quoteattr(str(value))


def stamp(moment: datetime.datetime) -> str:
    return moment.replace(microsecond=0).isoformat()


def axis_fields(model: PivotModel) -> dict[int, PivotField]:
    return {pivot_field.index: pivot_field for pivot_field in [*model.rows.fields, *model.columns.fields, *model.pages]}


def calculated_values(model: PivotModel) -> list:
    return [value for value in model.values if value.formula is not None]


def add_pivot_parts(package: Package, target_title: str, model: PivotModel, placement: PivotPlacement) -> None:
    sheet_part = next(part for part, title in worksheet_parts(package).items() if title == target_title)
    records_part = free_name(package, "xl/pivotCache/pivotCacheRecords", ".xml")
    package.add(records_part, records_xml(model).encode("utf-8"))
    add_content_type_override(package, records_part, CONTENT_TYPE_PREFIX + "pivotCacheRecords+xml")
    cache_part = free_name(package, "xl/pivotCache/pivotCacheDefinition", ".xml")
    records_identifier = add_relationship(package, cache_part, PIVOT_RECORDS_RELATIONSHIP, records_part.rsplit("/", 1)[1])
    package.add(cache_part, cache_xml(model, placement, records_identifier).encode("utf-8"))
    add_content_type_override(package, cache_part, CONTENT_TYPE_PREFIX + "pivotCacheDefinition+xml")
    cache_identifier = add_relationship(package, WORKBOOK_PART, PIVOT_CACHE_RELATIONSHIP, cache_part.removeprefix("xl/"))
    cache_id = register_cache(package, cache_identifier)
    table_part = free_name(package, "xl/pivotTables/pivotTable", ".xml")
    add_relationship(package, table_part, PIVOT_CACHE_RELATIONSHIP, "../pivotCache/" + cache_part.rsplit("/", 1)[1])
    package.add(table_part, table_xml(model, placement, cache_id, number_format_ids(package)).encode("utf-8"))
    add_content_type_override(package, table_part, CONTENT_TYPE_PREFIX + "pivotTable+xml")
    add_relationship(package, sheet_part, PIVOT_TABLE_RELATIONSHIP, "../pivotTables/" + table_part.rsplit("/", 1)[1])


def free_name(package: Package, stem: str, extension: str) -> str:
    return next(f"{stem}{number}{extension}" for number in range(1, 10000) if f"{stem}{number}{extension}" not in package.entries)


def register_cache(package: Package, identifier: str) -> int:
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


def number_format_ids(package: Package) -> dict[str, int]:
    found = dict(BUILTIN_FORMATS_REVERSE)
    if "xl/styles.xml" not in package.entries:
        return found
    for element in package.xml("xl/styles.xml").iter(main_tag("numFmt")):
        found[element.get("formatCode")] = int(element.get("numFmtId"))
    return found


def is_date(value: object) -> bool:
    return as_datetime(value) is not None


def holds_only_dates(values: list) -> bool:
    present = [value for value in values if value is not None and value != ""]
    return bool(present) and all(is_date(value) for value in present)


def shared_items(values: list) -> str:
    present = [value for value in values if value is not None and value != ""]
    blank = ' containsBlank="1"' if len(present) < len(values) else ""
    found = numbers(present)
    if present and len(found) == len(present):
        integer = ' containsInteger="1"' if all(float(value).is_integer() for value in found) else ""
        return f'<sharedItems containsSemiMixedTypes="0" containsString="0" containsNumber="1"{integer}{blank} minValue="{min(found)}" maxValue="{max(found)}"/>'
    if holds_only_dates(present):
        dates = [as_datetime(value) for value in present]
        return f'<sharedItems containsSemiMixedTypes="0" containsNonDate="0" containsDate="1" containsString="0"{blank} minDate="{stamp(min(dates))}" maxDate="{stamp(max(dates))}"/>'
    mixed = ' containsMixedTypes="1" containsNumber="1"' if found else ""
    return f"<sharedItems{mixed}{blank}/>"


def grouped_cache_field(header: str, index: int, pivot_field: PivotField, values: list) -> str:
    group = pivot_field.group
    items = "".join(f"<s v={escaped(item)}/>" for item in group.items)
    return (
        f'<cacheField name={escaped(header)} numFmtId="{group_format_id(pivot_field)}">{shared_items(values)}'
        f'<fieldGroup base="{index}">{range_xml(group)}'
        f'<groupItems count="{len(group.items)}">{items}</groupItems></fieldGroup></cacheField>'
    )


def range_xml(group) -> str:
    if isinstance(group, DateGroup):
        return f'<rangePr groupBy="{DATE_UNITS[group.unit]}" startDate="{stamp(group.start)}" endDate="{stamp(group.end)}"/>'
    return f'<rangePr autoStart="0" startNum="{shown_number(group.start)}" endNum="{shown_number(group.end)}" groupInterval="{shown_number(group.step)}"/>'


def group_format_id(pivot_field: PivotField) -> int:
    return SHORT_DATE_FORMAT_ID if isinstance(pivot_field.group, DateGroup) else 0


def listed_cache_field(header: str, pivot_field: PivotField) -> str:
    items = "".join(f"<s v={escaped(item)}/>" if item else "<m/>" for item in pivot_field.items)
    blank = ' containsBlank="1"' if "" in pivot_field.items else ""
    return f'<cacheField name={escaped(header)} numFmtId="0"><sharedItems{blank} count="{len(pivot_field.items)}">{items}</sharedItems></cacheField>'


def cache_field(model: PivotModel, index: int, header: str, dimensions: dict[int, PivotField]) -> str:
    values = [record[index] for record in model.records]
    pivot_field = dimensions.get(index)
    if pivot_field is None:
        format_id = SHORT_DATE_FORMAT_ID if holds_only_dates(values) else 0
        return f'<cacheField name={escaped(header)} numFmtId="{format_id}">{shared_items(values)}</cacheField>'
    if pivot_field.group is not None:
        return grouped_cache_field(header, index, pivot_field, values)
    return listed_cache_field(header, pivot_field)


def cache_xml(model: PivotModel, placement: PivotPlacement, records_identifier: str) -> str:
    dimensions = axis_fields(model)
    fields = [cache_field(model, index, header, dimensions) for index, header in enumerate(model.headers)]
    fields += [f'<cacheField name={escaped(value.calculated_name)} numFmtId="0" formula={escaped(value.formula.text)} databaseField="0"/>' for value in calculated_values(model)]
    return (
        XML_DECLARATION
        + f'<pivotCacheDefinition xmlns="{MAIN_NAMESPACE}" xmlns:r="{RELATIONSHIP_NAMESPACE}" r:id="{records_identifier}" refreshOnLoad="1" '
        f'createdVersion="6" refreshedVersion="6" minRefreshableVersion="3" recordCount="{len(model.records)}">'
        f'<cacheSource type="worksheet"><worksheetSource ref="{placement.source_reference}" sheet={escaped(placement.source_sheet)}/></cacheSource>'
        f'<cacheFields count="{len(fields)}">{"".join(fields)}</cacheFields></pivotCacheDefinition>'
    )


def record_value(value: object) -> str:
    if value is None or value == "":
        return "<m/>"
    if isinstance(value, bool):
        return f'<b v="{int(value)}"/>'
    if isinstance(value, (int, float)):
        return f'<n v="{value}"/>'
    if is_date(value):
        return f'<d v="{stamp(as_datetime(value))}"/>'
    return f"<s v={escaped(item_key(value))}/>"


def record_cell(dimensions: dict[int, PivotField], index: int, record_index: int, value: object) -> str:
    pivot_field = dimensions.get(index)
    if pivot_field is None or pivot_field.group is not None:
        return record_value(value)
    return f'<x v="{pivot_field.members[record_index]}"/>'


def records_xml(model: PivotModel) -> str:
    dimensions = axis_fields(model)
    rows = [f"<r>{''.join(record_cell(dimensions, index, position, value) for index, value in enumerate(record))}</r>" for position, record in enumerate(model.records)]
    return XML_DECLARATION + f'<pivotCacheRecords xmlns="{MAIN_NAMESPACE}" xmlns:r="{RELATIONSHIP_NAMESPACE}" count="{len(rows)}">{"".join(rows)}</pivotCacheRecords>'


def layout_attributes(is_tabular: bool) -> str:
    return ' compact="0" outline="0"' if is_tabular else ""


def item_list(pivot_field: PivotField) -> str:
    items = "".join(f'<item x="{index}"/>' for index in range(len(pivot_field.items)))
    return f'<items count="{len(pivot_field.items) + 1}">{items}<item t="default"/></items>'


def pivot_field_xml(model: PivotModel, index: int, is_tabular: bool) -> str:
    attributes = layout_attributes(is_tabular)
    if any(value.field == index for value in model.values):
        attributes = ' dataField="1"' + attributes
    for axis_name, fields in (("axisRow", model.rows.fields), ("axisCol", model.columns.fields), ("axisPage", model.pages)):
        pivot_field = next((candidate for candidate in fields if candidate.index == index), None)
        if pivot_field is not None:
            number_format = f' numFmtId="{SHORT_DATE_FORMAT_ID}"' if isinstance(pivot_field.group, DateGroup) else ""
            return f'<pivotField axis="{axis_name}"{attributes}{number_format} showAll="0">{item_list(pivot_field)}</pivotField>'
    return f'<pivotField{attributes} showAll="0"/>'


def axis_items_xml(axis: PivotAxis, tag: str) -> str:
    parts = []
    carried: tuple = ()
    for line in axis.lines:
        repeat = 0
        while repeat < len(line.members) - 1 and repeat < len(carried) and carried[repeat] == line.members[repeat]:
            repeat += 1
        members = "".join("<x/>" if member == 0 else f'<x v="{member}"/>' for member in line.members[repeat:])
        repeat_attribute = f' r="{repeat}"' if repeat else ""
        kind = ' t="default"' if line.is_subtotal else ""
        parts.append(f"<i{repeat_attribute}{kind}>{members}</i>")
        carried = line.members
    return f'<{tag} count="{len(axis.lines) + 1}">{"".join(parts)}<i t="grand"><x/></i></{tag}>'


def column_part(model: PivotModel) -> str:
    if model.columns.depth:
        fields = "".join(f'<field x="{pivot_field.index}"/>' for pivot_field in model.columns.fields)
        return f'<colFields count="{model.columns.depth}">{fields}</colFields>{axis_items_xml(model.columns, "colItems")}'
    if len(model.values) > 1:
        items = "".join("<i><x/></i>" if index == 0 else f'<i i="{index}"><x v="{index}"/></i>' for index in range(len(model.values)))
        return f'<colFields count="1"><field x="{VALUES_FIELD}"/></colFields><colItems count="{len(model.values)}">{items}</colItems>'
    return '<colItems count="1"><i/></colItems>'


def page_part(model: PivotModel) -> str:
    if not model.pages:
        return ""
    fields = "".join(f'<pageField fld="{pivot_field.index}" hier="-1"/>' for pivot_field in model.pages)
    return f'<pageFields count="{len(model.pages)}">{fields}</pageFields>'


def data_field_xml(model: PivotModel, value, format_ids: dict[str, int]) -> str:
    calculated = calculated_values(model)
    field_index = len(model.headers) + calculated.index(value) if value.formula is not None else value.field
    subtotal = "" if value.function == "sum" else f' subtotal="{value.function}"'
    show_as = f' showDataAs="{SHOW_DATA_AS[value.show_as]}"' if value.show_as in SHOW_DATA_AS else ""
    format_id = format_ids.get(value.number_format, 0)
    format_attribute = f' numFmtId="{format_id}"' if format_id else ""
    return f'<dataField name={escaped(value.caption)} fld="{field_index}"{subtotal}{show_as} baseField="0" baseItem="0"{format_attribute}/>'


def table_attributes(model: PivotModel, is_tabular: bool) -> str:
    captions = f"grandTotalCaption={escaped(model.total_label)}"
    if not is_tabular:
        captions += f" rowHeaderCaption={escaped(model.headers[model.rows.fields[0].index])}"
        if model.columns.depth == 1:
            captions += f" colHeaderCaption={escaped(model.headers[model.columns.fields[0].index])}"
    layout = 'compact="0" compactData="0" outline="0" outlineData="0"' if is_tabular else 'outline="1" outlineData="1"'
    return f'{captions} updatedVersion="6" minRefreshableVersion="3" useAutoFormatting="1" itemPrintTitles="1" createdVersion="6" indent="0" {layout} multipleFieldFilters="0"'


def location_xml(model: PivotModel, placement: PivotPlacement) -> str:
    pages = f' rowPageCount="{len(model.pages)}" colPageCount="1"' if model.pages else ""
    return f'<location ref="{placement.location}" firstHeaderRow="1" firstDataRow="{placement.first_data_row}" firstDataCol="{model.rows.depth}"{pages}/>'


def table_xml(model: PivotModel, placement: PivotPlacement, cache_id: int, format_ids: dict[str, int]) -> str:
    is_tabular = model.rows.depth > 1
    calculated_fields = "".join(f'<pivotField dataField="1"{layout_attributes(is_tabular)} dragToRow="0" dragToCol="0" dragToPage="0" showAll="0" defaultSubtotal="0"/>' for _ in calculated_values(model))
    fields = "".join(pivot_field_xml(model, index, is_tabular) for index in range(len(model.headers))) + calculated_fields
    field_count = len(model.headers) + len(calculated_values(model))
    row_fields = "".join(f'<field x="{pivot_field.index}"/>' for pivot_field in model.rows.fields)
    data_fields = "".join(data_field_xml(model, value, format_ids) for value in model.values)
    return (
        XML_DECLARATION
        + f'<pivotTableDefinition xmlns="{MAIN_NAMESPACE}" name={escaped(placement.name)} cacheId="{cache_id}" applyNumberFormats="0" applyBorderFormats="0" '
        'applyFontFormats="0" applyPatternFormats="0" applyAlignmentFormats="0" applyWidthHeightFormats="1" dataCaption="Values" '
        f'{table_attributes(model, is_tabular)}>'
        f'{location_xml(model, placement)}'
        f'<pivotFields count="{field_count}">{fields}</pivotFields>'
        f'<rowFields count="{model.rows.depth}">{row_fields}</rowFields>{axis_items_xml(model.rows, "rowItems")}'
        f'{column_part(model)}{page_part(model)}<dataFields count="{len(model.values)}">{data_fields}</dataFields>'
        '<pivotTableStyleInfo name="PivotStyleLight16" showRowHeaders="1" showColHeaders="1" showRowStripes="0" showColStripes="0" showLastColumn="1"/>'
        f'{filters_xml(model)}</pivotTableDefinition>'
    )


def filters_xml(model: PivotModel) -> str:
    if model.top is None:
        return ""
    direction = ' top="0"' if model.top.bottom else ""
    return (
        f'<filters count="1"><filter fld="{model.top.field}" type="count" evalOrder="-1" id="1" iMeasureFld="0">'
        f'<autoFilter ref="A1"><filterColumn colId="0"><top10{direction} val="{model.top.count}" filterVal="{model.top.count}"/></filterColumn></autoFilter>'
        '</filter></filters>'
    )
