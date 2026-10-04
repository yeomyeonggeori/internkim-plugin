from __future__ import annotations

from dataclasses import dataclass, field
import json

from core.css_color import contrast_ratio, hex_oklch, oklch_hex
from deck.deck_kit import KIT_PATH


DESIGN_PATH = KIT_PATH / "design.json"
DESIGN = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
QUESTIONS = DESIGN["questions"]
AXES = tuple(QUESTIONS)
SOURCE = "source"
DECIDED = "decided"
FALLBACK = "fallback"
BRAND = "logo"
HUED_TOKENS = ("accent", "accent-2", "feature-bg", "feature-ink", "feature-muted", "feature-accent")
LIGHTNESS_STEP = 0.01
WHITE = "FFFFFF"


@dataclass(frozen=True)
class Choice:
    option: str
    source: str
    probabilities: dict[str, float] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"option": self.option, "source": self.source, **({"probabilities": self.probabilities} if self.probabilities else {})}


@dataclass(frozen=True)
class Design:
    choices: dict[str, Choice]
    secondary_palette: str | None = None
    brand_color: str | None = None
    theme: str | None = None

    def option(self, axis: str) -> str:
        return self.choices[axis].option

    def label(self) -> str:
        return " ".join(self.option(axis) for axis in ("palette", "tone", "temperature", "type"))

    def to_json(self) -> dict:
        record = {axis: choice.to_json() for axis, choice in self.choices.items()}
        if self.secondary_palette:
            record["secondaryPalette"] = self.secondary_palette
        if self.brand_color:
            record["brandColor"] = f"#{self.brand_color}"
        if self.theme:
            record["theme"] = self.theme
        return record


def options(axis: str) -> tuple[str, ...]:
    return tuple(QUESTIONS[axis]["options"])


def attribute_name(axis: str) -> str:
    return f"data-{axis}"


def resolve_design(attributes: dict[str, str], decided: dict | None, brand_color: str | None = None) -> Design:
    decided_choices = (decided or {}).get("choices") or {}
    choices = {axis: chosen(axis, attributes.get(attribute_name(axis), ""), decided_choices.get(axis)) for axis in AXES}
    theme = attributes.get("data-theme", "").strip() or None
    return Design(choices, secondary_palette(choices["palette"]), brand_color, theme)


def chosen(axis: str, written: str, decided: dict | None) -> Choice:
    if written.strip() in options(axis):
        return Choice(written.strip(), SOURCE)
    fallback = QUESTIONS[axis]["fallback"]
    if not isinstance(decided, dict):
        return Choice(fallback, FALLBACK)
    probabilities = {name: float(value) for name, value in (decided.get("probabilities") or {}).items() if name in options(axis)}
    option = decided.get("option")
    if option not in options(axis):
        return Choice(fallback, FALLBACK, probabilities)
    if probabilities and probabilities.get(option, 0.0) < DESIGN["confidence"]:
        return Choice(fallback, FALLBACK, probabilities)
    return Choice(option, DECIDED, probabilities)


def secondary_palette(choice: Choice) -> str | None:
    ranked = sorted(choice.probabilities.items(), key=lambda item: item[1], reverse=True)
    if choice.source != DECIDED or len(ranked) < 2 or ranked[0][0] != choice.option:
        return None
    runner_up, share = ranked[1]
    return runner_up if share >= DESIGN["secondaryShare"] * ranked[0][1] else None


def accent_hue(design: Design) -> float:
    if design.brand_color:
        return hex_oklch(design.brand_color)[2]
    primary = DESIGN["hues"][design.option("palette")]["hue"]
    if not design.secondary_palette:
        return primary
    probabilities = design.choices["palette"].probabilities
    weight = probabilities[design.secondary_palette] / (probabilities[design.secondary_palette] + probabilities[design.option("palette")])
    return (primary + DESIGN["hueBlend"] * weight * hue_difference(primary, DESIGN["hues"][design.secondary_palette]["hue"])) % 360


def hue_difference(start: float, end: float) -> float:
    return (end - start + 180) % 360 - 180


def companion_hue(design: Design, hue: float) -> tuple[float, float]:
    if design.secondary_palette:
        companion = DESIGN["hues"][design.secondary_palette]
        return companion["hue"], companion["chroma"]
    if design.brand_color and abs(hue_difference(hue, DESIGN["hues"][design.option("palette")]["hue"])) >= 40:
        intent = DESIGN["hues"][design.option("palette")]
        return intent["hue"], intent["chroma"]
    return (hue - 35) % 360, palette_chroma(design)


def palette_chroma(design: Design) -> float:
    if design.brand_color:
        return max(0.08, min(0.2, hex_oklch(design.brand_color)[1]))
    return DESIGN["hues"][design.option("palette")]["chroma"]


def neutral_hue(design: Design, hue: float) -> float:
    return DESIGN["temperatures"].get(design.option("temperature"), hue)


def design_colors(design: Design) -> dict[str, str]:
    tone = DESIGN["tones"][design.option("tone")]
    hue = accent_hue(design)
    chroma = palette_chroma(design)
    companion, companion_chroma = companion_hue(design, hue)
    lightness_offset = 0.0 if design.brand_color else DESIGN["hues"][design.option("palette")].get("lightness", 0.0)
    gray = neutral_hue(design, hue)
    colors = {}
    for token, (lightness, scale) in ((name, value) for name, value in tone.items() if isinstance(value, list)):
        if token == "accent-2":
            colors[token] = oklch_hex(lightness, companion_chroma * scale, companion)
        elif token in HUED_TOKENS:
            shifted = lightness + (lightness_offset if token == "accent" else 0.0)
            colors[token] = oklch_hex(shifted, chroma * scale, hue)
        else:
            colors[token] = oklch_hex(lightness, tone["neutralChroma"] * scale, gray)
    colors = accessible(colors, tone["dark"])
    colors["on-accent"] = WHITE if contrast_ratio(WHITE, colors["accent"]) >= contrast_ratio(colors["bg"], colors["accent"]) else colors["bg"]
    colors["cover-panel"] = colors["accent"]
    return colors


def accessible(colors: dict[str, str], is_dark: bool) -> dict[str, str]:
    adjusted = dict(colors)
    for token, minimum in DESIGN["contrast"].items():
        backdrop = adjusted["feature-bg"] if token.startswith("feature-") else adjusted["bg"]
        adjusted[token] = contrasting_shade(adjusted[token], backdrop, minimum, lighten=is_dark or token.startswith("feature-"))
    return adjusted


def contrasting_shade(color: str, backdrop: str, minimum: float, lighten: bool) -> str:
    lightness, chroma, hue = hex_oklch(color)
    step = LIGHTNESS_STEP if lighten else -LIGHTNESS_STEP
    while contrast_ratio(color, backdrop) < minimum and 0.0 < lightness < 1.0:
        lightness = min(1.0, max(0.0, lightness + step))
        color = oklch_hex(lightness, chroma, hue)
    return color


def design_tokens(design: Design) -> dict[str, str]:
    tokens = {} if design.theme else {name: f"#{value}" for name, value in design_colors(design).items()}
    if not design.theme:
        tokens["radius"] = f"{DESIGN['tones'][design.option('tone')]['radius']}px"
    faces = DESIGN["types"][design.option("type")]
    tokens["font"] = f'"{faces["body"]}", sans-serif'
    tokens["font-display"] = f'"{faces["display"]}", var(--font)'
    return tokens | DESIGN["densities"][design.option("density")]


def design_style(design: Design) -> str:
    declarations = " ".join(f"--{name}: {value};" for name, value in design_tokens(design).items())
    return f":root {{ {declarations} }}"


def palette_of(design: Design) -> dict[str, str]:
    return {name: value.lstrip("#").upper() for name, value in design_tokens(design).items() if value.startswith("#")}
