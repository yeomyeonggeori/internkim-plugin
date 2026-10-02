from __future__ import annotations

from doc.operations.editing import DocxEditing
from doc.model.revisions import Revision, collect_revisions, describe_pending, settle
from core.office_operations import TARGET_NOT_FOUND, Change
from core.office_result import MISSING_FIELD, OfficeFailure


SELECTOR_FIELDS = ("all", "ids", "author", "type", "block")


def plan_accept_revisions(editing: DocxEditing, operation: dict, location: str) -> Change:
    return plan_settle(editing, operation, location, accept=True)


def plan_reject_revisions(editing: DocxEditing, operation: dict, location: str) -> Change:
    return plan_settle(editing, operation, location, accept=False)


def plan_settle(editing: DocxEditing, operation: dict, location: str, accept: bool) -> Change:
    selected = select_revisions(editing, operation, location)
    verb = "accepted" if accept else "rejected"

    def change() -> str:
        settled = settle(selected, accept, editing.document.element.body)
        return f"{verb} {settled} tracked changes: {', '.join(revision.identifier for revision in selected)}"
    return change


def select_revisions(editing: DocxEditing, operation: dict, location: str) -> list[Revision]:
    if not any(operation.get(name) not in (None, False, []) for name in SELECTOR_FIELDS):
        raise OfficeFailure(MISSING_FIELD.issue(f"{location}: give all: true, ids, author, type, or block", location))
    revisions = collect_revisions(editing.document.element.body, editing.elements)
    if not revisions:
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: the document has no tracked changes", location, suggestion="office read --revisions lists them"))
    require_known_ids(revisions, operation.get("ids") or [], location)
    selected = [revision for revision in revisions if matches(revision, operation)]
    if not selected:
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}: no tracked change matches; {describe_pending(revisions)}", location, suggestion="office read --revisions lists every id, author and type"))
    return selected


def require_known_ids(revisions: list[Revision], identifiers: list[str], location: str) -> None:
    known = {revision.identifier for revision in revisions}
    unknown = [identifier for identifier in identifiers if identifier not in known]
    if unknown:
        raise OfficeFailure(TARGET_NOT_FOUND.issue(f"{location}.ids: {', '.join(unknown)} do not exist; ids run r1-r{len(revisions)}", f"{location}.ids", suggestion=f"use ids from office read --revisions: r1-r{len(revisions)}"))


def matches(revision: Revision, operation: dict) -> bool:
    if operation.get("ids") and revision.identifier not in operation["ids"]:
        return False
    if operation.get("author") and revision.author.casefold() != operation["author"].strip().casefold():
        return False
    if operation.get("type") and revision.revision_type != operation["type"]:
        return False
    return operation.get("block") is None or revision.block == operation["block"]
