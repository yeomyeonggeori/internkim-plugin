#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.office_arguments import route_arguments
from core.office_result import WRONG_TYPE, Issue, IssueKind, OfficeFailure, Result, read_json_file, run_command
from paperwork.amounts import parse_amount
from paperwork.blanks import form_blanks, is_left_blank
from paperwork.company_profile import with_company_profile
from paperwork.contract_plan import plan_contract
from paperwork.forms import form_of
from paperwork.jurisdictions import Jurisdiction
from paperwork.paperwork_definitions import (
    AMOUNT_IN_WORDS_MISMATCH,
    AMOUNT_UNREADABLE,
    GRAND_TOTAL_MISMATCH,
    NO_AMOUNTS_FOUND,
    ROW_AMOUNT_MISMATCH,
    ROW_VAT_MISMATCH,
    SUPPLY_TOTAL_MISMATCH,
    VAT_MISMATCH,
)


SUPPLY_TOTAL_POSITION = 0
VAT_POSITION = 1
GRAND_TOTAL_POSITION = 2
TOTAL_LINE_COUNT = 3


@dataclass(frozen=True)
class Fact:
    kind: IssueKind
    location: str
    expected: int | float | str
    found: int | float | str

    @property
    def holds(self) -> bool:
        return self.expected == self.found

    def to_json(self) -> dict:
        return {"code": self.kind.code, "location": self.location, "expected": self.expected, "found": self.found, "holds": self.holds}

    def to_issue(self) -> Issue:
        message = f"{self.location}: expected {self.expected}, found {self.found}"
        return self.kind.issue(message, self.location, suggestion=f"{self.kind.default_suggestion()}: write {self.expected}")


@dataclass(frozen=True)
class Reading:
    facts: tuple[Fact, ...] = ()
    unreadable: tuple[Issue, ...] = ()
    has_blanks: bool = False

    def merge(self, other: "Reading") -> "Reading":
        return Reading(self.facts + other.facts, self.unreadable + other.unreadable, self.has_blanks or other.has_blanks)


@dataclass(frozen=True)
class Rules:
    jurisdiction: Jurisdiction
    tax_rate_percent: Decimal | None

    def rounded(self, value: Decimal) -> Decimal:
        return self.jurisdiction.money.rounded(value)

    def tax_on(self, amount: Decimal) -> Decimal | None:
        return None if self.tax_rate_percent is None else self.rounded(amount * self.tax_rate_percent / 100)


def main() -> Result:
    arguments = route_arguments("check", "form")
    document = read_json_file(arguments.file)
    if not isinstance(document, dict):
        raise OfficeFailure(WRONG_TYPE.issue("values: expected an object", "values"))
    form = form_of(document, "values")
    template = form.contract_template
    rules = document_rules(document)
    reading = read_document(with_amount_in_words(document), rules)
    if template is not None:
        return contract_result(template, document, reading, rules)
    printed = with_company_profile(document, form.jurisdiction.language)
    blanks = {"blanks": [blank.to_json() for blank in form_blanks(printed)]}
    if not reading.facts and not reading.unreadable and not reading.has_blanks:
        return Result(summary="no amounts to check", issues=(NO_AMOUNTS_FOUND.issue("the input holds no amounts to check"),), details=blanks)
    checked = amount_result(reading, rules)
    return Result(summary=checked.summary, issues=checked.issues, details={**(checked.details or {}), **blanks})


def contract_result(template, document: dict, reading: Reading, rules: Rules) -> Result:
    plan, contract_issues = plan_contract(template, document)
    amounts = amount_result(reading, rules)
    issues = (*contract_issues, *amounts.issues)
    details = {**(amounts.details or {}), **(plan.details if plan is not None else {})}
    return Result(summary=f"checked the contract's terms and clauses and {len(reading.facts)} amounts, {len(issues)} to fix", issues=issues, details=details)


def document_rules(document: dict) -> Rules:
    jurisdiction = form_of(document, "values").jurisdiction
    stated_rate = parse_amount(document["taxRatePercent"]) if document.get("taxRatePercent") is not None else None
    return Rules(jurisdiction, jurisdiction.tax_rate_percent if jurisdiction.tax_rate_percent is not None else stated_rate)


def read_document(document: dict, rules: Rules) -> Reading:
    if isinstance(document.get("items"), dict):
        return read_priced_form(document, rules)
    if "totalAmount" in document:
        return read_contract_amount(document, rules)
    return Reading()


def amount_result(reading: Reading, rules: Rules) -> Result:
    mismatches = tuple(fact.to_issue() for fact in reading.facts if not fact.holds)
    failed = len(mismatches) + len(reading.unreadable)
    details = {
        "jurisdiction": rules.jurisdiction.code,
        "vatRatePercent": None if rules.tax_rate_percent is None else json_number(rules.tax_rate_percent),
        "rounding": rules.jurisdiction.money.rounding_rule,
        "facts": [fact.to_json() for fact in reading.facts],
    }
    return Result(summary=f"checked {len(reading.facts)} amounts, {failed} to fix", issues=reading.unreadable + mismatches, details=details)


def read_priced_form(document: dict, rules: Rules) -> Reading:
    items = document["items"]
    untaxed = untaxed_rows(items)
    rows_reading = read_rows(items.get("headers", []), items.get("rows", []), untaxed, rules)
    totals = items.get("totals", [])
    if len(totals) != TOTAL_LINE_COUNT or rows_reading.has_blanks or any(is_left_blank(total, "value") for total in totals):
        return rows_reading
    stated = [parse_amount(total.get("value", "")) if isinstance(total, dict) else None for total in totals]
    untaxed_amount = sum((amount for index, amount in row_amounts(rows_reading) if index in untaxed), Decimal(0))
    return rows_reading.merge(read_totals(rows_reading, stated, untaxed_amount, rules)).merge(read_words(document, stated[GRAND_TOTAL_POSITION], rules))


def untaxed_rows(items: dict) -> frozenset[int]:
    indexes = items.get("untaxedRows")
    return frozenset(index for index in indexes if isinstance(index, int)) if isinstance(indexes, list) else frozenset()


def row_amounts(rows_reading: Reading) -> list[tuple[int, Decimal]]:
    if rows_reading.unreadable:
        return []
    return list(enumerate(Decimal(str(fact.found)) for fact in rows_reading.facts if fact.kind is ROW_AMOUNT_MISMATCH))


def column_index(headers: list, name: str) -> int | None:
    labels = [str(header).strip() for header in headers]
    return labels.index(name) if name in labels else None


def read_rows(headers: list, rows: list, untaxed: frozenset[int], rules: Rules) -> Reading:
    names = rules.jurisdiction.columns
    columns = [column_index(headers, name) for name in (names.quantity, names.unit_price, names.amount)]
    if None in columns:
        return Reading()
    tax_column = column_index(headers, names.tax) if rules.tax_rate_percent is not None else None
    reading = Reading()
    for index, row in enumerate(rows):
        reading = reading.merge(read_row(row, index, columns, tax_column, rules, index in untaxed))
    return reading


def read_row(row: list, index: int, columns: list[int], tax_column: int | None, rules: Rules, is_untaxed: bool) -> Reading:
    read_columns = columns if tax_column is None else [*columns, tax_column]
    if any(is_left_blank(row, column) for column in read_columns):
        return Reading(has_blanks=True)
    locations = [f"items.rows[{index}][{column}]" for column in read_columns]
    values = [parse_cell(row, column) for column in read_columns]
    unreadable = tuple(unreadable_issue(location) for value, location in zip(values, locations) if value is None)
    if unreadable:
        return Reading(unreadable=unreadable)
    quantity, unit_price, amount = values[:3]
    facts = [Fact(ROW_AMOUNT_MISMATCH, locations[2], json_number(rules.rounded(quantity * unit_price)), json_number(amount))]
    if tax_column is not None:
        expected_tax = Decimal(0) if is_untaxed else rules.tax_on(rules.rounded(amount))
        facts.append(Fact(ROW_VAT_MISMATCH, locations[3], json_number(expected_tax), json_number(values[3])))
    return Reading(tuple(facts))


def parse_cell(row: list, column: int) -> Decimal | None:
    return parse_amount(row[column]) if column < len(row) else None


def read_totals(rows_reading: Reading, stated: list[Decimal | None], untaxed_amount: Decimal, rules: Rules) -> Reading:
    locations = [f"items.totals[{position}].value" for position in range(TOTAL_LINE_COUNT)]
    unreadable = tuple(unreadable_issue(location) for value, location in zip(stated, locations) if value is None)
    if unreadable:
        return Reading(unreadable=unreadable)
    supply, tax, grand = (rules.rounded(value) for value in stated)
    expected_tax = expected_vat(rows_reading, supply - untaxed_amount, rules)
    tax_facts = [] if expected_tax is None else [Fact(VAT_MISMATCH, locations[VAT_POSITION], json_number(expected_tax), json_number(tax))]
    facts = [*tax_facts, Fact(GRAND_TOTAL_MISMATCH, locations[GRAND_TOTAL_POSITION], json_number(supply + tax), json_number(grand))]
    return Reading(tuple(row_sum_facts(rows_reading, locations[SUPPLY_TOTAL_POSITION], supply) + facts))


def expected_vat(rows_reading: Reading, taxed_supply: Decimal, rules: Rules) -> Decimal | None:
    row_vats = [Decimal(str(fact.found)) for fact in rows_reading.facts if fact.kind is ROW_VAT_MISMATCH]
    if not row_vats or rows_reading.unreadable:
        return rules.tax_on(taxed_supply)
    return sum(row_vats, Decimal(0))


def row_sum_facts(rows_reading: Reading, location: str, supply: Decimal) -> list[Fact]:
    amounts = [amount for _, amount in row_amounts(rows_reading)]
    if not amounts:
        return []
    return [Fact(SUPPLY_TOTAL_MISMATCH, location, json_number(sum(amounts, Decimal(0))), json_number(supply))]


def read_words(document: dict, grand: Decimal | None, rules: Rules) -> Reading:
    words = rules.jurisdiction.amount_in_words
    if words is None or grand is None:
        return Reading()
    entries = [(index, entry) for index, entry in enumerate(document.get("meta", [])) if isinstance(entry, dict) and str(entry.get("label", "")).strip() == words.label]
    if not entries:
        return Reading()
    index, entry = entries[0]
    found = squeeze(equivalent(str(entry.get("value", "")).split("(")[0], words.equivalents))
    return Reading((Fact(AMOUNT_IN_WORDS_MISMATCH, f"meta[{index}].value", squeeze(words.written(int(rules.rounded(grand)))), found),))


def with_amount_in_words(document: dict) -> dict:
    rules = document_rules(document)
    words = rules.jurisdiction.amount_in_words
    grand = stated_grand_total(document)
    meta = document.get("meta")
    if words is None or grand is None or not isinstance(meta, list):
        return document
    line = words.line(int(rules.rounded(grand)))
    return document | {"meta": [entry | {"value": line} if is_unwritten_words_entry(entry, words.label) else entry for entry in meta]}


def is_unwritten_words_entry(entry: object, label: str) -> bool:
    return isinstance(entry, dict) and str(entry.get("label", "")).strip() == label and not str(entry.get("value") or "").strip()


def stated_grand_total(document: dict) -> Decimal | None:
    items = document.get("items")
    totals = items.get("totals", []) if isinstance(items, dict) else []
    if not totals or not isinstance(totals[-1], dict):
        return None
    return parse_amount(totals[-1].get("value", ""))


def amount_issues(document: dict) -> tuple[Issue, ...]:
    reading = read_document(document, document_rules(document))
    return reading.unreadable + tuple(fact.to_issue() for fact in reading.facts if not fact.holds)


def read_contract_amount(document: dict, rules: Rules) -> Reading:
    if is_left_blank(document, "totalAmount"):
        return Reading(has_blanks=True)
    if parse_amount(document["totalAmount"]) is None:
        return Reading(unreadable=(unreadable_issue("totalAmount"),))
    return Reading()


def equivalent(text: str, equivalents: tuple[tuple[str, str], ...]) -> str:
    for written, meant in equivalents:
        text = text.replace(written, meant)
    return text


def squeeze(text: str) -> str:
    return "".join(text.split())


def json_number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def unreadable_issue(location: str) -> Issue:
    return AMOUNT_UNREADABLE.issue(f"{location} holds no number", location)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
