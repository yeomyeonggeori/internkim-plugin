# Memorandum of Understanding (업무협약서), based on the standard clauses of the Korean Intellectual Property Office's MOU manual (특허청 MOU 체결 매뉴얼)

output: docx
filename: 업무협약서_<counterpart organization>_<YYYYMMDD>.docx

## Purpose

A memorandum of understanding (MOU) recording that two organizations intend to cooperate in a given field. It is made from the BUNDLED template (`mou`), which already holds the full standard Articles 1 to 9. Article 9 (legal effect) keeps its nature as a document confirming the will to cooperate, not a main contract fixing concrete rights and duties. Only the context JSON values need filling.

## Required fields (confirm with the requester)

- Both parties: for organization A and organization B, the name and the representative
- The purpose of the cooperation (why the two organizations cooperate)
- An outline of the whole field of cooperation (cooperationItems) and what organization A and organization B each carry out (orgARoles/orgBRoles), listed item by item, never invented
- Term (2 years by default)
- Signing date

## Included clauses (already in the template)

- Preamble: the two organizations' shared understanding
- 제1조 (목적), purpose
- 제2조 (협력분야), fields of cooperation: the whole list (`cooperationItems`), organization A's roles (`orgARoles`) and organization B's roles (`orgBRoles`), each as numbered items
- 제3조 (홍보), publicity
- 제4조 (실무협의회 구성 및 운영), working committee
- 제5조 (비밀유지), confidentiality: survives 3 years (fixed)
- 제6조 (비용부담), costs
- 제7조 (협의조정), consultation
- 제8조 (협약의 효력), effect: term `termYears`
- 제9조 (법적 구속력), legal effect: including the exception "다만 제5조 비밀유지는 그러하지 아니하다" (except Article 5, confidentiality)
- Closing: signing statement, signing date, signature blocks for both representatives

## Context JSON skeleton

```json
{
  "orgAName": "<organization A name>",
  "orgARepresentative": "<organization A representative>",
  "orgBName": "<organization B name>",
  "orgBRepresentative": "<organization B representative>",
  "purpose": "<purpose of the cooperation>",
  "termYears": "2",
  "contractDate": "<YYYY년 M월 D일>",
  "cooperationItems": ["<field of cooperation 1>", "<field of cooperation 2>"],
  "orgARoles": ["<organization A role 1>", "<organization A role 2>"],
  "orgBRoles": ["<organization B role 1>", "<organization B role 2>"]
}
```

```json
{
  "command": "<skill>/scripts/office paperwork fill mou context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/mou"
}
```

## Context value check (self-check before delivery)

- Are `cooperationItems`, `orgARoles` and `orgBRoles` filled only with what the requester gave? `paperwork fill` refuses an empty array.
- Are the names and representatives on the right side, organization A or B?
- Is `termYears` the requester's value or the default (2 years)?
- Do `purpose` and `contractDate` match the request?

## Rules

- List the fields of cooperation concretely, split into organization A's and organization B's roles, and never invent a role the requester did not give.
- The Article 9 clause limiting legal effect is always included by MOU convention and cannot be removed from the template. When the requester wants it legally binding (in effect, wants a contract), point them to a contract form (service-agreement and the like) instead of an MOU.
- Use only the party names, term and other values the requester gave; when missing, use the default (a 2-year term) or leave an empty string.
- Say in one line of the reply that delivers it that this is a draft for legal review. Never invent missing information; leave an empty string.
