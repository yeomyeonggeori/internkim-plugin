import struct
import unittest
import zlib

from sheet_fixture import run_office
from test_sheet_operations import OperationFixture, archive_names, archive_text


def write_png(path, width=40, height=20):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + b"\x25\x63\xeb" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class SheetStructureTest(OperationFixture):
    def test_delete_sheet_breaks_what_read_it_and_check_names_it(self):
        self.edit([{"op": "set_cell", "sheet": "Sales", "cell": "F1", "value": "=Notes!A2"}, {"op": "add_defined_name", "name": "Memo", "sheet": "Notes", "range": "A2"}])
        self.edit([{"op": "delete_sheet", "sheet": "Notes"}])
        workbook = self.workbook()
        self.assertEqual(workbook.sheetnames, ["Sales"])
        self.assertEqual((workbook["Sales"]["F1"].value, workbook.defined_names["Memo"].attr_text), ("=#REF!", "#REF!"))
        codes = {issue["code"] for issue in run_office(["check", "book.xlsx"], self.directory)["issues"]}
        self.assertIn("BROKEN_DEFINED_NAME", codes)

    def test_the_last_visible_sheet_cannot_be_deleted(self):
        self.edit([{"op": "delete_sheet", "sheet": "Notes"}])
        self.assertEqual(self.refused([{"op": "delete_sheet", "sheet": "Sales"}])["code"], "OPERATION_NOT_APPLICABLE")

    def test_duplicate_keeps_cells_formats_and_rules_and_sits_after_the_original(self):
        self.edit([{"op": "add_conditional_format", "range": "D2:D7", "rule": "data_bar"}, {"op": "add_data_validation", "range": "A2:A7", "type": "list", "values": ["Seoul", "Busan"]}])
        envelope = self.edit([{"op": "duplicate_sheet", "sheet": "Sales"}])
        workbook = self.workbook()
        self.assertEqual(workbook.sheetnames, ["Sales", "Sales (2)", "Notes"])
        copy = workbook["Sales (2)"]
        self.assertEqual((copy["D2"].value, copy.freeze_panes, len(copy.conditional_formatting), len(copy.data_validations.dataValidation)), (3000, "A2", 1, 1))
        self.assertIn("copied sheet Sales to Sales (2)", envelope["details"]["changes"][0]["change"])

    def test_move_sheet_reorders_the_tabs(self):
        self.edit([{"op": "move_sheet", "sheet": "Notes", "index": 0}])
        self.assertEqual(self.workbook().sheetnames, ["Notes", "Sales"])
        self.assertIn("numbered from 0 to 1", self.refused([{"op": "move_sheet", "sheet": "Notes", "index": 5}])["message"])

    def test_defined_names_are_added_used_and_deleted(self):
        self.edit([{"op": "add_defined_name", "name": "Amounts", "range": "D2:D7"}, {"op": "add_defined_name", "name": "TaxRate", "value": 0.1}, {"op": "set_cell", "cell": "F1", "value": "=SUM(Amounts)*TaxRate"}])
        workbook = self.workbook()
        self.assertEqual(workbook.defined_names["Amounts"].attr_text, "Sales!$D$2:$D$7")
        self.assertEqual(self.cells()["F1"]["value"], "2200")
        self.edit([{"op": "delete_defined_name", "name": "TaxRate"}])
        self.assertNotIn("TaxRate", self.workbook().defined_names)
        self.assertIn("did you mean 'Amounts'", self.refused([{"op": "delete_defined_name", "name": "Amount"}])["message"])
        self.assertEqual(self.refused([{"op": "add_defined_name", "name": "A1", "value": 1}])["code"], "INVALID_VALUE")

    def test_protect_and_unprotect_a_sheet(self):
        self.edit([{"op": "protect_sheet", "password": "secret"}])
        protection = self.workbook()["Sales"].protection
        self.assertTrue(protection.sheet)
        self.assertTrue(protection.password)
        self.edit([{"op": "protect_sheet", "protected": False}])
        self.assertFalse(self.workbook()["Sales"].protection.sheet)


class RangeOperationTest(OperationFixture):
    def test_fill_down_copies_formulas_with_shifted_references(self):
        self.edit([{"op": "set_cell", "cell": "E2", "value": "=C2*2"}, {"op": "fill_range", "range": "E2:E7"}])
        sheet = self.workbook()["Sales"]
        self.assertEqual([sheet[f"E{row}"].value for row in (3, 7)], ["=C3*2", "=C7*2"])
        self.assertEqual(self.cells()["E7"]["value"], "8")

    def test_fill_series_counts_numbers_dates_and_numbered_text(self):
        self.edit([{"op": "set_range", "cell": "F1", "values": [[1, "항목1", 10]]}, {"op": "fill_range", "range": "F1:G4", "series": True}, {"op": "fill_range", "range": "H1:J1", "direction": "right", "series": True, "step": 5}])
        sheet = self.workbook()["Sales"]
        self.assertEqual([sheet["F4"].value, sheet["G4"].value, sheet["J1"].value], [4, "항목4", 20])

    def test_copy_range_moves_formulas_like_paste_and_pastes_values(self):
        self.edit([{"op": "set_cell", "cell": "E2", "value": "=D2/C2"}, {"op": "copy_range", "range": "C1:E3", "to": "A10", "toSheet": "Notes"}])
        notes = self.workbook()["Notes"]
        self.assertEqual((notes["A10"].value, notes["C11"].value), ("qty", "=B11/A11"))
        self.edit([{"op": "copy_range", "range": "E2:E3", "to": "G2", "paste": "values"}])
        self.assertEqual(self.workbook()["Sales"]["G2"].value, 1000)

    def test_clear_range_keeps_or_drops_formats(self):
        self.edit([{"op": "format_range", "range": "A2:B3", "bold": True}, {"op": "clear_range", "range": "A2:A3"}, {"op": "clear_range", "range": "B2:B3", "what": "formats"}])
        sheet = self.workbook()["Sales"]
        self.assertEqual((sheet["A2"].value, sheet["A2"].font.b, sheet["B2"].value, sheet["B2"].font.b), (None, True, "A", False))

    def test_convert_to_values_keeps_the_numbers(self):
        self.edit([{"op": "set_cell", "cell": "F2", "value": "=SUM(D2:D7)"}, {"op": "convert_to_values", "range": "F2"}])
        self.assertEqual(self.workbook()["Sales"]["F2"].value, 22000)

    def test_filter_criteria_hide_the_rows_that_do_not_match(self):
        self.edit([{"op": "set_filter_criteria", "column": "A", "values": ["seoul"]}])
        sheet = self.workbook()["Sales"]
        self.assertEqual([row for row in range(2, 8) if sheet.row_dimensions[row].hidden], [3, 5, 6])
        self.assertIn('<filter val="seoul"/>', self.sheet_xml())
        self.edit([{"op": "set_filter_criteria", "column": "A"}])
        self.assertFalse(any(self.workbook()["Sales"].row_dimensions[row].hidden for row in range(2, 8)))


class DrawingAndPrintTest(OperationFixture):
    def test_an_image_and_a_shape_land_in_the_drawing_and_survive_another_edit(self):
        write_png(self.directory / "logo.png")
        self.edit([{"op": "add_image", "cell": "G2", "path": "logo.png", "width": 4}, {"op": "add_shape", "cell": "G10", "shape": "rounded_rectangle", "text": "합계 확인", "fill": "FEF3C7"}])
        self.edit([{"op": "insert_rows", "at": 1}])
        drawing = archive_text(self.directory / "book.xlsx", "xl/drawings/drawing1.xml")
        self.assertIn('prst="roundRect"', drawing)
        self.assertIn("합계 확인", drawing)
        self.assertIn("<row>10</row>", drawing)
        self.assertEqual(self.workbook()["Sales"]._images[0].anchor._from.row, 2)
        self.assertTrue(any(name.startswith("xl/media/") for name in archive_names(self.directory / "book.xlsx")))

    def test_a_missing_image_is_named(self):
        self.assertEqual(self.refused([{"op": "add_image", "cell": "G2", "path": "nothing.png"}])["code"], "INPUT_NOT_FOUND")

    def test_header_footer_scale_and_page_breaks(self):
        self.edit([{"op": "set_page_setup", "scale": 80, "header": "매출 & 원가", "footer": "{page} / {pages}", "pageBreakRows": [4], "pageBreakColumns": ["C"]}])
        sheet = self.sheet_xml()
        self.assertIn('scale="80"', sheet)
        printed = self.workbook()["Sales"]
        self.assertEqual((printed.oddHeader.center.text, printed.oddFooter.center.text), ("매출 && 원가", "&P / &N"))
        self.assertIn('<brk id="4"', sheet)
        self.assertIn('<colBreaks count="1" manualBreakCount="1"><brk id="3"', sheet)


if __name__ == "__main__":
    unittest.main()
