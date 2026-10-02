from __future__ import annotations

import html
import re


INVALID_XML_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def text_content(text: str) -> str:
    return html.escape(INVALID_XML_CHARACTERS.sub("", text), quote=False)
