import re
import subprocess
import sys
import unittest

from test_office_results import OFFICE_ENTRY, OFFICE_PATH, all_known_codes, every_definitions

from core.office_commands import TOOLS, VERBS  # noqa: E402
from core.retired_commands import RETIRED_FORMATS  # noqa: E402
from deck.deck_definitions import KIT_LAYOUT_NAMES  # noqa: E402
from deck.deck_kit import theme_names  # noqa: E402
from office_guide import guide_for  # noqa: E402
from paperwork.forms import form_names  # noqa: E402
from schemas.schema_document import bundled_schema_names  # noqa: E402


DOCUMENTS = (OFFICE_PATH / "SKILL.md", *sorted((OFFICE_PATH / "references").rglob("*.md")))
CODE_PATTERN = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")
GUIDE_PATTERN = re.compile(r"office guide((?: [a-z_]+)*)")
FLAG_PATTERN = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*[a-z0-9])")
FORM_PATTERN = re.compile(r"(?<![\w/])((?:kr|intl)/[a-z]+(?:-[a-z]+)*)\b")
KIT_STYLE = (OFFICE_PATH / "assets" / "deck-kit" / "deck-kit.css").read_text(encoding="utf-8")


def documents_text() -> str:
    return "\n".join(document.read_text(encoding="utf-8") for document in DOCUMENTS)


def guided_codes() -> set[str]:
    codes = set(all_known_codes())
    for definitions in every_definitions():
        for _, _, kinds in getattr(definitions, "GUIDE_ISSUES", ()):
            codes.update(kind.code for kind in kinds)
    return codes


def help_text() -> str:
    names = [verb.name for verb in VERBS] + [tool.name for tool in TOOLS if tool.name != "python"]
    return "\n".join(subprocess.run([sys.executable, str(OFFICE_ENTRY), name, "--help"], capture_output=True, text=True).stdout for name in names)


class ReferenceNamesTest(unittest.TestCase):
    def test_every_command_the_documents_name_exists(self):
        commands = {verb.name for verb in VERBS} | {tool.name for tool in TOOLS}
        named = set(re.findall(r"(?:`|scripts/)office ([a-z]+)\b", documents_text()))
        self.assertEqual(named - commands, set())
        self.assertEqual(named & set(RETIRED_FORMATS), set())

    def test_every_issue_code_the_documents_name_exists(self):
        named = set(CODE_PATTERN.findall(documents_text()))
        self.assertEqual(named - guided_codes(), set())

    def test_every_layout_and_theme_the_documents_name_exists(self):
        text = documents_text()
        self.assertEqual(set(re.findall(r'data-layout="([a-z]+)"', text)) - set(KIT_LAYOUT_NAMES), set())
        self.assertEqual(set(re.findall(r'data-theme="([a-z]+)"', text)) - set(theme_names()), set())

    def test_every_guide_topic_the_documents_name_answers(self):
        for words in set(GUIDE_PATTERN.findall(documents_text())):
            topic = [word for word in words.split() if word]
            with self.subTest(topic=" ".join(topic)):
                guide_for(topic[:3])

    def test_every_flag_the_documents_name_is_a_command_flag_or_a_kit_token(self):
        known_flags = set(FLAG_PATTERN.findall(help_text())) | set(re.findall(r"(--[a-z][a-z0-9-]*):", KIT_STYLE))
        self.assertEqual(set(FLAG_PATTERN.findall(documents_text())) - known_flags, set())

    def test_every_form_a_document_names_exists_and_every_form_has_its_spec(self):
        named = set(FORM_PATTERN.findall(documents_text()))
        self.assertEqual(named - set(form_names()) - set(bundled_schema_names()), set())
        for name in form_names():
            self.assertTrue((OFFICE_PATH / "references" / "paperwork" / f"{name}.md").exists(), name)


if __name__ == "__main__":
    unittest.main()
