---
name: direct-message
description: Send or schedule direct messages to approved workspace people through message.send.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "message_send schedule_create"
---

# Direct Message

Call `message_send` directly with the recipient hint and message; its descriptor defines the remaining fields and result. The task is complete after one successful observation: do not send another message in the same task.

## Approval

The runtime confirms messages to someone else automatically; do not ask the user to confirm. Messages to the requester need no confirmation. Scheduled direct messages use `schedule_create` and do not require approval at run time.

## Workflow

1. Identify the person hint and exact message from the user's wording.
2. For an immediate message, call `message_send` with direct-message targeting.
3. For a future or recurring message, call `schedule_create` with a `taskInstruction` that names the person and message; use the scheduled-task workflow for current-conversation reminders.

If the operation reports a missing or ambiguous recipient, explain that resolution failed and ask for the missing distinction. Keep recipient resolution separate from approval language, and never claim delivery before success.
