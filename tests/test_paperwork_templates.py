import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

from doc_fixture import OFFICE_ENTRY, SCRIPTS_PATH, run_office

sys.path.insert(0, str(SCRIPTS_PATH / "paperwork"))

from template_context import DEFAULT_VALUES, DERIVED_VALUES, caller_fields, complete_context, scalar_fields
from template_fields import template_fields, template_list_fields, template_names


SPECIFICATIONS_PATH = SCRIPTS_PATH.parent / "references" / "paperwork" / "ko"
SKELETON_PATTERN = re.compile(r"## Context JSON skeleton\s+```json\n(.*?)\n```", re.DOTALL)
DOCXTPL_READER = """
import json, sys
from docxtpl import DocxTemplate
from template_fields import TEMPLATES_PATH, template_names
print(json.dumps({name: sorted(DocxTemplate(str(TEMPLATES_PATH / f"{name}.docx")).get_undeclared_template_variables()) for name in template_names()}))
"""


def documented_fields(template_name):
    specification = (SPECIFICATIONS_PATH / f"{template_name}.md").read_text(encoding="utf-8")
    match = SKELETON_PATTERN.search(specification)
    return set(json.loads(match.group(1))) if match else None


class TemplateFieldsTest(unittest.TestCase):
    def test_the_reader_finds_what_docxtpl_finds(self):
        completed = subprocess.run(
            [sys.executable, str(OFFICE_ENTRY), "python", "-c", DOCXTPL_READER],
            capture_output=True, text=True, check=True,
            env={**__import__("os").environ, "PYTHONPATH": str(SCRIPTS_PATH / "paperwork")},
        )
        for name, expected in json.loads(completed.stdout).items():
            self.assertEqual(template_fields(name), expected, name)

    def test_every_template_has_fields(self):
        self.assertEqual(template_names(), ["employment-contract", "mou", "nda", "offer-letter", "service-agreement"])
        for name in template_names():
            self.assertTrue(template_fields(name), name)

    def test_lists_are_the_loop_sources(self):
        self.assertEqual(template_list_fields("service-agreement"), ["deliverables", "payments", "scopeItems"])
        self.assertEqual(template_list_fields("nda"), [])


class TemplateGuardTest(unittest.TestCase):
    def test_defaults_and_derived_values_name_only_template_fields(self):
        for name, defaults in DEFAULT_VALUES.items():
            self.assertLessEqual(set(defaults), set(scalar_fields(name)), f"{name} defaults a field the template lacks")
        for name, derived in DERIVED_VALUES.items():
            self.assertLessEqual(set(derived), set(scalar_fields(name)), f"{name} derives a field the template lacks")

    def test_every_template_field_is_supplied_by_the_caller_a_default_or_a_derivation(self):
        for name in template_names():
            supplied = set(caller_fields(name)) | set(DEFAULT_VALUES.get(name, {})) | set(DERIVED_VALUES.get(name, {})) | set(template_list_fields(name))
            self.assertEqual(supplied, set(template_fields(name)), name)

    def test_the_documentation_lists_exactly_the_fields_a_caller_gives(self):
        for name in template_names():
            documented = documented_fields(name)
            self.assertIsNotNone(documented, f"{name}.md has no context skeleton")
            givable = set(template_fields(name)) - set(DERIVED_VALUES.get(name, {}))
            self.assertEqual(documented, givable, name)

    def test_a_derived_field_is_filled_from_the_amount(self):
        context = complete_context("service-agreement", {"totalAmount": "50,000,000"})
        self.assertEqual(context["totalAmountKorean"], "오천만")
        self.assertEqual(complete_context("service-agreement", {"totalAmount": "1", "totalAmountKorean": "직접"})["totalAmountKorean"], "직접")


class FillTest(unittest.TestCase):
    def test_fill_writes_the_words_it_derives_from_the_amount(self):
        with tempfile.TemporaryDirectory() as directory:
            context = {field: "예시" for field in caller_fields("service-agreement")}
            context.update({"totalAmount": "50,000,000", "scopeItems": ["a"], "payments": ["b"], "deliverables": ["c"]})
            (Path(directory) / "context.json").write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
            envelope = run_office(["paperwork", "fill", "service-agreement", "context.json", "out.docx"], directory)
            self.assertEqual(envelope["status"], "ok")
            with zipfile.ZipFile(Path(directory) / "out.docx") as archive:
                self.assertIn("금 오천만원整 (₩50,000,000", re.sub(r"<[^>]+>", "", archive.read("word/document.xml").decode("utf-8")))


if __name__ == "__main__":
    unittest.main()
