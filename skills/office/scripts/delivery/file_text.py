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
    if path in blanked:
        return BLANK
    kept = [piece for index, piece in enumerate(sentences(text)) if f"{path}{PIECE_MARK}{index}" not in blanked]
    return " ".join(kept) or BLANK


def cell_claims(rows: list, path: str, at: str) -> list[Claim]:
    return [claim for row_index, row in enumerate(rows) for column_index, cell in enumerate(row) if cell not in (None, "") for claim in pieces_of(str(cell), f"{path}/{row_index}/{column_index}", at)]


def docx_claims(file_path: Path) -> list[Claim]:
    claims, at = [], ""
    for block in office("read", str(file_path), "--limit", READ_LIMIT).get("details", {}).get("blocks", []):
        if block.get("kind") == "heading":
            at = block.get("text") or at
        if block.get("kind") == "table":
            claims += cell_claims(block.get("cells") or [], f"docx/{block['index']}", at or "table")
        elif block.get("text"):
            claims += pieces_of(block["text"], f"docx/{block['index']}", at or block["text"])
    return claims


def docx_operations(file_path: Path, claims: list[Claim]) -> list[dict]:
    blanked = {claim.path for claim in claims}
    operations = []
    for block in office("read", str(file_path), "--limit", READ_LIMIT).get("details", {}).get("blocks", []):
        path = f"docx/{block['index']}"
        if block.get("kind") == "table":
            operations += [{"op": "set_cell", "block": block["index"], "row": row, "column": column, "text": without_pieces(str(cell), blanked, f"{path}/{row}/{column}")}
                           for row, cells in enumerate(block.get("cells") or []) for column, cell in enumerate(cells) if touches(blanked, f"{path}/{row}/{column}")]
        elif block.get("text") and touches(blanked, path):
            operations.append({"op": "set_text", "block": block["index"], "text": without_pieces(block["text"], blanked, path)})
    return operations


def touches(blanked: set[str], path: str) -> bool:
    return path in blanked or any(item.startswith(path + PIECE_MARK) for item in blanked)


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
        operations += [{"op": "set_table_cell", "slide": slide, "shape": str(shape["index"]), "row": row, "column": column, "text": without_pieces(str(cell), blanked, f"{path}/{row}/{column}")}
                       for row, cells in enumerate(shape.get("rows") or []) for column, cell in enumerate(cells) if touches(blanked, f"{path}/{row}/{column}")]
        if shape.get("text") and touches(blanked, path):
            operations.append({"op": "set_text", "slide": slide, "shape": str(shape["index"]), "text": without_pieces(shape["text"], blanked, path)})
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
