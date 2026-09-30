# Quotation

output: pdf
filename: Quotation_<recipient>_<YYYYMMDD>.pdf

## Purpose

An external document proposing prices for goods or services to a customer. The recipient and the line items and amounts must be confirmed, not assumed.

## Required fields

- recipient: customer company name required, contact name if provided
- meta: quotation date, valid until, bank account (from profile.bankAccount)
- items: at least one row; use unit price and quantity only as supplied by the requester
- items.totals: subtotal → VAT (10%) → total, in that order
- signature: issue date + "<companyName> CEO <representative name>", stamp true

## Document JSON skeleton

```json
{
  "title": "Quotation",
  "documentNumber": "Q-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "recipient": { "label": "To", "lines": ["<recipient company name>", "Attn: <contact name>"] },
  "meta": [
    { "label": "Quotation date", "value": "<YYYY-MM-DD>" },
    { "label": "Valid until", "value": "30 days from issue" },
    { "label": "Bank account", "value": "<profile.bankAccount>" }
  ],
  "items": {
    "headers": ["Description", "Spec", "Qty", "Unit price", "Amount", "Tax"],
    "aligns": ["L", "L", "R", "R", "R", "R"],
    "rows": [["<description>", "<spec>", "<qty>", "<unit price>", "<amount>", "<tax>"]],
    "totals": [
      { "label": "Subtotal", "value": "<amount> KRW" },
      { "label": "VAT (10%)", "value": "<amount> KRW" },
      { "label": "Total (VAT included)", "value": "<amount> KRW" }
    ]
  },
  "notes": ["We are pleased to submit the quotation above."],
  "signature": { "date": "<Month D, YYYY>", "line": "<companyName> CEO <representative name>", "stamp": true },
  "footer": "This quotation is valid for 30 days from the date of issue."
}
```

## Fixed wording

- notes: "We are pleased to submit the quotation above."
- footer: validity period notice. If the requester specifies a different validity period, update meta and footer together.

## Rules

- Use thousands separators for all amounts and state the currency explicitly (default KRW unless the requester specifies otherwise). Always state whether VAT is included or excluded.
- Calculate tax as 10% of the subtotal and verify the totals match the sum of the item rows.
- Never invent the counterpart's name, prices, quantities, or dates — ask the requester when any of these are missing.
- Keep line item descriptions in the language the requester provides; do not translate proper nouns or SKU names.
