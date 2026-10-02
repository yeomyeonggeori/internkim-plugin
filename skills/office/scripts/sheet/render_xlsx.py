#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from sheet.formulas.cache import cache_formula_values
from render.office_preview import Preview, approximation_issues, blank_page_issues, draw_pages, write_preview
from core.office_outputs import preview_directory
from core.office_arguments import route_arguments
from core.office_result import Issue, OfficeFailure, Result, run_command
from fonts.preview import FontRegistry
from sheet.preview.colors import theme_palette
from sheet.workbook.access import missing_sheet_issue, open_workbook
from sheet.preview.pages import SheetPreviewer


BLANK_PAGE_SUGGESTION = "set the print area to the cells that hold content, or clear the far-off cell, empty formatted columns or page break that adds the page"


def workbook_values(source_path: Path):
    with tempfile.TemporaryDirectory(prefix="office-preview-") as directory:
        computed = Path(directory) / "computed.xlsx"
        shutil.copyfile(source_path, computed)
        cache_formula_values(str(computed))
        return open_workbook(str(computed), data_only=True)


def xlsx_preview(source_path: Path, sheet_name: str | None) -> tuple[Preview, list[dict], list[dict], list[Issue]]:
    workbook = open_workbook(str(source_path))
    values = workbook_values(source_path)
    names = [sheet_name] if sheet_name else [sheet.title for sheet in workbook.worksheets if sheet.sheet_state == "visible"]
    if sheet_name and sheet_name not in workbook.sheetnames:
        raise OfficeFailure(missing_sheet_issue(workbook.sheetnames, sheet_name, "--sheet"))
    fonts = FontRegistry()
    preview = Preview(title=source_path.stem)
    previewer = SheetPreviewer(workbook, values, source_path.name, theme_palette(workbook.loaded_theme), fonts, preview)
    planned = [page for name in names for page in previewer.sheet_pages(workbook[name], values[name])]
    preview.pages = [previewer.page_html(number, len(planned), *page) for number, page in enumerate(planned, start=1)]
    return preview, fonts.preview_fonts(), previewer.page_contents, previewer.print_issues


def main() -> Result:
    arguments = parse_arguments()
    source_path = Path(arguments.file).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(2, "no such file", str(source_path))
    output_directory = preview_directory(source_path, arguments.output_directory)
    preview, preview_fonts, page_contents, print_issues = xlsx_preview(source_path, arguments.sheet)
    preview_path = write_preview(preview, output_directory)
    drawn, drawing_issues = draw_pages(preview_path, preview_fonts, output_directory / f"{source_path.stem}.pdf")
    issues = [*print_issues, *approximation_issues(preview, source_path.name), *blank_page_issues(preview, BLANK_PAGE_SUGGESTION), *drawing_issues]
    details = {"preview": str(preview_path), "pageCount": len(preview.pages), "pageContents": page_contents, "previewFonts": preview_fonts, "approximations": preview.approximations, **drawn}
    return Result(summary=f"laid out {source_path.name} as {len(preview.pages)} printed pages in {preview_path}", output_path=str(preview_path), issues=tuple(issues), details=details)


def parse_arguments():
    return route_arguments("render", "xlsx")


if __name__ == "__main__":
    raise SystemExit(run_command(main))
