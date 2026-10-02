# Employment Contract (근로계약서), based on the Ministry of Employment and Labor's standard form (고용노동부 표준근로계약서)

output: docx
filename: 근로계약서_<employee name>_<YYYYMMDD>.docx

## Purpose

An employment contract that follows the Ministry of Employment and Labor's standard form as it is. It is made from the BUNDLED template (`employment-contract`), which already contains every item Article 17 of the Labor Standards Act (근로기준법 제17조) requires: the components, calculation and payment of wages, contractual working hours, the weekly paid holiday, annual paid leave, and the place and content of work. Only the context JSON values need filling.

## Required fields (confirm with the requester)

- Contract type: open-ended or fixed-term (fixed-term includes `endDate`)
- Employee: name, address and phone / start date / workplace / duties
- Contractual working hours (start, end, break), working days and the weekly paid holiday
- Wages: monthly salary (or daily or hourly wage), whether there is a bonus and how much, whether there are allowances and what they are, payday, payment method
- Which of the four social insurances apply (a startup's regular employee by default: all four checked)

## Included clauses (already in the template)

- Preamble: the employer and the employee as parties
- 1. 근로개시일 (start date): writes "근로개시일: start"; a filled `endDate` adds the paragraph "근로계약기간: start~end", and an empty one leaves it out, which makes the contract open-ended
- 2. 근무장소 (workplace) / 3. 업무의 내용 (duties) / 4. 소정근로시간 (working hours: start, end, break) / 5. 근무일 및 휴일 (working days and holidays)
- 6. 임금 (wages): all five parts, monthly salary, bonus, other pay, payday and payment method
- 7. 연차유급휴가 (annual paid leave) / 8. 사회보험 적용여부 (social insurance)
- 9. 근로계약서 교부 (handing over the contract, as Article 17 requires)
- 10. 근로계약·취업규칙 등의 성실한 이행의무 (duty to honour the contract and work rules) / 11. 기타 (other)
- Closing: contract date, signature blocks for employer and employee

## Context JSON skeleton

```json
{
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
  "otherAllowances": "<allowances, or '없음' when there are none>",
  "payday": "<payday>",
  "paymentMethod": "<payment method>",
  "employeeAddress": "<employee address>",
  "employeePhone": "<employee phone>",
  "insurances": "☑ 고용보험  ☑ 산재보험  ☑ 국민연금  ☑ 건강보험",
  "contractDate": "<YYYY년 M월 D일>"
}
```

```json
{
  "command": "<skill>/scripts/office paperwork fill employment-contract context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/employment-contract"
}
```

## Context value check (self-check before delivery)

- Are the salary, dates and hours the requester gave written exactly? Are values the requester did not give left as empty strings rather than invented?
- Are all five wage parts (monthly salary, bonus, other pay, payday, payment method) filled?
- Does the presence of `endDate` match the contract type the requester stated (fixed-term or open-ended)?
- When the requester's instructions on social insurance differ, was `insurances` changed to match?

## Rules

- This is a draft based on the Ministry's reference form, and the company is responsible for the final review (say so in one line of the reply that delivers it).
- Never invent the employee's personal details (address, phone); leave them as empty strings when missing.
- For a part-time worker (for example under 15 hours a week), say that this template has no per-day working hours table and no overtime premium rate, and when needed write the extra clauses through the fallback blocks path (`paperwork render`).
