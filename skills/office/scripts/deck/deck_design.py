from __future__ import annotations

from dataclasses import dataclass, field
import json
import math

from core.css_color import contrast_ratio, hex_oklch, oklch_hex
from core.design_rules import threshold_of
from deck.deck_kit import KIT_PATH
from deck.design_system import DesignSystem, build_design_system, token_issues
from deck.design_tokens import parse_front_matter


DESIGN_PATH = KIT_PATH / "design.json"
DESIGN = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
QUESTIONS = DESIGN["questions"]
AXES = tuple(QUESTIONS)
DECIDED = "decided"
FALLBACK = "fallback"
LIGHTNESS_STEP = 0.01
TEXT_CONTRAST = 4.5
ACCENT_CONTRAST = 4.5
SECONDARY_CONTRAST = 3.0
SECONDARY_ROLE = "secondary"
ACCENT_ROLE = "accent"
BRAND_CHROMA_RANGE = (0.08, 0.2)


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
    secondary_accent: str | None = None
    brand_color: str | None = None

    def option(self, axis: str) -> str:
        return self.choices[axis].option

    def label(self) -> str:
        return " ".join(self.option(axis) for axis in ("accent", "mood", "temperature", "type"))

    def to_json(self) -> dict:
        record = {axis: choice.to_json() for axis, choice in self.choices.items()}
        if self.secondary_accent:
            record["secondaryAccent"] = self.secondary_accent
        if self.brand_color:
            record["brandColor"] = f"#{self.brand_color}"
        return record


def options(axis: str) -> tuple[str, ...]:
    return tuple(QUESTIONS[axis]["options"])


def resolve_design(decided: dict | None, brand_color: str | None = None) -> Design:
    decided_choices = (decided or {}).get("choices") or {}
    choices = {axis: chosen(axis, decided_choices.get(axis)) for axis in AXES}
    return Design(choices, secondary_accent(choices["accent"]), brand_color)


def chosen(axis: str, decided: dict | None) -> Choice:
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


def secondary_accent(choice: Choice) -> str | None:
    ranked = sorted(choice.probabilities.items(), key=lambda item: item[1], reverse=True)
    if choice.source != DECIDED or len(ranked) < 2 or ranked[0][0] != choice.option:
        return None
    runner_up, share = ranked[1]
    return runner_up if share >= DESIGN["secondaryShare"] * ranked[0][1] else None


def hue_difference(start: float, end: float) -> float:
    return (end - start + 180) % 360 - 180


def accent_hue(design: Design) -> float:
    if design.brand_color:
        return hex_oklch(design.brand_color)[2]
    primary = DESIGN["hues"][design.option("accent")]["hue"]
    if not design.secondary_accent:
        return primary
    probabilities = design.choices["accent"].probabilities
    weight = probabilities[design.secondary_accent] / (probabilities[design.secondary_accent] + probabilities[design.option("accent")])
    return (primary + DESIGN["hueBlend"] * weight * hue_difference(primary, DESIGN["hues"][design.secondary_accent]["hue"])) % 360


def accent_chroma(design: Design) -> float:
    if design.brand_color:
        return max(BRAND_CHROMA_RANGE[0], min(BRAND_CHROMA_RANGE[1], hex_oklch(design.brand_color)[1]))
    return DESIGN["hues"][design.option("accent")]["chroma"]


def is_cream_hue(hue: float) -> bool:
    start, end = DESIGN["creamHues"]
    return start <= hue <= end


def neutral_hue(design: Design, hue: float) -> float:
    return DESIGN["temperatures"].get(design.option("temperature"), hue)


def grounds(design: Design, hue: float) -> tuple[str, str, bool]:
    mood = DESIGN["moods"][design.option("mood")]
    (ground_lightness, ground_chroma), (text_lightness, text_chroma) = mood["ground"], mood["text"]
    is_tinted = design.option("mood") != "formal" and not is_cream_hue(hue)
    ground = oklch_hex(ground_lightness, ground_chroma if is_tinted else 0.0, hue)
    text = oklch_hex(text_lightness, text_chroma, neutral_hue(design, hue))
    return ground, text, mood["dark"]


def readable(color: str, ground: str, minimum: float, is_dark: bool) -> str:
    lightness, chroma, hue = hex_oklch(color)
    step = LIGHTNESS_STEP if is_dark else -LIGHTNESS_STEP
    while contrast_ratio(color, ground) < minimum and 0.0 < lightness < 1.0:
        lightness = min(1.0, max(0.0, lightness + step))
        color = oklch_hex(lightness, chroma, hue)
    return color


def candidate_colors(design: Design, variant: dict) -> dict[str, str]:
    hue, chroma = accent_hue(design), accent_chroma(design)
    ground, text, is_dark = grounds(design, hue)
    mode = "dark" if is_dark else "light"
    accent_lightness, accent_scale = variant[mode]
    secondary_lightness = variant["secondaryLightness"][1 if is_dark else 0]
    secondary_hue = (hue + variant["secondaryTurn"]) % 360
    accent = readable(oklch_hex(accent_lightness, chroma * accent_scale, hue), ground, ACCENT_CONTRAST, is_dark)
    secondary = readable(oklch_hex(secondary_lightness, chroma * variant["secondaryScale"], secondary_hue), ground, SECONDARY_CONTRAST, is_dark)
    return {"ground": ground, "text": text, "accent": accent, "secondary": secondary}


def candidate_system(colors: dict[str, str]) -> DesignSystem:
    document = {"colors": colors, "fonts": {"display": "Paperlogy", "body": "Paperlogy"}, "type": {"title": "48px", "body": "28px"}}
    return build_design_system(document)


def passes_gate(colors: dict[str, str]) -> bool:
    return not token_issues(candidate_system(colors))


def palette_candidates(design: Design) -> list[dict]:
    candidates = []
    for name, variant in DESIGN["variants"].items():
        colors = candidate_colors(design, variant)
        if passes_gate(colors):
            candidates.append({"name": name, "colors": {role: f"#{value}" for role, value in colors.items()}, "textContrast": round(contrast_ratio(colors["text"], colors["ground"]), 1), "accentContrast": round(contrast_ratio(colors["accent"], colors["ground"]), 1)})
    return candidates


def type_pairing(design: Design) -> dict[str, str]:
    return DESIGN["types"][design.option("type")]


def stepped(value: float) -> int:
    step = DESIGN["scaleStep"]
    return step * round(value / step)


def type_scale(design: Design) -> dict[str, str]:
    density = DESIGN["densities"][design.option("density")]
    floors = threshold_of("TEXT_TOO_SMALL")
    body = max(density["base"], floors["bodyMinimum"])
    sizes = {
        "body": body,
        "small": max(stepped(body * density["smallRatio"]), floors["captionMinimum"]),
        "title": max(stepped(body * density["titleRatio"]), math.ceil(body * threshold_of("FLAT_HIERARCHY")["minimumRatio"])),
        "display": stepped(body * density["displayRatio"]),
    }
    sizes["display"] = max(sizes["display"], sizes["title"])
    return {name: f"{value}px" for name, value in sizes.items()} | {"margin": density["margin"], "gap": density["gap"]}
