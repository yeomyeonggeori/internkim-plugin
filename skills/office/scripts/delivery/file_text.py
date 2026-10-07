from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from delivery.claim_kinds import Claim
from schemas.claims import sentences
from schemas.typed_values import BLANK

OFFICE_ENTRY = Path(__file__).resolve().parents[1] / "office"
REMAKE_VARIABLE = "OFFICE_IS_REMAKE"
READ_LIMIT = "100000"
PIECE_MARK = "#"
FIELD_SEPARATORS = (":", "：")
FIELD_LABEL_LIMIT = 12
PAGE_PARTS = ("header", "footer")


def text_claims(file_path: Path) -> list[Claim]:
    reader = READERS.get(file_path.suffix.lower())
    return reader(file_path) if reader else []


def blank_in_place(file_path: Path, claims: list[Claim]) -> bool:
    editor = EDITORS.get(file_path.suffix.lower())
    if editor is None:
        return False
    operations = editor(file_path, claims)
    return not operations or office_apply(file_path, operations)


def office(*words: str) -> dict:
    environment = {**os.environ, REMAKE_VARIABLE: "1"}
    completed = subprocess.run([sys.executable, str(OFFICE_ENTRY), *words], capture_output=True, text=True, env=environment)
    return json.loads(completed.stdout or "{}")


def office_apply(file_path: Path, operations: list[dict]) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(operations, handle, ensure_ascii=False)
    try:
        return office("apply", str(file_path), handle.name, "--mode", "best-effort").get("status") != "error"
    finally:
        os.unlink(handle.name)


def pieces_of(text: str, path: str, at: str) -> list[Claim]:
    pieces = sentences(text)
    if len(pieces) <= 1:
        return [Claim(path=path, text=text.strip(), at=at)] if text.strip() else []
    return [Claim(path=f"{path}{PIECE_MARK}{index}", text=piece, at=at) for index, piece in enumerate(pieces)]


def without_pieces(text: str, blanked: set[str], path: str) -> str:
    kept = [] if path in blanked else [piece for index, piece in enumerate(sentences(text)) if f"{path}{PIECE_MARK}{index}" not in blanked]
    return " ".join(kept)


def field_label(text: str) -> str:
    for separator in FIELD_SEPARATORS:
        label, found, value = text.partition(separator)
        if found and value.strip() and 0 < len(label.strip()) <= FIELD_LABEL_LIMIT and "\n" not in label:
            return label.strip()
    return ""


def emptied_line(text: str) -> str:
    label = field_label(text)
    return f"{label}: {BLANK}" if label else ""


def cell_claims(rows: list, path: str, at: str) -> list[Claim]:
    return [claim for row_index, row in enumerate(rows) for column_index, cell in enumerate(row) if cell not in (None, "") for claim in pieces_of(str(cell), f"{path}/{row_index}/{column_index}", at)]


def cell_text(text: str, blanked: set[str], path: str) -> str:
    return without_pieces(text, blanked, path) or BLANK


def read_docx(file_path: Path) -> dict:
    return office("read", str(file_path), "--limit", READ_LIMIT).get("details", {})


def docx_claims(file_path: Path) -> list[Claim]:
    details = read_docx(file_path)
    claims, at = [], ""
    for block in details.get("blocks", []):
        if block.get("kind") == "heading":
            at = block.get("text") or at
        if block.get("kind") == "table":
            claims += cell_claims(block.get("cells") or [], f"docx/{block['index']}", at or "table")
        elif block.get("text"):
            claims += pieces_of(block["text"], f"docx/{block['index']}", at or block["text"])
    for section in owned_page_parts(details):
        claims += pieces_of(section["text"], section["path"], section["part"])
    for chart in details.get("charts") or []:
        claims += [Claim(path=f"{chart_path(chart)}/{index}", text=value, at=chart.get("title") or "chart") for index, value in enumerate(chart_values(chart))]
    return claims


def owned_page_parts(details: dict) -> list[dict]:
    parts = []
    for section in details.get("sections") or []:
        for part in PAGE_PARTS:
            is_own = section["index"] == 0 or not section.get(f"{part}LinkedToPrevious")
            if is_own and section.get(part):
                parts.append({"part": part, "section": section["index"], "text": section[part], "path": f"docx/{part}/{section['index']}"})
    return parts


def chart_path(chart: dict) -> str:
    return f"docx/chart/{chart['chart']}"


def chart_values(chart: dict) -> list[str]:
    categories = chart.get("categories") or []
    return [" ".join(str(part) for part in (category, series.get("name"), value) if part not in (None, "")) for series in chart.get("series") or [] for category, value in zip(categories, series.get("values") or [])]


def docx_operations(file_path: Path, claims: list[Claim]) -> list[dict]:
    blanked = {claim.path for claim in claims}
    details = read_docx(file_path)
    operations = body_operations(details.get("blocks", []), blanked)
    operations += [{"op": f"set_{part['part']}", "section": part["section"], "text": without_pieces(part["text"], blanked, part["path"])} for part in owned_page_parts(details) if touches(blanked, part["path"])]
    operations += [{"op": "delete_chart", "chart": chart["chart"]} for chart in details.get("charts") or [] if touches(blanked, chart_path(chart))]
    return operations


def body_operations(blocks: list[dict], blanked: set[str]) -> list[dict]:
    operations, texts = [], {}
    for block in blocks:
        path = f"docx/{block['index']}"
        if block.get("kind") == "table":
            operations += [{"op": "set_cell", "block": block["index"], "row": row, "column": column, "text": cell_text(str(cell), blanked, f"{path}/{row}/{column}")}
                           for row, cells in enumerate(block.get("cells") or []) for column, cell in enumerate(cells) if touches(blanked, f"{path}/{row}/{column}")]
        elif block.get("text") and touches(blanked, path):
            texts[block["index"]] = without_pieces(block["text"], blanked, path) or emptied_line(block["text"]) if block.get("kind") != "heading" else without_pieces(block["text"], blanked, path)
    for slot in fill_slots(blocks, texts):
        texts[slot] = BLANK
    operations += [{"op": "set_text", "block": index, "text": text} for index, text in texts.items() if text]
    operations += [{"op": "delete_block", "block": index} for index, text in texts.items() if not text]
    return operations


def fill_slots(blocks: list[dict], texts: dict[int, str]) -> list[int]:
    slots = []
    for heading, body in sections_of(blocks):
        if texts.get(heading["index"], heading.get("text")) and body and all(texts.get(block["index"], block.get("text") or "x") == "" for block in body if is_text_block(block)) and any(block["index"] in texts for block in body):
            slots.append(next(block["index"] for block in body if block["index"] in texts))
    return slots


def sections_of(blocks: list[dict]) -> list[tuple[dict, list[dict]]]:
    sections = []
    for block in blocks:
        if block.get("kind") == "heading":
            sections.append((block, []))
        elif sections and block.get("kind") != "table":
            sections[-1][1].append(block)
        elif sections:
            sections[-1][1].append(block | {"isTable": True})
    return [(heading, body) for heading, body in sections if not any(block.get("isTable") for block in body)]


def is_text_block(block: dict) -> bool:
    return bool(block.get("text"))


def touches(blanked: set[str], path: str) -> bool:
    return path in blanked or any(item.startswith(path + PIECE_MARK) or item.startswith(path + "/") for item in blanked)


def pptx_shapes(file_path: Path):
    for slide in office("read", str(file_path)).get("details", {}).get("slides", []):
        yield from flattened(slide["slide"], slide.get("shapes") or [])


def flattened(slide: int, shapes: list):
    for shape in shapes:
        yield slide, shape
        yield from flattened(slide, shape.get("shapes") or [])


def pptx_claims(file_path: Path) -> list[Claim]:
    claims = []
    for slide, shape in pptx_shapes(file_path):
        path, at = f"pptx/{slide}/{shape['index']}", f"slide {slide}"
        claims += cell_claims(shape.get("rows") or [], path, at) + (pieces_of(shape["text"], path, at) if shape.get("text") else [])
    return claims


def pptx_operations(file_path: Path, claims: list[Claim]) -> list[dict]:
    blanked = {claim.path for claim in claims}
    operations = []
    for slide, shape in pptx_shapes(file_path):
        path = f"pptx/{slide}/{shape['index']}"
        operations += [{"op": "set_table_cell", "slide": slide, "shape": str(shape["index"]), "row": row, "column": column, "text": cell_text(str(cell), blanked, f"{path}/{row}/{column}")}
                       for row, cells in enumerate(shape.get("rows") or []) for column, cell in enumerate(cells) if touches(blanked, f"{path}/{row}/{column}")]
        if shape.get("text") and touches(blanked, path):
            text = without_pieces(shape["text"], blanked, path) or emptied_line(shape["text"])
            operations.append({"op": "set_text", "slide": slide, "shape": str(shape["index"]), "text": text} if text else {"op": "delete_shape", "slide": slide, "shape": str(shape["index"])})
    return operations


def xlsx_cells(file_path: Path):
    for sheet in office("read", str(file_path)).get("details", {}).get("sheets", []):
        for kind in ("text", "number"):
            for cell in office("read", str(file_path), "--sheet", sheet["name"], "--where", kind, "--limit", READ_LIMIT).get("details", {}).get("range", {}).get("cells", []):
                if not cell.get("formula"):
                    yield sheet["name"], cell


def xlsx_claims(file_path: Path) -> list[Claim]:
    return [Claim(path=f"xlsx/{sheet}/{cell['cell']}", text=str(cell["value"]), at=f"{sheet} {cell['cell']}") for sheet, cell in xlsx_cells(file_path)]


def xlsx_operations(file_path: Path, claims: list[Claim]) -> list[dict]:
    operations = []
    for claim in claims:
        _, sheet, cell = claim.path.split("/", 2)
        operations.append({"op": "set_cell", "sheet": sheet, "cell": cell, "value": None})
    return operations


def pdf_claims(file_path: Path) -> list[Claim]:
    claims = []
    for page in office("read", str(file_path), "--limit", READ_LIMIT).get("details", {}).get("pages", []):
        lines = [line.strip() for line in (page.get("text") or "").splitlines() if line.strip()]
        claims += [Claim(path=f"pdf/{page['page']}/{index}", text=line, at=f"page {page['page']}") for index, line in enumerate(lines)]
    return claims


READERS = {".docx": docx_claims, ".pptx": pptx_claims, ".xlsx": xlsx_claims, ".pdf": pdf_claims}
EDITORS = {".docx": docx_operations, ".pptx": pptx_operations, ".xlsx": xlsx_operations}
