# 주간업무보고 (Weekly Report)

output: pdf
filename: 주간업무보고_<보고자>_<YYYYMMDD>.pdf

## Purpose

한 주간 수행한 업무와 이슈를 정리해 상급자·팀에 공유하는 문서. 결재가 아닌 보고 목적이므로 approvalLine은 사용하지 않는다.

## Required fields

- meta: 보고자, 소속, 보고기간
- sections: 금주 완료 업무(bullets) / 진행 중 업무 / 차주 계획 / 이슈 및 요청사항
- signature: 보고자 본인, stamp false
- approvalLine은 사용하지 않는다

## Document JSON skeleton

```json
{
  "title": "주 간 업 무 보 고",
  "documentNumber": "WR-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "보고자", "value": "<성명>" },
    { "label": "소속", "value": "<부서명>" },
    { "label": "보고기간", "value": "<YYYY-MM-DD ~ YYYY-MM-DD>" }
  ],
  "sections": [
    { "title": "1. 금주 완료 업무", "bullets": ["<완료 업무 1>", "<완료 업무 2>"] },
    { "title": "2. 진행 중 업무", "bullets": ["<진행 중 업무 1>"] },
    { "title": "3. 차주 계획", "bullets": ["<차주 계획 1>"] },
    { "title": "4. 이슈 및 요청사항", "paragraphs": ["<이슈나 지원 요청 사항, 없으면 \"특이사항 없음\">"] }
  ],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "보고자 <성명>", "stamp": false }
}
```

## Fixed wording

- 이슈 및 요청사항이 없을 경우: "특이사항 없음."

## Rules

- approvalLine은 절대 추가하지 않는다.
- 완료/진행/계획 업무는 보고자가 제공한 내용만 사용하고, 실제로 언급되지 않은 업무나 성과를 지어내지 않는다.
- 이슈나 요청사항이 불명확하면 임의로 판단하지 말고 요청자에게 확인한다.
- title은 "주 간 업 무 보 고"처럼 글자 사이 공백을 넣는다.
