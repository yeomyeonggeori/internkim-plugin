from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import os
from pathlib import Path
import tempfile
from typing import Callable, Sequence

from core.office_commands import BATCH_MODES
from core.office_outputs import same_kind_output
from core.office_result import ERROR, FILL_INS, VALUE_FILL_IN, WARNING, Issue, IssueKind, OfficeFailure, Result, read_json_file
from core.office_schema import ListOf, Variant, join_location, require_valid


TARGET_NOT_FOUND = IssueKind("TARGET_NOT_FOUND", ERROR, "an operation names a block, cell, sheet, or slide the file does not have", "read the file again and use an index or name it reports")
OPERATION_NOT_APPLICABLE = IssueKind("OPERATION_NOT_APPLICABLE", ERROR, "an operation cannot apply to the element it names", "pick an element of the kind the operation edits")
FILL_IN_LEFT = IssueKind("FILL_IN_LEFT", ERROR, f"an operation copied from a fix still holds a value in angle brackets, such as {VALUE_FILL_IN}, that was left for you to fill in, so nothing was written", "write the real value from the source in its place")

OPERATION_REFUSED = IssueKind("OPERATION_REFUSED", WARNING, "a --mode best-effort or stop-on-error batch left out an operation that does not apply and wrote the others", "correct the operation as the message says and apply it in a batch of its own")

OPERATION_ISSUE_KINDS = (TARGET_NOT_FOUND, OPERATION_NOT_APPLICABLE, FILL_IN_LEFT, OPERATION_REFUSED)

Change = Callable[[], str]


def chart_indexes_suggestion(owner: str, chart_count: int, add_operation: str) -> str:
    if chart_count == 0:
        return f"{owner} holds no chart; add one with {add_operation}, or name the place that holds it"
    if chart_count == 1:
        return f"use chart 0, the only chart of {owner}"
    return f"use a chart from 0 to {chart_count - 1}"
Planner = Callable[[object, dict, str], Change]
Preparer = Callable[[object, dict, int], dict]
ALL_MODE, BEST_EFFORT_MODE, STOP_ON_ERROR_MODE = BATCH_MODES


@dataclass(frozen=True)
class OperationSet:
    shape: Variant
    planners: dict[str, Planner]
    sequential: bool = False
    prepare: Preparer | None = None

    @property
    def batch(self) -> ListOf:
        return ListOf(self.shape, non_empty=True)


@dataclass(frozen=True)
class Refusal:
    index: int
    operation: object
    issues: tuple[Issue, ...]

    def to_json(self) -> dict:
        name = self.operation.get("op") if isinstance(self.operation, dict) else None
        return {"index": self.index, "op": name, "codes": [issue.kind.code for issue in self.issues]}


@dataclass
class BatchOutcome:
    mode: str
    total: int
    changes: list[dict] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    skipped: list[int] = field(default_factory=list)

    @property
    def stopped(self) -> bool:
        return self.mode == STOP_ON_ERROR_MODE and bool(self.refusals)

    def counted(self) -> str:
        if len(self.changes) == self.total:
            return f"{self.total} operations"
        return f"{len(self.changes)} of {self.total} operations"

    def issues(self) -> tuple[Issue, ...]:
        return tuple(refused_issue(refusal, issue, self.skipped) for refusal in self.refusals for issue in refusal.issues)

    def details(self) -> dict:
        if self.mode == ALL_MODE:
            return {"changes": self.changes}
        return {"mode": self.mode, "changes": self.changes, "refused": [refusal.to_json() for refusal in self.refusals], "skipped": self.skipped}


def refused_issue(refusal: Refusal, issue: Issue, skipped: list[int]) -> Issue:
    after = f"; the {len(skipped)} operations after it were not tried" if skipped else ""
    message = f"ops[{refusal.index}] was left out ({issue.kind.code}): {issue.message}{after}"
    return OPERATION_REFUSED.issue(message, issue.location, issue.suggestion, issue.fix)


def apply_batch(operation_set: OperationSet, editing: object, operations: list[dict]) -> list[dict]:
    return apply_operations(operation_set, editing, operations, ALL_MODE).changes


def apply_operations(operation_set: OperationSet, editing: object, operations: list, mode: str) -> BatchOutcome:
    outcome = BatchOutcome(mode, len(operations))
    if operation_set.sequential:
        apply_in_order(operation_set, editing, operations, outcome)
    else:
        apply_after_planning(operation_set, editing, operations, outcome)
    if outcome.refusals and not outcome.changes:
        raise OfficeFailure(*(issue for refusal in outcome.refusals for issue in refusal.issues))
    return outcome


def apply_in_order(operation_set: OperationSet, editing: object, operations: list, outcome: BatchOutcome) -> None:
    for index, operation in enumerate(operations):
        if outcome.stopped:
            outcome.skipped.append(index)
            continue
        change = planned_change(operation_set, editing, operation, index, outcome)
        if change is not None:
            outcome.changes.append({"index": index, "op": operation["op"], "change": change()})


def apply_after_planning(operation_set: OperationSet, editing: object, operations: list, outcome: BatchOutcome) -> None:
    planned = []
    for index, operation in enumerate(operations):
        if outcome.stopped:
            outcome.skipped.append(index)
            continue
        change = planned_change(operation_set, editing, operation, index, outcome)
        if change is not None:
            planned.append((index, operation["op"], change))
    outcome.changes.extend({"index": index, "op": name, "change": change()} for index, name, change in planned)


def planned_change(operation_set: OperationSet, editing: object, operation: object, index: int, outcome: BatchOutcome) -> Change | None:
    if outcome.mode == ALL_MODE:
        return plan_operation(operation_set, editing, operation, index)
    try:
        require_valid(operation_set.shape, operation, f"ops[{index}]")
        return plan_operation(operation_set, editing, operation, index)
    except OfficeFailure as failure:
        outcome.refusals.append(Refusal(index, operation, failure.issues))
        return None


def plan_operation(operation_set: OperationSet, editing: object, operation: dict, index: int) -> Change:
    prepared = operation_set.prepare(editing, operation, index) if operation_set.prepare is not None else operation
    return operation_set.planners[prepared["op"]](editing, prepared, f"ops[{index}]")


def read_batch(operation_set: OperationSet, operations_path: str, mode: str = ALL_MODE) -> list:
    operations = read_json_file(operations_path)
    if mode == ALL_MODE or not isinstance(operations, list) or not operations:
        require_valid(operation_set.batch, operations, "ops")
    issues = fill_in_issues(operations, "ops")
    if issues:
        raise OfficeFailure(*issues)
    return operations


def fill_in_issues(value: object, location: str) -> list[Issue]:
    if isinstance(value, dict):
        return [issue for name, item in value.items() for issue in fill_in_issues(item, join_location(location, name))]
    if isinstance(value, list):
        return [issue for index, item in enumerate(value) for issue in fill_in_issues(item, f"{location}[{index}]")]
    left = [fill_in for fill_in in FILL_INS if isinstance(value, str) and fill_in in value]
    return [FILL_IN_LEFT.issue(f"{location} still holds {', '.join(left)}, which a fix leaves for you to fill in", location)] if left else []


def save_atomically(save: Callable[[str], Sequence[Issue] | None], output_path: str) -> Sequence[Issue]:
    temporary_path = temporary_path_beside(output_path)
    try:
        issues = save(temporary_path) or ()
        with failures_named(output_path):
            os.replace(temporary_path, output_path)
        return issues
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def temporary_path_beside(output_path: str) -> str:
    directory = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(directory, exist_ok=True)
    with failures_named(output_path):
        descriptor, temporary_path = tempfile.mkstemp(prefix=".office-", suffix=Path(output_path).suffix, dir=directory)
    os.close(descriptor)
    return temporary_path


@contextmanager
def failures_named(path: str):
    try:
        yield
    except OSError as error:
        raise OSError(error.errno, error.strerror, path) from error


def apply_output_path(arguments) -> str:
    return os.path.expanduser(same_kind_output(arguments.output, arguments.file) if arguments.output else arguments.file)


@dataclass(frozen=True)
class Review:
    issues: tuple[Issue, ...] = ()
    details: dict = field(default_factory=dict)


def run_apply(arguments, operation_set: OperationSet, load: Callable[[str], object], save: Callable[[object, str], Sequence[Issue] | None], review: Callable[[object], Review] | None = None) -> Result:
    document = load(arguments.file)
    operations = read_batch(operation_set, arguments.operations, arguments.mode)
    outcome = apply_operations(operation_set, document, operations, arguments.mode)
    reviewed = review(document) if review is not None else Review()
    issues = outcome.issues() + reviewed.issues
    details = {"dryRun": arguments.dry_run, **outcome.details(), **reviewed.details}
    if arguments.dry_run:
        return Result(summary=f"dry run: {outcome.counted()} would apply to {arguments.file}", issues=issues, details=details)
    output_path = apply_output_path(arguments)
    saved_issues = save_atomically(lambda temporary_path: save(document, temporary_path), output_path)
    return Result(summary=f"applied {outcome.counted()} to {output_path}", output_path=output_path, issues=issues + tuple(saved_issues), details=details)
