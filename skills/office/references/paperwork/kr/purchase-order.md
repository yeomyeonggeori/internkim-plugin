# Purchase Order (발주서)

output: pdf
filename: 발주서_<supplier>_<YYYYMMDD>.pdf

## Purpose

An external document ordering goods or services from a supplier. It is issued only once the delivery date and delivery place are settled.

## Required fields

- recipient: the 수신 (supplier) company name is required, with the contact's name when given
- meta: 발주일자 (order date), 납기일 (delivery date), 납품장소 (delivery place), 결제조건 (payment terms); all four required
- items: at least one row, using only the unit price and quantity the requester gave
- items.totals: 공급가액 합계 (supply total) → 부가세(10%) (VAT) → 총 발주금액 (order total), in that order
- signature: issue date + "<company name> 대표이사 <representative name>", stamp true

## Document JSON skeleton

```json
{
  "form": "kr/purchase-order",
  "title": "발 주 서",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "recipient": { "label": "수신", "lines": ["<supplier company name>", "<contact name> 님"] },
  "meta": [
    { "label": "발주일자", "value": "<YYYY-MM-DD>" },
    { "label": "납기일", "value": "<YYYY-MM-DD>" },
    { "label": "납품장소", "value": "<delivery address>" },
    { "label": "결제조건", "value": "<e.g. 납품 후 30일 이내 현금 지급>" }
  ],
  "items": {
    "headers": ["품명", "규격", "수량", "단가", "공급가액", "세액"],
    "aligns": ["L", "L", "R", "R", "R", "R"],
    "rows": [["<item>", "<spec>", "<quantity>", "<unit price>", "<supply amount>", "<tax>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<amount>원" },
      { "label": "부가세(10%)", "value": "<amount>원" },
      { "label": "총 발주금액", "value": "<amount>원" }
    ]
  },
  "notes": ["위와 같이 발주합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<company name> 대표이사 <representative name>", "stamp": true },
  "footer": "납기일 및 납품장소는 상호 협의 없이 변경할 수 없습니다."
}
```

## Fixed wording

- notes: "위와 같이 발주합니다."
- footer: the fixed sentence on delivery date and place. When the terms differ, change meta and footer together.

## Rules

- Write amounts with thousands separators and put "원" only on the total values. Always state whether VAT is excluded or included.
- Calculate tax as 10% of the supply amount and check that the totals equal the sum of the rows.
- Space the title's characters apart: "발 주 서".
