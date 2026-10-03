# Memorandum of Understanding (업무협약서), based on the standard clauses of the Korean Intellectual Property Office's MOU manual (특허청 MOU 체결 매뉴얼)

output: docx
filename: 업무협약서_<counterpart organization>_<YYYYMMDD>.docx

## Purpose

A memorandum of understanding recording that two organizations intend to cooperate in a field, made from the bundled `mou` template. It confirms the will to cooperate rather than fixing concrete rights and duties. Every variable term of its articles is a value below; `references/paperwork.md` says how a requested clause replaces or joins the template's.

## Required terms (confirm with the requester)

- Both parties: for organization A and organization B, the name and the representative
- The purpose of the cooperation
- The whole field of cooperation (`cooperationItems`) and what each organization carries out (`orgARoles`, `orgBRoles`), item by item
- The signing date
- A term the request is silent on takes its customary value, written out: the working council meets `매분기 1회`, confidentiality survives 3 years, the agreement runs 2 years, extension notice 1 month before expiry

## Clauses

- `purpose` 제1조 (목적)
- `cooperation` 제2조 (협력분야): `cooperationItems`, `orgARoles`, `orgBRoles` as numbered items
- `publicity` 제3조 (홍보)
- `council` 제4조 (실무협의회 구성 및 운영): `councilMeetingFrequency`
- `confidentiality` 제5조 (비밀유지): `confidentialitySurvivalYears`
- `costs` 제6조 (비용부담)
- `consultation` 제7조 (협의조정)
- `effect` 제8조 (협약의 효력): `termYears`, `renewalNoticeMonths`
- `bindingEffect` 제9조 (법적 구속력): not legally binding, except the confidentiality clause

## Context JSON skeleton

```json
{
  "form": "kr/mou",
  "orgAName": "<organization A name>",
  "orgARepresentative": "<organization A representative>",
  "orgBName": "<organization B name>",
  "orgBRepresentative": "<organization B representative>",
  "purpose": "<purpose of the cooperation>",
  "councilMeetingFrequency": "<how often the council meets>",
  "confidentialitySurvivalYears": "<number>",
  "termYears": "<number>",
  "renewalNoticeMonths": "<number>",
  "contractDate": "<YYYY년 M월 D일>",
  "cooperationItems": ["<field of cooperation 1>", "<field of cooperation 2>"],
  "orgARoles": ["<organization A role 1>", "<organization A role 2>"],
  "orgBRoles": ["<organization B role 1>", "<organization B role 2>"]
}
```

```json
{
  "command": "<skill>/scripts/office merge kr/mou context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/mou"
}
```

## Rules

- When the requester wants the agreement legally binding, they want a contract: point them to a contract form such as service-agreement instead of removing `bindingEffect`.
- Say in one line of the reply that delivers it that this is a draft for legal review.
