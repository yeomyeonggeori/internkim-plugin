from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LETTERHEAD_FIELDS = ("name", "representative", "address", "phone", "email")


@dataclass(frozen=True)
class Blank:
    location: str
    label: str

    def to_json(self) -> dict:
        return {"location": self.location, "label": self.label}


def is_left_blank(container: object, key: str | int) -> bool:
    if isinstance(container, dict):
        return key in container and container[key] is None
    if isinstance(container, list) and isinstance(key, int):
        return key < len(container) and container[key] is None
    return False


def form_blanks(document: dict) -> list[Blank]:
    return [
        *letterhead_blanks(document.get("profile")),
        *labeled_blanks(document.get("meta"), "meta"),
        *recipient_blanks(document.get("recipient")),
        *approver_blanks(document.get("approvalLine")),
        *item_blanks(document.get("items")),
        *section_blanks(document.get("sections")),
        *signature_blanks(document.get("signature"), document.get("profile")),
    ]


def letterhead_blanks(profile: object) -> list[Blank]:
    if not isinstance(profile, dict):
        return [Blank("profile.name", "name")]
    reported = profile.get("missingFields") if isinstance(profile.get("missingFields"), list) else []
    missing = [field for field in LETTERHEAD_FIELDS if field in reported or (field == "name" and not company_name(profile))]
    return [Blank(f"profile.{field}", field) for field in missing]


def company_name(profile: dict) -> str:
    return str(profile.get("name") or profile.get("companyName") or "").strip()


def labeled_blanks(entries: object, location: str) -> list[Blank]:
    if not isinstance(entries, list):
        return []
    return [
        Blank(f"{location}[{index}].value", str(entry.get("label") or ""))
        for index, entry in enumerate(entries)
        if is_left_blank(entry, "value")
    ]


def recipient_blanks(recipient: object) -> list[Blank]:
    if not isinstance(recipient, dict) or not isinstance(recipient.get("lines"), list):
        return []
    label = str(recipient.get("label") or "recipient")
    return [Blank(f"recipient.lines[{index}]", label) for index, line in enumerate(recipient["lines"]) if line is None]


def approver_blanks(approvers: object) -> list[Blank]:
    if not isinstance(approvers, list):
        return []
    return [
        Blank(f"approvalLine[{index}].name", str(approver.get("role") or ""))
        for index, approver in enumerate(approvers)
        if is_left_blank(approver, "name")
    ]


def item_blanks(items: object) -> list[Blank]:
    if not isinstance(items, dict):
        return []
    headers = items.get("headers") if isinstance(items.get("headers"), list) else []
    rows = items.get("rows") if isinstance(items.get("rows"), list) else []
    cells = [
        Blank(f"items.rows[{row_index}][{column}]", f"{header_of(headers, column)} ({row_index + 1})")
        for row_index, row in enumerate(rows) if isinstance(row, list)
        for column, cell in enumerate(row) if cell is None
    ]
    return [*cells, *labeled_blanks(items.get("totals"), "items.totals")]


def header_of(headers: list, column: int) -> str:
    return str(headers[column]) if column < len(headers) else str(column + 1)


def section_blanks(sections: object) -> list[Blank]:
    if not isinstance(sections, list):
        return []
    blanks = []
    for section_index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "")
        for field in ("paragraphs", "bullets"):
            lines = section.get(field) if isinstance(section.get(field), list) else []
            blanks.extend(Blank(f"sections[{section_index}].{field}[{index}]", title) for index, line in enumerate(lines) if line is None)
    return blanks


def signature_blanks(signature: object, profile: object) -> list[Blank]:
    if not isinstance(signature, dict):
        return []
    blanks = [Blank(f"signature.{field}", field) for field in ("date", "line") if is_left_blank(signature, field)]
    if signature.get("stamp") and not has_seal(profile):
        blanks.append(Blank("signature.stamp", "seal"))
    return blanks


def has_seal(profile: object) -> bool:
    if not isinstance(profile, dict):
        return False
    stamp_path = str(profile.get("stampPath") or "").strip()
    return bool(stamp_path) and Path(stamp_path).is_file()
