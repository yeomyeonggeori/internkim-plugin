from __future__ import annotations

from charts.numbers import split_chart_list
from deck.deck_claims import Node, parsed, unit_role, unit_text

SLIDE_TITLE_TAGS = ("h1", "h2")
CELL_TAGS = ("td", "th")


def deck_slides(text: str) -> list[dict]:
    sections = [node for node in parsed(text).elements() if node.tag == "section"]
    return [slide_holds(number, section) for number, section in enumerate(sections, start=1)]


def slide_holds(number: int, section: Node) -> dict:
    title_node = next((node for node in section.elements() if node.tag in SLIDE_TITLE_TAGS and unit_role(node)), None)
    holds = {
        "slide": number,
        "layout": section.attributes.get("data-layout", ""),
        "title": unit_text(title_node) if title_node else "",
        "text": slide_text(section, title_node),
        "tables": [table_rows(table) for table in section.elements() if table.tag == "table" and not is_in_notes(table)],
        "charts": [chart_holds(figure) for figure in section.elements() if unit_role(figure) == "chart"],
        "icons": [node.attributes["data-icon"] for node in section.elements() if node.attributes.get("data-icon")],
    }
    return {key: value for key, value in holds.items() if value or key in ("slide", "title")}


def slide_text(section: Node, title_node: Node | None) -> list[str]:
    units = [node for node in section.elements() if node is not title_node and unit_role(node) not in ("", "cell", "chart")]
    return [content for content in map(unit_text, units) if content]


def table_rows(table: Node) -> list[list[str]]:
    rows = [node for node in table.elements() if node.tag == "tr"]
    return [[unit_text(cell) for cell in row.children if isinstance(cell, Node) and cell.tag in CELL_TAGS] for row in rows]


def chart_holds(figure: Node) -> dict:
    attributes = figure.attributes
    chart = {
        "type": attributes["data-chart"],
        "labels": split_chart_list(attributes.get("data-labels", "")),
        "values": split_chart_list(attributes.get("data-values", "")),
        "series": attributes.get("data-series", ""),
        "unit": attributes.get("data-unit", ""),
    }
    return {key: value for key, value in chart.items() if value}


def is_in_notes(node: Node) -> bool:
    return any(ancestor.tag == "aside" for ancestor in node.ancestors())
