from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from PIL import Image as PillowImage, UnidentifiedImageError

from doc_definitions import IMAGE_UNAVAILABLE
from markdown_charts import Chart, number_text
from markdown_blocks import Equation, Heading, Image, ListItem, Paragraph, Quote, Table, ThematicBreak, has_link, inline_segments, link_parts, local_image_problem, strip_inline_markers
from office_result import Issue


HEADING_SIZES = {1: 20, 2: 15, 3: 12.5, 4: 11}
LIST_INDENT = 4
NESTED_LIST_INDENT = 6
QUOTE_INDENT = 8
LINK_COLOR = (5, 99, 193)
TEXT_COLOR = (0, 0, 0)
RULE_COLOR = (140, 149, 159)
DEFAULT_IMAGE_DOTS_PER_INCH = 96
MILLIMETERS_PER_INCH = 25.4


class MarkdownPdf:
    def __init__(self, family: str, font_size: float, source_directory: Path):
        self.pdf = FPDF(format="A4")
        self.pdf.set_auto_page_break(auto=True, margin=18)
        self.pdf.add_page()
        self.family = family
        self.font_size = font_size
        self.source_directory = source_directory

    def add_block(self, block) -> list[Issue]:
        if isinstance(block, Heading):
            self.write_line(block.text, HEADING_SIZES[block.level], "B", spacing=3)
        elif isinstance(block, Table):
            self.add_table(block.rows)
        elif isinstance(block, ListItem):
            marker = "• " if not block.is_numbered else block.marker + " "
            self.write_line(marker + block.text, self.font_size, indent=LIST_INDENT + NESTED_LIST_INDENT * block.level, spacing=1)
        elif isinstance(block, Quote):
            self.write_line(block.text, self.font_size, "I", indent=QUOTE_INDENT)
        elif isinstance(block, Image):
            return self.add_image(block)
        elif isinstance(block, Chart):
            self.add_chart_table(block)
        elif isinstance(block, (Paragraph, Equation)):
            self.write_line(block.text, self.font_size)
        elif isinstance(block, ThematicBreak):
            self.add_rule()
        return []

    def add_rule(self) -> None:
        self.pdf.ln(2)
        self.pdf.set_draw_color(*RULE_COLOR)
        self.pdf.line(self.pdf.l_margin, self.pdf.get_y(), self.pdf.w - self.pdf.r_margin, self.pdf.get_y())
        self.pdf.ln(4)

    def write_line(self, text: str, size: float, style: str = "", indent: float = 0, spacing: float = 2) -> None:
        self.pdf.set_font(self.family, style, size)
        if has_link(text):
            self.write_linked_line(text, size, indent)
        else:
            self.pdf.set_x(self.pdf.l_margin + indent)
            self.pdf.multi_cell(0, size * 0.55, strip_inline_markers(text))
        self.pdf.ln(spacing)

    def write_linked_line(self, text: str, size: float, indent: float) -> None:
        line_height = size * 0.55
        original_margin = self.pdf.l_margin
        self.pdf.set_left_margin(original_margin + indent)
        self.pdf.set_x(original_margin + indent)
        for segment in inline_segments(text):
            link = link_parts(segment)
            if link:
                self.pdf.set_text_color(*LINK_COLOR)
                self.pdf.write(line_height, strip_inline_markers(link[0]), link=link[1])
                self.pdf.set_text_color(*TEXT_COLOR)
            else:
                self.pdf.write(line_height, strip_inline_markers(segment))
        self.pdf.ln(line_height)
        self.pdf.set_left_margin(original_margin)

    def add_chart_table(self, chart: Chart) -> None:
        specification = chart.specification
        if specification.get("title"):
            self.write_line(specification["title"], self.font_size, "B", spacing=1)
        header = ["", *(entry["name"] for entry in specification["series"])]
        rows = [[str(category), *(number_text(entry["values"][index]) for entry in specification["series"])] for index, category in enumerate(specification["categories"])]
        self.add_table([header, *rows])

    def add_table(self, rows: list[list[str]]) -> None:
        self.pdf.set_font(self.family, "", self.font_size)
        with self.pdf.table() as table:
            for row in rows:
                table_row = table.row()
                for cell in row:
                    table_row.cell(strip_inline_markers(cell))
        self.pdf.ln(3)

    def add_image(self, image: Image) -> list[Issue]:
        image_path = self.source_directory / image.source
        problem = local_image_problem(image.source, image_path)
        if problem:
            return [self.unavailable_image(image, problem)]
        try:
            width = image_width_millimeters(image_path)
        except (UnidentifiedImageError, OSError) as error:
            return [self.unavailable_image(image, f"could not be read ({error})")]
        self.pdf.image(str(image_path), x=self.pdf.l_margin, w=min(width, self.pdf.epw))
        self.pdf.ln(2)
        return []

    def unavailable_image(self, image: Image, reason: str) -> Issue:
        self.write_line(image.alt or image.source, self.font_size, "I")
        return IMAGE_UNAVAILABLE.issue(f"image {image.source} {reason}; wrote its alt text instead", image.source)


def image_width_millimeters(image_path: Path) -> float:
    with PillowImage.open(image_path) as image:
        dots_per_inch = image.info.get("dpi", (DEFAULT_IMAGE_DOTS_PER_INCH,))[0] or DEFAULT_IMAGE_DOTS_PER_INCH
        return image.width / float(dots_per_inch) * MILLIMETERS_PER_INCH
