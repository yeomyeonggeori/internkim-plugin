# 발주서 (Purchase Order)

output: pdf
filename: 발주서_<공급사>_<YYYYMMDD>.pdf

## Purpose

상품·서비스 공급을 거래처(공급사)에 발주하는 대외 문서. 납기일과 납품장소가 확정되어야 발행한다.

## Required fields

- recipient: 수신(공급사) 회사명 필수, 담당자명은 있으면 함께
- meta: 발주일자, 납기일, 납품장소, 결제조건 — 네 항목 모두 필수
- items: 품목 1행 이상, 단가·수량은 요청자 제공 값만 사용
- items.totals: 공급가액 합계 → 부가세(10%) → 총 발주금액 순서
- signature: 발행일 + "회사명 대표이사 대표자명", stamp true

## Document JSON skeleton

```json
{
  "title": "발 주 서",
  "documentNumber": "P-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "recipient": { "label": "수신", "lines": ["<공급사 회사명>", "<담당자명> 님"] },
  "meta": [
    { "label": "발주일자", "value": "<YYYY-MM-DD>" },
    { "label": "납기일", "value": "<YYYY-MM-DD>" },
    { "label": "납품장소", "value": "<납품 주소>" },
    { "label": "결제조건", "value": "<예: 납품 후 30일 이내 현금 지급>" }
  ],
  "items": {
    "headers": ["품명", "규격", "수량", "단가", "공급가액", "세액"],
    "aligns": ["L", "L", "R", "R", "R", "R"],
    "rows": [["<품명>", "<규격>", "<수량>", "<단가>", "<공급가액>", "<세액>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<금액>원" },
      { "label": "부가세(10%)", "value": "<금액>원" },
      { "label": "총 발주금액", "value": "<금액>원" }
    ]
  },
  "notes": ["위와 같이 발주합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<회사명> 대표이사 <대표자명>", "stamp": true },
  "footer": "납기일 및 납품장소는 상호 협의 없이 변경할 수 없습니다."
}
```

## Fixed wording

- notes: "위와 같이 발주합니다."
- footer: 납기·납품장소 고정 문구. 조건이 다르면 meta와 footer를 함께 맞춘다.

## Rules

- 금액은 천단위 콤마, 합계 값에만 "원"을 붙인다. 부가세 별도·포함을 반드시 명시한다.
- 세액은 공급가액의 10%로 계산하고 합계가 행 합과 일치하는지 검산한다.
- 납기일·납품장소·결제조건·공급사명·품명·단가·수량이 없으면 지어내지 말고 요청자에게 확인한다.
- title은 "발 주 서"처럼 글자 사이 공백을 넣는다.
