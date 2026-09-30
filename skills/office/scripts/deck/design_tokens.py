def read_design_tokens(design_document_text: str) -> dict[str, str]:
    front_matter = design_front_matter(design_document_text)
    tokens = {}
    section = ""
    for raw_line in front_matter.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            continue
        if not section or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            tokens[section + "." + key] = value
    return tokens


def design_front_matter(design_document_text: str) -> str:
    if not design_document_text.startswith("---"):
        return ""
    parts = design_document_text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]
