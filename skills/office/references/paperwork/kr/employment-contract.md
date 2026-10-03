# Employment Contract (근로계약서), based on the Ministry of Employment and Labor's standard form (고용노동부 표준근로계약서)

output: docx
filename: 근로계약서_<employee name>_<YYYYMMDD>.docx

## Purpose

An employment contract that follows the Ministry of Employment and Labor's standard form, made from the bundled `employment-contract` template. It holds every item Article 17 of the Labor Standards Act (근로기준법 제17조) requires: the components, calculation and payment of wages, contractual working hours, the weekly paid holiday, annual paid leave, and the place and content of work. `references/paperwork.md` says how a requested clause replaces or joins the template's.

## Required terms (confirm with the requester)

- Contract type: open-ended (an empty `endDate` leaves the contract-period line out) or fixed-term
- Employee: name, start date, workplace, duties; address and phone when given
- Contractual working hours (start, end, break), working days and the weekly paid holiday
- Wages: monthly salary (or daily or hourly wage), bonus, other allowances (`없음` when there are none), payday, payment method
- Social insurance: each of 고용보험, 산재보험, 국민연금, 건강보험 checked ☑ or unchecked ☐; a regular employee customarily has all four

## Clauses

- `start` 1. 근로개시일: `startDate`; a filled `endDate` adds the contract period
- `workplace` 2. 근무장소
- `duties` 3. 업무의 내용
- `hours` 4. 소정근로시간
- `workDays` 5. 근무일 및 휴일
- `wages` 6. 임금: all five parts
- `annualLeave` 7. 연차유급휴가
- `insurance` 8. 사회보험 적용여부: `insurances`
- `delivery` 9. 근로계약서 교부
- `faithfulPerformance` 10. 근로계약, 취업규칙 등의 성실한 이행의무
- `other` 11. 기타

## Context JSON skeleton

```json
{
  "form": "kr/employment-contract",
  "companyName": "<company name>",
  "companyPhone": "<company phone>",
  "companyAddress": "<company address>",
  "representative": "<representative name>",
  "employeeName": "<employee name>",
  "startDate": "<start date YYYY-MM-DD>",
  "endDate": "<contract end date, or an empty string for an open-ended contract>",
  "workplace": "<workplace>",
  "duties": "<duties>",
  "workStartTime": "<start time>",
  "workEndTime": "<end time>",
  "breakStart": "<break start>",
  "breakEnd": "<break end>",
  "workDays": "<working days per week, or which days>",
  "weeklyHoliday": "<weekly paid holiday>",
  "monthlySalary": "<monthly salary>",
  "bonus": "<whether there is a bonus, and the amount>",
  "otherAllowances": "<allowances, or 없음>",
  "payday": "<payday>",
  "paymentMethod": "<payment method>",
  "employeeAddress": "<employee address>",
  "employeePhone": "<employee phone>",
  "insurances": "<☑ or ☐ before each of 고용보험, 산재보험, 국민연금, 건강보험>",
  "contractDate": "<YYYY년 M월 D일>"
}
```

```json
{
  "command": "<skill>/scripts/office merge kr/employment-contract context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/employment-contract"
}
```

## Rules

- This is a draft based on the Ministry's reference form, and the company is responsible for the final review; say so in one line of the reply that delivers it.
- A part-time worker's per-day working hours or overtime premium rate goes in an added clause.
