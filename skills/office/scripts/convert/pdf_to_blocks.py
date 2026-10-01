from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import io
from pathlib import Path
import re
import statistics

import pdfplumber
import pypdfium2

from markdown_blocks import Heading, Image, ListItem, Paragraph, Table
from office_inputs import unlocked_pdf_bytes
from pdf_tables import page_tables


RENDER_SCALE = 2.0
LINE_TOLERANCE_POINTS = 3
WORD_GAP_FACTOR = 2.2
SPACE_FACTOR = 0.15
FURNITURE_BAND = 0.07
MINIMUM_IMAGE_POINTS = 24
HEADING_SIZE_RATIO = 1.18
BOLD_HEADING_SIZE_RATIO = 1.04
SHORT_LINE_CHARACTERS = 60
PARAGRAPH_GAP_FACTOR = 0.9
INDENT_TOLERANCE_POINTS = 4
MAXIMUM_LIST_LEVEL = 2
MAXIMUM_HEADING_LEVEL = 3
BULLET_MARKERS = frozenset("•◦▪‣–·*○■□●-")
NUMBERED_PATTERN = re.compile(r"^(?:\d{1,2}|[가-하]|[a-z])[.)]\s+|^[①-⑳]\s*")
PAGE_NUMBER_PATTERN = re.compile(r"^[\s\-–—(]*\d+(?:\s*/\s*\d+)?[\s\-–—)]*$|^page\s+\d+", re.IGNORECASE)
BOLD_FONT_PATTERN = re.compile(r"bold|black|heavy|semibold|extrabold|,b$", re.IGNORECASE)


@dataclass
class Segment:
    text: str
    markdown: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    bold: bool

    @property
    def is_bullet(self) -> bool:
        return len(self.text) > 2 and self.text[0] in BULLET_MARKERS and self.text[1] == " "

    @property
    def is_numbered(self) -> bool:
        return bool(NUMBERED_PATTERN.match(self.text))


@dataclass
class Placed:
    top: float
    x0: float
    x1: float
    content: object


@dataclass
class PageReport:
    page: int
    columns: int = 1
    paragraphs: int = 0
    headings: int = 0
    lists: int = 0
    tables: int = 0
    images: int = 0
    header_footer_lines: int = 0
    has_text: bool = True

    def to_json(self) -> dict:
        return {
            "page": self.page, "columns": self.columns, "paragraphs": self.paragraphs, "headings": self.headings,
            "listItems": self.lists, "tables": self.tables, "images": self.images,
            "headerFooterLinesDropped": self.header_footer_lines, "hasText": self.has_text,
        }


@dataclass
class PdfReading:
    blocks: list = field(default_factory=list)
    reports: list = field(default_factory=list)
    page_size_points: tuple[float, float] | None = None
    text_left: float | None = None
    text_right: float | None = None


def read_pdf_blocks(path: Path, media_directory: Path, media_prefix: str, password: str | None) -> PdfReading:
    reading = PdfReading()
    data = unlocked_pdf_bytes(str(path), password)
    rendered = pypdfium2.PdfDocument(data)
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page_segments(page) for page in pdf.pages]
            repeated = repeated_furniture(pages, pdf.pages)
            body_size = dominant_size([segment for segments in pages for segment in segments])
            heading_sizes = heading_size_ranks(pages, body_size)
            reading.page_size_points = (float(pdf.pages[0].width), float(pdf.pages[0].height)) if pdf.pages else None
            for number, (page, segments) in enumerate(zip(pdf.pages, pages), start=1):
                read_page(reading, page, segments, rendered[number - 1], number, repeated, body_size, heading_sizes, media_directory, media_prefix)
    finally:
        rendered.close()
    return reading


def page_segments(page) -> list[Segment]:
    links = [link for link in page.hyperlinks if link.get("uri")]
    words = [
        piece
        for word in page.extract_words(extra_attrs=["size", "fontname"], keep_blank_chars=False, use_text_flow=False, return_chars=True)
        for piece in split_at_links(word, links)
    ]
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda word: (round(word["top"]), word["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= LINE_TOLERANCE_POINTS:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [segment for line in lines for segment in split_line(sorted(line, key=lambda word: word["x0"]))]


def split_line(words: list[dict]) -> list[Segment]:
    groups = [[words[0]]]
    for word in words[1:]:
        previous = groups[-1][-1]
        if word["x0"] - previous["x1"] > WORD_GAP_FACTOR * max(previous["size"], word["size"]):
            groups.append([word])
        else:
            groups[-1].append(word)
    return [segment_from(group) for group in groups]


def split_at_links(word: dict, links: list[dict]) -> list[dict]:
    groups: list[list[dict]] = []
    for character in word["chars"]:
        uri = next((link["uri"] for link in links if covers(link, character)), None)
        if groups and groups[-1][0]["link"] == uri:
            groups[-1].append({**character, "link": uri})
        else:
            groups.append([{**character, "link": uri}])
    bold = bool(BOLD_FONT_PATTERN.search(word["fontname"]))
    return [
        {**word, "text": "".join(character["text"] for character in group), "x0": group[0]["x0"], "x1": group[-1]["x1"], "link": group[0]["link"], "bold": bold}
        for group in groups
    ]


def covers(link: dict, word: dict) -> bool:
    center_x, center_y = (word["x0"] + word["x1"]) / 2, (word["top"] + word["bottom"]) / 2
    return link["x0"] <= center_x <= link["x1"] and link["top"] <= center_y <= link["bottom"]


def segment_from(words: list[dict]) -> Segment:
    return Segment(
        text=joined_words(words, lambda word: word["text"]),
        markdown=marked_up(words),
        x0=min(word["x0"] for word in words),
        x1=max(word["x1"] for word in words),
        top=min(word["top"] for word in words),
        bottom=max(word["bottom"] for word in words),
        size=round(statistics.median(word["size"] for word in words), 1),
        bold=all(word["bold"] for word in words),
    )


def joined_words(words: list[dict], text_of) -> str:
    pieces = [text_of(words[0])]
    for previous, word in zip(words, words[1:]):
        if word["x0"] - previous["x1"] > SPACE_FACTOR * min(previous["size"], word["size"]):
            pieces.append(" ")
        pieces.append(text_of(word))
    return "".join(pieces)


def marked_up(words: list[dict]) -> str:
    runs: list[list[dict]] = []
    for word in words:
        if runs and (runs[-1][0]["bold"], runs[-1][0]["link"]) == (word["bold"], word["link"]):
            runs[-1].append(word)
        else:
            runs.append([word])
    every_word_bold = all(word["bold"] for word in words)
    pieces = []
    for index, run in enumerate(runs):
        text = joined_words(run, lambda word: word["text"])
        if run[0]["bold"] and not every_word_bold:
            text = f"**{text}**"
        if run[0]["link"]:
            text = f"[{text}]({run[0]['link']})"
        if index and run[0]["x0"] - runs[index - 1][-1]["x1"] > SPACE_FACTOR * min(run[0]["size"], runs[index - 1][-1]["size"]):
            pieces.append(" ")
        pieces.append(text)
    return "".join(pieces)


def furniture_key(segment: Segment) -> str:
    return re.sub(r"\d+", "#", segment.text.strip())


def in_furniture_band(segment: Segment, page_height: float) -> bool:
    return segment.bottom < page_height * FURNITURE_BAND or segment.top > page_height * (1 - FURNITURE_BAND)


def repeated_furniture(pages: list[list[Segment]], pdf_pages) -> set[str]:
    counts = Counter(
        furniture_key(segment)
        for segments, page in zip(pages, pdf_pages)
        for segment in {furniture_key(segment): segment for segment in segments if in_furniture_band(segment, float(page.height))}.values()
    )
    return {key for key, count in counts.items() if count >= 2 and len(pages) >= 2}


def is_furniture(segment: Segment, page_height: float, repeated: set[str]) -> bool:
    if not in_furniture_band(segment, page_height):
        return False
    return furniture_key(segment) in repeated or bool(PAGE_NUMBER_PATTERN.match(segment.text))


def dominant_size(segments: list[Segment]) -> float:
    weights = Counter()
    for segment in segments:
        weights[segment.size] += len(segment.text)
    return weights.most_common(1)[0][0] if weights else 10.0


def heading_size_ranks(pages: list[list[Segment]], body_size: float) -> dict[float, int]:
    sizes = sorted({segment.size for segments in pages for segment in segments if segment.size >= body_size * HEADING_SIZE_RATIO}, reverse=True)
    return {size: min(rank, MAXIMUM_HEADING_LEVEL) for rank, size in enumerate(sizes, start=1)}


def read_page(reading: PdfReading, page, segments: list[Segment], rendered_page, number: int, repeated: set[str], body_size: float, heading_sizes: dict, media_directory: Path, media_prefix: str) -> None:
    report = PageReport(number)
    page_height = float(page.height)
    content = [segment for segment in segments if not is_furniture(segment, page_height, repeated)]
    report.header_footer_lines = len(segments) - len(content)
    tables = page_tables(page)
    table_boxes = [table.bbox for table in tables]
    content = [segment for segment in content if not inside_any(segment, table_boxes)]
    placed = [Placed(segment.top, segment.x0, segment.x1, segment) for segment in content]
    placed.extend(Placed(table.bbox[1], table.bbox[0], table.bbox[2], Table(table.rows)) for table in tables)
    report.tables = len(tables)
    image = page_image_bitmap(rendered_page)
    pictures = [picture for picture in page.images if picture["x1"] - picture["x0"] >= MINIMUM_IMAGE_POINTS and picture["bottom"] - picture["top"] >= MINIMUM_IMAGE_POINTS]
    for index, picture in enumerate(pictures, start=1):
        name = f"page{number}-image{index}.png"
        crop(image, picture).save(media_directory / name)
        placed.append(Placed(float(picture["top"]), float(picture["x0"]), float(picture["x1"]), Image("", f"{media_prefix}/{name}")))
    report.images = len(pictures)
    if not content and not tables:
        report.has_text = False
        if not pictures:
            name = f"page{number}.png"
            image.save(media_directory / name)
            placed.append(Placed(0, 0, float(page.width), Image(f"page {number}", f"{media_prefix}/{name}")))
            report.images = 1
    gutter = column_gutter(content, float(page.width))
    report.columns = 2 if gutter is not None else 1
    ordered = reading_order(placed, gutter)
    track_text_edges(reading, content)
    reading.blocks.extend(page_blocks(ordered, body_size, heading_sizes, report))
    reading.reports.append(report)


def inside_any(segment: Segment, boxes: list) -> bool:
    center_x, center_y = (segment.x0 + segment.x1) / 2, (segment.top + segment.bottom) / 2
    return any(x0 <= center_x <= x1 and top <= center_y <= bottom for x0, top, x1, bottom in boxes)


def page_image_bitmap(rendered_page):
    return rendered_page.render(scale=RENDER_SCALE).to_pil().convert("RGB")


def crop(image, picture: dict):
    box = tuple(round(float(value) * RENDER_SCALE) for value in (picture["x0"], picture["top"], picture["x1"], picture["bottom"]))
    return image.crop(box)


def column_gutter(segments: list[Segment], page_width: float) -> float | None:
    if len(segments) < 8:
        return None
    best = None
    for step in range(35, 66):
        candidate = page_width * step / 100
        crossing = sum(1 for segment in segments if segment.x0 < candidate < segment.x1)
        left = sum(1 for segment in segments if segment.x1 <= candidate)
        right = sum(1 for segment in segments if segment.x0 >= candidate)
        if left >= 3 and right >= 3 and crossing <= max(1, len(segments) // 10) and (best is None or crossing < best[0]):
            best = (crossing, candidate)
    return best[1] if best else None


def reading_order(placed: list[Placed], gutter: float | None) -> list[Placed]:
    by_position = sorted(placed, key=lambda item: (item.top, item.x0))
    if gutter is None:
        return by_position
    ordered, left, right = [], [], []
    for item in by_position:
        if item.x1 <= gutter + 2:
            left.append(item)
        elif item.x0 >= gutter - 2:
            right.append(item)
        else:
            ordered.extend(left + right)
            left, right = [], []
            ordered.append(item)
    return ordered + left + right


def track_text_edges(reading: PdfReading, segments: list[Segment]) -> None:
    if not segments:
        return
    left = min(segment.x0 for segment in segments)
    right = max(segment.x1 for segment in segments)
    reading.text_left = left if reading.text_left is None else min(reading.text_left, left)
    reading.text_right = right if reading.text_right is None else max(reading.text_right, right)


def page_blocks(ordered: list[Placed], body_size: float, heading_sizes: dict, report: PageReport) -> list:
    blocks = []
    paragraph: list[Segment] = []
    list_indents = distinct_indents([item.x0 for item in ordered if is_list_start(item.content, heading_sizes)])
    for item in ordered:
        if not isinstance(item.content, Segment):
            blocks.extend(finish(paragraph, body_size, heading_sizes, list_indents, report))
            paragraph = []
            blocks.append(item.content)
            continue
        segment = item.content
        if paragraph and starts_new_paragraph(paragraph[-1], segment, body_size, heading_sizes):
            blocks.extend(finish(paragraph, body_size, heading_sizes, list_indents, report))
            paragraph = []
        paragraph.append(segment)
    blocks.extend(finish(paragraph, body_size, heading_sizes, list_indents, report))
    return blocks


def is_list_start(content, heading_sizes: dict) -> bool:
    return isinstance(content, Segment) and (content.is_bullet or content.is_numbered) and content.size not in heading_sizes and not content.bold


def distinct_indents(positions: list[float]) -> list[float]:
    indents: list[float] = []
    for position in sorted(positions):
        if not indents or position - indents[-1] > INDENT_TOLERANCE_POINTS:
            indents.append(position)
    return indents


def starts_new_paragraph(previous: Segment, segment: Segment, body_size: float, heading_sizes: dict) -> bool:
    if segment.is_bullet or segment.is_numbered:
        return True
    if abs(previous.size - segment.size) > 0.5 or previous.bold != segment.bold:
        return True
    if previous.size in heading_sizes or segment.size in heading_sizes:
        return True
    gap = segment.top - previous.bottom
    if gap > PARAGRAPH_GAP_FACTOR * segment.size or gap < -segment.size:
        return True
    return abs(segment.x0 - previous.x0) > segment.size * 1.5 and not (previous.is_bullet or previous.is_numbered)


def list_level(x0: float, list_indents: list[float]) -> int:
    level = sum(1 for indent in list_indents if indent < x0 - INDENT_TOLERANCE_POINTS)
    return min(level, MAXIMUM_LIST_LEVEL)


def finish(paragraph: list[Segment], body_size: float, heading_sizes: dict, list_indents: list[float], report: PageReport) -> list:
    if not paragraph:
        return []
    text = join_lines([segment.text for segment in paragraph])
    markdown = join_lines([segment.markdown for segment in paragraph])
    first = paragraph[0]
    if first.size in heading_sizes:
        report.headings += 1
        return [Heading(heading_sizes[first.size], text)]
    if all(segment.bold for segment in paragraph) and first.size >= body_size * BOLD_HEADING_SIZE_RATIO and len(text) <= SHORT_LINE_CHARACTERS:
        report.headings += 1
        return [Heading(min(len(heading_sizes) + 1, MAXIMUM_HEADING_LEVEL + 1), text)]
    if first.is_bullet or first.is_numbered:
        report.lists += 1
        level = list_level(first.x0, list_indents)
        if first.is_bullet:
            return [ListItem("-", level, markdown[2:].strip())]
        return [ListItem("1.", level, NUMBERED_PATTERN.sub("", markdown, count=1).strip())]
    report.paragraphs += 1
    if all(segment.bold for segment in paragraph):
        return [Paragraph(f"**{markdown}**")]
    return [Paragraph(markdown)]


def join_lines(lines: list[str]) -> str:
    joined = lines[0]
    for line in lines[1:]:
        if joined.endswith("-") and line[:1].islower():
            joined = joined[:-1] + line
        else:
            joined = f"{joined} {line}"
    return joined
