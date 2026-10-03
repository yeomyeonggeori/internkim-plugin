#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from core.office_arguments import route_arguments
from core.office_result import Result, run_command
from schemas.company_forms import docx_form_fields, xlsx_form_fields


FORM_READERS = {".docx": ("docx-form", docx_form_fields), ".xlsx": ("xlsx-form", xlsx_form_fields)}
TYPING_GUIDANCE = "Set each field once, then keep this file beside the form: type is text, person, organization, date, amount, quantity, percent handwritten (left for a pen, such as a signature box) or ignore (not a field, such as a printed note); a field the runtime knows gets known: requester, today, document.number or company.<field>; a field computed from others gets expression, such as items.quantity * items.price or sum(items.amount)."


def main() -> Result:
    arguments = route_arguments("convert")
    form_path = Path(arguments.input).expanduser().resolve()
    output_path = Path(arguments.output).expanduser()
    kind, read_fields = FORM_READERS[form_path.suffix.lower()]
    fields = read_fields(str(form_path))
    schema = {"name": output_path.name.removesuffix(".schema.json"), "kind": kind, "template": str(form_path), "language": "ko", "summary": f"the fields of {form_path.name}", "guidance": TYPING_GUIDANCE, "fields": fields}
    output_path.write_text(json.dumps(schema, ensure_ascii=False, indent=1), encoding="utf-8")
    labels = ", ".join(field["label"] for field in fields)
    return Result(summary=f"found {len(fields)} fields in {form_path.name}: {labels}; set each field's type in {output_path} once", output_path=str(output_path), details={"fields": [field["label"] for field in fields]})


if __name__ == "__main__":
    raise SystemExit(run_command(main))
