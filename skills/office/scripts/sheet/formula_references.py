from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from openpyxl.formula.tokenizer import Token, Tokenizer
from openpyxl.utils import column_index_from_string, get_column_letter
from excel_limits import MAXIMUM_COLUMN, MAXIMUM_ROW


ROW_AXIS = "row"
COLUMN_AXIS = "column"
REFERENCE_ERROR = "#REF!"

CELL_END = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)([0-9]+)$")
COLUMN_END = re.compile(r"^(\$?)([A-Za-z]{1,3})$")
ROW_END = re.compile(r"^(\$?)([0-9]+)$")
PLAIN_SHEET_NAME = re.compile(r"^[^\W\d][\w.]*$")


@dataclass(frozen=True)
class End:
    column: int | None
    column_absolute: bool
    row: int | None
    row_absolute: bool

    def text(self) -> str:
        column = f"{'$' if self.column_absolute else ''}{get_column_letter(self.column)}" if self.column is not None else ""
        row = f"{'$' if self.row_absolute else ''}{self.row}" if self.row is not None else ""
        return column + row

    def moved(self, axis: str, index: int) -> "End":
        if axis == ROW_AXIS:
            return End(self.column, self.column_absolute, index, self.row_absolute)
        return End(index, self.column_absolute, self.row, self.row_absolute)

    def index(self, axis: str) -> int | None:
        return self.row if axis == ROW_AXIS else self.column


@dataclass(frozen=True)
class Shift:
    sheet: str
    axis: str
    at: int
    count: int

    @property
    def is_insert(self) -> bool:
        return self.count > 0

    @property
    def removed(self) -> int:
        return abs(self.count)

    @property
    def last_removed(self) -> int:
        return self.at + self.removed - 1


def parse_end(text: str) -> End | None:
    cell = CELL_END.match(text)
    if cell:
        column = column_index_from_string(cell.group(2).upper())
        row = int(cell.group(4))
        if column > MAXIMUM_COLUMN or not 1 <= row <= MAXIMUM_ROW:
            return None
        return End(column, bool(cell.group(1)), row, bool(cell.group(3)))
    column_only = COLUMN_END.match(text)
    if column_only:
        column = column_index_from_string(column_only.group(2).upper())
        return End(column, bool(column_only.group(1)), None, False) if column <= MAXIMUM_COLUMN else None
    row_only = ROW_END.match(text)
    if row_only and 1 <= int(row_only.group(2)) <= MAXIMUM_ROW:
        return End(None, False, int(row_only.group(2)), bool(row_only.group(1)))
    return None


def split_outside_quotes(text: str, separator: str) -> list[str]:
    parts = []
    current = []
    quoted = False
    for character in text:
        if character == "'":
            quoted = not quoted
        if character == separator and not quoted:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    return parts


def split_sheet_prefix(text: str) -> tuple[str | None, str]:
    if text.startswith("'"):
        closing = closing_quote_index(text)
        if closing is not None and text[closing + 1:closing + 2] == "!":
            return text[:closing + 1], text[closing + 2:]
        return None, text
    if "!" in text:
        prefix, _, rest = text.partition("!")
        return prefix, rest
    return None, text


def closing_quote_index(text: str) -> int | None:
    index = 1
    while index < len(text):
        if text[index] == "'":
            if text[index + 1:index + 2] == "'":
                index += 2
                continue
            return index
        index += 1
    return None


def unquote_sheet_name(prefix: str) -> str:
    if prefix.startswith("'") and prefix.endswith("'"):
        return prefix[1:-1].replace("''", "'")
    return prefix


def quote_sheet_name(name: str) -> str:
    if PLAIN_SHEET_NAME.match(name) and CELL_END.match(name) is None and COLUMN_END.match(name) is None:
        return name
    return "'" + name.replace("'", "''") + "'"


def same_sheet(left: str, right: str) -> bool:
    return left.casefold() == right.casefold()


@dataclass(frozen=True)
class Part:
    prefix: str | None
    rest: str


def reference_parts(value: str) -> list[Part] | None:
    pieces = split_outside_quotes(value, ":")
    parts = [Part(*split_sheet_prefix(piece)) for piece in pieces]
    if any(part.prefix is not None and part.prefix.startswith("[") for part in parts):
        return None
    if len(parts) > 1 and parts[0].prefix is None and "!" in value and parse_end(parts[0].rest) is None:
        return None
    return parts


def referenced_sheet_names(value: str) -> list[str]:
    parts = reference_parts(value)
    if parts is None:
        return []
    return [unquote_sheet_name(part.prefix) for part in parts if part.prefix is not None]


def shift_reference(value: str, host_sheet: str, shift: Shift) -> str:
    parts = reference_parts(value)
    if parts is None or len(parts) > 2:
        return value
    target_sheet = unquote_sheet_name(parts[0].prefix) if parts[0].prefix is not None else host_sheet
    if not same_sheet(target_sheet, shift.sheet):
        return value
    ends = [parse_end(part.rest) for part in parts]
    if any(end is None for end in ends):
        return value
    if len(ends) == 1 and (ends[0].column is None or ends[0].row is None):
        return value
    shifted = shift_ends(ends, shift)
    if shifted is None:
        return join_parts(parts[0].prefix, REFERENCE_ERROR)
    if shifted == ends:
        return value
    return rebuild_reference(parts, shifted)


def shift_ends(ends: list[End], shift: Shift) -> list[End] | None:
    indexes = [end.index(shift.axis) for end in ends]
    if indexes[0] is None:
        return ends
    if len(ends) == 1:
        moved = shift_single(indexes[0], shift)
        return None if moved is None else [ends[0].moved(shift.axis, moved)]
    span = shift_span(indexes[0], indexes[1], shift)
    if span is None:
        return None
    return [ends[0].moved(shift.axis, span[0]), ends[1].moved(shift.axis, span[1])]


def shift_single(index: int, shift: Shift) -> int | None:
    if shift.is_insert:
        return index + shift.count if index >= shift.at else index
    if index < shift.at:
        return index
    if index <= shift.last_removed:
        return None
    return index - shift.removed


def shift_span(first: int, last: int, shift: Shift) -> tuple[int, int] | None:
    if shift.is_insert:
        return (first + shift.count if first >= shift.at else first, last + shift.count if last >= shift.at else last)
    new_first = first if first < shift.at else (shift.at if first <= shift.last_removed else first - shift.removed)
    new_last = last if last < shift.at else (shift.at - 1 if last <= shift.last_removed else last - shift.removed)
    if new_first > new_last:
        return None
    return new_first, new_last


def rebuild_reference(parts: list[Part], ends: list[End]) -> str:
    first = join_parts(parts[0].prefix, ends[0].text())
    if len(parts) == 1:
        return first
    return first + ":" + join_parts(parts[1].prefix, ends[1].text())


def join_parts(prefix: str | None, rest: str) -> str:
    return f"{prefix}!{rest}" if prefix is not None else rest


def rename_sheet_reference(value: str, old_name: str, new_name: str) -> str:
    parts = reference_parts(value)
    if parts is None:
        return value
    renamed = [rename_part(part, old_name, new_name) for part in parts]
    return ":".join(join_parts(part.prefix, part.rest) for part in renamed)


def rename_part(part: Part, old_name: str, new_name: str) -> Part:
    if part.prefix is None or not same_sheet(unquote_sheet_name(part.prefix), old_name):
        return part
    return Part(quote_sheet_name(new_name), part.rest)


def deleted_sheet_reference(value: str, deleted: str) -> str:
    return REFERENCE_ERROR if any(same_sheet(name, deleted) for name in referenced_sheet_names(value)) else value


def rewrite_formula(formula: str, rewrite_reference: Callable[[str], str]) -> str:
    if not formula.startswith("="):
        return formula
    tokenizer = Tokenizer(formula)
    changed = False
    for token in tokenizer.items:
        if token.type != Token.OPERAND or token.subtype != Token.RANGE:
            continue
        rewritten = rewrite_reference(token.value)
        if rewritten != token.value:
            token.value = rewritten
            changed = True
    return tokenizer.render() if changed else formula


def formula_references(formula: str) -> list[str]:
    if not formula.startswith("="):
        return []
    return [token.value for token in Tokenizer(formula).items if token.type == Token.OPERAND and token.subtype == Token.RANGE]


def referenced_names(formula: str) -> list[str]:
    return [reference for reference in formula_references(formula) if is_bare_name(reference)]


def is_bare_name(reference: str) -> bool:
    if "!" in reference or "[" in reference or ":" in reference:
        return False
    return parse_end(reference) is None


def formula_has_error_operand(formula: str) -> bool:
    if not formula.startswith("="):
        return False
    return any(is_error_operand(token) for token in Tokenizer(formula).items)


def is_error_operand(token: Token) -> bool:
    if token.type != Token.OPERAND:
        return False
    return token.subtype == Token.ERROR or (token.subtype == Token.RANGE and token.value.endswith(REFERENCE_ERROR))


def formula_function_names(formula: str) -> list[str]:
    if not formula.startswith("="):
        return []
    return [token.value[:-1].upper() for token in Tokenizer(formula).items if token.type == Token.FUNC and token.subtype == Token.OPEN]
