# Business Trip Report

output: pdf
filename: business-trip-report_<traveler>_<YYYYMMDD>.pdf

## Purpose

An internal document reporting the outcomes of a completed business trip, submitted by the traveler for the record and, when relevant, expense reimbursement. The destination, period, purpose, and any expense amounts must be confirmed facts.

## Required fields

- meta: traveler, destination, period, purpose
- sections: 1. Summary, 2. Key outcomes, 3. Follow-ups
- items (optional): Description, Amount (right-aligned) with total, only when expenses are reported
- signature: traveler

## Document JSON skeleton

```json
{
  "title": "Business Trip Report",
  "documentNumber": "BTR-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "Traveler", "value": "<name>" },
    { "label": "Destination", "value": "<destination>" },
    { "label": "Period", "value": "<YYYY-MM-DD to YYYY-MM-DD>" },
    { "label": "Purpose", "value": "<purpose>" }
  ],
  "sections": [
    { "title": "1. Summary", "paragraphs": ["<trip summary>"] },
    { "title": "2. Key outcomes", "bullets": ["<outcome 1>", "<outcome 2>"] },
    { "title": "3. Follow-ups", "bullets": ["<follow-up 1>"] }
  ],
  "items": {
    "headers": ["Description", "Amount"],
    "aligns": ["L", "R"],
    "rows": [["<expense description>", "<amount>"]],
    "totals": [{ "label": "Total", "value": "<amount> <currency>" }]
  },
  "signature": { "date": "<Month D, YYYY>", "line": "<traveler name>", "stamp": false }
}
```

## Fixed wording

- None. Omit the `items` field entirely when no expenses are being reported through this document; do not leave an empty table.

## Rules

- Use thousands separators for all expense amounts and state the currency the requester provides. Always state whether tax/VAT is included.
- The period must reflect the actual travel dates as stated by the requester, not inferred from the report submission date.
- Never invent names, amounts, dates, attendees, or decisions — use only requester-provided facts and ask when a required field is missing.
- Do not set `approvalLine`; use this document alongside a separate expense-approval document if reimbursement approval is also needed.
