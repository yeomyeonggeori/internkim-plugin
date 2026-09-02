# Internal Approval Request

output: pdf
filename: approval-request_<subject-slug>_<YYYYMMDD>.pdf

## Purpose

An internal document requesting management sign-off on a proposed action, purchase, or plan before it proceeds. The requester, subject, and details must be confirmed facts; this is a request for a decision, not a record of one already made.

## Required fields

- approvalLine: ["Prepared", "Reviewed", "Approved"] unless the requester specifies a different chain
- meta: requester (with team), date, subject
- sections: 1. Purpose, 2. Details (use an items table when amounts are involved), 3. Expected impact
- notes: "Submitted for your approval."

## Document JSON skeleton

```json
{
  "title": "Internal Approval Request",
  "documentNumber": "AR-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "approvalLine": ["Prepared", "Reviewed", "Approved"],
  "meta": [
    { "label": "Requester", "value": "<name>, <team>" },
    { "label": "Date", "value": "<YYYY-MM-DD>" },
    { "label": "Subject", "value": "<subject>" }
  ],
  "sections": [
    { "title": "1. Purpose", "paragraphs": ["<why this approval is being requested>"] },
    { "title": "2. Details", "paragraphs": ["<description of the proposed action or plan>"] },
    { "title": "3. Expected impact", "paragraphs": ["<expected outcome, benefit, or risk>"] }
  ],
  "items": {
    "headers": ["Item", "Description", "Amount"],
    "aligns": ["L", "L", "R"],
    "rows": [["<item>", "<description>", "<amount>"]],
    "totals": [{ "label": "Total", "value": "<amount> <currency>" }]
  },
  "notes": ["Submitted for your approval."],
  "signature": { "date": "<Month D, YYYY>", "line": "<requester name>", "stamp": false },
  "footer": ""
}
```

## Fixed wording

- notes: "Submitted for your approval."
- Omit the `items` field entirely when the request does not involve amounts; do not leave an empty items table.

## Rules

- Use thousands separators for all amounts and state the currency the requester provides. Always state whether tax/VAT is included when amounts are shown.
- Keep section 2 (Details) as plain paragraphs when no amounts are involved; switch to the items table only when line items or costs are part of the request.
- Never invent names, amounts, dates, attendees, or decisions — use only requester-provided facts and ask when a required field is missing.
- Do not fill in approval outcomes or signatures on behalf of approvers; approvalLine boxes stay empty for the approvers to complete.
