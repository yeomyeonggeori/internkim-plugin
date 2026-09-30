from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree


TEMPLATES_PATH = Path(__file__).resolve().parents[2] / "assets" / "templates"
WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TEMPLATE_PARTS = re.compile(r"word/(document|header\d*|footer\d*)\.xml")
TAG_PATTERN = re.compile(r"\{\{(.*?)\}\}|\{%-?p?\s*(.*?)\s*-?%\}")
FOR_PATTERN = re.compile(r"for\s+(\w+)\s+in\s+(\w+)")
IDENTIFIER_PATTERN = re.compile(r"(?<![\w.])[A-Za-z_]\w*")
RESERVED_WORDS = {"if", "elif", "else", "endif", "endfor", "for", "in", "not", "and", "or", "loop", "true", "false", "none"}


def template_names() -> list[str]:
    return sorted(path.stem for path in TEMPLATES_PATH.glob("*.docx"))


def template_paragraphs(template_name: str) -> list[str]:
    with zipfile.ZipFile(TEMPLATES_PATH / f"{template_name}.docx") as archive:
        parts = [name for name in archive.namelist() if TEMPLATE_PARTS.fullmatch(name)]
        roots = [ElementTree.fromstring(archive.read(name)) for name in parts]
    return [
        "".join(text.text or "" for text in paragraph.iter(f"{WORD_NAMESPACE}t"))
        for root in roots
        for paragraph in root.iter(f"{WORD_NAMESPACE}p")
    ]


def template_tags(template_name: str) -> list[str]:
    return [
        expression.strip() or statement
        for paragraph in template_paragraphs(template_name)
        for expression, statement in TAG_PATTERN.findall(paragraph)
    ]


def template_list_fields(template_name: str) -> list[str]:
    loops = [FOR_PATTERN.fullmatch(tag) for tag in template_tags(template_name)]
    return sorted({loop.group(2) for loop in loops if loop})


def template_fields(template_name: str) -> list[str]:
    tags = template_tags(template_name)
    loop_variables = {loop.group(1) for loop in map(FOR_PATTERN.fullmatch, tags) if loop}
    identifiers = {
        identifier
        for tag in tags
        for identifier in IDENTIFIER_PATTERN.findall(FOR_PATTERN.sub(lambda loop: loop.group(2), tag))
    }
    return sorted(identifiers - RESERVED_WORDS - loop_variables)
