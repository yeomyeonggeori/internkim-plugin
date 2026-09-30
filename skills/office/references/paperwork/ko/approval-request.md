# 품의서 (Approval Request)

output: pdf
filename: 품의서_<제목요약>_<YYYYMMDD>.pdf

## Purpose

사내 의사결정을 요청하는 내부 결재 문서. 목적·내역·기대 효과를 담아 결재권자의 승인을 받는다.

## Required fields

- approvalLine: ["담당", "검토", "대표"] 고정
- meta: 기안자(소속 포함, 예: "경영지원팀 홍길동"), 기안일자, 제목
- sections: 목적 / 내역 / 기대 효과 3단 구성
- items: 금액이 발생하는 안건은 내역을 표로 작성(금액 없으면 생략)
- signature: 기안자 본인, stamp true

## Document JSON skeleton

```json
{
  "title": "품 의 서",
  "documentNumber": "AR-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "approvalLine": ["담당", "검토", "대표"],
  "meta": [
    { "label": "기안자", "value": "<소속> <성명>" },
    { "label": "기안일자", "value": "<YYYY-MM-DD>" },
    { "label": "제목", "value": "<품의 제목>" }
  ],
  "sections": [
    { "title": "1. 목적", "paragraphs": ["<품의를 올리는 배경과 목적>"] },
    { "title": "2. 내역", "paragraphs": ["<금액이 없는 안건의 세부 내용>"] },
    { "title": "3. 기대 효과", "paragraphs": ["<승인 시 기대되는 효과>"] }
  ],
  "items": {
    "headers": ["항목", "내용", "금액"],
    "aligns": ["L", "L", "R"],
    "rows": [["<항목>", "<내용>", "<금액>원"]],
    "totals": [{ "label": "합계", "value": "<금액>원" }]
  },
  "notes": ["위와 같이 품의하오니 재가 바랍니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "기안자 <성명>", "stamp": true }
}
```

## Fixed wording

- notes: "위와 같이 품의하오니 재가 바랍니다."
- approvalLine은 항상 ["담당", "검토", "대표"] 순서로 고정한다.

## Rules

- 금액이 발생하는 안건은 "2. 내역"을 문단 대신 items 표로 작성하고, 금액이 없으면 items 블록 자체를 생략한다.
- 금액은 천단위 콤마 + "원"으로 표기하고, 부가세 포함/별도 여부를 명시한다.
- 기안자·금액·일자·결정사항 등은 요청자가 제공한 사실만 사용하고, 없는 정보는 지어내지 말고 요청자에게 확인한다.
- title은 "품 의 서"처럼 글자 사이 공백을 넣는다.
