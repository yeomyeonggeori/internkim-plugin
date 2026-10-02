import zipfile

from doc_fixture import DocumentFixture, block_texts, read_details, run_office, run_office_python, write_json


def apply(directory, operations, document="fixture.docx"):
    write_json(directory / "operations.json", operations)
    return run_office(["apply", document, "operations.json"], directory)


def document_xml(directory, document="fixture.docx"):
    with zipfile.ZipFile(directory / document) as archive:
        return archive.read("word/document.xml").decode("utf-8")


class StructureOperationTest(DocumentFixture):
    def test_moved_blocks_keep_their_order(self):
        envelope = apply(self.directory, [{"op": "move_blocks", "blocks": [2, 1], "after": 4}])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        texts = [text for _, text in block_texts(self.directory, "fixture.docx")]
        self.assertEqual(texts, ["개요", [["항목", "값"], ["매출", "100"]], "결론", "첫 문단 {{ customer_name }} 입니다.", "둘째 문단"])

    def test_paragraphs_become_a_list_and_back(self):
        self.assertEqual(apply(self.directory, [{"op": "set_list", "block": 1, "toBlock": 2, "numbered": True}])["status"], "ok")
        self.assertEqual([kind for kind, _ in block_texts(self.directory, "fixture.docx")][1:3], ["listItem", "listItem"])
        self.assertEqual(apply(self.directory, [{"op": "clear_list", "block": 1, "toBlock": 2}])["status"], "ok")
        self.assertEqual([kind for kind, _ in block_texts(self.directory, "fixture.docx")][1:3], ["paragraph", "paragraph"])

    def test_markdown_inserts_and_replaces_blocks_with_the_document_styles(self):
        envelope = apply(self.directory, [
            {"op": "insert_markdown", "after": 0, "markdown": "## 요약\n\n- 매출 **12%** 증가\n- 비용 절감"},
            {"op": "replace_blocks", "block": 1, "toBlock": 2, "markdown": "새 문단입니다."},
        ])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertEqual(block_texts(self.directory, "fixture.docx")[:5], [
            ("heading", "개요"), ("heading", "요약"), ("listItem", "매출 12% 증가"), ("listItem", "비용 절감"), ("paragraph", "새 문단입니다."),
        ])


class DrawingOperationTest(DocumentFixture):
    def setUp(self):
        super().setUp()
        run_office_python("""
            from PIL import Image
            Image.new("RGB", (300, 200), "teal").save("picture.png")
        """, self.directory)

    def test_a_picture_floats_with_square_wrapping_and_returns_inline(self):
        envelope = apply(self.directory, [
            {"op": "insert_image", "after": 1, "path": "picture.png", "widthInches": 2},
            {"op": "insert_image", "after": 2, "path": "picture.png", "widthInches": 1, "wrap": "topAndBottom"},
        ])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertEqual(document_xml(self.directory).count("<wp:wrapTopAndBottom/>"), 1)
        envelope = apply(self.directory, [{"op": "set_image_properties", "block": 2, "widthInches": 3, "wrap": "square", "align": "right", "description": "청록 사각형"}])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        xml = document_xml(self.directory)
        self.assertIn('<wp:wrapSquare wrapText="bothSides"/>', xml)
        self.assertIn("<wp:align>right</wp:align>", xml)
        self.assertIn('descr="청록 사각형"', xml)
        self.assertIn('cx="2743200" cy="1828800"', xml)
        self.assertEqual(apply(self.directory, [{"op": "set_image_properties", "block": 2, "wrap": "inline"}])["status"], "ok")
        self.assertEqual(document_xml(self.directory).count("<wp:anchor"), 1)

    def test_a_text_box_holds_its_lines_as_paragraphs(self):
        envelope = apply(self.directory, [{"op": "insert_text_box", "after": 1, "text": "요약\n매출 12% 증가", "fill": "#EEF2F7"}])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        xml = document_xml(self.directory)
        self.assertIn("<w:txbxContent><w:p><w:r><w:t xml:space=\"preserve\">요약</w:t></w:r></w:p><w:p><w:r><w:t xml:space=\"preserve\">매출 12% 증가</w:t>", xml)
        self.assertIn('<a:srgbClr val="EEF2F7"/>', xml)
        self.assertTrue(read_details(self.directory, "fixture.docx")["blocks"][2]["picture"])


class InlineOperationTest(DocumentFixture):
    def test_latex_becomes_a_word_equation_inline_or_on_its_own_line(self):
        envelope = apply(self.directory, [
            {"op": "insert_equation", "at": "end", "latex": "\\frac{a+b}{2} = \\sum_{i=1}^{n} x_i"},
            {"op": "insert_equation", "block": 2, "latex": "x^2"},
        ])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        xml = document_xml(self.directory)
        self.assertIn("<m:oMathPara>", xml)
        self.assertIn("<m:f>", xml)
        self.assertIn("<m:sSup>", xml)
        self.assertTrue(read_details(self.directory, "fixture.docx")["blocks"][2]["equation"])
        render = run_office(["render", "fixture.docx"], self.directory)
        self.assertIn("2 equations drawn as linear text", render["issues"][0]["message"])
        self.assertIn("(a+b)/2=∑_(i=1)^n x_i", (self.directory / "fixture-preview" / "preview.html").read_text(encoding="utf-8"))

    def test_latex_the_converter_cannot_read_is_refused(self):
        for latex in ("\\frac{a", "\\unknowncommand{x}"):
            envelope = apply(self.directory, [{"op": "insert_equation", "at": "end", "latex": latex}])
            self.assertEqual([issue["code"] for issue in envelope["issues"]], ["INVALID_VALUE"], latex)

    def test_a_date_field_carries_its_picture_and_a_shown_result(self):
        envelope = apply(self.directory, [{"op": "insert_field", "block": 2, "field": "DATE", "format": "yyyy-MM-dd"}, {"op": "insert_field", "block": 2, "field": "SEQ", "sequence": "표"}])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        xml = document_xml(self.directory)
        self.assertIn('DATE \\@ "yyyy-MM-dd"', xml)
        self.assertIn("SEQ 표 \\* ARABIC", xml)
        self.assertRegex(block_texts(self.directory, "fixture.docx")[2][1], r"^둘째 문단\d{4}-\d{2}-\d{2}1$")
        codes = {issue["code"] for issue in run_office(["check", "fixture.docx"], self.directory)["issues"]}
        self.assertNotIn("FIELD_NOT_EVALUATED", codes)

    def test_notes_are_rewritten_and_deleted_with_their_marks(self):
        apply(self.directory, [{"op": "insert_footnote", "block": 2, "text": "첫 주석"}, {"op": "insert_endnote", "block": 2, "text": "미주"}])
        envelope = apply(self.directory, [{"op": "edit_note", "kind": "footnote", "note": 1, "text": "고친 주석"}, {"op": "delete_note", "kind": "endnote", "note": 1}])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        self.assertEqual(read_details(self.directory, "fixture.docx")["notes"], [{"kind": "footnote", "id": 1, "text": "고친 주석"}])
        self.assertNotIn("endnoteReference", document_xml(self.directory))
        missing = apply(self.directory, [{"op": "delete_note", "kind": "endnote", "note": 1}])
        self.assertEqual([issue["code"] for issue in missing["issues"]], ["TARGET_NOT_FOUND"])


class TableSplitTest(DocumentFixture):
    def test_a_merged_cell_splits_back_into_the_cells_it_covered(self):
        self.assertEqual(apply(self.directory, [{"op": "merge_cells", "block": 3, "row": 0, "column": 0, "toRow": 1, "toColumn": 1}])["status"], "ok")
        self.assertTrue(read_details(self.directory, "fixture.docx")["blocks"][3]["mergedCells"])
        envelope = apply(self.directory, [{"op": "split_table_cell", "block": 3, "row": 1, "column": 1}])
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        table = read_details(self.directory, "fixture.docx")["blocks"][3]
        self.assertFalse(table["mergedCells"])
        self.assertEqual(table["cells"], [["항목\n값\n매출\n100", ""], ["", ""]])
        refused = apply(self.directory, [{"op": "split_table_cell", "block": 3, "row": 0, "column": 1}])
        self.assertEqual([issue["code"] for issue in refused["issues"]], ["OPERATION_NOT_APPLICABLE"])
