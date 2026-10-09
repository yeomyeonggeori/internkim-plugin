from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

from core.office_result import Result, run_command
from core.source_snapshot import DELIVERABLE_EXTENSIONS, read_source
from delivery.claim_check import BLANKED, REMAKE_FAILED, REWRITTEN, ClaimCheck, check_file, check_text, run_remake, snapshot_claims
from delivery.delivered_metadata import metadata_path_of, write_metadata
from delivery.finish import LEFTOVERS_KEY, is_as_made
from host import script_host
from host.task_context import TaskContext, load_task_context

CONVERT_COMMAND = "office convert"
CONVERTIBLE_SOURCES = (".docx",)


def main() -> Result:
    file_path = Path(sys.argv[1]).expanduser()
    metadata_path_of(file_path).unlink(missing_ok=True)
    context = load_task_context()
    if file_path.suffix.lower() not in DELIVERABLE_EXTENSIONS or context is None or not script_host.is_present():
        return Result(summary=f"{file_path.name}: nothing to check")
    snapshot = read_source(file_path)
    leftovers = snapshot.get(LEFTOVERS_KEY) or [] if is_as_made(file_path, snapshot) else []
    check = checked(context, file_path, snapshot)
    after = read_source(file_path)
    write_metadata(file_path, after if is_as_made(file_path, after) else {}, [check], leftovers)
    return Result(summary=f"{file_path.name}: {check.outcome}", output_path=str(file_path), details={"claimCheck": [check.to_json()]})


def checked(context: TaskContext, file_path: Path, snapshot: dict) -> ClaimCheck:
    source = converted_from(file_path, snapshot)
    if source is not None:
        return checked_through_source(context, file_path, snapshot, source)
    claims = snapshot_claims(snapshot)
    if claims and is_as_made(file_path, snapshot):
        return check_file(context, file_path, claims)
    return check_text(context, file_path, snapshot)


def converted_from(file_path: Path, snapshot: dict) -> Path | None:
    arguments = [str(argument) for argument in snapshot.get("arguments") or ()]
    if snapshot.get("command") != CONVERT_COMMAND or len(arguments) < 2:
        return None
    source = Path(snapshot.get("directory") or file_path.parent, arguments[0]).expanduser()
    if source.suffix.lower() not in CONVERTIBLE_SOURCES or not source.is_file() or source.stat().st_mtime > file_path.stat().st_mtime:
        return None
    return source


def checked_through_source(context: TaskContext, file_path: Path, snapshot: dict, source: Path) -> ClaimCheck:
    check = checked(context, source, read_source(source))
    if check.outcome in (BLANKED, REWRITTEN):
        directory = Path(snapshot.get("directory") or file_path.parent)
        failure = run_remake(["convert", str(source.resolve()), str(file_path.resolve()), *[str(argument) for argument in snapshot["arguments"][2:]]], directory)
        if failure:
            check.outcome, check.detail = REMAKE_FAILED, failure
    return replace(check, file=file_path.name)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
