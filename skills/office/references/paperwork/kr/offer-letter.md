# Offer Letter (채용 오퍼레터)

output: docx
filename: 오퍼레터_<candidate name>_<YYYYMMDD>.docx

## Purpose

An external letter offering a position and its compensation to a candidate the company has decided to hire, made from the bundled `offer-letter` template. `references/paperwork.md` says how a requested section replaces or joins the template's.

## Required terms (confirm with the requester)

- Candidate name, position, department, workplace, expected start date
- Compensation: annual salary, stock options (if any), benefits
- Offer expiry date (`expiryDate`) and sending date (`offerDate`)
- Probation terms, when there is a probation period

## Clauses

- `position` 포지션 요약: position, department, workplace, start date
- `compensation` 보상: salary; a filled `equity` adds the stock option line
- `benefits` 복리후생: `benefits`; a filled `probationNote` adds its paragraph
- `conditions` 제안 조건: `expiryDate`, confirmation after a background check

## Context JSON skeleton

```json
{
  "form": "kr/offer-letter",
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
  "command": "<skill>/scripts/office merge kr/offer-letter context.json <storageDirectory>/<filename>.docx",
  "workingDirectoryPath": "tmp/offer-letter"
}
```

## Rules

- When the workplace, position or start date is not settled, write the unsettled state into the value itself, such as "추후 확정" (to be confirmed).
