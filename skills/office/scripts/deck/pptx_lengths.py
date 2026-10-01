from __future__ import annotations

from dataclasses import dataclass
import re

from office_result import INVALID_VALUE, Issue, OfficeFailure
from office_schema import Shape, Variant, wrong_type


LENGTH_PATTERN = re.compile(r"\s*(-?\d+(?:\.\d+)?)\s*(emu|in|cm|mm|pt|px|%)\s*", re.IGNORECASE)
EMU_PER_UNIT = {"emu": 1, "in": 914400, "cm": 360000, "mm": 36000, "pt": 12700, "px": 9525}
LENGTH_EXAMPLES = '"2in", "1.5cm", "24pt", "10%"'


@dataclass(frozen=True)
class Length(Shape):
    axis: str
    minimum: int | None = None

    @property
    def label(self) -> str:
        return "length" if self.minimum is None else f"length >= {self.minimum}"

    def problems(self, value: object, location: str) -> list[Issue]:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return [wrong_type(self, value, location)]
        if isinstance(value, float) and not value.is_integer():
            return [INVALID_VALUE.issue(f"{location}: {value} is not a whole number of EMU", location, f"write a unit, such as {LENGTH_EXAMPLES}")]
        if isinstance(value, str) and not LENGTH_PATTERN.fullmatch(value):
            return [INVALID_VALUE.issue(f"{location}: {value!r} is not a length", location, f"write EMU as a number or a length such as {LENGTH_EXAMPLES}")]
        if self.minimum is not None and isinstance(value, (int, float)) and value < self.minimum:
            return [INVALID_VALUE.issue(f"{location}: {value} is below {self.minimum}", location)]
        return []


def length_in_emu(value: int | float | str, axis_size: int) -> int:
    if not isinstance(value, str):
        return int(value)
    match = LENGTH_PATTERN.fullmatch(value)
    amount, unit = float(match.group(1)), match.group(2).lower()
    if unit == "%":
        return round(amount * axis_size / 100)
    return round(amount * EMU_PER_UNIT[unit])


def normalize_lengths(operations_shape: Variant, operations: list[dict], slide_size: tuple[int, int]) -> list[dict]:
    return [normalized_operation(operations_shape, operation, index, slide_size) for index, operation in enumerate(operations)]


def normalized_operation(operations_shape: Variant, operation: dict, index: int, slide_size: tuple[int, int]) -> dict:
    record = operations_shape.record_named(operation[operations_shape.discriminator])
    normalized = dict(operation)
    for field in record.fields:
        if not isinstance(field.shape, Length) or operation.get(field.name) is None:
            continue
        axis_size = slide_size[0] if field.shape.axis == "x" else slide_size[1]
        normalized[field.name] = length_in_emu(operation[field.name], axis_size)
        if field.shape.minimum is not None and normalized[field.name] < field.shape.minimum:
            location = f"ops[{index}].{field.name}"
            raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {operation[field.name]!r} is {normalized[field.name]} EMU, below {field.shape.minimum}", location))
    return normalized
