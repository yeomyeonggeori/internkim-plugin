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
    maximum_length: int | None = None

    @property
    def label(self) -> str:
        noun = "non-empty text" if self.non_empty else "text"
        return f"{noun} of at most {self.maximum_length} characters" if self.maximum_length else noun

    def problems(self, value: object, location: str) -> list[Issue]:
        if not isinstance(value, str):
            return [wrong_type(self, value, location)]
        if self.non_empty and not value.strip():
            return [MISSING_FIELD.issue(f"{location}: must not be empty", location)]
        if self.maximum_length is not None and len(value) > self.maximum_length:
            return [INVALID_VALUE.issue(f"{location}: {len(value)} characters, more than the {self.maximum_length} this field holds", location, f"shorten it to {self.maximum_length} characters or fewer")]
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
        return [color_problem(value, self.label, location)]


def color_problem(value: str, label: str, location: str) -> Issue:
    named = named_color_hex(value)
    if named is None:
        return INVALID_VALUE.issue(f"{location}: {value!r} is not {label}", location)
    return INVALID_VALUE.issue(f"{location}: {value!r} is a color name, and this field takes {label}", location, f'use "{named}" for {value}')


def named_color_hex(value: str) -> str | None:
    from PIL import ImageColor

    named = ImageColor.colormap.get(value.strip().casefold().replace(" ", ""))
    return named.lstrip("#").upper() if named else None


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
        kind_matches = [problems for problems in candidate_problems if not is_kind_mismatch(problems, location)]
        if len(kind_matches) == 1:
            return kind_matches[0]
        return [wrong_type(self, value, location)]

    def structures(self) -> Iterator["Record | Variant"]:
        for shape in self.shapes:
            yield from shape.structures()


def is_kind_mismatch(problems: list[Issue], location: str) -> bool:
    return len(problems) == 1 and problems[0].kind is WRONG_TYPE and problems[0].location == location


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
        unknown = [name for name in value if name not in field_names and not self.keeps_other_fields]
        problems = [
            UNKNOWN_FIELD.issue(
                f"{join_location(location, name)}: {self.name} has no field {name!r}{did_you_mean(name, field_names)}; it takes {', '.join(sorted(field_names))}",
                join_location(location, name),
                closest_suggestion(name, field_names, "rename the field to {match!r}"),
            )
            for name in unknown
        ]
        renamed = {closest_name(name, field_names) for name in unknown}
        for field in self.fields:
            if field.name in renamed and field.name not in value:
                continue
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


NAME_SYNONYMS = {
    "name": ("title",),
    "title": ("name",),
    "data": ("rows", "range", "values"),
    "cells": ("range", "values"),
    "chartType": ("type",),
    "kind": ("type",),
    "sheetName": ("sheet",),
    "tab": ("sheet",),
    "rowFields": ("row",),
    "columnField": ("column",),
    "text": ("value",),
    "content": ("text", "value"),
    "column": ("bar",),
    "avg": ("average",),
    "mean": ("average",),
}


def closest_name(written: object, candidates) -> str | None:
    if not isinstance(written, str):
        return None
    synonym = synonym_in(written, candidates)
    if synonym is not None:
        return synonym
    agreeing = [candidate for candidate in candidates if words_agree(written, candidate)]
    ranked = sorted(agreeing, key=lambda candidate: name_similarity(written, candidate), reverse=True)
    if not ranked:
        return None
    if len(ranked) > 1 and name_similarity(written, ranked[0]) == name_similarity(written, ranked[1]):
        return None
    return ranked[0]


def synonym_in(written: str, candidates) -> str | None:
    present = {candidate.casefold(): candidate for candidate in candidates}
    meanings = NAME_SYNONYMS.get(written, NAME_SYNONYMS.get(written.casefold(), ()))
    return next((present[meaning.casefold()] for meaning in meanings if meaning.casefold() in present), None)


def words_agree(written: str, candidate: str) -> bool:
    written_words, candidate_words = name_words(written), name_words(candidate)
    if not written_words:
        return False
    if difflib.SequenceMatcher(None, "".join(written_words), "".join(candidate_words)).ratio() >= 0.85:
        return True
    if len(candidate_words) > len(written_words) + 1:
        return False
    return all(any(words_are_close(written_word, candidate_word) for candidate_word in candidate_words) for written_word in written_words)


def name_words(name: str) -> list[str]:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])", " ", name)
    return [word.casefold() for word in re.split(r"[\s_.-]+", separated) if word]


def words_are_close(first: str, second: str) -> bool:
    return difflib.SequenceMatcher(None, first, second).ratio() >= 0.75 or edit_distance(first, second) <= 1


def edit_distance(first: str, second: str) -> int:
    previous = list(range(len(second) + 1))
    for first_index, first_character in enumerate(first, start=1):
        current = [first_index]
        for second_index, second_character in enumerate(second, start=1):
            current.append(min(previous[second_index] + 1, current[second_index - 1] + 1, previous[second_index - 1] + (first_character != second_character)))
        previous = current
    return previous[-1]


def name_similarity(written: str, candidate: str) -> float:
    return difflib.SequenceMatcher(None, written.casefold(), candidate.casefold()).ratio()


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
