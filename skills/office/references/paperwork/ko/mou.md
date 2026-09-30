# 업무협약서 (특허청 MOU 체결 매뉴얼 표준 조항 기반)

output: docx
filename: 업무협약서_<상대방기관명>_<YYYYMMDD>.docx

## Purpose

두 기관이 특정 분야에서 협력하기로 한 취지를 문서화하는 업무협약(MOU). 이 문서는 BUNDLED 템플릿(`mou`)에서 만들어지며, 표준 제1조~제9조 전문이 이미 템플릿에 들어 있다. 구체적인 권리·의무를 정하는 본계약이 아니라 상호 협력 의지를 확인하는 문서라는 성격은 제9조(법적 구속력)에 그대로 남는다 — context JSON 값만 채우면 된다.

## Required fields (요청자에게 확인)

- 당사자 쌍방 정보: 기관A·기관B 각각 기관명, 대표자
- 협력 취지(양 기관이 왜 협력하는지)
- 전체 협력분야 개요(cooperationItems) 및 기관A·기관B가 각각 이행할 사항(orgARoles/orgBRoles) — 구체적으로 각호 열거, 지어내지 않는다
- 유효기간(기본 2년)
- 서명일자

## Included clauses (템플릿에 이미 포함됨)

- 전문 — 양 기관 인식 문구
- 제1조 (목적)
- 제2조 (협력분야) — 전체 협력분야 목록(`cooperationItems`) + 기관A 역할(`orgARoles`) + 기관B 역할(`orgBRoles`) 각각 호 형식으로 나열
- 제3조 (홍보)
- 제4조 (실무협의회 구성 및 운영)
- 제5조 (비밀유지) — 존속기간 3년(고정)
- 제6조 (비용부담)
- 제7조 (협의조정)
- 제8조 (협약의 효력) — 유효기간 `termYears`
- 제9조 (법적 구속력) — "다만 제5조 비밀유지는 그러하지 아니하다" 예외 포함
- 말미 — 서명문, 체결일자, 양 기관 대표 서명란

## Context JSON skeleton

```json
{
  "orgAName": "<기관A 기관명>",
  "orgARepresentative": "<기관A 대표자>",
  "orgBName": "<기관B 기관명>",
  "orgBRepresentative": "<기관B 대표자>",
  "purpose": "<협력 취지>",
  "termYears": "2",
  "contractDate": "<YYYY년 M월 D일>",
  "cooperationItems": ["<협력분야 1>", "<협력분야 2>"],
  "orgARoles": ["<기관A 역할 1>", "<기관A 역할 2>"],
  "orgBRoles": ["<기관B 역할 1>", "<기관B 역할 2>"]
}
```

```json
{
  "command": "<skill>/scripts/office paperwork fill mou context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/mou"
}
```

## context 값 검사 (deliver 전 자기검사)

- `cooperationItems`, `orgARoles`, `orgBRoles`가 요청자가 제공한 내용만으로 채워졌는가? 빈 배열이면 `paperwork fill`이 거부한다.
- 기관명·대표자가 기관A/기관B 방향에 맞게 정확히 들어갔는가?
- `termYears`가 요청자 제공값이거나 기본값(2년)인가?
- `purpose`, `contractDate`가 요청 내용과 일치하는가?

## Rules

- 협력분야는 기관A·기관B 각자의 역할로 나누어 구체적으로 열거하고, 요청자가 제공하지 않은 역할을 지어내지 않는다.
- 제9조 법적 구속력 제한 조항은 MOU 관례상 반드시 포함되며 템플릿에서 삭제할 수 없다. 요청자가 법적 구속력을 부여하고 싶어하면(사실상 계약을 원하면) MOU가 아니라 계약서 스킬(service-agreement 등)을 안내한다.
- 당사자명, 유효기간 등은 요청자가 제공한 값만 사용하고, 없으면 기본값(유효기간 2년)을 쓰거나 빈 문자열로 남긴다.
- 법률 검토용 초안임을 전달 답변에 한 줄 언급. 없는 정보는 지어내지 말고 빈 문자열 처리.
