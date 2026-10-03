# Approval Request (품의서)

output: pdf
filename: 품의서_<short subject>_<YYYYMMDD>.pdf

## Purpose

An internal approval document that asks for a decision inside the company. It sets out the purpose, the details and the expected benefit for the approvers to sign off.

## Required fields

- approvalLine: the approvers the request names, in its order, each `{"role", "name"}`; when it names none, the roles "담당", "검토", "대표" without names
- meta: 기안자 (drafter, with team, e.g. "경영지원팀 홍길동"), 기안일자 (draft date), 제목 (subject)
- sections: three parts, 목적 (purpose) / 내역 (details) / 기대 효과 (expected benefit)
- items: a request that involves money writes its details as a table (omit when there is no amount)
- signature: the drafter, stamp true

## Document JSON skeleton

```json
{
  "form": "kr/approval-request",
  "title": "품 의 서",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "approvalLine": [{ "role": "<role>", "name": "<name>" }],
  "meta": [
    { "label": "기안자", "value": "<team> <name>" },
    { "label": "기안일자", "value": "<YYYY-MM-DD>" },
    { "label": "제목", "value": "<subject of the request>" }
  ],
  "sections": [
    { "title": "1. 목적", "paragraphs": ["<background and purpose of the request>"] },
    { "title": "2. 내역", "paragraphs": ["<details of a request without amounts>"] },
    { "title": "3. 기대 효과", "paragraphs": ["<benefit expected once approved>"] }
  ],
  "items": {
    "headers": ["항목", "내용", "금액"],
    "aligns": ["L", "L", "R"],
    "rows": [["<item>", "<description>", "<amount>원"]],
    "totals": [{ "label": "합계", "value": "<amount>원" }]
  },
  "notes": ["위와 같이 품의하오니 재가 바랍니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "기안자 <name>", "stamp": true }
}
```

## Fixed wording

- notes: "위와 같이 품의하오니 재가 바랍니다."

## Rules

- A request that involves money writes "2. 내역" as the items table instead of paragraphs; with no amount, omit the items block entirely.
- Write amounts with thousands separators and "원", and state whether VAT is included or excluded.
- Space the title's characters apart: "품 의 서".
