from __future__ import annotations

from dataclasses import dataclass

from excel_functions import EXCEL_FUNCTIONS, PARAMETER_FUNCTIONS, parameter_names
from formula_references import formula_references, referenced_sheet_names
from formula_tree import Call, calls_in, parse_formula
from office_result import Issue
from office_schema import closest_name
from sheet_definitions import MISSING_SHEET_REFERENCE, UNKNOWN_FUNCTION
from workbook_access import formula_text


USER_FUNCTION_PREFIXES = ("_XLUDF.", "_XLL.")


@dataclass(frozen=True)
class NameProblem:
    sheet: str
    coordinate: str
    formula: str
    name: str

    @property
    def location(self) -> str:
        return f"{self.sheet}!{self.coordinate}"


def sheet_is_missing(workbook, name: str) -> bool:
    return name.casefold() not in {title.casefold() for title in workbook.sheetnames}


def missing_sheet_problems(workbook) -> list[NameProblem]:
    problems = []
    for sheet, coordinate, formula in formula_cells(workbook):
        missing = [name for reference in formula_references(formula) for name in referenced_sheet_names(reference) if sheet_is_missing(workbook, name)]
        if missing:
            problems.append(NameProblem(sheet, coordinate, formula, missing[0]))
    return problems


def unknown_function_problems(workbook) -> list[NameProblem]:
    if getattr(workbook, "vba_archive", None) is not None:
        return []
    defined = defined_names(workbook)
    problems = []
    for sheet, coordinate, formula in formula_cells(workbook):
        nodes = parse_formula(formula) or []
        calls = list(calls_in(nodes))
        known = defined | {name for call in calls if call.function in PARAMETER_FUNCTIONS for name in parameter_names(call)}
        unknown = [call.name for call in calls if is_unknown_function(call, known)]
        if unknown:
            problems.append(NameProblem(sheet, coordinate, formula, unknown[0]))
    return problems


def formula_cells(workbook):
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                formula = formula_text(cell)
                if formula:
                    yield worksheet.title, cell.coordinate, formula


def defined_names(workbook) -> set[str]:
    names = {name.casefold() for name in workbook.defined_names}
    return names | {name.casefold() for worksheet in workbook.worksheets for name in worksheet.defined_names}


def is_unknown_function(call: Call, known_names: set[str]) -> bool:
    if call.function in EXCEL_FUNCTIONS or call.name.casefold() in known_names:
        return False
    return not call.name.upper().startswith(USER_FUNCTION_PREFIXES)


def missing_sheet_issue(problem: NameProblem, sheet_names: list[str]) -> Issue:
    nearest = closest_name(problem.name, sheet_names)
    guess = f" (did you mean {nearest!r}?)" if nearest else f"; it has {', '.join(sheet_names)}"
    suggestion = f"write the formula with {nearest!r}, or add the sheet first" if nearest else None
    return MISSING_SHEET_REFERENCE.issue(f"{problem.location} reads sheet {problem.name!r}, which the workbook does not have{guess}", problem.location, suggestion)


def unknown_function_issue(problem: NameProblem) -> Issue:
    nearest = closest_name(problem.name.upper(), EXCEL_FUNCTIONS)
    guess = f" (did you mean {nearest}?)" if nearest else ""
    suggestion = f"write {nearest} in place of {problem.name}" if nearest else None
    return UNKNOWN_FUNCTION.issue(f"{problem.location} calls {problem.name}, which is not an Excel function{guess}: {problem.formula}", problem.location, suggestion)


def name_issues(workbook, problems_from_source: tuple[set[str], set[str]] | None = None) -> list[Issue]:
    known_sheets, known_functions = problems_from_source or (set(), set())
    missing = [problem for problem in missing_sheet_problems(workbook) if problem.name.casefold() not in known_sheets]
    unknown = [problem for problem in unknown_function_problems(workbook) if problem.name.casefold() not in known_functions]
    return [missing_sheet_issue(problem, workbook.sheetnames) for problem in missing] + [unknown_function_issue(problem) for problem in unknown]


def names_already_broken(workbook) -> tuple[set[str], set[str]]:
    return (
        {problem.name.casefold() for problem in missing_sheet_problems(workbook)},
        {problem.name.casefold() for problem in unknown_function_problems(workbook)},
    )
