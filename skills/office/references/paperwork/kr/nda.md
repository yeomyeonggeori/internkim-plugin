# Non-Disclosure Agreement (비밀유지협약서), based on the Ministry of SMEs and Startups' standard NDA (중소벤처기업부 표준비밀유지협약서)

output: docx
filename: 비밀유지협약서_<counterpart>_<YYYYMMDD>.docx

## Purpose

The standard non-disclosure agreement (NDA) prepared and recommended by the Ministry of SMEs and Startups. It is made from the BUNDLED template (`nda`), which already holds the full standard Articles 1 to 13. Never cut a clause unless the requester explicitly removed it. Only the context JSON values need filling.

## Required fields (confirm with the requester)

- Both parties: for "갑" (party A) and "을" (party B), the organization or trade name, address and representative
- One-way (only one side provides information) or mutual (either side may disclose and receive); mutual by default
- The gist of the underlying work (the business or deal in which confidential information changes hands)
- The agreement's term (5 years by default) and how long the confidentiality duty survives after it ends (3 years by default)
- Whether to include a penalty clause, and its amount (damages alone, or a penalty on top)
- The court with jurisdiction

## Included clauses (already in the template)

- Preamble: 갑 and 을 as parties, and the purpose of the agreement
- 제1조 (협약의 목적), purpose
- 제2조 (비밀정보의 정의), definition of confidential information
- 제3조 (비밀의 표시), marking: the duty to mark or announce information given in writing or orally
- 제4조 (비밀 유지 기간 등), term: the agreement's term and the survival period
- 제5조 (정보의 사용용도 및 정보취급자 제한), use and who may handle it
- 제6조 (비밀유지의무), duty of confidentiality: all six exclusions, items 1 to 6
- 제7조 (손해배상, 위약벌), damages and penalty: a filled `penaltyAmount` adds the penalty sentence; empty, only the damages clause remains
- 제8조 (비밀정보의 반환 등), return of information
- 제9조 (권리의 부존재 등), no rights granted
- 제10조 (권리의무의 양도, 협약의 변경), assignment and amendment
- 제11조 (협약의 분리가능성), severability
- 제12조 (분쟁의 해결), disputes: the `jurisdiction` court when mediation fails
- 제13조 (보칙), supplementary provisions
- Closing: signing date, signature blocks for 갑 and 을 (name, address, representative)

## Context JSON skeleton

```json
{
  "form": "kr/nda",
  "partyAName": "<갑 organization name>",
  "partyAAddress": "<갑 address>",
  "partyARepresentative": "<갑 representative>",
  "partyBName": "<을 organization name>",
  "partyBAddress": "<을 address>",
  "partyBRepresentative": "<을 representative>",
  "purpose": "<gist of the underlying work>",
  "termYears": "5",
  "survivalYears": "3",
  "jurisdiction": "<court with jurisdiction>",
  "contractDate": "<YYYY년 M월 D일>",
  "penaltyAmount": "<penalty amount, or an empty string when there is none>"
}
```

```json
{
  "command": "<skill>/scripts/office merge kr/nda context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/nda"
}
```

## Context value check (self-check before delivery)

- Are the names, addresses and representatives of 갑 and 을 the requester gave written exactly? Are values not received left as empty strings rather than invented?
- Are `termYears`/`survivalYears` the requester's values or the defaults (5 years / 3 years)?
- Is `penaltyAmount` filled only when the requester gave an amount, and never filled at will?
- Do `jurisdiction`, `contractDate` and `purpose` match the request?

## Rules

- Never fix 갑 or 을 as the disclosing or receiving party on your own. The default is mutual (either side may disclose and receive); when the requester wants one-way (only one side provides), explain that in the reply (the template's wording itself stays mutual).
- Fill `penaltyAmount` only when the requester gave an amount. Without one, leave it an empty string so the penalty sentence drops out.
- Say in one line of the reply that delivers it that this is a draft for legal review. Never invent missing information (address, representative, court and the like); leave an empty string.
