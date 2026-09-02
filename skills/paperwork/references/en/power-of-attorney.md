# Power of Attorney

output: pdf
filename: Power_of_Attorney_<agent-name>_<YYYYMMDD>.pdf

## Purpose

A document by which a principal grants a named agent authority to act on the principal's behalf for specific matters. The delegated powers must be enumerated item by item, never granted as a blanket authorization.

## Required fields

- meta: principal (name, ID or registration number, address), attorney-in-fact/agent (name, date of birth, address, contact), effective period
- sections: delegated powers (bullets, each a specific act, not a general grant)
- notes: "I hereby grant the powers described above to the person named."
- signature: principal, stamp true

## Document JSON skeleton

```json
{
  "title": "POWER OF ATTORNEY",
  "documentNumber": "POA-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "Principal's name", "value": "<principal name>" },
    { "label": "Principal's ID / registration number", "value": "<ID number or business registration number>" },
    { "label": "Principal's address", "value": "<principal address>" },
    { "label": "Agent's name", "value": "<agent name>" },
    { "label": "Agent's date of birth", "value": "<YYYY-MM-DD>" },
    { "label": "Agent's address", "value": "<agent address>" },
    { "label": "Agent's contact", "value": "<agent phone or email>" },
    { "label": "Effective period", "value": "<YYYY-MM-DD> to <YYYY-MM-DD>" }
  ],
  "sections": [
    { "title": "Delegated Powers", "bullets": ["<specific delegated act 1>", "<specific delegated act 2>", "<specific delegated act 3>"] }
  ],
  "notes": ["I hereby grant the powers described above to the person named."],
  "signature": { "date": "<Month D, YYYY>", "line": "Principal: <principal name> (seal)", "stamp": true }
}
```

## Fixed wording

- notes: "I hereby grant the powers described above to the person named."
- title is always "POWER OF ATTORNEY" in uppercase.

## Rules

- Never write the delegated powers as a blanket grant such as "full authority for all matters"; enumerate each specific act the principal actually intends to delegate.
- Never invent names, amounts, durations, or governing law — use requester-provided facts and ask when the principal's name, agent's name, ID or registration number, address, delegated powers, or effective period is missing.
- If the effective period is not given, do not invent an expiration date; ask the requester.
