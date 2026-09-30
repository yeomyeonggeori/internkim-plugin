# 휴가신청서 (Leave Request)

output: pdf
filename: 휴가신청서_<신청자>_<YYYYMMDD>.pdf

## Purpose

임직원이 휴가 사용을 신청하고 담당자·승인권자의 결재를 받는 대내 문서.

## Required fields

- approvalLine: ["담당", "승인"]
- meta: 신청자, 소속/직위, 휴가종류, 휴가기간, 사유, 비상연락처
- 휴가종류는 요청자가 밝힌 종류(연차/반차/병가/경조 등) 그대로 사용
- signature: 신청일 + 신청자 성명, stamp false

## Document JSON skeleton

```json
{
  "title": "휴 가 신 청 서",
  "documentNumber": "LR-<YYYYMMDD>-<순번>",
  "profile": { ...company profile... },
  "approvalLine": ["담당", "승인"],
  "meta": [
    { "label": "신청자", "value": "<성명>" },
    { "label": "소속/직위", "value": "<부서명> / <직위>" },
    { "label": "휴가종류", "value": "<연차/반차/병가/경조 등>" },
    { "label": "휴가기간", "value": "<YYYY-MM-DD> ~ <YYYY-MM-DD> (<일수>일)" },
    { "label": "사유", "value": "<사유>" },
    { "label": "비상연락처", "value": "<연락처>" }
  ],
  "notes": ["위와 같이 휴가를 신청합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "신청자 <성명>", "stamp": false },
  "footer": ""
}
```

## Fixed wording

- notes: "위와 같이 휴가를 신청합니다."
- approvalLine은 항상 ["담당", "승인"] 두 칸으로 고정한다.

## Rules

- 신청자, 휴가종류, 휴가기간, 사유가 없으면 지어내지 말고 요청자에게 확인한다.
- 휴가기간의 일수는 시작일·종료일로부터 정확히 계산하고 근무일/휴일 산정 기준이 회사 규정과 다르면 요청자에게 확인한다.
- 휴가신청서는 stamp를 사용하지 않는다 (신청자 본인 서명이므로 signature.stamp는 항상 false).
- title은 "휴 가 신 청 서"처럼 글자 사이 공백을 넣는다.
