from __future__ import annotations


def parse_front_matter(design_document_text: str) -> dict[str, str | dict[str, str]]:
    document: dict[str, str | dict[str, str]] = {}
    section = ""
    for raw_line in design_front_matter(design_document_text).splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), unquoted(value)
        if not line.startswith((" ", "\t")):
            section = key if not value else ""
            document[key] = {} if not value else value
        elif section and isinstance(document.get(section), dict) and value:
            document[section][key] = value
    return document


def read_design_tokens(design_document_text: str) -> dict[str, str]:
    tokens = {}
    for key, value in parse_front_matter(design_document_text).items():
        if isinstance(value, dict):
            tokens.update({f"{key}.{name}": entry for name, entry in value.items()})
        elif value:
            tokens[key] = value
    return tokens


def unquoted(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def design_front_matter(design_document_text: str) -> str:
    if not design_document_text.startswith("---"):
        return ""
    parts = design_document_text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]
