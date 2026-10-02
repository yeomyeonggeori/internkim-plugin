from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import datetime
import math
import re

from sheet.pivot_tables.formula import PivotFormula, evaluate


MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DATE_UNITS = {"month": "months", "quarter": "quarters", "year": "years"}
PERCENT_BASES = {"percent_of_total": (False, False), "percent_of_row": (True, False), "percent_of_column": (False, True)}
BLANK_LABEL = "(blank)"
SUBTOTAL_SUFFIX = "Total"
NATURAL_CHUNK = re.compile(r"(\d+)")


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


def as_datetime(value: object) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time())
    return None


@dataclass(frozen=True)
class DateGroup:
    unit: str
    start: datetime.datetime
    end: datetime.datetime
    years: tuple[int, ...]

    @property
    def middle_labels(self) -> list[str]:
        if self.unit == "month":
            return list(MONTH_LABELS)
        if self.unit == "quarter":
            return [f"Qtr{quarter}" for quarter in range(1, 5)]
        return [str(year) for year in self.years]

    @property
    def items(self) -> list[str]:
        return [f"<{self.start.date().isoformat()}", *self.middle_labels, f">{self.end.date().isoformat()}"]

    def member(self, value: object) -> int:
        moment = as_datetime(value)
        if self.unit == "month":
            return moment.month
        if self.unit == "quarter":
            return (moment.month - 1) // 3 + 1
        return self.years.index(moment.year) + 1


def date_group(unit: str, values: list) -> DateGroup:
    moments = [as_datetime(value) for value in values]
    start, last = min(moments), max(moments)
    end = datetime.datetime.combine(last.date() + datetime.timedelta(days=1), datetime.time())
    return DateGroup(unit, datetime.datetime.combine(start.date(), datetime.time()), end, tuple(range(start.year, last.year + 1)))


@dataclass(frozen=True)
class NumberGroup:
    step: float
    start: float
    end: float
    labels_whole_numbers: bool

    @property
    def bucket_count(self) -> int:
        return math.floor((self.end - self.start) / self.step) + 1

    def bucket_label(self, bucket: int) -> str:
        low = self.start + bucket * self.step
        high = low + self.step - 1 if self.labels_whole_numbers else low + self.step
        return f"{shown_number(low)}-{shown_number(high)}"

    @property
    def items(self) -> list[str]:
        upper = self.start + self.bucket_count * self.step
        return [f"<{shown_number(self.start)}", *(self.bucket_label(bucket) for bucket in range(self.bucket_count)), f">{shown_number(upper)}"]

    def member(self, value: float) -> int:
        if value < self.start:
            return 0
        return min(math.floor((value - self.start) / self.step), self.bucket_count) + 1


def shown_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def number_group(step: float, start: float | None, values: list) -> NumberGroup:
    found = numbers(values)
    first = start if start is not None else math.floor(min(found) / step) * step
    whole = float(step).is_integer() and float(first).is_integer() and all(float(value).is_integer() for value in found)
    return NumberGroup(step, first, max(found), whole)


@dataclass(frozen=True)
class TopFilter:
    field: int
    count: int
    bottom: bool = False


@dataclass(frozen=True)
class AxisLine:
    members: tuple[int, ...]
    is_subtotal: bool = False


@dataclass
class PivotField:
    index: int
    items: list[str]
    members: list[int]
    group: DateGroup | NumberGroup | None = None


def plain_field(index: int, records: list) -> PivotField:
    items = sorted({item_key(record[index]) for record in records}, key=natural_order)
    positions = {item: position for position, item in enumerate(items)}
    return PivotField(index, items, [positions[item_key(record[index])] for record in records])


def grouped_field(index: int, records: list, unit: str) -> PivotField:
    group = date_group(unit, [record[index] for record in records])
    return PivotField(index, group.items, [group.member(record[index]) for record in records], group)


def binned_field(index: int, records: list, step: float, start: float | None) -> PivotField:
    group = number_group(step, start, [record[index] for record in records])
    return PivotField(index, group.items, [group.member(record[index]) for record in records], group)


@dataclass
class PivotAxis:
    fields: list[PivotField]
    lines: list[AxisLine] = field(default_factory=list)

    @property
    def depth(self) -> int:
        return len(self.fields)

    def record_path(self, record_index: int) -> tuple[int, ...]:
        return tuple(pivot_field.members[record_index] for pivot_field in self.fields)

    def label(self, level: int, member: int) -> str:
        return self.fields[level].items[member] or BLANK_LABEL


def axis_lines(axis: PivotAxis, records: list[int]) -> list[AxisLine]:
    present = {axis.record_path(record)[:length] for record in records for length in range(1, axis.depth + 1)}
    lines: list[AxisLine] = []

    def emit(prefix: tuple[int, ...]) -> None:
        level = len(prefix)
        for member in range(len(axis.fields[level].items)):
            path = (*prefix, member)
            if path not in present:
                continue
            if level == axis.depth - 1:
                lines.append(AxisLine(path))
                continue
            emit(path)
            lines.append(AxisLine(path, is_subtotal=True))

    if axis.depth:
        emit(())
    return lines


@dataclass
class PivotValue:
    caption: str
    field: int | None
    function: str
    show_as: str
    number_format: str
    formula: PivotFormula | None = None
    calculated_name: str | None = None


@dataclass
class PivotModel:
    headers: list[str]
    records: list
    rows: PivotAxis
    columns: PivotAxis
    pages: list[PivotField]
    values: list[PivotValue]
    total_label: str
    top: TopFilter | None = None
    shown_records: list[int] = field(default_factory=list)
    buckets: dict = field(default_factory=dict)

    def bucket(self, row_path: tuple, column_path: tuple) -> list[int]:
        return self.buckets.get((row_path, column_path), [])

    def raw_measure(self, value: PivotValue, row_path: tuple, column_path: tuple) -> float | None:
        return self.measure_of(value, self.bucket(row_path, column_path))

    def measure_of(self, value: PivotValue, record_indexes: list[int]) -> float | None:
        records = [self.records[index] for index in record_indexes]
        if value.formula is None:
            return aggregate([record[value.field] for record in records], value.function)
        if not records:
            return None
        totals = {index: aggregate([record[index] for record in records], "sum") or 0 for index in value.formula.fields}
        return evaluate(value.formula.tree, totals)

    def measure(self, value: PivotValue, row_path: tuple, column_path: tuple) -> float | None:
        raw = self.raw_measure(value, row_path, column_path)
        if raw is None or value.show_as not in PERCENT_BASES:
            return raw
        keeps_row, keeps_column = PERCENT_BASES[value.show_as]
        base = self.raw_measure(value, row_path if keeps_row else (), column_path if keeps_column else ())
        return None if not base else raw / base


def fill_buckets(model: PivotModel) -> None:
    buckets = defaultdict(list)
    for record in model.shown_records:
        row_path, column_path = model.rows.record_path(record), model.columns.record_path(record)
        for row_length in range(len(row_path) + 1):
            for column_length in range(len(column_path) + 1):
                buckets[(row_path[:row_length], column_path[:column_length])].append(record)
    model.buckets = dict(buckets)


def build_model(model: PivotModel) -> PivotModel:
    model.shown_records = shown_records(model)
    model.rows.lines = axis_lines(model.rows, model.shown_records)
    model.columns.lines = axis_lines(model.columns, model.shown_records)
    fill_buckets(model)
    return model


def filtered_field(model: PivotModel) -> PivotField | None:
    if model.top is None:
        return None
    return next(pivot_field for pivot_field in [*model.rows.fields, *model.columns.fields] if pivot_field.index == model.top.field)


def shown_records(model: PivotModel) -> list[int]:
    every_record = list(range(len(model.records)))
    pivot_field = filtered_field(model)
    if pivot_field is None:
        return every_record
    by_member = defaultdict(list)
    for record in every_record:
        by_member[pivot_field.members[record]].append(record)
    totals = {member: model.measure_of(model.values[0], records) for member, records in by_member.items()}
    ranked = sorted((member for member in totals if totals[member] is not None), key=lambda member: totals[member], reverse=not model.top.bottom)
    kept = set(ranked[:model.top.count])
    return [record for record in every_record if pivot_field.members[record] in kept]


@dataclass
class PivotGrid:
    rows: list[list]
    kinds: list[str]
    number_formats: dict[int, str]
    header_rows: int


def subtotal_label(axis: PivotAxis, line: AxisLine) -> str:
    return f"{axis.label(len(line.members) - 1, line.members[-1])} {SUBTOTAL_SUFFIX}"


def line_labels(axis: PivotAxis, line: AxisLine, previous: tuple | None) -> list:
    labels = [None] * axis.depth
    if line.is_subtotal:
        labels[len(line.members) - 1] = subtotal_label(axis, line)
        return labels
    for level, member in enumerate(line.members):
        starts_group = previous is None or previous[:level + 1] != line.members[:level + 1]
        if level == axis.depth - 1 or starts_group:
            labels[level] = axis.label(level, member)
    return labels


def labelled_lines(axis: PivotAxis) -> list[tuple[AxisLine, list]]:
    labelled = []
    previous = None
    for line in axis.lines:
        labelled.append((line, line_labels(axis, line, previous)))
        previous = None if line.is_subtotal else line.members
    return labelled


def line_kind(line: AxisLine) -> str:
    return "subtotal" if line.is_subtotal else "data"


def value_grid(model: PivotModel) -> PivotGrid:
    depth = model.rows.depth
    rows = [[*(model.headers[pivot_field.index] for pivot_field in model.rows.fields), *(value.caption for value in model.values)]]
    kinds = ["header"]
    for line, labels in labelled_lines(model.rows):
        rows.append([*labels, *(model.measure(value, line.members, ()) for value in model.values)])
        kinds.append(line_kind(line))
    rows.append([model.total_label, *[None] * (depth - 1), *(model.measure(value, (), ()) for value in model.values)])
    kinds.append("total")
    formats = {depth + offset: value.number_format for offset, value in enumerate(model.values)}
    return PivotGrid(rows, kinds, formats, 1)


def column_headers(model: PivotModel) -> list[list]:
    depth, levels = model.rows.depth, model.columns.depth
    width = depth + len(model.columns.lines) + 1
    headers = [[None] * width for _ in range(levels + 1)]
    headers[0][0] = model.values[0].caption
    for level, pivot_field in enumerate(model.columns.fields):
        headers[0][depth + level] = model.headers[pivot_field.index]
    for level, pivot_field in enumerate(model.rows.fields):
        headers[levels][level] = model.headers[pivot_field.index]
    for offset, (line, labels) in enumerate(labelled_lines(model.columns)):
        for level, label in enumerate(labels):
            if label is not None:
                headers[level + 1][depth + offset] = label
    headers[1][width - 1] = model.total_label
    return headers


def crosstab_grid(model: PivotModel) -> PivotGrid:
    value = model.values[0]
    depth = model.rows.depth
    column_paths = [line.members for line in model.columns.lines] + [()]
    rows = column_headers(model)
    kinds = ["header"] * len(rows)
    for line, labels in labelled_lines(model.rows):
        rows.append([*labels, *(model.measure(value, line.members, path) for path in column_paths)])
        kinds.append(line_kind(line))
    rows.append([model.total_label, *[None] * (depth - 1), *(model.measure(value, (), path) for path in column_paths)])
    kinds.append("total")
    formats = {depth + offset: value.number_format for offset in range(len(column_paths))}
    return PivotGrid(rows, kinds, formats, model.columns.depth + 1)


def pivot_grid(model: PivotModel) -> PivotGrid:
    return crosstab_grid(model) if model.columns.depth else value_grid(model)
