# 청구서 (Invoice)

output: pdf
filename: 청구서_<수신처>_<YYYYMMDD>.pdf

## Purpose

이미 공급한 상품·서비스에 대한 대금 지급을 거래처에 요청하는 대외 문서. 지급기한과 입금계좌가 반드시 명시되어야 하고, 청구 금액은 숫자와 한글을 함께 적는 것이 실무 관례다.

## Required fields

- recipient: 수신처 회사명 필수, 담당자명은 있으면 함께
- 공급자 상세(사업자등록번호·업태·종목·대표자)는 별도 표를 만들지 않는다 — profile.legalAttributes가 letterhead에 이미 인쇄된다.
- meta: 합계금액(한글병기), 청구일자, 지급기한, 입금계좌(profile.bankAccount) — 전부 필수
- items: 품명·규격·수량·단위·단가는 요청자 제공 값만 사용, 1행 이상
- items.totals: 공급가액 합계 → 부가세(10%) → 총 청구금액 순서
- signature: 발행일 + "회사명 대표이사 대표자명", stamp true

## Document JSON skeleton

```json
{
  "title": "청 구 서",
  "documentNumber": "I-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "recipient": { "label": "수신", "lines": ["<수신처 회사명>", "<담당자명> 님"] },
  "meta": [
    { "label": "합계금액", "value": "일금 <한글 금액>원整 (₩<금액, 천단위 콤마>) (부가세 포함)" },
    { "label": "청구일자", "value": "<YYYY-MM-DD>" },
    { "label": "지급기한", "value": "<YYYY-MM-DD>" },
    { "label": "입금계좌", "value": "<profile.bankAccount>" }
  ],
  "items": {
    "headers": ["품명", "규격", "수량", "단위", "단가", "공급가액", "세액"],
    "aligns": ["L", "L", "R", "C", "R", "R", "R"],
    "rows": [["<품명>", "<규격>", "<수량>", "<단위>", "<단가>", "<공급가액>", "<세액>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<금액>원" },
      { "label": "부가세(10%)", "value": "<금액>원" },
      { "label": "총 청구금액", "value": "<금액>원" }
    ]
  },
  "notes": ["위 금액을 청구합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<회사명> 대표이사 <대표자명>", "stamp": true },
  "footer": "지급기한까지 위 계좌로 입금해 주시기 바랍니다."
}
```

## Fixed wording

- notes: "위 금액을 청구합니다."
- footer: 지급기한 입금 안내 문구. 요청자가 다른 지급 방식을 주면 meta와 footer를 함께 맞춘다.

## Density gate (deliver 전 자기검사)

- 합계금액 meta 행에 한글병기("일금 ○○○원整")와 아라비아 숫자(₩)가 둘 다 있는가?
- 지급기한이 meta에 있는가?
- 입금계좌(profile.bankAccount)가 meta에 있는가?
- notes에 "위 금액을 청구합니다."가 있는가?

## Rules

- 금액은 천단위 콤마, 합계 값에만 "원"을 붙인다. 부가세 별도·포함을 반드시 명시한다.
- 세액은 공급가액의 10%로 계산하고 합계가 행 합과 일치하는지 검산한다.
- 지급기한과 입금계좌는 meta에서 빠뜨리지 않는다. 값이 없으면 지어내지 말고 요청자에게 확인한다.
- 품명·단가·수량이 없으면 지어내지 말고 요청자에게 확인한다.
- title은 "청 구 서"처럼 글자 사이 공백을 넣는다.
