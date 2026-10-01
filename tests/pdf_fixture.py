NEWSLETTER_PDF = """
FONT_DIRECTORY = {font_directory!r}
from pathlib import Path
from fpdf import FPDF
from PIL import Image, ImageDraw
FONTS = Path(FONT_DIRECTORY)
pdf = FPDF(format="A4")
pdf.set_auto_page_break(False)
pdf.add_font("Korean", "", str(FONTS / "Paperlogy-4Regular.ttf"))
pdf.add_font("Korean", "B", str(FONTS / "Paperlogy-7Bold.ttf"))
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


def newsletter_pdf_code(font_directory):
    return NEWSLETTER_PDF.replace("{font_directory!r}", repr(str(font_directory)))
