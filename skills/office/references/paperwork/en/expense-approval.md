# Expense Approval

output: pdf
filename: expense-approval_<requester>_<YYYYMMDD>.pdf

## Purpose

An internal document requesting approval to reimburse or process an expense already incurred or about to be incurred. The requester, expense date, department, and amounts must be confirmed facts.

## Required fields

- approvalLine: ["Prepared", "Reviewed", "Approved"] unless the requester specifies a different chain
- meta: requester, expense date, department, payment method (corporate card / bank transfer)
- items: Description, Vendor, Amount (right-aligned); at least one row
- items.totals: total amount requested
- notes: whether receipts/tax invoices are attached

## Document JSON skeleton

```json
{
  "title": "Expense Approval",
  "documentNumber": "EA-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "approvalLine": ["Prepared", "Reviewed", "Approved"],
  "meta": [
    { "label": "Requester", "value": "<name>" },
    { "label": "Expense date", "value": "<YYYY-MM-DD>" },
    { "label": "Department", "value": "<department>" },
    { "label": "Payment method", "value": "<corporate card | bank transfer>" }
  ],
  "items": {
    "headers": ["Description", "Vendor", "Amount"],
    "aligns": ["L", "L", "R"],
    "rows": [["<description>", "<vendor>", "<amount>"]],
    "totals": [{ "label": "Total", "value": "<amount> <currency>" }]
  },
  "notes": ["Receipts and tax invoices attached."],
  "signature": { "date": "<Month D, YYYY>", "line": "<requester name>", "stamp": false }
}
```

## Fixed wording

- notes: state plainly whether receipts/tax invoices are attached, e.g. "Receipts and tax invoices attached." or "No receipts attached; expense reported on the honor system." Use the wording that matches the requester's actual situation.

## Rules

- Use thousands separators for all amounts and state the currency the requester provides. Always state whether tax/VAT is included in each amount.
- Record the payment method exactly as stated (corporate card or bank transfer); never assume one when the requester has not said which was used.
- Never invent names, amounts, dates, attendees, or decisions — use only requester-provided facts and ask when a required field is missing.
- Verify the total matches the sum of the item rows before filling the skeleton.
