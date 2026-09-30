from deck_fixture import DeckFixture, SCRIPTS_PATH, run_office_python_json


NOTES_DECK = """
<section data-slide-role="summary"><h2>매출이 늘었습니다</h2><p>본문</p><aside class="notes">첫 슬라이드 노트
둘째 줄 &amp; 끝</aside></section>
<section data-slide-role="risk"><h2>노트가 없는 슬라이드입니다</h2><p>본문</p></section>
<section data-slide-role="approval"><h2>마지막 슬라이드입니다</h2><p>본문</p><aside class="notes">마지막 노트</aside></section>
"""
EXPECTED_NOTES = ["첫 슬라이드 노트\n둘째 줄 & 끝", None, "마지막 노트"]

WRITE_AND_READ_BACK = """
import json, sys
from pathlib import Path
sys.path[:0] = [{deck_path!r}, {scripts_path!r}]
from image_pptx import write_image_backed_pptx
from native_pptx import write_native_text_pptx
from png_codec import write_png
from pptx import Presentation
from slide_model import create_slide_models
from slide_source import split_slide_sources

models = create_slide_models(split_slide_sources({deck!r}))
image_paths = []
for model in models:
    image_path = Path(f"slide{{model.index}}.png")
    write_png(image_path, 32, 18, [[(255, 255, 255, 255)] * 32 for _ in range(18)])
    image_paths.append(image_path)
write_native_text_pptx(models, {{}}, Path("native.pptx"))
write_image_backed_pptx(image_paths, [model.notes for model in models], Path("image.pptx"))

def notes_of(path):
    return [slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else None for slide in Presentation(path).slides]

print(json.dumps({{"native": notes_of("native.pptx"), "image": notes_of("image.pptx")}}, ensure_ascii=False))
"""


class NotesRoundTripTest(DeckFixture):
    def read_back(self, deck: str):
        code = WRITE_AND_READ_BACK.format(deck_path=str(SCRIPTS_PATH / "deck"), scripts_path=str(SCRIPTS_PATH), deck=deck)
        return run_office_python_json(code, self.directory)

    def test_both_pptx_modes_carry_the_slide_notes_python_pptx_reads_back(self):
        notes = self.read_back(NOTES_DECK)
        self.assertEqual(notes["native"], EXPECTED_NOTES)
        self.assertEqual(notes["image"], EXPECTED_NOTES)

    def test_a_deck_without_notes_gets_no_notes_parts(self):
        notes = self.read_back('<section><h2>노트 없는 덱입니다</h2></section>')
        self.assertEqual(notes, {"native": [None], "image": [None]})
