# Weekly Report (주간업무보고)

output: pdf
filename: 주간업무보고_<reporter>_<YYYYMMDD>.pdf

## Purpose

A summary of the week's work and issues, shared with a manager or the team. It is for reporting, not approval, so it has no approvalLine.

## Required fields

- meta: 보고자 (reporter), 소속 (department), 보고기간 (reporting period)
- sections: 금주 완료 업무 (done this week, bullets) / 진행 중 업무 (in progress) / 차주 계획 (next week's plan) / 이슈 및 요청사항 (issues and requests)
- signature: the reporter, stamp false
- No approvalLine

## Document JSON skeleton

```json
{
  "form": "kr/weekly-report",
  "title": "주 간 업 무 보 고",
  "documentNumber": "<the number company_document_register returned>",
  "company": "<the company-profile.json path company_info_get answered>",
  "meta": [
    { "label": "보고자", "value": "<name>" },
    { "label": "소속", "value": "<department>" },
    { "label": "보고기간", "value": "<YYYY-MM-DD ~ YYYY-MM-DD>" }
  ],
  "sections": [
    { "title": "1. 금주 완료 업무", "bullets": ["<work done 1>", "<work done 2>"] },
    { "title": "2. 진행 중 업무", "bullets": ["<work in progress 1>"] },
    { "title": "3. 차주 계획", "bullets": ["<next week's plan 1>"] },
    { "title": "4. 이슈 및 요청사항", "paragraphs": ["<issues or requests for support, or \"특이사항 없음\" when there are none>"] }
  ],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "보고자 <name>", "stamp": false }
}
```

## Fixed wording

- When there are no issues or requests: "특이사항 없음."

## Rules

- Never add an approvalLine.
- Space the title's characters apart: "주 간 업 무 보 고".
