import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

from doc_fixture import OFFICE_ENTRY, SCRIPTS_PATH, run_office


from paperwork.jurisdictions import JURISDICTIONS
from paperwork.template_context import DEFAULT_VALUES, DERIVED_VALUES, LIST_FIELDS, OPTIONAL_PARAGRAPH_FIELDS, caller_fields, complete_context, list_fields, scalar_fields
from paperwork.template_fields import template_fields, template_names


SPECIFICATIONS_PATH = SCRIPTS_PATH.parent / "references" / "paperwork" / "kr"
ENGLISH_SPECIFICATIONS_PATH = SPECIFICATIONS_PATH.parent / "intl"
SKELETON_PATTERN = re.compile(r"## Context JSON skeleton\s+```json\n(.*?)\n```", re.DOTALL)
DOCUMENT_SKELETON_PATTERN = re.compile(r"## Document JSON skeleton\s+```json\n(.*?)\n```", re.DOTALL)
TAX_RATE_MENTION = re.compile(r"(?:부가세|VAT|Tax) ?\((\d+)%\)|(?:세액은 공급가액의|tax as) (\d+)%")
PROFILE_PLACEHOLDER = re.compile(r"\{ \.\.\.[^}]*\.\.\. \}")
TEMPLATE_BUILDER = """
import json, sys, zipfile
from pathlib import Path
from paperwork import build_templates
from paperwork.template_fields import TEMPLATES_PATH
differences = {}
for name, builder in build_templates.BUILDERS.items():
    built_path = Path(sys.argv[1]) / f"{name}.docx"
    builder(built_path)
    with zipfile.ZipFile(built_path) as built, zipfile.ZipFile(TEMPLATES_PATH / f"{name}.docx") as committed:
        parts = set(built.namelist()) | set(committed.namelist())
        differences[name] = sorted(part for part in parts if part not in built.namelist() or part not in committed.namelist() or built.read(part) != committed.read(part))
print(json.dumps(differences))
"""
def document_skeleton_fields(path):
    match = DOCUMENT_SKELETON_PATTERN.search(path.read_text(encoding="utf-8"))
    return field_paths(json.loads(PROFILE_PLACEHOLDER.sub("{}", match.group(1)))) if match else None


def field_paths(value, prefix=""):
    if isinstance(value, dict):
        return {path for key, child in value.items() for path in {prefix + key} | field_paths(child, f"{prefix}{key}.")}
    if isinstance(value, list):
        return {path for item in value for path in field_paths(item, f"{prefix}[].")}
    return set()


def documented_fields(template_name):
    specification = (SPECIFICATIONS_PATH / f"{template_name}.md").read_text(encoding="utf-8")
    match = SKELETON_PATTERN.search(specification)
    return set(json.loads(match.group(1))) - {"form"} if match else None


class TemplateFieldsTest(unittest.TestCase):
    def test_every_template_has_fields(self):
        self.assertEqual(template_names(), ["employment-contract", "mou", "nda", "offer-letter", "service-agreement"])
        for name in template_names():
            self.assertTrue(template_fields(name), name)

    def test_list_and_optional_fields_are_template_fields(self):
        for declared in (LIST_FIELDS, OPTIONAL_PARAGRAPH_FIELDS):
            for name, fields in declared.items():
                self.assertLessEqual(set(fields), set(template_fields(name)), name)

    def test_the_documentation_gives_a_list_exactly_for_each_list_field(self):
        for name in template_names():
            specification = (SPECIFICATIONS_PATH / f"{name}.md").read_text(encoding="utf-8")
            skeleton = json.loads(SKELETON_PATTERN.search(specification).group(1))
            self.assertEqual(sorted(field for field, value in skeleton.items() if isinstance(value, list)), sorted(list_fields(name)), name)


class TemplateGuardTest(unittest.TestCase):
    def test_defaults_and_derived_values_name_only_template_fields(self):
        for name, defaults in DEFAULT_VALUES.items():
            self.assertLessEqual(set(defaults), set(scalar_fields(name)), f"{name} defaults a field the template lacks")
        for name, derived in DERIVED_VALUES.items():
            self.assertLessEqual(set(derived), set(scalar_fields(name)), f"{name} derives a field the template lacks")

    def test_every_template_field_is_supplied_by_the_caller_a_default_or_a_derivation(self):
        for name in template_names():
            supplied = set(caller_fields(name)) | set(DEFAULT_VALUES.get(name, {})) | set(DERIVED_VALUES.get(name, {})) | set(list_fields(name))
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


class TemplateSourceTest(unittest.TestCase):
    def test_the_committed_templates_are_what_build_templates_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, str(OFFICE_ENTRY), "python", "-c", TEMPLATE_BUILDER, directory],
                capture_output=True, text=True, check=True,
            )
        for name, differing_parts in json.loads(completed.stdout).items():
            self.assertEqual(differing_parts, [], f"{name}.docx differs from build_templates; rerun it")

    def test_english_and_korean_specs_describe_the_same_document_fields(self):
        for korean in sorted(SPECIFICATIONS_PATH.glob("*.md")):
            english = ENGLISH_SPECIFICATIONS_PATH / korean.name
            self.assertTrue(english.exists(), korean.name)
            korean_fields = document_skeleton_fields(korean)
            if korean_fields is not None:
                self.assertEqual(document_skeleton_fields(english), korean_fields, korean.name)


    def test_every_tax_rate_a_spec_states_is_the_rate_its_jurisdiction_checks(self):
        for jurisdiction in JURISDICTIONS:
            if jurisdiction.tax_rate_percent is None:
                continue
            for specification in sorted((SPECIFICATIONS_PATH.parent / jurisdiction.code).glob("*.md")):
                for match in TAX_RATE_MENTION.finditer(specification.read_text(encoding="utf-8")):
                    self.assertEqual(int(match.group(1) or match.group(2)), jurisdiction.tax_rate_percent, f"{jurisdiction.code}/{specification.name}: {match.group(0)}")

    def test_every_spec_skeleton_names_its_own_form(self):
        for specification in sorted(SPECIFICATIONS_PATH.parent.glob("*/*.md")):
            match = DOCUMENT_SKELETON_PATTERN.search(specification.read_text(encoding="utf-8")) or SKELETON_PATTERN.search(specification.read_text(encoding="utf-8"))
            named = re.search(r'"form": "([^"]+)"', match.group(1))
            self.assertEqual(named.group(1), f"{specification.parent.name}/{specification.stem}")


FILLED_PARAGRAPHS = """
import json, sys
from docx import Document
document = Document(sys.argv[1])
print(json.dumps([[paragraph.text, paragraph._p.pPr.numPr.numId.val if paragraph._p.pPr is not None and paragraph._p.pPr.numPr is not None else None] for paragraph in document.paragraphs], ensure_ascii=False))
"""


class FillTest(unittest.TestCase):
    def fill(self, template_name, context):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.directory / "context.json").write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
        envelope = run_office(["merge", f"kr/{template_name}", "context.json", "out.docx"], self.directory)
        self.assertEqual(envelope["status"], "ok", envelope)
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), "python", "-c", FILLED_PARAGRAPHS, str(self.directory / "out.docx")], capture_output=True, text=True, check=True)
        return json.loads(completed.stdout)

    def test_fill_writes_the_words_it_derives_from_the_amount(self):
        context = {field: "예시" for field in caller_fields("service-agreement")}
        context.update({"totalAmount": "50,000,000", "scopeItems": ["a"], "payments": ["b"], "deliverables": ["c"]})
        texts = [text for text, _ in self.fill("service-agreement", context)]
        self.assertIn("① 본 용역의 계약금액은 금 오천만원整 (₩50,000,000, 부가가치세 예시)으로 한다.", texts)

    def test_each_list_item_is_a_numbered_paragraph_and_each_list_restarts_at_one(self):
        context = {field: "예시" for field in caller_fields("service-agreement")}
        context.update({"totalAmount": "1,000", "scopeItems": ["설계", "구축", "운영"], "payments": ["선급금 30%", "잔금 70%"], "deliverables": ["결과 보고서"]})
        paragraphs = self.fill("service-agreement", context)
        numbered = {}
        for text, number in paragraphs:
            if number is not None:
                numbered.setdefault(number, []).append(text)
        self.assertEqual(list(numbered.values()), [["설계", "구축", "운영"], ["선급금 30%", "잔금 70%"], ["결과 보고서"]])
        self.assertFalse(any("{{" in text for text, _ in paragraphs))

    def test_a_blank_optional_field_leaves_its_paragraph_out(self):
        context = {field: "예시" for field in caller_fields("offer-letter")}
        context.update({"benefits": ["식대 지원", "자기계발비"], "equity": "1,000주"})
        texts = [text for text, _ in self.fill("offer-letter", context)]
        self.assertIn("스톡옵션: 1,000주", texts)
        self.assertEqual([text for text in texts if text.startswith("- ")], ["- 식대 지원", "- 자기계발비"])
        self.assertFalse(any("{{" in text for text in texts))
        self.assertEqual(len(texts), len(self.fill("offer-letter", {**context, "probationNote": "수습 3개월"})) - 1)

    def test_an_employment_contract_without_an_end_date_has_no_contract_period(self):
        context = {field: "예시" for field in caller_fields("employment-contract")}
        context.update({"startDate": "2026-11-01"})
        open_ended = [text for text, _ in self.fill("employment-contract", context)]
        self.assertIn("근로개시일: 2026-11-01", open_ended)
        self.assertFalse(any(text.startswith("근로계약기간") for text in open_ended))
        fixed_term = [text for text, _ in self.fill("employment-contract", {**context, "endDate": "2027-10-31"})]
        self.assertIn("근로계약기간: 2026-11-01부터 2027-10-31까지", fixed_term)


if __name__ == "__main__":
    unittest.main()
