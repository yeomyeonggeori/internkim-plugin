from __future__ import annotations

from pathlib import Path
import tempfile

from core.office_commands import find_conversion, normalized_extension
from core.office_inputs import read_text_input
from core.office_result import OfficeFailure
from delivery.file_text import office
from host.task_context import Attachment


PLAIN_TEXT_EXTENSIONS = ("txt", "md", "csv", "tsv", "json")
TEXT_TARGETS = ("md", "csv")


def attachment_text(attachment: Attachment) -> str:
    if attachment.text.strip():
        return attachment.text
    path = Path(attachment.path)
    if not attachment.path or not path.is_file():
        return ""
    extension = normalized_extension(path.suffix)
    if extension in PLAIN_TEXT_EXTENSIONS:
        return plain_text(path)
    target = next((target for target in TEXT_TARGETS if find_conversion(extension, target)), None)
    return converted_text(path, target) if target else ""


def plain_text(path: Path) -> str:
    try:
        return read_text_input(str(path))
    except OfficeFailure:
        return ""


def converted_text(path: Path, target: str) -> str:
    with tempfile.TemporaryDirectory() as directory:
        result = office("convert", str(path), str(Path(directory) / f"{path.stem}.{target}"))
        if result.get("status") == "error":
            return ""
        files = [Path(file) for file in (result.get("details") or {}).get("files") or ()]
        return "\n\n".join(labelled_text(file, len(files) > 1) for file in files if file.is_file())


def labelled_text(file: Path, is_one_of_several: bool) -> str:
    text = file.read_text(encoding="utf-8-sig").strip()
    return f"{file.stem}:\n{text}" if is_one_of_several else text
