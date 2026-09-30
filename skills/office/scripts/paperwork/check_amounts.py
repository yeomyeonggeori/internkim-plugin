#!/usr/bin/env python3
from dataclasses import dataclass
from decimal import Decimal

from amounts import (
    ROUNDING_RULE,
    VAT_RATE_PERCENT,
    grand_total,
    korean_amount_in_words,
    korean_number_words,
    parse_amount,
    row_amount,
    supply_total,
    truncate_to_won,
    value_added_tax,
    vat_total,
)
from office_result import WRONG_TYPE, Issue, IssueKind, OfficeArgumentParser, OfficeFailure, Result, read_json_file, run_command
from paperwork_definitions import (
    AMOUNT_HEADERS,
    AMOUNT_IN_WORDS_MISMATCH,
    AMOUNT_UNREADABLE,
    GRAND_TOTAL_MISMATCH,
    NO_AMOUNTS_FOUND,
    QUANTITY_HEADERS,
    ROW_AMOUNT_MISMATCH,
    ROW_VAT_MISMATCH,
    SUPPLY_TOTAL_MISMATCH,
    TAX_HEADERS,
    UNIT_PRICE_HEADERS,
    VAT_MISMATCH,
    WORDS_LABELS,
)


SUPPLY_TOTAL_POSITION = 0
VAT_POSITION = 1
GRAND_TOTAL_POSITION = 2
TOTAL_LINE_COUNT = 3


@dataclass(frozen=True)
class Fact:
    kind: IssueKind
    location: str
    expected: int | str
    found: int | str

    @property
    def holds(self) -> bool:
        return self.expected == self.found

    def to_json(self) -> dict:
        return {"code": self.kind.code, "location": self.location, "expected": self.expected, "found": self.found, "holds": self.holds}

    def to_issue(self) -> Issue:
        message = f"{self.location}: expected {self.expected}, found {self.found}"
        return self.kind.issue(message, self.location, suggestion={"expected": self.expected, "found": self.found})


@dataclass(frozen=True)
class Reading:
    facts: tuple[Fact, ...] = ()
    unreadable: tuple[Issue, ...] = ()

    def merge(self, other: "Reading") -> "Reading":
        return Reading(self.facts + other.facts, self.unreadable + other.unreadable)


def main() -> Result:
    arguments = parse_arguments()
    document = read_json_file(arguments.input_path)
    if not isinstance(document, dict):
        raise OfficeFailure(WRONG_TYPE.issue("input: expected an object", "input"))
    reading = read_document(document)
    if not reading.facts and not reading.unreadable:
        return Result(summary="no amounts to check", issues=(NO_AMOUNTS_FOUND.issue("the input holds no amounts to check"),))
    return amount_result(reading)


def read_document(document: dict) -> Reading:
    if isinstance(document.get("items"), dict):
        return read_priced_form(document)
    if "totalAmount" in document:
        return read_contract_amount(document)
    return Reading()


def amount_result(reading: Reading) -> Result:
    mismatches = tuple(fact.to_issue() for fact in reading.facts if not fact.holds)
    failed = len(mismatches) + len(reading.unreadable)
    details = {
        "vatRatePercent": VAT_RATE_PERCENT,
        "rounding": ROUNDING_RULE,
        "facts": [fact.to_json() for fact in reading.facts],
    }
    return Result(summary=f"checked {len(reading.facts)} amounts, {failed} to fix", issues=reading.unreadable + mismatches, details=details)


def read_priced_form(document: dict) -> Reading:
    items = document["items"]
    rows_reading = read_rows(items.get("headers", []), items.get("rows", []))
    totals = items.get("totals", [])
    if len(totals) != TOTAL_LINE_COUNT:
        return rows_reading
    stated = [parse_amount(total.get("value", "")) if isinstance(total, dict) else None for total in totals]
    return rows_reading.merge(read_totals(rows_reading, stated)).merge(read_words(document, stated[GRAND_TOTAL_POSITION]))


def column_index(headers: list, names: tuple[str, ...]) -> int | None:
    labels = [str(header).strip() for header in headers]
    return next((labels.index(name) for name in names if name in labels), None)


def read_rows(headers: list, rows: list) -> Reading:
    columns = [column_index(headers, names) for names in (QUANTITY_HEADERS, UNIT_PRICE_HEADERS, AMOUNT_HEADERS)]
    if None in columns:
        return Reading()
    tax_column = column_index(headers, TAX_HEADERS)
    reading = Reading()
    for index, row in enumerate(rows):
        reading = reading.merge(read_row(row, index, columns, tax_column))
    return reading


def read_row(row: list, index: int, columns: list[int], tax_column: int | None) -> Reading:
    read_columns = columns if tax_column is None else [*columns, tax_column]
    locations = [f"items.rows[{index}][{column}]" for column in read_columns]
    values = [parse_cell(row, column) for column in read_columns]
    unreadable = tuple(unreadable_issue(location) for value, location in zip(values, locations) if value is None)
    if unreadable:
        return Reading(unreadable=unreadable)
    quantity, unit_price, amount = values[:3]
    facts = [Fact(ROW_AMOUNT_MISMATCH, locations[2], row_amount(quantity, unit_price), json_number(amount))]
    if tax_column is not None:
        facts.append(Fact(ROW_VAT_MISMATCH, locations[3], value_added_tax(truncate_to_won(amount)), json_number(values[3])))
    return Reading(tuple(facts))


def parse_cell(row: list, column: int) -> Decimal | None:
    return parse_amount(row[column]) if column < len(row) else None


def read_totals(rows_reading: Reading, stated: list[Decimal | None]) -> Reading:
    locations = [f"items.totals[{position}].value" for position in range(TOTAL_LINE_COUNT)]
    unreadable = tuple(unreadable_issue(location) for value, location in zip(stated, locations) if value is None)
    if unreadable:
        return Reading(unreadable=unreadable)
    supply, tax, grand = (truncate_to_won(value) for value in stated)
    facts = [
        Fact(VAT_MISMATCH, locations[VAT_POSITION], expected_vat(rows_reading, supply), tax),
        Fact(GRAND_TOTAL_MISMATCH, locations[GRAND_TOTAL_POSITION], grand_total(supply, tax), grand),
    ]
    return Reading(tuple(row_sum_facts(rows_reading, locations[SUPPLY_TOTAL_POSITION], supply) + facts))


def expected_vat(rows_reading: Reading, supply: int) -> int:
    row_vats = [fact.found for fact in rows_reading.facts if fact.kind is ROW_VAT_MISMATCH]
    if not row_vats or rows_reading.unreadable:
        return value_added_tax(supply)
    return vat_total(row_vats)


def row_sum_facts(rows_reading: Reading, location: str, supply: int) -> list[Fact]:
    row_facts = [fact for fact in rows_reading.facts if fact.kind is ROW_AMOUNT_MISMATCH]
    if not row_facts or rows_reading.unreadable:
        return []
    return [Fact(SUPPLY_TOTAL_MISMATCH, location, supply_total([fact.found for fact in row_facts]), supply)]


def read_words(document: dict, grand: Decimal | None) -> Reading:
    entries = [(index, entry) for index, entry in enumerate(document.get("meta", [])) if isinstance(entry, dict) and str(entry.get("label", "")).strip() in WORDS_LABELS]
    if grand is None or not entries:
        return Reading()
    index, entry = entries[0]
    found = squeeze(str(entry.get("value", "")).split("(")[0].replace("整", "정"))
    return Reading((Fact(AMOUNT_IN_WORDS_MISMATCH, f"meta[{index}].value", squeeze(korean_amount_in_words(truncate_to_won(grand))), found),))


def read_contract_amount(document: dict) -> Reading:
    amount = parse_amount(document["totalAmount"])
    if amount is None:
        return Reading(unreadable=(unreadable_issue("totalAmount"),))
    found = squeeze(str(document.get("totalAmountKorean", "")))
    if not found:
        return Reading()
    return Reading((Fact(AMOUNT_IN_WORDS_MISMATCH, "totalAmountKorean", squeeze(korean_number_words(truncate_to_won(amount))), found),))


def squeeze(text: str) -> str:
    return "".join(text.split())


def json_number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def unreadable_issue(location: str) -> Issue:
    return AMOUNT_UNREADABLE.issue(f"{location} holds no number", location)


def parse_arguments():
    parser = OfficeArgumentParser(description="Report amount facts of a paperwork document JSON or contract context: row amounts, supply total, VAT, grand total and the Korean amount in words. Never rewrites the input; office guide paperwork lists the rules.")
    parser.add_argument("input_path", help="the document JSON of paperwork render, or the context JSON of paperwork fill")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
