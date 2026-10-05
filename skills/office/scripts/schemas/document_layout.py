from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

from core.office_result import INVALID_VALUE, OfficeFailure
from schemas.resolution import Instance, render_template
from schemas.typed_values import BLANK, NUMBER_TYPES, format_value, grouped, numeric_value


WORDS = {
    "ko": {"total": "합계", "item": "항목", "detail": "내용", "owner": "담당", "due": "기한", "recipient": "수신", "sender": "발신", "date": "일자", "sealMark": "(인)"},
    "en": {"total": "Total", "item": "Item", "detail": "Detail", "owner": "Owner", "due": "Due", "recipient": "To", "sender": "From", "date": "Date", "sealMark": ""},
}
ITEM_DETAILS = ("date", "owner", "due", "quantity", "amount", "percent", "status")
BLANK_WHEN_NULL = ("owner", "due")


def localized(text: object, language: str) -> str:
    return text.get(language) or next(iter(text.values()), "") if isinstance(text, dict) else str(text)


class MarkdownDocument:
    def __init__(self, instance: Instance):
        self.instance = instance
        self.language = instance.language
        self.words = WORDS.get(self.language, WORDS["en"])
        self.lines: list[str] = []
        self.blanks: list[dict] = []

    def text(self) -> str:
        return "\n".join(self.lines).strip() + "\n"

    def add(self, *lines: str) -> None:
        self.lines.extend(lines)

    def render(self) -> "MarkdownDocument":
        layout = self.instance.schema.layout
        for part in layout.get("parts", []):
            if part.get("for", self.language) == self.language:
                getattr(self, f"part_{part['type']}")(part)
        return self

    def template(self, template, row: dict | None = None) -> str | None:
        return render_template(self.instance, localized(template, self.language), row, whole_blank=BLANK)

    def part_lines(self, part: dict) -> None:
        rendered = [self.template(line) for line in part["lines"]]
        self.add(*[f"{line}  " for line in rendered if line is not None], "")

    def fence(self, kind: str, data: dict) -> None:
        self.add(f"```{kind}", json.dumps(data, ensure_ascii=False), "```", "")

    def company_image(self, field: str) -> str | None:
        path = (self.instance.known.get("company") or {}).get(field)
        return str(path) if path and Path(str(path)).is_file() else None

    def part_letterhead(self, part: dict) -> None:
        details = [self.template(line) for line in part["details"]]
        self.fence("letterhead", {"name": self.template(part["name"]) or "", "details": [line for line in details if line is not None], "logo": self.company_image("logoPath")})

    def part_memo(self, part: dict) -> None:
        rows = [[localized(row["label"], self.language), self.template(row["value"]), bool(row.get("emphasis"))] for row in part["rows"]]
        self.fence("memo", {"rows": [row for row in rows if row[1] is not None]})

    def part_address(self, part: dict) -> None:
        lines = [self.template(line) for line in part["lines"]]
        subject = self.template(part["subject"])
        self.fence("letter-address", {
            "date": self.template(part["date"]),
            "lines": [line for line in lines if line is not None],
            "subject": f"{part['subjectLabel']} {subject}" if subject is not None else None,
            "salutation": self.template(part["salutation"]),
        })

    def part_closing(self, part: dict) -> None:
        lines = [self.template(line) for line in part["lines"]]
        self.fence("letter-closing", {"complimentary": part.get("complimentary", ""), "align": part.get("align", "right"), "lines": [line for line in lines if line is not None],
                                      "seal": self.company_image("stampPath"), "sealMark": self.words["sealMark"] if part.get("align", "right") == "right" else ""})

    def part_enclosures(self, part: dict) -> None:
        names = [name for name in self.instance.given.get(part["field"]) or [] if name]
        if not names:
            return
        label = localized(part["label"], self.language)
        self.add(f"**{label}** " + "  ".join(f"{number}. {name}" for number, name in enumerate(names, start=1)) if self.language == "ko" else f"**{label}** " + "; ".join(names), "")

    def part_endmark(self, part: dict) -> None:
        self.add(localized(part["text"], self.language), "")

    def part_heading(self, part: dict) -> None:
        heading = self.template(part["text"])
        if heading:
            self.add(f"{'#' * part.get('level', 1)} {heading}", "")

    def part_labeled(self, part: dict) -> None:
        for entry in part["rows"]:
            value = self.template(entry["value"])
            if value is not None:
                self.add(f"**{localized(entry['label'], self.language)}**: {value}  ")
        self.add("")

    def part_sections(self, part: dict) -> None:
        sections = self.instance.given.get(part["field"]) or []
        for section_index, section in enumerate(sections):
            if section.get("heading"):
                self.add(f"## {section['heading']}", "")
            for block_index, block in enumerate(section.get("blocks") or []):
                self.block(block, f"{part['field']}[{section_index}].blocks[{block_index}]")

    def block(self, block: dict, location: str) -> None:
        kind = block.get("type")
        if kind == "paragraph":
            self.add(block.get("text") or BLANK, "")
        elif kind == "items":
            self.items(block, location)
        elif kind == "table":
            self.table(block, location)
        elif kind == "fields":
            self.fields(block, location)
        elif kind == "chart":
            self.chart(block, location)

    def items(self, block: dict, location: str) -> None:
        for index, item in enumerate(block.get("items") or []):
            marker = f"{index + 1}." if block.get("numbered") else "-"
            self.add(f"{marker} {self.item_line(item, f'{location}.items[{index}]')}")
        self.add("")

    def item_line(self, item: dict, location: str) -> str:
        details = [self.item_detail(item, name, location) for name in ITEM_DETAILS if item.get(name) is not None or name in BLANK_WHEN_NULL and name in item]
        text = item.get("text") or BLANK
        return f"{text} — {' · '.join(details)}" if details else text

    def item_detail(self, item: dict, name: str, location: str) -> str:
        label = f"{self.words[name]} " if name in ("owner", "due") else ""
        value = item.get(name)
        if value is None:
            self.blanks.append({"field": f"{location}.{name}", "label": f"{item.get('text') or ''} {self.words.get(name, name)}".strip()})
            return f"{label}{BLANK}"
        value_type = {"date": "date", "due": "date", "amount": "amount", "quantity": "quantity", "percent": "percent"}.get(name, "text")
        unit = item.get("currency", "") if name == "amount" else item.get("unit", "")
        return f"{label}{format_value(value_type, value, unit, self.language, f'{location}.{name}')}"

    def table(self, block: dict, location: str) -> None:
        columns = block.get("columns") or []
        rows = block.get("rows") or []
        if not columns:
            raise OfficeFailure(INVALID_VALUE.issue(f"{location}.columns: a table needs its columns", f"{location}.columns"))
        self.add("| " + " | ".join(column_header(column) for column in columns) + " |")
        self.add("|" + "|".join("---:" if column.get("type") in NUMBER_TYPES else "---" for column in columns) + "|")
        for row_index, row in enumerate(rows):
            cells = [self.cell(columns[index], row[index] if index < len(row) else None, f"{location}.rows[{row_index}][{index}]", row) for index in range(len(columns))]
            self.add("| " + " | ".join(cells) + " |")
        if block.get("totals"):
            self.add("| " + " | ".join(self.total_cell(index, column, rows, location) for index, column in enumerate(columns)) + " |")
        self.add("")

    def cell(self, column: dict, value: object, location: str, row: list) -> str:
        if value is None:
            self.blanks.append({"field": location, "label": f"{row[0] if row and row[0] is not None else ''} {column.get('name', '')}".strip()})
            return " "
        value_type = column.get("type", "text")
        unit = "" if value_type == "amount" and column.get("unit", "").upper() not in ("USD", "EUR", "GBP", "JPY") else column.get("unit", "")
        return format_value(value_type, value, "" if value_type == "quantity" else unit, self.language, location).replace("|", "/")

    def total_cell(self, index: int, column: dict, rows: list, location: str) -> str:
        if index == 0:
            return f"**{self.words['total']}**"
        if column.get("type") not in ("amount", "quantity"):
            return " "
        values = [numeric_value(row[index] if index < len(row) else None, location) for row in rows]
        if any(value is None for value in values):
            return " "
        return f"**{self.cell(column, sum(values, Decimal(0)), location, [])}**"

    def fields(self, block: dict, location: str) -> None:
        self.add(f"| {self.words['item']} | {self.words['detail']} |", "|---|---|")
        for index, entry in enumerate(block.get("fields") or []):
            value = entry.get("value")
            label = entry.get("label") or ""
            if value is None:
                self.blanks.append({"field": f"{location}.fields[{index}].value", "label": label})
                shown = BLANK
            else:
                shown = format_value(entry.get("type") or "text", value, entry.get("unit") or "", self.language, f"{location}.fields[{index}].value")
            self.add(f"| {label} | {shown} |")
        self.add("")

    def chart(self, block: dict, location: str) -> None:
        series = block.get("series") or []
        if any(value is None for entry in series for value in entry.get("values") or []):
            raise OfficeFailure(INVALID_VALUE.issue(f"{location}.series: a chart cannot draw a blank value", f"{location}.series", "leave the point out of the chart; a table beside it can keep the blank"))
        lines = ["```chart", f"type: {block.get('chart') or 'column'}", f"labels: {', '.join(str(label) for label in block.get('labels') or [])}"]
        if block.get("caption"):
            lines.append(f"title: {block['caption']}")
        lines.append("series: " + "; ".join(f"{entry.get('name')}: {', '.join(chart_number(value) for value in entry.get('values') or [])}" for entry in series))
        self.add(*lines, "```", "")


def column_header(column: dict) -> str:
    unit = column.get("unit") or ""
    name = column.get("name") or ""
    return f"{name} ({unit})" if unit and column.get("type") in ("amount", "quantity") else name


def chart_number(value: object) -> str:
    number = numeric_value(value, "chart")
    return grouped(number).replace(",", "") if number is not None else ""
