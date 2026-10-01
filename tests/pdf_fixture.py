from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"))

from fonts.registry import BOLD_WEIGHT, DECK, REGULAR_WEIGHT, default_family  # noqa: E402

PAPERLOGY = default_family(DECK)
REGULAR_FONT = PAPERLOGY.path(PAPERLOGY.face(REGULAR_WEIGHT))
BOLD_FONT = PAPERLOGY.path(PAPERLOGY.face(BOLD_WEIGHT))


def with_fonts(code):
    return code.replace("{regular!r}", repr(str(REGULAR_FONT))).replace("{bold!r}", repr(str(BOLD_FONT)))


NEWSLETTER_PDF = """
from fpdf import FPDF
from PIL import Image, ImageDraw
pdf = FPDF(format="A4")
pdf.set_auto_page_break(False)
pdf.add_font("Korean", "", {regular!r})
pdf.add_font("Korean", "B", {bold!r})
left_column = [
    "올해 하반기 사내 교육은 직무 역량과 리더십 두 축으로 운영한다. 교육 일정은 부서별 수요 조사를 반영해 확정했다.",
    "직무 교육은 매월 둘째 주 화요일에 열리며 사전 신청자에 한해 수료증을 발급한다.",
]
right_column = [
    "리더십 과정은 팀장급을 대상으로 하며 외부 강사를 초빙한다. 과정별 정원은 20명이다.",
    "교육 만족도 조사는 과정 종료 후 일주일 이내에 진행하고 결과는 다음 분기 계획에 반영한다.",
]

def furniture(number):
    pdf.set_font("Korean", "", 8)
    pdf.set_xy(15, 8)
    pdf.cell(180, 5, "주식회사 예시상사 사내 소식", align="R")
    pdf.set_xy(15, 285)
    pdf.cell(180, 5, f"- {number} -", align="C")

def paragraphs(texts, x):
    y = pdf.get_y()
    for text in texts:
        pdf.set_xy(x, y)
        pdf.multi_cell(85, 6, text)
        y = pdf.get_y() + 4

pdf.add_page()
furniture(1)
pdf.set_font("Korean", "B", 20)
pdf.set_xy(15, 20)
pdf.cell(180, 12, "2026년 하반기 교육 안내")
pdf.set_font("Korean", "B", 14)
pdf.set_xy(15, 38)
pdf.cell(180, 8, "1. 교육 운영 방향")
pdf.set_font("Korean", "", 10)
pdf.set_y(52)
paragraphs(left_column, 15)
pdf.set_y(52)
paragraphs(right_column, 110)

pdf.add_page()
furniture(2)
pdf.set_font("Korean", "B", 14)
pdf.set_xy(15, 20)
pdf.cell(180, 8, "2. 과정별 일정")
pdf.set_font("Korean", "", 10)
pdf.set_xy(15, 32)
with pdf.table(col_widths=(60, 60, 60)) as table:
    for row in (("과정", "일정", "정원"), ("직무 기초", "9월 9일", "30명"), ("리더십", "10월 14일", "20명")):
        cells = table.row()
        for value in row:
            cells.cell(value)
pdf.set_y(pdf.get_y() + 8)
for item in ("신청은 사내 포털에서 받는다.", "취소는 교육 3일 전까지 가능하다."):
    pdf.set_x(20)
    pdf.cell(170, 7, f"• {item}", new_x="LMARGIN", new_y="NEXT")

image = Image.new("RGB", (1240, 1754), "white")
ImageDraw.Draw(image).rectangle([200, 300, 1040, 700], fill=(200, 200, 200))
image.save("scan.png")
pdf.add_page()
pdf.image("scan.png", x=0, y=0, w=210, h=297)
pdf.output("newsletter.pdf")
"""


def newsletter_pdf_code():
    return with_fonts(NEWSLETTER_PDF)


STATEMENT_PDF = """
from fpdf import FPDF
pdf = FPDF(format="A4")
pdf.add_font("Korean", "", {regular!r})
pdf.add_font("Korean", "B", {bold!r})
pdf.add_page()
pdf.set_font("Korean", "B", 16)
pdf.text(20, 25, "2026년 9월 거래 명세서")
pdf.set_font("Korean", "", 10)
pdf.text(20, 35, "공급받는 자: 주식회사 예시상사 (담당 박예시)")
pdf.text(20, 41, "아래와 같이 9월 한 달 동안의 거래 내역을 알려 드립니다. 금액은 부가세를 포함합니다.")
columns = ((20, "L"), (48, "L"), (120, "R"), (145, "R"), (185, "R"))
rows = (
    ("일자", "품목", "수량", "단가", "금액"),
    ("2026-09-02", "사무용 의자", "12", "120,000", "1,440,000"),
    ("2026-09-09", "모니터 받침대", "30", "18,000", "540,000"),
    ("2026-09-16", "A4 복사 용지 (박스)", "45", "26,500", "1,192,500"),
    ("2026-09-23", "무선 키보드", "8", "54,000", "432,000"),
    ("2026-09-30", "회의실 화이트보드", "2", "210,000", "420,000"),
)

def place(x, align, y, value):
    pdf.text(x - pdf.get_string_width(value) if align == "R" else x, y, value)

y = 55
for row in rows:
    pdf.set_font("Korean", "B" if row is rows[0] else "", 10)
    for (x, align), value in zip(columns, row):
        place(x, align, y, value)
    y += 8
pdf.set_font("Korean", "B", 10)
place(20, "L", y + 2, "합계")
place(185, "R", y + 2, "4,024,500")
pdf.set_font("Korean", "", 10)
pdf.text(20, y + 16, "문의는 sample@example.com 으로 보내 주십시오. 담당자 이샘플.")
pdf.output("statement.pdf")
"""
STATEMENT_ROWS = [
    ["일자", "품목", "수량", "단가", "금액"],
    ["2026-09-02", "사무용 의자", "12", "120,000", "1,440,000"],
    ["2026-09-09", "모니터 받침대", "30", "18,000", "540,000"],
    ["2026-09-16", "A4 복사 용지 (박스)", "45", "26,500", "1,192,500"],
    ["2026-09-23", "무선 키보드", "8", "54,000", "432,000"],
    ["2026-09-30", "회의실 화이트보드", "2", "210,000", "420,000"],
    ["합계", "", "", "", "4,024,500"],
]


def statement_pdf_code():
    return with_fonts(STATEMENT_PDF)


SCANNED_STATEMENT_PDF = """
import pypdfium2
from fpdf import FPDF
image = pypdfium2.PdfDocument("statement.pdf")[0].render(scale=200 / 72, grayscale=True).to_pil()
image.save("statement-scan.png")
pdf = FPDF(format="A4")
pdf.add_page()
pdf.image("statement-scan.png", x=0, y=0, w=210, h=297)
pdf.output("scanned-statement.pdf")
"""
