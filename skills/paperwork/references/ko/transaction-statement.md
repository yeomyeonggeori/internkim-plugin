# 거래명세서 (Transaction Statement)

output: pdf
filename: 거래명세서_<공급받는자>_<YYYYMMDD>.pdf

## Purpose

완료된 거래 내역을 공급자와 공급받는자 사이에 기록으로 남기는 대외 문서. 견적서와 달리 확정 거래의 실제 품목·수량·금액을 옮겨 적고, 수령 확인을 받는 것이 실무 관례다.

## Required fields

- recipient: 공급받는자 회사명 필수, 담당자명은 있으면 함께. 공급받는자 사업자등록번호를 받았으면 회사명 다음 줄에 추가한다.
- 공급자 상세(사업자등록번호·업태·종목·대표자)는 별도 표를 만들지 않는다 — profile.legalAttributes가 letterhead에 이미 인쇄된다.
- meta: 거래일자 필수, meta 마지막 행에 인수자 확인란을 반드시 넣는다
- items: 품명·규격·수량·단위·단가는 요청자 제공 값만 사용, 1행 이상
- items.totals: 공급가액 합계 → 세액 합계 → 총 합계 순서
- signature: 공급자 측 발행일 + "회사명 대표이사 대표자명", stamp true. 인수자 확인은 signature가 아니라 meta 마지막 행으로 넣는다(스키마는 signature를 하나만 지원한다).

## Document JSON skeleton

```json
{
  "title": "거 래 명 세 서",
  "documentNumber": "T-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "recipient": { "label": "공급받는자", "lines": ["<공급받는자 회사명>", "<담당자명> 님"] },
  "meta": [
    { "label": "거래일자", "value": "<YYYY-MM-DD>" },
    { "label": "인수자", "value": "<인수자명>  (서명 또는 인)" }
  ],
  "items": {
    "headers": ["품명", "규격", "수량", "단위", "단가", "공급가액", "세액"],
    "aligns": ["L", "L", "R", "C", "R", "R", "R"],
    "rows": [["<품명>", "<규격>", "<수량>", "<단위>", "<단가>", "<공급가액>", "<세액>"]],
    "totals": [
      { "label": "공급가액 합계", "value": "<금액>원" },
      { "label": "세액 합계", "value": "<금액>원" },
      { "label": "총 합계 (부가세 포함)", "value": "<금액>원" }
    ]
  },
  "notes": ["위와 같이 계산합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<회사명> 대표이사 <대표자명>", "stamp": true },
  "footer": "본 명세서는 실제 거래 내역과 일치함을 확인합니다."
}
```

## Fixed wording

- notes: "위와 같이 계산합니다."
- 인수자 확인란은 meta 마지막 행에서 절대 빠지지 않는다. 인수자명을 못 받았으면 이름 자리는 비워 두고 "(서명 또는 인)"만 남긴다.

## Density gate (deliver 전 자기검사)

- 거래일자가 meta에 있는가?
- 품목표가 7열(품명·규격·수량·단위·단가·공급가액·세액)인가?
- meta 마지막 행이 인수자 확인란("(서명 또는 인)")인가?
- signature는 공급자 측("회사명 대표이사 대표자명")이고 stamp: true인가?

## Rules

- 금액은 천단위 콤마, 합계 값에만 "원"을 붙인다. 부가세 별도·포함을 반드시 명시한다.
- 세액은 공급가액의 10%로 계산하고 합계가 행 합과 일치하는지 검산한다.
- 공급받는자 명, 품명·단가·수량·거래일자가 없으면 지어내지 말고 요청자에게 확인한다.
- title은 "거 래 명 세 서"처럼 글자 사이 공백을 넣는다.
