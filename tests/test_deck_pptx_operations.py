from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
import zipfile

from lxml import etree

from pptx_edit_fixture import part_contents
from test_deck_pptx_editing import KoreanDeckFixture, codes, run_office


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.editable_pptx import read_text_layers, write_editable_pptx  # noqa: E402
from png_fixture import write_png  # noqa: E402


P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
INCH = 914400


def slide_xml(path: Path, number: int):
    with zipfile.ZipFile(path) as archive:
        return etree.fromstring(archive.read(f"ppt/slides/slide{number}.xml"))


class LengthTest(KoreanDeckFixture):
    def test_geometry_takes_units_and_shares_of_the_slide(self):
        envelope = self.apply([{"op": "set_transform", "slide": 2, "shape": 1, "x": "1in", "y": "10%", "w": "5cm", "h": "72pt"}])
        self.assertEqual(envelope["status"], "ok", envelope)
        self.assertEqual(self.slide(2)["shapes"][1]["box"], {"x": INCH, "y": 685800, "w": 1800000, "h": INCH})

    def test_a_length_without_a_known_unit_is_refused_before_anything_is_written(self):
        original = (self.directory / "deck.pptx").read_bytes()
        envelope = self.apply([{"op": "set_transform", "slide": 2, "shape": 1, "x": "2 inches"}, {"op": "set_transform", "slide": 2, "shape": 1, "y": 2.5}])
        self.assertEqual(codes(envelope), ["INVALID_VALUE", "INVALID_VALUE"])
        self.assertIn('"2in"', envelope["issues"][1]["suggestion"])
        self.assertEqual((self.directory / "deck.pptx").read_bytes(), original)


class ArrangementTest(KoreanDeckFixture):
    def test_align_moves_frames_to_the_common_edge_or_the_slide_center(self):
        self.apply([{"op": "align_shapes", "slide": 2, "shapes": [1, 3, 4], "edge": "left"}])
        shapes = self.slide(2)["shapes"]
        self.assertEqual({shapes[index]["box"]["x"] for index in (1, 3, 4)}, {609600})
        self.apply([{"op": "align_shapes", "slide": 2, "shapes": [4], "edge": "center", "to": "slide"}])
        box = self.slide(2)["shapes"][4]["box"]
        self.assertEqual(box["x"], (12192000 - box["w"]) // 2)

    def test_distribute_evens_the_gaps_and_keeps_the_outer_shapes(self):
        before = self.slide(2)["shapes"]
        self.apply([{"op": "distribute_shapes", "slide": 2, "shapes": [1, 2, 4], "axis": "vertical"}])
        after = self.slide(2)["shapes"]
        boxes = sorted((after[index]["box"] for index in (1, 2, 4)), key=lambda box: box["y"])
        gaps = [second["y"] - (first["y"] + first["h"]) for first, second in zip(boxes, boxes[1:])]
        self.assertLessEqual(abs(gaps[0] - gaps[1]), 1)
        self.assertEqual((boxes[0]["y"], boxes[-1]["y"] + boxes[-1]["h"]), (before[1]["box"]["y"], before[4]["box"]["y"] + before[4]["box"]["h"]))
        self.assertEqual([after[index]["box"]["x"] for index in (1, 2, 4)], [before[index]["box"]["x"] for index in (1, 2, 4)])

    def test_one_shape_cannot_be_distributed_against_itself(self):
        envelope = self.apply([{"op": "distribute_shapes", "slide": 2, "shapes": [1], "axis": "horizontal"}])
        self.assertEqual(codes(envelope), ["INVALID_VALUE"])
        self.assertIn('"to": "slide"', envelope["issues"][0]["suggestion"])

    def test_grouping_then_ungrouping_keeps_every_box(self):
        before = self.slide(2)["shapes"]
        envelope = self.apply([{"op": "group_shapes", "slide": 2, "shapes": [1, 2]}])
        self.assertEqual(envelope["status"], "ok", envelope)
        grouped = self.slide(2)["shapes"]
        group = next(shape for shape in grouped if shape["kind"] == "group")
        self.assertEqual([child["box"] for child in group["shapes"]], [before[1]["box"], before[2]["box"]])
        self.assertEqual(group["box"], {"x": 609600, "y": 1828800, "w": 3352800, "h": 1371600})
        self.apply([{"op": "ungroup_shape", "slide": 2, "shape": group["index"]}])
        self.assertEqual([shape["box"] for shape in self.slide(2)["shapes"]], [shape["box"] for shape in before])

    def test_a_placeholder_is_not_grouped(self):
        envelope = self.apply([{"op": "group_shapes", "slide": 2, "shapes": [0, 1]}])
        self.assertEqual(codes(envelope), ["OPERATION_NOT_APPLICABLE"])

    def test_crop_changes_only_the_sides_given_and_refuses_cropping_everything(self):
        self.apply([{"op": "crop_picture", "slide": 2, "shape": 4, "left": 0.2, "bottom": 0.05}])
        crop = self.slide(2, "--detail")["shapes"][4]["picture"]["crop"]
        self.assertEqual(crop, {"left": 0.2, "top": 0.0, "right": 0.1, "bottom": 0.05})
        envelope = self.apply([{"op": "crop_picture", "slide": 2, "shape": 4, "left": 0.95}])
        self.assertEqual(codes(envelope), ["INVALID_VALUE"])


class LinkTest(KoreanDeckFixture):
    def test_a_shape_links_to_a_web_address_or_to_a_slide(self):
        self.apply([
            {"op": "set_link", "slide": 2, "shape": 1, "url": "https://example.com/q3"},
            {"op": "set_link", "slide": 2, "shape": 4, "toSlide": 5},
        ])
        shapes = self.slide(2)["shapes"]
        self.assertEqual((shapes[1]["link"], shapes[4]["link"]), ("https://example.com/q3", "slide 5"))
        self.apply([{"op": "set_link", "slide": 2, "shape": 1, "url": ""}])
        self.assertNotIn("link", self.slide(2)["shapes"][1])

    def test_only_the_named_text_becomes_a_link_and_the_text_stays_whole(self):
        envelope = self.apply([{"op": "set_link", "slide": 2, "shape": 3, "text": "42곳", "url": "mailto:team@example.com"}])
        self.assertEqual(envelope["status"], "ok", envelope)
        body = self.slide(2, "--detail")["shapes"][3]
        self.assertEqual(body["text"], "신규 고객 42곳 확보\n재구매율 68%로 상승")
        runs = body["paragraphs"][0]["runs"]
        self.assertEqual([(run["text"], run.get("link")) for run in runs], [("신규 고객 ", None), ("42곳", "mailto:team@example.com"), (" 확보", None)])
        self.assertEqual({run["size"]["value"] for run in runs}, {20.0})

    def test_text_that_is_not_in_the_shape_is_named(self):
        envelope = self.apply([{"op": "set_link", "slide": 2, "shape": 3, "text": "없는 글", "url": "https://example.com"}])
        self.assertEqual(codes(envelope), ["TARGET_NOT_FOUND"])

    def test_url_and_slide_together_are_refused(self):
        envelope = self.apply([{"op": "set_link", "slide": 2, "shape": 1, "url": "https://example.com", "toSlide": 3}])
        self.assertEqual(codes(envelope), ["INVALID_VALUE"])


class ShowTest(KoreanDeckFixture):
    def test_transitions_are_set_for_every_slide_and_removed_for_one(self):
        self.apply([{"op": "set_transition", "kind": "fade", "speed": "slow", "advanceAfter": 5}, {"op": "set_transition", "slide": 2, "kind": "none"}])
        slides = self.read()["slides"]
        self.assertEqual(slides[2]["transition"], {"kind": "fade", "speed": "slow", "advanceAfter": 5.0})
        self.assertNotIn("transition", slides[1])
        root = slide_xml(self.directory / "deck.pptx", 5)
        self.assertEqual([etree.QName(child).localname for child in root], ["cSld", "clrMapOvr", "transition", "extLst"])

    def test_entrance_animations_follow_the_powerpoint_timeline(self):
        label, body = (self.slide(2)["shapes"][index]["id"] for index in (2, 3))
        envelope = self.apply([
            {"op": "add_animation", "slide": 2, "shape": 2, "effect": "fade"},
            {"op": "add_animation", "slide": 2, "shape": 3, "effect": "fly_in", "start": "after_previous", "direction": "from_left", "duration": 0.8},
        ])
        self.assertEqual(envelope["status"], "ok", envelope)
        timing = slide_xml(self.directory / "deck.pptx", 2).find(f"{P}timing")
        effects = [node for node in timing.iter(f"{P}cTn") if node.get("presetClass") == "entr"]
        self.assertEqual([(node.get("presetID"), node.get("nodeType")) for node in effects], [("10", "clickEffect"), ("2", "afterEffect")])
        steps = timing.findall(f".//{P}cTn[@nodeType='mainSeq']/{P}childTnLst/{P}par/{P}cTn/{P}childTnLst/{P}par")
        self.assertEqual([step.find(f"{P}cTn/{P}stCondLst/{P}cond").get("delay") for step in steps], ["0", "500"])
        self.assertEqual(list(dict.fromkeys(target.get("spid") for target in timing.iter(f"{P}spTgt"))), [str(label), str(body)])
        identifiers = [node.get("id") for node in timing.iter(f"{P}cTn")]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(self.slide(2, "--detail")["animated"], sorted([str(label), str(body)]))

    def test_animations_can_be_removed_for_a_whole_slide(self):
        self.apply([{"op": "remove_animations", "slide": 4}])
        self.assertIsNone(slide_xml(self.directory / "deck.pptx", 4).find(f"{P}timing"))

    def test_an_added_animation_joins_an_existing_timeline(self):
        self.apply([{"op": "add_animation", "slide": 4, "shape": 1, "effect": "zoom", "start": "with_previous"}])
        timing = slide_xml(self.directory / "deck.pptx", 4).find(f"{P}timing")
        effects = [node for node in timing.iter(f"{P}cTn") if node.get("presetClass") == "entr"]
        self.assertEqual([node.get("nodeType") for node in effects], ["clickEffect", "withEffect"])
        self.assertEqual(len(timing.findall(f".//{P}cTn[@nodeType='mainSeq']/{P}childTnLst/{P}par")), 1)


class CommentTest(KoreanDeckFixture):
    def test_comments_are_written_per_slide_with_their_authors(self):
        envelope = self.apply([
            {"op": "add_comment", "slide": 2, "text": "매출 단위를 확인해 주세요", "author": "박예시"},
            {"op": "add_comment", "slide": 2, "text": "그림 출처를 적어 주세요", "x": "50%", "y": "1in"},
            {"op": "add_comment", "slide": 3, "text": "축 제목이 필요합니다", "author": "박예시"},
        ])
        self.assertEqual(envelope["status"], "ok", envelope)
        slides = self.read()["slides"]
        self.assertEqual(slides[1]["comments"], [{"author": "박예시", "text": "매출 단위를 확인해 주세요"}, {"author": "InternKim", "text": "그림 출처를 적어 주세요"}])
        self.assertEqual(slides[2]["comments"], [{"author": "박예시", "text": "축 제목이 필요합니다"}])
        with zipfile.ZipFile(self.directory / "deck.pptx") as archive:
            authors = etree.fromstring(archive.read("ppt/commentAuthors.xml"))
            types = archive.read("[Content_Types].xml").decode()
        self.assertEqual([(author.get("name"), author.get("lastIdx")) for author in authors], [("박예시", "2"), ("InternKim", "1")])
        self.assertIn("presentationml.comments+xml", types)

    def test_a_comment_rewrites_no_other_slide(self):
        self.apply([{"op": "add_comment", "slide": 2, "text": "확인"}], "--output", "edited.pptx")
        before, after = part_contents(self.directory / "deck.pptx"), part_contents(self.directory / "edited.pptx")
        for name in ("ppt/slides/slide1.xml", "ppt/slides/slide2.xml", "ppt/slides/slide3.xml"):
            self.assertEqual(before[name], after[name], name)


class FooterTest(KoreanDeckFixture):
    def test_footer_and_slide_numbers_follow_the_layout_placeholders(self):
        envelope = self.apply([{"op": "set_header_footer", "footer": "주식회사 예시", "slideNumber": True}])
        self.assertEqual(envelope["status"], "ok", envelope)
        shapes = self.slide(3)["shapes"]
        by_type = {shape.get("placeholder"): shape for shape in shapes}
        self.assertEqual((by_type["ftr"]["text"], by_type["sldNum"]["text"]), ("주식회사 예시", "3"))
        self.assertNotIn("dt", by_type)
        self.apply([{"op": "set_header_footer", "slide": 3, "footer": ""}])
        self.assertNotIn("ftr", {shape.get("placeholder") for shape in self.slide(3)["shapes"]})
        self.assertIn("ftr", {shape.get("placeholder") for shape in self.slide(2)["shapes"]})

    def test_a_deck_without_footer_placeholders_gets_them_at_the_bottom(self):
        directory = Path(self.directory)
        layers = directory / "review" / "pptx-layers"
        layers.mkdir(parents=True)
        (layers / "layout.json").write_text(json.dumps({"language": "ko", "slides": [{"width": 1600, "height": 900, "visibleText": "", "pictureTexts": [], "blocks": [], "shapes": [], "boxesKeptAsPicture": 0}]}), encoding="utf-8")
        write_png(layers / "background.001.png", 32, 18, [[(255, 255, 255, 255)] * 32 for _ in range(18)])
        write_editable_pptx(read_text_layers(directory / "review", 1), [""], directory / "built.pptx")
        (directory / "ops.json").write_text(json.dumps([{"op": "set_header_footer", "slideNumber": True, "date": "2026년 10월"}]), encoding="utf-8")
        envelope = run_office(["apply", "built.pptx", "ops.json"], directory)
        self.assertEqual(envelope["status"], "ok", envelope)
        shapes = self.read(name="built.pptx")["slides"][0]["shapes"]
        numbers = next(shape for shape in shapes if shape.get("placeholder") == "sldNum")
        self.assertEqual(numbers["text"], "1")
        self.assertGreater(numbers["box"]["y"], 6858000 * 0.9)


class SectionTest(KoreanDeckFixture):
    def test_sections_are_added_renamed_filled_and_removed(self):
        self.assertEqual(self.read()["sections"], [{"name": "도입", "slides": [1, 2]}, {"name": "본론", "slides": [3, 4, 5]}])
        self.apply([{"op": "add_section", "slide": 4, "name": "부록"}, {"op": "rename_section", "section": "본론", "name": "성과"}])
        self.assertEqual(self.read()["sections"], [{"name": "도입", "slides": [1, 2]}, {"name": "성과", "slides": [3]}, {"name": "부록", "slides": [4, 5]}])
        closing_title = self.slide(5)["shapes"][0]["text"]
        self.apply([{"op": "move_to_section", "slides": [5], "section": "도입"}])
        details = self.read()
        self.assertEqual(details["sections"], [{"name": "도입", "slides": [1, 2, 3]}, {"name": "성과", "slides": [4]}, {"name": "부록", "slides": [5]}])
        self.assertEqual(details["slides"][2]["shapes"][0]["text"], closing_title)
        self.apply([{"op": "remove_section", "section": "성과"}])
        self.assertEqual(self.read()["sections"], [{"name": "도입", "slides": [1, 2, 3, 4]}, {"name": "부록", "slides": [5]}])

    def test_an_unknown_section_name_suggests_the_close_one(self):
        envelope = self.apply([{"op": "rename_section", "section": "본론 ", "name": "성과"}])
        self.assertEqual(codes(envelope), ["TARGET_NOT_FOUND"])

    def test_a_deck_without_sections_gets_a_default_section_before_the_first_named_one(self):
        self.apply([{"op": "remove_section", "section": "도입"}, {"op": "remove_section", "section": "본론"}])
        self.assertNotIn("sections", self.read())
        self.apply([{"op": "add_section", "slide": 3, "name": "본론"}])
        self.assertEqual(self.read()["sections"], [{"name": "Default Section", "slides": [1, 2]}, {"name": "본론", "slides": [3, 4, 5]}])

    def test_a_first_section_at_the_first_slide_leaves_no_empty_default(self):
        self.apply([{"op": "remove_section", "section": "도입"}, {"op": "remove_section", "section": "본론"}])
        self.apply([{"op": "add_section", "slide": 1, "name": "도입"}, {"op": "add_section", "slide": 4, "name": "부록"}])
        self.assertEqual(self.read()["sections"], [{"name": "도입", "slides": [1, 2, 3]}, {"name": "부록", "slides": [4, 5]}])


if __name__ == "__main__":
    unittest.main()
