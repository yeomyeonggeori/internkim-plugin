from __future__ import annotations

from dataclasses import dataclass, field
import html
import html.parser
import itertools
import re

from charts.numbers import split_chart_list
from deck.chart_data import axis_unit_texts, chart_series, series_axes, spaced_unit
from schemas.blank_paths import withdrawn_marked
from schemas.claims import sentences

UNIT_TAGS = ("h1", "h2", "h3", "h4", "p", "li", "td", "th", "figcaption", "blockquote")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
FRAMED_ROLES = ("title", "stat", "cell", "deck")
DECK_TITLE_PATH = "deck.title"
CHART_VALUE_SEPARATOR = "\n"
UNIT_PATH = re.compile(r"^slides\[(\d+)\]\.units\[(\d+)\](?:#(\d+))?$")
SLIDE_PATH = re.compile(r"^slides\[(\d+)\]")
ROLE_NAMES = {
    "ko": {"deck": "발표 자료 제목", "slide": "슬라이드", "title": "제목", "stat": "수치", "cell": "표", "chart": "차트", "caption": "차트 설명", "item": "항목", "text": "본문"},
    "en": {"deck": "deck title", "slide": "slide", "title": "title", "stat": "figure", "cell": "table", "chart": "chart", "caption": "chart caption", "item": "item", "text": "text"},
}


@dataclass
class Node:
    tag: str
    attributes: dict[str, str]
    start: int
    inner_start: int
    inner_end: int = -1
    end: int = -1
    children: list["Node | str"] = field(default_factory=list)
    parent: "Node | None" = None

    @property
    def classes(self) -> set[str]:
        return set(self.attributes.get("class", "").split())

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def elements(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.elements()


@dataclass(frozen=True)
class Unit:
    path: str
    role: str
    text: str
    node: Node


class PositionedParser(html.parser.HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.line_offsets = [0] + [match.end() for match in re.finditer("\n", text)]
        self.root = Node("document", {}, 0, 0)
        self.stack = [self.root]

    def absolute_position(self) -> int:
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attributes):
        start = self.absolute_position()
        raw = self.get_starttag_text() or ""
        node = Node(tag, {name: value or "" for name, value in attributes}, start, start + len(raw), parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag in VOID_TAGS:
            node.inner_end = node.end = node.inner_start
            return
        self.stack.append(node)

    def handle_startendtag(self, tag, attributes):
        start = self.absolute_position()
        end = start + len(self.get_starttag_text() or "")
        self.stack[-1].children.append(Node(tag, {name: value or "" for name, value in attributes}, start, end, end, end, parent=self.stack[-1]))

    def handle_endtag(self, tag):
        position = self.absolute_position()
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                for node in self.stack[depth:]:
                    node.inner_end = position
                    node.end = position + len(f"</{tag}>")
                del self.stack[depth:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parsed(text: str) -> Node:
    parser = PositionedParser(text)
    parser.feed(text)
    parser.close()
    for node in parser.stack[1:]:
        node.inner_end = node.end = len(text)
    return parser.root


def deck_units(text: str) -> list[Unit]:
    root = parsed(text)
    sections = [node for node in root.elements() if node.tag == "section"]
    units = [Unit(DECK_TITLE_PATH, "deck", unit_text(node), node) for node in root.elements() if node.tag == "title" and unit_text(node)][:1]
    for slide_index, section in enumerate(sections):
        unit_index = 0
        for node in section.elements():
            role = unit_role(node)
            content = unit_text(node) if role else ""
            if not content:
                continue
            for sentence_index, piece in enumerate(split_unit(role, content)):
                suffix = f"#{sentence_index}" if len(split_unit(role, content)) > 1 else ""
                units.append(Unit(f"slides[{slide_index}].units[{unit_index}]{suffix}", role, piece, node))
            unit_index += 1
    return units


def unit_role(node: Node) -> str:
    if node.tag == "aside" or any(ancestor.tag == "aside" for ancestor in node.ancestors()):
        return ""
    if node.tag == "figure" and node.attributes.get("data-chart"):
        return "chart"
    if node.tag in ("section", "style", "script") or is_inside_unit(node) or any(child.tag in UNIT_TAGS for child in node.elements()):
        return ""
    if node.tag not in UNIT_TAGS:
        return text_role(node) if has_own_text(node) else ""
    if node.tag in ("h1", "h2", "h3", "h4"):
        return "title"
    if node.tag in ("td", "th"):
        return "cell"
    if node.tag == "figcaption":
        return "caption"
    return "item" if node.tag == "li" else text_role(node)


def text_role(node: Node) -> str:
    return "stat" if "value" in node.classes else "text"


def has_own_text(node: Node) -> bool:
    return any(isinstance(child, str) and child.strip() for child in node.children)


def is_inside_unit(node: Node) -> bool:
    for ancestor in node.ancestors():
        if ancestor.tag == "section":
            return False
        if ancestor.tag in UNIT_TAGS or has_own_text(ancestor):
            return True
    return False


def unit_text(node: Node) -> str:
    if node.tag == "figure":
        return chart_text(node)
    return re.sub(r"\s+", " ", "".join(visible_strings(node))).strip()


def visible_strings(node: Node):
    for child in node.children:
        if isinstance(child, str):
            yield child
        elif child.tag != "aside":
            yield from visible_strings(child)


def chart_text(node: Node) -> str:
    return CHART_VALUE_SEPARATOR.join(plotted_values(node.attributes))


def plotted_values(attributes: dict[str, str]) -> list[str]:
    labels = split_chart_list(attributes.get("data-labels", ""))
    series = chart_series(attributes)
    if isinstance(series, str):
        return []
    chart_type = attributes["data-chart"].strip()
    units = axis_unit_texts(chart_type, attributes.get("data-unit", ""))
    axes = series_axes(chart_type, len(series))
    return [
        " ".join(part for part in (label, name, f"{value}{spaced_unit(units[axis])}") if part)
        for (name, values), axis in zip(series, axes)
        for label, value in zip(labels, values)
    ]


def split_unit(role: str, content: str) -> list[str]:
    if role == "chart":
        return content.split(CHART_VALUE_SEPARATOR)
    return sentences(content) if role in ("text", "item") else [content]


def deck_claims(text: str) -> list[dict]:
    language = "ko" if re.search(r"<html[^>]*\blang=[\"']?ko", text) else "en"
    return [{"path": unit.path, "at": place(unit, language), "text": unit.text} for unit in deck_units(text)]


def place(unit: Unit, language: str) -> str:
    names = ROLE_NAMES[language]
    if unit.path == DECK_TITLE_PATH:
        return names["deck"]
    slide_number = int(UNIT_PATH.match(unit.path).group(1)) + 1
    return f"{names['slide']} {slide_number} {names[unit.role]}"


def slide_index_of(path: str) -> int | None:
    match = SLIDE_PATH.match(path)
    return int(match.group(1)) if match else None


def renumbered_path(path: str, removed_slides: set[int]) -> str | None:
    index = slide_index_of(path)
    if index is None:
        return path
    if index in removed_slides:
        return None
    shift = sum(1 for gone in removed_slides if gone < index)
    return f"slides[{index - shift}]" + path[len(f"slides[{index}]"):]


def renumbered_place(at: str, path: str, moved_path: str) -> str:
    old, new = slide_index_of(path), slide_index_of(moved_path)
    if old is None or new is None or old == new:
        return at
    for names in ROLE_NAMES.values():
        prefix = f"{names['slide']} {old + 1} "
        if at.startswith(prefix):
            return f"{names['slide']} {new + 1} " + at[len(prefix):]
    return at


def units_by_path(units: list[Unit]) -> dict[str, Unit]:
    found = {unit.path: unit for unit in units}
    for unit in units:
        found.setdefault(unit.path.partition("#")[0], unit)
    return found


def blanked_deck(text: str, paths: list[str], replacements: dict[str, str] | None = None) -> str:
    units = units_by_path(deck_units(text))
    chosen = [(path, units.get(path) or units.get(path.partition("#")[0])) for path in paths]
    chosen = [(path, unit) for path, unit in chosen if unit is not None]
    removed_slides = {slide_of(unit.node).start: slide_of(unit.node) for _, unit in chosen if unit.role == "chart"}
    replacements = replacements or {}
    edits = {}
    for path, unit in chosen:
        if unit.role == "chart" or slide_of(unit.node).start in removed_slides:
            continue
        match = UNIT_PATH.match(path)
        edits.setdefault(unit.node.start, (unit, set(), {}))[1].add(int(match.group(3)) if match and match.group(3) else -1)
    for path, new_text in replacements.items():
        unit = units.get(path) or units.get(path.partition("#")[0])
        if unit is None or unit.role == "chart" or slide_of(unit.node).start in removed_slides:
            continue
        match = UNIT_PATH.match(path)
        edits.setdefault(unit.node.start, (unit, set(), {}))[2][int(match.group(3)) if match and match.group(3) else -1] = new_text
    deck_title = units.get(DECK_TITLE_PATH)
    cover_fallback = deck_title.text if deck_title and DECK_TITLE_PATH not in paths else ""
    emptied = {unit.node.start for unit, removed, replaced in edits.values() if not kept_pieces(unit, removed, replaced, cover_fallback)} | {unit.node.start for unit in units.values() if slide_of(unit.node).start in removed_slides}
    dropped = hollow_containers(list(units.values()), emptied, set(removed_slides))
    spans = [(slide.start, slide.end, "") for slide in removed_slides.values()]
    spans += [(node.start, node.end, "") for node in dropped]
    spans += [blank_span(unit, removed, replaced, cover_fallback) for unit, removed, replaced in edits.values()]
    result = text
    for start, end, replacement in sorted(without_nested(spans), reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


BODYLESS_ROLES = ("title", "caption")
MEDIA_TAGS = ("img", "svg", "figure", "table", "canvas", "video")


def hollow_containers(units: list[Unit], emptied: set[int], removed_slides: set[int]) -> list[Node]:
    slides = {id(slide): slide for slide in (slide_of(unit.node) for unit in units if unit.node.start in emptied) if slide.tag == "section"}
    dropped: list[Node] = []
    for slide in slides.values():
        if slide.start in removed_slides:
            continue
        if is_hollow(slide, units, emptied) and not is_first_slide(slide, units):
            dropped.append(slide)
        else:
            dropped += outermost_hollow(slide, units, emptied)
    return dropped


def outermost_hollow(slide: Node, units: list[Unit], emptied: set[int]) -> list[Node]:
    found: dict[int, Node] = {}
    for unit in units:
        if unit.node.start not in emptied or slide_of(unit.node) is not slide:
            continue
        inside = list(itertools.takewhile(lambda ancestor: ancestor is not slide, unit.node.ancestors()))
        hollow = [ancestor for ancestor in inside if is_hollow(ancestor, units, emptied)]
        if hollow:
            found[hollow[-1].start] = hollow[-1]
    return list(found.values())


def is_hollow(container: Node, units: list[Unit], emptied: set[int]) -> bool:
    inside = {id(descendant) for descendant in container.elements()}
    has_survivor = any(id(unit.node) in inside and unit.role not in BODYLESS_ROLES and unit.node.start not in emptied for unit in units)
    has_media = any(descendant.tag in MEDIA_TAGS and descendant.tag != "table" for descendant in container.elements())
    return not has_survivor and not has_media


def is_first_slide(slide: Node, units: list[Unit]) -> bool:
    first = next((unit for unit in units if unit.path != DECK_TITLE_PATH), None)
    return first is not None and slide_of(first.node) is slide


def without_nested(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    return [span for span in spans if not any(other is not span and other[0] <= span[0] and span[1] <= other[1] and (other[0], other[1]) != (span[0], span[1]) and other[2] == "" for other in spans)]


def slide_of(node: Node) -> Node:
    return next((ancestor for ancestor in node.ancestors() if ancestor.tag == "section"), node)


def kept_pieces(unit: Unit, removed: set[int], replaced: dict[int, str], cover_fallback: str) -> list[str]:
    pieces = split_unit(unit.role, unit_text(unit.node))
    if -1 in replaced:
        pieces = [replaced[-1]]
    pieces = [replaced.get(index, piece) for index, piece in enumerate(pieces)]
    kept = [] if -1 in removed else [piece for index, piece in enumerate(pieces) if index not in removed]
    if not kept and unit.role == "title" and unit.path.startswith("slides[0].") and cover_fallback:
        kept = [cover_fallback]
    return kept


def blank_span(unit: Unit, removed: set[int], replaced: dict[int, str], cover_fallback: str) -> tuple[int, int, str]:
    node = unit.node
    kept = kept_pieces(unit, removed, replaced, cover_fallback)
    if not kept and unit.role not in FRAMED_ROLES:
        return node.start, node.end, ""
    return node.inner_start, node.inner_end, html.escape(" ".join(kept), quote=False)


def blank_labels(text: str, paths: list[str]) -> list[dict]:
    return withdrawn_marked([], deck_claims(text), paths, [])
