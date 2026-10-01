from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Callable, Sequence

from office_inputs import office_file
from office_result import ERROR, Issue, IssueKind, OfficeArgumentParser, Result, read_json_file
from office_schema import ListOf, Variant, require_valid


TARGET_NOT_FOUND = IssueKind("TARGET_NOT_FOUND", ERROR, "an operation names a block, cell, sheet, or slide the file does not have", "read the file again and use an index or name it reports")
OPERATION_NOT_APPLICABLE = IssueKind("OPERATION_NOT_APPLICABLE", ERROR, "an operation cannot apply to the element it names", "pick an element of the kind the operation edits")

OPERATION_ISSUE_KINDS = (TARGET_NOT_FOUND, OPERATION_NOT_APPLICABLE)

Change = Callable[[], str]


def chart_indexes_suggestion(owner: str, chart_count: int, add_operation: str) -> str:
    if chart_count == 0:
        return f"{owner} holds no chart; add one with {add_operation}, or name the place that holds it"
    if chart_count == 1:
        return f"use chart 0, the only chart of {owner}"
    return f"use a chart from 0 to {chart_count - 1}"
Planner = Callable[[object, dict, str], Change]


@dataclass(frozen=True)
class OperationSet:
    shape: Variant
    planners: dict[str, Planner]
    sequential: bool = False

    @property
    def batch(self) -> ListOf:
        return ListOf(self.shape, non_empty=True)


def apply_batch(operation_set: OperationSet, editing: object, operations: list[dict]) -> list[dict]:
    if operation_set.sequential:
        return apply_in_order(operation_set, editing, operations)
    changes = [
        operation_set.planners[operation["op"]](editing, operation, f"ops[{index}]")
        for index, operation in enumerate(operations)
    ]
    return [
        {"index": index, "op": operation["op"], "change": change()}
        for index, (operation, change) in enumerate(zip(operations, changes))
    ]


def apply_in_order(operation_set: OperationSet, editing: object, operations: list[dict]) -> list[dict]:
    results = []
    for index, operation in enumerate(operations):
        change = operation_set.planners[operation["op"]](editing, operation, f"ops[{index}]")
        results.append({"index": index, "op": operation["op"], "change": change()})
    return results


def read_batch(operation_set: OperationSet, operations_path: str) -> list[dict]:
    operations = read_json_file(operations_path)
    require_valid(operation_set.batch, operations, "ops")
    return operations


def save_atomically(save: Callable[[str], Sequence[Issue] | None], output_path: str) -> Sequence[Issue]:
    directory = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(directory, exist_ok=True)
    suffix = Path(output_path).suffix
    descriptor, temporary_path = tempfile.mkstemp(prefix=".office-", suffix=suffix, dir=directory)
    os.close(descriptor)
    try:
        issues = save(temporary_path) or ()
        os.replace(temporary_path, output_path)
        return issues
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def apply_parser(description: str, input_kind: str) -> OfficeArgumentParser:
    parser = OfficeArgumentParser(description=description)
    parser.add_argument("path", type=office_file(input_kind), help="the file to edit")
    parser.add_argument("ops", help="JSON file with a list of operations")
    parser.add_argument("--output", help="write the result here instead of editing the file in place")
    parser.add_argument("--dry-run", action="store_true", help="check and plan every operation, report the changes, and write nothing")
    return parser


def run_apply(arguments, operation_set: OperationSet, load: Callable[[str], object], save: Callable[[object, str], Sequence[Issue] | None]) -> Result:
    operations = read_batch(operation_set, arguments.ops)
    document = load(arguments.path)
    changes = apply_batch(operation_set, document, operations)
    output_path = os.path.expanduser(arguments.output or arguments.path)
    if arguments.dry_run:
        return Result(summary=f"dry run: {len(changes)} operations would apply to {arguments.path}", details={"dryRun": True, "changes": changes})
    issues = save_atomically(lambda temporary_path: save(document, temporary_path), output_path)
    return Result(summary=f"applied {len(changes)} operations to {output_path}", output_path=output_path, issues=tuple(issues), details={"dryRun": False, "changes": changes})

