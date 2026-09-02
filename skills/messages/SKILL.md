---
name: messages
description: Read, search, post, update, and delete messages in the current conversation, and inspect the conversation a request arrived on. Use for chat, 채팅, 메시지, channel, thread, or team requests, and for leaving, editing, or removing a visible note in the current conversation (대화/스레드에 메모·노트 남기기, posted with message_send).
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "message_context message_search message_send message_update message_delete"
---

# Messages

Call the typed message operations directly; descriptors define exact fields and results. Use the returned IDs as the only basis for later reads, edits, or deletes. A company runs one messenger and the host is configured with its name, so no operation takes a platform.

## Read and search

- Use `message_context` when the request arrived on a conversation and the channel, thread, or requester is needed. Use `message_search` for channel, person, text, and date clues, then use the observed message IDs for follow-up actions.
- Distinguish no result, an ambiguous match, and a provider error. Never infer a message ID or claim unseen content.

## Write

- Use `message_send` for a new message and `message_update` only with an observed message ID. Do not duplicate a successful post.
- Use `message_delete` only when the user explicitly requests deletion; approval is handled by the runtime.
- Addressing a person rather than a conversation is the direct-message workflow.

## Reporting

Report successful posts, edits, and deletes only after the operation succeeds. For history, summarize observed messages with channel and timestamp context, and keep pagination or approval failures visible.
