from pathlib import Path
import shutil


PDF_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pdf"

STATEMENT_ROWS = [
    ["일자", "품목", "수량", "단가", "금액"],
    ["2026-09-02", "사무용 의자", "12", "120,000", "1,440,000"],
    ["2026-09-09", "모니터 받침대", "30", "18,000", "540,000"],
    ["2026-09-16", "A4 복사 용지 (박스)", "45", "26,500", "1,192,500"],
    ["2026-09-23", "무선 키보드", "8", "54,000", "432,000"],
    ["2026-09-30", "회의실 화이트보드", "2", "210,000", "420,000"],
    ["합계", "", "", "", "4,024,500"],
]

SCANNED_STATEMENT_PDF = """
import pypdfium2
pypdfium2.PdfDocument("statement.pdf")[0].render(scale=200 / 72, grayscale=True).to_pil().save("scanned-statement.pdf", resolution=200)
"""


def copy_pdf_fixture(name: str, directory) -> Path:
    return Path(shutil.copy(PDF_FIXTURES / name, Path(directory) / name))
