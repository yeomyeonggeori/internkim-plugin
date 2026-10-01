from __future__ import annotations

from dataclasses import dataclass
import difflib
import re
from typing import Iterator

from office_result import INVALID_VALUE, MISSING_FIELD, UNKNOWN_FIELD, WRONG_TYPE, Issue, OfficeFailure


HEX_COLOR_PATTERN = re.compile(r"#?[0-9A-Fa-f]{6}")


class Shape:
    label = "value"

    def problems(self, value: object, location: str) -> list[Issue]:
        raise NotImplementedError

    def structures(self) -> Iterator["Record | Variant"]:
        return iter(())


@dataclass(frozen=True)
class Text(Shape):
    non_empty: bool = False

    @property
    def label(self) -> str:
        return "non-empty text" if self.non_empty else "text"

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, str):
            return [wrong_type(self, value, location)]
        if self.non_empty and not value.strip():
            return [MISSING_FIELD.issue(f"{location}: must not be empty", location)]
        return []


@dataclass(frozen=True)
class Number(Shape):
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = False

    @property
    def label(self) -> str:
        noun = "integer" if self.integer else "number"
        if self.minimum is not None and self.maximum is not None:
            return f"{noun} {format_number(self.minimum)}-{format_number(self.maximum)}"
        if self.minimum is not None:
            return f"{noun} >= {format_number(self.minimum)}"
        return noun

    def problems(self, value: object, location: str) -> list[Issue]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [wrong_type(self, value, location)]
        if self.integer and not float(value).is_integer():
            return [wrong_type(self, value, location)]
        if self.minimum is not None and value < self.minimum or self.maximum is not None and value > self.maximum:
            return [INVALID_VALUE.issue(f"{location}: {value} is outside {self.label}", location)]
        return []


@dataclass(frozen=True)
class Boolean(Shape):
    label = "true or false"

    def problems(self, value: object, location: str) -> list[Issue]:
        return [] if isinstance(value, bool) else [wrong_type(self, value, location)]


@dataclass(frozen=True)
class Choice(Shape):
    values: tuple[str, ...]

    @property
    def label(self) -> str:
        return "one of " + ", ".join(self.values)

    def problems(self, value: object, location: str) -> list[Issue]:
        if value in self.values:
            return []
        return [INVALID_VALUE.issue(f"{location}: {value!r} is not {self.label}{did_you_mean(value, self.values)}", location, closest_suggestion(value, self.values))]


@dataclass(frozen=True)
class HexColor(Shape):
    allows_none: bool = False

    @property
    def label(self) -> str:
        return 'six hex digits such as 1F4E79, or "none"' if self.allows_none else "six hex digits such as 1F4E79"

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, str):
            return [wrong_type(self, value, location)]
        if self.allows_none and value == "none" or HEX_COLOR_PATTERN.fullmatch(value):
            return []
        return [INVALID_VALUE.issue(f"{location}: {value!r} is not {self.label}", location)]


@dataclass(frozen=True)
class CellValue(Shape):
    label = "cell"

    def problems(self, value: object, location: str) -> list[Issue]:
        if value is None or isinstance(value, (str, int, float, bool)):
            return []
        return [wrong_type(self, value, location)]


@dataclass(frozen=True)
class ListOf(Shape):
    item: Shape
    non_empty: bool = False

    @property
    def label(self) -> str:
        prefix = "non-empty list" if self.non_empty else "list"
        return f"{prefix} of {self.item.label}"

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, list):
            return [wrong_type(self, value, location)]
        if self.non_empty and not value:
            return [MISSING_FIELD.issue(f"{location}: must hold at least one item", location)]
        return [problem for index, item in enumerate(value) for problem in self.item.problems(item, f"{location}[{index}]")]

    def structures(self) -> Iterator["Record | Variant"]:
        return self.item.structures()


@dataclass(frozen=True)
class MapOf(Shape):
    value: Shape
    key: str

    @property
    def label(self) -> str:
        return f"object mapping {self.key} to {self.value.label}"

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, dict):
            return [wrong_type(self, value, location)]
        return [problem for key, item in value.items() for problem in self.value.problems(item, f"{location}.{key}")]


@dataclass(frozen=True)
class AnyOf(Shape):
    shapes: tuple[Shape, ...]
    name: str = ""

    @property
    def label(self) -> str:
        return self.name or " or ".join(shape.label for shape in self.shapes)

    def problems(self, value: object, location: str) -> list[Issue]:
        candidate_problems = [shape.problems(value, location) for shape in self.shapes]
        if any(not problems for problems in candidate_problems):
            return []
        return [wrong_type(self, value, location)]

    def structures(self) -> Iterator["Record | Variant"]:
        for shape in self.shapes:
            yield from shape.structures()


@dataclass(frozen=True)
class Field:
    name: str
    shape: Shape
    description: str
    required: bool = False


@dataclass(frozen=True)
class Record(Shape):
    name: str
    description: str
    fields: tuple[Field, ...]
    keeps_other_fields: bool = False

    @property
    def label(self) -> str:
        return self.name

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, dict):
            return [wrong_type(self, value, location)]
        return self.field_problems(value, location, known_names=set())

    def field_problems(self, value: dict, location: str, known_names: set[str]) -> list[Issue]:
        field_names = {field.name for field in self.fields} | known_names
        problems = [
            UNKNOWN_FIELD.issue(
                f"{join_location(location, name)}: {self.name} has no field {name!r}{did_you_mean(name, field_names)}; it takes {', '.join(sorted(field_names))}",
                join_location(location, name),
                closest_suggestion(name, field_names, "rename the field to {match!r}"),
            )
            for name in value
            if name not in field_names and not self.keeps_other_fields
        ]
        for field in self.fields:
            problems.extend(field_value_problems(field, value.get(field.name), join_location(location, field.name)))
        return problems

    def structures(self) -> Iterator["Record | Variant"]:
        yield self
        for field in self.fields:
            yield from field.shape.structures()


@dataclass(frozen=True)
class Variant(Shape):
    name: str
    description: str
    discriminator: str
    records: tuple[Record, ...]

    @property
    def label(self) -> str:
        return self.name

    def record_named(self, record_name: object) -> Record | None:
        return next((record for record in self.records if record.name == record_name), None)

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, dict):
            return [wrong_type(self, value, location)]
        discriminator_location = join_location(location, self.discriminator)
        if self.discriminator not in value:
            return [MISSING_FIELD.issue(f"{discriminator_location}: required field is missing; it is one of {', '.join(self.record_names())}", discriminator_location)]
        record = self.record_named(value[self.discriminator])
        if record is None:
            written = value[self.discriminator]
            return [INVALID_VALUE.issue(
                f"{discriminator_location}: {written!r} is not one of {', '.join(self.record_names())}{did_you_mean(written, self.record_names())}",
                discriminator_location,
                closest_suggestion(written, self.record_names(), f'use "{self.discriminator}": "{{match}}"'),
            )]
        return record.field_problems(value, location, known_names={self.discriminator})

    def record_names(self) -> list[str]:
        return [record.name for record in self.records]

    def structures(self) -> Iterator["Record | Variant"]:
        yield self
        for record in self.records:
            for field in record.fields:
                yield from field.shape.structures()


def closest_name(written: object, candidates) -> str | None:
    if not isinstance(written, str):
        return None
    matches = difflib.get_close_matches(written.casefold(), {candidate.casefold(): candidate for candidate in candidates}, n=1, cutoff=0.6)
    if not matches:
        return None
    return next(candidate for candidate in candidates if candidate.casefold() == matches[0])


def did_you_mean(written: object, candidates) -> str:
    match = closest_name(written, candidates)
    return f" (did you mean {match!r}?)" if match else ""


def closest_suggestion(written: object, candidates, template: str = "use {match!r}") -> str | None:
    match = closest_name(written, candidates)
    return template.format(match=match) if match else None


def field_value_problems(field: Field, value: object, location: str) -> list[Issue]:
    if value is None:
        return [MISSING_FIELD.issue(f"{location}: required field is missing", location)] if field.required else []
    return field.shape.problems(value, location)


def require_valid(shape: Shape, value: object, location: str) -> None:
    problems = shape.problems(value, location)
    if problems:
        raise OfficeFailure(*problems)


def wrong_type(shape: Shape, value: object, location: str) -> Issue:
    return WRONG_TYPE.issue(f"{location}: expected {shape.label}, got {json_type_name(value)}", location)


def json_type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "list"
    return "object"


def join_location(location: str, name: str) -> str:
    return f"{location}.{name}" if location else name


def format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
