---
name: mail
description: Read, search, send, and manage email through the connected mail provider. Use for email, inbox, Gmail, 메일, 이메일, 받은편지함, or sending a message by email.
compatibility: Requires InternKim's tool server with a connected mail account.
metadata:
  kim.intern.tool-references: "mail_connection_status mail_connection_start mail_message_list mail_message_search mail_message_read mail_message_send mail_mailbox_list mail_message_mark mail_message_move"
---

# Mail

Use the typed mail operations directly; descriptors define exact fields and result shapes.

## Read and search

- Use `mail_connection_status` before mail access when connection state is unknown. If mail is not connected, use `mail_connection_start` to begin setup.
- Use `mail_message_list` for recent messages and `mail_message_search` for sender, recipient, subject, date, or text queries. Search before reading when the user names a message but not its ID.
- Use `mail_message_read` for the mailbox and UID returned by a successful search. Summarize only observed content and distinguish quoted text from the newest message.

## Sort

- Marking read or starred is `mail_message_mark`; archiving or filing is `mail_message_move`, into a folder `mail_mailbox_list` shows.

## Send

- Use `mail_message_send` only when the user supplies a recipient and message intent. Preserve the requested subject and body; do not invent addresses or attachments.
- Let the runtime handle approval where required. Do not claim delivery until the operation succeeds.

## Failure handling

If a search returns no result, say so and ask for a narrower or corrected hint. If several messages match, ask which one; do not guess. Report provider failures honestly without fabricating a sent message or unread content.
