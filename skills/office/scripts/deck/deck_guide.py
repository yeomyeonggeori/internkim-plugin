# Style sheet, layout library, sizing and anti-pattern guidance adapted from GenOffice packages/pipelines/src/slides/guides/design.md and apps/slides/src/renderer/ai/AiPanel.tsx (Apache-2.0, Copyright 2026 Mainfunc, Inc.); see NOTICE.
from __future__ import annotations

from deck.deck_preparation import DeckPreparation, prepare_deck, request_preparation
from deck.outline import LAYOUTS, LIBRARY, PAGE_TYPES
from deck.typeface import type_pairing


DESIGN_TOPIC = "design"

STYLE_SHEET_LINES = (
    "Stage 1, the style sheet: DESIGN.md, one per deck, before any content. Concrete #RRGGBB values in its front matter:",
    "  style: one sentence describing the design language",
    "  colors: text, accent (primary), secondary (the second accent), surface (card background), line (border)",
    "  backgrounds: cover, content, data, closing; content pages share one background",
    "  sizes (px on the 1600x900 page): display (cover and hero numbers, 96 to 160), title (56 to 80), body (28 to 36), small (captions, 20 to 26)",
    "Honor a tone the request names (dark, a brand color) before a light neutral; let the subject's mood pick the background, and keep a light neutral for a neutral subject. One accent system for the whole deck: never more than the two accents, and never a color per company, product or option. Text reads at 4.5:1 on its background.",
)

PAGE_LINES = (
    "Stage 3, pages: for page N re-read DESIGN.md and outline entry N, write pages/NN.html in the layout the entry names, run office check pages/NN.html, fix it until it passes, then go to page N+1. Never write two pages in one step.",
    "  The layout names the composition; you decide its proportions, which parts appear and how many, sizes within the scale, emphasis, background treatment and photo crop.",
    "  Every word and figure comes from the entry's brief and figures. The title is one empty element, such as <h1 data-title></h1>: the build writes the entry's title into it. A chart plots the entry's figures: their labels, values and unit, one unit per axis.",
    "  Type scale: titles 56 to 80px, subtitles 30 to 40px, body 28 to 36px, captions 20px or more, hero numbers up to 160px.",
    "  Spacing: 64px or more from the page edge, 24px or more between text and a card edge, 24px or more between a title and its subtitle, 12px or more between stacked text blocks.",
    "  Fill the page: spread the content over the whole 1600x900 page and make text, charts and photos as large as the layout allows. The lowest part ends near the bottom margin, about 100px from the edge: cards, columns and charts stretch down to it, and a page with few words sets them larger. A blank band under the content is a defect.",
    "  A hero number is a quantity, amount, share or date from the brief, never an abbreviation, a label or a word set large in its place.",
    "  The parts the layout names are drawn: a photo layout shows its photo, chart_with_insight its chart. Colors come only from the style sheet; add a color to DESIGN.md before a page uses it.",
    "  Visuals: photos only from the list below; without photos, typography, color blocks and the kit's icons and charts carry the page, and never a grey box standing in for a photo. A chart's size is proportional to real values from the brief.",
)

ANTI_PATTERNS = (
    "a thin accent bar on one side of a card, a colored bar on top of cards, a small bar left of a title; show hierarchy with background, weight and size",
    "rainbow cards: a different accent per item",
    "decorative corner blocks or short lines; decoration that moves around from page to page",
    "every page as shape + bold subtitle + description; a cover that is a flat title and subtitle with no visual anchor (a large color block, a geometric composition, a huge number or a hero photo)",
    "a header bar with the page title repeated on every page",
    "sibling cards whose numbers mix metrics (a share beside a price beside a count): one row, one unit, one source",
    "two lines that say the same thing, such as a subtitle restating the chart caption",
    "emoji, gradients, glows and glass blur",
)


def guide_preamble() -> list[str]:
    if request_preparation(prepare_deck()):
        return ["", "Next, run office guide design as a command of its own: InternKim gathers the photos and logo the deck can use before the next command runs."]
    return ["", "Next, run office guide design: it gives the style sheet, the layout library and the photos and logo the deck can use."]


def design_text() -> str:
    preparation = prepare_deck()
    if request_preparation(preparation):
        return "InternKim is gathering this deck's photos, logo and typeface now. Run office guide design again as a command of its own; this answer is read only by the next command."
    sections = (typeface_lines(preparation), STYLE_SHEET_LINES, outline_lines(), library_lines(), PAGE_LINES, anti_pattern_lines(), logo_lines(preparation), image_lines(preparation))
    return "\n\n".join("\n".join(section) for section in sections)


def typeface_lines(preparation: DeckPreparation) -> list[str]:
    return [f"Typeface: {type_pairing(preparation.type_option)['display']}, chosen by InternKim from the request; the build sets it on every page."]


def outline_lines() -> list[str]:
    return [
        "Stage 2, the outline: outline.json, the content of every page before any page exists:",
        '  {"core_hook": "one sentence with tension, a number or a counter-intuitive contrast", "pages": [{"title": "...", "type": "cover", "brief": ["what goes on the page, one fact per line, with the real figures"], "figures": [{"label": "what it measures", "value": "64", "unit": "곳"}], "photos": ["<listed path>"]}]}',
        '  figures holds every number the page shows large or charts, each with its unit as the request states it ("" only for a bare count); a figure of a chart with several series adds "series": "<series name>". A source line under a figure is written only when the request names that source.',
        f"  type is {', '.join(PAGE_TYPES)}; the first page is the cover and the last the closing page. photos lists the photos the page shows, [] for none. Every figure and name comes from the request or its attachments; leave out what they do not state.",
        "  office check outline.json checks it, and InternKim then judges its statements and chooses each page's layout from the library below; run the check again, as a command of its own, until it lists every page's layout.",
    ]


def library_lines() -> list[str]:
    lines = ["Layout library, one composition intent per page:"]
    for page_type in PAGE_TYPES:
        lines += [f"  {name} ({page_type}{', needs a photo' if layout.get('photo') else ''}): {layout['description']}" for name, layout in LAYOUTS.items() if layout["type"] == page_type]
    return lines + [f"The layout follows the content's shape: {LIBRARY['criteria']}."]


def anti_pattern_lines() -> list[str]:
    return ["Avoid (a careful designer would not ship these):", *(f"  {pattern}" for pattern in ANTI_PATTERNS)]


def logo_lines(preparation: DeckPreparation) -> list[str]:
    logo = preparation.logo
    if logo is None:
        return ["Logo: none is known for this company; the deck goes without one."]
    kind = "transparent background" if logo.has_transparency else "its own opaque background"
    return [f"Logo: {logo.width}x{logo.height}, {kind}. The build places it on the cover and the closing page, in a corner no text covers; write no <img data-logo> and leave that corner free."]


def image_lines(preparation: DeckPreparation) -> list[str]:
    dropped = [f"  not readable from here, so not listed: {path}" for path in preparation.unreadable_images]
    if not preparation.images:
        return ["Photos: none. Plan pages that need no photo; the photo layouts are not offered.", *dropped]
    return [
        "Photos the requester can use: use them readily where they show the deck's subject, and skip one that does not. Plan one on the cover and on at least one content page, so InternKim can give those pages a photo layout. A caption or a fact about a photo comes only from its title, its summary or the request.",
        *(image_line(image) for image in preparation.images),
        *dropped,
    ]


def image_line(image: dict) -> str:
    facts = [f"{image['width']}x{image['height']}", image.get("source", ""), image.get("folder", ""), image.get("date", "")]
    described = ": ".join(part for part in (image.get("title", ""), image.get("summary", "")) if part)
    return f"  {image['path']} ({', '.join(fact for fact in facts if fact)}){' ' + described if described else ''}"
