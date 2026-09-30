from typing import Callable

from amounts import korean_number_words, parse_amount, truncate_to_won
from template_fields import template_fields, template_list_fields


DEFAULT_VALUES = {
    "employment-contract": {
        "otherAllowances": "없음",
        "insurances": "☑ 고용보험  ☑ 산재보험  ☑ 국민연금  ☑ 건강보험",
        "employeeAddress": "",
        "employeePhone": "",
        "endDate": "",
    },
    "service-agreement": {"penaltyRate": "1.25", "warrantyMonths": "3"},
    "nda": {"termYears": "5", "survivalYears": "3", "penaltyAmount": ""},
    "mou": {"termYears": "2"},
    "offer-letter": {"equity": "", "probationNote": ""},
}


def derive_korean_total(context: dict) -> str | None:
    amount = parse_amount(context.get("totalAmount", ""))
    return None if amount is None else korean_number_words(truncate_to_won(amount))


DERIVED_VALUES: dict[str, dict[str, Callable[[dict], str | None]]] = {
    "service-agreement": {"totalAmountKorean": derive_korean_total},
}


def default_values(template_name: str) -> dict[str, str]:
    return DEFAULT_VALUES.get(template_name, {})


def derived_values(template_name: str) -> dict[str, Callable[[dict], str | None]]:
    return DERIVED_VALUES.get(template_name, {})


def scalar_fields(template_name: str) -> list[str]:
    lists = set(template_list_fields(template_name))
    return [field for field in template_fields(template_name) if field not in lists]


def caller_fields(template_name: str) -> list[str]:
    defaults = default_values(template_name)
    derived = derived_values(template_name)
    return [field for field in scalar_fields(template_name) if field not in defaults and field not in derived]


def non_empty_fields(template_name: str) -> list[str]:
    blank_allowed = {field for field, value in default_values(template_name).items() if value == ""}
    return [field for field in scalar_fields(template_name) if field not in blank_allowed]


def complete_context(template_name: str, context: dict) -> dict:
    completed = {**default_values(template_name), **context}
    for field, derive in derived_values(template_name).items():
        if str(completed.get(field, "")).strip() == "":
            completed[field] = derive(completed)
    return completed
