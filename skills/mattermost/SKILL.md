---
name: mattermost
description: Read, search, post, update, and delete Mattermost messages, manage channels, and inspect approved workspace conversations. Use for Mattermost, chat, 채팅, 메시지, channel, or team requests, and for leaving, editing, or removing a visible note in the current conversation (대화/스레드에 메모·노트 남기기, posted with message_send).
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "message_context message_search message_send message_update message_delete channel_update"
---

# Mattermost

Call the typed Mattermost operations directly; descriptors define exact fields and results. Use the returned IDs as the only basis for later reads, edits, or deletes.

## Read and search

- Use `message_context` when the current Mattermost conversation supplies the channel, thread, or requester context. Use `message_search` for channel, person, text, and date clues, then use the observed message IDs for follow-up actions.
- Distinguish no result, an ambiguous match, and a provider error. Never infer a message ID or claim unseen content.

## Write and manage

- Use `message_send` for a new message and `message_update` only with an observed message ID. Do not duplicate a successful post.
- Use `message_delete` only when the user explicitly requests deletion; approval is handled by the runtime.
- Use `channel_update` for supported channel changes. Preserve existing names and membership unless the request says otherwise.

## Reporting

Report successful posts, edits, deletes, and channel changes only after the operation succeeds. For history, summarize observed messages with channel and timestamp context, and keep pagination or approval failures visible.
