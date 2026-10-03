# Expense Approval

output: pdf
filename: expense-approval_<requester>_<YYYYMMDD>.pdf

## Purpose

An internal document requesting approval to reimburse or process an expense already incurred or about to be incurred. The requester, expense date, department, and amounts must be confirmed facts.

## Required fields

- approvalLine: the approvers the request names, in its order, each `{"role", "name"}`; when it names none, the roles "Prepared", "Reviewed", "Approved" without names
- meta: requester, expense date, department, payment method (corporate card / bank transfer)
- items: one row per account the spending is booked to, with Account, Description, Vendor, Amount (before tax) and Tax, amounts right-aligned; a row without tax writes 0 as its Tax
- items.totals: Subtotal, Tax, Total, in that order
- notes: whether receipts/tax invoices are attached

## Document JSON skeleton

```json
{
  "form": "intl/expense-approval",
  "title": "Expense Approval",
  "documentNumber": "<the number company_document_register returned>",
  "company": "<the company-profile.json path company_info_get answered>",
  "approvalLine": [{ "role": "<role>", "name": "<name>" }],
  "meta": [
    { "label": "Requester", "value": "<name>" },
    { "label": "Expense date", "value": "<YYYY-MM-DD>" },
    { "label": "Department", "value": "<department>" },
    { "label": "Payment method", "value": "<corporate card | bank transfer>" }
  ],
  "items": {
    "headers": ["Account", "Description", "Vendor", "Amount", "Tax"],
    "aligns": ["L", "L", "L", "R", "R"],
    "rows": [["<account>", "<description>", "<vendor>", "<amount before tax>", "<tax>"]],
    "totals": [
      { "label": "Subtotal", "value": "<subtotal> <currency>" },
      { "label": "Tax", "value": "<tax total> <currency>" },
      { "label": "Total", "value": "<total> <currency>" }
    ]
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
- Subtotal and Tax are the sums of the rows and Total is their sum; `office check` reports any that are not, at the tax rate the values state in taxRatePercent.
