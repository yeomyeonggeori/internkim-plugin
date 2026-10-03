# Certificate of Employment (재직증명서)

output: pdf
filename: 재직증명서_<name>_<YYYYMMDD>.pdf

## Purpose

A certificate that a current employee works at the company, submitted inside or outside the company. It is usually requested for a particular recipient or purpose, so confirm it.

## Required fields

- documentNumber: the number company_document_register returns, printed as it is
- meta, personal details (4): 성명 (name), 생년월일 (date of birth), 주소 (address), 소속 (department)
- meta, employment details (4): 직위 (position or grade), 담당업무 (duties), 재직기간 (employment period), 제출용도 (purpose of submission)
- 재직기간 is written "<start date> ~ 현재 재직 중" (still employed, so there is no end date)
- signature: issue date + "<company name> 대표이사 <representative name>", stamp true

## Document JSON skeleton

```json
{
  "form": "kr/employment-certificate",
  "title": "재 직 증 명 서",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "성명", "value": "<name>" },
    { "label": "생년월일", "value": "<YYYY-MM-DD>" },
    { "label": "주소", "value": "<address>" },
    { "label": "소속", "value": "<department>" },
    { "label": "직위", "value": "<position>" },
    { "label": "담당업무", "value": "<duties>" },
    { "label": "재직기간", "value": "<start date> ~ 현재 재직 중" },
    { "label": "제출용도", "value": "<where it is submitted, or its purpose>" }
  ],
  "notes": ["위와 같이 재직하고 있음을 증명합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<company name> 대표이사 <representative name>", "stamp": true },
  "footer": "본 증명서는 발급일 기준 재직 사실을 증명합니다."
}
```

## Fixed wording

- notes: "위와 같이 재직하고 있음을 증명합니다."
- 재직기간 always ends in "현재 재직 중" (a certificate of employment is never issued to someone who has left).

## Density gate (self-check before delivery)

- Are all four personal details (성명, 생년월일, 주소, 소속) in meta?
- Are all four employment details (직위, 담당업무, 재직기간, 제출용도) in meta?
- Do the notes hold "위와 같이 재직하고 있음을 증명합니다."?
- Does the signature have stamp: true?

## Rules

- When the name, date of birth, address, department, position, duties, start date or purpose is missing, never invent it; ask the requester.
- Under Article 39 of the Labor Standards Act (근로기준법 제39조), state only what the employee asked for; never include salary, evaluations, contract terms or anything else not asked for.
- Space the title's characters apart: "재 직 증 명 서".
