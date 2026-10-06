from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path

from core.office_result import ERROR, IssueKind, OfficeFailure
from host.task_context import TaskContext, load_task_context


COMPANY_NOT_READ = IssueKind("COMPANY_NOT_READ", ERROR, "no company profile was read in this task, so the letterhead has nothing to print", "call company_info_get for the document's language, then run the same command again")


@dataclass(frozen=True)
class RuntimeContext:
    requester_name: str = ""
    requester_email: str = ""
    today: date | None = None
    companies: dict = field(default_factory=dict)
    registered_documents: tuple = ()
    attachments: tuple = ()

    def company(self, language: str) -> dict:
        if not self.companies:
            raise OfficeFailure(COMPANY_NOT_READ.issue(
                "the task context records no company profile: company_info_get has not answered in this task",
                "company",
                f"call company_info_get with language {language!r}, then run the same command again; the runtime records the profile it answers",
            ))
        found = self.companies.get(language) or next(iter(self.companies.values()), "")
        return company_profile(found) if isinstance(found, str) and found else {}

    def font_paths(self) -> list[Path]:
        attached = [Path(attachment["path"]) for attachment in self.attachments if isinstance(attachment, dict) and attachment.get("path")]
        return [path for path in attached if path.suffix.casefold() in FONT_SUFFIXES]

    def brand_font(self) -> str:
        profiles = [company_profile(path) for path in self.companies.values() if isinstance(path, str) and path]
        return next((str(profile["brandFont"]).strip() for profile in profiles if str(profile.get("brandFont") or "").strip()), "")

    def logo_path(self) -> Path | None:
        profiles = [company_profile(path) for path in self.companies.values() if isinstance(path, str) and path]
        logos = [Path(profile["logoPath"]) for profile in profiles if profile.get("logoPath")]
        return next((logo for logo in logos if logo.is_file()), None)

    def document_number(self) -> str:
        numbers = [document.get("documentNumber") for document in self.registered_documents if document.get("documentNumber")]
        return numbers[-1] if numbers else ""

    def value(self, name: str, language: str) -> object:
        if name == "today":
            return self.today
        if name == "requester":
            return self.requester_name
        if name == "requesterEmail":
            return self.requester_email
        if name == "document.number":
            return self.document_number()
        if name.startswith("company."):
            return company_value(self.company(language), name.removeprefix("company."))
        return None


FONT_SUFFIXES = (".ttf", ".otf", ".woff2")
COMPANY_IMAGES = (("sealImage", "stampPath"), ("logoImage", "logoPath"))


def company_profile(path_text: str) -> dict:
    path = Path(path_text).expanduser()
    if not path.is_file():
        return {}
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        return {}
    images = {printed: str(path.parent / Path(str(profile[kept])).name) for kept, printed in COMPANY_IMAGES if str(profile.get(kept) or "").strip()}
    return profile | images


def company_value(company: dict, name: str) -> str:
    if name == "registrationNumber":
        attributes = company.get("legalAttributes") or []
        return str(attributes[0].get("value", "")) if attributes else ""
    return str(company.get(name) or "")


COMPANY_INFO_TOOL = "company_info_get"
DOCUMENT_REGISTER_TOOL = "company_document_register"
COMPANY_PROFILE_FILE = "company-profile.json"
DEFAULT_PROFILE_LANGUAGE = "ko"


def load_runtime_context() -> RuntimeContext | None:
    context = load_task_context()
    return runtime_context_of(context) if context is not None else None


def runtime_context_of(context: TaskContext) -> RuntimeContext:
    return RuntimeContext(
        requester_name=context.requester_name,
        requester_email=context.requester_email,
        today=context.today,
        companies=company_profiles(context),
        registered_documents=registered_documents(context),
        attachments=tuple({"name": attachment.name, "path": attachment.path} for attachment in context.attachments if attachment.path),
    )


def company_profiles(context: TaskContext) -> dict:
    profiles = {}
    for record in context.records_of(COMPANY_INFO_TOOL):
        profile_path = record.file_named(COMPANY_PROFILE_FILE)
        if profile_path:
            profiles[str(record.input.get("language") or DEFAULT_PROFILE_LANGUAGE)] = profile_path
    return profiles


def registered_documents(context: TaskContext) -> tuple:
    numbers = [record.result.get("documentNumber") for record in context.records_of(DOCUMENT_REGISTER_TOOL) if isinstance(record.result, dict)]
    return tuple({"documentNumber": str(number)} for number in numbers if isinstance(number, str) and number.strip())
