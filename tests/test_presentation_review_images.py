from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
sys.path.insert(0, str(SCRIPTS_PATH))

from png_codec import write_png  # noqa: E402
from render_review import build_review_report  # noqa: E402


def write_blank_png(path: Path) -> None:
    write_png(path, 32, 18, [[(255, 255, 255, 255)] * 32 for _ in range(18)])


class ReviewImageSelectionTest(unittest.TestCase):
    def test_review_reads_only_numbered_slide_renders(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            deck_path = Path(temporary_directory)
            source_path = deck_path / "slides.html"
            source_path.write_text("<section><h2>하나뿐인 슬라이드입니다</h2></section>", encoding="utf-8")
            review_path = deck_path / "review"
            review_path.mkdir()
            for file_name in ("deck.001.png", "deck-extra.png", "deck.1.png", "deck.final.png"):
                write_blank_png(review_path / file_name)
            report = build_review_report(source_path, "deck", review_path)
        self.assertEqual(report["renderedSlideCount"], 1)
        self.assertEqual(report["slideCount"], 1)
        self.assertEqual([slide["filename"] for slide in report["slides"]], ["deck.001.png"])


if __name__ == "__main__":
    unittest.main()
