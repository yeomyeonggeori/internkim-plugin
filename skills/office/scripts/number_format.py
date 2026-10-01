from __future__ import annotations

from dataclasses import dataclass
import datetime
import re


SECTION_COLORS = {"black": "#000000", "blue": "#0000ff", "cyan": "#00ffff", "green": "#00ff00", "magenta": "#ff00ff", "red": "#ff0000", "white": "#ffffff", "yellow": "#ffff00"}
COLOR_TAG = re.compile(r"\[(black|blue|cyan|green|magenta|red|white|yellow|color\d+)\]", re.IGNORECASE)
CONDITION_TAG = re.compile(r"\[[<>=][^\]]*\]")
CURRENCY_TAG = re.compile(r"\[\$([^\]-]*)(-[^\]]*)?\]")
ELAPSED_TAG = re.compile(r"\[(h+|m+|s+)\]", re.IGNORECASE)
DATE_TOKEN = re.compile(r"yyyy|yy|mmmmm|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|am/pm|a/p|0+|\.0+", re.IGNORECASE)
DATE_LETTERS = set("ymdhs")
KOREAN_DATE_FORMAT = "yyyy-mm-dd"
KOREAN_DATE_TIME_FORMAT = "yyyy-mm-dd hh:mm"
BUILTIN_DATE_FORMATS = {"mm-dd-yy": KOREAN_DATE_FORMAT, "m/d/yy": KOREAN_DATE_FORMAT, "m/d/yy h:mm": KOREAN_DATE_TIME_FORMAT}
GENERAL_SIGNIFICANT_DIGITS = 10
WEEKDAYS = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")
EXCEL_EPOCH = datetime.datetime(1899, 12, 30)


@dataclass(frozen=True)
class Displayed:
    text: str
    color: str | None = None
    is_number: bool = False


def displayed(value, number_format: str | None) -> Displayed:
    number_format = BUILTIN_DATE_FORMATS.get(number_format or "General", number_format or "General")
    if value is None:
        return Displayed("")
    if isinstance(value, bool):
        return Displayed("TRUE" if value else "FALSE")
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return Displayed(formatted_date(value, date_section(number_format)), is_number=True)
    if isinstance(value, (int, float)):
        return formatted_number(float(value), number_format)
    return formatted_text(str(value), number_format)


def sections(number_format: str) -> list[str]:
    parts, current, quoted = [], "", False
    for character in number_format:
        if character == '"':
            quoted = not quoted
        if character == ";" and not quoted:
            parts.append(current)
            current = ""
            continue
        current += character
    return [*parts, current]


def section_color(section: str) -> tuple[str, str | None]:
    match = COLOR_TAG.search(section)
    color = SECTION_COLORS.get(match.group(1).lower()) if match else None
    return COLOR_TAG.sub("", section), color


def formatted_text(text: str, number_format: str) -> Displayed:
    parts = sections(number_format)
    if len(parts) < 4 and "@" not in parts[-1]:
        return Displayed(text)
    section, color = section_color(parts[3] if len(parts) >= 4 else parts[-1])
    return Displayed(literal_text(section).replace("@", text), color)


def formatted_number(value: float, number_format: str) -> Displayed:
    parts = sections(number_format)
    section = parts[0]
    signed = value < 0
    if value < 0 and len(parts) > 1:
        section, signed = parts[1], False
    elif value == 0 and len(parts) > 2:
        section = parts[2]
    section, color = section_color(CONDITION_TAG.sub("", section))
    if is_date_section(section):
        return Displayed(formatted_date(EXCEL_EPOCH + datetime.timedelta(days=value), section), color, True)
    magnitude = abs(value) if len(parts) > 1 and value < 0 else value
    text = general_number(magnitude) if section.strip().lower() in ("general", "") else number_text(abs(magnitude), section)
    return Displayed(("-" if signed and section.strip().lower() not in ("general", "") else "") + text, color, True)


def general_number(value: float) -> str:
    if value == int(value) and abs(value) < 1e11:
        return str(int(value))
    return f"{value:.{GENERAL_SIGNIFICANT_DIGITS}g}"


def literal_text(section: str) -> str:
    text = CURRENCY_TAG.sub(lambda match: match.group(1), section)
    result, index = "", 0
    while index < len(text):
        character = text[index]
        if character == '"':
            end = text.find('"', index + 1)
            end = len(text) if end < 0 else end
            result += text[index + 1:end]
            index = end + 1
            continue
        if character == "\\" and index + 1 < len(text):
            result += text[index + 1]
            index += 2
            continue
        if character == "_" and index + 1 < len(text):
            result += " "
            index += 2
            continue
        if character == "*" and index + 1 < len(text):
            index += 2
            continue
        result += character
        index += 1
    return result


def number_text(value: float, section: str) -> str:
    text = literal_text(section)
    placeholder_positions = [index for index, character in enumerate(text) if character in "0#?"]
    if not placeholder_positions:
        return text
    start, end = placeholder_positions[0], placeholder_positions[-1] + 1
    while end < len(text) and text[end] == ",":
        end += 1
    if end + 1 < len(text) and text[end] in "Ee" and text[end + 1] in "+-":
        end += 2
        while end < len(text) and text[end] in "0#":
            end += 1
    prefix, pattern, suffix = text[:start], text[start:end], text[end:]
    return prefix + formatted_digits(value * 100 ** literal_text_without_quotes(section).count("%"), pattern) + suffix


def formatted_digits(value: float, pattern: str) -> str:
    mantissa, exponent_marker, exponent_pattern = pattern.upper().partition("E")
    if exponent_marker:
        decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
        digits, _, exponent = f"{value:.{decimals}E}".partition("E")
        width = max(1, len(exponent_pattern) - 1)
        return f"{digits}E{exponent[0]}{abs(int(exponent)):0{width}d}"
    scaling_commas = len(pattern) - len(pattern.rstrip(","))
    core = pattern.rstrip(",")
    integer_part, _, decimal_part = core.partition(".")
    decimals = sum(1 for character in decimal_part if character in "0#?")
    required_decimals = sum(1 for character in decimal_part if character == "0")
    minimum_integer_digits = sum(1 for character in integer_part if character == "0")
    whole, _, fraction = f"{value / 1000 ** scaling_commas:.{decimals}f}".partition(".")
    if decimals > required_decimals:
        fraction = fraction.rstrip("0").ljust(required_decimals, "0")
    whole = whole.lstrip("0").rjust(minimum_integer_digits, "0")
    if "," in integer_part and whole:
        whole = f"{int(whole):,}"
    return whole + (f".{fraction}" if fraction else "")


def is_date_section(section: str) -> bool:
    text = literal_text_without_quotes(section).lower()
    return any(letter in text for letter in DATE_LETTERS) and "general" not in text


def literal_text_without_quotes(section: str) -> str:
    return re.sub(r'"[^"]*"|\\.|\[[^\]]*\]', "", section)


def date_section(number_format: str) -> str:
    section = sections(number_format)[0]
    return section if is_date_section(section) else KOREAN_DATE_FORMAT


def formatted_date(value, section: str) -> str:
    moment = value if isinstance(value, datetime.datetime) else datetime.datetime.combine(value, datetime.time()) if isinstance(value, datetime.date) else datetime.datetime.combine(EXCEL_EPOCH.date(), value)
    section = ELAPSED_TAG.sub(lambda match: match.group(1), CURRENCY_TAG.sub("", section_color(section)[0]))
    has_meridiem = "am/pm" in section.lower() or "a/p" in section.lower()
    tokens = date_tokens(section)
    return "".join(date_token_text(token, kind, moment, has_meridiem) for token, kind in tokens)


def date_tokens(section: str) -> list[tuple[str, str]]:
    tokens, index = [], 0
    while index < len(section):
        character = section[index]
        if character == '"':
            end = section.find('"', index + 1)
            end = len(section) if end < 0 else end
            tokens.append((section[index + 1:end], "literal"))
            index = end + 1
            continue
        if character == "\\" and index + 1 < len(section):
            tokens.append((section[index + 1], "literal"))
            index += 2
            continue
        match = DATE_TOKEN.match(section, index)
        if match:
            tokens.append((match.group(0), "date"))
            index = match.end()
            continue
        tokens.append((character, "literal"))
        index += 1
    return minutes_marked(tokens)


def minutes_marked(tokens: list[tuple[str, str]]) -> list[tuple[str, str]]:
    marked = list(tokens)
    date_indexes = [index for index, (_, kind) in enumerate(marked) if kind == "date"]
    for position, index in enumerate(date_indexes):
        token = marked[index][0].lower()
        if token not in ("m", "mm"):
            continue
        previous = marked[date_indexes[position - 1]][0].lower() if position else ""
        following = marked[date_indexes[position + 1]][0].lower() if position + 1 < len(date_indexes) else ""
        if previous.startswith("h") or following.startswith("s"):
            marked[index] = (marked[index][0], "minute")
    return marked


def date_token_text(token: str, kind: str, moment: datetime.datetime, has_meridiem: bool) -> str:
    if kind == "literal":
        return token
    if kind == "minute":
        return f"{moment.minute:0{len(token)}d}"
    lowered = token.lower()
    hour = moment.hour % 12 or 12 if has_meridiem else moment.hour
    values = {
        "yyyy": f"{moment.year:04d}", "yy": f"{moment.year % 100:02d}",
        "mmmmm": moment.strftime("%B")[0], "mmmm": f"{moment.month}월", "mmm": f"{moment.month}월", "mm": f"{moment.month:02d}", "m": str(moment.month),
        "dddd": WEEKDAYS[moment.weekday()], "ddd": WEEKDAYS[moment.weekday()][0], "dd": f"{moment.day:02d}", "d": str(moment.day),
        "hh": f"{hour:02d}", "h": str(hour), "ss": f"{moment.second:02d}", "s": str(moment.second),
        "am/pm": "오전" if moment.hour < 12 else "오후", "a/p": "오전" if moment.hour < 12 else "오후",
    }
    if lowered.startswith(".0"):
        return "." + f"{moment.microsecond / 1e6:.{len(token) - 1}f}"[2:]
    return values.get(lowered, token)
