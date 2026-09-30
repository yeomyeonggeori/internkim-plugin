from __future__ import annotations

import glob
import os

from office_result import NO_FILE_FOUND, OfficeFailure


def resolve_document_path(given_path: str | None, extension: str) -> str:
    if given_path:
        return os.path.expanduser(given_path)
    candidates = sorted(glob.glob(os.path.expanduser(f"~/documents/*.{extension}")), key=os.path.getmtime, reverse=True)
    if not candidates:
        raise OfficeFailure(NO_FILE_FOUND.issue(f"no .{extension} found in ~/documents; pass the file path explicitly"))
    return candidates[0]
