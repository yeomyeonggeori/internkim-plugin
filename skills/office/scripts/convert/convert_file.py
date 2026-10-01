#!/usr/bin/env python3
from __future__ import annotations

import base64
from dataclasses import dataclass, field, replace
import mimetypes
from pathlib import Path
import sys
import tempfile

SCRIPTS_PATH = Path(__file__).resolve().parents[1]
sys.path[1:1] = [str(SCRIPTS_PATH / "doc"), str(SCRIPTS_PATH / "sheet"), str(SCRIPTS_PATH / "deck")]

from block_writers import data_uri, html_document, markdown_text  # noqa: E402
from convert_definitions import (  # noqa: E402
    CONVERSION_APPROXIMATED, PAGE_WITHOUT_TEXT, ROUTES, UNSUPPORTED_CONVERSION, Route, find_route, normalized_extension,
)
from docx.shared import Pt  # noqa: E402
from docx_markdown import DEFAULT_DOCUMENT_FONT, DEFAULT_DOCUMENT_FONT_SIZE, markdown_document  # noqa: E402
from docx_to_blocks import read_docx_blocks  # noqa: E402
from export_document import export_pdf  # noqa: E402
from html_to_blocks import read_html_blocks  # noqa: E402
from office_preview import PAGE_SELECTOR, Preview, write_preview  # noqa: E402
from markdown_blocks import Image, parse_markdown  # noqa: E402
from office_result import Issue, OfficeArgumentParser, OfficeFailure, Result, run_command  # noqa: E402
from pdf_to_blocks import read_pdf_blocks  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx_preview import preview_document  # noqa: E402
from render.renderer import RENDER_FAILED, RENDERER_UNAVAILABLE, RenderFailed, RendererUnavailable, draw_preview  # noqa: E402
from render_docx import docx_preview  # noqa: E402
from render_xlsx import xlsx_preview  # noqa: E402
from check_pptx import SLIDE_SELECTOR, preview_fonts  # noqa: E402
from spreadsheet_import import legacy_workbook_to_xlsx  # noqa: E402
from table_conversions import DELIMITERS, delimited_to_workbook, workbook_to_delimited  # noqa: E402


MINIMUM_MARGIN_POINTS = 36
MAXIMUM_MARGIN_POINTS = 90


@dataclass
class Conversion:
    input_path: Path
    output_path: Path
    sheet: str | None
    issues: list[Issue] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    written: list[str] = field(default_factory=list)


def main() -> Result:
    arguments = parse_arguments()
    input_path = Path(arguments.input_path).expanduser()
    output_path = Path(arguments.output_path).expanduser()
    if not input_path.is_file():
        raise FileNotFoundError(2, "no such file", str(input_path))
    route = require_route(input_path, output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conversion = Conversion(input_path, output_path, arguments.sheet)
    CONVERTERS[(route.source, route.target)](conversion)
    written = conversion.written or [str(output_path)]
    details = {"route": f"{route.source} -> {route.target}", "files": written, **conversion.details}
    return Result(summary=f"converted {input_path.name} to {', '.join(Path(path).name for path in written)}", output_path=written[0], issues=tuple(conversion.issues), details=details)


def require_route(input_path: Path, output_path: Path) -> Route:
    source, target = normalized_extension(input_path.suffix), normalized_extension(output_path.suffix)
    route = find_route(source, target)
    if route is not None:
        return route
    targets = [candidate.target for candidate in ROUTES if candidate.source == source]
    suggestion = f".{source} converts to {', '.join('.' + target for target in targets)}" if targets else f"inputs this command reads: {', '.join(sorted({'.' + candidate.source for candidate in ROUTES}))}"
    raise OfficeFailure(UNSUPPORTED_CONVERSION.issue(f"no route converts .{source} to .{target}", f"{input_path.name} -> {output_path.name}", suggestion=suggestion))


def markdown_to_docx(conversion: Conversion) -> None:
    write_docx(conversion, parse_markdown(read_text(conversion.input_path)), conversion.input_path.parent)


def markdown_to_html(conversion: Conversion) -> None:
    blocks = [embedded(block, conversion.input_path.parent) for block in parse_markdown(read_text(conversion.input_path))]
    conversion.output_path.write_text(html_document(blocks, conversion.input_path.stem), encoding="utf-8")


def markdown_to_pdf(conversion: Conversion) -> None:
    text = read_text(conversion.input_path)
    conversion.issues.extend(export_pdf(parse_markdown(text), text, conversion.output_path, conversion.input_path.parent, "", DEFAULT_DOCUMENT_FONT_SIZE))


def docx_to_pdf(conversion: Conversion) -> None:
    preview, fonts = docx_preview(conversion.input_path)
    report_simplified(conversion, preview)
    with tempfile.TemporaryDirectory(prefix="office-convert-") as directory:
        draw_pdf(conversion, write_preview(preview, Path(directory)), PAGE_SELECTOR, fonts)


def workbook_to_pdf(conversion: Conversion) -> None:
    preview, fonts = xlsx_preview(conversion.input_path, conversion.sheet)
    report_simplified(conversion, preview)
    with tempfile.TemporaryDirectory(prefix="office-convert-") as directory:
        draw_pdf(conversion, write_preview(preview, Path(directory)), PAGE_SELECTOR, fonts)


def presentation_to_pdf(conversion: Conversion) -> None:
    presentation = Presentation(str(conversion.input_path))
    preview = preview_document(presentation, list(range(1, len(presentation.slides) + 1)))
    with tempfile.TemporaryDirectory(prefix="office-convert-") as directory:
        preview_path = Path(directory) / "preview.html"
        preview_path.write_text(preview.html, encoding="utf-8")
        draw_pdf(conversion, preview_path, SLIDE_SELECTOR, preview_fonts(preview.faces))


def draw_pdf(conversion: Conversion, preview_path: Path, page_selector: str, fonts: list[dict]) -> None:
    try:
        rendered = draw_preview(preview_path, page_selector, fonts, conversion.output_path.resolve(), draw_images=False)
    except RendererUnavailable as reason:
        raise OfficeFailure(RENDERER_UNAVAILABLE.issue(f"{conversion.output_path.name} was not written: {reason}", conversion.input_path.name))
    except RenderFailed as reason:
        raise OfficeFailure(RENDER_FAILED.issue(f"{conversion.output_path.name} was not written: {reason}", conversion.input_path.name))
    conversion.details["pageCount"] = len(rendered.page_sizes)


def report_simplified(conversion: Conversion, preview: Preview) -> None:
    if preview.approximations:
        listed = ", ".join(f"{count} {what}" for what, count in sorted(preview.approximations.items()))
        conversion.issues.append(CONVERSION_APPROXIMATED.issue(f"the PDF simplifies {listed}", conversion.input_path.name))


def docx_to_markdown(conversion: Conversion) -> None:
    media_name = f"{conversion.output_path.stem}-media"
    reading = read_docx_blocks(conversion.input_path, media_name)
    save_media(reading.media, conversion.output_path.parent / media_name, conversion)
    conversion.output_path.write_text(markdown_text(reading.blocks), encoding="utf-8")
    report_dropped(conversion, reading.dropped)


def docx_to_html(conversion: Conversion) -> None:
    reading = read_docx_blocks(conversion.input_path, "media")
    blocks = [with_data_source(block, reading.media) for block in reading.blocks]
    conversion.output_path.write_text(html_document(blocks, conversion.input_path.stem), encoding="utf-8")
    report_dropped(conversion, reading.dropped)


def html_to_docx(conversion: Conversion) -> None:
    with tempfile.TemporaryDirectory(prefix="office-convert-") as media_directory:
        blocks = [decoded(block, Path(media_directory)) for block in read_html_blocks(read_text(conversion.input_path))]
        write_docx(conversion, blocks, conversion.input_path.parent)


def html_to_markdown(conversion: Conversion) -> None:
    conversion.output_path.write_text(markdown_text(read_html_blocks(read_text(conversion.input_path))), encoding="utf-8")


def pdf_to_docx(conversion: Conversion) -> None:
    with tempfile.TemporaryDirectory(prefix="office-convert-") as media_directory:
        reading = read_pdf_reading(conversion, Path(media_directory), Path(media_directory).name)
        document = write_docx(conversion, reading.blocks, Path(media_directory).parent, save=False)
        match_pdf_page(document, reading)
        document.save(conversion.output_path)


def pdf_to_markdown(conversion: Conversion) -> None:
    media_name = f"{conversion.output_path.stem}-media"
    media_directory = conversion.output_path.parent / media_name
    media_directory.mkdir(parents=True, exist_ok=True)
    reading = read_pdf_reading(conversion, media_directory, media_name)
    conversion.output_path.write_text(markdown_text(reading.blocks), encoding="utf-8")
    if not any(media_directory.iterdir()):
        media_directory.rmdir()


def read_pdf_reading(conversion: Conversion, media_directory: Path, media_prefix: str):
    reading = read_pdf_blocks(conversion.input_path, media_directory, media_prefix)
    conversion.details["pages"] = [report.to_json() for report in reading.reports]
    pictures = [report.page for report in reading.reports if not report.has_text]
    if pictures:
        conversion.issues.append(PAGE_WITHOUT_TEXT.issue(f"pages {', '.join(map(str, pictures))} have no text layer and were kept as pictures", f"pages {', '.join(map(str, pictures))}"))
    approximations = ["text is reflowed into paragraphs, so line breaks and exact positions are not kept", "headings are inferred from font size and bold", "page breaks of the PDF are not kept"]
    if any(report.columns > 1 for report in reading.reports):
        approximations.append("two-column pages are read left column first, then right, into one column")
    if any(report.header_footer_lines for report in reading.reports):
        approximations.append("repeated header, footer and page number lines are dropped")
    conversion.details["approximations"] = approximations
    conversion.issues.append(CONVERSION_APPROXIMATED.issue("; ".join(approximations), conversion.input_path.name))
    return reading


def match_pdf_page(document, reading) -> None:
    if reading.page_size_points is None:
        return
    width, height = reading.page_size_points
    section = document.sections[0]
    section.page_width, section.page_height = Pt(width), Pt(height)
    left = reading.text_left if reading.text_left is not None else MAXIMUM_MARGIN_POINTS
    right = width - reading.text_right if reading.text_right is not None else MAXIMUM_MARGIN_POINTS
    section.left_margin = Pt(clamped_margin(left))
    section.right_margin = Pt(clamped_margin(right))


def clamped_margin(points: float) -> float:
    return min(max(points, MINIMUM_MARGIN_POINTS), MAXIMUM_MARGIN_POINTS)


def workbook_to_text(conversion: Conversion) -> None:
    delimiter = DELIMITERS[normalized_extension(conversion.output_path.suffix)]
    written, issues = workbook_to_delimited(conversion.input_path, conversion.output_path, delimiter, conversion.sheet)
    conversion.written = written
    conversion.issues.extend(issues)


def text_to_workbook(conversion: Conversion) -> None:
    delimiter = DELIMITERS[normalized_extension(conversion.input_path.suffix)]
    conversion.issues.extend(delimited_to_workbook(conversion.input_path, conversion.output_path, delimiter))


def legacy_workbook(conversion: Conversion) -> None:
    conversion.issues.extend(legacy_workbook_to_xlsx(conversion.input_path, conversion.output_path))


def write_docx(conversion: Conversion, blocks: list, source_directory: Path, save: bool = True):
    document, issues = markdown_document(blocks, DEFAULT_DOCUMENT_FONT, DEFAULT_DOCUMENT_FONT_SIZE, source_directory)
    conversion.issues.extend(issues)
    if save:
        document.save(conversion.output_path)
    return document


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def save_media(media: dict, directory: Path, conversion: Conversion) -> None:
    if not media:
        return
    directory.mkdir(parents=True, exist_ok=True)
    for name, blob in media.items():
        (directory / name).write_bytes(blob)
    conversion.details["mediaDirectory"] = str(directory)


def report_dropped(conversion: Conversion, dropped: dict) -> None:
    if dropped:
        listed = ", ".join(f"{count} {kind}" for kind, count in dropped.items())
        conversion.issues.append(CONVERSION_APPROXIMATED.issue(f"dropped {listed}; layout, fonts and colors are not carried", conversion.input_path.name))


def embedded(block, source_directory: Path):
    if not isinstance(block, Image):
        return block
    image_path = source_directory / block.source
    if block.source.startswith(("http://", "https://", "data:")) or not image_path.is_file():
        return block
    return replace(block, source=data_uri(image_path.read_bytes(), image_path.name))


def with_data_source(block, media: dict):
    if not isinstance(block, Image):
        return block
    name = Path(block.source).name
    return replace(block, source=data_uri(media[name], name)) if name in media else block


def decoded(block, media_directory: Path):
    if not isinstance(block, Image) or not block.source.startswith("data:") or ";base64," not in block.source:
        return block
    header, payload = block.source.split(",", 1)
    extension = mimetypes.guess_extension(header[5:].split(";", 1)[0]) or ".png"
    path = media_directory / f"image{len(list(media_directory.iterdir())) + 1}{extension}"
    path.write_bytes(base64.b64decode(payload))
    return replace(block, source=str(path))


CONVERTERS = {
    ("md", "docx"): markdown_to_docx,
    ("md", "html"): markdown_to_html,
    ("md", "pdf"): markdown_to_pdf,
    ("docx", "pdf"): docx_to_pdf,
    ("xlsx", "pdf"): workbook_to_pdf,
    ("pptx", "pdf"): presentation_to_pdf,
    ("docx", "md"): docx_to_markdown,
    ("docx", "html"): docx_to_html,
    ("html", "docx"): html_to_docx,
    ("html", "md"): html_to_markdown,
    ("pdf", "docx"): pdf_to_docx,
    ("pdf", "md"): pdf_to_markdown,
    ("xlsx", "csv"): workbook_to_text,
    ("xlsx", "tsv"): workbook_to_text,
    ("csv", "xlsx"): text_to_workbook,
    ("tsv", "xlsx"): text_to_workbook,
    ("xls", "xlsx"): legacy_workbook,
    ("ods", "xlsx"): legacy_workbook,
}


def parse_arguments():
    parser = OfficeArgumentParser(description="Convert an office file to another format; the input and output extensions pick the route. office guide convert lists every route.")
    parser.add_argument("input_path", help="the file to convert")
    parser.add_argument("output_path", help="the file to write; its extension names the target format")
    parser.add_argument("--sheet", help="xlsx to csv, tsv or pdf: convert only this sheet; default every sheet, one file each for csv and tsv")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
