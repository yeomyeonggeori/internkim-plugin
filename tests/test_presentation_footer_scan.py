from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
sys.path.insert(0, str(SCRIPTS_PATH.parent))
sys.path.insert(0, str(SCRIPTS_PATH))

import footer_warnings  # noqa: E402


class FooterScanTest(unittest.TestCase):
    def test_malformed_markup_still_yields_the_last_child(self):
        slide_source = '<section><h2>제목</h2><![bogus]><div class="foot">출처 <b>굵게</section>'
        self.assertEqual(footer_warnings.last_direct_child(slide_source), ("div", {"class": "foot"}))

    def test_a_scanner_failure_is_not_reported_as_no_footer(self):
        with mock.patch.object(footer_warnings.DirectChildScanner, "handle_starttag", side_effect=RuntimeError("scanner bug")):
            with self.assertRaises(RuntimeError):
                footer_warnings.last_direct_child("<section><footer>출처</footer></section>")


if __name__ == "__main__":
    unittest.main()
