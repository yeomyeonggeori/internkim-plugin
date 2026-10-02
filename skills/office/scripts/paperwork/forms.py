from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.office_result import INVALID_VALUE, MISSING_FIELD, OfficeFailure
from core.office_routing import FORM_NAME
from core.office_schema import closest_name
from paperwork.jurisdictions import Jurisdiction, find_jurisdiction, jurisdiction_codes


SKILL_PATH = Path(__file__).resolve().parents[2]
SPECIFICATIONS_PATH = SKILL_PATH / "references" / "paperwork"
TEMPLATES_ROOT = SKILL_PATH / "assets" / "templates"


@dataclass(frozen=True)
class Form:
    jurisdiction: Jurisdiction
    slug: str

    @property
    def name(self) -> str:
        return f"{self.jurisdiction.code}/{self.slug}"

    @property
    def specification_path(self) -> Path:
        return SPECIFICATIONS_PATH / self.jurisdiction.code / f"{self.slug}.md"

    @property
    def template_path(self) -> Path | None:
        path = TEMPLATES_ROOT / self.jurisdiction.code / f"{self.slug}.docx"
        return path if path.is_file() else None


def form_slugs(code: str) -> list[str]:
    return sorted(path.stem for path in (SPECIFICATIONS_PATH / code).glob("*.md"))


def form_names() -> list[str]:
    return [f"{code}/{slug}" for code in jurisdiction_codes() for slug in form_slugs(code)]


def require_form(name: object, location: str) -> Form:
    if not isinstance(name, str) or not name.strip():
        raise OfficeFailure(MISSING_FIELD.issue(f"{location}: name the form, such as kr/quote", location, suggestion=f"one of: {', '.join(form_names())}"))
    code, _, slug = name.partition("/")
    jurisdiction = find_jurisdiction(code)
    if not FORM_NAME.fullmatch(name) or jurisdiction is None or slug not in form_slugs(code):
        meant = closest_name(name, form_names())
        suggestion = f"use {meant}" if meant else f"a form is <jurisdiction>/<form>; jurisdictions: {', '.join(jurisdiction_codes())}; office guide form lists every form"
        raise OfficeFailure(INVALID_VALUE.issue(f"{location}: {name!r} is not a bundled form", location, suggestion))
    return Form(jurisdiction, slug)


def form_of(values: dict, location: str) -> Form:
    return require_form(values.get("form"), f"{location}.form")
