# Expense Approval (지출결의서)

output: pdf
filename: 지출결의서_<spending department>_<YYYYMMDD>.pdf

## Purpose

An internal approval document that settles spending already made or committed. The spending details and whether there is proof must be confirmed facts.

## Required fields

- approvalLine: always ["담당", "검토", "대표"]
- meta: 기안자 (drafter), 지출일자 (spending date), 지출부서 (spending department), 지급방법 (payment method: "법인카드" or "계좌이체"), 증빙 (proof: "영수증 첨부" / "세금계산서 첨부" / "증빙 없음")
- items: at least one row of 적요 (description), 거래처 (vendor) and 금액 (amount), amounts right-aligned
- items.totals: 합계 (total)
- signature: the drafter, stamp true

## Document JSON skeleton

```json
{
  "title": "지 출 결 의 서",
  "documentNumber": "EA-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "approvalLine": ["담당", "검토", "대표"],
  "meta": [
    { "label": "기안자", "value": "<team> <name>" },
    { "label": "지출일자", "value": "<YYYY-MM-DD>" },
    { "label": "지출부서", "value": "<department>" },
    { "label": "지급방법", "value": "<법인카드 | 계좌이체>" },
    { "label": "증빙", "value": "<영수증 첨부 | 세금계산서 첨부 | 증빙 없음>" }
  ],
  "items": {
    "headers": ["적요", "거래처", "금액"],
    "aligns": ["L", "L", "R"],
    "rows": [["<description>", "<vendor>", "<amount>원"]],
    "totals": [{ "label": "합계", "value": "<amount>원" }]
  },
  "notes": ["위와 같이 지출을 결의합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "기안자 <name>", "stamp": true }
}
```

## Fixed wording

- notes: "위와 같이 지출을 결의합니다."
- approvalLine is always ["담당", "검토", "대표"], in that order.

## Rules

- Always record in meta whether there is proof (receipt or tax invoice); when the requester did not say, confirm before writing it.
- Write amounts with thousands separators and "원", and state whether VAT is included or excluded.
- Check that the total in items.totals equals the sum of the row amounts.
- Use only the department, vendors, amounts and payment method the requester gave; never invent missing information, ask the requester.
- Space the title's characters apart: "지 출 결 의 서".
