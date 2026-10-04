# Statement of Delivered Goods and Services

output: pdf
filename: transaction-statement_<customer>_<YYYYMMDD>.pdf

## Purpose

An external document confirming goods or services already supplied to a customer, issued after delivery so both sides have a matching record of what was provided and for how much. The supplier, customer, transaction date, and line items must be confirmed facts.

## Required fields

- recipient: customer company name required, contact name if provided
- meta: transaction date, payment terms if applicable
- items: at least one row; description, quantity, unit price, and amount only as supplied by the requester
- items.totals: subtotal → VAT (or "no VAT applicable") → total, in that order
- notes: receiver-confirmation convention, e.g. "Received and confirmed as accurate."
- signature: issue date + "<companyName> <representative name>", stamp true

## Document JSON skeleton

```json
{
  "form": "intl/transaction-statement",
  "title": "Statement of Delivered Goods and Services",
  "documentNumber": "<the number company_document_register returned>",
  "recipient": { "label": "To", "lines": ["<customer company name>", "Attn: <contact name>"] },
  "meta": [
    { "label": "Transaction date", "value": "<YYYY-MM-DD>" },
    { "label": "Payment terms", "value": "<terms, e.g. Net 30>" }
  ],
  "items": {
    "headers": ["Description", "Qty", "Unit price", "Amount"],
    "aligns": ["L", "R", "R", "R"],
    "rows": [["<description>", "<qty>", "<unit price>", "<amount>"]],
    "totals": [
      { "label": "Subtotal", "value": "<amount> <currency>" },
      { "label": "VAT (<rate>%)", "value": "<amount> <currency>" },
      { "label": "Total", "value": "<amount> <currency>" }
    ]
  },
  "notes": ["Received and confirmed as accurate by the recipient."],
  "signature": { "date": "<Month D, YYYY>", "line": "<companyName> <representative name>", "stamp": true },
  "footer": "This statement documents goods and services already delivered under the transaction date above."
}
```

## Fixed wording

- notes: "Received and confirmed as accurate by the recipient." Adjust only if the requester supplies a different confirmation convention.
- footer: delivered-goods confirmation notice.

## Rules

- Use thousands separators for all amounts and state the currency the requester provides. Always state whether VAT is included, excluded, or not applicable.
- Put the VAT rate in `taxRatePercent`, and verify the totals match the sum of the item rows before filling the skeleton.
- The transaction date must reflect actual delivery, not the document issue date, unless the requester states they are the same.
