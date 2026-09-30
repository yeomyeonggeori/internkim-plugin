from __future__ import annotations

import re

from display_width import display_width


QUOTED_TEXT = re.compile(r'"([^"]*)"')
CURRENCY_BRACKET = re.compile(r"\[\$([^\]-]*)[^\]]*\]")
OTHER_BRACKET = re.compile(r"\[[^\]]*\]")
PADDING = re.compile(r"_.")
FILL = re.compile(r"\*.")
ESCAPED = re.compile(r"\\(.)")
PLACEHOLDERS = re.compile(r"[0#?.,]")
TRAILING_SCALING_COMMAS = re.compile(r"[0#?](,+)(?![0#?,])")


def displayed_number_width(value: float, number_format: str) -> int:
    sections = number_format.split(";")
    section = sections[1] if value < 0 and len(sections) > 1 else sections[0]
    sign_width = 1 if value < 0 and len(sections) == 1 else 0
    cleaned = cleaned_section(section)
    if "general" in cleaned.lower():
        return 0
    return sign_width + digits_width(abs(value), cleaned) + display_width(PLACEHOLDERS.sub("", cleaned))


def cleaned_section(section: str) -> str:
    text = ESCAPED.sub(lambda match: match.group(1), section)
    text = QUOTED_TEXT.sub(lambda match: match.group(1), text)
    text = CURRENCY_BRACKET.sub(lambda match: match.group(1), text)
    text = OTHER_BRACKET.sub("", text)
    text = FILL.sub("", text)
    return PADDING.sub(" ", text)


def digits_width(value: float, cleaned: str) -> int:
    scaled = value * 100 if "%" in cleaned else value
    scaling = TRAILING_SCALING_COMMAS.search(cleaned)
    if scaling:
        scaled = scaled / 1000 ** len(scaling.group(1))
    decimals = len(re.findall(r"[0#?]", cleaned.split(".", 1)[1])) if "." in cleaned else 0
    uses_thousands = bool(re.search(r"[0#?],[0#?]", cleaned))
    return len(f"{scaled:,.{decimals}f}" if uses_thousands else f"{scaled:.{decimals}f}")
