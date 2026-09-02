# 근로계약서 (고용노동부 표준근로계약서 기반)

output: docx
filename: 근로계약서_<근로자명>_<YYYYMMDD>.docx

## Purpose

고용노동부 표준근로계약서 서식을 그대로 따르는 근로계약서. 이 문서는 BUNDLED 템플릿(`employment-contract`)에서 만들어지며, 근로기준법 제17조 필수 기재사항(임금의 구성항목·계산방법·지급방법, 소정근로시간, 주휴일, 연차유급휴가, 취업 장소·업무)이 이미 템플릿에 전부 포함되어 있다 — context JSON 값만 채우면 된다.

## Required fields (요청자에게 확인)

- 계약 형태: 기간의 정함이 없는지/있는지 (있으면 `endDate` 포함)
- 근로자: 성명·주소·연락처 / 근로개시일 / 근무장소 / 업무의 내용
- 소정근로시간(시업·종업·휴게), 근무일과 주휴일
- 임금: 월급(또는 일급·시급), 상여금 유무·금액, 제수당 유무·내역, 임금지급일, 지급방법
- 사회보험 4종 적용 여부 (스타트업 정규직 기본: 4대보험 전부 체크)

## Included clauses (템플릿에 이미 포함됨)

- 전문 — 사업주·근로자 당사자 표시
- 1. 근로개시일 — `endDate`를 채우면 "근로계약기간: 시작~종료"로, 비우면 "기간의 정함이 없는 근로계약"으로 전환
- 2. 근무장소 / 3. 업무의 내용 / 4. 소정근로시간(시업·종업·휴게) / 5. 근무일 및 휴일
- 6. 임금 — 월급·상여금·기타급여·지급일·지급방법 5개 세부 전부 포함
- 7. 연차유급휴가 / 8. 사회보험 적용여부
- 9. 근로계약서 교부 (근로기준법 제17조 이행)
- 10. 근로계약·취업규칙 등의 성실한 이행의무 / 11. 기타
- 말미 — 체결일자, 사업주/근로자 서명란

## Context JSON skeleton

```json
{
  "companyName": "<회사명>",
  "companyPhone": "<회사 전화>",
  "companyAddress": "<회사 주소>",
  "representative": "<대표자명>",
  "employeeName": "<근로자명>",
  "startDate": "<근로개시일 YYYY-MM-DD>",
  "endDate": "<계약종료일, 기간의 정함이 없으면 빈 문자열>",
  "workplace": "<근무장소>",
  "duties": "<담당업무>",
  "workStartTime": "<시업시각>",
  "workEndTime": "<종업시각>",
  "breakStart": "<휴게시작>",
  "breakEnd": "<휴게종료>",
  "workDays": "<근무일수/요일>",
  "weeklyHoliday": "<주휴일>",
  "monthlySalary": "<월급>",
  "bonus": "<상여금 유무·금액>",
  "otherAllowances": "<제수당 내역, 없으면 '없음'>",
  "payday": "<임금지급일>",
  "paymentMethod": "<지급방법>",
  "employeeAddress": "<근로자 주소>",
  "employeePhone": "<근로자 연락처>",
  "insurances": "☑ 고용보험  ☑ 산재보험  ☑ 국민연금  ☑ 건강보험",
  "contractDate": "<YYYY년 M월 D일>"
}
```

```json
{
  "command": "python3 <skill>/scripts/skill_runtime.py python <skill>/scripts/fill_template.py employment-contract context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/employment-contract"
}
```

## context 값 검사 (deliver 전 자기검사)

- 요청자가 준 급여·날짜·시간이 정확히 반영됐는가? 안 준 값은 지어내지 않고 빈 문자열로 남겼는가?
- 임금 5개 세부(월급·상여금·기타급여·지급일·지급방법)가 모두 채워졌는가?
- `endDate` 유무가 요청자가 말한 계약 형태(기간제/무기한)와 일치하는가?
- 사회보험 항목이 요청자 지시와 다르면 `insurances` 값을 그에 맞게 수정했는가?

## Rules

- 고용노동부 참고 서식 기반의 초안이며 최종 검토 책임은 회사에 있다(전달 답변에 한 줄 언급).
- 근로자 개인정보(주소·연락처)를 지어내지 않는다 — 없으면 빈 문자열로.
- 단시간근로자(주 15시간 미만 등)는 근로일별 근로시간 표·초과근로 가산임금률 항목이 이 템플릿에 없다는 점을 알리고, 필요하면 fallback blocks 경로(`render_paperwork.py`)로 추가 조항을 작성한다.
