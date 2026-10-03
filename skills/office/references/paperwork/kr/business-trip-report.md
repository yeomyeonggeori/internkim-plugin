# Business Trip Report (출장보고서)

output: pdf
filename: 출장보고서_<traveler>_<YYYYMMDD>.pdf

## Purpose

A report of what a business trip covered, what it achieved and what follows from it. When expenses are settled, the spending is listed in a table too.

## Required fields

- meta: 출장자 (traveler), 출장지 (destination), 출장기간 (period), 출장목적 (purpose)
- sections: 출장 내용 (trip summary) / 주요 성과 (key outcomes) / 후속 조치 (follow-ups)
- items: when expenses need settling, a table of description and amount (omit when there are no expenses)
- signature: the traveler, stamp false

## Document JSON skeleton

```json
{
  "form": "kr/business-trip-report",
  "title": "출 장 보 고 서",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "출장자", "value": "<name>" },
    { "label": "출장지", "value": "<region or place>" },
    { "label": "출장기간", "value": "<YYYY-MM-DD ~ YYYY-MM-DD>" },
    { "label": "출장목적", "value": "<purpose of the trip>" }
  ],
  "sections": [
    { "title": "1. 출장 내용", "paragraphs": ["<summary of the work done and the schedule>"] },
    { "title": "2. 주요 성과", "bullets": ["<outcome 1>", "<outcome 2>"] },
    { "title": "3. 후속 조치", "bullets": ["<follow-up 1>"] }
  ],
  "items": {
    "headers": ["내역", "금액"],
    "aligns": ["L", "R"],
    "rows": [["<expense description>", "<amount>원"]],
    "totals": [{ "label": "합계", "value": "<amount>원" }]
  },
  "signature": { "date": "<YYYY년 M월 D일>", "line": "출장자 <name>", "stamp": false }
}
```

## Fixed wording

- None. Fill each section with a plain summary of the trip's facts.

## Rules

- A trip with no expenses to settle omits the items block.
- Write amounts with thousands separators and "원", and state whether VAT is included or excluded.
- Check that the total in items.totals equals the sum of the row amounts.
- Space the title's characters apart: "출 장 보 고 서".
