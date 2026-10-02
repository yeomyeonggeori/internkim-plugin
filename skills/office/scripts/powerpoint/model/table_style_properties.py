from __future__ import annotations

from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement

from powerpoint.model.style import TRUE_VALUES
from powerpoint.model.table_styles import DEFAULT_TABLE_STYLE, PART_FLAGS, TABLE_STYLES, TableStyle


def style_named(name: str) -> TableStyle:
    return next(style for style in TABLE_STYLES if style.name == name)


def style_of(table_properties) -> TableStyle | None:
    identifier = table_style_identifier(table_properties)
    if identifier is None:
        return DEFAULT_TABLE_STYLE
    return next((style for style in TABLE_STYLES if style.identifier.upper() == identifier.upper()), None)


def table_style_identifier(table_properties) -> str | None:
    if table_properties is None:
        return None
    identifier = table_properties.find(qn("a:tableStyleId"))
    return identifier.text.strip() if identifier is not None and identifier.text else None


def part_flags(table_properties) -> dict[str, bool]:
    return {name: table_properties is not None and table_properties.get(name) in TRUE_VALUES for name in PART_FLAGS}


def set_table_style(table_properties, style: TableStyle) -> None:
    identifier = table_properties.find(qn("a:tableStyleId"))
    if identifier is None:
        identifier = OxmlElement("a:tableStyleId")
        table_properties.insert_element_before(identifier, "a:extLst")
    identifier.text = style.identifier


def described_style(table_properties) -> dict:
    style = style_of(table_properties)
    name = style.name if style is not None else table_style_identifier(table_properties)
    return {"style": name, "styleParts": [flag for flag, shown in part_flags(table_properties).items() if shown]}
