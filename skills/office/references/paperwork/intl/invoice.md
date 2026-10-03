# Invoice

output: pdf
filename: Invoice_<recipient>_<YYYYMMDD>.pdf

## Purpose

An external document requesting payment from a customer for goods or services already delivered. The due date and bank account must always be stated.

## Required fields

- recipient: customer company name required, contact name if provided
- meta: invoice date, due date, bank account (from profile.bankAccount) — all three required
- items: at least one row; use unit price and quantity only as supplied by the requester
- items.totals: subtotal → tax (if applicable) → total due, in that order
- signature: issue date + "<companyName> CEO <representative name>", stamp true

## Document JSON skeleton

```json
{
  "form": "intl/invoice",
  "title": "Invoice",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "recipient": { "label": "Bill to", "lines": ["<recipient company name>", "Attn: <contact name>"] },
  "meta": [
    { "label": "Invoice date", "value": "<YYYY-MM-DD>" },
    { "label": "Due date", "value": "<YYYY-MM-DD>" },
    { "label": "Bank account", "value": "<profile.bankAccount>" }
  ],
  "items": {
    "headers": ["Description", "Spec", "Qty", "Unit price", "Amount", "Tax"],
    "aligns": ["L", "L", "R", "R", "R", "R"],
    "rows": [["<description>", "<spec>", "<qty>", "<unit price>", "<amount>", "<tax>"]],
    "totals": [
      { "label": "Subtotal", "value": "<amount> <currency>" },
      { "label": "Tax (<rate>%)", "value": "<amount> <currency>" },
      { "label": "Total due", "value": "<amount> <currency>" }
    ]
  },
  "notes": ["Please remit payment as invoiced above."],
  "signature": { "date": "<Month D, YYYY>", "line": "<companyName> CEO <representative name>", "stamp": true },
  "footer": "Please transfer the total due to the account above by the due date."
}
```

## Fixed wording

- notes: "Please remit payment as invoiced above."
- footer: remittance notice tied to the due date. If the requester specifies a different payment method, update meta and footer together.

## Rules

- Use thousands separators for all amounts and state the currency the requester provides. Always state whether tax is included, excluded, or not applicable.
- If tax applies, put its rate in `taxRatePercent`, calculate it from the subtotal, and verify the totals match the sum of the item rows.
- Never omit the due date or bank account from meta.
