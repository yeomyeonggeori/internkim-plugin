#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile

from pypdf import PdfReader, PdfWriter

from core.office_arguments import route_arguments
from core.office_inputs import require_unlocked_pdf
from core.office_operations import Change, OperationSet, run_apply
from core.office_result import Issue, Result, run_command
from core.page_sizes import Paper
from core.units import MILLIMETRES_PER_INCH, POINTS_PER_INCH
from doc.blocks.pdf import PageLayout, render_document_pdf
from pdf.create_pdf import section_blocks
from pdf.pdf_definitions import OPERATIONS


POINTS_TO_MILLIMETRES = MILLIMETRES_PER_INCH / POINTS_PER_INCH


@dataclass
class PdfEditing:
    path: str
    password: str | None
    reader: PdfReader
    sections: list[dict] = field(default_factory=list)


def main() -> Result:
    arguments = route_arguments("apply", "pdf")
    return run_apply(arguments, PDF_OPERATIONS, lambda path: load_editing(path, arguments.password), save_editing)


def load_editing(path: str, password: str | None) -> PdfEditing:
    expanded_path = str(Path(path).expanduser())
    require_unlocked_pdf(expanded_path, password)
    return PdfEditing(expanded_path, password, PdfReader(expanded_path, password=password))


def plan_append_section(editing: PdfEditing, operation: dict, location: str) -> Change:
    section = {name: value for name, value in operation.items() if name != "op"}

    def change() -> str:
        editing.sections.append(section)
        return f"appended a page holding {section.get('title') or 'an untitled section'}"
    return change


def save_editing(editing: PdfEditing, output_path: str) -> list[Issue]:
    layout = PageLayout(paper=last_page_paper(editing.reader), page_numbers=False)
    writer = PdfWriter()
    for page in editing.reader.pages:
        writer.add_page(page)
    issues: list[Issue] = []
    with tempfile.TemporaryDirectory() as directory:
        for index, section in enumerate(editing.sections):
            appended_path = Path(directory) / f"section-{index}.pdf"
            issues.extend(render_document_pdf(section_blocks(section), appended_path, Path.cwd(), section.get("title") or Path(editing.path).stem, layout=layout))
            for page in PdfReader(appended_path).pages:
                writer.add_page(page)
        if editing.password and editing.reader.is_encrypted:
            writer.encrypt(editing.password)
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
    return issues


def last_page_paper(reader: PdfReader) -> Paper:
    box = reader.pages[-1].mediabox
    return Paper("original", float(box.width) * POINTS_TO_MILLIMETRES, float(box.height) * POINTS_TO_MILLIMETRES, 0)


PDF_OPERATIONS = OperationSet(OPERATIONS, {"append_section": plan_append_section}, sequential=True)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
