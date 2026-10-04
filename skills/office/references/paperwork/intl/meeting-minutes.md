# Meeting Minutes

output: pdf
filename: meeting-minutes_<meeting-name-slug>_<YYYYMMDD>.pdf

## Purpose

An internal record of what was discussed and decided in a meeting, kept so attendees and absent stakeholders have a shared, accurate account. The meeting name, date, attendees, and decisions must be confirmed facts, not summarized from assumption.

## Required fields

- meta: meeting name, date and time, location, attendees, recorded by
- sections: 1. Agenda, 2. Discussion, 3. Decisions (bullets), 4. Action items (items table: Item, Owner, Due date)
- signature: recorded-by, stamp false

## Document JSON skeleton

```json
{
  "form": "intl/meeting-minutes",
  "title": "Meeting Minutes",
  "documentNumber": "<the number company_document_register returned>",
  "meta": [
    { "label": "Meeting", "value": "<meeting name>" },
    { "label": "Date and time", "value": "<YYYY-MM-DD, HH:MM–HH:MM>" },
    { "label": "Location", "value": "<location or call link>" },
    { "label": "Attendees", "value": "<name1, name2, name3>" },
    { "label": "Recorded by", "value": "<name>" }
  ],
  "sections": [
    { "title": "1. Agenda", "paragraphs": ["<agenda summary>"] },
    { "title": "2. Discussion", "paragraphs": ["<discussion summary>"] },
    { "title": "3. Decisions", "bullets": ["<decision 1>", "<decision 2>"] }
  ],
  "items": {
    "headers": ["Item", "Owner", "Due date"],
    "aligns": ["L", "L", "L"],
    "rows": [["<action item>", "<owner>", "<YYYY-MM-DD>"]]
  },
  "signature": { "date": "<Month D, YYYY>", "line": "Recorded by <name>", "stamp": false }
}
```

## Fixed wording

- Section 4 title "Action items" is rendered by the items table itself; keep the preceding section 3 ("Decisions") as bullets, not a table.
- If no action items were assigned, omit the `items` field rather than leaving an empty table.

## Rules

- Do not set `approvalLine` for this document; meeting minutes are a record, not an approval request.
- Attendees must list only people actually confirmed present; do not add people who were invited but did not attend.
- Keep decisions and action items separated: decisions are outcomes agreed upon, action items are follow-up work with an owner and due date.
