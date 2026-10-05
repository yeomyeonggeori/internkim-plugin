from __future__ import annotations

from dataclasses import dataclass, field
import pathlib
import re

from core.css_color import contrast_ratio, hex_oklch, oklch_hex, parse_css_color
from core.design_rules import DESIGN_RULE_KINDS, TOKEN_STAGE, rules_for, threshold_of
from core.office_result import ERROR, WARNING, Issue, IssueKind
from deck.design_tokens import parse_front_matter
from fonts.registry import FAMILIES, MONOSPACE, SERIF_BODY


DESIGN_FILE_NAME = "DESIGN.md"
REQUIRED_COLORS = ("ground", "text", "accent", "secondary")
REQUIRED_FONTS = ("display", "body")
REQUIRED_SIZES = ("title", "body")
GLOW_KEYS = ("glow", "glow-shadow")
LIGHTNESS_STEP = 0.01
TEXT_CONTRAST = 4.5
ACCENT_CONTRAST = 3.0
LENGTH_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*(px|em)?$")
HEX_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}\b")
SHADOW_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?(?:px)?")

DESIGN_MISSING = IssueKind("DESIGN_MISSING", ERROR, "DESIGN.md is missing beside slides.html, so the deck has no design system to check", "write DESIGN.md first, as references/deck.md shows, then run office check DESIGN.md")
DESIGN_INCOMPLETE = IssueKind("DESIGN_INCOMPLETE", ERROR, "DESIGN.md lacks a token the build needs", "add the token the message names to the front matter")
DESIGN_VALUE_INVALID = IssueKind("DESIGN_VALUE_INVALID", ERROR, "a DESIGN.md token has a value the build cannot read", "write colors as #RRGGBB and sizes as px")
DESIGN_LOW_CONTRAST = IssueKind("DESIGN_LOW_CONTRAST", ERROR, "two DESIGN.md colors that must be read against each other are too close", "darken the text or accent, or lighten the ground, until the contrast reaches the ratio the message names")
REQUESTED_FONT_UNAVAILABLE = IssueKind("REQUESTED_FONT_UNAVAILABLE", WARNING, "the font the person asked for could not be used, so the deck is set in Paperlogy", "tell the person which font was not available and what was tried, and offer to rebuild the same deck when they attach the font file")
DESIGN_ISSUE_KINDS = (DESIGN_MISSING, DESIGN_INCOMPLETE, DESIGN_VALUE_INVALID, DESIGN_LOW_CONTRAST, REQUESTED_FONT_UNAVAILABLE)


@dataclass(frozen=True)
class DesignSystem:
    document: dict
    colors: dict[str, str]
    fonts: dict[str, str]
    sizes: dict[str, float]
    tracking: float
    radius: float
    border: float
    shadow: str
    weights: dict[str, int] = field(default_factory=lambda: {"display": 700, "body": 400})

    def section(self, name: str) -> dict[str, str]:
        value = self.document.get(name)
        return value if isinstance(value, dict) else {}


def read_token_document(path: pathlib.Path) -> tuple[DesignSystem | None, list[Issue]]:
    if not path.is_file():
        return None, [DESIGN_MISSING.issue(f"{DESIGN_FILE_NAME} was not found beside slides.html", DESIGN_FILE_NAME)]
    document = parse_front_matter(path.read_text(encoding="utf-8"))
    missing = missing_tokens(document)
    if missing:
        return None, [DESIGN_INCOMPLETE.issue(f"{DESIGN_FILE_NAME} has no {token}", DESIGN_FILE_NAME) for token in missing]
    invalid = invalid_values(document)
    if invalid:
        return None, [DESIGN_VALUE_INVALID.issue(f"{DESIGN_FILE_NAME} {token} is \"{value}\"", DESIGN_FILE_NAME) for token, value in invalid]
    return build_design_system(document), []


TYPOGRAPHY_RULES = "section, section * { font-family: var(--font-body); } section h1, section h2, section h3, section h4, section h5, section h6 { font-family: var(--font-display); font-weight: var(--weight-display); }"
SELECTION_KEYS = ("intent", "palette", "type", "density", "shape", "weight", "requested-font")
REQUESTED_FONT_KEY = "requested-font"
WEIGHT_KEY = "weight"


def read_design_system(path: pathlib.Path) -> tuple[DesignSystem | None, list[Issue]]:
    from deck.deck_design import palette_candidates
    from deck.deck_preparation import prepare_deck

    if not path.is_file():
        return None, [DESIGN_MISSING.issue(f"{DESIGN_FILE_NAME} was not found beside slides.html", DESIGN_FILE_NAME)]
    selection = parse_front_matter(path.read_text(encoding="utf-8"))
    design = prepare_deck().design
    candidates = {candidate["name"]: candidate for candidate in palette_candidates(design)}
    requested, font_issues = requested_font_of(selection)
    problems = selection_problems(selection, design, candidates, requested)
    if problems:
        return None, problems
    return build_design_system(selected_document(selection, design, candidates, requested)), font_issues


def requested_font_of(selection: dict):
    from fonts.registry import register_runtime_family
    from fonts.requested import BUNDLED_SOURCE, resolve_requested_font
    from schemas.known_values import load_runtime_context

    context = load_runtime_context()
    name = str(selection.get(REQUESTED_FONT_KEY) or (context.brand_font() if context else "")).strip()
    if not name:
        return None, []
    resolution = resolve_requested_font(name, context.font_paths() if context else [])
    if resolution.font is None:
        return None, [REQUESTED_FONT_UNAVAILABLE.issue(resolution.note, DESIGN_FILE_NAME)]
    if resolution.font.source.kind != BUNDLED_SOURCE:
        register_runtime_family(resolution.font.family)
    return resolution.font, []


def selection_problems(selection: dict, design, candidates: dict, requested) -> list[Issue]:
    from deck.deck_design import DESIGN, options

    unknown = [key for key in selection if key not in SELECTION_KEYS]
    if unknown:
        return [DESIGN_VALUE_INVALID.issue(f"{DESIGN_FILE_NAME} has no {key} token: it takes only {', '.join(SELECTION_KEYS)}; colors, fonts, sizes and shape come from those choices", DESIGN_FILE_NAME) for key in unknown]
    if "palette" not in selection:
        return [DESIGN_INCOMPLETE.issue(f"{DESIGN_FILE_NAME} has no palette; choose one of {', '.join(candidates)}", DESIGN_FILE_NAME)]
    type_option = str(selection.get("type") or design.option("type"))
    allowed = {
        "palette": tuple(candidates),
        "type": options("type"),
        "density": options("density"),
        "shape": tuple(DESIGN["shapes"]),
        WEIGHT_KEY: allowed_weights(type_option, requested),
    }
    return [DESIGN_VALUE_INVALID.issue(f"{DESIGN_FILE_NAME} {key} is \"{selection[key]}\"; choose one of {', '.join(choices)}", DESIGN_FILE_NAME) for key, choices in allowed.items() if key in selection and str(selection[key]) not in choices]


def default_display_weight(requested) -> int:
    from deck.deck_design import DESIGN

    if requested is None:
        return DESIGN["weights"]["display"]
    available = sorted(face.weight for face in requested.family.faces)
    return DESIGN["weights"]["display"] if DESIGN["weights"]["display"] in available else available[-1]


def allowed_weights(type_option: str, requested) -> tuple[str, ...]:
    from deck.deck_design import DESIGN

    if requested is not None:
        return tuple(str(face.weight) for face in requested.family.faces)
    return tuple(str(weight) for weight in DESIGN["types"].get(type_option, {}).get("weights", ()))


def selected_document(selection: dict, design, candidates: dict, requested) -> dict:
    from deck.deck_design import DESIGN, type_scale
    from deck.deck_design import Choice, Design

    chosen = {axis: Choice(str(selection[axis]), "decided") for axis in ("type", "density") if axis in selection}
    effective = Design({**design.choices, **chosen}, design.secondary_accent, design.brand_color)
    pairing, scale = DESIGN["types"][effective.option("type")], type_scale(effective)
    if requested is not None:
        pairing = {"display": requested.family.name, "body": requested.family.name}
    shape = DESIGN["shapes"][str(selection.get("shape") or DESIGN["defaultShape"])]
    weight = int(selection.get(WEIGHT_KEY) or default_display_weight(requested))
    colors = {role: value for role, value in candidates[str(selection["palette"])]["colors"].items()}
    return {
        "colors": colors,
        "fonts": {"display": pairing["display"], "body": pairing["body"]},
        "type": {name: scale[name] for name in ("display", "title", "body", "small")},
        "radius": shape["radius"],
        "border": shape["border"],
        "shadow": shape["shadow"],
        "spacing": {"margin": scale["margin"], "gap": scale["gap"]},
        "weights": {"display": weight, "body": DESIGN["weights"]["body"]},
    }


def missing_tokens(document: dict) -> list[str]:
    required = [("colors", name) for name in REQUIRED_COLORS] + [("fonts", name) for name in REQUIRED_FONTS] + [("type", name) for name in REQUIRED_SIZES]
    return [f"{section}.{name}" for section, name in required if not isinstance(document.get(section), dict) or not document[section].get(name)]


def invalid_values(document: dict) -> list[tuple[str, str]]:
    colors = [(f"colors.{name}", value) for name, value in document["colors"].items() if not HEX_PATTERN.fullmatch(value)]
    sizes = [(f"type.{name}", value) for name, value in document["type"].items() if name != "tracking" and length_of(value) is None]
    return colors + sizes


def length_of(value: str) -> float | None:
    match = LENGTH_PATTERN.match(value.strip())
    return float(match.group(1)) if match else None


def build_design_system(document: dict) -> DesignSystem:
    sizes = {name: length_of(value) for name, value in document["type"].items() if name != "tracking" and length_of(value) is not None}
    return DesignSystem(
        document=document,
        colors={name: value.lstrip("#").upper() for name, value in document["colors"].items()},
        fonts=dict(document["fonts"]),
        sizes=sizes,
        tracking=length_of(str(document["type"].get("tracking", "0"))) or 0.0,
        radius=length_of(str(document.get("radius", "12px"))) or 0.0,
        border=length_of(str(document.get("border", "1px"))) or 0.0,
        shadow=str(document.get("shadow", "none")),
        weights={name: int(value) for name, value in (document.get("weights") or {"display": 700, "body": 400}).items()},
    )


def token_issues(system: DesignSystem) -> list[Issue]:
    checks = {rule["code"]: TOKEN_CHECKS[rule["measure"]] for rule in rules_for(TOKEN_STAGE)}
    findings = [(code, detail) for code, check in checks.items() for detail in check(system, threshold_of(code))]
    return [DESIGN_RULE_KINDS[code].issue(f"{DESIGN_FILE_NAME}: {detail}", DESIGN_FILE_NAME) for code, detail in findings] + contrast_issues(system)


def oklch_of(system: DesignSystem, name: str) -> tuple[float, float, float]:
    return hex_oklch(system.colors[name])


def in_hue_range(hue: float, start: float, end: float) -> bool:
    return start <= hue <= end


def cream_ground(system: DesignSystem, threshold: dict) -> list[str]:
    lightness, chroma, hue = oklch_of(system, "ground")
    is_cream = lightness >= threshold["lightnessMinimum"] and chroma >= threshold["chromaMinimum"] and in_hue_range(hue, threshold["hueFrom"], threshold["hueTo"])
    return [f"colors.ground #{system.colors['ground']} is a cream or beige tint"] if is_cream else []


def ai_palette(system: DesignSystem, threshold: dict) -> list[str]:
    return purple_blue_pair(system, threshold) + cyan_on_dark(system, threshold)


def is_chromatic(color: tuple[float, float, float], threshold: dict) -> bool:
    return color[1] >= threshold["chromaMinimum"]


def purple_blue_pair(system: DesignSystem, threshold: dict) -> list[str]:
    accent, secondary = oklch_of(system, "accent"), oklch_of(system, "secondary")
    is_purple = lambda color: is_chromatic(color, threshold) and in_hue_range(color[2], threshold["purpleHueFrom"], threshold["purpleHueTo"])
    is_indigo = lambda color: is_chromatic(color, threshold) and in_hue_range(color[2], threshold["indigoHueFrom"], threshold["indigoHueTo"])
    return ["colors.accent and colors.secondary pair purple with blue"] if (is_purple(accent) and is_indigo(secondary)) or (is_indigo(accent) and is_purple(secondary)) else []


def cyan_on_dark(system: DesignSystem, threshold: dict) -> list[str]:
    if oklch_of(system, "ground")[0] > threshold["darkGroundMaximum"]:
        return []
    cyan = [name for name in ("accent", "secondary", "text") if is_chromatic(oklch_of(system, name), threshold) and in_hue_range(oklch_of(system, name)[2], threshold["cyanHueFrom"], threshold["cyanHueTo"])]
    return [f"colors.{name} is cyan on a dark ground" for name in cyan]


def bundled_names() -> dict[str, str]:
    return {name.casefold(): family.name for family in FAMILIES for name in family.names}


def first_family(value: str) -> str:
    return value.split(",")[0].strip().strip('"').strip("'")


def flat_hierarchy(system: DesignSystem, threshold: dict) -> list[str]:
    ratio = max(system.sizes["title"], system.sizes.get("display", 0)) / system.sizes["body"]
    return [f"type.title is {ratio:.2f} times type.body; the title needs at least {threshold['minimumRatio']}"] if ratio < threshold["minimumRatio"] else []


def text_size(system: DesignSystem, threshold: dict) -> list[str]:
    declared = {"body": threshold["bodyMinimum"], "small": threshold["captionMinimum"]}
    return [f"type.{name} is {system.sizes[name]:g}px; it needs at least {minimum}px at the 1600px canvas" for name, minimum in declared.items() if name in system.sizes and system.sizes[name] < minimum]


def tight_tracking(system: DesignSystem, threshold: dict) -> list[str]:
    return [f"type.tracking {system.tracking:g}em squeezes letters past {threshold['minimumEm']:g}em"] if system.tracking < threshold["minimumEm"] else []


def extreme_radius(system: DesignSystem, threshold: dict) -> list[str]:
    return [f"radius {system.radius:g}px is past {threshold['maximum']}px"] if system.radius > threshold["maximum"] else []


def shadow_blur(shadow: str) -> float:
    numbers = [float(number.removesuffix("px")) for number in SHADOW_NUMBER_PATTERN.findall(shadow.split("rgb")[0].split("#")[0])]
    return numbers[2] if len(numbers) >= 3 else 0.0


def shadow_color(shadow: str) -> str | None:
    match = HEX_PATTERN.search(shadow)
    if match:
        return match.group(0).lstrip("#")
    functional = re.search(r"rgba?\([^)]*\)", shadow)
    return parse_css_color(functional.group(0)).hex_value if functional else None


def hairline_wide_shadow(system: DesignSystem, threshold: dict) -> list[str]:
    is_hairline = 0 < system.border <= threshold["hairlineMaximum"]
    return [f"border {system.border:g}px is a hairline under a shadow {shadow_blur(system.shadow):g}px wide"] if is_hairline and shadow_blur(system.shadow) >= threshold["wideBlurMinimum"] else []


def glow_shadow(system: DesignSystem, threshold: dict) -> list[str]:
    color = shadow_color(system.shadow)
    is_glow = color is not None and shadow_blur(system.shadow) >= threshold["glowBlurMinimum"] and hex_oklch(color)[1] >= threshold["glowChromaMinimum"]
    declared = [key for key in GLOW_KEYS if key in system.document]
    return [f"{key} declares a glow" for key in declared] + (["shadow is a colored glow"] if is_glow else [])


TOKEN_CHECKS = {
    "creamGround": cream_ground,
    "aiPalette": ai_palette,
    "flatHierarchy": flat_hierarchy,
    "tightTracking": tight_tracking,
    "textSize": text_size,
    "extremeRadius": extreme_radius,
    "hairlineWideShadow": hairline_wide_shadow,
    "glowShadow": glow_shadow,
}


def contrast_issues(system: DesignSystem) -> list[Issue]:
    ground = system.colors["ground"]
    pairs = (("text", TEXT_CONTRAST), ("accent", ACCENT_CONTRAST))
    return [
        DESIGN_LOW_CONTRAST.issue(f"{DESIGN_FILE_NAME}: colors.{name} on colors.ground is {contrast_ratio(system.colors[name], ground):.2f}:1; it needs {minimum}:1", DESIGN_FILE_NAME)
        for name, minimum in pairs
        if contrast_ratio(system.colors[name], ground) < minimum
    ]


SURFACE_ACCENT_SHARE = 0.07


def blend(first: str, second: str, share: float) -> str:
    (first_lightness, first_chroma, first_hue), (second_lightness, second_chroma, second_hue) = hex_oklch(first), hex_oklch(second)
    hue = first_hue if first_chroma >= second_chroma else second_hue
    return oklch_hex(first_lightness + (second_lightness - first_lightness) * share, first_chroma + (second_chroma - first_chroma) * share, hue)


def readable_shade(color: str, ground: str, minimum: float, is_dark: bool) -> str:
    lightness, chroma, hue = hex_oklch(color)
    step = LIGHTNESS_STEP if is_dark else -LIGHTNESS_STEP
    while contrast_ratio(color, ground) < minimum and 0.0 < lightness < 1.0:
        lightness = min(1.0, max(0.0, lightness + step))
        color = oklch_hex(lightness, chroma, hue)
    return color


def derived_colors(system: DesignSystem) -> dict[str, str]:
    colors = dict(system.colors)
    ground, text = colors["ground"], colors["text"]
    is_dark = hex_oklch(ground)[0] < 0.5
    colors.setdefault("text-soft", blend(text, ground, 0.22))
    colors.setdefault("muted", readable_shade(blend(text, ground, 0.45), ground, TEXT_CONTRAST, is_dark))
    colors.setdefault("surface", blend(ground, colors["accent"], SURFACE_ACCENT_SHARE))
    colors.setdefault("line", blend(ground, text, 0.16))
    colors.setdefault("chart-muted", blend(ground, text, 0.22))
    accent = colors["accent"]
    colors["on-accent"] = "FFFFFF" if contrast_ratio("FFFFFF", accent) >= contrast_ratio(ground, accent) else ground
    return colors


def font_stack(font_value: str) -> str:
    family = bundled_names().get(first_family(font_value).casefold(), first_family(font_value))
    entry = next((candidate for candidate in FAMILIES if candidate.name == family), None)
    generic = "serif" if entry and entry.role == SERIF_BODY else "monospace" if entry and entry.role == MONOSPACE else "sans-serif"
    return f'"{family}", {generic}'


def size_tokens(system: DesignSystem) -> dict[str, str]:
    body = system.sizes["body"]
    sizes = {"display": system.sizes.get("display", system.sizes["title"]), "title": system.sizes["title"], "body": body, "small": system.sizes.get("small", max(float(threshold_of("TEXT_TOO_SMALL")["captionMinimum"]), round(body * 0.8)))}
    return {f"size-{name}": f"{value:g}px" for name, value in sizes.items()}


def design_tokens(system: DesignSystem) -> dict[str, str]:
    spacing = system.section("spacing")
    return (
        {name: f"#{value}" for name, value in derived_colors(system).items()}
        | {"font-display": font_stack(system.fonts["display"]), "font-body": font_stack(system.fonts["body"])}
        | size_tokens(system)
        | {"radius": f"{system.radius:g}px", "border": f"{system.border:g}px", "shadow": system.shadow, "weight-display": str(system.weights["display"]), "weight-body": str(system.weights["body"]), "tracking": f"{system.tracking:g}em", "margin": spacing.get("margin", "96px"), "gap": spacing.get("gap", "32px")}
    )


def design_style(system: DesignSystem) -> str:
    declarations = " ".join(f"--{name}: {value};" for name, value in design_tokens(system).items())
    return f":root {{ {declarations} }} {TYPOGRAPHY_RULES}"


def palette_of(system: DesignSystem) -> dict[str, str]:
    return {name: value.lstrip("#").upper() for name, value in design_tokens(system).items() if value.startswith("#")}
