from __future__ import annotations

import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree
import zipfile

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts" / "deck"
OFFICE_ENTRY = SCRIPTS_PATH.parent / "office"
FONTS_PATH = SCRIPTS_PATH.parents[1] / "assets" / "fonts" / "paperlogy"
sys.path.insert(0, str(SCRIPTS_PATH.parent))
sys.path.insert(0, str(SCRIPTS_PATH))

from editable_pptx import read_text_layers, write_editable_pptx  # noqa: E402
from png_fixture import read_png, write_png  # noqa: E402
from resource_inlining import VENDORED_PAPERLOGY_FONTS  # noqa: E402
from truetype_font import read_truetype_face  # noqa: E402


NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
PACKAGE_RELATIONSHIPS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
EOT_MAGIC_NUMBER = 0x504C
EMU_PER_PIXEL = 7620
DECK_SOURCE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Fixture</title>
<style>
body { margin: 0; font-family: "Paperlogy", system-ui; }
section { width: 1600px; height: 900px; position: relative; overflow: hidden; box-sizing: border-box; padding: 96px 120px; background: #f8fafc; word-break: keep-all; }
h1 { font-size: 80px; font-weight: 800; margin: 0; }
h2 { font-size: 52px; font-weight: 700; margin: 0 0 40px; }
p, li, td, th { font-size: 30px; line-height: 1.5; }
.card { background: #fff; border: 2px solid #cbd5e1; border-radius: 24px; padding: 32px; margin-top: 32px; }
.meter { position: relative; height: 14px; width: 400px; margin-top: 24px; background: #e2e8f0; }
.meter span { position: absolute; left: 0; top: 0; bottom: 0; width: 60%; background: rgba(37, 99, 235, 0.5); border-radius: 7px; }
.stamp { position: absolute; right: 100px; top: 90px; transform: rotate(-8deg); border: 4px solid #b91c1c; font-weight: 800; }
td.number { text-align: right; }
.narrow { width: 440px; }
.rail { position: relative; height: 30px; }
.rail::before { content: ""; position: absolute; left: 0; right: 0; top: 10px; height: 4px; background: #14213d; }
</style></head><body data-visual-system="fixture">
<section data-slide-role="cover"><h1>샘플전자 매출은<br>3분기에 18% 늘었습니다</h1><p>박예시 · <em>전략기획팀</em></p><aside class="notes">표지 노트</aside></section>
<section data-slide-role="summary"><h2>성장은 두 가지에서 나왔습니다</h2>
<ul><li>프리미엄 전환이 <strong>2배</strong> 늘었습니다</li><li>설치가 하루로 줄었습니다</li></ul>
<ol start="3"><li>공공 계약 12건</li><li>자세한 표는 <a href="https://example.com/q3">부록</a>에 있습니다</li></ol>
<div class="card"><span>카드 안의 문장</span></div><div class="meter"><span></span></div>
<p class="narrow">연간 물류비 4.2억원 절감 · 회수 약 4.3년</p><div class="rail"></div></section>
<section data-slide-role="comparison"><h2>지역별 매출</h2>
<table><tr><th>지역</th><th>3분기</th></tr><tr><td>수도권</td><td class="number">₩25억</td></tr></table>
<div class="stamp">잠정</div><aside class="notes">표 노트</aside></section>
</body></html>
"""


def run_properties(slide_xml: ElementTree.Element) -> list[ElementTree.Element]:
    return slide_xml.findall(".//a:rPr", NAMESPACES) + slide_xml.findall(".//a:endParaRPr", NAMESPACES)


def text_box_texts(slide_xml: ElementTree.Element) -> list[str]:
    return ["".join(text.text or "" for text in shape.iterfind(".//a:t", NAMESPACES)) for shape in slide_xml.iterfind(".//p:sp", NAMESPACES)]


def table_cell_texts(slide_xml: ElementTree.Element) -> list[str]:
    return ["".join(text.text or "" for text in cell.iterfind(".//a:t", NAMESPACES)) for cell in slide_xml.iterfind(".//a:tc", NAMESPACES)]


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


def shape_tree_kinds(slide_xml: ElementTree.Element) -> list[str]:
    tree = slide_xml.find("p:cSld/p:spTree", NAMESPACES)
    kinds = []
    for child in tree:
        tag = child.tag.rsplit("}", 1)[1]
        if tag == "sp":
            is_text_box = child.find("p:nvSpPr/p:cNvSpPr", NAMESPACES).get("txBox") == "1"
            tag = "text" if is_text_box else child.find("p:spPr/a:prstGeom", NAMESPACES).get("prst")
        kinds.append(tag)
    return [kind for kind in kinds if kind not in ("nvGrpSpPr", "grpSpPr")]


def preset_shapes(slide_xml: ElementTree.Element, preset: str) -> list[ElementTree.Element]:
    return [shape for shape in slide_xml.iterfind(".//p:spPr", NAMESPACES) if shape.find("a:prstGeom", NAMESPACES).get("prst") == preset]


def solid_color(parent: ElementTree.Element) -> tuple[str | None, str | None]:
    color = parent.find("a:solidFill/a:srgbClr", NAMESPACES)
    if color is None:
        return None, None
    alpha = color.find("a:alpha", NAMESPACES)
    return color.get("val"), None if alpha is None else alpha.get("val")


def shape_center_pixel(shape_properties: ElementTree.Element) -> tuple[int, int]:
    offset, extent = shape_properties.find("a:xfrm/a:off", NAMESPACES), shape_properties.find("a:xfrm/a:ext", NAMESPACES)
    return (int(offset.get("x")) + int(extent.get("cx")) // 2) // EMU_PER_PIXEL, (int(offset.get("y")) + int(extent.get("cy")) // 2) // EMU_PER_PIXEL


def paragraph_lines(slide_xml: ElementTree.Element) -> list[list[str]]:
    paragraphs = []
    for paragraph in slide_xml.iterfind(".//p:txBody/a:p", NAMESPACES):
        lines = [""]
        for child in paragraph:
            tag = child.tag.rsplit("}", 1)[1]
            if tag == "br":
                lines.append("")
            if tag == "r":
                lines[-1] += child.find("a:t", NAMESPACES).text or ""
        paragraphs.append([without_whitespace(line) for line in lines])
    return paragraphs


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
    paragraph = {"alignment": "l", "lineHeightPx": 45, "spaceBeforePx": 0, "bullet": bullet, "runs": runs, "lines": [{"widthPx": 200, "sizePx": 30, "text": "".join(run["text"] for run in runs)}]}
    return {"box": box, "insets": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "anchor": "t", "noWrap": False, "keepWords": True, "firstLineHalfLeading": 7.5, "paragraphs": [paragraph]}


def write_layers(review_path: Path, blocks: list[dict], shapes: list[dict] | None = None) -> None:
    layers_path = review_path / "pptx-layers"
    layers_path.mkdir(parents=True)
    slide = {"width": 1600, "height": 900, "visibleText": "", "pictureTexts": [], "blocks": blocks, "shapes": shapes or [], "boxesKeptAsPicture": 0}
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

    def test_boxes_become_native_shapes_between_the_background_picture_and_the_text(self):
        card = {"geometry": "roundRect", "box": {"left": 101, "top": 101, "right": 499, "bottom": 299}, "radiusPx": 23, "fill": {"color": "rgb(255, 255, 255)", "opacity": 1}, "line": {"color": "rgb(203, 213, 225)", "opacity": 1, "widthPx": 2}}
        chip = {"geometry": "round2SameRect", "box": {"left": 120, "top": 240, "right": 220, "bottom": 280}, "radiusPx": 8, "bottomRadiusPx": 0, "fill": {"color": "rgba(37, 99, 235, 0.5)", "opacity": 0.8}, "line": None}
        rule = {"geometry": "line", "from": {"x": 100, "y": 400.5}, "to": {"x": 500, "y": 400.5}, "line": {"color": "rgb(20, 33, 61)", "opacity": 1, "widthPx": 3}}
        directory = Path(self.temporary_directory())
        write_layers(directory / "review", [layout_block([layout_run("카드")], {"left": 130, "top": 130, "right": 400, "bottom": 175})], [card, chip, rule])
        written = write_editable_pptx(read_text_layers(directory / "review", 1), [""], directory / "deck.pptx")
        with zipfile.ZipFile(directory / "deck.pptx") as archive:
            slide = ElementTree.fromstring(archive.read("ppt/slides/slide1.xml"))
        self.assertEqual(written.shape_count, 3)
        self.assertEqual(shape_tree_kinds(slide), ["pic", "roundRect", "round2SameRect", "cxnSp", "text"])
        card_properties, = preset_shapes(slide, "roundRect")
        self.assertEqual(card_properties.find("a:prstGeom/a:avLst/a:gd", NAMESPACES).get("fmla"), f"val {round(23 / 198 * 100000)}")
        self.assertEqual(solid_color(card_properties), ("FFFFFF", None))
        self.assertEqual(card_properties.find("a:ln", NAMESPACES).get("w"), str(2 * EMU_PER_PIXEL))
        self.assertEqual(solid_color(card_properties.find("a:ln", NAMESPACES)), ("CBD5E1", None))
        chip_properties, = preset_shapes(slide, "round2SameRect")
        self.assertEqual([guide.get("fmla") for guide in chip_properties.iterfind("a:prstGeom/a:avLst/a:gd", NAMESPACES)], ["val 20000", "val 0"])
        self.assertEqual(solid_color(chip_properties), ("2563EB", "40000"))
        rule_properties, = preset_shapes(slide, "line")
        self.assertEqual(rule_properties.find("a:xfrm/a:ext", NAMESPACES).get("cy"), "0")
        self.assertEqual(rule_properties.find("a:ln", NAMESPACES).get("w"), str(3 * EMU_PER_PIXEL))

    def test_measured_lines_are_written_as_breaks_and_the_box_widens_by_the_measured_slack(self):
        runs = [layout_run("연간 물류비 4.2억원 절감 · 회수 약 "), {"isBreak": True, "text": ""}, layout_run("4.3년")]
        block = layout_block(runs, {"left": 100, "top": 100, "right": 400, "bottom": 190})
        block["paragraphs"][0]["lines"] = [
            {"widthPx": 298, "sizePx": 24, "text": "연간 물류비 4.2억원 절감 · 회수 약"},
            {"widthPx": 50, "sizePx": 24, "text": "4.3년"},
        ]
        archive, _ = self.write([block])
        slide = ElementTree.fromstring(archive.read("ppt/slides/slide1.xml"))
        self.assertEqual(paragraph_lines(slide), [["연간물류비4.2억원절감·회수약", "4.3년"]])
        transitions_in_first_line = 4
        expected_width = 298 * 1.01 + transitions_in_first_line * 0.25 * 24
        frame = shape_frames(slide)[-1]
        self.assertEqual(frame[0], 100 * EMU_PER_PIXEL)
        self.assertEqual(frame[2], round(expected_width * EMU_PER_PIXEL))

    def test_a_box_whose_lines_already_fit_with_slack_keeps_its_measured_width(self):
        archive, _ = self.write([layout_block([layout_run("짧은 줄")], {"left": 100, "top": 100, "right": 900, "bottom": 150})])
        frame = shape_frames(ElementTree.fromstring(archive.read("ppt/slides/slide1.xml")))[-1]
        self.assertEqual(frame[2], 800 * EMU_PER_PIXEL)

    def test_validate_counts_the_shapes_that_hold_content_and_not_the_rules_between_them(self):
        rules = [{"geometry": "line", "from": {"x": 100, "y": 100 + row * 10}, "to": {"x": 900, "y": 100 + row * 10}, "line": {"color": "rgb(216, 212, 203)", "opacity": 1, "widthPx": 1}} for row in range(60)]
        directory = Path(self.temporary_directory())
        write_layers(directory / "review", [layout_block([layout_run("표 제목")], {"left": 100, "top": 20, "right": 900, "bottom": 70})], rules)
        write_editable_pptx(read_text_layers(directory / "review", 1), [""], directory / "deck.pptx")
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "validate", str(directory / "deck.pptx")], capture_output=True, text=True)
        envelope = json.loads(completed.stdout)
        self.assertEqual(envelope["details"]["slides"][0]["shapeCount"], 62)
        self.assertEqual(envelope["details"]["slides"][0]["contentShapeCount"], 2)
        self.assertNotIn("TOO_MANY_SHAPES", [issue["code"] for issue in envelope["issues"]])

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
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_the_pptx_holds_each_slides_visible_text_in_the_deck_font_inside_the_slide(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory)
            (deck_path / "slides.html").write_text(DECK_SOURCE, encoding="utf-8")
            completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "deck", "build", "--format", "pptx"], capture_output=True, text=True, cwd=deck_path)
            envelope = json.loads(completed.stdout)
            if envelope["details"]["pptx"]["source"] != "layout":
                self.skipTest("the renderer could not run on this host")
            layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
            with zipfile.ZipFile(deck_path / "build" / f"{deck_path.name}.pptx") as archive:
                slides = [ElementTree.fromstring(archive.read(f"ppt/slides/slide{number}.xml")) for number in range(1, len(layout["slides"]) + 1)]
                width, height = slide_size(archive)
                notes = [notes_text(archive, number) for number in range(1, len(slides) + 1)]
            backgrounds = [read_png(deck_path / "build" / "review" / "pptx-layers" / f"background.{number:03}.png") for number in range(1, len(slides) + 1)]
        self.assertEqual(envelope["details"]["pptx"]["textKeptAsPicture"], ["잠정"])
        self.assertEqual(notes, ["표지 노트", None, "표 노트"])
        self.assertEqual(table_cell_texts(slides[2]), ["지역", "3분기", "수도권", "₩25억"])
        self.assertNotIn("수도권", "".join(text_box_texts(slides[2])))
        self.assert_boxes_are_shapes_and_left_the_picture(slides, backgrounds)
        narrow, = [lines for lines in paragraph_lines(slides[1]) if "".join(lines).startswith("연간물류비")]
        self.assertGreater(len(narrow), 1)
        self.assertTrue(any("4.3년" in line for line in narrow), narrow)
        for number, (slide, measured) in enumerate(zip(slides, layout["slides"]), start=1):
            with self.subTest(slide=number):
                visible = without_whitespace(measured["visibleText"])
                for picture_text in measured["pictureTexts"]:
                    visible = visible.replace(without_whitespace(picture_text), "", 1)
                self.assertEqual(without_whitespace("".join(text_box_texts(slide) + table_cell_texts(slide))), visible)
                measured_lines = [[without_whitespace(line["text"]) for line in paragraph["lines"]] for block in measured["blocks"] if not block["cell"] for paragraph in block["paragraphs"]]
                self.assertEqual(paragraph_lines(slide), measured_lines)
                for properties in run_properties(slide):
                    self.assertTrue(properties.find("a:latin", NAMESPACES).get("typeface").startswith("Paperlogy "))
                    self.assertEqual(properties.find("a:ea", NAMESPACES).get("typeface"), properties.find("a:latin", NAMESPACES).get("typeface"))
                for left, top, frame_width, frame_height in shape_frames(slide):
                    self.assertTrue(0 <= left and 0 <= top and left + frame_width <= width and top + frame_height <= height)

    def assert_boxes_are_shapes_and_left_the_picture(self, slides: list[ElementTree.Element], backgrounds: list[dict]) -> None:
        summary, comparison = slides[1], slides[2]
        card, = [shape for shape in preset_shapes(summary, "roundRect") if solid_color(shape.find("a:ln", NAMESPACES))[0] == "CBD5E1"]
        self.assertEqual(solid_color(card), ("FFFFFF", None))
        self.assertEqual(card.find("a:ln", NAMESPACES).get("w"), str(2 * EMU_PER_PIXEL))
        track, = [shape for shape in preset_shapes(summary, "rect") if solid_color(shape) == ("E2E8F0", None)]
        meter_fill, = [shape for shape in preset_shapes(summary, "roundRect") if solid_color(shape)[0] == "2563EB"]
        self.assertEqual(solid_color(meter_fill), ("2563EB", "50000"))
        kinds = shape_tree_kinds(summary)
        self.assertEqual(kinds[0], "pic")
        self.assertEqual(kinds.index("text"), len(kinds) - kinds.count("text"))
        shape_order = list(summary.iter())
        self.assertLess(shape_order.index(track), shape_order.index(meter_fill))
        for shape in (card, track, meter_fill):
            x, y = shape_center_pixel(shape)
            self.assertEqual(backgrounds[1]["rows"][y][x][:3], (0xF8, 0xFA, 0xFC))
        rail, = [shape for shape in preset_shapes(summary, "rect") if solid_color(shape) == ("14213D", None)]
        self.assertEqual(rail.find("a:xfrm/a:ext", NAMESPACES).get("cx"), str(1360 * EMU_PER_PIXEL))
        self.assertEqual(rail.find("a:xfrm/a:ext", NAMESPACES).get("cy"), str(4 * EMU_PER_PIXEL))
        stamp_pixels = [pixel for row in backgrounds[2]["rows"] for pixel in row if pixel[3] > 200 and pixel[0] > 150 and pixel[1] < 80 and pixel[2] < 80]
        self.assertTrue(stamp_pixels, "the rotated stamp's border stays in the picture")
        stamp_outlines = [shape for shape in comparison.iterfind(".//p:spPr/a:ln/a:solidFill/a:srgbClr", NAMESPACES) if shape.get("val") == "B91C1C"]
        self.assertEqual(stamp_outlines, [])


if __name__ == "__main__":
    unittest.main()
