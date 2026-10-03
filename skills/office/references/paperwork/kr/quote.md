# Quotation (견적서)

output: pdf
filename: 견적서_<recipient>_<YYYYMMDD>.pdf

## Purpose

An external document proposing prices for goods or services to a customer. It needs information on a par with what the VAT Act requires of a tax invoice (supplier, recipient, items, supply amount, tax, date of issue) to serve in practice as the basis for an order or contract as it is. The recipient, items and amounts must be confirmed facts.

## Required fields

- recipient: the recipient's company name is required, with the contact's name when given. When the recipient's business registration number (사업자등록번호) was given, add it on the line after the company name.
- The supplier's details (사업자등록번호 business registration number, 업태 business type, 종목 business item, 대표자 representative) get no table of their own: profile.legalAttributes already prints them on the letterhead.
- meta: 합계금액 (total, also in Korean words), 견적일자 (quotation date), 유효기간 (validity), 납기 (delivery), 납품장소 (delivery place), 결제조건 (payment terms), 입금계좌 (bank account, profile.bankAccount); all required, ask the requester when a value is missing
- items: use only the 품명 (item), 규격 (spec), 수량 (quantity), 단위 (unit) and 단가 (unit price) the requester gave, at least one row
- items.totals: 공급가액 합계 (supply total) → 부가세(10%) (VAT) → 총 합계 (grand total), in that order
- notes: "아래와 같이 견적합니다."
- signature: issue date + "<company name> 대표이사 <representative name>", stamp true

## Document JSON skeleton

```json
{
  "form": "kr/quote",
  "title": "견 적 서",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "recipient": { "label": "수신", "lines": ["<recipient company name>", "<contact name> 님"] },
  "meta": [
    { "label": "합계금액", "value": "일금 <amount in Korean words>원整 (₩<amount with thousands separators>) (부가세 포함)" },
    { "label": "견적일자", "value": "<YYYY-MM-DD>" },
    { "label": "유효기간", "value": "발행일로부터 <N>일" },
    { "label": "납기", "value": "<delivery terms>" },
    { "label": "납품장소", "value": "<delivery address>" },
    { "label": "결제조건", "value": "<e.g. 계약금 30% / 잔금 납품 후 30일 이내>" },
    { "label": "입금계좌", "value": "<profile.bankAccount>" }
  ],
  "items": {
    "headers": ["품명", "규격", "수량", "단위", "단가", "공급가액", "세액"],
    "aligns": ["L", "L", "R", "C", "R", "R", "R"],
    "rows": [["<item>", "<spec>", "<quantity>", "<unit>", "<unit price>", "<supply amount>", "<tax>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<amount>원" },
      { "label": "부가세(10%)", "value": "<amount>원" },
      { "label": "총 합계 (부가세 포함)", "value": "<amount>원" }
    ]
  },
  "notes": ["아래와 같이 견적합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<company name> 대표이사 <representative name>", "stamp": true },
  "footer": "본 견적은 견적일로부터 <N>일간 유효합니다."
}
```

## Fixed wording

- notes: "아래와 같이 견적합니다."
- footer: "본 견적은 견적일로부터 <N>일간 유효합니다."; its N always matches 유효기간 in meta.

## Density gate (self-check before delivery)

- Does the 합계금액 meta row hold both the Korean words ("일금 ○○○원整") and the figures (₩)?
- Does the item table have 7 columns (품명, 규격, 수량, 단위, 단가, 공급가액, 세액)?
- Are 견적일자, 유효기간, 결제조건 and 입금계좌 all in meta?
- Do the notes hold "아래와 같이 견적합니다."?
- Does the signature have stamp: true?

## Rules

- Write amounts with thousands separators and put "원" only on the total values. Always state whether VAT is excluded or included.
- Calculate tax as 10% of the supply amount and check that the totals equal the sum of the rows.
- When the item, unit price or quantity is missing, never invent it; ask the requester.
- Space the title's characters apart: "견 적 서".
