# Non-Disclosure Agreement (비밀유지협약서), based on the Ministry of SMEs and Startups' standard NDA (중소벤처기업부 표준비밀유지협약서)

output: docx
filename: 비밀유지협약서_<counterpart>_<YYYYMMDD>.docx

## Purpose

The standard non-disclosure agreement the Ministry of SMEs and Startups recommends, made from the bundled `nda` template. Its wording is mutual: either side may disclose and receive. Every variable term of its articles is a value below; `references/paperwork.md` says how a requested clause replaces or joins the template's.

## Required terms (confirm with the requester)

- Both parties: for 갑 and 을, the organization or trade name, address and representative
- The underlying work in which confidential information changes hands
- A penalty on top of damages only when the requester gives its amount
- The court with jurisdiction and the signing date
- A term the request is silent on takes its customary value, written out: oral disclosures confirmed in writing within 30 days, the agreement in force 5 years, the duty surviving 3 years after it ends, information returned or destroyed within 10 days

## Clauses

- `purpose` 제1조 (협약의 목적): `purpose`, written as information each side gives the other
- `definition` 제2조 (비밀정보의 정의)
- `marking` 제3조 (비밀의 표시): `oralConfirmationDays`
- `term` 제4조 (비밀 유지 기간 등): `termYears`, `survivalYears`
- `use` 제5조 (정보의 사용용도 및 정보취급자 제한)
- `confidentialityDuty` 제6조 (비밀유지의무): the six exclusions, item 5 being information never marked or announced as confidential
- `damages` 제7조 (손해배상, 위약벌): damages; `penaltyAmount` adds the penalty paragraph
- `returnOfInformation` 제8조 (비밀정보의 반환 등): `returnDays`
- `noRights` 제9조 (권리의 부존재 등)
- `assignment` 제10조 (권리의무의 양도, 협약의 변경)
- `severability` 제11조 (협약의 분리가능성)
- `disputes` 제12조 (분쟁의 해결): mediation first, then `jurisdiction`
- `supplementary` 제13조 (보칙)

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
  "oralConfirmationDays": "<number>",
  "termYears": "<number>",
  "survivalYears": "<number>",
  "penaltyAmount": "<penalty amount, or an empty string when there is none>",
  "returnDays": "<number>",
  "jurisdiction": "<court with jurisdiction>",
  "contractDate": "<YYYY년 M월 D일>"
}
```

```json
{
  "command": "<skill>/scripts/office merge kr/nda context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/nda"
}
```

## Rules

- Never fix 갑 or 을 as the disclosing or receiving party on your own. A one-way agreement replaces `purpose` to name who discloses.
- Party details not received stay empty strings; never invent an address, representative or court.
- Say in one line of the reply that delivers it that this is a draft for legal review.
