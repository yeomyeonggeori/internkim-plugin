import unittest

from doc_fixture import ContractFixture, read_details


class ReadStylesTest(ContractFixture):
    def test_style_lists_appear_only_when_asked(self):
        self.assertNotIn("tableStyles", read_details(self.directory, "contract.docx"))
        details = read_details(self.directory, "contract.docx", "--styles")
        self.assertIn("Table Grid", details["tableStyles"])
        self.assertIn("Normal", details["paragraphStyles"])


if __name__ == "__main__":
    unittest.main()
