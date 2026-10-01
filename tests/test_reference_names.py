from pathlib import Path
import re
import subprocess
import sys
import unittest

from test_office_results import OFFICE_ENTRY, OFFICE_PATH, all_known_codes, load_definitions

from core.office_commands import COMMANDS, FORMATS, find_format  # noqa: E402
from office_guide import guide_text  # noqa: E402


from deck.deck_definitions import KIT_LAYOUT_NAMES  # noqa: E402
from deck.deck_kit import theme_names  # noqa: E402
from paperwork.paperwork_definitions import form_slugs  # noqa: E402


DOCUMENTS = (OFFICE_PATH / "SKILL.md", *sorted((OFFICE_PATH / "references").rglob("*.md")))
CODE_PATTERN = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")
GUIDE_PATTERN = re.compile(r"office guide ([a-z]+)((?: [a-z_]+)*)")
FLAG_PATTERN = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*[a-z0-9])")
KIT_STYLE = (OFFICE_PATH / "assets" / "deck-kit" / "deck-kit.css").read_text(encoding="utf-8")
SPEC_PATTERN = re.compile(r"references/paperwork/<ko\|en>/<slug>\.md|references/paperwork/(?:ko|en)/([a-z-]+)\.md")


def documents_text() -> str:
    return "\n".join(document.read_text(encoding="utf-8") for document in DOCUMENTS)


def guided_codes() -> set[str]:
    codes = set(all_known_codes())
    for office_format in FORMATS:
        for _, kinds in getattr(load_definitions(office_format), "GUIDE_ISSUES", ()):
            codes.update(kind.code for kind in kinds)
    return codes


def command_help_text() -> str:
    texts = []
    for command in COMMANDS:
        completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *command.words, "--help"], capture_output=True, text=True)
        texts.append(completed.stdout)
    return "\n".join(texts)


class ReferenceNamesTest(unittest.TestCase):
    def test_every_issue_code_the_documents_name_exists(self):
        named = set(CODE_PATTERN.findall(documents_text()))
        self.assertEqual(named - guided_codes(), set())

    def test_every_layout_and_theme_the_documents_name_exists(self):
        text = documents_text()
        self.assertEqual(set(re.findall(r'data-layout="([a-z]+)"', text)) - set(KIT_LAYOUT_NAMES), set())
        self.assertEqual(set(re.findall(r'data-theme="([a-z]+)"', text)) - set(theme_names()), set())

    def test_every_guide_topic_the_documents_name_answers(self):
        for format_name, words in set(GUIDE_PATTERN.findall(documents_text())):
            topic = [word for word in words.split() if word]
            with self.subTest(topic=" ".join([format_name, *topic])):
                guide_text(find_format(format_name), *topic[:2])

    def test_every_flag_the_documents_name_is_a_command_flag_or_a_kit_token(self):
        known_flags = set(FLAG_PATTERN.findall(command_help_text())) | set(re.findall(r"(--[a-z][a-z0-9-]*):", KIT_STYLE))
        self.assertEqual(set(FLAG_PATTERN.findall(documents_text())) - known_flags, set())

    def test_every_paperwork_spec_a_document_names_exists(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in (OFFICE_PATH / "references").rglob("*.md"))
        named = {slug for slug in SPEC_PATTERN.findall(text) if slug}
        self.assertEqual(named - set(form_slugs()), set())
        for slug in form_slugs():
            self.assertTrue((OFFICE_PATH / "references" / "paperwork" / "en" / f"{slug}.md").exists(), slug)


if __name__ == "__main__":
    unittest.main()
