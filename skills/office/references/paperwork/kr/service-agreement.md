# Service Agreement (용역계약서), based on private-sector practice and the general conditions of service contracts in the contract rules (계약예규 용역계약일반조건)

output: docx
filename: 용역계약서_<counterpart>_<YYYYMMDD>.docx

## Purpose

A service agreement in standard practice. It is made from the BUNDLED template (`service-agreement`), which already holds the full standard Articles 1 to 15. Only the context JSON values need filling.

## Required fields (confirm with the requester)

- Parties: 갑 (the client) and 을 (the provider), each with trade name, representative and address; always confirm which side is our company
- The subject and scope of the service (`scopeItems`), contract period, contract amount (VAT excluded or included)
- How payment is made (`payments`, the terms of each instalment), payday, bank account
- Deliverables (`deliverables`), the late-delivery penalty rate (customarily 1.25/1000), warranty period, court with jurisdiction

## Included clauses (already in the template)

- Preamble: 갑 and 을 as parties
- 제1조 (계약의 목적), purpose / 제2조 (용역의 대상 및 범위), subject and scope, `scopeItems` as numbered items / 제3조 (계약기간), contract period
- 제4조 (계약금액 및 지급방법), amount and payment, `payments` as numbered items / 제5조 (산출물 및 검수), deliverables and acceptance, `deliverables` as numbered items, 14-day acceptance deadline
- 제6조 (상호 의무), mutual duties / 제7조 (보고 및 자료 요청), reporting and requests for material
- 제8조 (지식재산권), intellectual property: belongs to 갑 once the balance is paid; 을's existing technology is reserved
- 제9조 (비밀유지), confidentiality: survives 3 years after the end
- 제10조 (지체상금), late-delivery penalty: `penaltyRate`, capped at 30% / 제11조 (하자보수), warranty: `warrantyMonths` months
- 제12조 (권리의무 양도 금지), no assignment / 제13조 (변경·해제·해지), amendment and termination / 제14조 (손해배상), damages
- 제15조 (분쟁의 해결), disputes: the agreed `jurisdiction` court
- Closing: signing date, signature blocks for 갑 and 을

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
  "penaltyRate": "1.25",
  "warrantyMonths": "3",
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

## Context value check (self-check before delivery)

- Do the 갑/을 sides match the context of the request?
- Are the contract amount, `payments`, `deliverables` and `scopeItems` exactly the requester's values? Was `totalAmountKorean` left out, since it is filled from `totalAmount`?
- Are `penaltyRate` and `warrantyMonths` the requester's values or the defaults (1.25/1000, 3 months)?
- Are the party details (trade name, address, representative) filled for both 갑 and 을, or left as empty strings where not received?

## Rules

- Never decide the 갑/을 sides (whether we provide or receive the service) on your own; confirm when the request's context does not settle it.
- When the requester gives figures for particular clauses such as the late-delivery penalty or the warranty, use them; otherwise use the defaults (late-delivery penalty 1.25/1000, warranty 3 months).
- Say in one line of the reply that delivers it that this is a draft for legal review. Never invent missing information (business registration number, address and the like); leave an empty string.
