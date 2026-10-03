# Quotation

output: pdf
filename: Quotation_<recipient>_<YYYYMMDD>.pdf

## Purpose

An external document proposing prices for goods or services to a customer. The recipient and the line items and amounts must be confirmed, not assumed.

## Required fields

- recipient: customer company name required, contact name if provided
- meta: quotation date, valid until, bank account (from profile.bankAccount)
- items: at least one row; use unit price and quantity only as supplied by the requester
- items.totals: subtotal → VAT (<rate>%) → total, in that order
- signature: issue date + "<companyName> CEO <representative name>", stamp true

## Document JSON skeleton

```json
{
  "form": "intl/quote",
  "title": "Quotation",
  "documentNumber": "<the number company_document_register returned>",
  "company": "<the company-profile.json path company_info_get answered>",
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
      { "label": "Subtotal", "value": "<amount> <currency>" },
      { "label": "VAT (<rate>%)", "value": "<amount> <currency>" },
      { "label": "Total (VAT included)", "value": "<amount> <currency>" }
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

- Use thousands separators for all amounts and state the currency the requester provides. Always state whether VAT is included or excluded.
- Put the tax rate in `taxRatePercent`, calculate tax from the subtotal, and verify the totals match the sum of the item rows.
- Keep line item descriptions in the language the requester provides; do not translate proper nouns or SKU names.
