# Certificate of Employment

output: pdf
filename: Certificate_of_Employment_<full-name>_<YYYYMMDD>.pdf

## Purpose

A document confirming that a named individual is currently employed by the company, issued for the employee to submit to a bank, embassy, agency, or other third party. Confirm the intended purpose with the requester when possible.

## Required fields

- meta: full name, date of birth, department, title, employment period, purpose
- Employment period is written as start date to "present" — the person must still be employed (use career-certificate.md for a former employee)
- signature: issue date + "<company name>, <representative name>, Representative", stamp true

## Document JSON skeleton

```json
{
  "form": "intl/employment-certificate",
  "title": "Certificate of Employment",
  "documentNumber": "<the number company_document_register returned>",
  "company": "<the company-profile.json path company_info_get answered>",
  "meta": [
    { "label": "Full name", "value": "<full name>" },
    { "label": "Date of birth", "value": "<YYYY-MM-DD>" },
    { "label": "Department", "value": "<department>" },
    { "label": "Title", "value": "<title>" },
    { "label": "Employment period", "value": "<start date> to present" },
    { "label": "Purpose", "value": "<submission purpose>" }
  ],
  "notes": ["This is to certify that the above-named person is employed by the company."],
  "signature": { "date": "<Month D, YYYY>", "line": "<company name>, <representative name>, Representative", "stamp": true },
  "footer": "This certificate confirms employment status as of the date of issue."
}
```

## Fixed wording

- notes: "This is to certify that the above-named person is employed by the company."
- The employment period end must always read "present" — never issue this certificate for someone who has already left the company.

## Rules

- Do not include salary, contract terms, or performance information; this document certifies employment status only.
