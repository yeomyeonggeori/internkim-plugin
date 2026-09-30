# 재직증명서 (Certificate of Employment)

output: pdf
filename: 재직증명서_<성명>_<YYYYMMDD>.pdf

## Purpose

현재 재직 중인 임직원의 재직 사실을 증명하는 대내외 제출용 문서. 제출처(용도)가 있는 경우가 많으므로 확인한다.

## Required fields

- documentNumber: company_document_register가 반환한 번호를 "제 <YYYY>-<NNN>호" 형식으로 표기한다 (예: 제 2026-013호)
- meta 인적사항(4): 성명, 생년월일, 주소, 소속(부서)
- meta 재직사항(4): 직위(직급), 담당업무, 재직기간, 제출용도
- 재직기간은 "<입사일> ~ 현재 재직 중" 형식으로 표기 (아직 재직 중이므로 종료일이 없음)
- signature: 발급일 + "회사명 대표이사 대표자명", stamp true

## Document JSON skeleton

```json
{
  "title": "재 직 증 명 서",
  "documentNumber": "제 <YYYY>-<NNN>호",
  "profile": { ...company profile... },
  "meta": [
    { "label": "성명", "value": "<성명>" },
    { "label": "생년월일", "value": "<YYYY-MM-DD>" },
    { "label": "주소", "value": "<주소>" },
    { "label": "소속", "value": "<부서명>" },
    { "label": "직위", "value": "<직위>" },
    { "label": "담당업무", "value": "<담당업무>" },
    { "label": "재직기간", "value": "<입사일> ~ 현재 재직 중" },
    { "label": "제출용도", "value": "<제출처 또는 용도>" }
  ],
  "notes": ["위와 같이 재직하고 있음을 증명합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "<회사명> 대표이사 <대표자명>", "stamp": true },
  "footer": "본 증명서는 발급일 기준 재직 사실을 증명합니다."
}
```

## Fixed wording

- notes: "위와 같이 재직하고 있음을 증명합니다."
- 재직기간의 종료 시점은 항상 "현재 재직 중"으로 고정한다 (재직증명서는 퇴사자에게 발급하지 않는다).

## Density gate (deliver 전 자기검사)

- 인적사항 4개(성명·생년월일·주소·소속)가 meta에 전부 있는가?
- 재직사항 4개(직위·담당업무·재직기간·제출용도)가 meta에 전부 있는가?
- notes에 "위와 같이 재직하고 있음을 증명합니다."가 있는가?
- signature에 stamp: true가 있는가?

## Rules

- 성명, 생년월일, 주소, 소속, 직위, 담당업무, 입사일, 용도가 없으면 지어내지 말고 요청자에게 확인한다.
- 근로기준법 제39조에 따라 근로자가 요구한 사항만 기재한다 — 요구하지 않은 급여·평가·계약조건 등은 절대 넣지 않는다.
- title은 "재 직 증 명 서"처럼 글자 사이 공백을 넣는다.
