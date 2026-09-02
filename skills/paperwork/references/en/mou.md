# Memorandum of Understanding (MOU)

output: docx
filename: MOU_<counterparty>_<YYYYMMDD>.docx

## Purpose

Documents the intent of two organizations or companies to cooperate in a given area. Make clear this records an intent to collaborate rather than a binding contract of specific rights and obligations.

## Required fields

- parties: organization name, address, and representative for both parties
- purpose: purpose of the cooperation
- cooperationAreas: at least two specific areas of cooperation
- term: term of the memorandum, notice period for termination
- date, signatures of both parties

## Document JSON skeleton

```json
{
  "title": "Memorandum of Understanding",
  "fontName": "맑은 고딕",
  "fontSize": 10.5,
  "page": { "marginInches": 0.9 },
  "blocks": [
    { "type": "paragraph", "text": "This Memorandum of Understanding (this \"MOU\") is entered into by and between <Party A name> (\"Party A\") and <Party B name> (\"Party B\") for the purpose of <purpose of cooperation>." },
    { "type": "heading", "level": 1, "text": "1. Purpose" },
    { "type": "paragraph", "text": "This MOU sets out the basic terms under which Party A and Party B intend to cooperate in order to achieve <purpose of cooperation>." },
    { "type": "heading", "level": 1, "text": "2. Areas of Cooperation" },
    { "type": "paragraph", "text": "The parties intend to cooperate in the following areas." },
    { "type": "bullets", "items": ["<area of cooperation 1>", "<area of cooperation 2>", "<area of cooperation 3>"] },
    { "type": "heading", "level": 1, "text": "3. Roles" },
    { "type": "paragraph", "text": "Party A will <Party A's role> and Party B will <Party B's role>. Detailed execution plans and schedules will be agreed separately by the parties." },
    { "type": "heading", "level": 1, "text": "4. Confidentiality" },
    { "type": "paragraph", "text": "Each party shall keep confidential any information of the other party learned in the course of this MOU and shall not disclose it to any third party or use it outside the purpose of this MOU without the other party's prior written consent." },
    { "type": "heading", "level": 1, "text": "5. Term and Termination" },
    { "type": "paragraph", "text": "This MOU is effective for <n> years from the date of execution and may be renewed by mutual agreement. Either party may terminate this MOU by giving <m> days' prior written notice to the other party." },
    { "type": "heading", "level": 1, "text": "6. Non-Binding Effect" },
    { "type": "paragraph", "text": "This MOU records the parties' intent to cooperate. Except for Article 4, the provisions of this MOU are not legally binding, and any specific rights or obligations will be set out in a separate definitive agreement between the parties." },
    { "type": "heading", "level": 1, "text": "7. General" },
    { "type": "paragraph", "text": "Any matter not addressed in this MOU shall be resolved through mutual consultation between the parties." },
    { "type": "paragraph", "text": "IN WITNESS WHEREOF, the parties have executed this MOU in duplicate, each party retaining one signed copy." },
    { "type": "paragraph", "text": "<Month D, YYYY>" },
    { "type": "table", "columnWidthsInches": [1.2, 2.7, 2.7], "rows": [
      ["", "Party A", "Party B"],
      ["Organization", "<Party A name>", "<Party B name>"],
      ["Address", "<Party A address>", "<Party B address>"],
      ["Representative", "<Party A representative>", "<Party B representative>"]
    ] }
  ]
}
```

## Fixed wording

- Execution sentence: "IN WITNESS WHEREOF, the parties have executed this MOU in duplicate, each party retaining one signed copy."
- Article 6 (non-binding effect) is a standard MOU clause and must always be included.

## Rules

- List cooperation areas specifically; do not invent areas the requester did not mention.
- Never invent party names, addresses, amounts, durations, or governing law — use only requester-provided facts, and ask when any are missing.
- This document is a draft for legal review; say so when delivering it.
