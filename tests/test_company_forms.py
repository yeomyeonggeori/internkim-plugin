import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from doc_fixture import OFFICE_ENTRY, run_office, run_office_python, write_json


FORM_DOCUMENT = """
from docx import Document
document = Document()
approval = document.add_table(rows=2, cols=3)
for cell, text in zip(approval.rows[0].cells, ["담당", "팀장", "대표"]):
    cell.text = text
header = document.add_table(rows=2, cols=4)
for row, texts in zip(header.rows, [["문서번호", "", "작성일", ""], ["거래처", "", "작성자", ""]]):
    for cell, text in zip(row.cells, texts):
        cell.text = text
document.add_paragraph("품목")
items = document.add_table(rows=5, cols=5)
for cell, text in zip(items.rows[0].cells, ["No", "품명", "수량", "단가", "금액"]):
    cell.text = text
for number, row in enumerate(items.rows[1:4], start=1):
    row.cells[0].text = str(number)
total = items.rows[4].cells
total[0].merge(total[3]).text = "합계"
document.save("form.docx")
"""

FORM_WORKBOOK = """
from openpyxl import Workbook
workbook = Workbook()
sheet = workbook.active
sheet.title = "Plan"
sheet["A1"], sheet["C1"] = "Project", "Owner"
sheet.append([])
sheet.append(["No", "Name", "Months", "Rate", "Cost"])
for number in range(1, 4):
    sheet.append([number, None, None, None, f"=C{number + 3}*D{number + 3}"])
sheet.append(["Total", None, None, None, "=SUM(E4:E6)"])
workbook.save("form.xlsx")
"""


def runtime_context(directory):
    path = Path(directory, "context.json")
    write_json(path, {"requester": {"name": "이샘플"}, "today": "2026-10-04", "company": {"ko": {"name": "샘플테크"}}, "registeredDocuments": [{"documentNumber": "SAMPLE-7"}]})
    return path


def merge(directory, schema, values, output):
    write_json(Path(directory, "values.json"), values)
    environment = dict(os.environ, OFFICE_RUNTIME_CONTEXT=str(runtime_context(directory)))
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "merge", schema, "values.json", output], capture_output=True, text=True, cwd=directory, env=environment)
    return json.loads(completed.stdout)


def typed(schema_path, changes):
    schema = json.loads(Path(schema_path).read_text())
    for field in schema["fields"]:
        field.update(changes.get(field["name"], {}))
        for child in field.get("fields") or []:
            child.update(changes.get(f"{field['name']}.{child['name']}", {}))
    Path(schema_path).write_text(json.dumps(schema, ensure_ascii=False))
    return schema


class DocxFormTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        run_office_python(FORM_DOCUMENT, self.directory.name)

    def derive(self):
        result = run_office(["convert", "form.docx", "form.schema.json"], self.directory.name)
        self.assertEqual(result["status"], "ok", result)
        return json.loads(Path(self.directory.name, "form.schema.json").read_text())

    def test_every_empty_cell_beside_or_under_a_label_becomes_a_field(self):
        names = [field["name"] for field in self.derive()["fields"]]
        self.assertEqual(names, ["담당", "팀장", "대표", "문서번호", "작성일", "거래처", "작성자", "품목", "합계"])

    def test_a_table_of_empty_numbered_rows_becomes_a_list_named_by_the_text_above_it(self):
        items = next(field for field in self.derive()["fields"] if field["type"] == "list")
        self.assertEqual(items["label"], "품목")
        self.assertEqual([child["name"] for child in items["fields"]], ["품명", "수량", "단가", "금액"])
        self.assertEqual(items["at"]["rows"], 3)

    def test_the_filled_form_keeps_its_layout_and_writes_only_its_cells(self):
        self.derive()
        typed(Path(self.directory.name, "form.schema.json"), {
            "담당": {"type": "handwritten"}, "팀장": {"type": "handwritten"}, "대표": {"type": "handwritten"},
            "문서번호": {"known": "document.number"}, "작성일": {"known": "today"}, "작성자": {"known": "requester"},
            "품목.수량": {"type": "quantity"}, "품목.단가": {"type": "amount", "unit": "KRW"},
            "품목.금액": {"type": "amount", "unit": "KRW", "expression": "품목.수량 * 품목.단가"},
            "합계": {"type": "amount", "unit": "KRW", "expression": "sum(품목.금액)"},
        })
        values = {"거래처": None, "품목": [{"품명": "의자", "수량": 2, "단가": 50000}, {"품명": "책상", "수량": 1, "단가": 120000}]}
        result = merge(self.directory.name, "form.schema.json", values, "filled.docx")
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual([blank["label"] for blank in result["details"]["blanks"]], ["거래처"])
        tables = run_office(["read", "filled.docx"], self.directory.name)["details"]["blocks"]
        cells = [block["cells"] for block in tables if block["kind"] == "table"]
        self.assertEqual(cells[0][1], ["", "", ""])
        self.assertEqual(cells[1], [["문서번호", "SAMPLE-7", "작성일", "2026년 10월 4일"], ["거래처", "", "작성자", "이샘플"]])
        self.assertEqual(cells[2][1], ["1", "의자", "2", "50,000원", "100,000원"])
        self.assertEqual(cells[2][4][-1], "220,000원")


class XlsxFormTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        run_office_python(FORM_WORKBOOK, self.directory.name)

    def test_a_column_the_form_computes_stays_its_own_formula(self):
        run_office(["convert", "form.xlsx", "form.schema.json"], self.directory.name)
        schema = json.loads(Path(self.directory.name, "form.schema.json").read_text())
        plan = next(field for field in schema["fields"] if field["type"] == "list")
        self.assertEqual({child["name"]: child["type"] for child in plan["fields"]}, {"Name": "text", "Months": "text", "Rate": "text", "Cost": "ignore"})
        typed(Path(self.directory.name, "form.schema.json"), {"Name.Months": {"type": "quantity"}, f"{plan['name']}.Months": {"type": "quantity"}, f"{plan['name']}.Rate": {"type": "amount"}})
        values = {"Project": "Pilot", "Owner": None, plan["name"]: [{"Name": "박예시", "Months": 2, "Rate": 100}]}
        result = merge(self.directory.name, "form.schema.json", values, "filled.xlsx")
        self.assertEqual(result["status"], "ok", result)
        cells = run_office(["read", "filled.xlsx", "--range", "A1:E7", "--where", "formula"], self.directory.name)["details"]["range"]["cells"]
        self.assertEqual({cell["cell"]: cell["value"] for cell in cells}["E4"], 200)
        rows = run_office(["read", "filled.xlsx", "--range", "A1:E4"], self.directory.name)["details"]["range"]["values"]
        self.assertEqual(rows[0][1], "Pilot")
        self.assertEqual(rows[3][:4], [1, "박예시", 2, 100])


if __name__ == "__main__":
    unittest.main()
