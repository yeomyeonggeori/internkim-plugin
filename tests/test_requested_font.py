import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from fontTools.ttLib import TTFont  # noqa: E402

from fonts.registry import FONT_DIRECTORY  # noqa: E402
from fonts.requested import GOOGLE_LISTING_URL, resolve_requested_font  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
