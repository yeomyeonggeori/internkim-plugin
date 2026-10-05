from __future__ import annotations

from dataclasses import dataclass, field
import html
import re

from deck.deck_source import Element, VOID_TAGS, parse_source, visible_text, normalized_text


RECOMPOSE = "recompose"
TEXT_TAGS = ("p", "blockquote", "h3", "h4", "h5", "h6", "span", "em", "strong", "b")
CONTAINER_TAGS = ("div", "section", "article", "header", "footer", "main", "ul", "ol", "li", "figure")
LARGE_TEXT_CHARACTER_MAXIMUM = 240
SEQUENCE_ITEMS = (2, 6)
COLUMN_ITEMS = (2, 3)
STAGE = "display:flex;flex-direction:column;gap:var(--gap);box-sizing:border-box;width:1600px;height:900px;padding:var(--margin);"
FILL = "flex:1;min-height:0;"
ICON_ROW = "display:flex;align-items:center;gap:20px;"
ITEM = "margin:0;font-size:var(--size-body);line-height:1.4;"


@dataclass(frozen=True)
class Edit:
    id: str
    operation: str
    description: str
    section: str


@dataclass
class Content:
    opening: str
    title: str = ""
    notes: str = ""
    texts: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    charts: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)

    @property
    def has_media(self) -> bool:
        return bool(self.tables or self.charts or self.images)

    @property
    def characters(self) -> int:
        return sum(len(normalized_text(visible_text(parse_source(text)))) for text in self.texts)


def serialized(node: Element | str) -> str:
    if isinstance(node, str):
        return html.escape(node, quote=False)
    attributes = "".join(f' {name}="{html.escape(value, quote=True)}"' if value != "" else f" {name}" for name, value in node.attributes.items())
    if node.tag in VOID_TAGS:
        return f"<{node.tag}{attributes}>"
    return f"<{node.tag}{attributes}>{''.join(serialized(child) for child in node.children)}</{node.tag}>"


def has_text(node: Element) -> bool:
    return bool(normalized_text(visible_text(node)))


def is_media(node: Element) -> bool:
    return node.tag in ("table", "img", "svg") or "data-chart" in node.attributes


def holds_parts(node: Element) -> bool:
    if any(is_media(descendant) or descendant.tag in ("ul", "ol") for descendant in node.descendants()):
        return True
    return any(child.tag in CONTAINER_TAGS and has_text(child) for child in node.child_elements())


def has_icon(node: Element) -> bool:
    return any("data-icon" in child.attributes for child in node.child_elements())


def without_font_size(style: str) -> str:
    return re.sub(r"font-size\s*:[^;]*;?", "", style).strip()


def unit_attributes(node: Element) -> str:
    style = without_font_size(node.attributes.get("style", ""))
    if has_icon(node) and "display" not in style:
        style = ICON_ROW + style
    attributes = {"class": node.attributes.get("class", ""), "style": style}
    return "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in attributes.items() if value)


def unit_of(node: Element) -> str:
    return f"<div{unit_attributes(node)}>{''.join(serialized(child) for child in node.children)}</div>"


def collect(parent: Element, content: Content) -> None:
    for node in parent.children:
        if isinstance(node, str):
            if node.strip():
                content.texts.append(f"<p>{html.escape(node.strip(), quote=False)}</p>")
            continue
        if node.is_notes() or node.tag in ("style", "script"):
            continue
        if "data-logo" in node.attributes:
            continue
        if node.tag == "table":
            content.tables.append(serialized(node))
        elif node.tag in ("img", "svg"):
            content.images.append(serialized(node))
        elif "data-chart" in node.attributes:
            content.charts.append(serialized(node))
        elif node.tag in ("ul", "ol"):
            for item in node.child_elements():
                content.texts.append(f"<div>{''.join(serialized(child) for child in item.children)}</div>")
        elif node.tag in CONTAINER_TAGS and holds_parts(node):
            collect(node, content)
        elif has_text(node):
            content.texts.append(serialized(node) if node.tag in TEXT_TAGS else unit_of(node))


def section_opening(source: str) -> str:
    match = re.match(r"\s*<section\b[^>]*>", source, flags=re.IGNORECASE)
    return match.group(0).strip() if match else "<section>"


def content_of(source: str) -> Content | None:
    section = next((child for child in parse_source(source).descendants() if child.tag == "section"), None)
    if section is None:
        return None
    content = Content(section_opening(source))
    heading = next((node for node in section.descendants() if node.tag in ("h1", "h2")), None)
    notes = next((child for child in section.child_elements() if child.is_notes()), None)
    content.title = serialized(heading) if heading is not None else ""
    content.notes = serialized(notes) if notes is not None else ""
    if heading is not None:
        detach(section, heading)
    collect(section, content)
    return content


def detach(parent: Element, target: Element) -> None:
    for index, child in enumerate(parent.children):
        if child is target:
            del parent.children[index]
            return
    for child in parent.child_elements():
        detach(child, target)


def with_style(opening: str, style: str) -> str:
    if style in opening:
        return opening
    existing = re.search(r"\sstyle=([\"'])(.*?)\1", opening, flags=re.IGNORECASE | re.DOTALL)
    if existing:
        merged = existing.group(2).rstrip(";") + ";" + style
        return opening[: existing.start()] + f' style="{merged}"' + opening[existing.end():]
    return opening[:-1] + f' style="{style}">'


def assembled(content: Content, body: str, title_style: str = "flex:none;margin:0;") -> str:
    title = f'<div style="{title_style}">{content.title}</div>' if content.title else ""
    return f"{with_style(content.opening, STAGE)}{title}{body}{content.notes}</section>"


def item(markup: str, extra: str = "") -> str:
    return f'<div style="{ITEM}{extra}">{markup}</div>'


def column(items: list[str], style: str, extra: str = "") -> str:
    return f'<div style="{FILL}display:flex;flex-direction:column;justify-content:center;gap:var(--gap);{style}">{"".join(item(text, extra) for text in items)}</div>'


def text_body(content: Content, extra: str = "") -> str:
    return column(content.texts, "", extra)


def sequence_body(content: Content) -> str:
    last = len(content.texts) - 1
    rows = "".join(
        f'<div style="{ITEM}{FILL}display:flex;align-items:center;{"" if index == last else "border-bottom:1px solid var(--line);"}">{text}</div>'
        for index, text in enumerate(content.texts)
    )
    return f'<div style="{FILL}display:flex;flex-direction:column;">{rows}</div>'


def panel_body(content: Content) -> str:
    return column(content.texts, "background:var(--surface);border-radius:var(--radius);padding:48px;")


def columns_body(content: Content) -> str:
    cells = "".join(f'<div style="{ITEM}flex:1;min-width:0;display:flex;align-items:center;">{text}</div>' for text in content.texts)
    return f'<div style="{FILL}display:flex;gap:var(--gap);">{cells}</div>'


def table_body(content: Content) -> str:
    tables = f'<div style="{FILL}display:flex;flex-direction:column;justify-content:center;">{"".join(content.tables)}</div>'
    return tables + ("".join(item(text) for text in content.texts))


def side_by_side(media: list[str], content: Content, media_weight: int) -> str:
    left = f'<div style="flex:{media_weight};min-width:0;display:flex;align-items:center;justify-content:center;">{"".join(media)}</div>'
    right = column(content.texts, "min-width:0;")
    return f'<div style="{FILL}display:flex;gap:var(--gap);">{left}{right.replace(FILL, "flex:1;", 1)}</div>'


def photo_body(content: Content) -> str:
    frames = "".join(image.replace("<img", '<img style="width:100%;height:100%;object-fit:cover;"', 1) if image.startswith("<img") else image for image in content.images)
    left = f'<div style="flex:1;min-width:0;overflow:hidden;">{frames}</div>'
    right = column(content.texts, "min-width:0;").replace(FILL, "flex:1;", 1)
    return f'<div style="{FILL}display:flex;gap:var(--gap);">{left}{right}</div>'


def statement_edit(content: Content) -> str:
    title = content.title.replace(">", ' style="font-size:var(--size-display);line-height:1.15;margin:0;">', 1) if content.title else ""
    body = f'<div style="{FILL}display:flex;flex-direction:column;justify-content:center;gap:var(--gap);">{title}{"".join(item(text) for text in content.texts)}</div>'
    return f"{with_style(content.opening, STAGE)}{body}{content.notes}</section>"


def offered(content: Content) -> list[tuple[str, str, str]]:
    texts, count = content.texts, len(content.texts)
    plain = not content.has_media
    options: list[tuple[str, str, str]] = []
    if plain and count >= 1:
        options.append(("text", "the text in one column, centered in the slide", assembled(content, text_body(content))))
        if content.characters <= LARGE_TEXT_CHARACTER_MAXIMUM:
            options.append(("text-large", "the text in one column at the title size, centered in the slide", assembled(content, text_body(content, "font-size:var(--size-title);"))))
        options.append(("statement", "the title at the display size with the text under it, centered", statement_edit(content)))
    if plain and SEQUENCE_ITEMS[0] <= count <= SEQUENCE_ITEMS[1]:
        options.append(("sequence", "the items as rows divided by hairlines, each row sharing the height", assembled(content, sequence_body(content))))
    if plain and count >= 2:
        options.append(("panel", "the items together on one tinted panel that fills the slide", assembled(content, panel_body(content))))
    if plain and COLUMN_ITEMS[0] <= count <= COLUMN_ITEMS[1]:
        options.append(("columns", "the items side by side in columns of equal width", assembled(content, columns_body(content))))
    if content.tables:
        options.append(("table", "the table across the full width with the text under it", assembled(content, table_body(content))))
    if content.charts:
        options.append(("chart", "the chart on the left two thirds and the text beside it", assembled(content, side_by_side(content.charts, content, 2))))
    if content.images:
        options.append(("photo-text", "the picture filling half the slide and the text on the other half", assembled(content, photo_body(content))))
    return options


def slide_edits(source: str) -> list[Edit]:
    content = content_of(source)
    if content is None:
        return []
    return [Edit(f"{RECOMPOSE}:{name}", RECOMPOSE, description, section) for name, description, section in offered(content) if section.strip() != source.strip()]
