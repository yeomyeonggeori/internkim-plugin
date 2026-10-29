---
name: internkim-task
description: Add, find, update, or complete weekly work items when the user asks to add, record, request, find, change, or complete work, todos, 업무, deadlines, or task notes.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "task_add task_list task_board_get task_update task_delete task_vocabulary_set person_list"
---

# 업무 관리

Use the typed work capability operations for work items; descriptors define fields and results, and the runtime supplies identity and approval. In Korean replies, do not call the product `Flow` unless the user explicitly uses that English name.

## Routing and workflow

- "This week's board" or a week's view, carry-over included, is `task_board_get`. History and reports are `task_list`.
- Decide by intent, not by the noun used. Deliverables, deadlines, todos, requests, handoffs, and completion targets are work. Meetings, appointments, attendance blocks, locations, and time blocks are calendar events.
- A deadline-driven deliverable uses `task_add` and, when a due time belongs on the calendar, `event_add` too. Completion uses `task_update`, not `event_update`.
- Business, type and size follow the `task_add` and `task_update` descriptors: a label comes from `registeredLabels` (call `task_list` when it is not in context), and whatever is left out of a new task the record decides. In the reply, use the result's `type`; an empty one renders as the localized `기타`.
- A label the record refuses as unregistered: when it was your own choice, leave it out and write the work without it. When the requester named it, an administrator adds it with `task_vocabulary_set`, sending each current list back whole with the new label, then applies it; for anyone else, do the rest of the request without it and say an administrator must register the label first.
- Add work directly only to the requester's own list. Work for another person is a `요청`. Include the requester as a participant only when joint work is implied.
- When the runtime answers a person with candidates, the user chooses, never you. Never drop an unresolved person and record the work without them: that answers a different request than the one that was made.

## Replies and failures

Report successful created, updated, or listed work as a Markdown table with exactly these columns, one row per task: `상태 | 업무 | 유형 | 크기 | 참여자`. `업무` is the task title. Status values in results are canonical English (planned, in_progress, completed, requested, paused, rejected, stopped); write them in the user's language in the table (Korean: 예정, 진행, 완료, 요청, 일시정지, 기각, 중단). `참여자` is the participant's `displayName`, falling back to the participant name. Write people as plain names everywhere; platform handles never appear in replies. To actually notify someone, write `@` plus their display name (the result's `mention` value) — the runtime resolves it to the platform's own mention. Translate the headers only when replying in another language. Task IDs, week codes, content, and business labels stay out of the table; give one in prose only when the user asks for it. If an owner is ambiguous, show the returned candidates by name; if an operation fails, explain it honestly and do not fabricate a task.
