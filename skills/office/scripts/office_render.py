from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Iterable
from xml.sax.saxutils import escape

from office_result import ERROR, IssueKind, OfficeFailure
from skill_runtime import HANGUL_FONT_PATHS


SOFFICE_NAMES = ("soffice", "libreoffice")
MACOS_SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
CONVERSION_TIMEOUT_SECONDS = 240
SUBSTITUTION_PATH = "/org.openoffice.Office.Common/Font/Substitution"

LIBREOFFICE_UNAVAILABLE = IssueKind("LIBREOFFICE_UNAVAILABLE", ERROR, "LibreOffice (soffice) is not installed, so this file cannot be laid out or converted here", "install LibreOffice, or deliver without this step and say the layout was not seen")
LIBREOFFICE_FAILED = IssueKind("LIBREOFFICE_FAILED", ERROR, "LibreOffice ran but wrote no output file", "check the file opens in its own application, then retry once")

LIBREOFFICE_ISSUE_KINDS = (LIBREOFFICE_UNAVAILABLE, LIBREOFFICE_FAILED)


class RenderFailure(Exception):
    pass


def soffice_command() -> str | None:
    found = next((shutil.which(name) for name in SOFFICE_NAMES if shutil.which(name)), None)
    if found:
        return found
    return str(MACOS_SOFFICE) if MACOS_SOFFICE.exists() else None


def korean_font_paths() -> list[Path]:
    return [Path(path) for path in HANGUL_FONT_PATHS if Path(path).exists()]


def prepare_profile(profile: Path, font_paths: Iterable[Path], substitutions: Iterable[tuple[str, str]] = ()) -> None:
    fonts = profile / "user" / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(sorted({str(path) for path in font_paths})):
        (fonts / f"{index:03d}-{Path(path).name}").symlink_to(path)
    (profile / "user" / "registrymodifications.xcu").write_text(replacement_table(sorted(set(substitutions))), encoding="utf-8")


def replacement_table(pairs: list[tuple[str, str]]) -> str:
    entries = "".join(
        f'<item oor:path="{SUBSTITUTION_PATH}/FontPairs"><node oor:name="_{index}" oor:op="replace">'
        f'<prop oor:name="Always" oor:op="fuse"><value>true</value></prop>'
        f'<prop oor:name="OnScreenOnly" oor:op="fuse"><value>false</value></prop>'
        f'<prop oor:name="ReplaceFont" oor:op="fuse"><value>{escape(requested)}</value></prop>'
        f'<prop oor:name="SubstituteFont" oor:op="fuse"><value>{escape(used)}</value></prop>'
        "</node></item>"
        for index, (requested, used) in enumerate(pairs)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<item oor:path="{SUBSTITUTION_PATH}"><prop oor:name="Replacement" oor:op="fuse"><value>true</value></prop></item>'
        f"{entries}</oor:items>"
    )


def conversion_command(command: str, profile: Path, target: str, output_directory: Path, input_path: Path) -> list[str]:
    return [command, f"-env:UserInstallation={profile.resolve().as_uri()}", "--headless", "--norestore", "--convert-to", target, "--outdir", str(output_directory), str(input_path)]


def convert_to(command: str, input_path: Path, target: str, output_directory: Path, font_paths: Iterable[Path] = (), substitutions: Iterable[tuple[str, str]] = ()) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    produced = output_directory / f"{input_path.stem}.{target.split(':', 1)[0]}"
    if produced.exists():
        produced.unlink()
    with tempfile.TemporaryDirectory(prefix="office-render-") as scratch:
        profile = Path(scratch) / "profile"
        prepare_profile(profile, font_paths, substitutions)
        try:
            completed = subprocess.run(conversion_command(command, profile, target, output_directory, input_path), capture_output=True, text=True, timeout=CONVERSION_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            raise RenderFailure(f"LibreOffice did not finish within {CONVERSION_TIMEOUT_SECONDS} seconds") from error
    if completed.returncode != 0 or not produced.exists():
        raise RenderFailure(f"LibreOffice exited {completed.returncode} without {produced.name}: {(completed.stderr or completed.stdout).strip()[:400]}")
    return produced


def convert_with_libreoffice(input_path: Path, target: str, output_directory: Path) -> Path:
    command = soffice_command()
    if command is None:
        raise OfficeFailure(LIBREOFFICE_UNAVAILABLE.issue(f"no soffice on PATH or at {MACOS_SOFFICE}", str(input_path)))
    try:
        return convert_to(command, input_path, target, output_directory, korean_font_paths())
    except RenderFailure as failure:
        raise OfficeFailure(LIBREOFFICE_FAILED.issue(str(failure), str(input_path))) from failure
