# 비밀유지협약서 (중소벤처기업부 표준비밀유지협약서 기반)

output: docx
filename: 비밀유지협약서_<상대방명>_<YYYYMMDD>.docx

## Purpose

중소벤처기업부가 마련·권고하는 표준비밀유지협약서(NDA). 이 문서는 BUNDLED 템플릿(`nda`)에서 만들어지며, 표준 제1조~제13조 전문이 이미 템플릿에 들어 있다. 요청자가 명시적으로 뺀 조항이 없는 한 조항을 줄이지 않는다 — context JSON 값만 채우면 된다.

## Required fields (요청자에게 확인)

- 당사자 쌍방 정보: "갑"·"을" 각각 기관명(상호), 주소, 대표자
- 편면(일방만 정보 제공)인지 상호(양측 모두 정보제공자·정보수령자가 될 수 있음)인지 — 기본은 상호형
- 본 업무 요지(비밀정보가 오가는 사업·거래의 내용)
- 협약 유효기간(기본 5년)과 종료 후 비밀유지의무 존속기간(기본 3년)
- 위약벌 조항 포함 여부와 금액(손해배상만으로 할지, 위약벌을 더할지)
- 관할법원

## Included clauses (템플릿에 이미 포함됨)

- 전문 — 갑·을 당사자 표시 및 협약 체결 취지
- 제1조 (협약의 목적)
- 제2조 (비밀정보의 정의)
- 제3조 (비밀의 표시) — 서면/구두 제공 시 표시·고지 의무
- 제4조 (비밀 유지 기간 등) — 협약 유효기간·비밀유지 존속기간
- 제5조 (정보의 사용용도 및 정보취급자 제한)
- 제6조 (비밀유지의무) — 비밀정보 제외사유 1~6호 전부 포함
- 제7조 (손해배상, 위약벌) — `penaltyAmount`를 채우면 위약벌 문장이 추가되고, 비워두면 손해배상 조항만 남는다
- 제8조 (비밀정보의 반환 등)
- 제9조 (권리의 부존재 등)
- 제10조 (권리의무의 양도, 협약의 변경)
- 제11조 (협약의 분리가능성)
- 제12조 (분쟁의 해결) — 조정 불성립 시 `jurisdiction` 관할법원
- 제13조 (보칙)
- 말미 — 체결일자, 갑/을 서명란(명칭·주소·대표자)

## Context JSON skeleton

```json
{
  "partyAName": "<갑 기관명>",
  "partyAAddress": "<갑 주소>",
  "partyARepresentative": "<갑 대표자>",
  "partyBName": "<을 기관명>",
  "partyBAddress": "<을 주소>",
  "partyBRepresentative": "<을 대표자>",
  "purpose": "<본 업무 요지>",
  "termYears": "5",
  "survivalYears": "3",
  "jurisdiction": "<관할법원>",
  "contractDate": "<YYYY년 M월 D일>",
  "penaltyAmount": "<위약벌 금액, 없으면 빈 문자열>"
}
```

```json
{
  "command": "python3 <skill>/scripts/skill_runtime.py python <skill>/scripts/fill_template.py nda context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/nda"
}
```

## context 값 검사 (deliver 전 자기검사)

- 요청자가 준 갑·을 명칭·주소·대표자가 정확히 들어갔는가? 못 받은 값은 지어내지 말고 빈 문자열로 남겼는가?
- `termYears`/`survivalYears`가 요청자 제공값이거나 기본값(5년/3년)인가?
- `penaltyAmount`는 요청자가 금액을 준 경우에만 채웠는가? 안 준 값을 임의로 채우지 않았는가?
- `jurisdiction`, `contractDate`, `purpose`가 요청 내용과 일치하는가?

## Rules

- 갑/을을 임의로 정보제공자 또는 정보수령자로 고정하지 말 것 — 기본은 상호형(양측 모두 정보제공자·정보수령자가 될 수 있음)이며, 요청자가 편면(일방만 제공)을 요구하면 그 취지를 답변에서 안내한다(템플릿 문구 자체는 상호형 고정).
- `penaltyAmount`는 요청자가 금액을 제공한 경우에만 채운다. 금액을 받지 못하면 빈 문자열로 두어 위약벌 문장을 자동으로 뺀다.
- 법률 검토용 초안임을 전달 답변에 한 줄 언급. 없는 정보(주소·대표자·관할법원 등)는 지어내지 말고 빈 문자열 처리.
