# 출장보고서 (Business Trip Report)

output: pdf
filename: 출장보고서_<출장자>_<YYYYMMDD>.pdf

## Purpose

출장 내용과 성과, 후속 조치를 정리해 보고하는 문서. 경비 정산이 포함되면 지출 내역을 표로 함께 정리한다.

## Required fields

- meta: 출장자, 출장지, 출장기간, 출장목적
- sections: 출장 내용 / 주요 성과 / 후속 조치
- items: 경비 정리가 필요하면 내역·금액 표로 작성(경비가 없으면 생략)
- signature: 출장자 본인, stamp false

## Document JSON skeleton

```json
{
  "title": "출 장 보 고 서",
  "documentNumber": "BT-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "출장자", "value": "<성명>" },
    { "label": "출장지", "value": "<지역/장소>" },
    { "label": "출장기간", "value": "<YYYY-MM-DD ~ YYYY-MM-DD>" },
    { "label": "출장목적", "value": "<출장목적>" }
  ],
  "sections": [
    { "title": "1. 출장 내용", "paragraphs": ["<수행한 업무와 일정 요약>"] },
    { "title": "2. 주요 성과", "bullets": ["<성과 1>", "<성과 2>"] },
    { "title": "3. 후속 조치", "bullets": ["<후속 조치 1>"] }
  ],
  "items": {
    "headers": ["내역", "금액"],
    "aligns": ["L", "R"],
    "rows": [["<경비 내역>", "<금액>원"]],
    "totals": [{ "label": "합계", "value": "<금액>원" }]
  },
  "signature": { "date": "<YYYY년 M월 D일>", "line": "출장자 <성명>", "stamp": false }
}
```

## Fixed wording

- 고정 문구 없음. 출장 사실을 그대로 요약해 각 섹션에 채운다.

## Rules

- 경비 정리가 필요 없는 출장은 items 블록을 생략한다.
- 금액은 천단위 콤마 + "원"으로 표기하고, 부가세 포함/별도 여부를 명시한다.
- items.totals의 합계가 각 행 금액의 합과 일치하는지 검산한다.
- 출장지·기간·성과·후속 조치는 출장자가 제공한 사실만 사용하고, 없는 정보는 지어내지 말고 요청자에게 확인한다.
- title은 "출 장 보 고 서"처럼 글자 사이 공백을 넣는다.
