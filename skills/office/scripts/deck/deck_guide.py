from __future__ import annotations

from deck.deck_design import AXES, DECIDED, DESIGN, Design, Choice, palette_candidates, type_pairing, type_scale
from deck.deck_preparation import DeckPreparation, prepare_deck, request_preparation


DESIGN_TOPIC = "design"
IMAGERY_WORK = {
    "photo": "photos lead: use each listed photo that shows the subject on the cover, a divider or the slide it shows",
    "icon": "line icons mark items; type and layout carry the rest",
    "data": "charts, key numbers and tables lead; icons only where a list needs them",
}
AVOID_LIST = (
    "text under 28px (body) or 20px (captions); an empty band over a fifth of the slide height",
    "a part drawn outside the slide, content spilling out of the box that holds it, two parts drawn over each other (a background photo is the one overlap allowed)",
    "eyebrows, badges or small caps labels above text; icon tiles above headings; a big number over a small label as a slide's design",
    "one-sided accent bars including a left or right rule, nested cards, grids of identical cards",
    "gradients, glass blur, glows, wide shadows, radius past 24px, oversized or italic serif headlines, tight letter-spacing",
    "rough illustrations, one spacing everywhere, numbering with no real sequence",
    "em dashes in titles, more than two on a slide",
)


COMPOSITIONS = (
    "field cover: the section's background is var(--accent), the title in var(--on-accent) at the display size, a subtitle under it, the block centered vertically; for the cover and the closing slide",
    "statement: one sentence at the display size on the ground with one supporting line, for the turning point of the argument",
    "chart with a takeaway: the chart fills two thirds of the width and the full height, the takeaway sentence fills the third beside it",
    "table: one full-width table, rows divided by var(--line) hairlines, the row that carries the point in var(--accent)",
    "sequence: three to five steps in one row or column, each a short label with its date or owner, divided by hairlines",
    "photo beside text: the photo fills half the slide edge to edge with object-fit: cover, the text takes the other half",
    "tinted panel: one var(--surface) panel fills the area under the title (flex: 1) and holds the two or three facts that belong together, centered in it",
)


def composition_lines() -> list[str]:
    return [
        "Compositions to choose from (use the one the content has; give two slides in a row different ones; each slide has one dominant part, the largest thing on it, and everything else supports it):",
        *(f"  {composition}" for composition in COMPOSITIONS),
    ]


def guide_preamble() -> list[str]:
    preparation = prepare_deck()
    if request_preparation(preparation):
        return ["", "Next, run office guide design as a command of its own: InternKim gathers the photos and logo the deck can use before the next command runs."]
    return ["", "Next, run office guide design: it says this deck's design intent and lists the photos and logo it can use."]


def design_text() -> str:
    preparation = prepare_deck()
    if request_preparation(preparation):
        return "InternKim is gathering this deck's photos, logo and design intent now. Run office guide design again as a command of its own; this answer is read only by the next command."
    return "\n".join([*intent_lines(preparation.design), "", *composition_lines(), "", *logo_lines(preparation), "", *image_lines(preparation), "", *avoid_lines()])


def is_decided(design: Design) -> bool:
    return any(choice.source == DECIDED for choice in design.choices.values())


def intent_lines(design: Design) -> list[str]:
    if not is_decided(design):
        return ["Design intent: none was decided for this request; the build uses the default intent. Palette candidates, each checked for contrast; write palette: <name> in DESIGN.md:", *candidate_lines(design)]
    pairing, scale = type_pairing(design), type_scale(design)
    return [
        "Design intent, chosen by InternKim from the request; DESIGN.md names a palette from the candidates below and nothing else is required. The build sets colors from it, and fonts, sizes and shape from the intent.",
        f"  accent: {choice_label(design.choices['accent'])}{'; leaning toward ' + design.secondary_accent if design.secondary_accent else ''}",
        f"  mood: {choice_label(design.choices['mood'])}; temperature: {choice_label(design.choices['temperature'])}",
        f"  type: {choice_label(design.choices['type'])}; {pairing['display']} titles and text",
        f"  density: {choice_label(design.choices['density'])}; display {scale['display']}, title {scale['title']}, body {scale['body']}, small {scale['small']}",
        f"  imagery: {choice_label(design.choices['imagery'])}; {IMAGERY_WORK[design.option('imagery')]}",
        *(["  brand color from the logo: #" + design.brand_color] if design.brand_color else []),
        "Palette candidates, each checked for contrast; write palette: <name> in DESIGN.md:",
        *candidate_lines(design),
    ]


def candidate_lines(design: Design) -> list[str]:
    return [
        f"  {candidate['name']}: " + ", ".join(f"{role} {value}" for role, value in candidate["colors"].items()) + f" (text {candidate['textContrast']}:1, accent {candidate['accentContrast']}:1)"
        for candidate in palette_candidates(design)
    ]


def choice_label(choice: Choice) -> str:
    ranked = sorted(choice.probabilities.items(), key=lambda item: item[1], reverse=True)
    odds = ", ".join(f"{name} {share:.2f}" for name, share in ranked[:2])
    return f"{choice.option} ({odds})" if odds else choice.option


def avoid_lines() -> list[str]:
    return ["Never produce (office check refuses these): " + "; ".join(AVOID_LIST)]


def logo_lines(preparation: DeckPreparation) -> list[str]:
    logo = preparation.logo
    if logo is None:
        return ["Logo: none is known for this company; the deck goes without one."]
    kind = "transparent background" if logo.has_transparency else "its own opaque background"
    return [f"Logo: {logo.width}x{logo.height}, {kind}. The build places it on the cover and the closing slide, in a corner no text covers; write no <img data-logo> and leave that corner free."]


def image_lines(preparation: DeckPreparation) -> list[str]:
    dropped = [f"  not readable from here, so not listed: {path}" for path in preparation.unreadable_images]
    if not preparation.images:
        return ["Images: none.", *dropped, "  Give the deck its rhythm with type, figures and charts, and never leave an empty photo frame or a placeholder box."]
    return [
        "Images the requester can use: use them readily, where they show the deck's subject; skip one that does not. A caption or a fact about a photo comes only from its title, its summary or the request.",
        *(image_line(image) for image in preparation.images),
        *dropped,
    ]


def image_line(image: dict) -> str:
    facts = [f"{image['width']}x{image['height']}", image.get("source", ""), image.get("folder", ""), image.get("date", "")]
    described = ": ".join(part for part in (image.get("title", ""), image.get("summary", "")) if part)
    return f"  {image['path']} ({', '.join(fact for fact in facts if fact)}){' ' + described if described else ''}"
