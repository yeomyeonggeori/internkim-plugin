# 지출결의서 (Expense Approval)

output: pdf
filename: 지출결의서_<지출부서>_<YYYYMMDD>.pdf

## Purpose

이미 발생했거나 확정된 지출 건을 사후 결의받는 내부 결재 문서. 지출 내역과 증빙 여부가 확정 정보여야 한다.

## Required fields

- approvalLine: ["담당", "검토", "대표"] 고정
- meta: 기안자, 지출일자, 지출부서, 지급방법("법인카드" 또는 "계좌이체"), 증빙 여부("영수증 첨부" / "세금계산서 첨부" / "증빙 없음")
- items: 적요·거래처·금액 1행 이상, 금액은 우측 정렬
- items.totals: 합계
- signature: 기안자 본인, stamp true

## Document JSON skeleton

```json
{
  "title": "지 출 결 의 서",
  "documentNumber": "EA-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "approvalLine": ["담당", "검토", "대표"],
  "meta": [
    { "label": "기안자", "value": "<소속> <성명>" },
    { "label": "지출일자", "value": "<YYYY-MM-DD>" },
    { "label": "지출부서", "value": "<부서명>" },
    { "label": "지급방법", "value": "<법인카드 | 계좌이체>" },
    { "label": "증빙", "value": "<영수증 첨부 | 세금계산서 첨부 | 증빙 없음>" }
  ],
  "items": {
    "headers": ["적요", "거래처", "금액"],
    "aligns": ["L", "L", "R"],
    "rows": [["<적요>", "<거래처>", "<금액>원"]],
    "totals": [{ "label": "합계", "value": "<금액>원" }]
  },
  "notes": ["위와 같이 지출을 결의합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "기안자 <성명>", "stamp": true }
}
```

## Fixed wording

- notes: "위와 같이 지출을 결의합니다."
- approvalLine은 항상 ["담당", "검토", "대표"] 순서로 고정한다.

## Rules

- meta에 증빙(영수증/세금계산서) 유무를 반드시 기록하고, 요청자가 밝히지 않았으면 확인 후 기재한다.
- 금액은 천단위 콤마 + "원"으로 표기하고, 부가세 포함/별도 여부를 명시한다.
- items.totals의 합계가 각 행 금액의 합과 일치하는지 검산한다.
- 지출부서·거래처·금액·지급방법 등은 요청자가 제공한 사실만 사용하고, 없는 정보는 지어내지 말고 요청자에게 확인한다.
- title은 "지 출 결 의 서"처럼 글자 사이 공백을 넣는다.
