from __future__ import annotations

from dataclasses import dataclass


MEDIUM_FAMILY = "medium"
GRID_FAMILY = "grid"
PLAIN_FAMILY = "plain"
TEXT_SLOT = "dk1"
PART_FLAGS = ("firstRow", "lastRow", "firstCol", "lastCol", "bandRow", "bandCol")


@dataclass(frozen=True)
class TableStyle:
    name: str
    identifier: str
    family: str
    color_slot: str


# Built-in table style GUIDs as Microsoft lists them in "Table Style GUIDs" (Open Specifications, hh273476)
TABLE_STYLES = (
    TableStyle("Medium Style 2", "{073A0DAA-6AF3-43AB-8588-CEC1D06C72B9}", MEDIUM_FAMILY, TEXT_SLOT),
    TableStyle("Medium Style 2 - Accent 1", "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}", MEDIUM_FAMILY, "accent1"),
    TableStyle("Medium Style 2 - Accent 2", "{21E4AEA4-8DFA-4A89-87EB-49C32662AFE0}", MEDIUM_FAMILY, "accent2"),
    TableStyle("Medium Style 2 - Accent 3", "{F5AB1C69-6EDB-4FF4-983F-18BD219EF322}", MEDIUM_FAMILY, "accent3"),
    TableStyle("Medium Style 2 - Accent 4", "{00A15C55-8517-42AA-B614-E9B94910E393}", MEDIUM_FAMILY, "accent4"),
    TableStyle("Medium Style 2 - Accent 5", "{7DF18680-E054-41AD-8BC1-D1AEF772440D}", MEDIUM_FAMILY, "accent5"),
    TableStyle("Medium Style 2 - Accent 6", "{93296810-A885-4BE3-A3E7-6D5BEEA58F35}", MEDIUM_FAMILY, "accent6"),
    TableStyle("No Style, Table Grid", "{5940675A-B579-460E-94D1-54222C63F5DA}", GRID_FAMILY, TEXT_SLOT),
    TableStyle("No Style, No Grid", "{2D5ABB26-0587-4C30-8999-92F81FD0307C}", PLAIN_FAMILY, TEXT_SLOT),
)
TABLE_STYLE_NAMES = tuple(style.name for style in TABLE_STYLES)
DEFAULT_TABLE_STYLE = TABLE_STYLES[1]
