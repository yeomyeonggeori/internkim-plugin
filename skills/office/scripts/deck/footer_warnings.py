import html.parser
import re
import typing

from design_warnings import LABEL_ONLY_SLIDE_ROLES, append_deck_warning
from slide_source import has_speaker_notes_class, split_slide_sources
from slide_structure import extract_class_names


FOOTER_BASELINE_VARIANCE_RATIO = 0.05
FOOTER_CANDIDATE_MINIMUM_SLIDES = 3
FOOTER_CANDIDATE_MINIMUM_SHARE = 0.6
VOID_HTML_TAGS = {"img", "br", "hr", "meta", "input", "link", "source", "track", "wbr", "area", "base", "col", "embed"}


class DirectChildScanner(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.direct_children = []

    def handle_starttag(self, tag, attributes):
        if self.depth == 1:
            self.direct_children.append((tag, dict(attributes)))
        if tag not in VOID_HTML_TAGS:
            self.depth += 1

    def handle_startendtag(self, tag, attributes):
        if self.depth == 1:
            self.direct_children.append((tag, dict(attributes)))

    def handle_endtag(self, tag):
        if tag not in VOID_HTML_TAGS:
            self.depth = max(0, self.depth - 1)


def last_direct_child(slide_source: str) -> typing.Optional[tuple[str, dict]]:
    scanner = DirectChildScanner()
    scanner.feed(slide_source)
    for child in reversed(scanner.direct_children):
        if not is_speaker_note_child(child):
            return child
    return None


def is_speaker_note_child(child: tuple[str, dict]) -> bool:
    tag, attributes = child
    if tag == "aside" or "data-speaker-notes" in attributes:
        return True
    return has_speaker_notes_class(str(attributes.get("class") or ""))


def footer_identity(child: typing.Optional[tuple[str, dict]]) -> str:
    if child is None:
        return ""
    tag, attributes = child
    if tag == "footer":
        return "footer"
    class_value = str(attributes.get("class") or "").strip()
    if class_value:
        return "." + class_value.split()[0]
    return ""


def apply_unpinned_footer_warning(slides: list[dict[str, object]], source_text: str) -> None:
    slide_sources = split_slide_sources(source_text)
    if len(slide_sources) < FOOTER_CANDIDATE_MINIMUM_SLIDES:
        return
    last_children = [last_direct_child(slide_source) for slide_source in slide_sources]
    identities = [footer_identity(child) for child in last_children]
    candidate = most_common_footer_identity(identities)
    if not candidate:
        return
    footer_style_text = collect_rule_text(source_text, candidate) + footer_inline_styles(last_children, identities, candidate)
    if re.search(r"position\s*:\s*absolute", footer_style_text, flags=re.IGNORECASE):
        return
    if re.search(r"margin-top\s*:\s*auto", footer_style_text, flags=re.IGNORECASE):
        return
    if grow_class_present_on_footer_slides(source_text, slide_sources, identities, candidate):
        return
    append_deck_warning(
        slides,
        f"unpinnedFooterWarning: the recurring bottom element {candidate} is not pinned to the frame bottom; give it margin-top: auto (or grow the body with flex: 1) inside the flex column slide",
    )


def footer_inline_styles(last_children: list[typing.Optional[tuple[str, dict]]], identities: list[str], candidate: str) -> str:
    return " ".join(
        str(child[1].get("style") or "")
        for child, identity in zip(last_children, identities)
        if child is not None and identity == candidate
    )


def most_common_footer_identity(identities: list[str]) -> str:
    counts: dict[str, int] = {}
    for identity in identities:
        if identity:
            counts[identity] = counts.get(identity, 0) + 1
    if not counts:
        return ""
    candidate, count = max(counts.items(), key=lambda pair: pair[1])
    if count < FOOTER_CANDIDATE_MINIMUM_SLIDES or count < len(identities) * FOOTER_CANDIDATE_MINIMUM_SHARE:
        return ""
    return candidate


def collect_rule_text(source_text: str, identity: str) -> str:
    if identity.startswith("."):
        selector_pattern = re.escape(identity)
    else:
        selector_pattern = rf"(?:^|[,\s}}]){re.escape(identity)}"
    parts = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source_text):
        if re.search(selector_pattern, match.group(1)):
            parts.append(match.group(2))
    return "\n".join(parts)


def grow_class_present_on_footer_slides(
    source_text: str,
    slide_sources: list[str],
    identities: list[str],
    candidate: str,
) -> bool:
    grow_classes = flex_grow_classes(source_text)
    if not grow_classes:
        return False
    for slide_source, identity in zip(slide_sources, identities):
        if identity != candidate:
            continue
        slide_classes = set(extract_class_names(slide_source))
        if not (slide_classes & grow_classes):
            return False
    return True


def flex_grow_classes(source_text: str) -> set[str]:
    grow_classes = set()
    for match in re.finditer(r"\.([\w-]+)[^{}]*\{([^{}]*)\}", source_text):
        if re.search(r"\bflex\s*:\s*1\b|\bflex-grow\s*:\s*[1-9]", match.group(2)):
            grow_classes.add(match.group(1).casefold())
    return grow_classes


def apply_footer_baseline_warning(slides: list[dict[str, object]]) -> None:
    content_slides = [
        slide
        for slide in slides
        if slide["hasRenderEvidence"]
        and slide["contentBounds"]
        and str(slide["structure"]["slideRole"]) not in LABEL_ONLY_SLIDE_ROLES
    ]
    if len(content_slides) < 3:
        return
    bottoms = [int(slide["contentBounds"]["bottom"]) for slide in content_slides]
    height = max(int(slide["height"]) for slide in content_slides)
    variance = max(bottoms) - min(bottoms)
    if variance > height * FOOTER_BASELINE_VARIANCE_RATIO:
        append_deck_warning(
            slides,
            f"inconsistentFooterBaselineWarning: the content bottom edge varies by {variance}px across slides; keep the footer on the same baseline on every slide",
        )
