from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from core.office_result import WRONG_OUTPUT_FORMAT, OfficeFailure


def output_file(*extensions: str) -> Callable[[str], str]:
    def checked_path(path: str) -> str:
        require_output_extension(path, extensions)
        return path

    return checked_path


def require_output_extension(path: str, extensions: tuple[str, ...]) -> str:
    suffix = Path(path).suffix
    if suffix.lower() in extensions:
        return suffix.lower()
    ending = f"ends in {suffix}" if suffix else "has no extension"
    raise OfficeFailure(WRONG_OUTPUT_FORMAT.issue(
        f"{path} {ending}, and {os.environ.get('OFFICE_COMMAND') or 'this command'} writes {' or '.join(extensions)}",
        path,
        suggestion="name the output " + " or ".join(str(Path(path).with_suffix(extension)) for extension in extensions),
    ))


def same_kind_output(output_path: str, source_path: str) -> str:
    require_output_extension(output_path, (Path(source_path).suffix.lower(),))
    return output_path
