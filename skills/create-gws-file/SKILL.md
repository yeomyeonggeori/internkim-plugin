---
name: create-gws-file
description: Create Google Docs, Sheets, or Gmail messages through typed Google Workspace capability operations when those optional operations are available. Use document, spreadsheet, mail, or presentation for local artifacts or when the Google operations are unavailable.
compatibility: Requires InternKim's tool server with a connected Google account.
tool-references: google_docs_create google_sheets_create google_gmail_send
---

# Google Workspace Files

Use this skill only when every referenced Google Workspace operation is available. Call the named operation directly; its descriptor defines input fields and results. Blueclaw does not read API keys, service-account JSON, OAuth exports, webhook URLs, or other Google credentials.

## Routing

- Google Docs: `google_docs_create`
- Google Sheets: `google_sheets_create`
- Gmail: `google_gmail_send`
- Calendar: use the `calendar` skill.
- Slide decks or Google Slides: use the `presentation` skill.

## Rules

- Do not use `gws`, service-account wrappers, shell scripts, or credential files.
- Sharing and editing policy belongs to the capability provider.
- Do not claim a URL exists until the operation returns it.
- If credentials are missing, tell the user to install Google Workspace credentials through setup or Companion.
