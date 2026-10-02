# Transaction Statement (거래명세서)

output: pdf
filename: 거래명세서_<buyer>_<YYYYMMDD>.pdf

## Purpose

An external document that records a completed transaction between the supplier and the buyer (공급받는자). Unlike a quotation, it copies the actual items, quantities and amounts of a settled transaction, and Korean practice has the receiver confirm receipt on it.

## Required fields

- recipient: the buyer's company name is required, with the contact's name when given. When the buyer's business registration number (사업자등록번호) was given, add it on the line after the company name.
- The supplier's details (사업자등록번호 business registration number, 업태 business type, 종목 business item, 대표자 representative) get no table of their own: profile.legalAttributes already prints them on the letterhead.
- meta: 거래일자 (transaction date) is required, and the last meta row is always the receiver's confirmation box (인수자)
- items: use only the 품명 (item), 규격 (spec), 수량 (quantity), 단위 (unit) and 단가 (unit price) the requester gave, at least one row
- items.totals: 공급가액 합계 (supply total) → 세액 합계 (tax total) → 총 합계 (grand total), in that order
- signature: the supplier's issue date + "<company name> 대표이사 <representative name>", stamp true. The receiver's confirmation goes in the last meta row, not in signature (the schema supports only one signature).

## Document JSON skeleton

```json
{
  "title": "거 래 명 세 서",
  "documentNumber": "T-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "recipient": { "label": "공급받는자", "lines": ["<buyer company name>", "<contact name> 님"] },
  "meta": [
    { "label": "거래일자", "value": "<YYYY-MM-DD>" },
    { "label": "인수자", "value": "<receiver name>  (서명 또는 인)" }
  ],
  "items": {
    "headers": ["품명", "규격", "수량", "단위", "단가", "공급가액", "세액"],
    "aligns": ["L", "L", "R", "C", "R", "R", "R"],
    "rows": [["<item>", "<spec>", "<quantity>", "<unit>", "<unit price>", "<supply amount>", "<tax>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<amount>원" },
      { "label": "세액 합계", "value": "<amount>원" },
      { "label": "총 합계 (부가세 포함)", "value": "<amount>원" }
    ]
  },
  "notes": ["위와 같이 계산합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<company name> 대표이사 <representative name>", "stamp": true },
  "footer": "본 명세서는 실제 거래 내역과 일치함을 확인합니다."
}
```

## Fixed wording

- notes: "위와 같이 계산합니다."
- The receiver's confirmation box never drops out of the last meta row. When the receiver's name was not given, leave the name blank and keep only "(서명 또는 인)".

## Density gate (self-check before delivery)

- Is 거래일자 in meta?
- Does the item table have 7 columns (품명, 규격, 수량, 단위, 단가, 공급가액, 세액)?
- Is the last meta row the receiver's confirmation box ("(서명 또는 인)")?
- Is the signature the supplier's ("<company name> 대표이사 <representative name>") with stamp: true?

## Rules

- Write amounts with thousands separators and put "원" only on the total values. Always state whether VAT is excluded or included.
- Calculate tax as 10% of the supply amount and check that the totals equal the sum of the rows.
- When the buyer's name, item, unit price, quantity or transaction date is missing, never invent it; ask the requester.
- Space the title's characters apart: "거 래 명 세 서".
