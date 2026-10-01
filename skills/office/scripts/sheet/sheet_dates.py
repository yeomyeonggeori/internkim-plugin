from __future__ import annotations

import calendar
import datetime
import math

from openpyxl.utils.datetime import to_excel

from sheet_semantics import INVALID_NUMBER, ExcelError


SERIAL_EPOCH = datetime.date(1899, 12, 30)
FIRST_UNAMBIGUOUS_DATE = datetime.date(1900, 3, 1)
LAST_DATE = datetime.date(9999, 12, 31)
TWO_DIGIT_YEAR_LIMIT = 1900


def serial_from_date(day: datetime.date) -> int:
    if day < FIRST_UNAMBIGUOUS_DATE:
        raise NotImplementedError("a date before March 1900 falls on Excel's leap year 1900")
    return (day - SERIAL_EPOCH).days


def date_from_serial(serial: float) -> datetime.date:
    if serial < 0:
        raise ExcelError(INVALID_NUMBER, "a negative date serial")
    whole = math.floor(serial)
    if whole > serial_from_date(LAST_DATE):
        raise ExcelError(INVALID_NUMBER, "a date after 9999")
    if whole < serial_from_date(FIRST_UNAMBIGUOUS_DATE):
        raise NotImplementedError("a date before March 1900 falls on Excel's leap year 1900")
    return SERIAL_EPOCH + datetime.timedelta(days=whole)


def serial_from_parts(year: int, month: int, day: int) -> int:
    if not 0 <= year <= LAST_DATE.year:
        raise ExcelError(INVALID_NUMBER, "a year outside 0 to 9999")
    full_year = year + TWO_DIGIT_YEAR_LIMIT if year < TWO_DIGIT_YEAR_LIMIT else year
    first_year, month_index = divmod(full_year * 12 + month - 1, 12)
    if not 1 <= first_year <= LAST_DATE.year:
        raise ExcelError(INVALID_NUMBER, "a date outside 1900 to 9999")
    try:
        result = datetime.date(first_year, month_index + 1, 1) + datetime.timedelta(days=day - 1)
    except OverflowError as error:
        raise ExcelError(INVALID_NUMBER, "a date outside 1900 to 9999") from error
    return serial_from_date(result)


def months_later(day: datetime.date, months: int) -> datetime.date:
    year, month_index = divmod(day.year * 12 + day.month - 1 + months, 12)
    if not 1 <= year <= LAST_DATE.year:
        raise ExcelError(INVALID_NUMBER, "a date outside 1900 to 9999")
    return datetime.date(year, month_index + 1, min(day.day, calendar.monthrange(year, month_index + 1)[1]))


def month_end(day: datetime.date) -> datetime.date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def weekday(day: datetime.date, return_type: int) -> int:
    if return_type == 1:
        return day.isoweekday() % 7 + 1
    if return_type == 2:
        return day.isoweekday()
    if return_type == 3:
        return day.isoweekday() - 1
    raise NotImplementedError("only weekday numberings 1, 2 and 3 are evaluated")


def whole_months_between(start: datetime.date, end: datetime.date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    return months - 1 if end.day < start.day else months


def difference(start: datetime.date, end: datetime.date, unit: str) -> int:
    if start > end:
        raise ExcelError(INVALID_NUMBER, "the start date is after the end date")
    if unit == "D":
        return (end - start).days
    if unit == "M":
        return whole_months_between(start, end)
    if unit == "Y":
        return whole_months_between(start, end) // 12
    if unit == "YM":
        return whole_months_between(start, end) % 12
    if unit in ("MD", "YD"):
        raise NotImplementedError("DATEDIF MD and YD are not evaluated")
    raise ExcelError(INVALID_NUMBER, f"DATEDIF has no unit {unit!r}")


def today_serial() -> int:
    return serial_from_date(datetime.date.today())


def now_serial() -> float:
    return to_excel(datetime.datetime.now())
