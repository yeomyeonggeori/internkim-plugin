from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


SETTINGS_ORDER_TAIL = (
    "updateFields",
    "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr", "attachedSchema",
    "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats", "doNotAutoCompressPictures", "forceUpgrade",
    "captions", "readModeInkLockDown", "smartTagType", "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags",
    "decimalSymbol", "listSeparator",
)


def request_field_update(document) -> None:
    settings = document.settings.element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        insert_setting(settings, update_fields)
    update_fields.set(qn("w:val"), "true")


def insert_setting(settings, element) -> None:
    name = element.tag.split("}", 1)[-1]
    successor_tags = {qn(f"w:{successor}") for successor in SETTINGS_ORDER_TAIL[SETTINGS_ORDER_TAIL.index(name) + 1:]}
    successor = next((child for child in settings if child.tag in successor_tags), None)
    if successor is None:
        settings.append(element)
    else:
        successor.addprevious(element)
