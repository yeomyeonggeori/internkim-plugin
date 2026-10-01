from __future__ import annotations

from dataclasses import dataclass, field
import html.parser
import re


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
INVISIBLE_TAGS = {"script", "style", "template", "head", "title"}
BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "td", "th", "tr", "blockquote", "figcaption", "section", "footer", "br", "ul", "ol", "table", "figure"}


@dataclass
class Element:
    tag: str
    attributes: dict[str, str]
    children: list["Element | str"] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set(self.attributes.get("class", "").split())

    def child_elements(self) -> list["Element"]:
        return [child for child in self.children if isinstance(child, Element)]

    def descendants(self) -> list["Element"]:
        found = []
        for child in self.child_elements():
            found.append(child)
            found.extend(child.descendants())
        return found

    def is_notes(self) -> bool:
        return self.tag == "aside" and "notes" in self.classes


class SourceTreeBuilder(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attributes):
        element = Element(tag, {name: value or "" for name, value in attributes})
        self.stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self.stack.append(element)

    def handle_startendtag(self, tag, attributes):
        self.stack[-1].children.append(Element(tag, {name: value or "" for name, value in attributes}))

    def handle_endtag(self, tag):
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_source(source_text: str) -> Element:
    builder = SourceTreeBuilder()
    builder.feed(source_text)
    builder.close()
    return builder.root


def find_all(element: Element, tag: str) -> list[Element]:
    return [descendant for descendant in element.descendants() if descendant.tag == tag]


def visible_text(element: Element) -> str:
    if element.tag in INVISIBLE_TAGS or element.is_notes():
        return ""
    parts = []
    for child in element.children:
        if isinstance(child, str):
            parts.append(child)
            continue
        separator = "\n" if child.tag in BLOCK_TAGS else ""
        parts.append(separator + visible_text(child) + separator)
    return "".join(parts)


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def style_texts(root: Element) -> list[str]:
    blocks = ["".join(child for child in style.children if isinstance(child, str)) for style in find_all(root, "style")]
    inline = [element.attributes["style"] for element in root.descendants() if "style" in element.attributes]
    return blocks + inline
