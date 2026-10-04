from __future__ import annotations

from dataclasses import dataclass, field
import html
import html.parser
import re

from schemas.claims import sentences

UNIT_TAGS = ("h1", "h2", "h3", "h4", "p", "li", "td", "th", "figcaption", "blockquote")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
FRAMED_ROLES = ("title", "stat", "cell", "deck")
DECK_TITLE_PATH = "deck.title"
UNIT_PATH = re.compile(r"^slides\[(\d+)\]\.units\[(\d+)\](?:#(\d+))?$")
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
    if any(ancestor.tag == "aside" for ancestor in node.ancestors()):
        return ""
    if node.tag == "figure" and node.attributes.get("data-chart"):
        return "chart"
    if node.tag not in UNIT_TAGS or any(child.tag in UNIT_TAGS for child in node.elements()):
        return ""
    if node.tag in ("h1", "h2", "h3", "h4"):
        return "title"
    if node.tag in ("td", "th"):
        return "cell"
    if node.tag == "figcaption":
        return "caption"
    if "value" in node.classes:
        return "stat"
    return "item" if node.tag == "li" else "text"


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
    labels = [label.strip() for label in node.attributes.get("data-labels", "").split(",")]
    values = [value.strip() for value in node.attributes.get("data-values", "").split(",")]
    unit = node.attributes.get("data-unit", "")
    pairs = ", ".join(f"{label} {value}{unit}" for label, value in zip(labels, values) if label or value)
    series = node.attributes.get("data-series", "")
    return f"{node.attributes['data-chart']} chart: {pairs}" + (f" ({series})" if series else "")


def split_unit(role: str, content: str) -> list[str]:
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


def blanked_deck(text: str, paths: list[str]) -> str:
    units = {unit.path: unit for unit in deck_units(text)}
    chosen = [(path, units.get(path) or units.get(path.partition("#")[0])) for path in paths]
    chosen = [(path, unit) for path, unit in chosen if unit is not None]
    removed_slides = {slide_of(unit.node).start: slide_of(unit.node) for _, unit in chosen if unit.role == "chart"}
    edits = {}
    for path, unit in chosen:
        if unit.role == "chart" or slide_of(unit.node).start in removed_slides:
            continue
        match = UNIT_PATH.match(path)
        edits.setdefault(unit.node.start, (unit, set()))[1].add(int(match.group(3)) if match and match.group(3) else -1)
    deck_title = units.get(DECK_TITLE_PATH)
    cover_fallback = deck_title.text if deck_title and DECK_TITLE_PATH not in paths else ""
    result = text
    spans = [(slide.start, slide.end, "") for slide in removed_slides.values()]
    spans += [blank_span(unit, removed, cover_fallback) for unit, removed in edits.values()]
    for start, end, replacement in sorted(spans, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def slide_of(node: Node) -> Node:
    return next((ancestor for ancestor in node.ancestors() if ancestor.tag == "section"), node)


def blank_span(unit: Unit, removed: set[int], cover_fallback: str) -> tuple[int, int, str]:
    node = unit.node
    pieces = split_unit(unit.role, unit_text(node))
    kept = [] if -1 in removed else [piece for index, piece in enumerate(pieces) if index not in removed]
    if not kept and unit.role == "title" and unit.path.startswith("slides[0].") and cover_fallback:
        kept = [cover_fallback]
    if not kept and unit.role not in FRAMED_ROLES:
        return node.start, node.end, ""
    return node.inner_start, node.inner_end, html.escape(" ".join(kept), quote=False)


def blank_labels(text: str, paths: list[str]) -> list[dict]:
    places = {claim["path"]: claim["at"] for claim in deck_claims(text)}
    return [{"field": path, "label": places.get(path, path)} for path in dict.fromkeys(paths)]
