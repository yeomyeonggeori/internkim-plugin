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
    "cream or beige grounds, purple-and-blue palettes, cyan on dark",
    "gradients of any kind: fills, text, halos, grid or stripe backgrounds",
    "glass blur, glows, a wide shadow under a hairline border, radius past 24px",
    "eyebrows, badges or icon tiles above headings",
    "one-sided accent bars, nested cards, grids of identical cards",
    "oversized or italic serif headlines, tight letter-spacing, a flat type scale",
    "a big metric used as a cover template, rough illustrations, one spacing everywhere, numbering with no real sequence",
    "em dash strings",
)


def guide_preamble() -> list[str]:
    preparation = prepare_deck()
    if request_preparation(preparation):
        return ["", "Next, run office guide design as a command of its own: InternKim gathers the photos and logo the deck can use before the next command runs."]
    return ["", "Next, run office guide design: it says this deck's design intent and lists the photos and logo it can use."]


def design_text() -> str:
    preparation = prepare_deck()
    if request_preparation(preparation):
        return "InternKim is gathering this deck's photos, logo and design intent now. Run office guide design again as a command of its own; this answer is read only by the next command."
    return "\n".join([*intent_lines(preparation.design), "", *logo_lines(preparation), "", *image_lines(preparation), "", *avoid_lines()])


def is_decided(design: Design) -> bool:
    return any(choice.source == DECIDED for choice in design.choices.values())


def intent_lines(design: Design) -> list[str]:
    if not is_decided(design):
        return ["Design intent: none was decided for this request. Choose it yourself from the request's subject, audience and purpose, and write it in DESIGN.md."]
    pairing, scale = type_pairing(design), type_scale(design)
    return [
        "Design intent, chosen by InternKim from the request; write your own DESIGN.md within it. A color the request names, or the logo's own color, takes precedence over the accent.",
        f"  accent: {choice_label(design.choices['accent'])}{'; leaning toward ' + design.secondary_accent if design.secondary_accent else ''}",
        f"  mood: {choice_label(design.choices['mood'])}; temperature: {choice_label(design.choices['temperature'])}",
        f"  type: {choice_label(design.choices['type'])}; {pairing['display']} titles, {pairing['body']} text",
        f"  density: {choice_label(design.choices['density'])}; scale display {scale['display']}, title {scale['title']}, body {scale['body']}, small {scale['small']}, margin {scale['margin']}, gap {scale['gap']}",
        f"  imagery: {choice_label(design.choices['imagery'])}; {IMAGERY_WORK[design.option('imagery')]}",
        *(["  brand color from the logo: #" + design.brand_color] if design.brand_color else []),
        "Palette candidates derived from that hue family, each checked for contrast and against the design gate; pick one, adjust it or keep your own within the gate:",
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
    return [f"Logo: {logo.width}x{logo.height}, {kind}. Always show it: <img data-logo> on the cover, and on the other slides where it fits, at a height you choose; never stretch or recolor it."]


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
