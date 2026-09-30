import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "office" / "scripts"
OFFICE_ENTRY = SCRIPTS_PATH / "office"

FIXTURE_DOCUMENT = """
from docx import Document
document = Document()
document.add_heading("개요", 1)
document.add_paragraph("첫 문단 {{ customer_name }} 입니다.")
document.add_paragraph("둘째 문단")
table = document.add_table(rows=2, cols=2)
for row, values in zip(table.rows, [["항목", "값"], ["매출", "100"]]):
    for cell, value in zip(row.cells, values):
        cell.text = value
document.add_heading("결론", 1)
document.save("fixture.docx")
"""


def run_office(arguments, working_directory):
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *arguments], capture_output=True, text=True, cwd=working_directory)
    return json.loads(completed.stdout)


def run_office_python(code, working_directory):
    subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", textwrap.dedent(code)], check=True, cwd=working_directory)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def block_texts(working_directory, document_name):
    envelope = run_office(["doc", "read", document_name], working_directory)
    return [(block["kind"], block.get("text", block.get("cells"))) for block in envelope["details"]["blocks"]]


class DocumentFixture(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        run_office_python(FIXTURE_DOCUMENT, self.directory)

    def tearDown(self):
        self.temporary_directory.cleanup()
