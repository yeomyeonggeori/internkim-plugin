from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Callable

from paperwork.amounts import korean_amount_in_words, korean_amount_line, korean_number_words


@dataclass(frozen=True)
class Labels:
    document_number: str
    recipient: str
    registration_number: str
    representative_title: str
    seal_mark: str


@dataclass(frozen=True)
class ItemColumns:
    quantity: str
    unit_price: str
    amount: str
    tax: str


@dataclass(frozen=True)
class Money:
    currency: str
    minor_unit_digits: int
    rounding: str
    rounding_rule: str

    def rounded(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal(1).scaleb(-self.minor_unit_digits), rounding=self.rounding)


@dataclass(frozen=True)
class AmountInWords:
    label: str
    written: Callable[[int], str]
    spoken: Callable[[int], str]
    line: Callable[[int], str]
    example: str
    equivalents: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    name: str
    language: str
    labels: Labels
    columns: ItemColumns
    money: Money
    tax_rate_percent: Decimal | None
    amount_in_words: AmountInWords | None
    date_format: str


JURISDICTIONS = (
    Jurisdiction(
        code="intl",
        name="international, the default",
        language="en",
        labels=Labels(document_number="No.", recipient="To", registration_number="Registration No.", representative_title="Representative", seal_mark=""),
        columns=ItemColumns(quantity="Qty", unit_price="Unit price", amount="Amount", tax="Tax"),
        money=Money(currency="", minor_unit_digits=2, rounding=ROUND_HALF_UP, rounding_rule="every computed amount rounds half up to the cent"),
        tax_rate_percent=None,
        amount_in_words=None,
        date_format="MMMM d, y",
    ),
    Jurisdiction(
        code="kr",
        name="Korea",
        language="ko",
        labels=Labels(document_number="문서번호", recipient="수신", registration_number="사업자등록번호", representative_title="대표", seal_mark="(인)"),
        columns=ItemColumns(quantity="수량", unit_price="단가", amount="공급가액", tax="세액"),
        money=Money(currency="KRW", minor_unit_digits=0, rounding=ROUND_DOWN, rounding_rule="every computed amount drops its fraction below one won (truncates toward zero)"),
        tax_rate_percent=Decimal(10),
        amount_in_words=AmountInWords(label="합계금액", written=korean_amount_in_words, spoken=korean_number_words, line=korean_amount_line, example="\"일금 일백만원정\" for 1,000,000; a trailing 整 counts as 정", equivalents=(("整", "정"),)),
        date_format="y년 M월 d일",
    ),
)
DEFAULT_JURISDICTION = JURISDICTIONS[0]


def jurisdiction_codes() -> list[str]:
    return [jurisdiction.code for jurisdiction in JURISDICTIONS]


def find_jurisdiction(code: str) -> Jurisdiction | None:
    return next((jurisdiction for jurisdiction in JURISDICTIONS if jurisdiction.code == code), None)
