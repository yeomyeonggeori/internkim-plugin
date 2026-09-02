# 용역계약서 (민간 실무 표준 + 계약예규 용역계약일반조건 기반)

output: docx
filename: 용역계약서_<상대방명>_<YYYYMMDD>.docx

## Purpose

실무 표준 용역계약서. 이 문서는 BUNDLED 템플릿(`service-agreement`)에서 만들어지며, 표준 제1조~제15조 전문이 이미 템플릿에 들어 있다 — context JSON 값만 채우면 된다.

## Required fields (요청자에게 확인)

- 당사자: 갑(위임인)·을(수급인) 상호·대표자·주소 — 어느 쪽이 우리 회사인지 반드시 확인
- 용역의 대상·범위(`scopeItems`), 계약기간, 계약금액(부가세 별도/포함)
- 대금 지급 방식(`payments` 각 회차 조건), 지급일, 계좌
- 산출물(`deliverables`), 지체상금 요율(관례 1.25/1000), 하자보수 기간, 관할법원

## Included clauses (템플릿에 이미 포함됨)

- 전문 — 갑·을 당사자 표시
- 제1조 (계약의 목적) / 제2조 (용역의 대상 및 범위, `scopeItems` 각호) / 제3조 (계약기간)
- 제4조 (계약금액 및 지급방법, `payments` 각호) / 제5조 (산출물 및 검수, `deliverables` 각호, 14일 검수 기한)
- 제6조 (상호 의무) / 제7조 (보고 및 자료 요청)
- 제8조 (지식재산권 — 잔금 지급 완료 시 갑 귀속, 을의 기존 보유 기술은 유보)
- 제9조 (비밀유지, 종료 후 3년 존속)
- 제10조 (지체상금 — `penaltyRate`, 상한 30%) / 제11조 (하자보수 — `warrantyMonths`개월)
- 제12조 (권리의무 양도 금지) / 제13조 (변경·해제·해지) / 제14조 (손해배상)
- 제15조 (분쟁의 해결 — `jurisdiction` 합의관할)
- 말미 — 체결일자, 갑/을 서명란

## Context JSON skeleton

```json
{
  "clientName": "<갑 상호>",
  "clientAddress": "<갑 주소>",
  "clientRepresentative": "<갑 대표자>",
  "providerName": "<을 상호>",
  "providerAddress": "<을 주소>",
  "providerRepresentative": "<을 대표자>",
  "serviceName": "<용역명>",
  "startDate": "<YYYY-MM-DD>",
  "endDate": "<YYYY-MM-DD>",
  "totalAmount": "<숫자 금액>",
  "totalAmountKorean": "<한글 병기 금액, 예: 일금 오천만원整>",
  "vatNote": "<별도|포함>",
  "bankAccount": "<은행 계좌 예금주>",
  "penaltyRate": "1.25",
  "warrantyMonths": "3",
  "jurisdiction": "<관할법원>",
  "contractDate": "<YYYY년 M월 D일>",
  "scopeItems": ["<용역 범위 1>", "<용역 범위 2>"],
  "payments": ["<착수금 조건>", "<중도금 조건>", "<잔금 조건>"],
  "deliverables": ["<산출물 1>", "<산출물 2>"]
}
```

```json
{
  "command": "python3 <skill>/scripts/skill_runtime.py python <skill>/scripts/fill_template.py service-agreement context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/service-agreement"
}
```

## context 값 검사 (deliver 전 자기검사)

- 갑/을 방향이 요청 문맥과 일치하는가?
- 계약금액·`payments`·`deliverables`·`scopeItems`가 요청자 제공 값 그대로인가? 금액은 한글병기(일금 ○○○원整) 관례를 따랐는가?
- `penaltyRate`, `warrantyMonths`가 요청자 제공값이거나 기본값(1.25/1000, 3개월)인가?
- 당사자 표시(상호·주소·대표자)가 갑·을 모두 채워졌거나, 못 받은 값은 빈 문자열로 남겼는가?

## Rules

- 갑/을 방향(우리가 제공자인지 수령자인지)을 임의로 정하지 말 것 — 요청 문맥으로 판단이 안 서면 확인한다.
- 요청자가 지체상금·하자보수 등 특정 조항의 수치를 주면 그 값을 쓰고, 안 주면 기본값(지체상금 1.25/1000, 하자보수 3개월)을 쓴다.
- 법률 검토용 초안임을 전달 답변에 한 줄 언급. 없는 정보(사업자번호·주소 등)는 지어내지 말고 빈 문자열 처리.
