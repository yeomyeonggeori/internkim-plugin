from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree

from core.template_merge import placeholder_paths
from paperwork.forms import TEMPLATES_ROOT


TEMPLATES_PATH = TEMPLATES_ROOT / "kr"
WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TEMPLATE_PARTS = re.compile(r"word/(document|header\d*|footer\d*)\.xml")


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


def template_fields(template_name: str) -> list[str]:
    return sorted({path.split(".", 1)[0] for paragraph in template_paragraphs(template_name) for path in placeholder_paths(paragraph)})
