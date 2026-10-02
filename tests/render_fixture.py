import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from render.renderer import RendererUnavailable, javascript_runtime  # noqa: E402
from skill_runtime import cache_home_path  # noqa: E402


PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page(?!s)")


def can_render() -> bool:
    try:
        javascript_runtime()
    except RendererUnavailable:
        return False
    return True


def bare_environment(home) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        "XDG_CACHE_HOME": str(cache_home_path(os.environ)),
    }


def run_office_without_renderer(arguments: list[str], directory: Path) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as home:
        return subprocess.run([sys.executable, str(SCRIPTS_PATH / "office"), *arguments], capture_output=True, text=True, cwd=directory, env=bare_environment(home))


def png_size(path) -> tuple[int, int]:
    header = Path(path).read_bytes()[:24]
    return struct.unpack(">II", header[16:24])


def pdf_page_count(path) -> int:
    return len(PDF_PAGE_PATTERN.findall(Path(path).read_bytes()))


def assert_pages_drawn(test, details: dict, directory: Path, page_count: int, page_size: tuple[int, int]) -> None:
    test.assertTrue(details["seen"])
    pages = [directory / path for path in details["pages"]]
    test.assertEqual(len(pages), page_count)
    test.assertEqual({png_size(page) for page in pages}, {page_size})
    test.assertEqual(len(details["contactSheets"]), -(-page_count // 4))
    test.assertTrue(all((directory / sheet).is_file() for sheet in details["contactSheets"]))
