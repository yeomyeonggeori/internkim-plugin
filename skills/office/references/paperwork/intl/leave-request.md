# Leave Request

output: pdf
filename: Leave_Request_<requester-name>_<YYYYMMDD>.pdf

## Purpose

An internal document by which an employee requests leave and routes it to the reviewer and approver for sign-off.

## Required fields

- approvalLine: ["Reviewed", "Approved"]
- meta: requester, department/title, leave type, leave period, reason, emergency contact
- Leave type uses whatever the requester states (annual, half-day, sick, family event, etc.) as-is
- signature: request date + requester's full name, stamp false

## Document JSON skeleton

```json
{
  "form": "intl/leave-request",
  "title": "Leave Request",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "approvalLine": ["Reviewed", "Approved"],
  "meta": [
    { "label": "Requester", "value": "<full name>" },
    { "label": "Department / Title", "value": "<department> / <title>" },
    { "label": "Leave type", "value": "<annual / half-day / sick / family event / other>" },
    { "label": "Leave period", "value": "<YYYY-MM-DD> to <YYYY-MM-DD> (<n> days)" },
    { "label": "Reason", "value": "<reason>" },
    { "label": "Emergency contact", "value": "<phone or other contact>" }
  ],
  "notes": ["I hereby request the leave described above."],
  "signature": { "date": "<Month D, YYYY>", "line": "Requester: <full name>", "stamp": false },
  "footer": ""
}
```

## Fixed wording

- notes: "I hereby request the leave described above."
- approvalLine is always fixed to two boxes: ["Reviewed", "Approved"].

## Rules

- Never invent names, amounts, durations, or governing law — use requester-provided facts and ask when requester name, leave type, leave period, or reason is missing.
- Calculate the number of days precisely from the start and end dates; if the company's rule for counting weekends or holidays is unclear, confirm with the requester rather than assuming.
- Leave requests never use a stamp — this is the requester's own signature, so signature.stamp is always false.
