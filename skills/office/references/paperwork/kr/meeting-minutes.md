# Meeting Minutes (회의록)

output: pdf
filename: 회의록_<meeting name>_<YYYYMMDD>.pdf

## Purpose

A record of the agenda, decisions and action items of a meeting. It is for recording and sharing, not for approval, so it has no approvalLine.

## Required fields

- meta: 회의명 (meeting name), 일시 (date and time), 장소 (place), 참석자 (attendees), 작성자 (author)
- sections: 안건 (agenda) / 논의 내용 (discussion) / 결정사항 (decisions, bullets) / 실행 항목 (action items)
- items: when there are action items, a table of item, owner and due date (omit when there are none)
- signature: the author, stamp false
- No approvalLine

## Document JSON skeleton

```json
{
  "form": "kr/meeting-minutes",
  "title": "회 의 록",
  "documentNumber": "MM-<YYYYMMDD>-<sequence>",
  "profile": { ...company profile... },
  "meta": [
    { "label": "회의명", "value": "<meeting name>" },
    { "label": "일시", "value": "<YYYY-MM-DD HH:MM>" },
    { "label": "장소", "value": "<place or video call link>" },
    { "label": "참석자", "value": "<name 1, name 2, ...>" },
    { "label": "작성자", "value": "<name>" }
  ],
  "sections": [
    { "title": "1. 안건", "bullets": ["<agenda item 1>", "<agenda item 2>"] },
    { "title": "2. 논의 내용", "paragraphs": ["<summary of the discussion per agenda item>"] },
    { "title": "3. 결정사항", "bullets": ["<decision 1>", "<decision 2>"] },
    { "title": "4. 실행 항목", "paragraphs": [] }
  ],
  "items": {
    "headers": ["항목", "담당", "기한"],
    "aligns": ["L", "L", "L"],
    "rows": [["<action item>", "<owner>", "<YYYY-MM-DD>"]]
  },
  "signature": { "date": "<YYYY년 M월 D일>", "line": "작성자 <name>", "stamp": false }
}
```

## Fixed wording

- None. Fill each section with a factual summary of the meeting.

## Rules

- Never add an approvalLine.
- When there are action items, write them as the items table (item, owner, due date) under section 4; with none, omit the items block.
- Use only the attendees, decisions, owners and due dates the requester gave; never invent missing information, ask the requester.
- Space the title's characters apart: "회 의 록".
