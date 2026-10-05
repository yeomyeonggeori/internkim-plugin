from __future__ import annotations

from dataclasses import dataclass, field
import pathlib
import re

from core.css_color import contrast_ratio, hex_oklch, oklch_hex
from core.design_rules import threshold_of
from core.office_result import ERROR, WARNING, Issue, IssueKind
from deck.design_tokens import parse_front_matter
from deck.typeface import TYPE_OPTIONS, TYPEFACE, decided_type, type_pairing


DESIGN_FILE_NAME = "DESIGN.md"
COLOR_ROLES = ("text", "accent", "secondary", "surface", "line")
PAGE_TYPES = ("cover", "content", "data", "closing")
SIZE_ROLES = ("display", "title", "body", "small")
SECTIONS = {"colors": COLOR_ROLES, "backgrounds": PAGE_TYPES, "sizes": SIZE_ROLES}
STYLE_KEY = "style"
TYPE_KEY = "type"
REQUESTED_FONT_KEY = "requested-font"
SHEET_KEYS = (STYLE_KEY, *SECTIONS, TYPE_KEY, REQUESTED_FONT_KEY)
TEXT_CONTRAST = 4.5
ACCENT_CONTRAST = 3.0
LIGHTNESS_STEP = 0.01
HEX_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}")
PIXEL_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*px")
READABLE_INKS = ("FFFFFF", "000000")
KIT_RADIUS = "12px"

DESIGN_MISSING = IssueKind("DESIGN_MISSING", ERROR, "DESIGN.md, the deck's style sheet, is missing", "write DESIGN.md first, as references/deck.md shows, then run office check DESIGN.md")
DESIGN_INCOMPLETE = IssueKind("DESIGN_INCOMPLETE", ERROR, "the style sheet lacks a value the deck needs", "add the value the message names to the front matter of DESIGN.md")
DESIGN_VALUE_INVALID = IssueKind("DESIGN_VALUE_INVALID", ERROR, "a style sheet value cannot be used", "write colors as #RRGGBB and sizes as px at or above the floors the message names, and use only the keys it lists")
DESIGN_LOW_CONTRAST = IssueKind("DESIGN_LOW_CONTRAST", ERROR, "two style sheet colors that must be read against each other are too close", "darken or lighten one of the two until the contrast reaches the ratio the message names")
REQUESTED_FONT_UNAVAILABLE = IssueKind("REQUESTED_FONT_UNAVAILABLE", WARNING, "the font the person asked for could not be used, so the deck is set in Paperlogy", "tell the person which font was not available and what was tried, and offer to rebuild the same deck when they attach the font file")
DESIGN_ISSUE_KINDS = (DESIGN_MISSING, DESIGN_INCOMPLETE, DESIGN_VALUE_INVALID, DESIGN_LOW_CONTRAST, REQUESTED_FONT_UNAVAILABLE)


@dataclass(frozen=True)
class DesignSystem:
    style: str
    colors: dict[str, str]
    backgrounds: dict[str, str]
    sizes: dict[str, float]
    fonts: dict[str, str]
    weights: dict[str, int] = field(default_factory=lambda: dict(TYPEFACE["weights"]))


def read_design_system(path: pathlib.Path) -> tuple[DesignSystem | None, list[Issue]]:
    if not path.is_file():
        return None, [DESIGN_MISSING.issue(f"{DESIGN_FILE_NAME} was not found beside outline.json", DESIGN_FILE_NAME)]
    sheet = parse_front_matter(path.read_text(encoding="utf-8"))
    problems = sheet_problems(sheet)
    if problems:
        return None, problems
    requested, font_issues = requested_font_of(sheet)
    system = design_system_of(sheet, requested)
    low_contrast = contrast_issues(system)
    return (None, low_contrast) if low_contrast else (system, font_issues)


def sheet_problems(sheet: dict) -> list[Issue]:
    unknown = [key for key in sheet if key not in SHEET_KEYS]
    if unknown:
        return [DESIGN_VALUE_INVALID.issue(f"{DESIGN_FILE_NAME} has no {key}: it takes {', '.join(SHEET_KEYS)}", DESIGN_FILE_NAME) for key in unknown]
    missing = missing_values(sheet)
    if missing:
        return [DESIGN_INCOMPLETE.issue(f"{DESIGN_FILE_NAME} has no {name}", DESIGN_FILE_NAME) for name in missing]
    return [DESIGN_VALUE_INVALID.issue(f"{DESIGN_FILE_NAME}: {problem}", DESIGN_FILE_NAME) for problem in invalid_values(sheet)]


def missing_values(sheet: dict) -> list[str]:
    missing = [] if str(sheet.get(STYLE_KEY) or "").strip() else [STYLE_KEY]
    for section, roles in SECTIONS.items():
        values = sheet.get(section) if isinstance(sheet.get(section), dict) else {}
        missing += [f"{section}.{role}" for role in roles if not values.get(role)]
    return missing


def invalid_values(sheet: dict) -> list[str]:
    extra = [f"{section}.{name} is not one of {', '.join(roles)}" for section, roles in SECTIONS.items() for name in sheet[section] if name not in roles]
    colors = [f"{section}.{name} \"{value}\" is not #RRGGBB" for section in ("colors", "backgrounds") for name, value in sheet[section].items() if not HEX_PATTERN.fullmatch(value)]
    sizes = [f"sizes.{name} \"{value}\" is not a px size" for name, value in sheet["sizes"].items() if pixels(value) is None]
    floors = [] if sizes else size_floor_problems(sheet["sizes"])
    typeface = [f"type \"{sheet[TYPE_KEY]}\" is not one of {', '.join(TYPE_OPTIONS)}"] if TYPE_KEY in sheet and sheet[TYPE_KEY] not in TYPE_OPTIONS else []
    return extra + colors + sizes + floors + typeface


def size_floor_problems(sizes: dict[str, str]) -> list[str]:
    floors = threshold_of("TEXT_TOO_SMALL")
    minimums = {"display": floors["bodyMinimum"], "title": floors["bodyMinimum"], "body": floors["bodyMinimum"], "small": floors["captionMinimum"]}
    return [f"sizes.{name} is {pixels(sizes[name]):g}px; it needs at least {minimum}px on the 1600px slide" for name, minimum in minimums.items() if pixels(sizes[name]) < minimum]


def pixels(value: str) -> float | None:
    match = PIXEL_PATTERN.fullmatch(str(value).strip())
    return float(match.group(1)) if match else None


def requested_font_of(sheet: dict):
    from fonts.registry import register_runtime_family
    from fonts.requested import BUNDLED_SOURCE, resolve_requested_font
    from schemas.known_values import load_runtime_context

    context = load_runtime_context()
    name = str(sheet.get(REQUESTED_FONT_KEY) or (context.brand_font() if context else "")).strip()
    if not name:
        return None, []
    resolution = resolve_requested_font(name, context.font_paths() if context else [])
    if resolution.font is None:
        return None, [REQUESTED_FONT_UNAVAILABLE.issue(resolution.note, DESIGN_FILE_NAME)]
    if resolution.font.source.kind != BUNDLED_SOURCE:
        register_runtime_family(resolution.font.family)
    return resolution.font, []


def design_system_of(sheet: dict, requested) -> DesignSystem:
    from schemas.known_values import load_runtime_context

    context = load_runtime_context()
    pairing = type_pairing(str(sheet.get(TYPE_KEY) or decided_type(context.deck_design if context else None)))
    family = None if requested is None else requested.family.name
    return DesignSystem(
        style=str(sheet[STYLE_KEY]).strip(),
        colors={role: hex_digits(sheet["colors"][role]) for role in COLOR_ROLES},
        backgrounds={page_type: hex_digits(sheet["backgrounds"][page_type]) for page_type in PAGE_TYPES},
        sizes={role: pixels(sheet["sizes"][role]) for role in SIZE_ROLES},
        fonts={"display": family or pairing["display"], "body": family or pairing["body"]},
        weights=dict(TYPEFACE["weights"]) | ({} if requested is None else {"display": display_weight_of(requested)}),
    )


def display_weight_of(requested) -> int:
    available = sorted(face.weight for face in requested.family.faces)
    preferred = TYPEFACE["weights"]["display"]
    return preferred if preferred in available else available[-1]


def hex_digits(value: str) -> str:
    return value.strip().lstrip("#").upper()


def contrast_issues(system: DesignSystem) -> list[Issue]:
    pairs = (
        ("colors.text", system.colors["text"], "backgrounds.content", system.backgrounds["content"], TEXT_CONTRAST),
        ("colors.text", system.colors["text"], "backgrounds.data", system.backgrounds["data"], TEXT_CONTRAST),
        ("colors.text", system.colors["text"], "colors.surface", system.colors["surface"], TEXT_CONTRAST),
        ("colors.accent", system.colors["accent"], "backgrounds.content", system.backgrounds["content"], ACCENT_CONTRAST),
    )
    return [
        DESIGN_LOW_CONTRAST.issue(f"{DESIGN_FILE_NAME}: {first} on {second} is {contrast_ratio(ink, ground):.2f}:1; it needs {minimum}:1", DESIGN_FILE_NAME)
        for first, ink, second, ground, minimum in pairs
        if contrast_ratio(ink, ground) < minimum
    ]


def blend(first: str, second: str, share: float) -> str:
    (first_lightness, first_chroma, first_hue), (second_lightness, second_chroma, second_hue) = hex_oklch(first), hex_oklch(second)
    hue = first_hue if first_chroma >= second_chroma else second_hue
    return oklch_hex(first_lightness + (second_lightness - first_lightness) * share, first_chroma + (second_chroma - first_chroma) * share, hue)


def readable_shade(color: str, ground: str, minimum: float) -> str:
    lightness, chroma, hue = hex_oklch(color)
    step = LIGHTNESS_STEP if hex_oklch(ground)[0] < 0.5 else -LIGHTNESS_STEP
    while contrast_ratio(color, ground) < minimum and 0.0 < lightness < 1.0:
        lightness = min(1.0, max(0.0, lightness + step))
        color = oklch_hex(lightness, chroma, hue)
    return color


def readable_ink(text: str, ground: str) -> str:
    if contrast_ratio(text, ground) >= TEXT_CONTRAST:
        return text
    return max(READABLE_INKS, key=lambda ink: contrast_ratio(ink, ground))


def derived_colors(system: DesignSystem) -> dict[str, str]:
    ground, text, accent = system.backgrounds["content"], system.colors["text"], system.colors["accent"]
    return {
        **system.colors,
        "ground": ground,
        **{f"bg-{page_type}": color for page_type, color in system.backgrounds.items()},
        **{f"on-{page_type}": readable_ink(text, color) for page_type, color in system.backgrounds.items()},
        "text-soft": blend(text, ground, 0.22),
        "muted": readable_shade(blend(text, ground, 0.45), ground, TEXT_CONTRAST),
        "chart-muted": blend(ground, text, 0.22),
        "on-accent": "FFFFFF" if contrast_ratio("FFFFFF", accent) >= contrast_ratio(ground, accent) else ground,
    }


def font_stack(family: str) -> str:
    return f'"{family}", sans-serif'


def design_tokens(system: DesignSystem) -> dict[str, str]:
    return (
        {name: f"#{value}" for name, value in derived_colors(system).items()}
        | {"font-display": font_stack(system.fonts["display"]), "font-body": font_stack(system.fonts["body"])}
        | {f"size-{name}": f"{value:g}px" for name, value in system.sizes.items()}
        | {"weight-display": str(system.weights["display"]), "weight-body": str(system.weights["body"]), "radius": KIT_RADIUS}
    )


TYPOGRAPHY_RULES = "section, section * { font-family: var(--font-body); } section h1, section h2, section h3, section h4, section h5, section h6 { font-family: var(--font-display); font-weight: var(--weight-display); }"


def page_type_rules() -> str:
    return " ".join(f'section[data-type="{page_type}"] {{ --ground: var(--bg-{page_type}); background: var(--bg-{page_type}); color: var(--on-{page_type}); }}' for page_type in PAGE_TYPES)


def design_style(system: DesignSystem) -> str:
    declarations = " ".join(f"--{name}: {value};" for name, value in design_tokens(system).items())
    return f":root {{ {declarations} }} {TYPOGRAPHY_RULES} {page_type_rules()}"


def palette_of(system: DesignSystem) -> dict[str, str]:
    return {name: value.lstrip("#").upper() for name, value in design_tokens(system).items() if value.startswith("#")}


def style_summary(system: DesignSystem) -> dict:
    tokens = design_tokens(system)
    return {"style": system.style, "colors": {name: tokens[name] for name in ("text", "accent", "secondary", "surface", "line", "bg-cover", "bg-content", "bg-data", "bg-closing")}, "fonts": dict(system.fonts)}
