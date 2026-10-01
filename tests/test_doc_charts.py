import tempfile
import unittest
import zipfile
from pathlib import Path

from doc_fixture import run_office, run_office_python, write_json


REPORT = """# 분기 보고

```chart
type: combo
title: 분기 매출과 이익률 (백만 원, %)
labels: 1분기, 2분기, 3분기
series: 매출: 3820, 4010, 4230; 이익률: 7.6, 8.1, 8.4
line: 이익률
```

```chart
type: donut
labels: 공공, 민간
values: 60, 40
```
"""

PATH_COUNT = """
import pathlib
import pypdfium2
import pypdfium2.raw as raw
page = pypdfium2.PdfDocument("report.pdf")[0]
paths = sum(1 for drawn in page.get_objects(max_depth=4) if drawn.type == raw.FPDF_PAGEOBJ_PATH)
pathlib.Path("paths.txt").write_text(str(paths))
"""


class DocumentChartTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        (self.directory / "report.md").write_text(REPORT, encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def export(self, *arguments):
        envelope = run_office(["doc", "export", "report.md", *arguments], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])

    def charts(self, name):
        return run_office(["doc", "read", name], self.directory)["details"]["charts"]

    def test_markdown_chart_blocks_become_native_charts_that_read_back(self):
        self.export("--output", "report.docx")
        with zipfile.ZipFile(self.directory / "report.docx") as archive:
            embedded = [name for name in archive.namelist() if name.startswith("word/embeddings/")]
        charts = self.charts("report.docx")
        self.assertEqual(len(embedded), 2)
        self.assertEqual([chart["type"] for chart in charts], ["combo", "doughnut"])
        self.assertEqual(charts[0]["series"][1], {"name": "이익률", "values": [7.6, 8.1, 8.4], "line": True})
        self.assertEqual(charts[1]["series"][0]["values"], [60, 40])

    def test_a_converted_document_writes_the_same_chart_blocks_back(self):
        self.export("--output", "report.docx")
        envelope = run_office(["convert", "report.docx", "back.md"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        markdown = (self.directory / "back.md").read_text(encoding="utf-8")
        self.assertIn("type: combo", markdown)
        self.assertIn("series: 매출: 3820, 4010, 4230; 이익률: 7.6, 8.1, 8.4", markdown)
        self.assertIn("line: 이익률", markdown)

    def test_charts_are_inserted_edited_and_deleted_by_index(self):
        self.export("--output", "report.docx")
        write_json(self.directory / "ops.json", [
            {"op": "edit_chart", "chart": 1, "type": "pie", "title": "부문 비중"},
            {"op": "insert_chart", "after": 0, "type": "bar", "categories": ["서울", "부산"], "series": [{"name": "2026", "values": [21, 10]}]},
            {"op": "delete_chart", "chart": 0},
        ])
        envelope = run_office(["doc", "apply", "report.docx", "ops.json", "--output", "edited.docx"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        charts = self.charts("edited.docx")
        self.assertEqual([(chart["type"], chart.get("title")) for chart in charts], [("bar", None), ("pie", "부문 비중")])

    def test_a_series_that_does_not_line_up_is_refused_with_its_location(self):
        self.export("--output", "report.docx")
        write_json(self.directory / "ops.json", [{"op": "insert_chart", "after": 0, "type": "column", "categories": ["가", "나"], "series": [{"name": "값", "values": [1]}]}])
        envelope = run_office(["doc", "apply", "report.docx", "ops.json", "--output", "edited.docx"], self.directory)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["issues"][0]["location"], "ops[0].series[0].values")

    def test_a_malformed_chart_block_stops_the_export(self):
        (self.directory / "report.md").write_text("```chart\ntype: column\nlabels: 가, 나\nvalues: 1, 둘\n```\n", encoding="utf-8")
        envelope = run_office(["doc", "export", "report.md", "--output", "report.docx"], self.directory)
        self.assertEqual([issue["code"] for issue in envelope["issues"]], ["CHART_BLOCK_INVALID"])
        self.assertFalse((self.directory / "report.docx").exists())

    def test_the_pdf_export_draws_charts_as_vector_shapes(self):
        self.export("--format", "pdf", "--output", "report.pdf")
        run_office_python(PATH_COUNT, self.directory)
        self.assertGreater(int((self.directory / "paths.txt").read_text()), 20)


if __name__ == "__main__":
    unittest.main()
