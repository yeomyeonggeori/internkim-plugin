import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


TESTS_PATH = Path(__file__).resolve().parent
SCRIPTS_PATH = TESTS_PATH.parent / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))
sys.path.insert(0, str(TESTS_PATH))

from deck.html_export import deck_html_text  # noqa: E402
from png_fixture import write_png  # noqa: E402


AUTHORED_DECK = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>복원 시험</title>
<style>@font-face { font-family: "Brand"; src: url("fonts/brand.woff2") format("woff2"); } h2 { font-family: "Paperlogy", sans-serif; }</style></head>
<body data-theme="editorial">
<section data-layout="image"><img src="images/photo.png" alt="사진"><h2>진열대가 비기 전에 알려 드립니다</h2><ul><li>포스 데이터를 가져옵니다</li></ul></section>
<section data-layout="statement"><h2>재고 확인이 하루 47분 줄어듭니다</h2></section>
</body>
</html>
"""


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text)


class RestoreTest(unittest.TestCase):
    def test_restore_gives_back_the_small_authored_source(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            source_path = deck_path / "slides.html"
            source_path.write_text(AUTHORED_DECK, encoding="utf-8")
            (deck_path / "images").mkdir()
            write_png(deck_path / "images" / "photo.png", 64, 48, [[(30, 60, 90, 255)] * 64 for _ in range(48)])
            (deck_path / "fonts").mkdir()
            (deck_path / "fonts" / "brand.woff2").write_bytes(b"wOF2" + bytes(2048))
            delivered_path = deck_path / "build" / "deck.html"
            delivered_path.parent.mkdir()
            delivered_path.write_text(deck_html_text(source_path), encoding="utf-8")
            restored_path = deck_path / "restored.html"
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "convert", str(delivered_path), str(restored_path)], capture_output=True, text=True)
            self.assertEqual(json.loads(completed.stdout)["status"], "ok", completed.stdout)
            restored = restored_path.read_text(encoding="utf-8")
        self.assertEqual(squeezed(restored), squeezed(AUTHORED_DECK))
        self.assertLess(len(restored.encode()), 2 * len(AUTHORED_DECK.encode()))


if __name__ == "__main__":
    unittest.main()
