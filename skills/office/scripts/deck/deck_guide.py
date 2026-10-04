from __future__ import annotations

from deck.deck_design import AXES, DECIDED, DESIGN, QUESTIONS, Choice, Design, attribute_name
from deck.deck_preparation import DeckPreparation, deck_palette, prepare_deck, request_preparation
from deck.deck_source import parse_source


DESIGN_TOPIC = "design"
COVER_WORK = {
    "photo": "make the listed photo that best shows the subject the cover's <img>",
    "key_figure": "give the cover one to three .kpi, each a .value and a .label, holding the request's headline figures",
    "icon": "put data-icon on the cover <section>, naming the icon that stands for the subject",
    "type_only": "let the cover's title stand alone",
}
IMAGERY_WORK = {
    "photo": "put each listed photo that shows the subject where it belongs: the cover, a section divider, an image slide beside what it shows",
    "icon": "give cards, metrics, steps and agenda or closing lists a data-icon",
    "data": "lead with chart, kpi, number and table slides; icons only where a list needs them",
}
SHOWN_TOKENS = ("accent", "accent-2", "bg", "ink")


def guide_preamble() -> list[str]:
    preparation = prepare_deck(parse_source("<body></body>"))
    if request_preparation(preparation):
        return ["", "Next, run office guide design: InternKim picks this deck's design and gathers the photos and logo it can use before that command runs."]
    return ["", "Next, run office guide design: it says this deck's design and lists the photos and logo it can use."]


def design_text() -> str:
    preparation = prepare_deck(parse_source("<body></body>"))
    lines = decided_lines(preparation) if is_decided(preparation.design) else choice_lines()
    return "\n".join([*lines, "", *logo_lines(preparation), "", *image_lines(preparation)])


def is_decided(design: Design) -> bool:
    return any(choice.source == DECIDED for choice in design.choices.values())


def decided_lines(preparation: DeckPreparation) -> list[str]:
    design = preparation.design
    palette = deck_palette(preparation)
    colors = ", ".join(f"{token} #{palette[token]}" for token in SHOWN_TOKENS)
    faces = DESIGN["types"][design.option("type")]
    return [
        "This deck's design, chosen by InternKim from the request; the build applies it, so write none of it on <body>:",
        f"  palette: {choice_label(design.choices['palette'])}; {colors}",
        f"  tone: {choice_label(design.choices['tone'])}; temperature: {choice_label(design.choices['temperature'])}",
        f"  type: {choice_label(design.choices['type'])}; {faces['display']} titles, {faces['body']} text",
        f"  density: {choice_label(design.choices['density'])}",
        f"  cover: {choice_label(design.choices['cover'])}; {COVER_WORK[design.option('cover')]}",
        f"  imagery: {choice_label(design.choices['imagery'])}; {IMAGERY_WORK[design.option('imagery')]}",
        "  a request that names a color still sets data-accent=\"#RRGGBB\" on <body>",
    ]


def choice_label(choice: Choice) -> str:
    ranked = sorted(choice.probabilities.items(), key=lambda item: item[1], reverse=True)
    odds = ", ".join(f"{name} {share:.2f}" for name, share in ranked[:2])
    return f"{choice.option} ({odds})" if odds else choice.option


def choice_lines() -> list[str]:
    lines = ["Choose this deck's design from the request's subject, audience and purpose, and write each choice on <body>, such as data-palette=\"trust\":"]
    for axis in AXES:
        options = "; ".join(f"{name}: {meaning}" for name, meaning in QUESTIONS[axis]["options"].items())
        lines.append(f"  {attribute_name(axis)} (default {QUESTIONS[axis]['fallback']}): {options}")
    lines.append(f"  the cover and imagery choices ask of you: {'; '.join(f'{name}: {work}' for name, work in COVER_WORK.items())}")
    return lines


def logo_lines(preparation: DeckPreparation) -> list[str]:
    logo = preparation.logo
    if logo is None:
        return ["Logo: none is known for this company; the deck goes without one."]
    brand = f"; its color #{preparation.design.brand_color} leads the palette" if preparation.design.brand_color else ""
    return [f"Logo: the kit places the company logo on the cover, in every footer and on the closing{brand}; never add it yourself."]


def image_lines(preparation: DeckPreparation) -> list[str]:
    if not preparation.images:
        return ["Images: none. Give the deck its rhythm with figures, icons and charts, and never leave an empty photo frame or a placeholder box."]
    lines = ["Images the requester can use: use each one that shows the deck's subject where it fits, and skip one that does not. A caption or a fact about a photo comes only from its title, its summary or the request.", *(image_line(image) for image in preparation.images)]
    return lines


def image_line(image: dict) -> str:
    facts = [f"{image['width']}x{image['height']}", image.get("source", ""), image.get("folder", ""), image.get("date", "")]
    described = ": ".join(part for part in (image.get("title", ""), image.get("summary", "")) if part)
    return f"  {image['path']} ({', '.join(fact for fact in facts if fact)}){' ' + described if described else ''}"
