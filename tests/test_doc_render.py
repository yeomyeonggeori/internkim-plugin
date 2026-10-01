from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from doc_fixture import SCRIPTS_PATH, ContractFixture, run_office

sys.path.insert(0, str(SCRIPTS_PATH))

import libreoffice  # noqa: E402
from office_result import OfficeFailure  # noqa: E402


class LibreOfficeCommandTest(unittest.TestCase):
    def test_conversion_runs_headless_with_its_own_profile(self):
        profile = Path(tempfile.gettempdir()).resolve() / "profile"
        command = libreoffice.conversion_command("soffice", profile, "pdf", Path("out"), Path("보고서.docx"))
        self.assertEqual(command, ["soffice", f"-env:UserInstallation={profile.as_uri()}", "--headless", "--norestore", "--convert-to", "pdf", "--outdir", "out", "보고서.docx"])

    def test_the_profile_carries_an_installed_korean_font(self):
        with tempfile.TemporaryDirectory() as profile, tempfile.NamedTemporaryFile(suffix=".ttf") as font:
            with mock.patch.object(libreoffice, "HANGUL_FONT_PATHS", [font.name, "/missing/NanumGothic.ttf"]):
                libreoffice.prepare_profile(Path(profile))
            self.assertEqual([path.name for path in (Path(profile) / "user" / "fonts").iterdir()], [Path(font.name).name])

    def test_a_missing_libreoffice_is_a_named_error(self):
        with mock.patch.object(libreoffice.shutil, "which", return_value=None), mock.patch.object(libreoffice, "APPLICATION_PATHS", ("/missing/soffice",)):
            with self.assertRaises(OfficeFailure) as raised:
                libreoffice.convert_with_libreoffice(Path("report.docx"), "pdf", Path(tempfile.gettempdir()))
        self.assertEqual(raised.exception.issues[0].kind.code, "LIBREOFFICE_UNAVAILABLE")


@unittest.skipUnless(libreoffice.find_soffice(), "LibreOffice is not installed")
class RenderTest(ContractFixture):
    def test_a_document_renders_to_pages_and_a_contact_sheet(self):
        envelope = run_office(["doc", "render", "contract.docx", "--scale", "0.5"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertEqual(envelope["details"]["pageCount"], 1)
        self.assertTrue((self.directory / "contract-pages" / "contact-sheet.png").exists())
        self.assertTrue((self.directory / "contract-pages" / "contract.pdf").exists())

    def test_a_workbook_renders_through_the_same_route(self):
        run_office(["sheet", "create", "매출.xlsx", "--title", "매출", "--row", "월,매출", "--row", "1월,1200"], self.directory)
        envelope = run_office(["sheet", "render", "매출.xlsx"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertTrue((self.directory / "매출-pages" / "page-001.png").exists())


if __name__ == "__main__":
    unittest.main()
