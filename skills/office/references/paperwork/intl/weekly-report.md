# Weekly Report

output: pdf
filename: weekly-report_<author>_<YYYYMMDD>.pdf

## Purpose

An internal status document summarizing one person's or team's work for a given week, submitted to a manager or team for visibility. The reporting period and the content of each section must reflect only what the requester actually reports.

## Required fields

- meta: author, team, reporting period
- sections: 1. Completed this week (bullets), 2. In progress, 3. Planned next week, 4. Issues and requests
- signature: author, stamp false

## Document JSON skeleton

```json
{
  "form": "intl/weekly-report",
  "title": "Weekly Report",
  "documentNumber": "<the number company_document_register returned>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "Author", "value": "<name>" },
    { "label": "Team", "value": "<team>" },
    { "label": "Reporting period", "value": "<YYYY-MM-DD to YYYY-MM-DD>" }
  ],
  "sections": [
    { "title": "1. Completed this week", "bullets": ["<item 1>", "<item 2>"] },
    { "title": "2. In progress", "paragraphs": ["<in-progress work summary>"] },
    { "title": "3. Planned next week", "paragraphs": ["<plan for next week>"] },
    { "title": "4. Issues and requests", "paragraphs": ["<blockers, risks, or requests for help>"] }
  ],
  "signature": { "date": "<Month D, YYYY>", "line": "<author name>", "stamp": false }
}
```

## Fixed wording

- None; all section content is requester-specific. Keep "1. Completed this week" as bullets and the remaining sections as paragraphs unless the requester supplies bullet-style content for those too.

## Rules

- The reporting period must match the actual week being reported on; do not assume it is the current calendar week without confirming with the requester.
- If section 4 has nothing to report, write "None this week" rather than omitting the section.
- Do not set `approvalLine`; this is a status report, not an approval request.
