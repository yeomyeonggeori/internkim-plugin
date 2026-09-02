# Offer Letter

output: docx
filename: Offer_Letter_<candidate-name>_<YYYYMMDD>.docx

## Purpose

An editable outbound document proposing a role and compensation package to a confirmed candidate, laid out for easy review and reply.

## Required fields

- Candidate name, position title, department, work location, start date
- Compensation: base salary, equity (if any), benefits
- Employment basis (at-will or fixed-term, per the requester's jurisdiction), offer expiration date

## Document JSON skeleton

```json
{
  "title": "Offer Letter",
  "fontName": "Noto Sans",
  "fontSize": 10.5,
  "page": { "marginInches": 0.9 },
  "blocks": [
    { "type": "paragraph", "text": "Dear <candidate name>, we are delighted to extend the following offer to join <company name>." },
    { "type": "heading", "level": 2, "text": "Position Summary" },
    {
      "type": "table",
      "columnWidthsInches": [1.8, 4.2],
      "rows": [
        ["Item", "Detail"],
        ["Title", "<position title>"],
        ["Department", "<department>"],
        ["Location", "<work location>"],
        ["Start date", "<YYYY-MM-DD>"]
      ]
    },
    { "type": "heading", "level": 2, "text": "Compensation and Benefits" },
    {
      "type": "table",
      "columnWidthsInches": [1.8, 4.2],
      "rows": [
        ["Item", "Detail"],
        ["Base salary", "<base salary amount>"],
        ["Equity", "<equity grant or not applicable>"],
        ["Benefits", "<benefits summary>"]
      ]
    },
    { "type": "heading", "level": 2, "text": "Terms" },
    { "type": "paragraph", "text": "This offer is contingent on <background check / other conditions> and, where applicable under <jurisdiction> law, employment is <at-will / for a fixed term of <duration>>." },
    { "type": "paragraph", "text": "This offer remains open through <expiration date>. Please let us know your decision by <reply-by date>." },
    { "type": "paragraph", "text": "We are excited about the possibility of you joining the team." },
    { "type": "paragraph", "text": "<company name>\n<representative name>, <representative title>" },
    { "type": "heading", "level": 2, "text": "Acceptance" },
    {
      "type": "table",
      "columnWidthsInches": [3.0, 3.0],
      "rows": [
        ["Company", "Candidate"],
        ["Signature: ____________________", "Signature: ____________________"],
        ["Date: ____________________", "Date: ____________________"]
      ]
    }
  ]
}
```

## Fixed wording

- Opening and closing lines follow the example wording above unless the requester specifies a different tone.
- The employment-basis sentence (at-will vs. fixed-term) must match the requester's stated jurisdiction; do not default to "at-will" for a jurisdiction where that concept does not apply.

## Rules

- Never invent salary figures, equity numbers, dates, or terms — use only requester-provided facts and ask when a required field is missing.
- If location, title, or start date is not yet finalized, mark it explicitly as "to be confirmed" rather than guessing.
- This is a draft for review; final legal and compliance review before sending is the company's responsibility.
