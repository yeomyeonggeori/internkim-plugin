import unittest
import zipfile

from doc_fixture import ContractFixture, read_details, run_office, write_json


class CommentThreadTest(ContractFixture):
    def apply(self, operations):
        write_json(self.directory / "ops.json", operations)
        envelope = run_office(["doc", "apply", "contract.docx", "ops.json"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope["issues"])
        return envelope

    def test_a_comment_marks_exact_text_and_a_reply_joins_its_thread(self):
        self.apply([{"op": "add_comment", "block": 5, "find": "일천만 원", "text": "금액 변경 근거가 필요합니다.", "author": "이샘플"}])
        self.apply([{"op": "reply_comment", "comment": 0, "text": "견적서 3차 수정본 기준입니다.", "author": "박예시"}])
        threads = read_details(self.directory, "contract.docx")["comments"]
        self.assertEqual(len(threads), 1)
        self.assertEqual({key: threads[0][key] for key in ("author", "text", "block", "anchorText", "resolved")}, {
            "author": "이샘플", "text": "금액 변경 근거가 필요합니다.", "block": 5, "anchorText": "일천만 원", "resolved": False,
        })
        self.assertEqual([(reply["author"], reply["text"]) for reply in threads[0]["replies"]], [("박예시", "견적서 3차 수정본 기준입니다.")])
        with zipfile.ZipFile(self.directory / "contract.docx") as archive:
            self.assertIn("word/commentsExtended.xml", archive.namelist())
            self.assertIn(b"commentsExtended+xml", archive.read("[Content_Types].xml"))

    def test_resolving_a_reply_resolves_its_thread_and_deleting_the_first_comment_removes_the_thread(self):
        self.apply([{"op": "add_comment", "block": 7, "find": "30일", "text": "기한 검토 요청", "author": "최견본"}])
        self.apply([{"op": "reply_comment", "comment": 0, "text": "14일로 단축 제안", "author": "박예시"}])
        self.apply([{"op": "resolve_comment", "comment": 1}])
        self.assertTrue(read_details(self.directory, "contract.docx")["comments"][0]["resolved"])
        self.apply([{"op": "delete_comment", "comment": 0}])
        self.assertEqual(read_details(self.directory, "contract.docx")["comments"], [])
        with zipfile.ZipFile(self.directory / "contract.docx") as archive:
            document_xml = archive.read("word/document.xml").decode()
        self.assertNotIn("commentRange", document_xml)
        self.assertNotIn("commentReference", document_xml)

    def test_a_tracked_run_signs_its_comments_with_the_tracking_author(self):
        write_json(self.directory / "ops.json", [{"op": "add_comment", "block": 5, "find": "일천만 원", "text": "금액 확인 요청"}])
        self.assertEqual(run_office(["doc", "apply", "contract.docx", "ops.json", "--track", "--author", "최견본"], self.directory)["status"], "ok")
        self.assertEqual(read_details(self.directory, "contract.docx")["comments"][0]["author"], "최견본")

    def test_a_comment_or_reply_without_an_author_is_refused_and_writes_nothing(self):
        before = (self.directory / "contract.docx").read_bytes()
        for operation in ({"op": "add_comment", "block": 5, "find": "일천만 원", "text": "확인"}, {"op": "reply_comment", "comment": 0, "text": "확인"}):
            if operation["op"] == "reply_comment":
                self.apply([{"op": "add_comment", "block": 5, "find": "일천만 원", "text": "금액 확인", "author": "이샘플"}])
                before = (self.directory / "contract.docx").read_bytes()
            with self.subTest(op=operation["op"]):
                write_json(self.directory / "ops.json", [operation])
                envelope = run_office(["doc", "apply", "contract.docx", "ops.json"], self.directory)
                self.assertEqual([(issue["code"], issue["location"]) for issue in envelope["issues"]], [("MISSING_FIELD", "ops[0].author")])
                self.assertEqual((self.directory / "contract.docx").read_bytes(), before)

    def test_text_the_block_does_not_hold_is_refused_with_the_block_text(self):
        write_json(self.directory / "ops.json", [{"op": "add_comment", "block": 5, "find": "일천이백만", "text": "확인"}])
        envelope = run_office(["doc", "apply", "contract.docx", "ops.json"], self.directory)
        self.assertEqual([issue["location"] for issue in envelope["issues"]], ["ops[0].find"])
        self.assertIn("일천만 원", envelope["issues"][0]["suggestion"])


if __name__ == "__main__":
    unittest.main()
