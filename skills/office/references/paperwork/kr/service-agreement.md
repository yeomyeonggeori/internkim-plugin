# Service Agreement (용역계약서), based on private-sector practice and the general conditions of service contracts in the contract rules (계약예규 용역계약일반조건)

output: docx
filename: 용역계약서_<counterpart>_<YYYYMMDD>.docx

## Purpose

A service agreement in standard practice, made from the bundled `service-agreement` template. Every variable term of its articles is a value below; `references/paperwork.md` says how a requested clause replaces or joins the template's.

## Required terms (confirm with the requester)

- Parties: 갑 (the client) and 을 (the provider), each with trade name, representative and address; always confirm which side is our company
- The subject and scope of the service (`scopeItems`), contract period, contract amount and whether VAT is excluded (별도) or included (포함)
- How payment is made (`payments`, each instalment's share, amount and timing) and the account it goes to
- Deliverables (`deliverables`), the court with jurisdiction, the signing date
- A term the request is silent on takes its customary value, written out: acceptance 14 days, rights pass to 갑 `잔금 지급 완료와 동시에`, confidentiality 3 years after the end, late-delivery penalty 1.25/1000 a day capped at 30% of the amount, warranty 3 months

## Clauses

- `purpose` 제1조 (계약의 목적): `serviceName`
- `scope` 제2조 (용역의 대상 및 범위): `scopeItems` as numbered items
- `period` 제3조 (계약기간): `startDate`, `endDate`
- `payment` 제4조 (계약금액 및 지급방법): `totalAmount` with its amount in words, `vatNote`, `bankAccount`, `payments` as numbered items
- `deliverables` 제5조 (산출물 및 검수): `deliverables`, `acceptanceDays`
- `duties` 제6조 (계약당사자의 상호 의무)
- `reporting` 제7조 (보고 및 자료의 요청)
- `intellectualProperty` 제8조 (지식재산권): `intellectualPropertyVesting`; 을's earlier technology stays 을's
- `confidentiality` 제9조 (비밀유지): `confidentialitySurvivalYears`
- `latePenalty` 제10조 (지체상금): `latePenaltyPerMille`, `latePenaltyCapPercent`
- `warranty` 제11조 (하자보수): `warrantyMonths`
- `assignment` 제12조 (권리의무의 양도 금지)
- `termination` 제13조 (계약의 변경, 해제 및 해지)
- `damages` 제14조 (손해배상)
- `disputes` 제15조 (분쟁의 해결): `jurisdiction`

## Context JSON skeleton

```json
{
  "form": "kr/service-agreement",
  "clientName": "<갑 trade name>",
  "clientAddress": "<갑 address>",
  "clientRepresentative": "<갑 representative>",
  "providerName": "<을 trade name>",
  "providerAddress": "<을 address>",
  "providerRepresentative": "<을 representative>",
  "serviceName": "<name of the service>",
  "startDate": "<YYYY-MM-DD>",
  "endDate": "<YYYY-MM-DD>",
  "totalAmount": "<amount in figures>",
  "vatNote": "<별도|포함>",
  "bankAccount": "<bank, account number, account holder>",
  "acceptanceDays": "<number>",
  "intellectualPropertyVesting": "<when the rights pass to 갑>",
  "confidentialitySurvivalYears": "<number>",
  "latePenaltyPerMille": "<number>",
  "latePenaltyCapPercent": "<number>",
  "warrantyMonths": "<number>",
  "jurisdiction": "<court with jurisdiction>",
  "contractDate": "<YYYY년 M월 D일>",
  "scopeItems": ["<scope item 1>", "<scope item 2>"],
  "payments": ["<down payment terms>", "<interim payment terms>", "<balance terms>"],
  "deliverables": ["<deliverable 1>", "<deliverable 2>"]
}
```

```json
{
  "command": "<skill>/scripts/office merge kr/service-agreement context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/service-agreement"
}
```

## Rules

- Never decide the 갑/을 sides (whether we provide or receive the service) on your own; confirm when the request's context does not settle it.
- Party details not received stay empty strings; never invent a registration number, address or representative.
- Say in one line of the reply that delivers it that this is a draft for legal review.
