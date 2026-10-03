from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re

from core.office_result import INVALID_VALUE, WRONG_TYPE, OfficeFailure


VALUE_TYPES = ("text", "person", "organization", "date", "amount", "quantity", "percent")
NUMBER_TYPES = ("amount", "quantity", "percent")
BLANK = "__________"
FORMATTED_NUMBER = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
KOREAN_UNIT = re.compile(r"[가-힣]")
ENGLISH_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
DATE_SHAPES = "YYYY-MM-DD, YYYY-MM-DD HH:MM, YYYY-MM, HH:MM, or two of them as start/end"


def parse_number(value: object, location: str) -> Decimal:
    if isinstance(value, bool):
        raise OfficeFailure(WRONG_TYPE.issue(f"{location}: expected a number, got true/false", location))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str) and FORMATTED_NUMBER.fullmatch(value.strip()):
        return Decimal(value.strip().replace(",", ""))
    raise OfficeFailure(WRONG_TYPE.issue(f"{location}: expected a number such as 1350000, got {value!r}", location, "write the number alone; the unit goes in unit and the renderer adds separators"))


def grouped(number: Decimal, decimals: int | None = None) -> str:
    if decimals is not None:
        return f"{number:,.{decimals}f}"
    normalized = number.normalize()
    if normalized == normalized.to_integral_value():
        return f"{int(normalized):,}"
    return f"{normalized:,f}"


def format_amount(number: Decimal, unit: str, language: str) -> str:
    code = unit.strip().upper()
    if code == "KRW":
        return f"{grouped(number)}원" if language == "ko" else f"KRW {grouped(number)}"
    if code in CURRENCY_SYMBOLS:
        decimals = 0 if number == number.to_integral_value() else 2
        return f"{CURRENCY_SYMBOLS[code]}{grouped(number, decimals)}"
    return with_unit(grouped(number), unit)


def with_unit(number_text: str, unit: str) -> str:
    unit = unit.strip()
    if not unit:
        return number_text
    return f"{number_text}{unit}" if KOREAN_UNIT.match(unit) else f"{number_text} {unit}"


def format_number_value(value_type: str, value: object, unit: str, language: str, location: str) -> str:
    number = parse_number(value, location)
    if value_type == "amount":
        return format_amount(number, unit, language)
    if value_type == "percent":
        return f"{grouped(number)}%"
    return with_unit(grouped(number), unit)


def parse_moment(text: str, location: str) -> date | datetime | tuple:
    text = text.strip()
    for shape, parse in (
        (r"\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}", lambda value: datetime.strptime(value, "%Y-%m-%d %H:%M")),
        (r"\d{4}-\d{2}-\d{2}", date.fromisoformat),
        (r"\d{4}-\d{2}", lambda value: ("month", int(value[:4]), int(value[5:7]))),
        (r"\d{1,2}:\d{2}", lambda value: ("time", value)),
    ):
        if re.fullmatch(shape, text):
            try:
                return parse(text)
            except ValueError:
                break
    raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {text!r} is not a date in {DATE_SHAPES}", location, "write the date as YYYY-MM-DD; the renderer writes it in the document's language"))


def format_moment(moment, language: str) -> str:
    if isinstance(moment, tuple) and moment[0] == "time":
        return moment[1]
    if isinstance(moment, tuple):
        _, year, month = moment
        return f"{year}년 {month}월" if language == "ko" else f"{ENGLISH_MONTHS[month - 1]} {year}"
    day_text = f"{moment.year}년 {moment.month}월 {moment.day}일" if language == "ko" else f"{ENGLISH_MONTHS[moment.month - 1]} {moment.day}, {moment.year}"
    if isinstance(moment, datetime):
        return f"{day_text} {moment.hour:02d}:{moment.minute:02d}"
    return day_text


def format_date(value: object, language: str, location: str) -> str:
    if isinstance(value, date):
        return format_moment(value, language)
    if not isinstance(value, str):
        raise OfficeFailure(WRONG_TYPE.issue(f"{location}: expected a date in {DATE_SHAPES}, got {value!r}", location))
    if "/" in value:
        start, end = (parse_moment(part, location) for part in value.split("/", 1))
        if start == end:
            return format_moment(start, language)
        return f"{format_moment(start, language)} ~ {format_moment(end, language)}" if language == "ko" else f"{format_moment(start, language)} – {format_moment(end, language)}"
    return format_moment(parse_moment(value, location), language)


def format_value(value_type: str, value: object, unit: str, language: str, location: str) -> str:
    if value_type in NUMBER_TYPES:
        return format_number_value(value_type, value, unit or "", language, location)
    if value_type == "date":
        return format_date(value, language, location)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return grouped(Decimal(str(value)))
    if not isinstance(value, str):
        raise OfficeFailure(WRONG_TYPE.issue(f"{location}: expected text, got {value!r}", location))
    return value.strip()


def is_number_type(value_type: str) -> bool:
    return value_type in NUMBER_TYPES


def numeric_value(value: object, location: str) -> Decimal | None:
    if value is None:
        return None
    try:
        return parse_number(value, location)
    except (OfficeFailure, InvalidOperation):
        return None
