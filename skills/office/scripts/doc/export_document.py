#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from fonts.docx_embedding import save_document
from doc.docx_markdown import DEFAULT_DOCUMENT_FONT, markdown_document
from doc.document_pdf import render_document_pdf
from doc.latex_math import math_issues
from doc.markdown_blocks import Heading, parse_markdown
from doc.markdown_charts import require_valid_charts
from core.office_inputs import read_text_input
from fonts.registry import BODY_SIZE_POINTS, SANS_BODY, default_family
from core.office_outputs import require_output_extension
from core.office_result import Issue, OfficeArgumentParser, Result, run_command


EXPORT_EXTENSIONS = (".docx", ".pdf")


def main() -> Result:
    arguments = parse_arguments()
    markdown_path = Path(arguments.markdown_path)
    output_path = Path(arguments.output) if arguments.output else markdown_path.with_suffix(".docx")
    output_format = require_output_extension(str(output_path), EXPORT_EXTENSIONS).lstrip(".")
    markdown_text = read_text_input(arguments.markdown_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = parse_markdown(markdown_text)
    require_valid_charts(blocks, markdown_path.name)
    if output_format == "pdf":
        issues = export_pdf(blocks, output_path, markdown_path.parent, arguments.font_path)
    else:
        document, issues = markdown_document(blocks, arguments.font, arguments.font_size, markdown_path.parent)
        save_document(document, output_path)
    return Result(summary=f"exported {output_path} from {markdown_path}", output_path=str(output_path), issues=(*math_issues(blocks, output_format), *issues))


def export_pdf(blocks: list, output_path: Path, source_directory: Path, font_path_argument: str) -> list[Issue]:
    return render_document_pdf(blocks, output_path, source_directory, document_title(blocks, output_path), Path(font_path_argument) if font_path_argument else None)


def document_title(blocks: list, output_path: Path) -> str:
    return next((block.text for block in blocks if isinstance(block, Heading)), output_path.stem)


def parse_arguments():
    parser = OfficeArgumentParser()
    parser.add_argument("markdown_path", help="path to content.md")
    parser.add_argument("--output", help="the file to write; its extension, .docx or .pdf, picks the format; default <markdown name>.docx beside the markdown")
    parser.add_argument("--font", default=DEFAULT_DOCUMENT_FONT, help="base font family name for docx")
    parser.add_argument("--font-size", type=float, default=BODY_SIZE_POINTS, help="body size in points for docx")
    parser.add_argument("--font-path", default="", help=f"Korean-capable TTF for pdf output instead of the bundled {default_family(SANS_BODY).name}; a Bold file beside it is used for bold")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_command(main))
