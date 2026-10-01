from pathlib import Path
import re
import struct
import sys


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from render.renderer import RendererUnavailable, javascript_runtime  # noqa: E402


PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page(?!s)")


def can_render() -> bool:
    try:
        javascript_runtime()
    except RendererUnavailable:
        return False
    return True


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
