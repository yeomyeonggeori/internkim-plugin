# Employment Agreement

output: docx
filename: Employment_Agreement_<employee-name>_<YYYYMMDD>.docx

## Purpose

An editable draft agreement between the company ("Company") and an employee ("Employee") setting out the terms of employment, for review before execution.

## Required fields

- Company legal name, address, representative
- Employee name, address
- Term, position and duties, work hours, compensation, holidays and leave
- Governing law jurisdiction

## Document JSON skeleton

```json
{
  "title": "Employment Agreement",
  "page": { "marginInches": 0.9 },
  "blocks": [
    { "type": "paragraph", "text": "This Employment Agreement (\"Agreement\") is entered into by and between <company legal name> (\"Company\") and <employee name> (\"Employee\")." },
    { "type": "heading", "level": 2, "text": "1. Term" },
    { "type": "paragraph", "text": "This Agreement begins on <start date> and continues until <end date, or \"terminated in accordance with Section 7\">." },
    { "type": "heading", "level": 2, "text": "2. Position and Duties" },
    { "type": "paragraph", "text": "Employee shall serve as <position title> in the <department> department, reporting to <manager title>, and shall perform the duties customarily associated with that role and any other duties reasonably assigned by the Company." },
    { "type": "heading", "level": 2, "text": "3. Work Hours" },
    { "type": "paragraph", "text": "Employee's regular work hours are <start time> to <end time>, <days per week>, with a <duration> unpaid break, subject to the Company's policies and applicable law." },
    { "type": "heading", "level": 2, "text": "4. Compensation" },
    {
      "type": "table",
      "columnWidthsInches": [1.8, 4.2],
      "rows": [
        ["Item", "Detail"],
        ["Base salary", "<base salary amount and pay frequency>"],
        ["Additional pay", "<bonus/commission or not applicable>"],
        ["Payment method", "<direct deposit to employee-designated account>"]
      ]
    },
    { "type": "heading", "level": 2, "text": "5. Holidays and Leave" },
    { "type": "paragraph", "text": "Employee is entitled to holidays and paid leave in accordance with the Company's policies and applicable law in <jurisdiction>." },
    { "type": "heading", "level": 2, "text": "6. Confidentiality" },
    { "type": "paragraph", "text": "Employee shall not disclose the Company's confidential or proprietary information to any third party, during employment or thereafter, except as required by law." },
    { "type": "heading", "level": 2, "text": "7. Termination" },
    { "type": "paragraph", "text": "Either party may terminate this Agreement in accordance with <notice period / at-will provision, per jurisdiction> and applicable law." },
    { "type": "heading", "level": 2, "text": "8. Governing Law" },
    { "type": "paragraph", "text": "This Agreement is governed by the laws of <jurisdiction>, without regard to its conflict-of-laws principles." },
    { "type": "paragraph", "text": "IN WITNESS WHEREOF, the parties have executed this Agreement in two counterparts, each party retaining one, as of the date below." },
    { "type": "paragraph", "text": "<Month D, YYYY>" },
    { "type": "heading", "level": 2, "text": "Company" },
    {
      "type": "table",
      "columnWidthsInches": [1.5, 4.5],
      "rows": [
        ["Legal name", "<company legal name>"],
        ["Address", "<company address>"],
        ["Representative", "<representative name>, <representative title>  Signature: ____________________"]
      ]
    },
    { "type": "heading", "level": 2, "text": "Employee" },
    {
      "type": "table",
      "columnWidthsInches": [1.5, 4.5],
      "rows": [
        ["Name", "<employee name>  Signature: ____________________"],
        ["Address", "<employee address>"]
      ]
    }
  ]
}
```

## Fixed wording

- The preamble sentence and the "IN WITNESS WHEREOF" closing sentence are fixed and must always be included.
- Article numbers and titles follow the order above by default; if the requester adds or removes articles, renumber sequentially.

## Rules

- Term, position and duties, work hours, compensation, holidays and leave, and governing law are required articles; never omit them.
- Never invent names, salary figures, dates, or terms — use only requester-provided facts and ask when a required field is missing.
- This is a draft for legal review; final review by a qualified professional before execution is the company's responsibility.
