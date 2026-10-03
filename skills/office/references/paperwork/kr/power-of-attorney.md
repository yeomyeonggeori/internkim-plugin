# Power of Attorney (위임장)

output: pdf
filename: 위임장_<agent name>_<YYYYMMDD>.pdf

## Purpose

An external document proving that the principal (위임인) entrusts the agent (수임인) with exercising particular powers. The delegated matters must be listed as concrete items, never written as a blanket grant.

## Required fields

- meta: the principal (name, date of birth or business registration number, address), the agent (name, date of birth, address, phone), 위임기간 (period of delegation)
- sections: 위임 사항 (delegated matters, bullets, one concrete act each)
- notes: "위와 같이 위 사람에게 권한을 위임합니다."
- signature: the principal, stamp true

## Document JSON skeleton

```json
{
  "form": "kr/power-of-attorney",
  "title": "위 임 장",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "위임인 성명", "value": "<principal name>" },
    { "label": "위임인 생년월일/사업자번호", "value": "<YYYY-MM-DD, or the business registration number>" },
    { "label": "위임인 주소", "value": "<principal address>" },
    { "label": "수임인 성명", "value": "<agent name>" },
    { "label": "수임인 생년월일", "value": "<YYYY-MM-DD>" },
    { "label": "수임인 주소", "value": "<agent address>" },
    { "label": "수임인 연락처", "value": "<agent phone>" },
    { "label": "위임기간", "value": "<YYYY-MM-DD> ~ <YYYY-MM-DD>" }
  ],
  "sections": [
    { "title": "위임 사항", "bullets": ["<concrete act delegated 1>", "<concrete act delegated 2>", "<concrete act delegated 3>"] }
  ],
  "notes": ["위와 같이 위 사람에게 권한을 위임합니다."],
  "signature": { "date": "<YYYY년 M월 D일>", "line": "위임인 <name> (인)", "stamp": true }
}
```

## Fixed wording

- notes: "위와 같이 위 사람에게 권한을 위임합니다."
- Space the title's characters apart: "위 임 장".

## Rules

- Never write the delegated matters as a blanket grant such as "일체의 권한을 위임함" (all powers delegated); list item by item, concretely, the acts the principal actually wants to entrust.
- Use only the names, dates of birth, addresses, phones, period and delegated matters of the principal and agent that the requester gave; never invent them, and ask the requester when one is missing.
- When the period of delegation is missing, never invent an end date; ask the requester.
