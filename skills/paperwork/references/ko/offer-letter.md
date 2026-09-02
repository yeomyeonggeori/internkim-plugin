# 채용 오퍼레터 (Offer Letter)

output: docx
filename: 오퍼레터_<후보자명>_<YYYYMMDD>.docx

## Purpose

채용 확정 후보자에게 포지션·보상 조건을 제안하는 대외 문서. 이 문서는 BUNDLED 템플릿(`offer-letter`)에서 만들어진다 — context JSON 값만 채우면 된다.

## Required fields (요청자에게 확인)

- 후보자명, 포지션(직위), 소속, 근무지, 입사예정일
- 보상: 연봉, 스톡옵션(있는 경우), 복리후생 목록
- 오퍼 유효기한(expiryDate), 발송일(offerDate)
- 수습기간 유무(있으면 조건 문구)

## Included clauses (템플릿에 이미 포함됨)

- 인사말 문단 — "{candidateName}님께, 안녕하세요..." 채용 제안 취지
- 포지션 요약 — 직위/소속/근무지/입사예정일
- 보상 — 연봉, `equity`를 채우면 스톡옵션 문장이 추가됨
- 복리후생 — `benefits` 목록을 항목별로 나열
- 수습 조건 — `probationNote`를 채운 경우에만 문단 추가
- 제안 조건 — 오퍼 유효기한(`expiryDate`)과 회신 요청 안내
- 마무리 인사 + 발송일(`offerDate`) + 회사명 + 대표이사(`representative`)

## Context JSON skeleton

```json
{
  "companyName": "<회사명>",
  "representative": "<대표자명>",
  "candidateName": "<후보자명>",
  "position": "<직위>",
  "department": "<부서명>",
  "workplace": "<근무지>",
  "startDate": "<YYYY-MM-DD>",
  "salary": "<연봉 금액>",
  "expiryDate": "<오퍼 유효기한 YYYY-MM-DD>",
  "offerDate": "<발송일 YYYY-MM-DD>",
  "equity": "<스톡옵션 조건, 없으면 빈 문자열>",
  "probationNote": "<수습기간 안내 문구, 없으면 빈 문자열>",
  "benefits": ["<복리후생 1>", "<복리후생 2>"]
}
```

```json
{
  "command": "python3 SKILL_DIR/scripts/skill_runtime.py python SKILL_DIR/scripts/fill_template.py offer-letter context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/offer-letter"
}
```

## context 값 검사 (deliver 전 자기검사)

- 후보자명, 직위, 소속, 근무지, 입사예정일이 요청 내용과 정확히 일치하는가?
- 연봉·스톡옵션 수치는 요청자가 제공한 값만 사용했는가? 관행적인 숫자를 추정해 채우지 않았는가?
- `benefits`가 빈 배열이 아닌가? (fill_template.py가 빈 리스트를 거부한다)
- `expiryDate`, `offerDate`가 요청자가 지정한 날짜인가? 지정이 없으면 채우지 말고 요청자에게 확인했는가?

## Rules

- 이름, 급여, 날짜, 조건은 절대 지어내지 않는다. 필수 정보가 없으면 요청자에게 확인한다.
- `equity`/`probationNote`는 요청자가 실제로 제공한 경우에만 채운다 — 없으면 빈 문자열로 두어 해당 문단을 자동으로 뺀다.
- 근무지·직위·입사예정일이 확정되지 않았으면 값 자체에 "추후 확정"처럼 명시적으로 미확정 상태를 적는다(필드를 비워두지 않는다).
