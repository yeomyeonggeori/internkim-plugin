# Invoice (청구서)

output: pdf
filename: 청구서_<recipient>_<YYYYMMDD>.pdf

## Purpose

An external document asking a customer to pay for goods or services already supplied. It must state the payment due date and the bank account, and Korean practice writes the billed amount both in figures and in Korean words.

## Required fields

- recipient: the recipient's company name is required, with the contact's name when given
- The supplier's details (사업자등록번호 business registration number, 업태 business type, 종목 business item, 대표자 representative) get no table of their own: profile.legalAttributes already prints them on the letterhead.
- meta: 합계금액 (total in Korean words and figures; leave its value empty and merge writes it from the grand total), 청구일자 (invoice date), 지급기한 (payment due date), 입금계좌 (bank account, profile.bankAccount); all required
- items: use only the 품명 (item), 규격 (spec), 수량 (quantity), 단위 (unit) and 단가 (unit price) the requester gave, at least one row
- items.totals: 공급가액 합계 (supply total) → 부가세(10%) (VAT) → 총 청구금액 (total billed), in that order
- signature: issue date + "<company name> 대표이사 <representative name>", stamp true

## Document JSON skeleton

```json
{
  "form": "kr/invoice",
  "title": "청 구 서",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "recipient": { "label": "수신", "lines": ["<recipient company name>", "<contact name> 님"] },
  "meta": [
    { "label": "합계금액", "value": "" },
    { "label": "청구일자", "value": "<YYYY-MM-DD>" },
    { "label": "지급기한", "value": "<YYYY-MM-DD>" },
    { "label": "입금계좌", "value": "<profile.bankAccount>" }
  ],
  "items": {
    "headers": ["품명", "규격", "수량", "단위", "단가", "공급가액", "세액"],
    "aligns": ["L", "L", "R", "C", "R", "R", "R"],
    "rows": [["<item>", "<spec>", "<quantity>", "<unit>", "<unit price>", "<supply amount>", "<tax>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<amount>원" },
      { "label": "부가세(10%)", "value": "<amount>원" },
      { "label": "총 청구금액", "value": "<amount>원" }
    ]
  },
  "notes": ["위 금액을 청구합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<company name> 대표이사 <representative name>", "stamp": true },
  "footer": "지급기한까지 위 계좌로 입금해 주시기 바랍니다."
}
```

## Fixed wording

- notes: "위 금액을 청구합니다."
- footer: the notice to pay into the account by the due date. When the requester gives a different way to pay, change meta and footer together.

## Density gate (self-check before delivery)

- Does the 합계금액 meta row hold both the Korean words ("일금 ○○○원整") and the figures (₩)?
- Is 지급기한 in meta?
- Is 입금계좌 (profile.bankAccount) in meta?
- Do the notes hold "위 금액을 청구합니다."?

## Rules

- Write amounts with thousands separators and put "원" only on the total values. Always state whether VAT is excluded or included.
- Calculate tax as 10% of the supply amount and check that the totals equal the sum of the rows.
- Never leave 지급기한 or 입금계좌 out of meta. When a value is missing, never invent it; ask the requester.
- When the item, unit price or quantity is missing, never invent it; ask the requester.
- Space the title's characters apart: "청 구 서".
