from __future__ import annotations

import math


PHOTO_LAYOUTS = ("cover", "image")
CAPACITY_ENTRIES_NAMED = 3
PART_LABELS = {"title": "the title", "lead": "the lead line", "eyebrow": "the eyebrow", "takeaway": "the takeaway", "chart": "the chart", "quote": "the quote", "steps": "the steps"}
DEAD_ZONE_ADVICE = {
    "kpi": "give each .kpi a change line under its .value, add a .takeaway band, or add the third or fourth metric",
    "cards": "add a .takeaway band under the cards, or a .label or .value at the top of each card",
    "comparison": "add the points each .column's list is missing, or a .takeaway band",
    "timeline": "add a <p> to each .step, or a .takeaway band",
    "table": "add a .takeaway band with what the rows show",
    "chart": "add an .insight beside the chart with the number to remember",
    "number": "add the points that explain the number as a <ul>",
    "image": "add a .lead or a <ul> of points beside the photo",
}
DEFAULT_DEAD_ZONE_ADVICE = "add a .takeaway band with the slide's conclusion, or move this content to a statement slide"
LIST_ADVICE = {
    "agenda": "keep {fits} items on the agenda and fold the rest into them",
    "closing": "ask for at most {fits} decisions; move the rest to a slide before the closing",
}


def capacity_fix(capacity: list[dict], layout: str) -> str:
    return "; ".join(entry_fix(entry, layout) for entry in capacity[:CAPACITY_ENTRIES_NAMED])


def entry_fix(entry: dict, layout: str) -> str:
    if entry["part"] == "slide":
        return slide_fix(entry["share"])
    if entry["part"] == "table" and "items" in entry:
        return table_fix(entry["items"], entry["fits"])
    if "items" in entry:
        return list_fix(entry["items"], entry["fits"], layout)
    return text_fix(part_label(entry), entry["characters"], entry["fits"])


def table_fix(rows: int, fits: int) -> str:
    per_slide = max(1, fits)
    slides = math.ceil(rows / per_slide)
    return (
        f"a table slide shows {per_slide} of these {rows} rows at full type size: split the rows over {slides} table slides of at most {per_slide} rows each, "
        f"repeating the header row, or keep the {per_slide} rows that carry the point and chart the trend on a chart slide"
    )


def list_fix(items: int, fits: int, layout: str) -> str:
    shown = max(1, fits)
    advice = LIST_ADVICE.get(layout, "keep {fits} items and move the rest to the next slide or the speaker notes").format(fits=shown)
    return f"the {layout or 'slide'} shows {shown} of its {items} items at full type size: {advice}"


def text_fix(label: str, characters: int, fits: int) -> str:
    return f"{label} holds {characters} characters where about {fits} fit at full type size: cut it to {fits} or fewer, move the detail to the speaker notes, or split the slide in two"


def slide_fix(share: float) -> str:
    cut = max(1, round((1 - share) * 100))
    return f"the slide's parts need {cut}% more height than the slide has: cut about {cut}% of the body text, drop the .lead or .takeaway, or split the slide in two"


def part_label(entry: dict) -> str:
    return PART_LABELS.get(entry["part"], f"{entry['part']} {entry['index']}")


def photo_fix(layout: str) -> str:
    if layout in PHOTO_LAYOUTS:
        return "remove the style that sizes the photo; the kit crops a cover or image photo to its frame"
    return f"move the photo out of this {layout} slide into a cover or image slide, where the kit crops it to its frame"


def placement_fix(finding_text: str) -> str:
    return f"{finding_text}: no kit layout places one part over another or off the slide, so remove the <style> rule or style attribute that moves it"


def size_fix() -> str:
    return "the kit draws every part at 16px or more; remove the <style> rule or style attribute that sets this size"


def dead_zone_fix(layout: str) -> str:
    return f"the kit fills a {layout} slide with its parts: {DEAD_ZONE_ADVICE.get(layout, DEFAULT_DEAD_ZONE_ADVICE)}"
