from __future__ import annotations

from pathlib import Path
import sys

from core.office_result import Result, run_command
from core.source_snapshot import DELIVERABLE_EXTENSIONS, read_source
from delivery.claim_check import ClaimCheck, check_file, check_text, snapshot_claims
from delivery.delivered_metadata import write_metadata
from delivery.finish import LEFTOVERS_KEY, is_as_made
from host import script_host
from host.task_context import TaskContext, load_task_context


def main() -> Result:
    file_path = Path(sys.argv[1]).expanduser()
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
    claims = snapshot_claims(snapshot)
    if claims and is_as_made(file_path, snapshot):
        return check_file(context, file_path, claims)
    return check_text(context, file_path)


if __name__ == "__main__":
    raise SystemExit(run_command(main))
