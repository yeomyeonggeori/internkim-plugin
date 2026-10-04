from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
import os
from pathlib import Path

from core.host_contract import RUNTIME_CONTEXT_VARIABLE
from core.office_result import ERROR, IssueKind, OfficeFailure


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
                f"the runtime context names no company profile: company_info_get has not answered in this task",
                "company",
                f"call company_info_get with language {language!r}, then run the same command again; the runtime records the profile it answers",
            ))
        found = self.companies.get(language) or next(iter(self.companies.values()), "")
        return company_profile(found) if isinstance(found, str) and found else {}

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


def load_runtime_context() -> RuntimeContext | None:
    path = os.environ.get(RUNTIME_CONTEXT_VARIABLE, "").strip()
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as context_file:
        document = json.load(context_file)
    requester = document.get("requester") or {}
    return RuntimeContext(
        requester_name=str(requester.get("name") or ""),
        requester_email=str(requester.get("email") or ""),
        today=date.fromisoformat(document["today"]) if document.get("today") else None,
        companies=document.get("company") or {},
        registered_documents=tuple(document.get("registeredDocuments") or ()),
        attachments=tuple(document.get("attachments") or ()),
    )
