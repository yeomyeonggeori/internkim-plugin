import unittest

from openpyxl import load_workbook

from sheet_fixture import WorkbookFixture, run_office_python


STYLED_WORKBOOK = """
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

workbook = Workbook()
sheet = workbook.active
sheet.title = "Sales"
side = Side(style="thin", color="CBD5E1")
for row in [["item", "amount", "share"], ["A", 1000, 0.25], ["B", 2000, 0.5], ["C", 3000, 0.75]]:
    sheet.append(row)
for row in sheet["A3:C3"]:
    for cell in row:
        cell.font = Font(bold=True, color="FF0000")
        cell.fill = PatternFill("solid", fgColor="FFF2CC")
        cell.border = Border(left=side, right=side, top=side, bottom=side)
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
sheet["B3"].number_format = "#,##0"
sheet["C3"].number_format = "0.0%"
for row in range(1, 5):
    sheet.cell(row=row, column=2).fill = PatternFill("solid", fgColor="DDEBF7")
    sheet.cell(row=row, column=2).number_format = "#,##0.00"
workbook.save("fixture.xlsx")
"""


def style_of(cell):
    return (cell.number_format, cell.font.b, cell.font.color.rgb if cell.font.color else None, cell.fill.fgColor.rgb, cell.border.left.style, cell.alignment.horizontal, cell.alignment.wrap_text)


class InsertedCellsTest(WorkbookFixture):
    def setUp(self):
        super().setUp()
        run_office_python(STYLED_WORKBOOK, self.directory)

    def insert(self, operation):
        envelope = self.apply([operation], name="fixture.xlsx")
        self.assertEqual(envelope["status"], "ok", envelope)
        return load_workbook(self.directory / "fixture.xlsx")["Sales"]

    def test_inserted_rows_copy_the_style_of_the_row_above(self):
        sheet = self.insert({"op": "insert_rows", "sheet": "Sales", "at": 4, "count": 2})
        for row in (4, 5):
            for column in "ABC":
                self.assertEqual(style_of(sheet[f"{column}{row}"]), style_of(sheet[f"{column}3"]), f"{column}{row}")
        self.assertEqual(sheet["C5"].number_format, "0.0%")

    def test_inserted_columns_copy_the_style_of_the_column_to_the_left(self):
        sheet = self.insert({"op": "insert_columns", "sheet": "Sales", "at": "C", "count": 2})
        for row in range(1, 5):
            for column in "CD":
                self.assertEqual(style_of(sheet[f"{column}{row}"]), style_of(sheet[f"B{row}"]), f"{column}{row}")
        self.assertEqual(sheet["D3"].number_format, "#,##0.00")
        self.assertEqual(sheet["E3"].number_format, "0.0%")

    def test_a_row_inserted_at_the_top_has_nothing_above_to_copy(self):
        sheet = self.insert({"op": "insert_rows", "sheet": "Sales", "at": 1})
        self.assertFalse(sheet["A1"].has_style)


if __name__ == "__main__":
    unittest.main()
