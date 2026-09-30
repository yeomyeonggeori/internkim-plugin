from __future__ import annotations

import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree
import zipfile

from test_deck_geometry import can_render_in_a_browser


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
OFFICE_ENTRY = SCRIPTS_PATH.parent / "office"
FONTS_PATH = SCRIPTS_PATH.parents[1] / "assets" / "fonts" / "paperlogy"
sys.path.insert(0, str(SCRIPTS_PATH.parent))
sys.path.insert(0, str(SCRIPTS_PATH))

from editable_pptx import read_text_layers, write_editable_pptx  # noqa: E402
from png_codec import write_png  # noqa: E402
from resource_inlining import VENDORED_PAPERLOGY_FONTS  # noqa: E402
from truetype_font import read_truetype_face  # noqa: E402


NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
PACKAGE_RELATIONSHIPS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
EOT_MAGIC_NUMBER = 0x504C
DECK_SOURCE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Fixture</title>
<style>
body { margin: 0; font-family: "Paperlogy", system-ui; }
section { width: 1600px; height: 900px; position: relative; overflow: hidden; box-sizing: border-box; padding: 96px 120px; background: #f8fafc; word-break: keep-all; }
h1 { font-size: 80px; font-weight: 800; margin: 0; }
h2 { font-size: 52px; font-weight: 700; margin: 0 0 40px; }
p, li, td, th { font-size: 30px; line-height: 1.5; }
.card { background: #fff; border: 2px solid #cbd5e1; border-radius: 24px; padding: 32px; margin-top: 32px; }
.stamp { position: absolute; right: 100px; top: 90px; transform: rotate(-8deg); border: 4px solid #b91c1c; font-weight: 800; }
td.number { text-align: right; }
</style></head><body data-visual-system="fixture">
<section data-slide-role="cover"><h1>샘플전자 매출은<br>3분기에 18% 늘었습니다</h1><p>박예시 · <em>전략기획팀</em></p><aside class="notes">표지 노트</aside></section>
<section data-slide-role="summary"><h2>성장은 두 가지에서 나왔습니다</h2>
<ul><li>프리미엄 전환이 <strong>2배</strong> 늘었습니다</li><li>설치가 하루로 줄었습니다</li></ul>
<ol start="3"><li>공공 계약 12건</li><li>자세한 표는 <a href="https://example.com/q3">부록</a>에 있습니다</li></ol>
<div class="card"><span>카드 안의 문장</span></div></section>
<section data-slide-role="comparison"><h2>지역별 매출</h2>
<table><tr><th>지역</th><th>3분기</th></tr><tr><td>수도권</td><td class="number">₩25억</td></tr></table>
<div class="stamp">잠정</div><aside class="notes">표 노트</aside></section>
</body></html>
"""


def run_properties(slide_xml: ElementTree.Element) -> list[ElementTree.Element]:
    return slide_xml.findall(".//a:rPr", NAMESPACES) + slide_xml.findall(".//a:endParaRPr", NAMESPACES)


def text_box_texts(slide_xml: ElementTree.Element) -> list[str]:
    return ["".join(text.text or "" for text in shape.iterfind(".//a:t", NAMESPACES)) for shape in slide_xml.iterfind(".//p:sp", NAMESPACES)]


def without_whitespace(text: str) -> str:
    return re.sub(r"\s+", "", text)


def slide_size(archive: zipfile.ZipFile) -> tuple[int, int]:
    size = ElementTree.fromstring(archive.read("ppt/presentation.xml")).find("p:sldSz", NAMESPACES)
    return int(size.get("cx")), int(size.get("cy"))


def shape_frames(slide_xml: ElementTree.Element) -> list[tuple[int, int, int, int]]:
    frames = []
    for transform in slide_xml.iterfind(".//a:xfrm", NAMESPACES):
        offset, extent = transform.find("a:off", NAMESPACES), transform.find("a:ext", NAMESPACES)
        frames.append((int(offset.get("x")), int(offset.get("y")), int(extent.get("cx")), int(extent.get("cy"))))
    return frames


def notes_text(archive: zipfile.ZipFile, number: int) -> str | None:
    relationships = ElementTree.fromstring(archive.read(f"ppt/slides/_rels/slide{number}.xml.rels"))
    for relationship in relationships.iter(f"{PACKAGE_RELATIONSHIPS}Relationship"):
        if relationship.get("Type").endswith("/notesSlide"):
            notes = ElementTree.fromstring(archive.read("ppt/notesSlides/" + Path(relationship.get("Target")).name))
            return "".join(text.text or "" for text in notes.iterfind(".//a:t", NAMESPACES))
    return None


def layout_run(text: str, **overrides) -> dict:
    run = {"text": text, "fontFamily": "PaperlogyLocal", "fontWeight": 400, "italic": False, "sizePx": 30, "color": "rgb(15, 23, 42)", "opacity": 1, "letterSpacingPx": 0, "underline": False, "strike": False, "baseline": "", "href": None}
    return {**run, **overrides}


def layout_block(runs: list[dict], box: dict, bullet: dict | None = None) -> dict:
    paragraph = {"alignment": "l", "lineHeightPx": 45, "spaceBeforePx": 0, "bullet": bullet, "runs": runs}
    return {"box": box, "insets": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "anchor": "t", "singleLine": True, "noWrap": False, "keepWords": True, "firstLineHalfLeading": 7.5, "paragraphs": [paragraph]}


def write_layers(review_path: Path, blocks: list[dict]) -> None:
    layers_path = review_path / "pptx-layers"
    layers_path.mkdir(parents=True)
    slide = {"width": 1600, "height": 900, "visibleText": "", "pictureTexts": [], "blocks": blocks}
    (layers_path / "layout.json").write_text(json.dumps({"language": "ko", "slides": [slide]}), encoding="utf-8")
    write_png(layers_path / "background.001.png", 32, 18, [[(255, 255, 255, 255)] * 32 for _ in range(18)])


class EditablePptxPackageTest(unittest.TestCase):
    def write(self, blocks: list[dict]) -> tuple[zipfile.ZipFile, object]:
        directory = Path(self.temporary_directory())
        write_layers(directory / "review", blocks)
        written = write_editable_pptx(read_text_layers(directory / "review", 1), [""], directory / "deck.pptx")
        archive = zipfile.ZipFile(directory / "deck.pptx")
        self.addCleanup(archive.close)
        return archive, written

    def temporary_directory(self) -> str:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return directory.name

    def test_weights_map_to_their_own_embedded_paperlogy_face(self):
        blocks = [
            layout_block([layout_run("본문 "), layout_run("굵게", fontWeight=700)], {"left": 100, "top": 100, "right": 900, "bottom": 150}),
            layout_block([layout_run("제목", fontWeight=800, sizePx=80)], {"left": 100, "top": 200, "right": 900, "bottom": 300}),
        ]
        archive, written = self.write(blocks)
        slide = ElementTree.fromstring(archive.read("ppt/slides/slide1.xml"))
        typefaces = [(properties.find("a:latin", NAMESPACES).get("typeface"), properties.find("a:ea", NAMESPACES).get("typeface")) for properties in run_properties(slide)]
        self.assertEqual(set(typefaces), {("Paperlogy 4 Regular", "Paperlogy 4 Regular"), ("Paperlogy 7 Bold", "Paperlogy 7 Bold"), ("Paperlogy 8 ExtraBold", "Paperlogy 8 ExtraBold")})
        self.assertFalse(any(properties.get("b") == "1" for properties in run_properties(slide)))
        self.assertEqual(written.embedded_typefaces, ("Paperlogy 4 Regular", "Paperlogy 7 Bold", "Paperlogy 8 ExtraBold"))

    def test_embedded_fonts_are_listed_related_and_wrapped_as_embedded_open_type(self):
        archive, _ = self.write([layout_block([layout_run("본문")], {"left": 100, "top": 100, "right": 900, "bottom": 150})])
        presentation = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
        self.assertEqual(presentation.get("embedTrueTypeFonts"), "1")
        relationships = {relationship.get("Id"): relationship.get("Target") for relationship in ElementTree.fromstring(archive.read("ppt/_rels/presentation.xml.rels")).iter(f"{PACKAGE_RELATIONSHIPS}Relationship")}
        embedded = presentation.findall("p:embeddedFontLst/p:embeddedFont", NAMESPACES)
        self.assertEqual([font.find("p:font", NAMESPACES).get("typeface") for font in embedded], ["Paperlogy 4 Regular"])
        font_part = "ppt/" + relationships[embedded[0].find("p:regular", NAMESPACES).get(f"{{{NAMESPACES['r']}}}id")]
        font_data = archive.read(font_part)
        eot_size, font_data_size, version = struct.unpack_from("<III", font_data)
        self.assertEqual(eot_size, len(font_data))
        self.assertEqual(version, 0x00020002)
        self.assertEqual(struct.unpack_from("<H", font_data, 34)[0], EOT_MAGIC_NUMBER)
        self.assertEqual(font_data[-font_data_size:], (FONTS_PATH / "Paperlogy-4Regular.ttf").read_bytes())
        self.assertIn('Extension="fntdata"', archive.read("[Content_Types].xml").decode())

    def test_text_boxes_never_autofit_and_wrap_inside_the_slide(self):
        archive, _ = self.write([layout_block([layout_run("오른쪽 끝에 닿는 한 줄")], {"left": 1200, "top": 820, "right": 1600, "bottom": 900})])
        slide = ElementTree.fromstring(archive.read("ppt/slides/slide1.xml"))
        body = slide.find(".//p:txBody/a:bodyPr", NAMESPACES)
        self.assertEqual(body.get("wrap"), "square")
        self.assertIsNotNone(body.find("a:noAutofit", NAMESPACES))
        width, height = slide_size(archive)
        for left, top, frame_width, frame_height in shape_frames(slide):
            self.assertGreaterEqual(min(left, top), 0)
            self.assertLessEqual(left + frame_width, width)
            self.assertLessEqual(top + frame_height, height)

    def test_an_ordered_list_numbers_from_its_start_and_a_default_start_is_left_implicit(self):
        numbering = {"character": "", "numbering": "arabicPeriod", "color": "rgb(15, 23, 42)", "outside": True, "markerWidthPx": 30}
        blocks = [
            layout_block([layout_run("첫째")], {"left": 100, "top": 100, "right": 900, "bottom": 150}, {**numbering, "startAt": 1}),
            layout_block([layout_run("셋째")], {"left": 100, "top": 200, "right": 900, "bottom": 250}, {**numbering, "startAt": 3}),
        ]
        archive, _ = self.write(blocks)
        numbers = ElementTree.fromstring(archive.read("ppt/slides/slide1.xml")).findall(".//a:buAutoNum", NAMESPACES)
        self.assertEqual([number.get("startAt") for number in numbers], [None, "3"])

    def test_an_unknown_family_is_named_as_rendered_and_reported_unembedded(self):
        archive, written = self.write([layout_block([layout_run("Hello", fontFamily="Georgia")], {"left": 100, "top": 100, "right": 900, "bottom": 150})])
        self.assertEqual(written.unembedded_families, ("Georgia",))
        properties = run_properties(ElementTree.fromstring(archive.read("ppt/slides/slide1.xml")))[0]
        self.assertEqual(properties.find("a:latin", NAMESPACES).get("typeface"), "Georgia")
        self.assertEqual(properties.find("a:ea", NAMESPACES).get("typeface"), "Georgia")


class VendoredFontTest(unittest.TestCase):
    def test_each_embedded_ttf_is_the_weight_its_browser_twin_is_declared_as(self):
        for weight, woff2_name in VENDORED_PAPERLOGY_FONTS:
            with self.subTest(font=woff2_name):
                face = read_truetype_face((FONTS_PATH / woff2_name).with_suffix(".ttf"))
                self.assertEqual(face.weight, weight)
                self.assertTrue(face.family.startswith("Paperlogy "))
                self.assertTrue(face.allows_embedding)


class RenderedEditablePptxTest(unittest.TestCase):
    @unittest.skipUnless(can_render_in_a_browser(), "needs bun and a browser that speaks the Chrome DevTools Protocol")
    def test_the_pptx_holds_each_slides_visible_text_in_the_deck_font_inside_the_slide(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(DECK_SOURCE, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build"], capture_output=True, text=True, cwd=deck_path, env={**os.environ, "FORMATS": "pptx"})
            envelope = json.loads(completed.stdout)
            if envelope["details"]["pptx"]["source"] != "browser":
                self.skipTest("the browser did not render the deck on this host")
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
            with zipfile.ZipFile(deck_path / "build" / f"{deck_path.name}.pptx") as archive:
                slides = [ElementTree.fromstring(archive.read(f"ppt/slides/slide{number}.xml")) for number in range(1, len(layout["slides"]) + 1)]
                width, height = slide_size(archive)
                notes = [notes_text(archive, number) for number in range(1, len(slides) + 1)]
        self.assertEqual(envelope["details"]["pptx"]["textKeptAsPicture"], ["잠정"])
        self.assertEqual(notes, ["표지 노트", None, "표 노트"])
        for number, (slide, measured) in enumerate(zip(slides, layout["slides"]), start=1):
            with self.subTest(slide=number):
                visible = without_whitespace(measured["visibleText"])
                for picture_text in measured["pictureTexts"]:
                    visible = visible.replace(without_whitespace(picture_text), "", 1)
                self.assertEqual(without_whitespace("".join(text_box_texts(slide))), visible)
                for properties in run_properties(slide):
                    self.assertTrue(properties.find("a:latin", NAMESPACES).get("typeface").startswith("Paperlogy "))
                    self.assertEqual(properties.find("a:ea", NAMESPACES).get("typeface"), properties.find("a:latin", NAMESPACES).get("typeface"))
                for left, top, frame_width, frame_height in shape_frames(slide):
                    self.assertTrue(0 <= left and 0 <= top and left + frame_width <= width and top + frame_height <= height)


if __name__ == "__main__":
    unittest.main()
