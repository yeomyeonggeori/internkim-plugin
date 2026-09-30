# Purchase Order

output: pdf
filename: PurchaseOrder_<supplier>_<YYYYMMDD>.pdf

## Purpose

An external document ordering goods or services from a supplier. Delivery date and delivery address must be confirmed before issuing.

## Required fields

- recipient: supplier company name required, contact name if provided
- meta: PO date, delivery date, delivery address, payment terms — all four required
- items: at least one row; use unit price and quantity only as supplied by the requester
- items.totals: subtotal → VAT (10%) → total order amount, in that order
- signature: issue date + "<companyName> CEO <representative name>", stamp true

## Document JSON skeleton

```json
{
  "title": "Purchase Order",
  "documentNumber": "PO-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "recipient": { "label": "To", "lines": ["<supplier company name>", "Attn: <contact name>"] },
  "meta": [
    { "label": "PO date", "value": "<YYYY-MM-DD>" },
    { "label": "Delivery date", "value": "<YYYY-MM-DD>" },
    { "label": "Delivery address", "value": "<delivery address>" },
    { "label": "Payment terms", "value": "<e.g. Net 30 after delivery>" }
  ],
  "items": {
    "headers": ["Description", "Spec", "Qty", "Unit price", "Amount", "Tax"],
    "aligns": ["L", "L", "R", "R", "R", "R"],
    "rows": [["<description>", "<spec>", "<qty>", "<unit price>", "<amount>", "<tax>"]],
    "totals": [
      { "label": "Subtotal", "value": "<amount> KRW" },
      { "label": "VAT (10%)", "value": "<amount> KRW" },
      { "label": "Total order amount", "value": "<amount> KRW" }
    ]
  },
  "notes": ["We hereby place the order above."],
  "signature": { "date": "<Month D, YYYY>", "line": "<companyName> CEO <representative name>", "stamp": true },
  "footer": "The delivery date and address may not be changed without mutual agreement."
}
```

## Fixed wording

- notes: "We hereby place the order above."
- footer: fixed delivery-terms notice. If terms differ, update meta and footer together.

## Rules

- Use thousands separators for all amounts and state the currency explicitly (default KRW unless the requester specifies otherwise). Always state whether VAT is included or excluded.
- Calculate tax as 10% of the subtotal and verify the totals match the sum of the item rows.
- Never invent the supplier's name, prices, quantities, delivery terms, or dates — ask the requester when any of these are missing.
