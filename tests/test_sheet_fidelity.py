import unittest
import zipfile

from sheet_fidelity_fixture import CONDITIONAL_FORMATTING_URI, DATA_BAR_ID, DATA_VALIDATION_URI, SPARKLINE_URI, build_rich_workbook
from sheet_fixture import WorkbookFixture, run_office, run_office_python, write_json

CONTROLS = (
    '<controls><control shapeId="1025" r:id="rIdControl" name="Check Box 1"/></controls>'
)


def package(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


class RoundTripTest(WorkbookFixture):
    def setUp(self):
        super().setUp()
        build_rich_workbook(self.directory, run_office_python)

    def apply_to_rich(self, operations, *extra):
        return self.apply(operations, *extra, name="rich.xlsx")

    def sheet_xml(self):
        return package(self.directory / "rich.xlsx")["xl/worksheets/sheet1.xml"].decode()

    def test_an_edit_keeps_sparklines_extensions_slicers_shapes_and_unknown_parts(self):
        before = package(self.directory / "rich.xlsx")
        envelope = self.apply_to_rich([{"op": "set_cell", "sheet": "Data", "cell": "A8", "value": "note"}])
        self.assertEqual(envelope["status"], "ok", envelope)
        after = package(self.directory / "rich.xlsx")
        for part in ("customXml/item1.xml", "customXml/itemProps1.xml", "xl/slicers/slicer1.xml", "xl/slicerCaches/slicerCache1.xml"):
            self.assertEqual(after[part], before[part], part)
        sheet = after["xl/worksheets/sheet1.xml"].decode()
        for uri in (SPARKLINE_URI, CONDITIONAL_FORMATTING_URI, DATA_VALIDATION_URI):
            self.assertIn(uri, sheet)
        self.assertIn("<xm:f>Data!B6:D6</xm:f><xm:sqref>F6</xm:sqref>", sheet)
        self.assertIn(b"keep this note", after["xl/drawings/drawing1.xml"])
        self.assertIn(f"<x14:id>{DATA_BAR_ID}</x14:id>", sheet)
        self.assertIn('<phoneticPr fontId="1" type="noConversion"/>', sheet)
        self.assertIn('<ignoredError sqref="E2:E6" formula="1"/>', sheet)
        self.assertIn(b"slicerCache", after["xl/workbook.xml"])
        relationships = after["xl/worksheets/_rels/sheet1.xml.rels"].decode()
        self.assertIn("../slicers/slicer1.xml", relationships)

    def test_inserted_rows_move_sparklines_validations_and_shapes(self):
        envelope = self.apply_to_rich([{"op": "insert_rows", "sheet": "Data", "at": 4, "count": 2}])
        self.assertEqual(envelope["status"], "ok", envelope)
        sheet = self.sheet_xml()
        self.assertIn("<xm:f>Data!B2:D2</xm:f><xm:sqref>F2</xm:sqref>", sheet)
        self.assertIn("<xm:f>Data!B8:D8</xm:f><xm:sqref>F8</xm:sqref>", sheet)
        self.assertIn("<xm:sqref>A10:A14</xm:sqref>", sheet)
        self.assertIn('<ignoredError sqref="E2:E8" formula="1"/>', sheet)
        drawing = package(self.directory / "rich.xlsx")["xl/drawings/drawing1.xml"].decode()
        self.assertIn("<from><col>1</col><colOff>0</colOff><row>10</row>", drawing)

    def test_a_deleted_row_takes_its_sparkline_with_it_and_a_rename_follows_into_extensions(self):
        envelope = self.apply_to_rich([{"op": "delete_rows", "sheet": "Data", "at": 6}, {"op": "rename_sheet", "sheet": "Lists", "name": "목록"}])
        self.assertEqual(envelope["status"], "ok", envelope)
        sheet = self.sheet_xml()
        self.assertNotIn("<xm:sqref>F6</xm:sqref>", sheet)
        self.assertIn("<xm:sqref>F2</xm:sqref>", sheet)
        self.assertIn("<xm:f>목록!$A$1:$A$3</xm:f>", sheet)

    def test_appending_rows_keeps_the_same_content(self):
        write_json(self.directory / "rows.json", [["r9", 1, 2, 3]])
        envelope = run_office(["sheet", "edit", "rich.xlsx", "--sheet", "Data", "--rows", "rows.json"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope)
        self.assertIn(SPARKLINE_URI, self.sheet_xml())


class LossTest(WorkbookFixture):
    def setUp(self):
        super().setUp()
        path = build_rich_workbook(self.directory, run_office_python)
        entries = package(path)
        entries["xl/worksheets/sheet1.xml"] = entries["xl/worksheets/sheet1.xml"].replace(b"<tableParts", CONTROLS.encode() + b"<tableParts")
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
        self.original = (self.directory / "rich.xlsx").read_bytes()

    def test_content_the_editor_cannot_carry_stops_the_save(self):
        envelope = self.apply([{"op": "set_cell", "sheet": "Data", "cell": "A8", "value": 1}], name="rich.xlsx")
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["CONTENT_WOULD_BE_LOST"])
        self.assertIn("Data: <controls>", envelope["issues"][0]["message"])
        self.assertEqual((self.directory / "rich.xlsx").read_bytes(), self.original)

    def test_allow_loss_saves_and_says_what_was_dropped(self):
        envelope = self.apply([{"op": "set_cell", "sheet": "Data", "cell": "A8", "value": 1}], "--allow-loss", name="rich.xlsx")
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["CONTENT_DROPPED"])
        self.assertIn(SPARKLINE_URI, package(self.directory / "rich.xlsx")["xl/worksheets/sheet1.xml"].decode())


if __name__ == "__main__":
    unittest.main()
