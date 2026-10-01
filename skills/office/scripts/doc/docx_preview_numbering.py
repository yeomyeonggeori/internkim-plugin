from __future__ import annotations

from dataclasses import dataclass
import re

from docx.oxml.ns import qn

from doc.docx_preview_styles import attribute, paragraph_properties, run_properties


LEVEL_REFERENCE = re.compile(r"%(\d)")
GANADA = "가나다라마바사아자차카타파하"
CHOSUNG = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"
KOREAN_DIGITS = "영일이삼사오육칠팔구"
ENCLOSED_CIRCLE_START = 0x2460
ROMAN_NUMERALS = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
SYMBOL_GLYPHS = {"": "•", "": "▪", "": "➢", "": "✓", "": "❖", "": "■", "": "□", "": "●", "": "→", "o": "◦", "§": "▪"}


@dataclass(frozen=True)
class Label:
    text: str
    paragraph: dict
    run: dict


def readable_symbol(text: str) -> str:
    return "".join(SYMBOL_GLYPHS.get(character, character) for character in text)


def roman(value: int) -> str:
    result = ""
    for amount, numeral in ROMAN_NUMERALS:
        while value >= amount:
            result += numeral
            value -= amount
    return result


def letters(value: int) -> str:
    return chr(ord("A") + (value - 1) % 26) * ((value - 1) // 26 + 1)


def formatted(value: int, number_format: str) -> str:
    formats = {
        "decimal": lambda: str(value),
        "decimalZero": lambda: f"{value:02d}",
        "upperRoman": lambda: roman(value),
        "lowerRoman": lambda: roman(value).lower(),
        "upperLetter": lambda: letters(value),
        "lowerLetter": lambda: letters(value).lower(),
        "ganada": lambda: GANADA[(value - 1) % len(GANADA)],
        "chosung": lambda: CHOSUNG[(value - 1) % len(CHOSUNG)],
        "decimalEnclosedCircle": lambda: chr(ENCLOSED_CIRCLE_START + value - 1) if 1 <= value <= 20 else str(value),
        "koreanDigital": lambda: "".join(KOREAN_DIGITS[int(digit)] for digit in str(value)),
        "decimalFullWidth": lambda: "".join(chr(0xFF10 + int(digit)) for digit in str(value)),
        "none": lambda: "",
    }
    return formats.get(number_format, formats["decimal"])()


class Numbering:
    def __init__(self, numbering_root):
        self.abstracts = {}
        self.instances = {}
        if numbering_root is not None:
            self.abstracts = {abstract.get(qn("w:abstractNumId")): abstract for abstract in numbering_root.iter(qn("w:abstractNum"))}
            self.instances = {instance.get(qn("w:numId")): instance for instance in numbering_root.iter(qn("w:num"))}
        self.counters: dict[str, list[int]] = {}

    def level_definition(self, num_id: str, level: int):
        instance = self.instances.get(num_id)
        if instance is None:
            return None, None
        override = next((item for item in instance.iter(qn("w:lvlOverride")) if item.get(qn("w:ilvl")) == str(level)), None)
        override_level = override.find(qn("w:lvl")) if override is not None else None
        abstract = self.abstracts.get(attribute(instance, "w:abstractNumId", "w:val"))
        definition = override_level if override_level is not None else next((item for item in abstract.iter(qn("w:lvl")) if item.get(qn("w:ilvl")) == str(level)), None) if abstract is not None else None
        start_override = attribute(override, "w:startOverride", "w:val") if override is not None else None
        return definition, start_override

    def label(self, num_id: str | None, level: int) -> Label | None:
        if not num_id or num_id == "0":
            return None
        definition, start_override = self.level_definition(num_id, level)
        if definition is None:
            return None
        values = self.advance(num_id, level, definition, start_override)
        number_format = attribute(definition, "w:numFmt", "w:val") or "decimal"
        template = attribute(definition, "w:lvlText", "w:val") or ""
        text = readable_symbol(template) if number_format == "bullet" else self.filled(num_id, template, values)
        return Label(text, paragraph_properties(definition.find(qn("w:pPr"))), run_properties(definition.find(qn("w:rPr"))))

    def advance(self, num_id: str, level: int, definition, start_override: str | None) -> list[int]:
        key = attribute(self.instances[num_id], "w:abstractNumId", "w:val") or num_id
        start = int(start_override or attribute(definition, "w:start", "w:val") or 1)
        counters = self.counters.setdefault(key, [])
        while len(counters) <= level:
            counters.append(0)
        counters[level] = counters[level] + 1 if counters[level] else start
        del counters[level + 1:]
        return counters

    def filled(self, num_id: str, template: str, values: list[int]) -> str:
        def replacement(match) -> str:
            level = int(match.group(1)) - 1
            definition, _ = self.level_definition(num_id, level)
            number_format = attribute(definition, "w:numFmt", "w:val") if definition is not None else "decimal"
            value = values[level] if level < len(values) and values[level] else 1
            return formatted(value, number_format or "decimal")
        return LEVEL_REFERENCE.sub(replacement, template)
