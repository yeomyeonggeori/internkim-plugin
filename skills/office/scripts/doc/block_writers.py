from __future__ import annotations

import base64
from dataclasses import dataclass
import html
import mimetypes

from chart_svg import chart_svg
from docx_charts import specification
from markdown_charts import Chart
from markdown_blocks import Heading, Image, ListItem, Quote, Table, inline_segments, link_parts


LIST_INDENT = "   "
CHART_FONT_FAMILY = "Malgun Gothic"
CHART_WIDTH_PIXELS = 640
CHART_HEIGHT_RATIO = 0.56


@dataclass(frozen=True)
class SizedImage:
    alt: str
    data: bytes
    suffix: str
    width: int
    height: int

    @property
    def source(self) -> str:
        return data_uri(self.data, f"image{self.suffix}")
HTML_STYLE = """body{font-family:"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR","Nanum Gothic",sans-serif;line-height:1.6;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
table{border-collapse:collapse;margin:1rem 0}th,td{border:1px solid #999;padding:.3rem .6rem;text-align:left;vertical-align:top}th{background:#eef2f7}
img{max-width:100%}blockquote{margin:1rem 0;padding-left:1rem;border-left:3px solid #ccc;color:#444}"""


def markdown_text(blocks: list) -> str:
    lines: list[str] = []
    previous = None
    for block in blocks:
        if lines and not (isinstance(block, ListItem) and isinstance(previous, ListItem)):
            lines.append("")
        lines.extend(markdown_lines(block))
        previous = block
    return "\n".join(lines).rstrip() + "\n"


def markdown_lines(block) -> list[str]:
    if isinstance(block, Heading):
        return [f"{'#' * block.level} {block.text}"]
    if isinstance(block, ListItem):
        marker = "1." if block.is_numbered else "-"
        return [f"{LIST_INDENT * block.level}{marker} {block.text}"]
    if isinstance(block, Table):
        return table_markdown(block.rows, block.alignments)
    if isinstance(block, Quote):
        return [f"> {block.text}"]
    if isinstance(block, Image):
        return [f"![{block.alt}]({block.source})"]
    if isinstance(block, Chart):
        return block.source().split("\n")
    return [block.text]


def table_markdown(rows: list[list[str]], alignments: tuple[str, ...] = ()) -> list[str]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    padded = [[markdown_cell(row[index]) if index < len(row) else "" for index in range(width)] for row in rows]
    divider = "| " + " | ".join(DIVIDER_CELLS[alignments[index] if index < len(alignments) else ""] for index in range(width)) + " |"
    return ["| " + " | ".join(padded[0]) + " |", divider, *("| " + " | ".join(row) + " |" for row in padded[1:])]


DIVIDER_CELLS = {"": "---", "left": ":---", "center": ":---:", "right": "---:"}


def alignment_style(alignments: tuple[str, ...], index: int) -> str:
    alignment = alignments[index] if index < len(alignments) else ""
    return f' style="text-align:{alignment}"' if alignment else ""


def markdown_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def html_document(blocks: list, title: str) -> str:
    body = "\n".join(html_blocks(blocks))
    return (
        "<!doctype html>\n<html lang=\"ko\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>{html.escape(title)}</title>\n"
        f"<style>\n{HTML_STYLE}\n</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def html_blocks(blocks: list, chart_font_family: str = CHART_FONT_FAMILY, headings_on_new_page: frozenset[int] = frozenset()) -> list[str]:
    parts = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if isinstance(block, ListItem):
            end = index
            while end < len(blocks) and isinstance(blocks[end], ListItem):
                end += 1
            parts.append(html_list(blocks[index:end]))
            index = end
            continue
        if isinstance(block, Chart):
            parts.append(chart_html(block, chart_font_family))
        elif index in headings_on_new_page:
            parts.append(f'<h{block.level} style="break-before:page">{inline_html(block.text)}</h{block.level}>')
        else:
            parts.append(html_block(block))
        index += 1
    return parts


def chart_html(chart: Chart, font_family: str) -> str:
    svg = chart_svg(specification(chart.specification).model(), CHART_WIDTH_PIXELS, CHART_WIDTH_PIXELS * CHART_HEIGHT_RATIO, font_family)
    return f'<figure class="chart" style="margin:12px 0">{svg}</figure>'


def html_block(block) -> str:
    if isinstance(block, SizedImage):
        return f"<img src=\"{block.source}\" alt=\"{html.escape(block.alt, quote=True)}\" style=\"width:{block.width}px;height:{block.height}px\">"
    if isinstance(block, Heading):
        return f"<h{block.level}>{inline_html(block.text)}</h{block.level}>"
    if isinstance(block, Table):
        return html_table(block.rows, block.alignments)
    if isinstance(block, Quote):
        return f"<blockquote>{inline_html(block.text)}</blockquote>"
    if isinstance(block, Image):
        return f"<p><img src=\"{html.escape(block.source, quote=True)}\" alt=\"{html.escape(block.alt, quote=True)}\"></p>"
    return f"<p>{inline_html(block.text)}</p>"


def html_list(items: list[ListItem]) -> str:
    output: list[str] = []
    open_tags: list[str] = []
    for item in items:
        tag = "ol" if item.is_numbered else "ul"
        while len(open_tags) > item.level + 1:
            output.append(f"</li></{open_tags.pop()}>")
        if len(open_tags) == item.level + 1 and open_tags[-1] != tag:
            output.append(f"</li></{open_tags.pop()}>")
        if len(open_tags) == item.level + 1:
            output.append("</li>")
        while len(open_tags) < item.level + 1:
            output.append(f"<{tag}>")
            open_tags.append(tag)
        output.append(f"<li>{inline_html(item.text)}")
    while open_tags:
        output.append(f"</li></{open_tags.pop()}>")
    return "".join(output)


def html_table(rows: list[list[str]], alignments: tuple[str, ...] = ()) -> str:
    if not rows:
        return ""
    header = "".join(f"<th{alignment_style(alignments, index)}>{inline_html(cell)}</th>" for index, cell in enumerate(rows[0]))
    body = "".join("<tr>" + "".join(f"<td{alignment_style(alignments, index)}>{inline_html(cell)}</td>" for index, cell in enumerate(row)) + "</tr>" for row in rows[1:])
    return f"<table>\n<thead><tr>{header}</tr></thead>\n<tbody>{body}</tbody>\n</table>"


def inline_html(text: str) -> str:
    parts = []
    for segment in inline_segments(text):
        link = link_parts(segment)
        if link:
            parts.append(f"<a href=\"{html.escape(link[1], quote=True)}\">{inline_html(link[0])}</a>")
        elif segment.startswith("**") and segment.endswith("**") and len(segment) > 4:
            parts.append(f"<strong>{html.escape(segment[2:-2])}</strong>")
        elif segment.startswith("*") and segment.endswith("*") and len(segment) > 2:
            parts.append(f"<em>{html.escape(segment[1:-1])}</em>")
        elif segment.startswith("`") and segment.endswith("`") and len(segment) > 2:
            parts.append(f"<code>{html.escape(segment[1:-1])}</code>")
        else:
            parts.append(html.escape(segment).replace("&lt;br&gt;", "<br>"))
    return "".join(parts)


def data_uri(blob: bytes, name: str) -> str:
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return f"data:{media_type};base64,{base64.b64encode(blob).decode()}"
