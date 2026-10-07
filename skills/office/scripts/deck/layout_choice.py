from __future__ import annotations

import hashlib
import json

from deck.deck_decisions import decided, read_state, request_wordings, write_state
from deck.outline import LAYOUTS, LIBRARY, VARIETY_MINIMUM, VARIETY_MINIMUM_BODY_PAGES, Outline, OutlinePage, valid_layouts


LAYOUTS_FILE = "deck-layouts.json"
QUESTION = LIBRARY["question"]
NO_PHOTOS = "none"


def question_name(index: int) -> str:
    return f"page_{index + 1:02d}"


def page_question(index: int, page: OutlinePage, count: int) -> dict:
    instructions = QUESTION["page"].format(number=index + 1, count=count, type=page.type, title=page.title, brief=" / ".join(page.brief), photos=len(page.photos) or NO_PHOTOS)
    return {"instructions": instructions, "options": {name: LAYOUTS[name]["description"] for name in valid_layouts(page)}}


def layout_request(outline: Outline) -> dict:
    count = len(outline.pages)
    return {"instructions": QUESTION["instructions"].format(criteria=LIBRARY["criteria"]), "questions": {question_name(index): page_question(index, page, count) for index, page in enumerate(outline.pages)}}


def request_bytes(outline: Outline) -> bytes:
    return json.dumps(layout_request(outline), ensure_ascii=False, sort_keys=True).encode("utf-8")


def request_digest(outline: Outline) -> str:
    return hashlib.sha256(request_bytes(outline)).hexdigest()


def layout_decision(outline: Outline) -> dict:
    digest = request_digest(outline)
    recorded = read_state(LAYOUTS_FILE)
    if isinstance(recorded, dict) and recorded.get("digest") == digest:
        return recorded
    decision = decided({"request": request_wordings()}, layout_request(outline)) | {"digest": digest}
    write_state(LAYOUTS_FILE, decision)
    return decision


def decided_choices(outline: Outline, decision: dict | None) -> dict | None:
    if not isinstance(decision, dict) or decision.get("digest") != request_digest(outline) or decision.get("failure"):
        return None
    choices = decision.get("choices")
    return choices if isinstance(choices, dict) and choices else None


def ranked_layouts(page: OutlinePage, choice: object) -> tuple[list[str], dict[str, float]]:
    valid = valid_layouts(page)
    answer = choice if isinstance(choice, dict) else {}
    probabilities = {name: float(value) for name, value in (answer.get("probabilities") or {}).items() if name in valid}
    if answer.get("option") in valid:
        probabilities.setdefault(answer["option"], 1.0)
    return sorted(valid, key=lambda name: (-probabilities.get(name, 0.0), valid.index(name))), probabilities


def assigned_layouts(outline: Outline, choices: dict) -> list[str]:
    ranked = [ranked_layouts(page, choices.get(question_name(index))) for index, page in enumerate(outline.pages)]
    picks = without_repeats(outline.pages, [ranking for ranking, _ in ranked])
    return with_variety(outline.pages, ranked, picks)


def follows_body_page(pages: tuple[OutlinePage, ...], index: int) -> bool:
    return index > 0 and pages[index].is_body and pages[index - 1].is_body


def without_repeats(pages: tuple[OutlinePage, ...], rankings: list[list[str]]) -> list[str]:
    picks: list[str] = []
    for index, ranking in enumerate(rankings):
        previous = picks[index - 1] if follows_body_page(pages, index) else None
        picks.append(next((name for name in ranking if name != previous), ranking[0] if ranking else ""))
    return picks


def neighbors(pages: tuple[OutlinePage, ...], picks: list[str], index: int) -> set[str]:
    before = {picks[index - 1]} if follows_body_page(pages, index) else set()
    after = {picks[index + 1]} if index + 1 < len(pages) and follows_body_page(pages, index + 1) else set()
    return before | after


def with_variety(pages: tuple[OutlinePage, ...], ranked: list[tuple[list[str], dict[str, float]]], picks: list[str]) -> list[str]:
    body = [index for index, page in enumerate(pages) if page.is_body]
    picks = list(picks)
    while len(body) >= VARIETY_MINIMUM_BODY_PAGES and len({picks[index] for index in body}) < VARIETY_MINIMUM:
        swap = cheapest_swap(pages, ranked, picks, body)
        if swap is None:
            break
        picks[swap[0]] = swap[1]
    return picks


def cheapest_swap(pages: tuple[OutlinePage, ...], ranked: list[tuple[list[str], dict[str, float]]], picks: list[str], body: list[int]) -> tuple[int, str] | None:
    used = [picks[index] for index in body]
    candidates = []
    for index in body:
        ranking, probabilities = ranked[index]
        if used.count(picks[index]) < 2:
            continue
        fresh = next((name for name in ranking if name not in used and name not in neighbors(pages, picks, index)), None)
        if fresh is not None:
            candidates.append((probabilities.get(picks[index], 0.0) - probabilities.get(fresh, 0.0), index, fresh))
    return min(candidates)[1:] if candidates else None
