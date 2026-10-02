# Offer Letter (채용 오퍼레터)

output: docx
filename: 오퍼레터_<candidate name>_<YYYYMMDD>.docx

## Purpose

An external document offering a position and its compensation to a candidate the company has decided to hire. It is made from the BUNDLED template (`offer-letter`). Only the context JSON values need filling.

## Required fields (confirm with the requester)

- Candidate name, position, department, workplace, expected start date
- Compensation: annual salary, stock options (if any), list of benefits
- Offer expiry date (expiryDate), sending date (offerDate)
- Whether there is a probation period (if so, the wording of its terms)

## Included clauses (already in the template)

- Greeting paragraph: "{candidateName}님께, 안녕하세요..." and the purpose of the offer
- Position summary: position / department / workplace / expected start date
- Compensation: annual salary; a filled `equity` adds the stock option sentence
- Benefits: the `benefits` list, item by item
- Probation: a paragraph only when `probationNote` is filled
- Offer terms: the offer expiry date (`expiryDate`) and a request to reply
- Closing greeting + sending date (`offerDate`) + company name + 대표이사 (`representative`)

## Context JSON skeleton

```json
{
  "companyName": "<company name>",
  "representative": "<representative name>",
  "candidateName": "<candidate name>",
  "position": "<position>",
  "department": "<department>",
  "workplace": "<workplace>",
  "startDate": "<YYYY-MM-DD>",
  "salary": "<annual salary>",
  "expiryDate": "<offer expiry date YYYY-MM-DD>",
  "offerDate": "<sending date YYYY-MM-DD>",
  "equity": "<stock option terms, or an empty string when there are none>",
  "probationNote": "<probation notice, or an empty string when there is none>",
  "benefits": ["<benefit 1>", "<benefit 2>"]
}
```

```json
{
  "command": "<skill>/scripts/office paperwork fill offer-letter context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/offer-letter"
}
```

## Context value check (self-check before delivery)

- Do the candidate name, position, department, workplace and expected start date match the request exactly?
- Are the salary and stock option figures only the requester's values, with no customary figure guessed in?
- Is `benefits` non-empty? (`paperwork fill` refuses an empty list)
- Are `expiryDate` and `offerDate` the dates the requester set? When none was set, was the requester asked rather than a date filled in?

## Rules

- Never invent names, salary, dates or terms. When required information is missing, ask the requester.
- Fill `equity`/`probationNote` only when the requester actually gave them; otherwise leave an empty string so the paragraph drops out.
- When the workplace, position or start date is not settled, write the unsettled state into the value itself, such as "추후 확정" (to be confirmed), instead of leaving the field empty.
