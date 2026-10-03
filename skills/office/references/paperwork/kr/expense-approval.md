# Expense Approval (지출결의서)

output: pdf
filename: 지출결의서_<spending department>_<YYYYMMDD>.pdf

## Purpose

An internal approval document that settles spending already made or committed. The spending details and whether there is proof must be confirmed facts.

## Required fields

- approvalLine: the approvers the request names, in its order, each `{"role", "name"}`; when it names none, the roles "담당", "검토", "대표" without names
- meta: 기안자 (drafter), 지출일자 (spending date), 지출부서 (spending department), 지급방법 (payment method: "법인카드" or "계좌이체"), 증빙 (proof: "영수증 첨부" / "세금계산서 첨부" / "증빙 없음")
- items: one row per account the spending is booked to, with 계정과목 (account), 적요 (description), 거래처 (vendor), 공급가액 (supply amount) and 세액 (VAT, booked as input VAT, 부가세대급금), amounts right-aligned; a row without VAT writes 0 as its 세액
- items.totals: 공급가액 합계, 세액, 합계, in that order
- signature: the drafter, stamp true

## Document JSON skeleton

```json
{
  "form": "kr/expense-approval",
  "title": "지 출 결 의 서",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "approvalLine": [{ "role": "<role>", "name": "<name>" }],
  "meta": [
    { "label": "기안자", "value": "<team> <name>" },
    { "label": "지출일자", "value": "<YYYY-MM-DD>" },
    { "label": "지출부서", "value": "<department>" },
    { "label": "지급방법", "value": "<법인카드 | 계좌이체>" },
    { "label": "증빙", "value": "<영수증 첨부 | 세금계산서 첨부 | 증빙 없음>" }
  ],
  "items": {
    "headers": ["계정과목", "적요", "거래처", "공급가액", "세액"],
    "aligns": ["L", "L", "L", "R", "R"],
    "rows": [["<account>", "<description>", "<vendor>", "<supply amount>", "<VAT>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<supply total>원" },
      { "label": "세액", "value": "<VAT total>원" },
      { "label": "합계", "value": "<grand total>원" }
    ]
  },
  "notes": ["위와 같이 지출을 결의합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "기안자 <name>", "stamp": true }
}
```

## Fixed wording

- notes: "위와 같이 지출을 결의합니다."

## Rules

- Always record in meta whether there is proof (receipt or tax invoice); when the requester did not say, confirm before writing it.
- Write amounts with thousands separators and "원", and state whether VAT is included or excluded.
- Check that 공급가액 합계 and 세액 are the sums of the rows and 합계 is their sum; `office check` reports any that are not.
- Use only the department, vendors, amounts and payment method the requester gave; never invent missing information, ask the requester.
- Space the title's characters apart: "지 출 결 의 서".
