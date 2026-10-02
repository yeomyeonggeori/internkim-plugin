import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

from render_fixture import can_render


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"
KIT_PATH = SCRIPTS_PATH.parent / "assets" / "deck-kit"
sys.path.insert(0, str(SCRIPTS_PATH))

from deck.check_deck import CheckRequest, check_deck  # noqa: E402
from deck.deck_kit import icon_names, inject_deck_kit, theme_palettes  # noqa: E402


CONTAINMENT_TOLERANCE = 1
ICON_DECK = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>아이콘 표본</title></head>
<body data-theme="corporate">
<section data-layout="cover"><h1>아이콘이 슬라이드에 리듬을 줍니다</h1><p class="meta">박예시 · 2026년 10월</p></section>
<section data-layout="agenda"><h2>세 가지를 말씀드립니다</h2><ol><li data-icon="search">문제</li><li data-icon="calendar">일정</li><li data-icon="users">사람</li></ol></section>
<section data-layout="kpi"><h2>지표가 모두 올랐습니다</h2>
  <div class="kpi" data-icon="users"><p class="value">4.2만</p><p class="label">관심 등록</p><p class="up">+40%</p></div>
  <div class="kpi" data-icon="percent"><p class="value">31%</p><p class="label">구매 전환</p><p class="up">+9%p</p></div></section>
<section data-layout="cards"><h2>네 가지 위험에 대비합니다</h2>
  <div class="card" data-icon="package"><p class="label">공급</p><h3>부품 단일 공급</h3><p>두 번째 공급사를 찾습니다.</p></div>
  <div class="card" data-icon="trending-down"><p class="label">가격</p><h3>할인 경쟁</h3><p>전용 색상으로 지킵니다.</p></div>
  <div class="card" data-icon="shield-check"><p class="label">품질</p><h3>초기 불량</h3><p>전수 검사를 합니다.</p></div>
  <div class="card" data-icon="truck"><p class="label">물류</p><h3>배송 지연</h3><p>재고를 나눕니다.</p></div></section>
<section data-layout="timeline"><h2>세 단계로 출시합니다</h2>
  <div class="step" data-icon="factory"><p class="label">1월</p><h3>양산</h3><p>첫 물량을 만듭니다.</p></div>
  <div class="step" data-icon="megaphone"><p class="label">2월</p><h3>사전 판매</h3><p>회원에게 먼저 엽니다.</p></div>
  <div class="step" data-icon="rocket"><p class="label">3월</p><h3>출시</h3><p>모든 채널에 엽니다.</p></div></section>
<section data-layout="closing"><h2>두 가지를 승인해 주십시오</h2><ol><li data-icon="banknote">예산 4억 원</li><li data-icon="calendar-check">3월 2일 출시</li></ol></section>
</body>
</html>
"""
CHECKED_DECK = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>점검</title></head>
<body data-theme="corporate">
<section data-layout="cover"><h1>아이콘을 점검합니다</h1></section>
<section data-layout="cards"><h2 data-icon="users">두 가지입니다</h2>
  <div class="card" data-icon="usres"><h3>첫째</h3><p>설명</p></div>
  <div class="card" data-icon="users"><h3>둘째</h3><p>설명</p></div></section>
<section data-layout="closing"><h2>승인해 주십시오</h2><ol><li data-icon="banknote">예산</li></ol></section>
</body></html>"""


def build(deck_path: Path, source: str) -> dict:
    deck_path.mkdir()
    (deck_path / "slides.html").write_text(source, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "create", f"build/{Path(deck_path).name}.pptx", "slides.html"], capture_output=True, text=True, cwd=deck_path)
    return json.loads(completed.stdout)


def block_text(block: dict) -> str:
    return "".join("".join(run["text"] for paragraph in block["paragraphs"] for run in paragraph["runs"]).split())


def contains(outer: dict, inner: dict) -> bool:
    return all(
        (inner[side] >= outer[side] - CONTAINMENT_TOLERANCE) if side in ("left", "top") else (inner[side] <= outer[side] + CONTAINMENT_TOLERANCE)
        for side in ("left", "top", "right", "bottom")
    )


def kit_constant(name: str) -> str:
    return re.search(rf"const {name} = (.+?);", (KIT_PATH / "deck-kit.js").read_text(encoding="utf-8")).group(1)


def renderer_constant(file_name: str, name: str) -> str:
    return re.search(rf"const {name} = (.+?);", (SCRIPTS_PATH / "render" / file_name).read_text(encoding="utf-8")).group(1)


class IconSourceTest(unittest.TestCase):
    def check_issues(self, source: str) -> list:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "slides.html"
            path.write_text(source, encoding="utf-8")
            return list(check_deck(CheckRequest(path)).issues)

    def test_an_unknown_icon_is_refused_with_the_nearest_name(self):
        unknown = [issue for issue in self.check_issues(CHECKED_DECK) if issue.kind.code == "ICON_UNKNOWN"]
        self.assertEqual(len(unknown), 1, unknown)
        self.assertEqual(unknown[0].kind.severity, "error")
        self.assertIn("did you mean 'users'", unknown[0].suggestion)

    def test_an_icon_on_a_part_the_kit_draws_none_for_is_refused(self):
        misplaced = [issue for issue in self.check_issues(CHECKED_DECK) if issue.kind.code == "ICON_MISPLACED"]
        self.assertEqual(len(misplaced), 1, misplaced)
        self.assertIn("<h2>", misplaced[0].message)

    def test_icons_on_their_hosts_pass_the_check(self):
        self.assertEqual([issue.kind.code for issue in self.check_issues(ICON_DECK) if issue.kind.code.startswith("ICON_")], [])

    def test_the_guide_lists_every_bundled_icon(self):
        guide = subprocess.run([sys.executable, str(OFFICE_ENTRY), "guide", "slides"], capture_output=True, text=True).stdout
        names_line = next(line for line in guide.splitlines() if line.strip().startswith("names: "))
        self.assertEqual(names_line.strip().removeprefix("names: ").split(", "), list(icon_names()))

    def test_a_deck_carries_only_the_icons_it_names(self):
        injected = inject_deck_kit(ICON_DECK)
        carried = set(re.findall(r'"([a-z0-9-]+)": "<svg', injected))
        self.assertEqual(carried, set(re.findall(r'data-icon="([^"]+)"', ICON_DECK)))

    def test_the_bundled_icons_ship_with_their_license(self):
        license_text = (KIT_PATH / "icons" / "LICENSE.txt").read_text(encoding="utf-8")
        self.assertIn("ISC License", license_text)
        self.assertIn("MIT License", license_text)

    def test_the_renderer_exports_the_icons_the_kit_marks(self):
        self.assertEqual(kit_constant("nativeIconAttribute"), renderer_constant("native_icons.mjs", "nativeIconAttribute"))


@unittest.skipUnless(can_render(), "needs bun, or node 18 or newer")
class IconBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        deck_path = Path(cls.directory.name) / "icons"
        cls.envelope = build(deck_path, ICON_DECK)
        cls.pptx_path = deck_path / "build" / "icons.pptx"
        cls.layout = json.loads((deck_path / "build" / "review" / "pptx-layers" / "layout.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_every_icon_host_gets_its_icon_as_a_picture(self):
        named = re.findall(r'data-icon="([^"]+)"', ICON_DECK)
        drawn = [icon["name"] for slide in self.layout["slides"] for icon in slide.get("icons", [])]
        self.assertEqual(drawn, named)
        self.assertEqual(self.envelope["details"]["pptx"]["icons"], len(named))
        self.assertTrue(self.envelope["details"]["acceptance"]["acceptable"], self.envelope["summary"])

    def test_an_icon_sits_inside_its_card(self):
        slide = self.layout["slides"][3]
        cards = [shape["box"] for shape in slide["shapes"] if shape.get("fill")]
        for icon in slide["icons"]:
            self.assertTrue(any(contains(card, icon["box"]) for card in cards), (icon, cards))

    def test_an_icon_takes_the_place_of_a_list_number(self):
        for slide_index in (1, 5):
            numerals = [text for text in map(block_text, self.layout["slides"][slide_index]["blocks"]) if text.isdigit()]
            self.assertEqual(numerals, [f"{slide_index + 1:02d}"])

    def test_the_pptx_carries_each_icon_as_a_vector_picture_in_the_accent(self):
        accent = theme_palettes()["corporate"]["accent"]
        with zipfile.ZipFile(self.pptx_path) as archive:
            names = archive.namelist()
            vectors = [name for name in names if name.startswith("ppt/media/icon") and name.endswith(".svg")]
            card_slide = archive.read("ppt/slides/slide4.xml").decode("utf-8")
            content_types = archive.read("[Content_Types].xml").decode("utf-8")
            strokes = {archive.read(name).decode("utf-8").count(f'stroke="{accent}"') for name in vectors if name.startswith("ppt/media/icon4_")}
        self.assertEqual(len(vectors), len(re.findall(r'data-icon="', ICON_DECK)))
        self.assertEqual(card_slide.count("svgBlip"), 4)
        self.assertIn('Extension="svg"', content_types)
        self.assertEqual(strokes, {1})

    def test_a_built_deck_with_icons_passes_the_pptx_check(self):
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "check", str(self.pptx_path)], capture_output=True, text=True)
        self.assertEqual(json.loads(completed.stdout)["issues"], [])


if __name__ == "__main__":
    unittest.main()
