from __future__ import annotations

from schemas.claims import listed, text_claims


def declaration_claims(declaration: dict) -> list[dict]:
    claims = list(text_claims("text", declaration.get("title"), "title", ("workbook title",)))
    for table_index, table in enumerate(listed(declaration.get("tables"))):
        claims += table_cell_claims(table, f"tables[{table_index}]")
    for chart_index, chart in enumerate(listed(declaration.get("charts"))):
        claims += text_claims("text", chart.get("title"), f"charts[{chart_index}].title", ("chart title",))
    return claims


def table_cell_claims(table: dict, location: str) -> list[dict]:
    columns = [column for column in listed(table.get("columns")) if isinstance(column, dict)]
    claims = []
    for row_index, row in enumerate(listed(table.get("rows"))):
        for cell_index, cell in enumerate(listed(row)):
            column = columns[cell_index] if cell_index < len(columns) else {}
            names = (str(table.get("name") or ""), str(column.get("name") or ""))
            claims += text_claims(column.get("type") or "text", cell, f"{location}.rows[{row_index}][{cell_index}]", names)
    return claims
