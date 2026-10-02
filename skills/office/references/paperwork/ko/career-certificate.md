# Certificate of Career (경력증명서)

output: pdf
filename: 경력증명서_<name>_<YYYYMMDD>.pdf

## Purpose

A certificate of past employment for someone who has left or who once worked at the company, submitted inside or outside the company. Unlike the certificate of employment (재직증명서), its 재직기간 (employment period) is a closed period that has ended.

## Required fields

- documentNumber: the number company_document_register returns, written as "제 <YYYY>-<NNN>호" (e.g. 제 2026-013호)
- meta, personal details (4): 성명 (name), 생년월일 (date of birth), 주소 (address), 소속 (department)
- meta, employment details (4): 직위 (position or grade), 담당업무 (duties), 재직기간 (employment period), 제출용도 (purpose of submission)
- 재직기간 is a closed period, "<start date> ~ <end date>" (never "현재" (present), which only the certificate of employment uses)
- 퇴직사유 (reason for leaving) goes in meta only when the requester explicitly asks for it (omitted by default)
- signature: issue date + "<company name> 대표이사 <representative name>", stamp true

## Document JSON skeleton

```json
{
  "title": "경 력 증 명 서",
  "documentNumber": "제 <YYYY>-<NNN>호",
  "profile": { ...company profile... },
  "meta": [
    { "label": "성명", "value": "<name>" },
    { "label": "생년월일", "value": "<YYYY-MM-DD>" },
    { "label": "주소", "value": "<address>" },
    { "label": "소속", "value": "<department>" },
    { "label": "직위", "value": "<position>" },
    { "label": "담당업무", "value": "<duties in detail>" },
    { "label": "재직기간", "value": "<start date> ~ <end date>" },
    { "label": "제출용도", "value": "<where it is submitted, or its purpose>" }
  ],
  "notes": ["위와 같이 근무하였음을 증명합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<company name> 대표이사 <representative name>", "stamp": true },
  "footer": "본 증명서는 상기 근무 이력이 사실임을 증명합니다."
}
```

## Fixed wording

- notes: "위와 같이 근무하였음을 증명합니다."
- 재직기간 is always a closed period with an end date.
- To include 퇴직사유, add the row `{ "label": "퇴직사유", "value": "<reason for leaving>" }` to meta right after 재직기간; never add it unless the requester asks.

## Density gate (self-check before delivery)

- Are all four personal details (성명, 생년월일, 주소, 소속) in meta?
- Are all four employment details (직위, 담당업무, 재직기간, 제출용도) in meta?
- Is 재직기간 a closed period from start date to end date (not "현재")?
- Is 퇴직사유 present only if the requester asked for it?
- Do the notes hold "위와 같이 근무하였음을 증명합니다."?

## Rules

- When the name, date of birth, address, department, position, duties, start date, end date or purpose is missing, never invent it; ask the requester.
- Under Article 39 of the Labor Standards Act (근로기준법 제39조), state only what the employee asked for; never include salary, evaluations, a reason for leaving or anything else not asked for.
- Space the title's characters apart: "경 력 증 명 서".
