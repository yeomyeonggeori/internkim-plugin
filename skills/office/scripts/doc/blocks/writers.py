from __future__ import annotations

from dataclasses import dataclass, replace
import html
import mimetypes
from pathlib import Path

from fonts.registry import MONOSPACE, SANS_BODY, default_family
from charts.look import OFFICE_SERIES_COLORS
from charts.svg import chart_svg
from doc.model.charts import specification
from doc.blocks.charts import FENCE, Chart
from doc.blocks.latex_math import LatexNotReadable, latex_html
from core.image_fit import sized_style
from render.office_preview import data_uri
from doc.blocks.markdown import CodeBlock, Equation, Heading, Image, LetterPart, ListItem, Quote, Table, ThematicBreak, inline_segments, link_parts, math_latex


LIST_INDENT = "   "
BODY_FONT_FAMILY = default_family(SANS_BODY).name
CODE_FONT_FAMILY = default_family(MONOSPACE).name
CHART_FONT_FAMILY = BODY_FONT_FAMILY
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
        return file_data_uri(self.data, f"image{self.suffix}")
HTML_STYLE = f'body{{font-family:"{BODY_FONT_FAMILY}",sans-serif;line-height:1.6;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}code{{font-family:"{CODE_FONT_FAMILY}",monospace}}\n' + """pre{background:#f2f4f7;padding:.6rem .8rem;white-space:pre-wrap}table{border-collapse:collapse;margin:1rem 0}th,td{border:1px solid #999;padding:.3rem .6rem;text-align:left;vertical-align:top}th{background:#eef2f7}
img{max-width:100%}hr{border:0;border-top:1px solid #8c959f;margin:1rem 0}.equation{text-align:center;margin:1rem 0}blockquote{margin:1rem 0;border:1px solid #d0d7de;background:#f6f8fa;padding:.5rem 1rem;color:#444}"""


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
    if isinstance(block, ThematicBreak):
        return ["---"]
    if isinstance(block, Equation):
        return [block.text]
    if isinstance(block, CodeBlock):
        return [f"{FENCE}{block.language}", *block.text.split("\n"), FENCE]
    return block.text.split("\n")


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
    chart_specification = specification(chart.specification)
    svg = chart_svg(chart_specification.model(), CHART_WIDTH_PIXELS, CHART_WIDTH_PIXELS * CHART_HEIGHT_RATIO, chart_specification.look(OFFICE_SERIES_COLORS), font_family)
    return f'<figure class="chart" style="margin:12px 0">{svg}</figure>'


def letter_html(part: LetterPart) -> str:
    data = part.data
    if part.kind == "letterhead":
        logo = picture_html("logo", data["logo"], LETTER_LOGO_BOX_POINTS) if data.get("logo") else ""
        details = "".join(f'<p class="detail">{html.escape(line)}</p>' for line in data.get("details", []))
        return f'<header class="letterhead">{logo}<div class="company"><p class="name">{html.escape(data.get("name", ""))}</p>{details}</div></header>'
    if part.kind == "memo":
        rows = "".join(meta_row_html(label, value, bool(flags and flags[0])) for label, value, *flags in data.get("rows", []))
        return f'<div class="memo">{rows}</div>'
    if part.kind == "letter-address":
        return address_html(data)
    return closing_html(data)


def address_html(data: dict) -> str:
    inside = "".join(f"<p>{html.escape(line)}</p>" for line in data.get("lines", []))
    subject = f'<p class="subject-line">{html.escape(data["subject"])}</p>' if data.get("subject") else ""
    salutation = f'<p class="salutation">{html.escape(data["salutation"])}</p>' if data.get("salutation") else ""
    date = f'<p class="dateline">{html.escape(data["date"])}</p>' if data.get("date") else ""
    return f'<div class="address">{date}<div class="inside">{inside}</div>{subject}{salutation}</div>'


def closing_html(data: dict) -> str:
    seal = picture_html("seal", data["seal"], LETTER_SEAL_BOX_POINTS) if data.get("seal") else html.escape(data.get("sealMark", ""))
    side = "left" if data.get("align") == "left" else "right"
    complimentary = f'<p>{html.escape(data["complimentary"])}</p><div class="signature-space"></div>' if data.get("complimentary") else ""
    lines = "".join(f"<p>{html.escape(line)}</p>" for line in data.get("lines", [])[:-1])
    signer = f'<p class="signer"><span>{html.escape(data["lines"][-1]) if data.get("lines") else ""}</span><span class="seal-mark">{seal}</span></p>'
    return f'<div class="letter-closing {side}">{complimentary}{lines}{signer}</div>'


def meta_row_html(label: str, value: str, is_subject: bool) -> str:
    style = " subject" if is_subject else ""
    return f'<div class="row"><div class="label">{html.escape(label)}</div><div class="value{style}">{html.escape(value)}</div></div>'


LETTER_LOGO_BOX_POINTS = (120.0, 30.0)
LETTER_SEAL_BOX_POINTS = (40.0, 40.0)


def picture_html(css_class: str, path: str, box: tuple[float, float]) -> str:
    return f'<img class="{css_class}" src="{image_data_uri(path)}" style="{sized_style(Path(path), *box, "pt")}">'


def image_data_uri(path: str) -> str:
    file = Path(path)
    return file_data_uri(file.read_bytes(), file.name)


def html_block(block) -> str:
    if isinstance(block, LetterPart):
        return letter_html(block)
    if isinstance(block, SizedImage):
        return f"<div class=\"figure\"><img src=\"{block.source}\" alt=\"{html.escape(block.alt, quote=True)}\" style=\"width:{block.width}px;height:{block.height}px\"></div>"
    if isinstance(block, Heading):
        return f"<h{block.level}>{inline_html(block.text)}</h{block.level}>"
    if isinstance(block, Table):
        return html_table(block.rows, block.alignments)
    if isinstance(block, Quote):
        return f"<blockquote>{inline_html(block.text)}</blockquote>"
    if isinstance(block, Image):
        return f"<p><img src=\"{html.escape(block.source, quote=True)}\" alt=\"{html.escape(block.alt, quote=True)}\"></p>"
    if isinstance(block, ThematicBreak):
        return "<hr>"
    if isinstance(block, Equation):
        return f'<div class="equation">{math_html(block.latex, block.text, display=True)}</div>'
    if isinstance(block, CodeBlock):
        return f"<pre><code>{html.escape(block.text)}</code></pre>"
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
        latex = math_latex(segment)
        if latex is not None:
            parts.append(math_html(latex, segment))
        elif link:
            parts.append(f"<a href=\"{html.escape(link[1], quote=True)}\">{inline_html(link[0])}</a>")
        elif segment.startswith("**") and segment.endswith("**") and len(segment) > 4:
            parts.append(f"<strong>{html.escape(segment[2:-2])}</strong>")
        elif segment.startswith("*") and segment.endswith("*") and len(segment) > 2:
            parts.append(f"<em>{html.escape(segment[1:-1])}</em>")
        elif segment.startswith("`") and segment.endswith("`") and len(segment) > 2:
            parts.append(f"<code>{html.escape(segment[1:-1])}</code>")
        else:
            parts.append(html.escape(segment).replace("&lt;br&gt;", "<br>").replace("\n", "<br>"))
    return "".join(parts)


def math_html(latex: str, source: str, display: bool = False) -> str:
    try:
        return latex_html(latex, display)
    except LatexNotReadable:
        return html.escape(source)


def file_data_uri(blob: bytes, name: str) -> str:
    return data_uri(mimetypes.guess_type(name)[0] or "application/octet-stream", blob)


def embedded_image(block, source_directory: Path):
    if not isinstance(block, Image):
        return block
    image_path = source_directory / block.source
    if block.source.startswith(("http://", "https://", "data:")) or not image_path.is_file():
        return block
    return replace(block, source=file_data_uri(image_path.read_bytes(), image_path.name))
