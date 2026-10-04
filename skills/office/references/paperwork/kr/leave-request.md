# Leave Request (휴가신청서)

output: pdf
filename: 휴가신청서_<applicant>_<YYYYMMDD>.pdf

## Purpose

An internal document in which an employee applies for leave and gets it approved by the person in charge and the approver.

## Required fields

- approvalLine: the approvers the request names, in its order, each `{"role", "name"}`; when it names none, the roles "담당", "승인" without names
- meta: 신청자 (applicant), 소속/직위 (department and position), 휴가종류 (type of leave), 휴가기간 (leave period), 사유 (reason), 비상연락처 (emergency contact)
- 휴가종류 uses the type the requester named (연차 annual, 반차 half-day, 병가 sick, 경조 family event, and so on) as it is
- signature: application date + the applicant's name, stamp false

## Document JSON skeleton

```json
{
  "form": "kr/leave-request",
  "title": "휴 가 신 청 서",
  "documentNumber": "<the number company_document_register returned>",
  "approvalLine": [{ "role": "<role>", "name": "<name>" }],
  "meta": [
    { "label": "신청자", "value": "<name>" },
    { "label": "소속/직위", "value": "<department> / <position>" },
    { "label": "휴가종류", "value": "<연차/반차/병가/경조 등>" },
    { "label": "휴가기간", "value": "<YYYY-MM-DD> ~ <YYYY-MM-DD> (<days>일)" },
    { "label": "사유", "value": "<reason>" },
    { "label": "비상연락처", "value": "<phone>" }
  ],
  "notes": ["위와 같이 휴가를 신청합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "신청자 <name>", "stamp": false },
  "footer": ""
}
```

## Fixed wording

- notes: "위와 같이 휴가를 신청합니다."

## Rules

- Count the days of the leave period exactly from its start and end dates, and when the way working days and holidays are counted differs from company rules, confirm with the requester.
- A leave request never uses a stamp (the applicant signs it, so signature.stamp is always false).
- Space the title's characters apart: "휴 가 신 청 서".
