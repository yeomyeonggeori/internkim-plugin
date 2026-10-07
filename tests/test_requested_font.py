import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from fontTools.ttLib import TTFont  # noqa: E402

from fonts.registry import FONT_DIRECTORY, reset_runtime_families  # noqa: E402
from fonts.requested import GOOGLE_LISTING_URL, resolve_requested_font  # noqa: E402
from task_context_fixture import CONTEXT_VARIABLE, environment_with_context, write_context_at  # noqa: E402

BASE_FACE = FONT_DIRECTORY / "a2z" / "A2Z-4Regular.woff2"
NAME_IDS = (1, 4, 6, 16)


def font_bytes(family: str, weight: int = 400, fs_type: int = 0) -> bytes:
    font = TTFont(str(BASE_FACE))
    font.flavor = None
    for record in font["name"].names:
        if record.nameID in NAME_IDS:
            record.string = family
    font["OS/2"].usWeightClass = weight
    font["OS/2"].fsType = fs_type
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


class Web:
    def __init__(self, fonts: dict[str, dict[str, bytes]]):
        self.fonts = fonts
        self.requests: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.requests.append(url)
        for slug, files in self.fonts.items():
            if url == GOOGLE_LISTING_URL.format(directory="ofl", slug=slug):
                return json.dumps([{"name": name, "download_url": f"https://raw.example/{slug}/{name}"} for name in files]).encode()
            for name, content in files.items():
                if url == f"https://raw.example/{slug}/{name}":
                    return content
        raise urllib.error.URLError("not found")


class RequestedFontTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.cache = self.path / "cache"

    def attach(self, name: str, content: bytes) -> Path:
        attachment = self.path / "attachments" / name
        attachment.parent.mkdir(exist_ok=True)
        attachment.write_bytes(content)
        return attachment

    def test_no_request_needs_no_font_at_all(self):
        resolution = resolve_requested_font("Paperlogy", [], self.cache, Web({}))
        self.assertEqual(resolution.font.family.name, "Paperlogy")
        self.assertEqual(resolution.font.source.kind, "bundled")

    def test_a_font_attached_by_the_requester_is_used(self):
        attached = [self.attach("Sample-Regular.ttf", font_bytes("Sample Sans")), self.attach("Sample-Bold.ttf", font_bytes("Sample Sans", 700))]
        web = Web({})
        resolution = resolve_requested_font("Sample Sans", attached, self.cache, web)
        self.assertIsNone(resolution.note)
        self.assertEqual([face.weight for face in resolution.font.family.faces], [400, 700])
        self.assertEqual(web.requests, [])
        for face in resolution.font.family.faces:
            self.assertTrue(resolution.font.family.path(face).is_file())

    def test_a_font_on_google_fonts_is_downloaded_verified_and_cached_with_its_source(self):
        web = Web({"samplesans": {"SampleSans-Regular.ttf": font_bytes("Sample Sans"), "SampleSans-Bold.ttf": font_bytes("Sample Sans", 700)}})
        resolution = resolve_requested_font("Sample Sans", [], self.cache, web)
        self.assertIsNone(resolution.note)
        self.assertEqual(resolution.font.source.kind, "google fonts")
        self.assertEqual(resolution.font.source.license, "OFL-1.1")
        self.assertTrue(resolution.font.source.url.startswith("https://raw.example/samplesans/"))
        self.assertEqual([face.weight for face in resolution.font.family.faces], [400, 700])

    def test_a_font_cached_by_an_earlier_deck_is_reused_without_a_download(self):
        web = Web({"samplesans": {"SampleSans-Regular.ttf": font_bytes("Sample Sans"), "SampleSans-Bold.ttf": font_bytes("Sample Sans", 700)}})
        resolve_requested_font("Sample Sans", [], self.cache, web)
        offline = Web({})
        again = resolve_requested_font("Sample Sans", [], self.cache, offline)
        self.assertEqual(offline.requests, [])
        self.assertEqual(again.font.source.kind, "google fonts")
        self.assertEqual(again.font.source.license, "OFL-1.1")

    def test_a_download_whose_family_name_differs_is_rejected(self):
        web = Web({"samplesans": {"SampleSans-Regular.ttf": font_bytes("Another Family")}})
        resolution = resolve_requested_font("Sample Sans", [], self.cache, web)
        self.assertIsNone(resolution.font)
        self.assertIn("Sample Sans", resolution.note)

    def test_a_download_that_is_not_a_font_is_rejected(self):
        web = Web({"samplesans": {"SampleSans-Regular.ttf": b"<html>not a font</html>"}})
        self.assertIsNone(resolve_requested_font("Sample Sans", [], self.cache, web).font)

    def test_a_font_that_forbids_embedding_gives_paperlogy_and_says_why(self):
        web = Web({"samplesans": {"SampleSans-Regular.ttf": font_bytes("Sample Sans", fs_type=2)}})
        resolution = resolve_requested_font("Sample Sans", [], self.cache, web)
        self.assertIsNone(resolution.font)
        self.assertIn("do not allow embedding", resolution.note)
        self.assertIn("Paperlogy", resolution.note)

    def test_a_missing_font_gives_paperlogy_a_note_naming_what_was_tried_and_an_offer(self):
        resolution = resolve_requested_font("Nowhere Display", [], self.cache, Web({}))
        self.assertIsNone(resolution.font)
        self.assertEqual(resolution.tried, ("local file", "cache", "google fonts"))
        self.assertIn("Attach the Nowhere Display font file", resolution.note)
        self.assertIn("rebuild the same deck", resolution.note)

    def test_an_unreachable_network_is_a_missing_font_not_a_failure(self):
        def offline(url: str) -> bytes:
            raise urllib.error.URLError("no network")

        self.assertIsNone(resolve_requested_font("Sample Sans", [], self.cache, offline).font)


DECK_PAGE = "<h2>Revenue grew 18 percent in the third quarter</h2><p>The logistics business closed the quarter above its plan in every region and every line of business we run.</p><svg aria-hidden=\"true\" width=\"1400\" height=\"520\" style=\"flex: 0 1 520px; min-height: 0; width: 100%\"></svg>"


def context_file(directory: Path, attachments: list[Path] = (), brand_font: str | None = None) -> Path:
    company = directory / "company"
    company.mkdir(exist_ok=True)
    profile = {"name": "Sample"} | ({"brandFont": brand_font} if brand_font else {})
    (company / "company-profile.json").write_text(json.dumps(profile), encoding="utf-8")
    facts = {"today": "2026-10-04", "company": {"en": str(company / "company-profile.json")}, "attachments": [{"name": path.name, "path": str(path)} for path in attachments]}
    return write_context_at(directory / "task" / "task-context.json", facts)


def style_sheet_with(selection: str) -> str:
    from staged_deck_fixture import style_sheet_markdown

    return style_sheet_markdown().removesuffix("---\n") + (f"{selection}\n" if selection else "") + "---\n"


def read_with(selection: str, directory: Path, context: Path, cache: Path):
    import os

    from deck.design_system import read_design_system

    (directory / "DESIGN.md").write_text(style_sheet_with(selection), encoding="utf-8")
    previous = {name: os.environ.get(name) for name in (CONTEXT_VARIABLE, "OFFICE_FONT_CACHE")}
    os.environ[CONTEXT_VARIABLE], os.environ["OFFICE_FONT_CACHE"] = str(context), str(cache)
    try:
        return read_design_system(directory / "DESIGN.md")
    finally:
        for name, value in previous.items():
            os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value)


class DesignFileFontTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(reset_runtime_families)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.cache = self.path / "cache"

    def attach(self, name: str, content: bytes) -> Path:
        attachment = self.path / name
        attachment.write_bytes(content)
        return attachment

    def test_no_request_is_paperlogy(self):
        system, issues = read_with("", self.path, context_file(self.path), self.cache)
        self.assertEqual((system.fonts["body"], issues), ("Paperlogy", []))

    def test_a_requested_font_that_was_attached_becomes_the_deck_family(self):
        attached = [self.attach("Sample-Regular.ttf", font_bytes("Sample Sans")), self.attach("Sample-Bold.ttf", font_bytes("Sample Sans", 700))]
        system, issues = read_with('requested-font: "Sample Sans"', self.path, context_file(self.path, attached), self.cache)
        self.assertEqual(issues, [])
        self.assertEqual((system.fonts["display"], system.fonts["body"]), ("Sample Sans", "Sample Sans"))

    def test_a_requested_font_that_cannot_be_found_is_paperlogy_with_a_warning_that_says_so(self):
        system, issues = read_with('requested-font: "Nowhere Display"', self.path, context_file(self.path), self.cache)
        self.assertEqual(system.fonts["body"], "Paperlogy")
        self.assertEqual([issue.kind.code for issue in issues], ["REQUESTED_FONT_UNAVAILABLE"])
        self.assertEqual(issues[0].kind.severity, "warning")
        self.assertIn("Attach the Nowhere Display font file", issues[0].message)

    def test_a_brand_font_in_the_company_profile_counts_as_requested(self):
        attached = [self.attach("Brand-Regular.ttf", font_bytes("Brand Face"))]
        system, issues = read_with("", self.path, context_file(self.path, attached, brand_font="Brand Face"), self.cache)
        self.assertEqual((system.fonts["body"], issues), ("Brand Face", []))

    def test_a_request_in_the_design_file_wins_over_the_brand_font(self):
        attached = [self.attach("Brand-Regular.ttf", font_bytes("Brand Face")), self.attach("Asked-Regular.ttf", font_bytes("Asked Face"))]
        system, _ = read_with('requested-font: "Asked Face"', self.path, context_file(self.path, attached, brand_font="Brand Face"), self.cache)
        self.assertEqual(system.fonts["body"], "Asked Face")


class RequestedFontEmbeddedTest(unittest.TestCase):
    def test_the_pptx_embeds_the_requested_family_and_names_it_on_every_run(self):
        import os
        import subprocess
        import zipfile

        from render_fixture import can_render
        from staged_deck_fixture import OFFICE_ENTRY, write_staged_deck

        if not can_render():
            self.skipTest("the renderer is not available")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            attached = [path / "Sample-Regular.ttf", path / "Sample-Bold.ttf"]
            attached[0].write_bytes(font_bytes("Sample Sans"))
            attached[1].write_bytes(font_bytes("Sample Sans", 700))
            context = context_file(path, attached)
            write_staged_deck(path, [DECK_PAGE])
            (path / "DESIGN.md").write_text(style_sheet_with('requested-font: "Sample Sans"'), encoding="utf-8")
            environment = environment_with_context(context) | {"OFFICE_FONT_CACHE": str(path / "cache")}
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", "build/deck.pptx", "."], capture_output=True, text=True, cwd=path, env=environment)
            envelope = json.loads(completed.stdout)
            self.assertNotEqual(envelope["status"], "error", envelope["summary"])
            with zipfile.ZipFile(path / "build" / "deck.pptx") as archive:
                names = archive.namelist()
                presentation = archive.read("ppt/presentation.xml").decode("utf-8")
                slide = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertTrue([name for name in names if name.startswith("ppt/fonts/")])
        self.assertIn('typeface="Sample Sans"', presentation)
        self.assertIn('typeface="Sample Sans"', slide)


if __name__ == "__main__":
    unittest.main()
