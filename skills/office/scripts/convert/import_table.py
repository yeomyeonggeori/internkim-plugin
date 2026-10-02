#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from convert.convert_definitions import CONVERSION_APPROXIMATED
from convert.convert_file import Conversion, draw_workbook_pdf
from convert.table_conversions import DELIMITERS, delimited_to_workbook
from core.office_arguments import route_arguments
from core.office_commands import command_text, normalized_extension
from core.office_result import Issue, Result, run_command


def main() -> Result:
    arguments = route_arguments("create", "csv")
    source_path = Path(arguments.source).expanduser()
    output_path = Path(arguments.output).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(2, "no such file", str(source_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    delimiter = DELIMITERS[normalized_extension(source_path.suffix)]
    conversion = Conversion(source_path, output_path, None)
    if output_path.suffix.lower() == ".pdf":
        conversion.issues.extend(printed_table_issues(conversion, delimiter))
    else:
        conversion.issues.extend(delimited_to_workbook(source_path, output_path, delimiter))
    return Result(summary=f"created {output_path.name} from {source_path.name}", output_path=str(output_path), issues=tuple(conversion.issues), details=conversion.details)


def printed_table_issues(conversion: Conversion, delimiter: str) -> list[Issue]:
    with tempfile.TemporaryDirectory(prefix="office-create-") as directory:
        workbook_path = Path(directory) / f"{conversion.input_path.stem}.xlsx"
        conversion.issues.extend(delimited_to_workbook(conversion.input_path, workbook_path, delimiter))
        print_issues = draw_workbook_pdf(conversion, workbook_path, None)
    workbook_command = command_text(["office", "create", str(conversion.output_path.with_suffix(".xlsx")), str(conversion.input_path)])
    return [CONVERSION_APPROXIMATED.issue(issue.message, conversion.input_path.name, f"run {workbook_command}, apply {json.dumps(list(issue.fix), ensure_ascii=False)} to it, then convert the workbook to .pdf") for issue in print_issues]


if __name__ == "__main__":
    raise SystemExit(run_command(main))
