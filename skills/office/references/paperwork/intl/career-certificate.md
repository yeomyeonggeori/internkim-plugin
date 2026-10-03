# Certificate of Employment History

output: pdf
filename: Certificate_of_Employment_History_<full-name>_<YYYYMMDD>.pdf

## Purpose

A document confirming that a named individual was employed by the company during a defined past period, issued for a former employee to submit to a new employer, agency, or other third party. Unlike the current-employment certificate, the employment period here is closed.

## Required fields

- meta: full name, date of birth, department, title, duties, employment period, purpose
- Employment period is written as a closed start-to-end range — never "present" (that belongs on the employment-certificate)
- signature: issue date + "<company name>, <representative name>, Representative", stamp true

## Document JSON skeleton

```json
{
  "form": "intl/career-certificate",
  "title": "Certificate of Employment History",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "Full name", "value": "<full name>" },
    { "label": "Date of birth", "value": "<YYYY-MM-DD>" },
    { "label": "Department", "value": "<department>" },
    { "label": "Title", "value": "<title>" },
    { "label": "Duties", "value": "<duties performed>" },
    { "label": "Employment period", "value": "<start date> to <end date>" },
    { "label": "Purpose", "value": "<submission purpose>" }
  ],
  "notes": ["This is to certify that the above-named person was employed by the company as described above."],
  "signature": { "date": "<Month D, YYYY>", "line": "<company name>, <representative name>, Representative", "stamp": true },
  "footer": "This certificate confirms the employment history described above."
}
```

## Fixed wording

- notes: "This is to certify that the above-named person was employed by the company as described above."
- The employment period must always show a definite end date; never leave it open-ended.

## Rules

- Never invent names, amounts, durations, or governing law — use requester-provided facts and ask when full name, date of birth, department, title, duties, start date, end date, or purpose is missing.
- Do not include reason for departure, performance evaluation, or salary; this document certifies employment history only.
