import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from render_fixture import can_render
from test_deck_check import CLOSING, COVER, kit_deck


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.check_deck import CheckRequest, check_deck  # noqa: E402
from deck.pptx_connectors import facing_route  # noqa: E402
from deck.pptx_geometry import Box  # noqa: E402

PROCESS = '<section data-layout="process"><h2>주문은 네 단계로 처리됩니다</h2><ol><li>주문 접수</li><li>재고 확인</li><li>출고</li><li class="pick">배송 완료</li></ol></section>'
CYCLE = '<section data-layout="cycle"><h2>개선은 네 단계를 반복합니다</h2><ol><li>계획</li><li>실행</li><li>점검</li><li>개선</li></ol></section>'
HIERARCHY = (
    '<section data-layout="hierarchy"><h2>두 본부가 다섯 팀을 이끕니다</h2><ul><li>대표이사<small>이샘플</small><ul>'
    '<li>영업본부<ul><li>수도권팀</li><li>영남팀</li><li>호남팀</li></ul></li><li>운영본부<ul><li>물류팀</li><li>고객지원팀</li></ul></li></ul></li></ul></section>'
)
PYRAMID = '<section data-layout="pyramid"><h2>비전은 세 층의 목표로 이룹니다</h2><ol><li>업계 1위 물류</li><li>당일 출고 95%</li><li>권역 센터 3곳</li></ol></section>'
MATRIX = (
    '<section data-layout="matrix"><h2>효과가 크고 쉬운 일부터 합니다</h2><ul data-y="기대 효과" data-x="실행 난이도">'
    '<li class="pick"><h3>자동 발주</h3><p>바로 시작</p></li><li><h3>센터 신설</h3><p>내년 계획</p></li><li><h3>알림 개선</h3><p>틈틈이</p></li><li><h3>자체 배송</h3><p>보류</p></li></ul></section>'
)
DIAGRAM_DECK = kit_deck(COVER, PROCESS, CYCLE, HIERARCHY, PYRAMID, MATRIX, CLOSING)
EXPECTED_CONNECTORS = {2: 3, 3: 4, 4: 7, 6: 2}


class DiagramSourceTest(unittest.TestCase):
    def check(self, source: str, slides: int | None = None):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "slides.html").write_text(source, encoding="utf-8")
            return check_deck(CheckRequest(Path(directory) / "slides.html", slides, ()))

    def codes(self, source: str) -> list[tuple[str, str | None]]:
        return [(issue.kind.code, issue.location) for issue in self.check(source).issues]

    def test_a_diagram_deck_is_ready_to_build(self):
        self.assertEqual(self.check(DIAGRAM_DECK, slides=7).status, "ok")

    def test_each_diagram_counts_its_items(self):
        two_steps = PROCESS.replace("<li>재고 확인</li><li>출고</li>", "")
        three_quadrants = MATRIX.replace("<li><h3>자체 배송</h3><p>보류</p></li>", "")
        deep_tree = HIERARCHY.replace("<li>수도권팀</li>", "<li>수도권팀<ul><li>강남지점</li></ul></li>")
        self.assertIn(("LAYOUT_PART_MISSING", "slide 2"), self.codes(kit_deck(COVER, two_steps, CLOSING)))
        self.assertIn(("LAYOUT_PART_MISSING", "slide 2"), self.codes(kit_deck(COVER, three_quadrants, CLOSING)))
        deep = self.check(kit_deck(COVER, deep_tree, CLOSING)).issues
        self.assertIn("nests 4 levels", next(issue.message for issue in deep if issue.kind.code == "LAYOUT_PART_EXCESS"))


class DiagramBuildTest(unittest.TestCase):
    @unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
    def test_diagrams_build_into_native_boxes_joined_by_attached_connectors(self):
        with tempfile.TemporaryDirectory() as directory:
            deck_path = Path(directory) / "diagrams"
            deck_path.mkdir()
            (deck_path / "slides.html").write_text(DIAGRAM_DECK, encoding="utf-8")
            envelope = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", f"build/{Path(deck_path).name}.pptx", "slides.html"], capture_output=True, text=True, cwd=deck_path).stdout)
            pptx_path = deck_path / "build" / "diagrams.pptx"
            check = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "check", str(pptx_path)], capture_output=True, text=True).stdout)
            read = json.loads(subprocess.run([sys.executable, str(OFFICE_ENTRY), "read", str(pptx_path)], capture_output=True, text=True).stdout)
            layers = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))
        self.assertTrue(envelope["details"]["acceptance"]["acceptable"], envelope["summary"])
        self.assertEqual([slide["boxesKeptAsPicture"] for slide in layers["slides"][1:6]], [0] * 5)
        self.assertEqual(check["issues"], [])
        for slide in read["details"]["slides"]:
            connectors = [shape for shape in slide["shapes"] if shape["kind"] == "connector" and shape["name"].startswith("Connector")]
            with self.subTest(slide=slide["slide"]):
                self.assertEqual(len(connectors), EXPECTED_CONNECTORS.get(slide["slide"], 0))
                attached = [connector for connector in connectors if connector.get("connects")]
                expected_attached = 0 if slide["slide"] == 6 else len(connectors)
                self.assertEqual(len(attached), expected_attached)
                for connector in attached:
                    self.assertEqual(slide["shapes"][connector["connects"]["from"]]["kind"], "shape")
                    self.assertEqual(slide["shapes"][connector["connects"]["to"]]["kind"], "shape")
        self.assert_cycle_arrows_leave_by_the_sides_deck_apply_would_pick(layers["slides"][2])
        texts = [shape.get("text", "") for slide in read["details"]["slides"] for shape in slide["shapes"]]
        for label in ("수도권팀", "개선", "자동 발주", "권역 센터 3곳", "기대 효과"):
            self.assertTrue(any(re.search(re.escape(label), text) for text in texts), label)


    def assert_cycle_arrows_leave_by_the_sides_deck_apply_would_pick(self, slide: dict):
        boxes = {shape["exportId"]: pixel_box(shape["box"]) for shape in slide["shapes"] if shape.get("exportId") and shape["geometry"] != "line"}
        for connector in slide["connectors"]:
            route = facing_route(boxes[connector["fromShape"]], boxes[connector["toShape"]])
            self.assertEqual(list(route.sides), connector["sides"])


def pixel_box(box: dict) -> Box:
    return Box(round(box["left"]), round(box["top"]), round(box["right"] - box["left"]), round(box["bottom"] - box["top"]))


if __name__ == "__main__":
    unittest.main()
