from __future__ import annotations

from html.parser import HTMLParser
import re

from markdown_blocks import Heading, Image, ListItem, Paragraph, Quote, Table, ThematicBreak


HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 4, "h6": 4}
BLOCK_TAGS = {"p", "div", "section", "article", "header", "footer", "main", "li", "blockquote", "pre", "figure", "figcaption", "dd", "dt", "address"}
SKIPPED_TAGS = {"script", "style", "head", "title", "noscript", "template", "svg"}
EMPHASIS_MARKERS = {"strong": "**", "b": "**", "em": "*", "i": "*", "code": "`"}
WHITESPACE = re.compile(r"\s+")


class BlockParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list = []
        self.text: list[str] = []
        self.heading_level: int | None = None
        self.lists: list[str] = []
        self.quote_depth = 0
        self.skip_depth = 0
        self.links: list[str | None] = []
        self.table_rows: list[list[str]] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag in SKIPPED_TAGS:
            self.skip_depth += 1
        elif tag in HEADING_TAGS:
            self.flush()
            self.heading_level = HEADING_TAGS[tag]
        elif tag in ("ul", "ol"):
            self.flush()
            self.lists.append(tag)
        elif tag == "blockquote":
            self.flush()
            self.quote_depth += 1
        elif tag == "table":
            self.flush()
            self.table_rows = []
        elif tag == "tr" and self.table_rows is not None:
            self.table_rows.append([])
        elif tag in ("td", "th") and self.table_rows is not None:
            self.cell = []
        elif tag == "br":
            self.write("<br>" if self.cell is not None else "\n")
        elif tag == "hr":
            self.flush()
            self.blocks.append(ThematicBreak())
        elif tag == "img":
            self.flush()
            self.blocks.append(Image(attributes.get("alt") or "", attributes.get("src") or ""))
        elif tag == "a":
            self.links.append(attributes.get("href"))
            self.write("[" if attributes.get("href") else "")
        elif tag in EMPHASIS_MARKERS:
            self.write(EMPHASIS_MARKERS[tag])
        elif tag in BLOCK_TAGS:
            self.flush()

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in HEADING_TAGS:
            self.flush()
            self.heading_level = None
        elif tag in ("ul", "ol"):
            self.flush()
            if self.lists:
                self.lists.pop()
        elif tag == "blockquote":
            self.flush()
            self.quote_depth = max(0, self.quote_depth - 1)
        elif tag in ("td", "th") and self.cell is not None and self.table_rows:
            self.table_rows[-1].append(clean("".join(self.cell)))
            self.cell = None
        elif tag == "table" and self.table_rows is not None:
            rows = [row for row in self.table_rows if row]
            if rows:
                self.blocks.append(Table(rows))
            self.table_rows = None
        elif tag == "a" and self.links:
            href = self.links.pop()
            self.write(f"]({href})" if href else "")
        elif tag in EMPHASIS_MARKERS:
            self.write(EMPHASIS_MARKERS[tag])
        elif tag in BLOCK_TAGS:
            self.flush()

    def handle_data(self, data):
        self.write(WHITESPACE.sub(" ", data))

    def write(self, text: str) -> None:
        if self.skip_depth:
            return
        if self.cell is not None:
            self.cell.append(text)
        elif self.table_rows is None:
            self.text.append(text)

    def flush(self) -> None:
        text = clean("".join(self.text))
        self.text = []
        if not text:
            return
        if self.heading_level is not None:
            self.blocks.append(Heading(self.heading_level, strip_markers(text)))
        elif self.lists:
            self.blocks.append(ListItem("1." if self.lists[-1] == "ol" else "-", len(self.lists) - 1, text))
        elif self.quote_depth:
            self.blocks.append(Quote(text))
        else:
            self.blocks.append(Paragraph(text))


def clean(text: str) -> str:
    lines = [WHITESPACE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def strip_markers(text: str) -> str:
    return re.sub(r"\*\*|`", "", text)


def read_html_blocks(html_text: str) -> list:
    parser = BlockParser()
    parser.feed(html_text)
    parser.close()
    parser.flush()
    return parser.blocks
