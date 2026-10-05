#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, replace
import pathlib

from core.office_arguments import route_arguments
from core.office_result import ERROR, WARNING, Issue, IssueKind, Result, run_command
from core.text_checks import text_presence_issues
from deck.deck_html import render_gate_issues
from deck.deck_preparation import prepare_deck
from deck.deck_source import find_all, parse_source
from deck.design_system import DESIGN_FILE_NAME, DesignSystem, read_design_system
from deck.draft_claims import draft_claim_issues, draft_claims
from deck.layout_choice import assigned_layouts, decided_choices, is_decision_pending, write_layout_request
from deck.outline import OUTLINE_FILE_NAME, PAGES_DIRECTORY_NAME, Outline, layout_issues, outline_issues, read_outline, write_outline
from deck.page_checks import Page, page_issues
from deck.page_files import assembled_deck, lone_section, page_number, page_path
from schemas.known_values import load_runtime_context


ASSEMBLED_FILE_NAME = "slides.html"
PAGE_CHECK_FILE_NAME = ".page-check.html"

STAGE_NOT_READY = IssueKind("STAGE_NOT_READY", ERROR, "an earlier stage of the deck is missing or does not pass its check", "run office check on the file the message names and fix it before this one")
OUTLINE_BEING_PREPARED = IssueKind("OUTLINE_BEING_PREPARED", ERROR, "InternKim is choosing each page's layout and judging the outline's statements", "run office check outline.json again, as a command of its own, before writing any page")
LAYOUT_CHOICE_FAILED = IssueKind("LAYOUT_CHOICE_FAILED", ERROR, "InternKim could not choose the pages' layouts, so the outline must name them", 'add "layout" to every page from the library office guide design lists, then check the outline again')
PAGE_NOT_ONE_SECTION = IssueKind("PAGE_NOT_ONE_SECTION", ERROR, "a page file is not exactly one <section> element", "write the page as one <section>, with its <style> inside it, and nothing outside it")
PAGE_MISSING = IssueKind("PAGE_MISSING", ERROR, "an outline page has no page file", "write pages/NN.html for every outline page, checking each with office check")
PAGE_NOT_IN_OUTLINE = IssueKind("PAGE_NOT_IN_OUTLINE", ERROR, "a page file has no outline entry", "add the page to outline.json and check the outline, or delete the file")
OUTLINE_WAIT_SUMMARY = "the outline passes its checks; InternKim now chooses each page's layout and judges its statements on its own, and nothing is asked of the person: run office check outline.json again as your next command, before writing any page"
STAGE_ISSUE_KINDS = (STAGE_NOT_READY, OUTLINE_BEING_PREPARED, LAYOUT_CHOICE_FAILED, PAGE_NOT_ONE_SECTION, PAGE_MISSING, PAGE_NOT_IN_OUTLINE)


@dataclass(frozen=True)
class DeckRequest:
    directory: pathlib.Path
    requested_slide_count: int | None = None
    required_text: tuple[str, ...] = ()
    forbidden_text: tuple[str, ...] = ()
    is_blank_remake: bool = False

    @property
    def outline_path(self) -> pathlib.Path:
        return self.directory / OUTLINE_FILE_NAME

    @property
    def assembled_path(self) -> pathlib.Path:
        return self.directory / ASSEMBLED_FILE_NAME


@dataclass(frozen=True)
class DeckCheck:
    result: Result
    system: DesignSystem | None = None
    outline: Outline | None = None


def has_errors(issues: list[Issue]) -> bool:
    return any(issue.kind.severity == ERROR for issue in issues)


def demoted_to_warning(issue: Issue) -> Issue:
    return replace(issue, kind=replace(issue.kind, severity=WARNING)) if issue.kind.severity == ERROR else issue


def refusal_summary(issues: list[Issue]) -> str:
    errors = [issue for issue in issues if issue.kind.severity == ERROR]
    listed = "; ".join(f"{number}. {issue.kind.code}{' on ' + issue.location if issue.location else ''}: {issue.message}" for number, issue in enumerate(errors, start=1))
    return f"{len(errors)} problems to fix, all listed here: {listed}"


def stage_result(path: pathlib.Path, issues: list[Issue], ready: str, details: dict | None = None) -> Result:
    summary = refusal_summary(issues) if has_errors(issues) else ready
    return Result(summary=summary, output_path=str(path), issues=tuple(issues), details=details or {})


def check_design(design_path: pathlib.Path) -> Result:
    system, issues = read_design_system(design_path)
    return stage_result(design_path, issues, f"{design_path.name} passes: write outline.json next, then run office check outline.json")


def listed_photos() -> set[str]:
    return {image["path"] for image in prepare_deck().images}


def chooses_layouts() -> bool:
    context = load_runtime_context()
    return bool(context and context.chooses_deck_layouts)


def design_or_refusal(directory: pathlib.Path) -> tuple[DesignSystem | None, list[Issue]]:
    system, issues = read_design_system(directory / DESIGN_FILE_NAME)
    if system is None:
        return None, issues + [STAGE_NOT_READY.issue(f"{DESIGN_FILE_NAME} does not pass: run office check {DESIGN_FILE_NAME}", DESIGN_FILE_NAME)]
    return system, issues


def existing_sections(directory: pathlib.Path, outline: Outline) -> dict[int, str]:
    sections = {}
    for number in range(1, len(outline.pages) + 1):
        path = page_path(directory, number)
        section = lone_section(path.read_text(encoding="utf-8")) if path.is_file() else None
        if section is not None:
            sections[number] = section
    return sections


def check_outline(outline_path: pathlib.Path, requested_slide_count: int | None) -> Result:
    directory = outline_path.parent
    system, issues = design_or_refusal(directory)
    if system is None:
        return stage_result(outline_path, issues, "")
    outline, read_issues = read_outline(outline_path)
    if outline is None:
        return stage_result(outline_path, issues + read_issues, "")
    issues += outline_issues(outline, listed_photos(), requested_slide_count)
    issues += [] if chooses_layouts() else layout_issues(outline)
    if has_errors(issues):
        return stage_result(outline_path, issues, "")
    claim_issues, is_judged = draft_claim_issues(draft_claims(outline, assembled_deck(outline, existing_sections(directory, outline))))
    outline, layout_issues_found, is_pending = settled_layouts(outline_path, outline)
    issues += claim_issues + layout_issues_found
    details = {"pages": [page.to_json() for page in outline.pages]}
    if not has_errors(issues) and (is_pending or not is_judged):
        return Result(summary=OUTLINE_WAIT_SUMMARY, output_path=str(outline_path), issues=(*issues, OUTLINE_BEING_PREPARED.issue(OUTLINE_WAIT_SUMMARY, "outline")), details=details)
    return stage_result(outline_path, issues, outline_ready_summary(outline), details)


def settled_layouts(outline_path: pathlib.Path, outline: Outline) -> tuple[Outline, list[Issue], bool]:
    context = load_runtime_context()
    if not (context and context.chooses_deck_layouts):
        return outline, [], False
    write_layout_request(outline)
    if is_decision_pending(outline, context.deck_layouts):
        return outline, [], True
    choices = decided_choices(outline, context.deck_layouts)
    if choices is None:
        return outline, fallback_layout_issues(outline, context.deck_layouts), False
    settled = outline.with_layouts(assigned_layouts(outline, choices))
    write_outline(outline_path, settled)
    return settled, [], False


def fallback_layout_issues(outline: Outline, decision: dict) -> list[Issue]:
    own = layout_issues(outline)
    if not own:
        return []
    return [LAYOUT_CHOICE_FAILED.issue(f"the layout choice failed: {decision.get('failure') or 'no answer'}", "outline"), *own]


def outline_ready_summary(outline: Outline) -> str:
    listed = "; ".join(f"page {number} {page.layout}" for number, page in enumerate(outline.pages, start=1))
    return f"outline passes: {listed}. Write pages/01.html in its layout, run office check pages/01.html, and go on one page at a time"


def outline_for_pages(directory: pathlib.Path) -> tuple[Outline | None, list[Issue]]:
    outline, issues = read_outline(directory / OUTLINE_FILE_NAME)
    if outline is None or any(not page.layout for page in outline.pages):
        return None, issues + [STAGE_NOT_READY.issue(f"{OUTLINE_FILE_NAME} has no layout for every page yet: run office check {OUTLINE_FILE_NAME}", OUTLINE_FILE_NAME)]
    return outline, []


def checked_page(directory: pathlib.Path, outline: Outline, number: int, system: DesignSystem) -> tuple[Page | None, list[Issue]]:
    path = page_path(directory, number)
    section = lone_section(path.read_text(encoding="utf-8")) if path.is_file() else None
    if section is None:
        return None, [PAGE_NOT_ONE_SECTION.issue(f"{path.relative_to(directory)} is not one <section>", f"page {number}")]
    page = Page(number, find_all(parse_source(section), "section")[0], outline.pages[number - 1])
    return page, page_issues(page, directory, system)


def page_render_issues(directory: pathlib.Path, outline: Outline, number: int, section: str, system: DesignSystem) -> list[Issue]:
    path = directory / PAGE_CHECK_FILE_NAME
    path.write_text(assembled_deck(outline, {number: section}), encoding="utf-8")
    try:
        return render_gate_issues(path, system, [f"page {number}"])
    finally:
        path.unlink(missing_ok=True)


def check_page(path: pathlib.Path) -> Result:
    directory = path.parent.parent
    number = page_number(path)
    system, issues = design_or_refusal(directory)
    outline, outline_problems = outline_for_pages(directory) if system else (None, [])
    if system is None or outline is None:
        return stage_result(path, issues + outline_problems, "")
    if number > len(outline.pages):
        return stage_result(path, [PAGE_NOT_IN_OUTLINE.issue(f"outline.json has {len(outline.pages)} pages, so page {number} has no entry", f"page {number}")], "")
    page, issues = checked_page(directory, outline, number, system)
    if page is None:
        return stage_result(path, issues, "")
    issues += draft_claim_issues(draft_claims(outline, assembled_deck(outline, existing_sections(directory, outline))))[0]
    if not has_errors(issues):
        issues += page_render_issues(directory, outline, number, lone_section(path.read_text(encoding="utf-8")), system)
    following = f"write pages/{number + 1:02d}.html next" if number < len(outline.pages) else "every page is written: build the deck with office create"
    return stage_result(path, issues, f"page {number} ({outline.pages[number - 1].layout}) passes: {following}")


def deck_file_issues(directory: pathlib.Path, outline: Outline) -> list[Issue]:
    missing = [PAGE_MISSING.issue(f"pages/{number:02d}.html is missing for outline page {number}", f"page {number}") for number in range(1, len(outline.pages) + 1) if not page_path(directory, number).is_file()]
    extra = [PAGE_NOT_IN_OUTLINE.issue(f"{path.relative_to(directory)} has no outline entry", path.name) for path in sorted((directory / PAGES_DIRECTORY_NAME).glob("*.htm*")) if (page_number(path) or 0) > len(outline.pages)]
    return missing + extra


def check_staged_deck(request: DeckRequest) -> DeckCheck:
    system, issues = design_or_refusal(request.directory)
    outline, outline_problems = outline_for_pages(request.directory) if system else (None, [])
    if system is None or outline is None:
        return DeckCheck(stage_result(request.outline_path, issues + outline_problems, ""))
    issues += outline_issues(outline, listed_photos(), request.requested_slide_count) + ([] if chooses_layouts() else layout_issues(outline))
    issues += deck_file_issues(request.directory, outline)
    pages = [checked_page(request.directory, outline, number, system) for number in range(1, len(outline.pages) + 1) if page_path(request.directory, number).is_file()]
    issues += [issue for _, page_issues_found in pages for issue in page_issues_found]
    issues += text_presence_issues(" ".join(page.text() for page, _ in pages if page), request.required_text, request.forbidden_text)
    sections = existing_sections(request.directory, outline)
    request.assembled_path.write_text(assembled_deck(outline, sections), encoding="utf-8")
    if not request.is_blank_remake:
        issues += draft_claim_issues(draft_claims(outline, request.assembled_path.read_text(encoding="utf-8")))[0]
    if not has_errors(issues):
        issues += render_gate_issues(request.assembled_path, system, [f"page {number}" for number in sorted(sections)])
    if request.is_blank_remake:
        issues = [demoted_to_warning(issue) for issue in issues]
    return DeckCheck(stage_result(request.outline_path, issues, f"checked {len(outline.pages)} pages: ready to build", {"slideCount": len(outline.pages)}), system, outline)


def deck_directory(target: str) -> pathlib.Path:
    path = pathlib.Path(target).expanduser().resolve()
    return path if path.is_dir() else path.parent


def stage_refusal(path: pathlib.Path) -> Result:
    issue = STAGE_NOT_READY.issue(f"office check takes {DESIGN_FILE_NAME}, {OUTLINE_FILE_NAME}, a page file pages/NN.html or the deck's folder, not {path.name}", str(path))
    return stage_result(path, [issue], "")


def main() -> Result:
    parsed = route_arguments("check", "slides")
    path = pathlib.Path(parsed.file).expanduser().resolve()
    if path.name == DESIGN_FILE_NAME:
        return check_design(path)
    if path.name == OUTLINE_FILE_NAME:
        return check_outline(path, parsed.slide_count)
    if page_number(path) is not None:
        return check_page(path)
    if path.is_dir():
        return check_staged_deck(DeckRequest(path, parsed.slide_count, tuple(parsed.required_text), tuple(parsed.forbidden_text))).result
    return stage_refusal(path)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
