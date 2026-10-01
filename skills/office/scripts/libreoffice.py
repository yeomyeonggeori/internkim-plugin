from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from office_result import ERROR, IssueKind, OfficeFailure
from skill_runtime import HANGUL_FONT_PATHS


EXECUTABLE_NAMES = ("soffice", "libreoffice")
APPLICATION_PATHS = ("/Applications/LibreOffice.app/Contents/MacOS/soffice",)
CONVERSION_TIMEOUT_SECONDS = 180

LIBREOFFICE_UNAVAILABLE = IssueKind("LIBREOFFICE_UNAVAILABLE", ERROR, "LibreOffice (soffice) is not installed, so this file cannot be laid out or converted here", "install LibreOffice, or deliver without this step and say the layout was not seen")
LIBREOFFICE_FAILED = IssueKind("LIBREOFFICE_FAILED", ERROR, "LibreOffice ran but wrote no output file", "check the file opens in its own application, then retry once")

LIBREOFFICE_ISSUE_KINDS = (LIBREOFFICE_UNAVAILABLE, LIBREOFFICE_FAILED)


def find_soffice() -> str | None:
    for name in EXECUTABLE_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return next((path for path in APPLICATION_PATHS if os.access(path, os.X_OK)), None)


def conversion_command(soffice: str, profile_directory: Path, target: str, output_directory: Path, input_path: Path) -> list[str]:
    return [
        soffice,
        f"-env:UserInstallation={profile_directory.resolve().as_uri()}",
        "--headless",
        "--norestore",
        "--convert-to",
        target,
        "--outdir",
        str(output_directory),
        str(input_path),
    ]


def prepare_profile(profile_directory: Path) -> None:
    fonts_directory = profile_directory / "user" / "fonts"
    fonts_directory.mkdir(parents=True, exist_ok=True)
    for font_path in map(Path, HANGUL_FONT_PATHS):
        if font_path.exists():
            (fonts_directory / font_path.name).symlink_to(font_path)


def convert_with_libreoffice(input_path: Path, target: str, output_directory: Path) -> Path:
    soffice = find_soffice()
    if soffice is None:
        raise OfficeFailure(LIBREOFFICE_UNAVAILABLE.issue(f"no soffice on PATH or in {APPLICATION_PATHS[0]}", str(input_path)))
    output_directory.mkdir(parents=True, exist_ok=True)
    expected = output_directory / f"{input_path.stem}.{target.split(':', 1)[0]}"
    if expected.exists():
        expected.unlink()
    with tempfile.TemporaryDirectory(prefix="office-libreoffice-") as profile:
        prepare_profile(Path(profile))
        completed = run_conversion(conversion_command(soffice, Path(profile), target, output_directory, input_path))
    if not expected.exists():
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()[-1:] if completed else ["timed out"]
        raise OfficeFailure(LIBREOFFICE_FAILED.issue(f"LibreOffice wrote no {expected.name}: {' '.join(detail) or 'no message'}", str(input_path)))
    return expected


def run_conversion(command: list[str]):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=CONVERSION_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return None
