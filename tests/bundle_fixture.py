from pathlib import Path
import subprocess


def bundled_files(directory: Path, pattern: str = "*") -> list[Path]:
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", pattern], cwd=directory, capture_output=True, text=True, check=True).stdout
    return sorted(path for path in (directory / name for name in listed.split("\0") if name) if path.is_file())
