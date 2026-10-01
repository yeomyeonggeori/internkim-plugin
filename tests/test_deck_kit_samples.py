import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


TESTS_PATH = Path(__file__).resolve().parent
SCRIPTS_PATH = TESTS_PATH.parent / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
SAMPLE_DECKS_PATH = TESTS_PATH / "fixtures" / "deck-kit"
sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(SCRIPTS_PATH / "deck"))
sys.path.insert(0, str(TESTS_PATH))

from check_deck import CheckRequest, check_deck  # noqa: E402
from png_codec import write_png  # noqa: E402
from test_deck_geometry import can_render_in_a_browser  # noqa: E402


LAYOUT_DEFECT_CODES = {"CONTENT_OVERFLOW", "TEXT_OVERLAP", "OUT_OF_FRAME"}
PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page(?!s)")
GENERATED_PHOTO_SIZE = (960, 640)


def sample_deck_paths() -> list[Path]:
    return sorted(path for path in SAMPLE_DECKS_PATH.iterdir() if (path / "slides.html").exists())


def slide_count(deck_path: Path) -> int:
    return (deck_path / "slides.html").read_text(encoding="utf-8").count("<section")


def referenced_images(deck_path: Path) -> list[str]:
    return re.findall(r'src="(images/[^"]+\.png)"', (deck_path / "slides.html").read_text(encoding="utf-8"))


def write_gradient_photo(path: Path) -> None:
    width, height = GENERATED_PHOTO_SIZE
    rows = [[(40 + 120 * column // width, 70 + 90 * row // height, 110, 255) for column in range(width)] for row in range(height)]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_png(path, width, height, rows)


def copy_sample_deck(sample_path: Path, directory: Path) -> Path:
    deck_path = directory / sample_path.name
    shutil.copytree(sample_path, deck_path)
    for image in referenced_images(deck_path):
        write_gradient_photo(deck_path / image)
    return deck_path


class SampleDeckCheckTest(unittest.TestCase):
    def test_every_sample_deck_passes_the_check_at_its_slide_count(self):
        for sample_path in sample_deck_paths():
            with self.subTest(sample_path.name), tempfile.TemporaryDirectory() as directory:
                deck_path = copy_sample_deck(sample_path, Path(directory))
                result = check_deck(CheckRequest(deck_path / "slides.html", slide_count(deck_path), ()))
                self.assertEqual([issue.kind.code for issue in result.issues if issue.kind.severity == "error"], [])


class SampleDeckBuildTest(unittest.TestCase):
    @unittest.skipUnless(can_render_in_a_browser(), "needs bun and a browser that speaks the Chrome DevTools Protocol")
    def test_every_sample_deck_builds_an_acceptable_pdf_without_layout_defects(self):
        for sample_path in sample_deck_paths():
            with self.subTest(sample_path.name), tempfile.TemporaryDirectory() as directory:
                deck_path = copy_sample_deck(sample_path, Path(directory))
                count = slide_count(deck_path)
                completed = subprocess.run(
                    [sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "pdf", "--slide-count", str(count)],
                    capture_output=True,
                    text=True,
                    cwd=deck_path,
                )
                envelope = json.loads(completed.stdout)
                if envelope["details"]["review"]["renderSource"] != "browser":
                    self.skipTest("the browser did not render the deck on this host")
                pdf_bytes = Path(envelope["outputPath"]).read_bytes()
                self.assertEqual({issue["code"] for issue in envelope["issues"]} & LAYOUT_DEFECT_CODES, set())
                self.assertTrue(envelope["details"]["acceptance"]["acceptable"], envelope["summary"])
                self.assertEqual(len(PDF_PAGE_PATTERN.findall(pdf_bytes)), count)


if __name__ == "__main__":
    unittest.main()
