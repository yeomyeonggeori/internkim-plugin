#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

from skill_runtime import ensure_requirements

TEMPLATE_CONTEXTS = {
    "employment-contract": {
        "required": ["companyName", "companyPhone", "companyAddress", "representative", "employeeName",
                     "startDate", "workplace", "duties", "workStartTime", "workEndTime", "breakStart",
                     "breakEnd", "workDays", "weeklyHoliday", "monthlySalary", "bonus", "payday",
                     "paymentMethod", "contractDate"],
        "optional": ["endDate", "employeeAddress", "employeePhone", "otherAllowances", "insurances"],
        "lists": [],
        "defaults": {"otherAllowances": "없음", "insurances": "☑ 고용보험  ☑ 산재보험  ☑ 국민연금  ☑ 건강보험",
                     "employeeAddress": "", "employeePhone": "", "endDate": ""},
    },
    "service-agreement": {
        "required": ["clientName", "clientAddress", "clientRepresentative", "providerName", "providerAddress",
                     "providerRepresentative", "serviceName", "startDate", "endDate", "totalAmount",
                     "totalAmountKorean", "vatNote", "bankAccount", "penaltyRate", "warrantyMonths",
                     "jurisdiction", "contractDate"],
        "optional": [],
        "lists": ["scopeItems", "payments", "deliverables"],
        "defaults": {"penaltyRate": "1.25", "warrantyMonths": "3"},
    },
    "nda": {
        "required": ["partyAName", "partyAAddress", "partyARepresentative", "partyBName", "partyBAddress",
                     "partyBRepresentative", "purpose", "termYears", "survivalYears", "jurisdiction", "contractDate"],
        "optional": ["penaltyAmount"],
        "lists": [],
        "defaults": {"termYears": "5", "survivalYears": "3", "penaltyAmount": ""},
    },
    "mou": {
        "required": ["orgAName", "orgARepresentative", "orgBName", "orgBRepresentative", "purpose",
                     "termYears", "contractDate"],
        "optional": [],
        "lists": ["cooperationItems", "orgARoles", "orgBRoles"],
        "defaults": {"termYears": "2"},
    },
    "offer-letter": {
        "required": ["companyName", "representative", "candidateName", "position", "department", "workplace",
                     "startDate", "salary", "expiryDate", "offerDate"],
        "optional": ["equity", "probationNote"],
        "lists": ["benefits"],
        "defaults": {"equity": "", "probationNote": ""},
    },
}


def context_hint(template_name):
    manifest = TEMPLATE_CONTEXTS[template_name]
    fields = {field: "<값>" for field in manifest["required"]}
    fields.update({field: ["<항목>"] for field in manifest["lists"]})
    return f"context JSON for {template_name} must contain: {json.dumps(fields, ensure_ascii=False)}"


def load_context(template_name, context_path):
    with open(context_path, "r", encoding="utf-8") as context_file:
        context = json.load(context_file)
    if not isinstance(context, dict):
        raise ValueError(f"context must be a JSON object; {context_hint(template_name)}")
    manifest = TEMPLATE_CONTEXTS[template_name]
    for field, default in manifest["defaults"].items():
        context.setdefault(field, default)
    missing = [field for field in manifest["required"] if str(context.get(field, "")).strip() == ""]
    for list_field in manifest["lists"]:
        value = context.get(list_field)
        if not isinstance(value, list) or not value:
            missing.append(f"{list_field} (non-empty array)")
    if missing:
        raise ValueError(f"missing context fields {missing}; fill EVERY field — use \"미정\" only when the requester truly did not provide the value. {context_hint(template_name)}")
    return context


def main():
    parser = argparse.ArgumentParser(description="Fill a bundled standard-form DOCX template with a context JSON.")
    parser.add_argument("template_name", choices=sorted(TEMPLATE_CONTEXTS), help="Template name")
    parser.add_argument("context_path", help="Path to the context JSON file")
    parser.add_argument("output_path", help="Path to the output .docx file")
    arguments = parser.parse_args()
    if not ensure_requirements("paperwork"):
        raise RuntimeError("paperwork dependencies are unavailable after bootstrap")
    template_path = Path(__file__).resolve().parent.parent / "assets" / "templates" / f"{arguments.template_name}.docx"
    output_path = Path(os.path.expanduser(arguments.output_path))
    try:
        context = load_context(arguments.template_name, os.path.expanduser(arguments.context_path))
        from docxtpl import DocxTemplate
        template = DocxTemplate(str(template_path))
        template.render(context)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template.save(str(output_path))
    except FileNotFoundError as missing_file:
        print(f"paperwork template error: {missing_file}; write the context JSON with write first", file=sys.stderr)
        raise SystemExit(1)
    except PermissionError:
        print(f"paperwork template error: cannot write to {output_path} (permission denied); rerun the SAME command with the output changed to ~/documents/{output_path.parent.name}/{output_path.name}", file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, json.JSONDecodeError) as validation_error:
        print(f"paperwork template error: {validation_error}", file=sys.stderr)
        raise SystemExit(1)
    print(output_path)


if __name__ == "__main__":
    main()
